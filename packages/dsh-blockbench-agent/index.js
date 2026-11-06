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
import { imageTokens } from './lib/viewsheet.js'
import { offloadSessionImages, countLiveImages } from './lib/imageprune.js'
import { searchRefs, sortCandidates, SOURCES as REF_SOURCES } from './lib/refsearch.js'
import { collectRefs } from './lib/refcollect.js'
import { validateSpec, derivePlan, renderSpecMarkdown, normalizeSpec, SPEC_VERSION } from './lib/spec.js'
import { spawn, execFile } from 'node:child_process'
import fs from 'node:fs'
import fsp from 'node:fs/promises'
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
  bridgeTransport: 'auto',

  // ---- 视口实时反馈（docs/07）----
  /** 写操作后自动附图（A 眼）。可一键关闭。 */
  autoLook: true,
  /** 每 N 次写操作附一次图；1 = 每次（同 step 仍会合并）。 */
  autoLookEvery: 1,
  /** 自动附图的画布边长（单格）。320 → 2 格 640×320 ≈ 180 token。 */
  autoLookCell: 320,
  /** 自动附图强制不透明底色，避免"透明=黑"被误读（docs/07 R4）。 */
  autoLookBackground: '#1b1b1b',
  /** 单会话累计附图上限；超过后自动关闭 autoLook 并在状态里提示。 */
  sessionImageBudget: 40,
  /** 图史压缩：最多保留多少张"活图"（L1 触发阈值）。 */
  maxLiveImages: 6,
  /** 图史压缩：永远保留的最新图片数。 */
  keepImages: 2,
  /** 图史压缩：单次最多改写多少条 tool result（控制前缀缓存失效范围）。 */
  offloadMaxNodes: 4,

  // ---- 参考图收集（docs/11，零安装）----
  /** 参考图落盘子目录（位于 workspace 下）。 */
  refDir: 'refs',
  /** 单次收集最多保留多少张。 */
  refMaxImages: 24,
  /** 下载并发。 */
  refConcurrency: 6,
  /** 单图下载超时（ms）。 */
  refTimeoutMs: 20000,
  /** 参考图对照表单格像素。 */
  refCell: 240,
  /** 搜索用的默认源（空 = 全部）。 */
  refSources: [],

  // ---- 建模规格（docs/12）----
  /** spec 落盘子目录（位于 workspace 下）。 */
  specDir: 'specs',
}

function log(...args) { console.log('[blockbench-agent]', ...args) }

function textBlocks(value) {
  return [{ type: 'text', text: typeof value === 'string' ? value : JSON.stringify(value) }]
}

/**
 * 通用输出渲染：文本 + （若存在）自动附图块。
 * 写操作工具经 withAutoLook 包装后，结果里带 `__autoLookBlocks`；
 * 这里把它转成真正的 image block 附在文本之后（docs/07 眼睛 A）。
 */
function renderWithAutoLook(value) {
  if (!value || typeof value !== 'object' || !Array.isArray(value.__autoLookBlocks)) {
    return textBlocks(value)
  }
  const { __autoLookBlocks, __autoLook, ...rest } = value
  return [...textBlocks(rest), ...__autoLookBlocks]
}

export function apply(ctx, config = {}) {
  const cfg = { ...DEFAULTS, ...config }
  const workspace = path.resolve(cfg.workspaceRoot, cfg.project || 'default')
  const runtimeTag = `${process.pid}-${randomBytes(3).toString('hex')}`
  const userDataDir = path.join(workspace, '.bb', `userdata-${runtimeTag}`)
  const attachments = ctx.get?.('attachments')

  // 运行时目录：插件在会话中会持续写入，缺失会导致写日志/落盘失败。
  // 每次 apply 都重建（recursive 幂等），避免被外部清理后崩溃。
  for (const sub of ['', 'logs', 'artifacts', 'checkpoints', path.join('.bb')]) {
    try { fs.mkdirSync(path.join(workspace, sub), { recursive: true }) } catch { /* 只读盘等场景不阻断加载 */ }
  }

  const state = {
    server: null, rpcUrl: '', token: '', child: null, connected: false,
    hello: null, workspace, lastHeartbeat: null, startedAt: null, lastError: null,
    starting: null, runtimeTag, serverStarted: false,
    revision: 0, guiVisible: false, disposed: false, restartAttempts: 0, reconnectTimer: null,
    revisionSynced: false, lastChange: null, safeMode: false,
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
          server: { name: 'bb-agent-runtime', version: '0.4.0', blockbench: '5.2.2' },
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
        `--transport=${cfg.bridgeTransport || 'auto'}`,
      ]
      if (state.safeMode) args.push('--safe-mode')
      const childEnv = { ...process.env, BB_AGENT_WORKSPACE: workspace }
      delete childEnv.ELECTRON_RUN_AS_NODE
      state.child = spawn(cfg.executable, args, {
        cwd: cfg.appPath,
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'pipe'],
        env: childEnv,
      })
      const child = state.child
      // 目录可能在运行期被清理（例如归档/手动删除），必须每次 spawn 前确保存在；
      // 且 WriteStream 的 'error' 必须有监听器 —— 否则 ENOENT 会以未捕获异常
      // 冒泡到宿主进程，直接把 dsh 打崩（2026-11-06 实报过一次）。
      const logsDir = path.join(workspace, 'logs')
      let logStream = null
      try {
        fs.mkdirSync(logsDir, { recursive: true })
        logStream = fs.createWriteStream(path.join(logsDir, 'runtime.log'), { flags: 'a' })
        logStream.on('error', (error) => log('runtime log stream error:', error?.message))
      } catch (error) {
        log('cannot open runtime log:', error?.message)
      }
      if (logStream) {
        child.stdout?.on('data', (d) => { try { logStream.write(d) } catch { /* ignore */ } })
        child.stderr?.on('data', (d) => { try { logStream.write(d) } catch { /* ignore */ } })
      }
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

  // GPU 降级链：渲染失败/引擎降级时重启 BAE 到 SwiftShader safe-mode，再重试一次
  async function restartInSafeMode() {
    if (state.safeMode) return false
    log('restarting runtime in safe-mode (software rendering)')
    state.safeMode = true
    if (state.child && !state.child.killed) killTree(state.child.pid)
    state.child = null
    state.connected = false
    state.revisionSynced = false
    try {
      await startRuntime()
      return true
    } catch (error) {
      log('safe-mode restart failed:', error?.message)
      return false
    }
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

  // ------------------------------------------------------------ 视口实时反馈辅助（docs/07）

  /** 会话级图片计数（用于 sessionImageBudget 与 /bb-status）。 */
  const lookStats = { images: 0, autolook: 0, offloaded: 0, lastError: null, disabledByBudget: false }

  /**
   * 把 renderer 返回的 inline base64 直接存成附件（不落盘）。
   * 失败返回 null —— 视觉反馈永远不能影响主流程（docs/07 D9）。
   */
  async function saveInlineAttachment(base64, name) {
    if (!attachments || !base64) return null
    try {
      const data = Buffer.from(base64, 'base64')
      if (data.length > cfg.imageMaxBytes) {
        log(`inline attachment skipped: ${data.length}B > ${cfg.imageMaxBytes}B`)
        return null
      }
      return await attachments.saveImage({ data, mediaType: 'image/png', name })
    } catch (error) {
      log('inline attachment failed:', error?.message)
      return null
    }
  }

  /**
   * 渲染一张视图拼图并返回 { ok, attachment, meta }。
   * 所有"看图"工具共用这一条路径：调用 bridge `render.sheet` → 一张 PNG → 一个附件。
   *
   * @param {object} p
   * @param {string} p.tool               调用来源（用于 stats/命名）
   * @param {object[]} p.cells            见 bridge render.sheet
   * @param {number} [p.cell=320]         单格像素
   * @param {string|null} [p.background]  底色
   * @param {number} [p.timeoutMs=30000]
   * @param {AbortSignal} [p.signal]
   */
  async function renderSheet(p) {
    const t0 = Date.now()
    const params = {
      cells: p.cells,
      cell: p.cell ?? cfg.autoLookCell,
      background: p.background === undefined ? cfg.autoLookBackground : p.background,
      cols: p.cols,
      gap: p.gap,
      labels: p.labels,
      projection: p.projection,
      padding: p.padding,
      animation: p.animation,
      focus: p.focus,
    }
    const result = await raceAbort(call('render.sheet', params, p.timeoutMs ?? 30000), p.signal)

    const attachment = await saveInlineAttachment(result.png, `${p.tool}-${Date.now()}.png`)
    if (!attachment) {
      return { ok: false, code: 'ATTACHMENT_FAILED', message: '渲染成功但附件提交失败', result }
    }

    const tokens = imageTokens(result.width, result.height)
    lookStats.images += 1
    const meta = {
      tool: p.tool,
      revision: result.revision,
      views: (result.cells ?? []).map((c) => c.view ?? (c.time !== null ? `t=${c.time}` : 'custom')),
      cells: result.count,
      width: result.width, height: result.height,
      tokens_est: tokens,
      render_ms: result.elapsed_ms,
      total_ms: Date.now() - t0,
    }
    return { ok: true, attachment, meta, result }
  }

  /** 触发一次图史压缩（L1）。失败只记日志，永不抛出（docs/07 R2）。 */
  function maybeOffloadImages(reason) {
    try {
      const session = currentSession()
      if (!session) return null
      const before = countLiveImages(session)
      if (before.images <= cfg.maxLiveImages) return null
      const r = offloadSessionImages({
        session,
        tokenMeter: ctx.get?.('tokenMeter') ?? null,
        keepImages: cfg.keepImages,
        maxNodes: cfg.offloadMaxNodes,
        protectSeqs: currentStepSeqs(),
      })
      if (r.imagesRemoved > 0) {
        lookStats.offloaded += r.imagesRemoved
        log(`[图史压缩/${reason}] 剥离 ${r.imagesRemoved} 张图，改写 ${r.nodesRewritten} 条 tool result`)
      }
      return r
    } catch (error) {
      lookStats.lastError = error?.message ?? String(error)
      log('image offload failed:', lookStats.lastError)
      return null
    }
  }

  /** 当前 agent 的 Session（拿不到返回 null，纯 Node 测试环境就是 null）。 */
  function currentSession() {
    try {
      const agent = ctx.get?.('agents')?.currentInitiator?.()
      if (!agent) return null
      const sessions = ctx.get?.('sessions')
      if (!sessions?.get) return null
      return sessions.get(agent.id) ?? null
    } catch { return null }
  }

  /** 当前 step 产生的 surface 节点（这些图永不被剥离）。 */
  function currentStepSeqs() {
    const seqs = new Set()
    try {
      const session = currentSession()
      if (!session) return seqs
      const n = session.surface?.nodes ?? []
      // 取尾部 20 个节点作为"当前窗口"保守保护区
      for (const s of n.slice(-20)) seqs.add(s)
    } catch { /* ignore */ }
    return seqs
  }

  // ------------------------------------------------------------ tool registry
  const registered = []
  const registeredTools = new Map()
  const tool = (definition) => {
    // 写操作工具统一套一层"编辑即看"（docs/07 眼睛 A）
    const def = AUTO_LOOK_TOOLS.has(definition.name) && definition.execute
      ? withAutoLook(definition)
      : definition
    try { registeredTools.set(def.name, def) } catch { /* ignore */ }
    registered.push(ctx.tools.register(defineTool(def)))
  }

  // ---- 编辑即看（docs/07 眼睛 A）--------------------------------------------
  // 写操作完成后自动附加一张小拼图。关键约束：
  //   1) 同一 step 内连续写操作**合并成一张**（D2）—— 避免 set_uv 连点刷图；
  //   2) 失败绝不影响写操作结果（D9）；
  //   3) 可一键关闭（D8），且受 sessionImageBudget 限制。

  /** 需要自动附图的写操作工具。 */
  const AUTO_LOOK_TOOLS = new Set([
    'bb_apply_model_patch',
    'bb_texture_patch',
    'bb_texture_create',
    'bb_texture_import_png',
    'bb_texture_pbr',
    'bb_animation_create',
    'bb_animation_patch',
    'bb_project_open',
    'bb_session_start',
  ])

  /** step 级合并：<turn:step, { at, count }>。 */
  const autoLookSteps = new Map()
  let autoLookWrites = 0

  /**
   * 给一次写操作的结果附加"改完的样子"。
   * 返回额外的 content blocks（可能为空数组）。
   */
  async function autoLookFor(toolName, exec) {
    if (!cfg.autoLook) return { blocks: [], reason: 'disabled' }
    if (lookStats.disabledByBudget) return { blocks: [], reason: 'budget' }
    if (!AUTO_LOOK_TOOLS.has(toolName)) return { blocks: [], reason: 'not-write-tool' }

    autoLookWrites += 1
    const every = Math.max(1, Math.round(cfg.autoLookEvery) || 1)
    if (autoLookWrites % every !== 0) return { blocks: [], reason: 'skipped-by-frequency' }

    // step 级合并：同一个 step 里只保留最后一次（后续替换前一次的附图）
    const stepKey = `${exec?.log?.turn ?? 0}:${exec?.log?.step ?? 0}`
    const prev = autoLookSteps.get(stepKey)
    const merged = Boolean(prev)

    const t0 = Date.now()
    try {
      const r = await renderSheet({
        tool: 'autolook',
        cells: [{ view: 'front' }, { view: 'iso_fr' }],
        cell: cfg.autoLookCell,
        background: cfg.autoLookBackground,
        signal: exec?.signal,
      })
      if (!r.ok) {
        lookStats.lastError = r.message ?? 'render failed'
        return { blocks: [], reason: 'render-failed' }
      }
      autoLookSteps.set(stepKey, { at: Date.now(), count: (prev?.count ?? 0) + 1 })
      lookStats.autolook += 1

      // 预算：附图后立即检查是否需要压缩历史图
      maybeOffloadImages('autolook')

      if (lookStats.images >= cfg.sessionImageBudget) {
        lookStats.disabledByBudget = true
        log(`autoLook disabled: session image budget ${cfg.sessionImageBudget} reached`)
      }

      const blocks = [
        {
          type: 'text',
          text: `【改完的样子】revision ${r.meta.revision} · ${r.meta.tokens_est} token`
            + (merged ? `（本步第 ${(prev?.count ?? 0) + 1} 次写操作，已合并）` : '')
            + `· ${Date.now() - t0}ms`,
        },
        { type: 'image', attachment: r.attachment },
      ]
      return { blocks, meta: r.meta }
    } catch (error) {
      lookStats.lastError = error?.message ?? String(error)
      log('autoLook failed:', lookStats.lastError)
      return { blocks: [], reason: 'exception' }
    }
  }

  /**
   * 包装一个写操作工具：执行后自动附图。
   * 附图失败或超时都只影响"有没有图"，不影响工具本身的返回值与错误语义。
   */
  function withAutoLook(definition) {
    const inner = definition.execute
    return {
      ...definition,
      async execute(args, exec) {
        const value = await inner(args, exec)
        try {
          // 写操作失败 / 明确 ok:false 时不附图（没有可看的新状态）
          if (value && value.ok === false) return value
          const extra = await autoLookFor(definition.name, exec)
          if (!extra.blocks.length) return value
          return { ...value, __autoLook: extra.meta ?? true, __autoLookBlocks: extra.blocks }
        } catch {
          return value
        }
      },
    }
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
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
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
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
    async execute(args, exec) {
      try { return await callTool('bb_project_open', 'project.open_pack', args, { timeoutMs: 120000, signal: exec?.signal }) } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_session_status',
    description: '查看 Blockbench 引擎状态、当前项目 revision、连接与健康信息；卡住或怀疑降级时先调用。',
    parameters: {},
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
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
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
    async execute(args) { try { return await call('project.get_scene', args, 10000) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_get_element',
    description: '取单个骨骼/方块的完整字段（可含 UV）；bb_scene 已包含的信息不要重复取。',
    parameters: {
      id: { type: 'string', required: true },
      include_uv: { type: 'boolean' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
    async execute(args) { try { return await call('project.get_element', args, 5000) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_apply_model_patch',
    description: '模型原子变更：add_bone/add_cube/update_cube/update_bone/delete/rename 等一组 ops，一个 Undo 与一个 revision。add_cube/update_cube 支持 inflate、rotation、pivot；set_uv 支持每面 uv_size（可把设计图指定到任意面）。',
    parameters: {
      note: { type: 'string', description: '写入 Undo 标签的说明' },
      ops: { type: 'array', description: 'ops 数组，见 docs/03 §3.6', required: true },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
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
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
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
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
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
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
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
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
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
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
    async execute(args, exec) {
      try {
        const method = args.op === 'create' ? 'texture.pbr_create' : 'texture.pbr_list'
        return await callTool('bb_texture_pbr', method, args, { timeoutMs: 30000, signal: exec?.signal, mutating: args.op === 'create' })
      } catch (error) { return errorResult(error) }
    },
  })

  // ---- 视口实时反馈工具（docs/07 眼睛 A/B）--------------------------------

  const LOOK_OUTPUT = {
    schema: { type: 'object', additionalProperties: true },
    render: (_a, v) => {
      if (!v || v.ok === false) return textBlocks(v ?? 'look failed')
      const { attachment, ...rest } = v
      const { result, ...clean } = rest
      const blocks = textBlocks(clean)
      if (attachment) blocks.push({ type: 'image', attachment })
      return blocks
    },
  }

  tool({
    name: 'bb_look',
    description: '【最常用】看一眼当前模型。可指定任意相机角度或固定机位，多格合成为一张图返回。'
      + '用于确认造型、比例、配色、以及"刚改完到底长什么样"。返回一张拼图（约 180-260 token），比调三次 bb_render_views 便宜得多。'
      + 'cells 每项可为 {view:"front"} 或 {camera:{azimuth,elevation}}；不传则默认 front + iso_fr。',
    parameters: {
      cells: { type: 'array', description: '格子列表：[{view:"front"} | {camera:{azimuth:45,elevation:15}}]；默认 front+iso_fr' },
      camera: { type: 'object', description: '统一相机：{azimuth,elevation,distance,projection:"ortho"|"persp",fov,padding}', additionalProperties: false },
      focus: { type: 'string', description: '聚焦元素名（骨骼/方块），如 "Head"' },
      cell: { type: 'number', description: '单格像素，默认 320；要看清细节用 512/640' },
      cols: { type: 'number', description: '列数；默认自动接近正方形' },
      background: { type: 'string', description: '底色 #RRGGBB；传 "transparent" 用透明背景' },
      attach: { type: 'boolean', description: '是否附图（默认 true）' },
    },
    output: LOOK_OUTPUT,
    async execute(args, exec) {
      try {
        const cells = Array.isArray(args.cells) && args.cells.length
          ? args.cells
          : [{ view: 'front' }, { view: 'iso_fr' }]
        const bg = args.background === 'transparent' ? null : args.background
        const autoCols = args.cols ?? Math.max(1, Math.ceil(Math.sqrt(cells.length * 1.33)))
        const r = await renderSheet({
          tool: 'bb_look', cells, cell: args.cell, cols: autoCols,
          background: bg, focus: args.focus, signal: exec?.signal,
        })
        if (!r.ok) return r
        if (args.attach === false) return { ok: true, meta: r.meta }
        return { ok: true, ...r.meta, attachment: r.attachment }
      } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_camera',
    description: '读或设置 AI 自己的离屏相机位姿。get 返回当前角度，便于"接着上次的角度继续看"；'
      + '设置后相机保持，后续 bb_look 不传相机就沿用。不改变用户在 Blockbench GUI 里的视角。',
    parameters: {
      get: { type: 'boolean', description: 'true = 只读当前位姿，不做设置' },
      azimuth: { type: 'number', description: '方位角：0=正前，90=右侧，180=背后（度，顺时针）' },
      elevation: { type: 'number', description: '俯仰角：0=水平，90=正上方（度）' },
      distance: { type: 'number', description: '相机距离；不传按模型尺寸自动' },
      projection: { type: 'string', description: 'ortho（默认）| persp' },
      fov: { type: 'number', description: '透视视角（projection=persp 时生效）' },
      focus: { type: 'string', description: '以某元素为中心' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
    async execute(args, exec) {
      try {
        if (args.get === true || (args.azimuth === undefined && args.elevation === undefined)) {
          return await call('camera.get', { source: 'offscreen' }, 10000)
        }
        return await call('camera.set', args, 15000)
      } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_orbit',
    description: '【自由转动】绕模型转一圈，把 N 个角度合成为一张拼图（默认 8 个角度 360°）。'
      + '替代"靠三视图脑补"：一次调用就能从任意方位核对轮廓、对称性、背面和侧面穿模。'
      + '每格角落有编号，可以直接说"第 5 格背面有问题"。',
    parameters: {
      steps: { type: 'number', description: '角度个数，默认 8（2-24）' },
      from: { type: 'number', description: '起始角度，默认 0' },
      to: { type: 'number', description: '结束角度，默认 360' },
      elevation: { type: 'number', description: '俯仰角，默认 15（略俯视）' },
      axis: { type: 'string', description: 'y（默认，水平转）| x（上下翻）' },
      cell: { type: 'number', description: '单格像素，默认 320' },
      focus: { type: 'string', description: '围绕某元素转' },
      background: { type: 'string', description: '底色 #RRGGBB；默认深灰' },
      attach: { type: 'boolean', description: '是否附图（默认 true）' },
    },
    output: LOOK_OUTPUT,
    async execute(args, exec) {
      try {
        const steps = Math.max(2, Math.min(24, Math.round(Number(args.steps) || 8)))
        const from = Number.isFinite(args.from) ? args.from : 0
        const to = Number.isFinite(args.to) ? args.to : 360
        const elevation = Number.isFinite(args.elevation) ? args.elevation : 15
        const cells = []
        for (let i = 0; i < steps; i++) {
          const t = i / steps
          const angle = from + (to - from) * t
          cells.push(args.axis === 'x'
            ? { camera: { azimuth: 0, elevation: angle } }
            : { camera: { azimuth: angle, elevation } })
        }
        const bg = args.background === 'transparent' ? null : args.background
        // 自动列数：让整体接近 4:3，避免 8 格竖排成长条（320×2560）
        const autoCols = args.cols ?? Math.max(1, Math.ceil(Math.sqrt(steps * 1.33)))
        const r = await renderSheet({
          tool: 'bb_orbit', cells, cell: args.cell, cols: autoCols,
          background: bg, focus: args.focus, signal: exec?.signal,
        })
        if (!r.ok) return r
        if (args.attach === false) return { ok: true, meta: r.meta }
        return {
          ok: true, ...r.meta,
          hint: `第 1 格是方位 ${from}°，每格间隔 ${((to - from) / steps).toFixed(0)}°，共 ${steps} 格。`,
          attachment: r.attachment,
        }
      } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_anim_check',
    description: '【动作检查】把某个动画在时间轴上采样若干帧、合成为一张拼图，用来确认动作幅度、起止姿势、有无穿模。'
      + 'YSM 自带基础动画，建模完成后可用它逐个检查动作。',
    parameters: {
      animation: { type: 'string', description: '动画名，如 "animation.main.wave"；不传用当前选中动画' },
      from: { type: 'number', description: '起始时间（秒），默认 0' },
      to: { type: 'number', description: '结束时间（秒），默认整段长度' },
      samples: { type: 'number', description: '采样帧数，默认 4（2-16）' },
      cell: { type: 'number', description: '单格像素，默认 320' },
      camera: { type: 'object', description: '统一相机角度（默认 iso_fr 略俯视）', additionalProperties: false },
      focus: { type: 'string', description: '聚焦元素' },
      background: { type: 'string', description: '底色' },
      attach: { type: 'boolean', description: '是否附图（默认 true）' },
    },
    output: LOOK_OUTPUT,
    async execute(args, exec) {
      try {
        // 先查动画长度，用于默认 to
        let to = args.to
        if (!Number.isFinite(to)) {
          const list = await call('animation.list', {}, 10000).catch(() => null)
          // 注意：bridge 的 animation.list 字段名是 `animation`（不是 name）
          const hit = (list?.animations ?? []).find((a) => (a.animation ?? a.name) === args.animation)
          to = hit?.length ?? 1
        }
        const samples = Math.max(2, Math.min(16, Math.round(Number(args.samples) || 4)))
        const from = Number.isFinite(args.from) ? args.from : 0
        const cells = []
        for (let i = 0; i < samples; i++) {
          const t = samples === 1 ? 0 : from + ((to - from) * i) / (samples - 1)
          cells.push({ time: +t.toFixed(3), camera: args.camera ?? { azimuth: 135, elevation: 15 } })
        }
        const bg = args.background === 'transparent' ? null : args.background
        const r = await renderSheet({
          tool: 'bb_anim_check', cells, cell: args.cell,
          background: bg, focus: args.focus, animation: args.animation, signal: exec?.signal,
        })
        if (!r.ok) return r
        if (args.attach === false) return { ok: true, meta: r.meta }
        return {
          ok: true, ...r.meta,
          animation: args.animation ?? null,
          span: [from, to],
          hint: `按时间顺序：${cells.map((c) => `${c.time}s`).join(' → ')}`,
          attachment: r.attachment,
        }
      } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_render_views',
    description: '用固定机位无头渲染当前模型；默认透明背景、768px、front/right/iso_fr 三视图，图片作为附件返回（最多 4 张）。结果含逐图 changed/alpha_ratio/bbox/edge_touch 与 review（watchdog-v2：empty/clipped/no-visible-change/no-progress 判定与建议）。',
    parameters: {
      views: { type: 'array', description: 'front/back/left/right/top/bottom/iso_fr/iso_fl/iso_br/iso_bl/closeup' },
      size: { type: 'array', description: '[w,h]，默认 [768,768]' },
      transparent: { type: 'boolean' },
      antialias: { type: 'string', description: 'off|msaa|ssaa（ssaa 为 2x 超采样后缩小）' },
      focus: { type: 'object', description: '{element:"Head", padding?} 局部特写；closeup 默认 Head', properties: { element: { type: 'string' }, padding: { type: 'number' } }, additionalProperties: false },
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
        let result
        try {
          result = await raceAbort(call('render.views', args, 120000), exec?.signal)
        } catch (error) {
          const code = error?.rpc?.data?.code ?? error?.code
          if (['ENGINE_DEGRADED', 'RENDER_FAILED', 'TIMEOUT'].includes(code) && !state.safeMode && cfg.executable && cfg.appPath) {
            const restarted = await restartInSafeMode()
            if (!restarted) return errorResult(error)
            result = await raceAbort(call('render.views', args, 120000), exec?.signal)
            result.safe_mode_fallback = true
          } else {
            return errorResult(error)
          }
        }
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
        // inline 模式：不落盘、直接回 base64，走统一的"一张图"交付路径（docs/07 B3）
        const result = await raceAbort(call('render.texture', {
          ...args,
          inline: true,
          background: args.background ?? cfg.autoLookBackground,
        }, 30000), exec?.signal)
        if (!result?.png) return result
        const attachment = await saveInlineAttachment(result.png, `texture-${result.texture ?? 'tex'}-${Date.now()}.png`)
        if (!attachment) return { ...result, png: undefined, attachment_error: 'attachment failed' }
        lookStats.images += 1
        const { png, ...rest } = result
        return {
          ok: true, ...rest,
          tokens_est: imageTokens(result.width, result.height),
          attachment,
        }
      } catch (error) { return errorResult(error) }
    },
  })

  // ---- 参考图收集（docs/11，零安装）---------------------------------------

  /** 上一次搜索结果，供 bb_ref_collect 免传 urls。 */
  let lastRefSearch = null

  /** 角色名 → 安全的目录名。 */
  function slugify(s) {
    return String(s || 'ref')
      .replace(/[\\/:*?"<>|\s]+/g, '_')
      .replace(/^[._]+|[._]+$/g, '')
      .slice(0, 48) || 'ref'
  }

  /** dHash 汉明距离（16 进制字符串 XOR 后数 1）。 */
  function hammingHex(a, b) {
    try {
      const x = BigInt(`0x${a}`) ^ BigInt(`0x${b}`)
      let n = 0n
      let v = x
      while (v > 0n) { if (v & 1n) n += 1n; v >>= 1n }
      return Number(n)
    } catch { return 64 }
  }

  /**
   * 去掉 undefined / 非有限数 / 函数，保证返回值是「无损 JSON」。
   * DSH 会校验工具输出能否 JSON 往返 —— 带 undefined 字段的对象会被判为 lossy 而整次调用失败。
   */
  function lossless(value) {
    if (Array.isArray(value)) return value.map(lossless)
    if (value && typeof value === 'object') {
      const out = {}
      for (const [k, v] of Object.entries(value)) {
        if (v === undefined || typeof v === 'function') continue
        out[k] = lossless(v)
      }
      return out
    }
    if (typeof value === 'number' && !Number.isFinite(value)) return null
    return value
  }

  tool({
    name: 'bb_ref_search',
    description: '按角色名在多个图片源搜索**造型参考图**（正面/侧面/背面的官方立绘、设定集、动画截图）。'
      + '内置 Bing / 360 / 萌娘百科图库三个源，单源失败自动跳过并在 sources 里报告状态。'
      + '结果按「信息密度」先验排序：设定集/全身立绘 > 一般图。'
      + '拿到列表后调用 bb_ref_collect 下载并拼成对照表。找不到的源会明确写 error，不要谎报成功。',
    parameters: {
      character: { type: 'string', required: true, description: '角色名（中文/日文/英文都可以）' },
      queries: { type: 'array', description: '自定义查询词数组；省略则用内置模板（设定集/三视图/全身立绘/背面/日英版本）' },
      sources: { type: 'array', description: `源 id 白名单，可选：${REF_SOURCES.map((s) => s.id).join(' / ')}；省略用全部` },
      per_source: { type: 'number', description: '每个源每次查询取多少条，默认 30（5-50）' },
      max_queries: { type: 'number', description: '最多用几个查询词，默认 6' },
      timeout_ms: { type: 'number', description: '单次请求超时，默认 20000' },
      limit: { type: 'number', description: '返回给模型的候选条数上限，默认 60' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args, exec) {
      try {
        const t0 = Date.now()
        const res = await raceAbort(searchRefs({
          character: args.character,
          extraQueries: Array.isArray(args.queries) ? args.queries : undefined,
          sources: Array.isArray(args.sources) && args.sources.length ? args.sources : (cfg.refSources?.length ? cfg.refSources : undefined),
          perSource: args.per_source,
          maxQueries: args.max_queries,
          timeoutMs: args.timeout_ms ?? cfg.refTimeoutMs,
          signal: exec?.signal,
          onLog: log,
        }), exec?.signal)
        const sorted = sortCandidates(res.candidates)
        lastRefSearch = { character: args.character, candidates: sorted, sources: res.sources, queries: res.queries }
        const limit = Math.max(1, Math.min(200, args.limit ?? 60))
        const okSources = res.sources.filter((s) => s.ok)
        return lossless({
          ok: true,
          character: args.character,
          total: sorted.length,
          queries: res.queries,
          sources: res.sources,
          sources_ok: okSources.length,
          sources_total: res.sources.length,
          elapsed_ms: Date.now() - t0,
          candidates: sorted.slice(0, limit).map((c, i) => ({
            i,
            url: c.url,
            source: c.source,
            kind: c.kind,
            size: c.width && c.height ? `${c.width}x${c.height}` : null,
            page: c.pageUrl ?? null,
            query: c.query ?? null,
          })),
          hint: sorted.length
            ? '下一步：bb_ref_collect（不传 urls 会用这次结果）'
            : '所有源都没结果：换角色名（日文/英文）或显式传 queries 再试一次；仍为空就说明网上确实没有',
        })
      } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_ref_collect',
    description: '把候选参考图**下载到本地并拼成一张带编号的对照表**返回（一张图，省 token）。'
      + '会做格式校验、精确去重（sha256）、感知去重（dHash 汉明距离），并把清单写成 refs.json。'
      + '拿到的编号可以直接用来指认角度（例如"#3 是背面"），后续再据此定建模方案。'
      + '**必须真的看图判断**：这张表里的图是不是同一角色、各自是什么角度，不能靠 URL 猜。',
    parameters: {
      urls: { type: 'array', description: '要下载的图片 URL 数组；省略则用上一次 bb_ref_search 的结果' },
      max_images: { type: 'number', description: '最多保留几张，默认 24（1-80）' },
      out_dir: { type: 'string', description: 'workspace 下的子目录名；默认 refs/<角色名>' },
      cell: { type: 'number', description: '对照表单格像素，默认 240' },
      cols: { type: 'number', description: '列数；省略自动' },
      concurrency: { type: 'number', description: '下载并发，默认 6' },
      dedupe: { type: 'boolean', description: '是否做感知去重，默认 true' },
      attach: { type: 'boolean', description: '是否附图（默认 true）' },
    },
    output: LOOK_OUTPUT,
    async execute(args, exec) {
      try {
        const t0 = Date.now()
        const hasUrls = Array.isArray(args.urls) && args.urls.length > 0
        if (!hasUrls && !lastRefSearch?.candidates?.length) {
          return {
            ok: false, code: 'NO_CANDIDATES',
            message: '还没有候选图：先调用 bb_ref_search，或直接传 urls',
            hint: 'bb_ref_search({character:"角色名"}) → bb_ref_collect()',
          }
        }
        const candidates = hasUrls
          ? args.urls.map((url) => ({ url: String(url), kind: 'custom' }))
          : lastRefSearch.candidates
        const relDir = String(args.out_dir || path.posix.join(cfg.refDir, slugify(lastRefSearch?.character || 'ref')))
          .replace(/\\/g, '/')
          .replace(/^\/+/, '')
        const absDir = path.resolve(workspace, relDir)
        if (!absDir.startsWith(workspace + path.sep) && absDir !== workspace) {
          return { ok: false, code: 'INVALID_PARAMS', message: `out_dir escapes workspace: ${relDir}` }
        }

        const collected = await raceAbort(collectRefs({
          candidates,
          outDir: absDir,
          fsp,
          maxImages: args.max_images ?? cfg.refMaxImages,
          concurrency: args.concurrency ?? cfg.refConcurrency,
          timeoutMs: cfg.refTimeoutMs,
          signal: exec?.signal,
          onLog: log,
        }), exec?.signal)

        if (!collected.images.length) {
          return {
            ok: false, code: 'DOWNLOAD_FAILED',
            message: `候选 ${collected.attempted} 个，全部下载失败或不合格`,
            hint: '换源/换查询词；很多图站对非浏览器请求返回 403',
          }
        }

        // 转成 workspace 相对路径给 bridge
        const toRel = (abs) => path.relative(workspace, abs).split(path.sep).join('/')
        const compose = async (files) => raceAbort(call('ref.sheet', {
          files,
          cell: args.cell ?? cfg.refCell,
          cols: args.cols,
          background: '#141418',
          labels: true,
          hash: true,
        }, 60000), exec?.signal)

        let sheet = await compose(collected.images.map((im) => toRel(im.file)))

        // 感知去重：dHash 汉明距离 <= 阈值视为同一张图
        let duplicates = []
        if (args.dedupe !== false) {
          const byName = new Map((sheet.images || []).map((r) => [r.file, r]))
          const kept = []
          for (const im of collected.images) {
            const rec = byName.get(toRel(im.file))
            const h = rec?.dhash
            if (!h) { kept.push(im); continue }
            const dupOf = kept.find((k) => k._dhash && hammingHex(k._dhash, h) <= 6)
            if (dupOf) {
              duplicates.push({ name: im.name, dupOf: dupOf.name, url: im.url })
              continue
            }
            im._dhash = h
            kept.push(im)
          }
          if (duplicates.length) {
            collected.images = kept
            sheet = await compose(kept.map((im) => toRel(im.file)))
          }
        }

        const hashByName = new Map((sheet.images || []).map((r) => [r.file, r]))
        const images = collected.images.map((im, i) => {
          const rec = hashByName.get(toRel(im.file))
          return {
            index: i,
            name: im.name,
            // 对照表里的编号 = 数组下标，方便模型直接说 "#3"
            file: im.file,
            rel: toRel(im.file),
            size: im.width && im.height ? `${im.width}x${im.height}` : undefined,
            bytes: im.bytes,
            source: im.source,
            kind: im.kind,
            dhash: rec?.dhash ?? null,
            url: im.url,
            page: im.pageUrl,
          }
        })

        // 清单落盘，便于后续标注与复用
        const manifest = {
          generatedAt: new Date().toISOString(),
          character: lastRefSearch?.character ?? null,
          queries: lastRefSearch?.queries ?? [],
          sources: lastRefSearch?.sources ?? [],
          attempted: collected.attempted,
          duplicates,
          images,
        }
        try {
          await fsp.writeFile(path.join(absDir, 'refs.json'), JSON.stringify(manifest, null, 2), 'utf8')
        } catch (error) { log('refs.json write failed:', error?.message) }

        const tokens = imageTokens(sheet.width, sheet.height)
        let attachment = null
        if (args.attach !== false) {
          attachment = await saveInlineAttachment(sheet.png, `refs-${Date.now()}.png`)
          if (attachment) lookStats.images += 1
        }

        return lossless({
          ok: true,
          dir: relDir,
          count: images.length,
          duplicates_removed: duplicates.length,
          attempted: collected.attempted,
          sheet: { width: sheet.width, height: sheet.height, cols: sheet.cols, rows: sheet.rows, cell: sheet.cell },
          tokens_est: tokens,
          images,
          elapsed_ms: Date.now() - t0,
          hint: '看这张对照表：确认哪些是同一角色、各是什么角度（正面/侧面/背面/设定集），'
            + '并把判断写成结论。编号就是 images[].index。',
          ...(attachment ? { attachment } : {}),
          ...(attachment ? {} : { attachment_error: 'attachment failed' }),
        })
      } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_spec_save',
    description: '保存「建模规格」（spec）：把看参考图得到的结论固化成结构化数据，并校验是否符合语料规律。'
      + '校验项：部位/骨骼/方块数是否完整、配色是否合法、方块总数与头部占比是否落在实测区间、'
      + '**缺背面参考时是否在 gaps 里记录**（没记录会直接报错）。'
      + '通过后返回构建计划（按什么顺序建、每个骨骼给多少方块、贴图怎么分区），后续按计划调用 bb_* 建模。',
    parameters: {
      // 注意：DSH 要求 object 类型参数必须显式声明 additionalProperties，
      // 否则整条插件会 fiberPhase=failed（不只是这个工具失败）。
      spec: {
        type: 'object',
        description: '规格对象：{character, references, palette, parts, budget, gaps, notes}',
        required: true,
        properties: {},
        additionalProperties: true,
      },
      name: { type: 'string', description: '文件名（默认用 character.name）' },
      write_markdown: { type: 'boolean', description: '同时写一份人读 .md，默认 true' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args) {
      try {
        const check = validateSpec(args.spec)
        if (!check.ok) {
          return lossless({
            ok: false,
            code: 'SPEC_INVALID',
            message: `规格校验失败：${check.errors.length} 个错误`,
            errors: check.errors,
            warnings: check.warnings,
            hint: '按 errors 改 spec 再保存；gaps 里要写明"缺背面参考"这类缺口',
          })
        }
        const plan = derivePlan(check.spec)
        const md = renderSpecMarkdown(check.spec, plan)
        const baseName = slugify(args.name || check.spec.character.name || 'model')
        const relDir = `${cfg.specDir}`.replace(/\\/g, '/')
        const absDir = path.resolve(workspace, relDir)
        if (!absDir.startsWith(workspace + path.sep) && absDir !== workspace) {
          return { ok: false, code: 'INVALID_PARAMS', message: `specDir escapes workspace: ${relDir}` }
        }
        await fsp.mkdir(absDir, { recursive: true })
        const jsonAbs = path.join(absDir, `${baseName}.json`)
        await fsp.writeFile(jsonAbs, JSON.stringify({ ...check.spec, plan }, null, 2), 'utf8')
        if (args.write_markdown !== false) {
          await fsp.writeFile(path.join(absDir, `${baseName}.md`), md, 'utf8')
        }
        return lossless({
          ok: true,
          version: SPEC_VERSION,
          path: `${relDir}/${baseName}.json`,
          markdown: args.write_markdown !== false ? `${relDir}/${baseName}.md` : null,
          warnings: check.warnings,
          totals: plan.totals,
          order: plan.order,
          bones: plan.bones,
          texture: plan.texture,
          hint: '按 order 顺序建；每个 bone 用 plan.bones 里的方块数做预算。'
            + '建的过程中用 bb_look / bb_orbit 对照参考图核对。',
        })
      } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_spec_load',
    description: '读取已保存的建模规格，重新校验并返回构建计划（spec + plan + 人读 markdown）。'
      + '换会话/隔天继续时用它恢复上下文，不用重新看图。',
    parameters: {
      name: { type: 'string', description: '规格文件名（不含扩展名）；省略则列出 specs/ 下所有规格' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => textBlocks(v) },
    async execute(args) {
      try {
        const relDir = `${cfg.specDir}`.replace(/\\/g, '/')
        const absDir = path.resolve(workspace, relDir)
        if (!fs.existsSync(absDir)) {
          return { ok: false, code: 'SPEC_NOT_FOUND', message: `还没有规格目录：${relDir}`, hint: '先调用 bb_spec_save' }
        }
        if (!args.name) {
          const files = fs.readdirSync(absDir).filter((f) => f.endsWith('.json'))
          return lossless({
            ok: true,
            dir: relDir,
            specs: files.map((f) => {
              let meta = null
              try {
                const d = JSON.parse(fs.readFileSync(path.join(absDir, f), 'utf8'))
                meta = {
                  character: d?.character?.name ?? null,
                  parts: Array.isArray(d?.parts) ? d.parts.length : null,
                  cubes: d?.plan?.totals?.cubes ?? null,
                  headShare: d?.plan?.totals?.headShare ?? null,
                }
              } catch { /* ignore */ }
              return { name: f.replace(/\.json$/, ''), file: f, ...(meta ?? {}) }
            }),
            hint: 'bb_spec_load({name:"..."}) 载入某一份',
          })
        }
        const base = slugify(args.name)
        const jsonAbs = path.join(absDir, `${base}.json`)
        if (!fs.existsSync(jsonAbs)) {
          return { ok: false, code: 'SPEC_NOT_FOUND', message: `找不到 ${relDir}/${base}.json` }
        }
        const stored = JSON.parse(await fsp.readFile(jsonAbs, 'utf8'))
        const check = validateSpec(stored)
        const plan = derivePlan(check.spec)
        return lossless({
          ok: true,
          path: `${relDir}/${base}.json`,
          valid: check.ok,
          errors: check.errors,
          warnings: check.warnings,
          spec: check.spec,
          plan,
          markdown: renderSpecMarkdown(check.spec, plan),
        })
      } catch (error) { return errorResult(error) }
    },
  })

  tool({
    name: 'bb_validate',
    description: '按 YSM 规范校验当前项目；A 级定位组缺失=error，B 级默认层级偏离=warning。导出前必须调用。',
    parameters: { strict: { type: 'boolean' } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
    async execute(args) { try { return await call('project.validate', args, 30000) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_checkpoint',
    description: '把当前项目保存为 .bbmodel 检查点，并同步内嵌当前贴图像素；若 arm tab 打开也一并快照。大改或导出前调用。',
    parameters: { label: { type: 'string' }, note: { type: 'string' } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
    async execute(args, exec) { try { return await callTool('bb_checkpoint', 'project.checkpoint', args, { timeoutMs: 30000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_revisions',
    description: '列出最近的 .bbmodel 检查点与当前 revision。',
    parameters: { limit: { type: 'number' } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
    async execute(args) { try { return await call('project.revisions', args, 10000) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_restore',
    description: '恢复到指定 revision 的 .bbmodel 检查点（破坏性：丢弃当前未保存改动，需 confirm:true）。内嵌贴图会一起恢复；arm 有快照时从快照加载，否则从磁盘重载。',
    parameters: {
      revision: { type: 'number', required: true },
      confirm: { type: 'boolean', description: '必须为 true' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
    async execute(args, exec) { try { return await callTool('bb_restore', 'project.restore', args, { timeoutMs: 60000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_save_project',
    description: '把当前项目显式写回 workspace/pack：模型 JSON、动画、控制器、贴图 PNG 与 ysm.json。',
    parameters: {},
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
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
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
    async execute(args, exec) { try { return await callTool('bb_export_ysm', 'project.export_ysm', args, { timeoutMs: 300000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_project_close',
    description: '关闭当前项目（先保存/检查点自行负责）；force=true 跳过未保存提示。',
    parameters: { force: { type: 'boolean', description: '默认 true' } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
    async execute(args, exec) { try { return await callTool('bb_project_close', 'project.close', args, { timeoutMs: 15000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_animation_list',
    description: '列出动画名、时长、循环方式、路径与关键帧数量；含控制器/状态及已绑定动画。',
    parameters: {},
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
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
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
    async execute(args, exec) { try { return await callTool('bb_animation_create', 'animation.create', args, { timeoutMs: 30000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_animation_patch',
    description: '动画原子变更：update_animation/set_keyframes/delete_keyframes/delete_animation/bind_controller，一组 ops 一个 Undo。',
    parameters: {
      note: { type: 'string' },
      ops: { type: 'array', description: '动画 ops 数组，见 docs/03 §3.10', required: true },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
    async execute(args, exec) { try { return await callTool('bb_animation_patch', 'animation.apply_patch', args, { timeoutMs: 30000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_animation_delete',
    description: '删除一个动画。',
    parameters: { animation: { type: 'string', required: true } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
    async execute(args, exec) { try { return await callTool('bb_animation_delete', 'animation.delete', args, { timeoutMs: 30000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_texture_export_png',
    description: '把指定纹理导出为 PNG（workspace 内路径），返回宽高与字节数。',
    parameters: {
      texture: { type: 'string' },
      out_dir: { type: 'string', description: 'workspace 相对目录，默认 artifacts/textures' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
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
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
    async execute(args, exec) { try { return await callTool('bb_texture_import_png', 'texture.import_png', args, { timeoutMs: 60000, signal: exec?.signal }) } catch (error) { return errorResult(error) } },
  })

  tool({
    name: 'bb_batch',
    description: '把多个 bb_* 调用合并成一次工具往返（顺序执行；当前不保证原子回滚）。失败即停止并返回已完成项。',
    parameters: {
      calls: { type: 'array', description: '[{tool:"bb_...", args:{...}}]', required: true },
      stop_on_error: { type: 'boolean', description: '默认 true' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
    async execute(args, exec) {
      const calls = Array.isArray(args.calls) ? args.calls : []
      if (!calls.length) return { ok: false, code: 'INVALID_PARAMS', message: 'calls is empty' }
      if (calls.length > 16) return { ok: false, code: 'RESOURCE_LIMIT', message: 'max 16 calls per batch' }
      const results = []
      // 子调用可能带图片块（bb_look / bb_render_views / bb_render_texture / 自动附图）。
      // 以前整包塞进 JSON 会把 image block 丢掉，模型看不到图；这里统一收集到最后。
      const imageBlocks = []
      const collect = (value, toolName) => {
        if (!value || typeof value !== 'object') return
        // 1) 自动附图块
        if (Array.isArray(value.__autoLookBlocks)) {
          for (const b of value.__autoLookBlocks) if (b?.type === 'image') imageBlocks.push(b)
        }
        // 2) 普通 attachment（bb_look / bb_render_texture / bb_orbit / bb_anim_check）
        if (value.attachment?.attachmentId) {
          imageBlocks.push({ type: 'image', attachment: value.attachment })
        }
        // 3) bb_render_views 的 images[]
        if (Array.isArray(value.images)) {
          for (const img of value.images) {
            if (img?.attachment?.attachmentId) imageBlocks.push({ type: 'image', attachment: img.attachment })
          }
        }
      }
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
          collect(result, item.tool)
          // 结果里去掉图片块与 base64，只保留可读摘要（避免 JSON 体积暴涨）
          const slim = result && typeof result === 'object'
            ? (() => {
              const { __autoLookBlocks, __autoLook, png, data_url, attachment, ...rest } = result
              const out = { ...rest }
              if (Array.isArray(out.images)) {
                out.images = out.images.map(({ attachment: _a, ...i }) => i)
              }
              if (attachment) out.attachment = { attached: true, bytes: attachment.bytes }
              return out
            })()
            : result
          results.push({ tool: item.tool, ok: result?.ok !== false, result: slim })
          if (result?.ok === false && args.stop_on_error !== false) break
        } catch (error) {
          results.push({ tool: item.tool, ok: false, ...errorResult(error) })
          if (args.stop_on_error !== false) break
        }
      }
      // 注意：bb_batch 本身不是写操作工具，不会触发 withAutoLook，
      // 所以这里收集的子图不会被重复包装。
      const value = {
        ok: results.every((r) => r.ok),
        revision: state.revision,
        results,
        rolled_back: false,
      }
      if (imageBlocks.length) {
        // 复用 __autoLookBlocks 通道，由 renderWithAutoLook 统一转成 image block
        value.__autoLookBlocks = [
          { type: 'text', text: `【批量结果附图】共 ${imageBlocks.length} 张` },
          ...imageBlocks,
        ]
      }
      return value
    },
  })

  tool({
    name: 'bb_diagnostics',
    description: '输出 Blockbench Agent 的运行诊断：连接/进程/端口/版本/最近心跳/日志尾部，用于排障。',
    parameters: {},
    output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
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
        transport: cfg.bridgeTransport || 'auto', safeMode: state.safeMode,
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
      output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
      async execute(args) { try { return await call('gui.show', args, 10000) } catch (error) { return errorResult(error) } },
    })
    tool({
      name: 'bb_hide_gui',
      description: '隐藏 Blockbench 窗口并同步用户改动。',
      parameters: {},
      output: { schema: { type: 'object', additionalProperties: true }, render: (_a, v) => renderWithAutoLook(v) },
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
      const look = {
        autoLook: cfg.autoLook,
        disabledByBudget: lookStats.disabledByBudget,
        imagesThisSession: lookStats.images,
        budget: cfg.sessionImageBudget,
        autolookRenders: lookStats.autolook,
        offloadedImages: lookStats.offloaded,
        lastError: lookStats.lastError,
      }
      if (!state.connected) {
        return { kind: 'success', text: `未连接。rpc=${state.rpcUrl || '(not started)'} lastError=${JSON.stringify(state.lastError)}\n看图：${JSON.stringify(look)}` }
      }
      const result = await call('session.status', {}, 5000)
      return { kind: 'success', text: `${JSON.stringify(result)}\n看图：${JSON.stringify(look)}` }
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
      '- bb_look / bb_camera / bb_orbit / bb_anim_check（新：看模型的四只眼睛）',
      '- bb_render_views / bb_render_texture',
      '- bb_validate / bb_checkpoint / bb_revisions / bb_restore',
      '- bb_save_project / bb_export_ysm / bb_batch / bb_diagnostics',
      '命令：/show 显示窗口，/hide 隐藏并同步，/bb-status 状态，/bb-start 启动运行时。',
    ].join('\n'),
  }))

  // ------------------------------------------------------------ Web UI status endpoint
  // Client 插件（client.js）通过同源 GET /bb-agent/status 读取实时状态，避免额外 IPC。
  ctx.effect(() => {
    const webServer = ctx.get?.('webServer')
    if (!webServer?.register) return undefined
    return webServer.register({
      kind: 'exact',
      path: '/bb-agent/status',
      handler: async (req, res) => {
        let remote = null
        try {
          if (state.connected) remote = await call('session.status', {}, 2000)
        } catch { /* runtime busy */ }
        const payload = {
          ok: true,
          version: '0.4.0',
          connected: !!state.connected,
          state: remote?.state ?? (state.connected ? 'idle' : 'offline'),
          revision: remote?.revision ?? state.revision,
          gui_visible: remote?.gui_visible ?? state.guiVisible,
          budgets: remote?.budgets ?? null,
          loop: remote?.loop ?? null,
          last_render: remote?.last_render ?? null,
          review: remote?.last_render?.review ?? null,
          runtime: {
            child_pid: state.child?.pid ?? null,
            workspace: state.workspace,
            safe_mode: state.safeMode,
            last_error: state.lastError,
          },
          updated_at: new Date().toISOString(),
        }
        try {
          res.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' })
          res.end(JSON.stringify(payload))
        } catch { /* client closed */ }
      },
    })
  })

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



