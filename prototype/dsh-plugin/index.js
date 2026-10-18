// dsh Blockbench Agent · Host 插件（设计参考骨架）
// 职责：
//   1) 启动/监管 Blockbench Agent Runtime（BAE），暴露本地 WebSocket JSON-RPC BridgeServer
//   2) 注册 bb_* 语义工具（只保留最小集合，其余按 docs/03 复制扩展）
//   3) 注册 /show /hide /bb-status 人类命令
//   4) 把渲染 PNG 通过 ctx.attachments 变成多模态图片块返回给模型
//
// 依赖：@deepseek-ai/dsh-tools（dsh 安装内解析）、node 内建模块、./ws-server.js（零依赖）
// 安装：plugin_manager.install_bundle(target = 本目录)；本地 link 安装需要重启 harness 载入新 JS。

import { defineTool } from '@deepseek-ai/dsh-tools'
import { createWsServer } from './ws-server.js'
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { randomBytes } from 'node:crypto'

export const name = 'blockbench-agent'
export const inject = ['tools', 'commands']

const DEFAULTS = {
  workspaceRoot: 'F:\\Deepseek_harness\\blockbench\\workspace',
  project: 'default',
  executable: '',          // 例如 F:\\...\\dist\\blockbench-agent\\BlockbenchAgent.exe
  appPath: '',             // 例如 F:\\...\\dist\\blockbench-agent\\resources\\app
  autoStart: true,
  connectTimeoutMs: 30000,
  defaultTimeoutMs: 120000,
}

function log(...args) { console.log('[blockbench-agent]', ...args) }

function toolText(value) {
  return [{ type: 'text', text: typeof value === 'string' ? value : JSON.stringify(value) }]
}

export function apply(ctx, config = {}) {
  const cfg = { ...DEFAULTS, ...config }
  const attachments = ctx.get?.('attachments')
  const state = {
    server: null,
    rpcUrl: '',
    token: '',
    child: null,
    connected: false,
    hello: null,
    workspace: path.resolve(cfg.workspaceRoot, cfg.project),
    ready: null,
    readyResolve: null,
    readyReject: null,
  }
  state.ready = new Promise((resolve, reject) => { state.readyResolve = resolve; state.readyReject = reject })
  state.ready.catch(() => {}) // 避免未处理拒绝

  // ------------------------------------------------------------ RPC server
  const server = createWsServer({
    token: randomBytes(32).toString('base64url'),
    defaultTimeoutMs: cfg.defaultTimeoutMs,
    methods: {
      'system.hello': (params) => {
        state.hello = params
        return {
          protocol: 'bb-agent/1',
          transport: 'ws',
          server: { name: 'bb-agent-runtime', version: '0.1.0-prototype', blockbench: '5.2.2' },
          capabilities: {
            render: { offscreen: true, transparent: true, max_size: 4096, antialias: ['off', 'msaa', 'ssaa'] },
            texture: { layers: true, max_size: 8192 },
            ysm: { spec: 2, models: ['main', 'arm'] },
            gui: { show: true },
            eval: false,
          },
          limits: { max_message_bytes: 8388608, max_batch: 64, max_patch_ops: 4096, max_inflight: 8 },
          session: { project_id: null, revision: 0, state: 'idle' },
        }
      },
    },
    onConnection: () => {
      state.connected = true
      log('Blockbench connected')
      state.readyResolve?.({ ok: true })
    },
    onNotification: (method, params) => {
      if (method === 'event.heartbeat') state.lastHeartbeat = { ...params, at: Date.now() }
      if (method === 'event.engine_degraded') log('engine degraded', params?.reason)
    },
  })
  state.server = server

  // ------------------------------------------------------------ runtime lifecycle
  async function startRuntime() {
    const { port } = await server.listen(0)
    state.token = server.token
    state.rpcUrl = `ws://127.0.0.1:${port}/bb-agent/v1`
    fs.mkdirSync(state.workspace, { recursive: true })
    fs.mkdirSync(path.join(state.workspace, 'logs'), { recursive: true })
    log(`bridge listening on ${state.rpcUrl}`)
    if (!cfg.executable || !cfg.appPath) {
      log('executable/appPath not configured; waiting for an external Blockbench to connect')
      return
    }
    const args = [
      cfg.appPath,
      `--workspace=${state.workspace}`,
      `--rpc-url=${state.rpcUrl}`,
      `--token=${server.token}`,
      `--plugin=${path.join(cfg.appPath, 'agent', 'bb-agent-bridge.js')}`,
      `--user-data=${path.join(state.workspace, '.bb', 'userdata')}`,
    ]
    state.child = spawn(cfg.executable, args, {
      cwd: cfg.appPath,
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, BB_AGENT_WORKSPACE: state.workspace },
    })
    state.child.stdout?.on('data', (d) => fs.appendFileSync(path.join(state.workspace, 'logs', 'agent.log'), d))
    state.child.stderr?.on('data', (d) => fs.appendFileSync(path.join(state.workspace, 'logs', 'agent.log'), d))
    state.child.on('exit', (code, signal) => {
      log(`runtime exited code=${code} signal=${signal}`)
      state.connected = false
    })
    await Promise.race([
      waitFor(() => state.connected, cfg.connectTimeoutMs),
      new Promise((_, reject) => setTimeout(() => reject(new Error('runtime connect timeout')), cfg.connectTimeoutMs)),
    ])
  }

  function waitFor(predicate, timeoutMs) {
    return new Promise((resolve, reject) => {
      const started = Date.now()
      const timer = setInterval(() => {
        if (predicate()) { clearInterval(timer); resolve(true) }
        else if (Date.now() - started > timeoutMs) { clearInterval(timer); reject(new Error('timeout')) }
      }, 100)
    })
  }

  if (cfg.autoStart) startRuntime().catch((error) => {
    log('startRuntime failed:', error?.message)
    state.readyReject?.(error)
  })

  async function call(method, params = {}, timeoutMs = cfg.defaultTimeoutMs) {
    await state.ready
    return server.request(method, params, { timeoutMs })
  }

  function errorResult(error) {
    const code = error?.rpc?.data?.code ?? error?.bbCode ?? 'INTERNAL_ERROR'
    const hint = error?.rpc?.data?.hint ?? ''
    return { ok: false, code, message: error?.message ?? String(error), hint }
  }

  // ------------------------------------------------------------ tools
  const tool = (definition) => ctx.tools.register(defineTool(definition))

  tool({
    name: 'bb_session_status',
    description: '查看 Blockbench 引擎状态、当前项目 revision、连接与健康信息；卡住或怀疑降级时先调用。',
    parameters: {},
    output: { schema: { type: 'object' }, render: (_args, value) => toolText(value) },
    async execute(_args, _exec) {
      if (!state.connected) return { ok: false, code: 'PROJECT_NOT_OPEN', hint: 'runtime not connected; check /bb-status' }
      try { return await call('session.status', {}, 5000) } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_scene',
    description: '读取压缩后的 Blockbench 场景信息：summary/bones/bone/cube/textures/animations；默认 summary，列表分页。',
    parameters: {
      scope: { type: 'string', description: 'summary|bones|bone|cube|textures|animations|uv', required: false },
      id: { type: 'string', description: 'scope=bone/cube 时的 id 或名字' },
      limit: { type: 'number', description: '分页大小 1-100' },
      include_uv: { type: 'boolean' },
    },
    output: { schema: { type: 'object' }, render: (_args, value) => toolText(value) },
    async execute(args, _exec) {
      try { return await call('project.get_scene', args) } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_apply_model_patch',
    description: '模型原子变更：骨骼/方块/UV/删除等一组 ops，一个事务与一个 revision。',
    parameters: {
      expected_revision: { type: 'number', description: '通常省略；冲突时用最新 revision 重试' },
      atomic: { type: 'boolean', description: '任一 op 失败整体回滚（默认 true）' },
      note: { type: 'string', description: '写入 Undo 标签的说明' },
      ops: { type: 'json', description: 'ops 数组，见 docs/03 §3.6', required: true },
    },
    output: { schema: { type: 'object' }, render: (_args, value) => toolText(value) },
    async execute(args, _exec) {
      try { return await call('model.apply_patch', args, 30000) } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_texture_patch',
    description: '按像素坐标绘制纹理：pixel/rect/line/shade/replace/clear/copy_mirror；一次调用一个 Undo 与 revision。',
    parameters: {
      expected_revision: { type: 'number' },
      texture: { type: 'string', description: '纹理名或 id；省略为当前激活纹理' },
      clip: { type: 'boolean', description: '越界像素裁剪（默认 true）' },
      note: { type: 'string' },
      ops: { type: 'json', description: '绘制 ops 数组，见 docs/03 §3.8', required: true },
    },
    output: { schema: { type: 'object' }, render: (_args, value) => toolText(value) },
    async execute(args, _exec) {
      try { return await call('texture.apply_patch', args, 60000) } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_render_views',
    description: '用固定机位无头渲染当前模型；默认透明背景、768px、front/right/iso_fr 三视图，图片作为附件返回。',
    parameters: {
      views: { type: 'array', description: '机位：front/back/left/right/top/bottom/iso_fr/iso_fl/iso_br/iso_bl', required: false },
      size: { type: 'array', description: '[w,h]，默认 [768,768]' },
      transparent: { type: 'boolean' },
      antialias: { type: 'string', description: 'off|msaa|ssaa' },
      attach_images: { type: 'boolean', description: '是否附图（默认 true，最多 4 张）' },
    },
    output: {
      schema: { type: 'object' },
      render: (_args, value) => {
        if (!value || value.ok === false) return toolText(value ?? 'render failed')
        const summary = {
          revision: value.revision,
          views: value.images.map((i) => i.view),
          images: value.images.map((i) => ({ view: i.view, path: i.path, bytes: i.bytes })),
        }
        const blocks = [{ type: 'text', text: JSON.stringify(summary) }]
        for (const img of value.images ?? []) {
          if (img.attachment) blocks.push({ type: 'image', attachment: img.attachment })
        }
        return blocks
      },
    },
    async execute(args, exec) {
      try {
        const result = await call('render.views', args, 120000)
        if (!attachments) return result
        const images = []
        for (const img of (result.images ?? []).slice(0, 4)) {
          try {
            const bytes = fs.readFileSync(img.workspace_path)
            const attachment = await attachments.saveImage({ data: bytes, mediaType: 'image/png', name: `${img.view}.png` })
            images.push({ ...img, attachment })
          } catch (error) {
            images.push(img)
          }
        }
        return { ...result, images }
      } catch (error) {
        return errorResult(error)
      }
    },
  })

  tool({
    name: 'bb_validate',
    description: '按 YSM 规范校验当前项目；导出前必须调用，返回 errors/warnings 与修复提示。',
    parameters: {
      profile: { type: 'string', description: 'ysm|generic' },
      strict: { type: 'boolean' },
    },
    output: { schema: { type: 'object' }, render: (_args, value) => toolText(value) },
    async execute(args, _exec) {
      try { return await call('project.validate', args, 30000) } catch (error) { return errorResult(error) }
    },
  })

  // ------------------------------------------------------------ commands
  ctx.commands.register({
    name: 'show',
    description: '显示后台 Blockbench 窗口，交给你检查/手动修改',
    handler: async () => {
      try {
        const result = await call('gui.show', { mode: 'inspect' }, 10000)
        return { kind: 'success', text: `Blockbench 已显示（revision ${result.revision}）。编辑完成后输入 /hide 返回。` }
      } catch (error) {
        return { kind: 'error', text: `显示失败：${error?.message ?? error}` }
      }
    },
  })
  ctx.commands.register({
    name: 'hide',
    description: '隐藏 Blockbench 窗口，把控制权还给 Agent',
    handler: async () => {
      try {
        const result = await call('gui.hide', { resync: true }, 15000)
        return { kind: 'success', text: `Blockbench 已隐藏（revision ${result.revision}）。` }
      } catch (error) {
        return { kind: 'error', text: `隐藏失败：${error?.message ?? error}` }
      }
    },
  })
  ctx.commands.register({
    name: 'bb-status',
    description: '查看 Blockbench Agent 连接与运行状态',
    handler: async () => {
      try {
        if (!state.connected) return { kind: 'success', text: `未连接。rpc=${state.rpcUrl || '(not started)'}` }
        const result = await call('session.status', {}, 5000)
        return { kind: 'success', text: JSON.stringify(result) }
      } catch (error) {
        return { kind: 'error', text: `查询失败：${error?.message ?? error}` }
      }
    },
  })

  // ------------------------------------------------------------ cleanup
  ctx.effect(() => () => {
    log('disposing blockbench-agent')
    try { state.child?.kill('SIGTERM') } catch { /* ignore */ }
    try { state.child?.kill('SIGKILL') } catch { /* ignore */ }
    void server.close()
  })
}
