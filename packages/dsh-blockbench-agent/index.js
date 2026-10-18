// dsh Blockbench Agent · Host 插件（工程实现 v0.1）
// 职责：
//   1) 启动/监管 Blockbench Agent Runtime（BAE），暴露本地 WebSocket JSON-RPC BridgeServer
//   2) 注册 bb_* 语义工具（建模/贴图/渲染/校验/保存）
//   3) 注册 /show /hide /bb-status 人类命令
//   4) 把渲染 PNG 通过 ctx.attachments 变成多模态图片块返回给模型
//
// 依赖：@deepseek-ai/dsh-tools（dsh 安装内解析）、node 内建模块、./lib/ws-server.js（零依赖）
// 安装：plugin_manager.install_bundle(target = 本目录)；本地 link 安装需要重启 harness 载入新 JS。

import { defineTool } from '@deepseek-ai/dsh-tools'
import { createWsServer } from './lib/ws-server.js'
import { spawn, execFile } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { randomBytes } from 'node:crypto'
import { createRequire } from 'node:module'

const nodeRequire = createRequire(import.meta.url)
let nativeImage = null
try {
  const electron = nodeRequire('electron')
  if (electron?.nativeImage) nativeImage = electron.nativeImage
} catch { /* plain Node (tests): image downscale unavailable */ }

export const name = 'blockbench-agent'
export const inject = ['tools', 'commands']

const DEFAULTS = {
  workspaceRoot: 'F:\\Deepseek_harness\\blockbench\\workspace',
  project: 'default',
  executable: '',            // BAE 的 electron.exe
  appPath: '',               // BAE 应用目录（含 index.html / agent/）
  pluginPath: '',            // 默认 <appPath>/agent/bb-agent-bridge.js
  autoStart: true,
  connectTimeoutMs: 30000,
  defaultTimeoutMs: 120000,
  maxImagesPerCall: 4,
  imageMaxBytes: 8 * 1024 * 1024,
  imageMaxDimension: 512,
  exposeGuiTools: false,
}

function log(...args) { console.log('[blockbench-agent]', ...args) }

function textBlocks(value) {
  return [{ type: 'text', text: typeof value === 'string' ? value : JSON.stringify(value) }]
}

export function apply(ctx, config = {}) {
  const cfg = { ...DEFAULTS, ...config }
  const workspace = path.resolve(cfg.workspaceRoot, cfg.project || 'default')
  const runtimeTag = `${process.pid}-${randomBytes(3).toString('hex')}`
  const userDataDir = path.join(workspace, '.bb', `userdata-${runtimeTag}`)
  const attachments = ctx.get?.('attachments')

  fs.mkdirSync(workspace, { recursive: true })
  fs.mkdirSync(path.join(workspace, 'logs'), { recursive: true })
  fs.mkdirSync(path.join(workspace, 'artifacts'), { recursive: true })

  const state = {
    server: null, rpcUrl: '', token: '', child: null, connected: false,
    hello: null, workspace, lastHeartbeat: null, startedAt: null, lastError: null,
    starting: null, runtimeTag, serverStarted: false,
    revision: 0, guiVisible: false, disposed: false, restartAttempts: 0, reconnectTimer: null,
    revisionSynced: false, lastChange: null,
    ready: null, readyResolve: null, readyReject: null,
  }
  state.ready = new Promise((resolve, reject) => { state.readyResolve = resolve; state.readyReject = reject })
  state.ready.catch(() => {})

  // ------------------------------------------------------------ RPC server
  const server = createWsServer({
    token: randomBytes(32).toString('base64url'),
    defaultTimeoutMs: cfg.defaultTimeoutMs,
    methods: {
      'system.hello': (params) => {
        state.hello = params
        state.startedAt = new Date().toISOString()
        return {
          protocol: 'bb-agent/1',
          transport: 'ws',
          server: { name: 'bb-agent-runtime', version: '0.2.0', blockbench: '5.2.2' },
          capabilities: {
            render: { offscreen: true, transparent: true, max_size: 4096, antialias: ['off', 'msaa'] },
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
      state.revisionSynced = false
      state.restartAttempts = 0
      if (state.reconnectTimer) { clearTimeout(state.reconnectTimer); state.reconnectTimer = null }
      log('Blockbench connected')
      state.readyResolve?.({ ok: true, workspace })
      setTimeout(async () => {
        try {
          const status = await server.request('session.status', {}, 5000)
          state.revision = status?.revision ?? 0
          state.guiVisible = !!status?.gui_visible
          state.revisionSynced = true
        } catch { /* retried by next call */ }
      }, 100).unref?.()
    },
    onNotification: (method, params) => {
      if (method === 'event.heartbeat') state.lastHeartbeat = { ...params, at: Date.now() }
      if (method === 'event.engine_degraded') { state.lastError = { code: 'ENGINE_DEGRADED', params }; log('engine degraded', params?.reason) }
      if (method === 'event.project_changed') {
        state.revision = params?.revision ?? state.revision
        state.lastChange = { revision: state.revision, source: params?.source ?? 'agent', at: Date.now() }
      }
      if (method === 'event.gui_state') {
        state.guiVisible = !!params?.visible
        state.revision = params?.revision ?? state.revision
      }
    },
  })
  state.server = server

  // ------------------------------------------------------------ lifecycle
  function waitUntil(predicate, timeoutMs) {
    return new Promise((resolve, reject) => {
      const started = Date.now()
      const timer = setInterval(() => {
        if (predicate()) { clearInterval(timer); resolve(true) }
        else if (Date.now() - started > timeoutMs) { clearInterval(timer); reject(new Error('timeout')) }
      }, 100)
    })
  }

  function killTree(pid) {
    if (!pid) return
    try {
      if (process.platform === 'win32') execFile('taskkill', ['/PID', String(pid), '/T', '/F'], () => {})
      else process.kill(pid, 'SIGKILL')
    } catch { /* ignore */ }
  }

  async function ensureServer() {
    if (state.serverStarted) return
    const { port } = await server.listen(0)
    state.token = server.token
    state.rpcUrl = `ws://127.0.0.1:${port}/bb-agent/v1`
    state.serverStarted = true
    log(`bridge listening on ${state.rpcUrl}`)
  }

  async function startRuntime() {
    if (state.starting) return state.starting
    state.starting = (async () => {
      await ensureServer()
      if (!cfg.executable || !cfg.appPath) {
        log('executable/appPath not configured; waiting for an external BAE to connect')
        return
      }
      if (state.connected) return
      if (state.child && !state.child.killed) {
        killTree(state.child.pid)
        state.child = null
      }
      const pluginPath = cfg.pluginPath || path.join(cfg.appPath, 'agent', 'bb-agent-bridge.js')
      const args = [
        cfg.appPath,
        `--workspace=${workspace}`,
        `--plugin=${pluginPath}`,
        `--user-data=${userDataDir}`,
        `--rpc-url=${state.rpcUrl}`,
        `--token=${server.token}`,
      ]
      const childEnv = { ...process.env, BB_AGENT_WORKSPACE: workspace }
      delete childEnv.ELECTRON_RUN_AS_NODE
      state.child = spawn(cfg.executable, args, {
        cwd: cfg.appPath,
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'pipe'],
        env: childEnv,
      })
      const child = state.child
      const logStream = fs.createWriteStream(path.join(workspace, 'logs', 'runtime.log'), { flags: 'a' })
      child.stdout?.on('data', (d) => logStream.write(d))
      child.stderr?.on('data', (d) => logStream.write(d))
      child.on('exit', (code, signal) => {
        log(`runtime exited code=${code} signal=${signal}${code === 3 ? ' (instance conflict / stale userData lock)' : ''}`)
        state.connected = false
        if (state.child === child) state.child = null
        state.lastError = { code: 'RUNTIME_EXITED', message: `code=${code} signal=${signal}` }
        if (!state.disposed && cfg.autoStart) scheduleRestart()
      })
      try {
        await Promise.race([
          waitUntil(() => state.connected, cfg.connectTimeoutMs),
          new Promise((_, reject) => setTimeout(() => reject(new Error('runtime connect timeout')), cfg.connectTimeoutMs)),
        ])
      } catch (error) {
        killTree(child.pid)
        throw error
      }
    })()
    try {
      return await state.starting
    } finally {
      state.starting = null
    }
  }

  function scheduleRestart() {
    if (state.disposed || !cfg.autoStart || !cfg.executable || !cfg.appPath) return
    if (state.restartAttempts >= 5) {
      state.lastError = { code: 'RUNTIME_RESTART_EXHAUSTED', message: 'runtime failed to stay up after 5 attempts' }
      log('runtime restart exhausted')
      return
    }
    state.restartAttempts += 1
    const delay = Math.min(15000, 400 * 2 ** state.restartAttempts)
    log(`scheduling runtime restart in ${delay}ms (attempt ${state.restartAttempts}/5)`)
    if (state.reconnectTimer) clearTimeout(state.reconnectTimer)
    state.reconnectTimer = setTimeout(() => {
      state.reconnectTimer = null
      if (state.disposed || state.connected) return
      startRuntime().catch((error) => {
        log('runtime restart failed:', error?.message)
        scheduleRestart()
      })
    }, delay)
    state.reconnectTimer.unref?.()
  }

  if (cfg.autoStart) {
    startRuntime().catch((error) => {
      log('startRuntime failed:', error?.message)
      state.lastError = { code: 'RUNTIME_START_FAILED', message: error?.message }
      state.readyReject?.(error)
    })
  } else {
    log('autoStart=false; tools will report runtime not connected until /bb-start or external connect')
  }

  async function ensureConnected(timeoutMs = 3000) {
    if (state.connected) return
    if (cfg.autoStart && cfg.executable && cfg.appPath && !state.starting) {
      startRuntime().catch((error) => { log('ensureConnected start failed:', error?.message); scheduleRestart() })
    }
    try {
      await waitUntil(() => state.connected, timeoutMs)
    } catch {
      throw Object.assign(new Error('Blockbench runtime not connected'), {
        code: 'PROJECT_NOT_OPEN',
        hint: 'configure executable/appPath with autoStart=true, or start BAE externally with --rpc-url/--token',
      })
    }
  }

  async function call(method, params = {}, timeoutMs = cfg.defaultTimeoutMs) {
    await ensureConnected()
    const result = await server.request(method, params, { timeoutMs })
    if (typeof result?.revision === 'number') state.revision = result.revision
    if (typeof result?.gui_visible === 'boolean') state.guiVisible = result.gui_visible
    return result
  }

  function errorResult(error) {
    const code = error?.rpc?.data?.code ?? error?.code ?? 'INTERNAL_ERROR'
    const hint = error?.rpc?.data?.hint ?? error?.hint ?? ''
    const extra = error?.rpc?.data && typeof error.rpc.data === 'object' ? error.rpc.data : undefined
    return { ok: false, code, message: error?.message ?? String(error), hint, ...(extra ? { details: extra } : {}) }
  }

  // ------------------------------------------------------------ tool helpers
  const MUTATING_TOOLS = new Set([
    'bb_session_start', 'bb_project_close', 'bb_apply_model_patch',
    'bb_texture_create', 'bb_texture_patch', 'bb_texture_import_png',
    'bb_animation_create', 'bb_animation_patch', 'bb_animation_delete',
    'bb_checkpoint', 'bb_restore', 'bb_save_project', 'bb_export_ysm', 'bb_batch',
  ])

  function abortError() {
    return Object.assign(new Error('tool call aborted'), { code: 'REQUEST_CANCELLED' })
  }

  function raceAbort(promise, signal) {
    if (!signal) return promise
    if (signal.aborted) return Promise.reject(abortError())
    return new Promise((resolve, reject) => {
      const onAbort = () => reject(abortError())
      signal.addEventListener('abort', onAbort, { once: true })
      promise.then(
        (value) => { signal.removeEventListener('abort', onAbort); resolve(value) },
        (error) => { signal.removeEventListener('abort', onAbort); reject(error) },
      )
    })
  }

  async function callTool(toolName, method, params = {}, opts = {}) {
    const { timeoutMs = cfg.defaultTimeoutMs, signal } = opts
    const mutating = opts.mutating ?? MUTATING_TOOLS.has(toolName)
    if (mutating) {
      if (state.guiVisible) {
        return { ok: false, code: 'GUI_BUSY', message: 'user is inspecting Blockbench', hint: 'run /hide before mutating' }
      }
      if (!state.revisionSynced) {
        try {
          const status = await raceAbort(call('session.status', {}, 5000), signal)
          state.revision = status?.revision ?? state.revision
          state.revisionSynced = true
        } catch { /* still try */ }
      }
      if (params.expected_revision === undefined) params = { ...params, expected_revision: state.revision }
    }
    const result = await raceAbort(call(method, params, timeoutMs), signal)
    if (typeof result?.revision === 'number') { state.revision = result.revision; state.revisionSynced = true }
    return result
  }

  async function saveImageAttachment(img) {
    if (!attachments) return img
    try {
      const filePath = img.attachment_workspace_path ?? img.workspace_path ?? path.join(workspace, img.path ?? '')
      if (!filePath || !fs.existsSync(filePath)) return img
      const stat = fs.statSync(filePath)
      if (stat.size > cfg.imageMaxBytes) return { ...img, attachment_skipped: 'too-large' }
      let data = fs.readFileSync(filePath)
      if (nativeImage) {
        try {
          const image = nativeImage.createFromPath(filePath)
          if (!image.isEmpty()) {
            const size = image.getSize()
            const longest = Math.max(size.width, size.height)
            if (longest > cfg.imageMaxDimension) {
              const scale = cfg.imageMaxDimension / longest
              data = image.resize({ width: Math.round(size.width * scale), height: Math.round(size.height * scale) }).toPNG()
              log(`attachment downscaled ${size.width}x${size.height} -> ${cfg.imageMaxDimension}px (${data.length}B)`)
            }
          }
        } catch (error) { log('nativeImage resize failed:', error?.message) }
      }
      const attachment = await attachments.saveImage({ data, mediaType: 'image/png', name: `${img.view ?? img.texture ?? 'image'}.png` })
      return { ...img, attachment }
    } catch (error) {
      log('attachment failed:', error?.message)
      return img
    }
  }

  // ------------------------------------------------------------ tool registry
  const registered = []
  const registeredTools = new Map()
  const tool = (definition) => {
    try { registeredTools.set(definition.name, definition) } catch { /* ignore */ }
    registered.push(ctx.tools.register(defineTool(definition)))
  }

  tool({
    name: 'bb_session_start',
    description: '新建 YSM 皮肤项目（默认骨架）或打开已有资源包。返回项目 id、revision、骨骼/贴图摘要。后续工具都作用于该项目。',
    parameters: {
      mode: { type: 'string', description: 'new_ysm | open_pack', required: true },
      name: { type: 'string', description: '项目名（new_ysm 时必填）' },
      resolution: { type: 'array', description: '[w,h]，默认 [128,128]' },
      height_scale: { type: 'number', description: '写入 ysm.json，默认 0.7' },
      width_scale: { type: 'number', description: '默认 0.7' },
      pack_dir: { type: 'string', description: 'workspace 内相对路径（默认 pack；mode=open_pack 时必填）' },
      overwrite: { type: 'boolean', description: 'pack 已存在时是否覆盖（危险）' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args, exec) {
      try {
        const method = args.mode === 'open_pack' ? 'project.open_pack' : 'project.create_ysm'
        return await callTool('bb_session_start', method, args, { timeoutMs: 120000, signal: exec?.signal })
      } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_project_open',
    description: '打开已有的 YSM 资源包目录（workspace 内相对路径），加载 main/arm、贴图、动画与控制器。',
    parameters: {
      pack_dir: { type: 'string', required: true, description: 'workspace 内相对路径' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args, exec) {
      try { return await callTool('bb_project_open', 'project.open_pack', args, { timeoutMs: 120000, signal: exec?.signal }) } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_session_status',
    description: '查看 Blockbench 引擎状态、当前项目 revision、连接与健康信息；卡住或怀疑降级时先调用。',
    parameters: {},
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute() {
      if (!state.connected) {
        return { ok: false, code: 'PROJECT_NOT_OPEN', message: 'Blockbench runtime not connected', rpcUrl: state.rpcUrl, lastError: state.lastError }
      }
      try { return await call('session.status', {}, 5000) } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_scene',
    description: '读取压缩后的场景信息：summary/bones/bone/cube/textures/animations；默认 summary，列表分页。不要读取原始 JSON。',
    parameters: {
      scope: { type: 'string', description: 'summary|bones|bone|cube|textures|animations|uv' },
      id: { type: 'string', description: 'scope=bone/cube 时的 id 或名字' },
      limit: { type: 'number', description: '分页大小 1-100' },
      include_uv: { type: 'boolean' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args) { try { return await call('project.get_scene', args, 10000) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_get_element',
    description: '取单个骨骼/方块的完整字段（可含 UV）；bb_scene 已包含的信息不要重复取。',
    parameters: {
      id: { type: 'string', required: true },
      include_uv: { type: 'boolean' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args) { try { return await call('project.get_element', args, 5000) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_apply_model_patch',
    description: '模型原子变更：add_bone/add_cube/update_cube/update_bone/delete/rename 等一组 ops，一个 Undo 与一个 revision。',
    parameters: {
      note: { type: 'string', description: '写入 Undo 标签的说明' },
      ops: { type: 'array', description: 'ops 数组，见 docs/03 §3.6', required: true },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args, exec) { try { return await callTool('bb_apply_model_patch', 'model.apply_patch', args, { timeoutMs: 30000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_texture_create',
    description: '新建一张纹理（YSM 多套皮肤）。默认 128x128、全透明；可指定填充色。',
    parameters: {
      name: { type: 'string', required: true },
      width: { type: 'number', description: '默认 128' },
      height: { type: 'number', description: '默认 128' },
      fill: { type: 'string', description: '#RRGGBB 或 #RRGGBBAA' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args, exec) { try { return await callTool('bb_texture_create', 'texture.create', args, { timeoutMs: 30000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_texture_patch',
    description: '按像素坐标绘制纹理：pixel/rect/line/shade/replace/clear/copy_mirror；一次调用一个 Undo 与 revision。',
    parameters: {
      texture: { type: 'string', description: '纹理名或 id；省略为当前激活纹理' },
      clip: { type: 'boolean', description: '越界像素裁剪（默认 true）' },
      note: { type: 'string' },
      ops: { type: 'array', description: '绘制 ops 数组，见 docs/03 §3.8', required: true },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args, exec) { try { return await callTool('bb_texture_patch', 'texture.apply_patch', args, { timeoutMs: 60000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_texture_read',
    description: '读取纹理局部：调色板统计 / ASCII 网格 / 小图 base64；默认不返回整图像素数组。',
    parameters: {
      texture: { type: 'string' },
      region: { type: 'array', description: '[x1,y1,x2,y2]' },
      format: { type: 'string', description: 'palette|ascii|png' },
      max_cells: { type: 'number' },
      max_colors: { type: 'number' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args) { try { return await call('texture.read', args, 10000) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_texture_layer',
    description: '纹理图层：list/create/select/delete/flatten。图层是编辑期便利，保存时合成回单张 PNG。',
    parameters: {
      op: { type: 'string', description: 'list|create|select|delete|flatten', required: true },
      texture: { type: 'string' },
      name: { type: 'string', description: 'create 时的图层名' },
      layer: { type: 'string', description: 'select/delete 时的图层 id 或名字' },
      fill: { type: 'string', description: 'create 时的填充色 #RRGGBB' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args, exec) {
      try {
        const method = { list: 'texture.layer_list', create: 'texture.layer_create', select: 'texture.layer_select', delete: 'texture.layer_delete', flatten: 'texture.layer_flatten' }[args.op]
        if (!method) return { ok: false, code: 'INVALID_PARAMS', message: `unknown op: ${args.op}` }
        const mutating = args.op === 'create' || args.op === 'delete' || args.op === 'flatten'
        return await callTool('bb_texture_layer', method, args, { timeoutMs: 30000, signal: exec?.signal, mutating })
          .then((result) => result)
          .catch((error) => errorResult(error))
      } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_texture_pbr',
    description: 'PBR 贴图：list 列出现有 _n/_s 贴图；create 创建 Iris/YSM 约定的 normal(_n)/specular(_s) 贴图并随包保存。',
    parameters: {
      op: { type: 'string', description: 'list|create', required: true },
      texture: { type: 'string', description: '基础贴图名（create 时）' },
      channel: { type: 'string', description: 'normal|specular' },
      fill: { type: 'string', description: '可选填充色' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args, exec) {
      try {
        const method = args.op === 'create' ? 'texture.pbr_create' : 'texture.pbr_list'
        return await callTool('bb_texture_pbr', method, args, { timeoutMs: 30000, signal: exec?.signal, mutating: args.op === 'create' })
      } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_render_views',
    description: '用固定机位无头渲染当前模型；默认透明背景、768px、front/right/iso_fr 三视图，图片作为附件返回（最多 4 张）。结果含逐图 changed/alpha_ratio 与 NO_VISIBLE_CHANGE/EMPTY_RENDER 警告。',
    parameters: {
      views: { type: 'array', description: 'front/back/left/right/top/bottom/iso_fr/iso_fl/iso_br/iso_bl' },
      size: { type: 'array', description: '[w,h]，默认 [768,768]' },
      transparent: { type: 'boolean' },
      antialias: { type: 'string', description: 'off|msaa' },
      attach_images: { type: 'boolean', description: '是否附图（默认 true）' },
      attach_size: { type: 'number', description: '附件缩略图边长，默认 512' },
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (_a, value) => {
        if (!value || value.ok === false) return textBlocks(value ?? 'render failed')
        const summary = {
          revision: value.revision,
          changed_any: value.changed_any,
          warnings: value.warnings,
          review: value.review,
          views: (value.images ?? []).map((i) => i.view),
          images: (value.images ?? []).map((i) => ({ view: i.view, path: i.path, bytes: i.bytes, changed: i.changed, alpha_ratio: i.alpha_ratio })),
        }
        const blocks = textBlocks(summary)
        for (const img of value.images ?? []) if (img.attachment) blocks.push({ type: 'image', attachment: img.attachment })
        return blocks
      },
    },
    async execute(args, exec) {
      try {
        const result = await raceAbort(call('render.views', args, 120000), exec?.signal)
        if (!attachments || args.attach_images === false) return result
        const images = []
        for (const img of (result.images ?? []).slice(0, cfg.maxImagesPerCall)) {
          images.push(await saveImageAttachment(img))
        }
        for (const img of (result.images ?? []).slice(cfg.maxImagesPerCall)) images.push(img)
        return { ...result, images }
      } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_render_texture',
    description: '把纹理按最近邻放大输出 PNG，用于检查像素细节、色带与接缝。',
    parameters: {
      texture: { type: 'string' },
      scale: { type: 'number', description: '1-16，默认 8' },
      region: { type: 'array', description: '[x1,y1,x2,y2]' },
      attach_image: { type: 'boolean', description: '是否作为图片附件返回（默认 true）' },
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (_a, v) => {
        if (!v?.attachment) return textBlocks(v)
        const { attachment, ...rest } = v
        return [...textBlocks(rest), { type: 'image', attachment }]
      },
    },
    async execute(args, exec) {
      try {
        const result = await raceAbort(call('render.texture', args, 30000), exec?.signal)
        if (attachments && args.attach_image !== false) {
          const withAttachment = await saveImageAttachment({ ...result, view: result.texture ?? 'texture' })
          return withAttachment
        }
        return result
      } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_validate',
    description: '按 YSM 规范校验当前项目；A 级定位组缺失=error，B 级默认层级偏离=warning。导出前必须调用。',
    parameters: { strict: { type: 'boolean' } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args) { try { return await call('project.validate', args, 30000) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_checkpoint',
    description: '把当前项目保存为 .bbmodel 检查点，便于回滚/对比；大改或导出前调用。',
    parameters: { label: { type: 'string' }, note: { type: 'string' } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args, exec) { try { return await callTool('bb_checkpoint', 'project.checkpoint', args, { timeoutMs: 30000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_revisions',
    description: '列出最近的 .bbmodel 检查点与当前 revision。',
    parameters: { limit: { type: 'number' } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args) { try { return await call('project.revisions', args, 10000) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_restore',
    description: '恢复到指定 revision 的 .bbmodel 检查点（破坏性：丢弃当前未保存改动，需 confirm:true）。',
    parameters: {
      revision: { type: 'number', required: true },
      confirm: { type: 'boolean', description: '必须为 true' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args, exec) { try { return await callTool('bb_restore', 'project.restore', args, { timeoutMs: 60000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_save_project',
    description: '把当前项目显式写回 workspace/pack：模型 JSON、动画、控制器、贴图 PNG 与 ysm.json。',
    parameters: {},
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(_args, exec) { try { return await callTool('bb_save_project', 'project.save', {}, { timeoutMs: 120000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_export_ysm',
    description: '校验并导出 YSM 资源包目录（含 export-manifest.json）与 zip（默认生成）；导出前强制 validate。',
    parameters: {
      out_dir: { type: 'string', description: 'workspace 相对路径；默认 exports/<时间戳>' },
      validate: { type: 'boolean', description: '导出前校验（默认 true）' },
      zip: { type: 'boolean', description: '是否生成 zip（默认 true）' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args, exec) { try { return await callTool('bb_export_ysm', 'project.export_ysm', args, { timeoutMs: 300000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_project_close',
    description: '关闭当前项目（先保存/检查点自行负责）；force=true 跳过未保存提示。',
    parameters: { force: { type: 'boolean', description: '默认 true' } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args, exec) { try { return await callTool('bb_project_close', 'project.close', args, { timeoutMs: 15000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_animation_list',
    description: '列出动画名、时长、循环方式、路径与关键帧数量；含控制器/状态及已绑定动画。',
    parameters: {},
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute() { try { return await call('animation.list', {}, 10000) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_animation_create',
    description: '创建动画（name/length/loop/file）；创建后可用 bb_animation_patch 设置关键帧。',
    parameters: {
      name: { type: 'string', required: true },
      length: { type: 'number', description: '秒，默认 1' },
      loop: { type: 'string', description: 'loop | once | hold，默认 loop' },
      file: { type: 'string', description: '包内动画文件路径，默认 animations/main.animation.json' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args, exec) { try { return await callTool('bb_animation_create', 'animation.create', args, { timeoutMs: 30000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_animation_patch',
    description: '动画原子变更：update_animation/set_keyframes/delete_keyframes/delete_animation/bind_controller，一组 ops 一个 Undo。',
    parameters: {
      note: { type: 'string' },
      ops: { type: 'array', description: '动画 ops 数组，见 docs/03 §3.10', required: true },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args, exec) { try { return await callTool('bb_animation_patch', 'animation.apply_patch', args, { timeoutMs: 30000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_animation_delete',
    description: '删除一个动画。',
    parameters: { animation: { type: 'string', required: true } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args, exec) { try { return await callTool('bb_animation_delete', 'animation.delete', args, { timeoutMs: 30000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_texture_export_png',
    description: '把指定纹理导出为 PNG（workspace 内路径），返回宽高与字节数。',
    parameters: {
      texture: { type: 'string' },
      out_dir: { type: 'string', description: 'workspace 相对目录，默认 artifacts/textures' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args) { try { return await call('texture.export_png', args, 30000) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_texture_import_png',
    description: '把 workspace 内 PNG 或 base64 图片导入到指定纹理的指定位置。',
    parameters: {
      texture: { type: 'string' },
      path: { type: 'string', description: 'workspace 相对 PNG 路径' },
      base64: { type: 'string', description: 'PNG base64（与 path 二选一）' },
      at: { type: 'array', description: '[x,y] 目标纹理坐标，默认 [0,0]' },
      region: { type: 'array', description: '[x1,y1,x2,y2] 源图裁剪区域（可选）' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args, exec) { try { return await callTool('bb_texture_import_png', 'texture.import_png', args, { timeoutMs: 60000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_batch',
    description: '把多个 bb_* 调用合并成一次工具往返（顺序执行；当前不保证原子回滚）。失败即停止并返回已完成项。',
    parameters: {
      calls: { type: 'array', description: '[{tool:"bb_...", args:{...}}]', required: true },
      stop_on_error: { type: 'boolean', description: '默认 true' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args, exec) {
      const calls = Array.isArray(args.calls) ? args.calls : []
      if (!calls.length) return { ok: false, code: 'INVALID_PARAMS', message: 'calls is empty' }
      if (calls.length > 16) return { ok: false, code: 'RESOURCE_LIMIT', message: 'max 16 calls per batch' }
      const results = []
      for (const item of calls) {
        if (!item?.tool || item.tool === 'bb_batch') {
          results.push({ tool: item?.tool, ok: false, code: 'INVALID_PARAMS', message: 'nested/unknown tool' })
          if (args.stop_on_error !== false) break
          continue
        }
        const definition = registeredTools.get(item.tool)
        if (!definition) {
          results.push({ tool: item.tool, ok: false, code: 'METHOD_NOT_FOUND', message: `unknown tool ${item.tool}` })
          if (args.stop_on_error !== false) break
          continue
        }
        try {
          const result = await definition.execute(item.args ?? {}, exec)
          results.push({ tool: item.tool, ok: result?.ok !== false, result })
          if (result?.ok === false && args.stop_on_error !== false) break
        } catch (error) {
          results.push({ tool: item.tool, ok: false, ...errorResult(error) })
          if (args.stop_on_error !== false) break
        }
      }
      return { ok: results.every((r) => r.ok), revision: state.revision, results, rolled_back: false }
    },
  })

  tool({
    name: 'bb_diagnostics',
    description: '输出 Blockbench Agent 的运行诊断：连接/进程/端口/版本/最近心跳/日志尾部，用于排障。',
    parameters: {},
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute() {
      const tails = {}
      for (const [name, file] of [['runtime', 'runtime.log'], ['agent', 'agent.log']]) {
        try { tails[name] = fs.readFileSync(path.join(workspace, 'logs', file), 'utf8').split('\n').slice(-30).join('\n') } catch { tails[name] = '' }
      }
      let remote = null
      try { if (state.connected) remote = await call('session.status', {}, 5000) } catch (error) { remote = errorResult(error) }
      return {
        ok: true, dsh: { pid: process.pid, platform: process.platform, node: process.version },
        image: { nativeImage: !!nativeImage, maxDimension: cfg.imageMaxDimension, maxBytes: cfg.imageMaxBytes },
        runtime: {
          connected: state.connected, rpcUrl: state.rpcUrl, childPid: state.child?.pid ?? null,
          restartAttempts: state.restartAttempts, lastHeartbeat: state.lastHeartbeat, lastError: state.lastError,
          hello: state.hello?.server ?? null, workspace, userDataDir,
        },
        remote,
        logs: tails,
      }
    },
  })

  // 可选 GUI 工具：默认不暴露给模型，由 `/show` `/hide` 命令负责
  if (cfg.exposeGuiTools) {
    tool({
      name: 'bb_show_gui',
      description: '显示后台 Blockbench 窗口，把控制权交给用户；期间写操作会被冻结。',
      parameters: { mode: { type: 'string', description: 'inspect | edit' } },
      output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
      async execute(args) { try { return await call('gui.show', args, 10000) } catch (error) { return errorResult(error) } },
    })
    tool({
      name: 'bb_hide_gui',
      description: '隐藏 Blockbench 窗口并同步用户改动。',
      parameters: {},
      output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
      async execute() { try { return await call('gui.hide', {}, 15000) } catch (error) { return errorResult(error) } },
    })
  }

  // ------------------------------------------------------------ skill registration
  try {
    const skills = ctx.get?.('skills')
    if (skills) {
      const content = fs.readFileSync(new URL('./skills/blockbench-ysm-artist.md', import.meta.url), 'utf8')
      registered.push(skills.register({
        name: 'blockbench-ysm-artist',
        description: '用 bb_* 工具在后台 Blockbench 中完成 YSM 皮肤/模型的造型、贴图、动画、渲染自检与导出；需要无头可视化闭环时使用。',
        whenToUse: '当用户要求制作/修改 YSM 模型或皮肤、给 Blockbench 模型加方块/改 UV/涂贴图/做动画，或需要通过无头渲染检查模型效果时。',
        source: 'runtime',
        invocation: { modelInvocable: true, userInvocable: true },
        content,
      }))
      log('registered skill blockbench-ysm-artist')
    }
  } catch (error) { log('skill registration skipped:', error?.message) }

  // ------------------------------------------------------------ commands
  function command(name, description, handler) {
    registered.push(ctx.commands.register({ name, description, handler }))
  }

  command('show', '显示后台 Blockbench 窗口，交给你检查/手动修改', async () => {
    try {
      const result = await call('gui.show', { mode: 'inspect' }, 10000)
      state.guiVisible = true
      return { kind: 'success', text: `Blockbench 已显示（revision ${result.revision}）。编辑完成后输入 /hide 返回。` }
    } catch (error) { return { kind: 'error', text: `显示失败：${error?.message ?? error}` } }
  })
  command('hide', '隐藏 Blockbench 窗口，把控制权还给 Agent', async () => {
    try {
      const result = await call('gui.hide', { resync: true }, 15000)
      state.guiVisible = false
      const edits = result.user_edits?.length ? `；检测到用户改动 ${JSON.stringify(result.user_edits)}` : ''
      return { kind: 'success', text: `Blockbench 已隐藏（revision ${result.revision}）${edits}。` }
    } catch (error) { return { kind: 'error', text: `隐藏失败：${error?.message ?? error}` } }
  })
  command('bb-status', '查看 Blockbench Agent 连接与运行状态', async () => {
    try {
      if (!state.connected) return { kind: 'success', text: `未连接。rpc=${state.rpcUrl || '(not started)'} lastError=${JSON.stringify(state.lastError)}` }
      const result = await call('session.status', {}, 5000)
      return { kind: 'success', text: JSON.stringify(result) }
    } catch (error) { return { kind: 'error', text: `查询失败：${error?.message ?? error}` } }
  })
  command('bb-start', '启动/重启 Blockbench Agent Runtime', async () => {
    if (state.connected) return { kind: 'success', text: 'Blockbench 已连接。' }
    try { await startRuntime(); return { kind: 'success', text: 'Blockbench 已启动并连接。' } }
    catch (error) { return { kind: 'error', text: `启动失败：${error?.message ?? error}` } }
  })
  command('bb-help', '列出 Blockbench Agent 工具与快捷命令', async () => ({
    kind: 'success',
    text: [
      'Blockbench Agent 工具：',
      '- bb_session_start / bb_project_close / bb_session_status',
      '- bb_scene / bb_get_element / bb_apply_model_patch',
      '- bb_texture_create / bb_texture_patch / bb_texture_read / bb_texture_export_png / bb_texture_import_png',
      '- bb_animation_list / bb_animation_create / bb_animation_patch / bb_animation_delete',
      '- bb_render_views / bb_render_texture',
      '- bb_validate / bb_checkpoint / bb_revisions / bb_restore',
      '- bb_save_project / bb_export_ysm / bb_batch / bb_diagnostics',
      '命令：/show 显示窗口，/hide 隐藏并同步，/bb-status 状态，/bb-start 启动运行时。',
    ].join('\n'),
  }))

  // ------------------------------------------------------------ cleanup
  ctx.effect(() => () => {
    log('disposing blockbench-agent')
    state.disposed = true
    if (state.reconnectTimer) { clearTimeout(state.reconnectTimer); state.reconnectTimer = null }
    killTree(state.child?.pid)
    state.child = null
    void server.close()
    for (const dispose of registered) { try { dispose?.() } catch { /* ignore */ } }
  })
}

