// BB-Agent Bridge Plugin · Blockbench renderer 侧（设计参考骨架）
// 加载方式：由 agent/main.js 在 Blockbench 初始化完成后执行
//   new Plugin().loadFromFile({path, name, content:''}, false)
//
// 职责：作为 WebSocket 客户端连接 dsh Host 的 BridgeServer，处理其下发的 JSON-RPC 请求。
// 依赖 Blockbench 全局：Plugin/Project/Group/Cube/Texture/Animation/Codecs/Undo/Canvas/Preview/
// MediaPreview/DefaultCameraPresets/Screencam/Blockbench/ipcRenderer/@electron/remote。
//
// 说明：本文件只实现“可跑通协议 + 核心编辑/渲染”的最小集合；标注 TODO(YRL) 的部分
// 需要接入 docs/03 与 research/ysm-format.md 的完整 YSM 逻辑。

(function () {
  'use strict'

  const cfg = window.__BB_AGENT__
  if (!cfg || window.__BB_AGENT_BRIDGE__) return
  const BRIDGE_ID = cfg.bridgeId || 'bb-agent-bridge'
  const WS_URL = cfg.rpcUrl
  const TOKEN = cfg.token
  const TRANSPORT_PREF = cfg.transport || 'auto'
  let httpMode = false
  let eventSource = null
  let httpBase = ''
  try {
    const u = new URL(WS_URL)
    u.protocol = u.protocol === 'wss:' ? 'https:' : 'http:'
    httpBase = u.origin
  } catch { /* ignore */ }
  const remoteApi = (() => { try { return require('@electron/remote') } catch { return null } })()
  const currentWindow = () => {
    try { return remoteApi?.getCurrentWindow?.() ?? null } catch { return null }
  }
  // fs：主进程已预写 plugin_permissions.json 授权；失败时回退 Blockbench IO（需目录已存在）
  const nodeFs = (() => {
    try {
      if (typeof requireNativeModule === 'function') return requireNativeModule('fs')
    } catch (error) { console.warn('[bb-agent] fs permission unavailable', error?.message ?? error) }
    return null
  })()

  const state = {
    state: 'booting',
    revision: 0,
    project: null,
    guiVisible: false,
    userEditing: false,
    agentEditing: false,
    startedAt: Date.now(),
    lastError: null,
    counters: { edits: 0, renders: 0, saves: 0, exports: 0, restores: 0 },
    limits: { edits: 60, renders: 40, restores: 2 },
    lastRender: null,
    loop: { pendingEdits: 0, unchangedStreak: 0, lastRenderRevision: null },
    dirtyTextures: new Set(),
    dirtyAnimations: new Set(),
    dirtyControllers: new Set(),
  }

  // 变更类方法：GUI 可见时冻结；支持 expected_revision 前置条件；受预算限制
  const MUTATING_METHODS = new Set([
    'project.create_ysm', 'project.open_pack', 'project.close', 'project.save', 'project.export_ysm',
    'project.checkpoint', 'project.restore',
    'model.apply_patch',
    'texture.create', 'texture.select', 'texture.apply_patch', 'texture.import_png',
    'animation.create', 'animation.apply_patch', 'animation.delete',
  ])

  const pathModule = (() => { try { return require('path') } catch { return null } })()

  // ------------------------------------------------------------------ 工具函数
  const vec = (v) => {
    if (Array.isArray(v)) return v.slice()
    if (v && typeof v === 'object') return [v.x ?? 0, v.y ?? 0, v.z ?? 0]
    return [0, 0, 0]
  }
  const num = (v, fallback = 0) => (typeof v === 'number' && Number.isFinite(v) ? v : fallback)
  const colorOk = (c) => typeof c === 'string' && /^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(c)
  const err = (code, message, data = {}) => Object.assign(new Error(message), { bbCode: code, bbData: data })
  const ensureProject = () => {
    let active = (typeof Project !== 'undefined' && Project) ? Project : (window.Project ?? null)
    if ((!active || active === 0) && state.project?.mainProject && ModelProject.all.includes(state.project.mainProject)) {
      try { state.project.mainProject.select?.() } catch { /* ignore */ }
      active = (typeof Project !== 'undefined' && Project) ? Project : (window.Project ?? null)
    }
    if (!active || active === 0) throw err('PROJECT_NOT_OPEN', 'no project open')
    return active
  }
  const findGroup = (ref) => {
    if (ref === undefined || ref === null) return null
    return Group.all.find((g) => g.uuid === ref || g.name === ref) ?? null
  }
  const findCube = (ref) => Cube.all.find((c) => c.uuid === ref || c.name === ref) ?? null
  const findTexture = (ref) => {
    if (!ref) return Texture.selected ?? Texture.all[0] ?? null
    return Texture.all.find((t) => t.uuid === ref || t.name === ref || t.name === `${ref}.png`) ?? null
  }
  const undoAspects = () => ({ elements: Cube.all.slice(), groups: Group.all.slice() })
  const textureOpaqueRatio = (tex) => {
    try {
      const canvas = tex.canvas
      if (!canvas?.width || !canvas?.height) return null
      const ctx = canvas.getContext('2d')
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data
      let opaque = 0
      for (let i = 3; i < data.length; i += 4) if (data[i] > 0) opaque += 1
      return Math.round((opaque / (canvas.width * canvas.height)) * 1000) / 1000
    } catch { return null }
  }
  const bump = (source, changed = []) => {
    state.revision += 1
    if (state.loop && ['agent', 'user', 'restore'].includes(source)) state.loop.pendingEdits += 1
    notify('event.project_changed', { revision: state.revision, source, changed })
    return state.revision
  }

  function workspacePath(...parts) {
    const base = String(cfg.workspace || '').replace(/[\\/]+$/, '')
    const sep = base.includes('\\') ? '\\' : '/'
    return [base, ...parts].join(sep)
  }
  function ensureDir(dir) {
    try {
      const scopedFs = nodeFs ?? (typeof fs !== 'undefined' ? fs : null) ?? window.fs ?? null
      if (scopedFs?.mkdirSync) scopedFs.mkdirSync(dir, { recursive: true })
    } catch (error) { console.warn('[bb-agent] mkdir failed', dir, error?.message ?? error) }
  }
  function writeBlockbenchFile(filePath, content, savetype) {
    ensureDir(filePath.replace(/[\\/][^\\/]+$/, ''))
    Blockbench.writeFile(filePath, { content, savetype: savetype || 'text' })
  }

  // ------------------------------------------------------------------ YRL v0（YSM pack 读写）
  const joinPath = (...parts) => (pathModule ? pathModule.join(...parts) : parts.join('\\').replace(/\\+/g, '\\'))
  const packAbsolute = (packDir, rel) => joinPath(packDir, ...String(rel).split(/[\\/]+/).filter(Boolean))

  function readTextSync(absPath) {
    if (!nodeFs?.readFileSync) throw err('INTERNAL_ERROR', 'fs permission unavailable')
    return nodeFs.readFileSync(absPath, 'utf8')
  }
  function readJsonSync(absPath) {
    return JSON.parse(readTextSync(absPath))
  }
  function copyDirRecursive(src, dst) {
    if (!nodeFs) throw err('INTERNAL_ERROR', 'fs permission unavailable')
    ensureDir(dst)
    for (const entry of nodeFs.readdirSync(src)) {
      const s = joinPath(src, entry), d = joinPath(dst, entry)
      const stat = nodeFs.statSync(s)
      if (stat.isDirectory()) copyDirRecursive(s, d)
      else nodeFs.copyFileSync(s, d)
    }
  }
  function listFilesRecursive(root, rel = '') {
    if (!nodeFs?.readdirSync) return []
    const out = []
    for (const entry of nodeFs.readdirSync(joinPath(root, rel))) {
      const relPath = rel ? `${rel}/${entry}` : entry
      const stat = nodeFs.statSync(joinPath(root, relPath))
      if (stat.isDirectory()) out.push(...listFilesRecursive(root, relPath))
      else out.push(relPath)
    }
    return out
  }

  /** 零依赖 ZIP 写入（deflate；无 zlib 时退化为 store） */
  function createZipFromDir(rootDir, zipPath) {
    if (!nodeFs?.readFileSync) throw err('INTERNAL_ERROR', 'fs permission unavailable')
    let zlib = null
    try { zlib = require('zlib') } catch { /* store */ }
    const files = listFilesRecursive(rootDir).sort()
    const crcTable = new Uint32Array(256)
    for (let n = 0; n < 256; n++) {
      let c = n
      for (let k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1)
      crcTable[n] = c >>> 0
    }
    const crc32 = (buf) => {
      let c = 0xffffffff
      for (let i = 0; i < buf.length; i++) c = crcTable[(c ^ buf[i]) & 0xff] ^ (c >>> 8)
      return (c ^ 0xffffffff) >>> 0
    }
    const dosTime = (mtime) => {
      const d = mtime ? new Date(mtime) : new Date()
      const time = ((d.getHours() & 0x1f) << 11) | ((d.getMinutes() & 0x3f) << 5) | (Math.floor(d.getSeconds() / 2) & 0x1f)
      const date = (((d.getFullYear() - 1980) & 0x7f) << 9) | (((d.getMonth() + 1) & 0x0f) << 5) | (d.getDate() & 0x1f)
      return { time, date }
    }
    const localParts = []
    const centralParts = []
    let offset = 0
    for (const rel of files) {
      const abs = joinPath(rootDir, ...rel.split('/'))
      const data = nodeFs.readFileSync(abs)
      const name = Buffer.from(rel, 'utf8')
      const crc = crc32(data)
      const store = !zlib
      const method = store ? 0 : 8
      const compressed = store ? data : zlib.deflateRawSync(data, { level: 6 })
      const dt = dosTime(nodeFs.statSync(abs).mtimeMs)
      const local = Buffer.alloc(30)
      local.writeUInt32LE(0x04034b50, 0)
      local.writeUInt16LE(20, 4)
      local.writeUInt16LE(0x0800, 6)
      local.writeUInt16LE(method, 8)
      local.writeUInt16LE(dt.time, 10)
      local.writeUInt16LE(dt.date, 12)
      local.writeUInt32LE(crc, 14)
      local.writeUInt32LE(compressed.length, 18)
      local.writeUInt32LE(data.length, 22)
      local.writeUInt16LE(name.length, 26)
      local.writeUInt16LE(0, 28)
      localParts.push(local, name, compressed)
      const central = Buffer.alloc(46)
      central.writeUInt32LE(0x02014b50, 0)
      central.writeUInt16LE(20, 4)
      central.writeUInt16LE(20, 6)
      central.writeUInt16LE(0x0800, 8)
      central.writeUInt16LE(method, 10)
      central.writeUInt16LE(dt.time, 12)
      central.writeUInt16LE(dt.date, 14)
      central.writeUInt32LE(crc, 16)
      central.writeUInt32LE(compressed.length, 20)
      central.writeUInt32LE(data.length, 24)
      central.writeUInt16LE(name.length, 28)
      central.writeUInt16LE(0, 30)
      central.writeUInt16LE(0, 32)
      central.writeUInt16LE(0, 34)
      central.writeUInt16LE(0, 36)
      central.writeUInt32LE(0, 38)
      central.writeUInt32LE(offset, 42)
      centralParts.push(central, name)
      offset += local.length + name.length + compressed.length
    }
    const centralSize = centralParts.reduce((sum, b) => sum + b.length, 0)
    const end = Buffer.alloc(22)
    end.writeUInt32LE(0x06054b50, 0)
    end.writeUInt16LE(0, 4)
    end.writeUInt16LE(0, 6)
    end.writeUInt16LE(files.length, 8)
    end.writeUInt16LE(files.length, 10)
    end.writeUInt32LE(centralSize, 12)
    end.writeUInt32LE(offset, 16)
    end.writeUInt16LE(0, 20)
    const zipBuffer = Buffer.concat([...localParts, ...centralParts, end])
    nodeFs.writeFileSync(zipPath, zipBuffer)
    return { path: zipPath, files: files.length, bytes: zipBuffer.length }
  }

  /** YSM spec2 的最小规范化（只补必填/默认，未知字段保留；不实现插件 load→save 的 UI 默认值） */
  function normalizeYsm(ysmJson) {
    const out = JSON.parse(JSON.stringify(ysmJson ?? {}))
    out.spec = 2
    const metadata = out.metadata ?? (out.metadata = {})
    if (!metadata.name) metadata.name = 'Unnamed'
    if (!metadata.license || !metadata.license.type) metadata.license = { type: 'All Rights Reserved' }
    const files = out.files ?? (out.files = {})
    const player = files.player ?? (files.player = {})
    const model = player.model ?? (player.model = {})
    if (!model.main) model.main = 'models/main.json'
    if (!model.arm) model.arm = 'models/arm.json'
    const props = out.properties ?? (out.properties = {})
    if (typeof props.height_scale !== 'number') props.height_scale = 0.7
    if (typeof props.width_scale !== 'number') props.width_scale = 0.7
    if (!props.preview_animation) props.preview_animation = 'idle'
    if (!Array.isArray(player.texture)) player.texture = []
    return out
  }

  function textureEntries(ysmJson) {
    const list = ysmJson?.files?.player?.texture ?? []
    return list.map((entry) => {
      if (typeof entry === 'string') return { uv: entry }
      return entry ?? {}
    }).filter((entry) => entry.uv)
  }

  function ysmTextureName(relPath) {
    const base = String(relPath).replace(/\\/g, '/').split('/').pop() ?? relPath
    return base.replace(/\.[^.]+$/, '')
  }

  function addTexturesToCurrentProject(packDir, ysmJson) {
    const map = new Map()
    for (const entry of textureEntries(ysmJson)) {
      const abs = packAbsolute(packDir, entry.uv)
      if (!nodeFs.existsSync(abs)) continue
      const tex = new Texture()
      tex.fromFile({ path: abs })
      tex.add(false)
      tex.path = abs
      tex.name = ysmTextureName(entry.uv)
      map.set(tex.name, tex)
    }
    return map
  }

  async function waitForTextureSize(textureMap) {
    for (const tex of textureMap.values()) {
      const started = Date.now()
      while ((!tex.width || !tex.height) && Date.now() - started < 2000) await new Promise((r) => setTimeout(r, 20))
    }
  }

  async function loadArmFromDisk(packDir, ysmJson) {
    const rel = ysmJson?.files?.player?.model?.arm
    if (!rel) return null
    const abs = packAbsolute(packDir, rel)
    if (!nodeFs?.existsSync?.(abs)) return null
    loadModelFile({ path: abs, content: readTextSync(abs), name: pathModule.basename(abs) })
    const armProject = Project
    const armTextureMap = addTexturesToCurrentProject(packDir, ysmJson)
    await waitForTextureSize(armTextureMap)
    const defaultName = ysmJson?.properties?.default_texture
    const tex = armTextureMap.get(defaultName) ?? [...armTextureMap.values()][0] ?? null
    if (tex) {
      tex.select?.()
      const texUuid = tex.uuid
      for (const cube of Cube.all) {
        for (const faceName of Object.keys(cube.faces ?? {})) if (cube.faces[faceName]) cube.faces[faceName].texture = texUuid
      }
      Canvas.updateAllFaces?.()
    }
    return { armProject, armTextureMap }
  }

  async function loadYsmPack(packDir, ysmJson) {
    const mainPath = packAbsolute(packDir, ysmJson.files?.player?.model?.main ?? 'models/main.json')
    const armPath = packAbsolute(packDir, ysmJson.files?.player?.model?.arm ?? 'models/arm.json')
    if (!nodeFs?.existsSync?.(mainPath)) throw err('PACK_INVALID', `main model missing: ${mainPath}`)
    loadModelFile({ path: mainPath, content: readTextSync(mainPath), name: pathModule.basename(mainPath) })
    const mainProject = Project
    // 贴图：主项目打开状态下创建（Texture.add 会挂到当前 Project）
    const textureMap = addTexturesToCurrentProject(packDir, ysmJson)
    await waitForTextureSize(textureMap)
    // 动画 / 控制器：loadFile 不弹窗
    const animationPaths = Object.values(ysmJson.files?.player?.animation ?? {}).filter(Boolean)
    for (const rel of animationPaths) {
      const abs = packAbsolute(packDir, rel)
      if (!nodeFs.existsSync(abs)) continue
      try { AnimationCodec.codecs.bedrock.loadFile({ path: abs, content: readTextSync(abs) }) } catch (error) { console.warn('[bb-agent] animation load failed', rel, error?.message) }
    }
    for (const rel of ysmJson.files?.player?.animation_controllers ?? []) {
      const abs = packAbsolute(packDir, rel)
      if (!nodeFs.existsSync(abs)) continue
      try { AnimationCodec.codecs.bedrock_animation_controller.loadFile({ path: abs, content: readTextSync(abs) }) } catch (error) { console.warn('[bb-agent] controller load failed', rel, error?.message) }
    }
    // 第一人称手臂模型（独立 tab，独立贴图对象）
    let armProject = null
    let armTextureMap = new Map()
    if (nodeFs.existsSync(armPath)) {
      loadModelFile({ path: armPath, content: readTextSync(armPath), name: pathModule.basename(armPath) })
      armProject = Project
      armTextureMap = addTexturesToCurrentProject(packDir, ysmJson)
      await waitForTextureSize(armTextureMap)
    }
    // 每个项目各自选择默认贴图并绑定所有面（bedrock single_texture）
    const defaultName = ysmJson.properties?.default_texture || textureEntries(ysmJson).map((e) => ysmTextureName(e.uv))[0] || ''
    const pickDefault = (map) => map.get(defaultName) ?? [...map.values()][0] ?? null
    let defaultTexture = null
    for (const [project, map] of [[mainProject, textureMap], [armProject, armTextureMap]]) {
      if (!project) continue
      project.select?.()
      const tex = pickDefault(map)
      if (!tex) continue
      if (!defaultTexture) defaultTexture = tex
      tex.select?.()
      Texture.selected = tex
      const texUuid = tex.uuid
      for (const cube of Cube.all) {
        for (const faceName of Object.keys(cube.faces ?? {})) if (cube.faces[faceName]) cube.faces[faceName].texture = texUuid
      }
      Canvas.updateAllFaces?.()
    }
    mainProject?.select?.()
    Canvas.updateAll?.()
    return { mainProject, armProject, textureMap, armTextureMap, defaultTexture }
  }

  function writeYsmFile(packDir, ysmJson) {
    const content = JSON.stringify(normalizeYsm(ysmJson), null, 2) + '\n'
    writeBlockbenchFile(packAbsolute(packDir, 'ysm.json'), content, 'text')
    return content
  }

  function selectProject(project) {
    try { project?.select?.() } catch { /* ignore */ }
  }
  function selectMainProject() {
    selectProject(state.project?.mainProject)
  }

  /** 显式保存回 pack：模型/动画/控制器/贴图/ysm.json（不依赖 ysm-utils 或 export_over） */
  function saveYsmPack(packDir, ysmJson) {
    const files = []
    try { Settings.set('export_empty_groups', true) } catch { /* ignore */ }
    // 1) 模型（每个 ModelProject tab 逐个 compile/write）
    for (const project of ModelProject.all) {
      selectProject(project)
      const codec = Codecs[project.export_codec] ?? Codecs.bedrock
      const target = project.export_path
      if (!target) continue
      const content = codec.compile()
      writeBlockbenchFile(target, content, 'text')
      files.push({ path: target, bytes: content.length })
    }
    // 2) 动画/控制器：只写脏文件（未修改则保留磁盘原文件，避免重排/膨胀）
    selectMainProject()
    const animPaths = [...new Set(Animation.all.map((a) => a.path).filter(Boolean))]
    for (const animPath of animPaths) {
      const dirty = state.dirtyAnimations.has(animPath)
      if (!dirty && nodeFs?.existsSync?.(animPath)) continue
      try {
        AnimationCodec.codecs.bedrock.exportFile(animPath)
        state.dirtyAnimations.delete(animPath)
        files.push({ path: animPath })
      } catch (error) {
        console.warn('[bb-agent] animation save failed', animPath, error?.message)
        files.push({ path: animPath, error: error?.message ?? String(error) })
      }
    }
    const controllerPaths = [...new Set((window.AnimationController?.all ?? []).map((c) => c.path).filter(Boolean))]
    for (const controllerPath of controllerPaths) {
      const dirty = state.dirtyControllers.has(controllerPath)
      if (!dirty && nodeFs?.existsSync?.(controllerPath)) continue
      try {
        AnimationCodec.codecs.bedrock_animation_controller.exportFile(controllerPath)
        state.dirtyControllers.delete(controllerPath)
        files.push({ path: controllerPath })
      } catch (error) {
        console.warn('[bb-agent] controller save failed', controllerPath, error?.message)
        files.push({ path: controllerPath, error: error?.message ?? String(error) })
      }
    }
    // 3) 贴图：只从主项目写；未编辑且磁盘已存在的贴图跳过（保持原始字节）
    selectMainProject()
    const textureRels = textureEntries(ysmJson).map((e) => e.uv)
    const writtenTextures = new Set()
    for (const tex of Texture.all) {
      let target = tex.path
      if (!target) {
        const rel = textureRels.find((p) => ysmTextureName(p) === tex.name) ?? `textures/${tex.name}.png`
        target = packAbsolute(packDir, rel)
      }
      if (writtenTextures.has(target)) continue
      const dirty = state.dirtyTextures.has(tex.uuid) || !tex.path
      if (!dirty && nodeFs?.existsSync?.(target)) continue
      writtenTextures.add(target)
      const dataUrl = tex.canvas.toDataURL('image/png')
      writeBlockbenchFile(target, dataUrl, 'image')
      state.dirtyTextures.delete(tex.uuid)
      files.push({ path: target, bytes: Math.round(dataUrl.length * 0.75) })
    }
    // 4) ysm.json
    const ysmContent = writeYsmFile(packDir, ysmJson)
    files.push({ path: packAbsolute(packDir, 'ysm.json'), bytes: ysmContent.length })
    selectMainProject()
    return files
  }

  function exportYsmPack(packDir, ysmJson, params = {}) {
    if (params.validate !== false) {
      const validation = handlers['project.validate']({ profile: 'ysm', strict: true })
      if (!validation.ok) {
        throw err('VALIDATION_FAILED', 'YSM validation failed', { code: 'VALIDATION_FAILED', errors: validation.errors, warnings: validation.warnings })
      }
    }
    const stamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14)
    const exportRoot = params.out_dir
      ? packAbsolute(String(cfg.workspace || ''), params.out_dir)
      : workspacePath('exports', stamp)
    const packName = pathModule.basename(packDir)
    const target = joinPath(exportRoot, packName)
    if (nodeFs.existsSync(target)) nodeFs.rmSync(target, { recursive: true, force: true })
    copyDirRecursive(packDir, target)
    const files = listFilesRecursive(target)
    let sha256 = null
    try { const cryptoLib = require('crypto'); sha256 = cryptoLib.createHash('sha256') } catch { /* ignore */ }
    const manifest = {
      exported_at: new Date().toISOString(),
      source_revision: state.revision,
      pack_name: packName,
      files: files.map((rel) => {
        const abs = joinPath(target, ...rel.split('/'))
        const bytes = nodeFs.statSync(abs).size
        let hash = ''
        if (sha256) { const h = require('crypto').createHash('sha256'); h.update(nodeFs.readFileSync(abs)); hash = h.digest('hex') }
        return { path: rel, bytes, sha256: hash }
      }),
    }
    const manifestContent = JSON.stringify(manifest, null, 2) + '\n'
    writeBlockbenchFile(joinPath(target, 'export-manifest.json'), manifestContent, 'text')
    let zip = null
    if (params.zip !== false) {
      try {
        const zipPath = `${target}.zip`
        zip = createZipFromDir(target, zipPath)
      } catch (error) {
        zip = { error: error?.message ?? String(error) }
      }
    }
    return {
      revision: state.revision,
      export_dir: target,
      zip_path: zip?.path ?? null,
      zip_files: zip?.files ?? null,
      zip_bytes: zip?.bytes ?? null,
      zip_error: zip?.error ?? null,
      files: { total: files.length + 1, models: files.filter((f) => f.startsWith('models/')).length, textures: files.filter((f) => f.startsWith('textures/')).length, animations: files.filter((f) => f.startsWith('animations/')).length },
      manifest: joinPath(target, 'export-manifest.json'),
      validation: params.validate === false ? null : { ok: true },
    }
  }

  // ------------------------------------------------------------------ WebSocket
  let socket = null
  let connected = false
  let helloDone = false
  let reconnectAttempt = 0
  const pending = new Map()
  let nextId = 1
  let disposed = false
  let heartbeatTimer = null

  function sendRaw(obj) {
    if (socket && socket.readyState === WebSocket.OPEN) { socket.send(JSON.stringify(obj)); return }
    if (httpMode && httpBase) { void httpRpc(obj).catch(() => { /* SSE 通道仅需送达 */ }) }
  }
  function notify(method, params) {
    sendRaw({ jsonrpc: '2.0', method, params })
  }

  function handleTransportMessage(msg) {
    if (msg.id !== undefined && msg.method === undefined) {
      const waiter = pending.get(msg.id)
      if (!waiter) return
      pending.delete(msg.id)
      clearTimeout(waiter.timer)
      if (msg.error) waiter.reject(Object.assign(new Error(msg.error.message), { rpc: msg.error }))
      else waiter.resolve(msg.result)
      return
    }
    if (typeof msg.method === 'string') void handleInbound(msg)
  }

  async function httpRpc(message) {
    const response = await fetch(`${httpBase}/rpc`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-bb-token': TOKEN },
      body: JSON.stringify(message),
    })
    if (response.status === 204) return null
    const text = await response.text()
    return text ? JSON.parse(text) : null
  }

  function startHeartbeat() {
    if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null }
    notify('event.heartbeat', heartbeatPayload())
    heartbeatTimer = setInterval(() => notify('event.heartbeat', heartbeatPayload()), 2000)
  }

  function handleDisconnect() {
    connected = false
    helloDone = false
    if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null }
    for (const [, waiter] of pending) { clearTimeout(waiter.timer); waiter.reject(err('DISCONNECTED', 'bridge disconnected')) }
    pending.clear()
  }

  function connect() {
    if (disposed || !WS_URL) return
    if (TRANSPORT_PREF === 'http' || httpMode) { void httpConnect(); return }
    try {
      socket = new WebSocket(WS_URL, ['bb-agent.v1'])
    } catch (error) {
      scheduleReconnect()
      return
    }
    socket.onopen = async () => {
      reconnectAttempt = 0
      try {
        const hello = await new Promise((resolve, reject) => {
          const id = `bb-${nextId++}`
          const timer = setTimeout(() => reject(err('TIMEOUT', 'hello timeout')), 5000)
          pending.set(id, { resolve, reject, timer })
          sendRaw({
            jsonrpc: '2.0', id, method: 'system.hello',
            params: {
              protocol: 'bb-agent/1',
              auth: { token: TOKEN },
              client: { name: 'bb-agent-bridge', version: '0.3.0' },
              requested_capabilities: ['render.offscreen', 'gui.show', 'ysm.v2'],
            },
            _meta: { deadline_ms: 5000 },
          })
        })
        connected = true
        helloDone = true
        state.state = 'idle'
        console.log('[bb-agent] connected', hello?.server?.version ?? '')
        startHeartbeat()
      } catch (error) {
        console.error('[bb-agent] hello failed', error)
        try { socket.close() } catch { /* ignore */ }
      }
    }
    socket.onmessage = (event) => {
      let msg
      try { msg = JSON.parse(event.data) } catch { return }
      handleTransportMessage(msg)
    }
    socket.onclose = () => {
      handleDisconnect()
      if (!disposed) {
        if (TRANSPORT_PREF === 'auto' && reconnectAttempt >= 2) httpMode = true
        scheduleReconnect()
      }
    }
    socket.onerror = () => { /* onclose 会处理 */ }
  }

  async function httpConnect() {
    if (disposed || !httpBase) return
    httpMode = true
    try {
      try { eventSource?.close?.() } catch { /* ignore */ }
      eventSource = new EventSource(`${httpBase}/events?token=${encodeURIComponent(TOKEN)}`)
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(err('TIMEOUT', 'sse timeout')), 6000)
        eventSource.onopen = () => { clearTimeout(timer); resolve() }
        eventSource.onerror = () => { clearTimeout(timer); reject(err('DISCONNECTED', 'sse failed')) }
      })
      eventSource.onmessage = (event) => {
        let msg
        try { msg = JSON.parse(event.data) } catch { return }
        handleTransportMessage(msg)
      }
      eventSource.onerror = () => {
        if (disposed) return
        connected = false
        helloDone = false
        scheduleReconnect()
      }
      const id = `bb-${nextId++}`
      const hello = await httpRpc({
        jsonrpc: '2.0', id, method: 'system.hello',
        params: {
          protocol: 'bb-agent/1',
          auth: { token: TOKEN },
          client: { name: 'bb-agent-bridge', version: '0.3.0', transport: 'http-sse' },
          requested_capabilities: ['render.offscreen', 'gui.show', 'ysm.v2'],
        },
        _meta: { deadline_ms: 5000 },
      })
      if (hello?.error) throw new Error(hello.error.message)
      connected = true
      helloDone = true
      state.state = 'idle'
      reconnectAttempt = 0
      console.log('[bb-agent] connected via http-sse', hello?.result?.server?.version ?? '')
      startHeartbeat()
    } catch (error) {
      connected = false
      console.error('[bb-agent] http connect failed', error?.message ?? error)
      scheduleReconnect()
    }
  }
  function call(method, params = {}, timeoutMs = 120000) {
    return new Promise((resolve, reject) => {
      if (!connected) {
        reject(err('PROJECT_NOT_OPEN', 'bridge not connected'))
        return
      }
      const id = `bb-${nextId++}`
      const timer = setTimeout(() => {
        pending.delete(id)
        reject(err('TIMEOUT', `${method} timeout`))
      }, timeoutMs)
      pending.set(id, { resolve, reject, timer })
      sendRaw({ jsonrpc: '2.0', id, method, params, _meta: { deadline_ms: timeoutMs } })
    })
  }

  function scheduleReconnect() {
    if (disposed) return
    reconnectAttempt += 1
    const delay = Math.min(8000, 500 * 2 ** Math.min(reconnectAttempt, 5))
    setTimeout(connect, delay)
  }

  function heartbeatPayload() {
    return {
      revision: state.revision,
      queue_len: 0,
      mem_mb: typeof performance !== 'undefined' && performance.memory
        ? Math.round(performance.memory.usedJSHeapSize / 1048576) : 0,
      gpu_ok: state.state !== 'degraded',
    }
  }

  // ------------------------------------------------------------------ RPC dispatch
  async function handleInbound(msg) {
    const id = msg.id ?? null
    try {
      const method = msg.method
      const params = msg.params ?? {}
      const handler = handlers[method]
      if (!handler) throw err('METHOD_NOT_FOUND', `method not found: ${method}`, { code: 'METHOD_NOT_FOUND' })
      if (MUTATING_METHODS.has(method)) {
        if (state.guiVisible) {
          throw err('GUI_BUSY', 'user is inspecting Blockbench; hide the GUI first', { code: 'GUI_BUSY', hint: 'run /hide or gui.hide' })
        }
        if (typeof params.expected_revision === 'number' && params.expected_revision !== state.revision) {
          throw err('REVISION_CONFLICT', `expected revision ${params.expected_revision} but current is ${state.revision}`, {
            code: 'REVISION_CONFLICT', expected_revision: params.expected_revision, actual_revision: state.revision,
            hint: 'call project.get_scene then retry', recoverable: true,
          })
        }
        if (state.counters.edits >= state.limits.edits && method !== 'project.save' && method !== 'project.export_ysm') {
          throw err('RESOURCE_LIMIT', `edit budget exhausted (${state.limits.edits})`, { code: 'RESOURCE_LIMIT', recoverable: true })
        }
      }
      if (method === 'project.restore' && state.counters.restores >= state.limits.restores) {
        throw err('RESOURCE_LIMIT', `restore budget exhausted (${state.limits.restores})`, { code: 'RESOURCE_LIMIT', recoverable: true })
      }
      state.agentEditing = MUTATING_METHODS.has(method)
      const result = await handler(params, msg._meta ?? {})
      sendRaw({ jsonrpc: '2.0', id, result })
    } catch (error) {
      state.lastError = { code: error?.bbCode ?? 'INTERNAL_ERROR', message: error?.message ?? String(error) }
      sendRaw({
        jsonrpc: '2.0', id,
        error: {
          code: error?.rpc?.code ?? -32603,
          message: error?.message ?? 'internal error',
          data: { code: error?.bbCode ?? 'INTERNAL_ERROR', ...(error?.bbData ?? {}), recoverable: true },
        },
      })
    } finally {
      state.agentEditing = false
    }
  }

  // ------------------------------------------------------------------ handlers
  const handlers = {}

  handlers['system.ping'] = (params) => ({ t: params.t ?? null, server_time: Date.now() })

  handlers['system.shutdown'] = () => {
    setTimeout(() => { try { ipcRenderer.send('bb-agent:shutdown') } catch { /* ignore */ } }, 10)
    return { bye: true }
  }

  handlers['session.status'] = () => ({
    state: state.state,
    project_id: state.project?.project_id ?? null,
    revision: state.revision,
    gui_visible: state.guiVisible,
    user_editing: state.userEditing,
    render_queue: 0,
    gpu_ok: state.state !== 'degraded',
    uptime_s: Math.round((Date.now() - state.startedAt) / 1000),
    budgets: {
      edits_used: state.counters.edits, edits_max: state.limits.edits,
      renders_used: state.counters.renders, renders_max: state.limits.renders,
      restores_used: state.counters.restores, restores_max: state.limits.restores,
    },
    last_error: state.lastError,
    last_render: state.lastRender,
    loop: state.loop,
  })

  handlers['project.create_ysm'] = async (params = {}) => {
    const name = String(params.name || 'agent_model')
    const packDir = params.pack_dir ? packAbsolute(String(cfg.workspace || ''), params.pack_dir) : workspacePath('pack')
    if (nodeFs.existsSync(packDir)) {
      if (params.overwrite !== true) throw err('PACK_EXISTS', `pack already exists: ${packDir}`, { code: 'PACK_EXISTS', hint: 'pass overwrite:true to replace' })
      nodeFs.rmSync(packDir, { recursive: true, force: true })
    }
    const templateCandidates = [
      joinPath(String(cfg.appRoot || ''), 'templates', 'ysm_default'),
      workspacePath('templates', 'ysm_default'),
    ]
    const template = templateCandidates.find((p) => p && nodeFs.existsSync(p))
    if (!template) throw err('PACK_INVALID', `YSM default template missing (looked in ${templateCandidates.join(', ')})`, { code: 'PACK_INVALID' })
    copyDirRecursive(template, packDir)
    const ysmJson = normalizeYsm(readJsonSync(joinPath(packDir, 'ysm.json')))
    ysmJson.metadata.name = name
    if (typeof params.height_scale === 'number') ysmJson.properties.height_scale = params.height_scale
    if (typeof params.width_scale === 'number') ysmJson.properties.width_scale = params.width_scale
    const loaded = await loadYsmPack(packDir, ysmJson)
    const textureIds = new Map()
    let bones = 0, cubes = 0
    for (const project of ModelProject.all) {
      project.select?.()
      bones += Group.all.length
      cubes += Cube.all.length
      for (const tex of Texture.all) textureIds.set(tex.name, tex)
    }
    loaded.mainProject?.select?.()
    Canvas.updateAll?.()
    state.project = {
      project_id: `${name}-${Math.random().toString(16).slice(2, 10)}`,
      pack_dir: packDir,
      ysmJson,
      mainProject: loaded.mainProject,
      armProject: loaded.armProject,
      textureMap: loaded.textureMap,
    }
    state.state = 'editing'
    state.userEditing = false
    state.counters = { edits: 0, renders: 0, saves: 0, exports: 0, restores: 0 }
    state.dirtyTextures = new Set()
    state.dirtyAnimations = new Set()
    state.dirtyControllers = new Set()
    state.lastRenderHashes = null
    state.lastRenderSignatures = null
    state.loop = { pendingEdits: 0, unchangedStreak: 0, lastRenderRevision: null }
    bump('agent')
    return {
      project_id: state.project.project_id,
      revision: state.revision,
      pack_dir: packDir,
      summary: { bones, cubes, textures: textureIds.size, animations: Animation.all.length, controllers: (window.AnimationController?.all ?? []).length },
      root_bones: Group.all.filter((g) => !g.parent).map((g) => ({ bone: g.name, id: g.uuid, parent: null, cubes: g.children?.length ?? 0 })),
      textures: [...textureIds.values()].map((t) => ({ texture: t.name, id: t.uuid, size: [t.width, t.height] })),
      warnings: [],
    }
  }

  handlers['project.get_scene'] = (params = {}) => {
    selectMainProject()
    ensureProject()
    const scope = params.scope ?? 'summary'
    const base = {
      revision: state.revision,
      counts: {
        bones: Group.all.length, cubes: Cube.all.length,
        textures: Texture.all.length, animations: Animation.all.length,
      },
    }
    if (scope === 'summary') {
      const bounds = modelBounds()
      return {
        ...base,
        project: { name: Project.name, format: Format?.id ?? 'bedrock', box_uv: !!Project.box_uv },
        bounds,
        textures: Texture.all.map((t) => ({
          texture: t.name, id: t.uuid, size: [t.width, t.height],
          opaque_ratio: textureOpaqueRatio(t),
        })),
        animations: { count: Animation.all.length, sample: Animation.all.slice(0, 8).map((a) => a.name) },
        warnings: [],
      }
    }
    if (scope === 'bones') {
      const limit = Math.min(100, Math.max(1, Number(params.limit) || 40))
      return {
        ...base,
        nodes: Group.all.slice(0, limit).map((g) => ({
          bone: g.name, id: g.uuid, parent: g.parent?.name ?? null,
          pivot: vec(g.origin), cubes: Cube.all.filter((c) => c.parent === g).length,
          children: (g.children ?? []).map((c) => c.name),
        })),
        total: Group.all.length,
        next_cursor: null,
      }
    }
    if (scope === 'bone' || scope === 'cube') {
      const el = scope === 'bone' ? findGroup(params.id) : findCube(params.id)
      if (!el) throw err('INVALID_REFERENCE', `unknown ${scope}: ${params.id}`, { code: 'INVALID_REFERENCE' })
      if (scope === 'bone') {
        return {
          bone: el.name, id: el.uuid, parent: el.parent?.name ?? null,
          pivot: vec(el.origin), rotation: vec(el.rotation),
          cubes: Cube.all.filter((c) => c.parent === el).map((c) => ({ cube_id: c.uuid, name: c.name, size: vec(c.to).map((v, i) => v - vec(c.from)[i]) })),
          children: (el.children ?? []).map((c) => c.name),
        }
      }
      const faceUv = {}
      if (!el.box_uv) {
        for (const [faceName, face] of Object.entries(el.faces ?? {})) {
          if (face?.uv) faceUv[faceName] = { uv: vec(face.uv).slice(0, 2), uv_size: vec(face.uv_size ?? [0, 0]).slice(0, 2) }
        }
      }
      const faceTextures = {}
      for (const [faceName, face] of Object.entries(el.faces ?? {})) {
        if (!face?.texture) continue
        const tex = Texture.all.find((t) => t.uuid === face.texture)
        faceTextures[faceName] = tex ? { id: tex.uuid, name: tex.name } : { id: face.texture, name: null }
      }
      return {
        cube_id: el.uuid, name: el.name, bone: el.parent?.name ?? null,
        origin: vec(el.from), size: vec(el.to).map((v, i) => v - vec(el.from)[i]),
        rotation: vec(el.rotation), pivot: vec(el.origin), inflate: num(el.inflate, 0),
        uv: el.box_uv ? { mode: 'box', uv: vec(el.uv_offset).slice(0, 2) } : { mode: 'faces', faces: faceUv },
        face_textures: faceTextures,
        textures: Texture.all.map((t) => ({ id: t.uuid, name: t.name })),
      }
    }
    if (scope === 'textures') {
      return { ...base, textures: Texture.all.map((t) => ({ texture: t.name, id: t.uuid, size: [t.width, t.height] })) }
    }
    if (scope === 'animations') {
      return { ...base, animations: Animation.all.map((a) => ({ animation: a.name, length: a.length, loop: a.loop })) }
    }
    throw err('UNSUPPORTED', `unsupported scope: ${scope}`, { code: 'UNSUPPORTED' })
  }

  function modelBounds() {
    if (!Cube.all.length) return [[0, 0, 0], [0, 0, 0]]
    const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity]
    for (const cube of Cube.all) {
      const from = vec(cube.from), to = vec(cube.to)
      for (let i = 0; i < 3; i++) {
        min[i] = Math.min(min[i], from[i], to[i])
        max[i] = Math.max(max[i], from[i], to[i])
      }
    }
    return [min, max]
  }

  handlers['project.get_element'] = (params) => handlers['project.get_scene']({ scope: params.id && findCube(params.id) ? 'cube' : 'bone', id: params.id })

  handlers['model.apply_patch'] = (params = {}) => {
    ensureProject()
    const ops = Array.isArray(params.ops) ? params.ops : []
    if (!ops.length) throw err('INVALID_PARAMS', 'ops is empty', { code: 'INVALID_PARAMS' })
    const aspects = undoAspects()
    Undo.initEdit(aspects)
    const changed = []
    let success = false
    try {
      for (const op of ops) {
        switch (op.op) {
          case 'add_bone': {
            const parent = op.parent ? findGroup(op.parent) : null
            const group = new Group({ name: op.name || 'Bone', origin: vec(op.pivot) })
            if (parent) group.addTo(parent)
            group.init()
            changed.push({ kind: 'bone', id: group.uuid, op: 'add', name: group.name })
            break
          }
          case 'add_cube': {
            const bone = findGroup(op.bone)
            if (!bone) throw err('INVALID_REFERENCE', `bone not found: ${op.bone}`, { code: 'INVALID_REFERENCE' })
            const origin = vec(op.origin), size = vec(op.size, [2, 2, 2])
            const cube = new Cube({
              from: origin,
              to: [origin[0] + size[0], origin[1] + size[1], origin[2] + size[2]],
              origin: [0, 0, 0],
              uv_offset: [0, 0],
              autouv: 1,
            })
            if (op.name) cube.name = op.name
            cube.init()
            if (!cube.box_uv) cube.mapAutoUV?.()
            if (Texture.all.length && Format?.single_texture) {
              const texName = op.texture ? String(op.texture).replace(/\.png$/i, '') : null
              const wantedTex = texName ? (state.project?.textureMap?.get(texName) ?? findTexture(texName)) : null
              const defaultTex = wantedTex ?? Texture.getDefault?.() ?? Texture.selected ?? Texture.all[0]
              if (defaultTex) for (const faceName of Object.keys(cube.faces ?? {})) if (cube.faces[faceName]) cube.faces[faceName].texture = defaultTex.uuid
            }
            if (bone) cube.addTo(bone)
            Canvas.updateView?.({ elements: [cube], element_aspects: { transform: true, geometry: true, faces: true } })
            if (op.uv?.mode === 'faces' && op.uv.faces) {
              cube.box_uv = false
              for (const [face, uv] of Object.entries(op.uv.faces)) {
                if (cube.faces?.[face] && Array.isArray(uv)) {
                  cube.faces[face].uv = [uv[0], uv[1]]
                  cube.faces[face].uv_size = [size[0], size[2]]
                }
              }
            }
            changed.push({ kind: 'cube', id: cube.uuid, op: 'add', bone: bone.name })
            break
          }
          case 'update_cube': {
            const cube = findCube(op.cube_id ?? op.id)
            if (!cube) throw err('INVALID_REFERENCE', `cube not found: ${op.cube_id ?? op.id}`, { code: 'INVALID_REFERENCE' })
            if (op.origin) cube.from = vec(op.origin)
            if (op.size) {
              const from = vec(cube.from)
              cube.to = [from[0] + op.size[0], from[1] + op.size[1], from[2] + op.size[2]]
            }
            if (op.rotation) cube.rotation = vec(op.rotation)
            if (op.pivot) cube.origin = vec(op.pivot)
            if (op.texture) {
              const tex = findTexture(op.texture)
              if (tex) for (const faceName of Object.keys(cube.faces ?? {})) if (cube.faces[faceName]) cube.faces[faceName].texture = tex.uuid
            }
            changed.push({ kind: 'cube', id: cube.uuid, op: 'update' })
            break
          }
          case 'update_bone': {
            const bone = findGroup(op.bone ?? op.id)
            if (!bone) throw err('INVALID_REFERENCE', `bone not found: ${op.bone ?? op.id}`, { code: 'INVALID_REFERENCE' })
            if (op.pivot) bone.origin = vec(op.pivot)
            if (op.rotation) bone.rotation = vec(op.rotation)
            if (op.name) bone.name = op.name
            changed.push({ kind: 'bone', id: bone.uuid, op: 'update' })
            break
          }
          case 'set_uv': {
            const ids = Array.isArray(op.ids) ? op.ids : [op.id]
            for (const id of ids.filter(Boolean)) {
              const cube = findCube(id)
              if (!cube) throw err('INVALID_REFERENCE', `cube not found: ${id}`, { code: 'INVALID_REFERENCE' })
              if (op.mode === 'box' || (!op.faces && op.uv)) {
                cube.box_uv = true
                cube.uv_offset = vec(op.uv ?? [0, 0])
              } else if (op.faces) {
                cube.box_uv = false
                const from = vec(cube.from)
                const size = [vec(cube.to)[0] - from[0], vec(cube.to)[1] - from[1], vec(cube.to)[2] - from[2]]
                const faceSize = {
                  north: [size[0], size[1]], south: [size[0], size[1]],
                  east: [size[2], size[1]], west: [size[2], size[1]],
                  up: [size[0], size[2]], down: [size[0], size[2]],
                }
                for (const [faceName, uv] of Object.entries(op.faces)) {
                  if (!cube.faces?.[faceName] || !Array.isArray(uv)) continue
                  cube.faces[faceName].uv = [uv[0], uv[1]]
                  cube.faces[faceName].uv_size = faceSize[faceName] ?? [size[0], size[1]]
                  // up/down 的内部约定：Y 方向取负（与默认模型一致）
                  if (faceName === 'up' || faceName === 'down') cube.faces[faceName].uv_size = [size[0], -size[2]]
                }
              }
              changed.push({ kind: 'cube', id: cube.uuid, op: 'set_uv' })
            }
            break
          }
          case 'rename': {
            const el = findGroup(op.id) ?? findCube(op.id)
            if (!el) throw err('INVALID_REFERENCE', `element not found: ${op.id}`, { code: 'INVALID_REFERENCE' })
            el.name = op.name
            changed.push({ kind: findGroup(op.id) ? 'bone' : 'cube', id: el.uuid, op: 'rename' })
            break
          }
          case 'delete': {
            for (const ref of op.refs ?? []) {
              const el = ref.kind === 'bone' ? findGroup(ref.id) : findCube(ref.id)
              if (!el) continue
              try { el.remove?.() } catch { /* ignore */ }
              changed.push({ kind: ref.kind, id: ref.id, op: 'delete' })
            }
            break
          }
          default:
            throw err('INVALID_OPERATION', `unsupported op: ${op.op}`, { code: 'INVALID_OPERATION' })
        }
      }
      Canvas.updateAll?.()
      state.state = 'editing'
      const revision = bump('agent', changed)
      state.counters.edits += 1
      success = true
      return { ok: true, revision, changed, warnings: [], digest: { revision, bones: Group.all.length, cubes: Cube.all.length } }
    } catch (error) {
      try { Undo.cancelEdit?.(true) } catch { /* ignore */ }
      throw error
    } finally {
      if (success) {
        try { Undo.finishEdit?.(params.note || 'Agent model patch', aspects) } catch { /* ignore */ }
      }
    }
  }

  // ---- texture -----------------------------------------------------------
  function paintTexture(tex, ops, clip) {
    const active = tex.getActiveCanvas()
    const canvas = active.canvas ?? active
    const ctx = active.ctx ?? canvas.getContext('2d')
    const off = active.offset ?? [0, 0]
    const w = canvas.width, h = canvas.height
    let painted = 0, clipped = 0
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    const mark = (x, y) => {
      minX = Math.min(minX, x); minY = Math.min(minY, y)
      maxX = Math.max(maxX, x); maxY = Math.max(maxY, y); painted++
    }
    const inBounds = (x, y) => x >= 0 && y >= 0 && x < w && y < h
    const px = (x, y, color) => {
      if (!inBounds(x, y)) { if (clip) clipped++; else throw err('INVALID_PARAMS', `pixel out of bounds ${x},${y}`); return }
      ctx.fillStyle = color; ctx.fillRect(x + off[0], y + off[1], 1, 1); mark(x, y)
    }
    const rect = (x1, y1, x2, y2, color, filled = true) => {
      const ax = Math.min(x1, x2), bx = Math.max(x1, x2), ay = Math.min(y1, y2), by = Math.max(y1, y2)
      for (let y = ay; y <= by; y++) {
        for (let x = ax; x <= bx; x++) {
          if (!filled && x !== ax && x !== bx && y !== ay && y !== by) continue
          px(x, y, color)
        }
      }
    }
    const line = (x1, y1, x2, y2, color) => {
      let x = x1, y = y1
      const dx = Math.abs(x2 - x1), dy = Math.abs(y2 - y1)
      const sx = x1 < x2 ? 1 : -1, sy = y1 < y2 ? 1 : -1
      let e = dx - dy
      for (;;) {
        px(x, y, color)
        if (x === x2 && y === y2) break
        const e2 = 2 * e
        if (e2 > -dy) { e -= dy; x += sx }
        if (e2 < dx) { e += dx; y += sy }
      }
    }
    for (const op of ops) {
      switch (op.op) {
        case 'pixel': px(op.x, op.y, op.color); break
        case 'rect': rect(op.x1, op.y1, op.x2, op.y2, op.color, op.filled !== false); break
        case 'line': line(op.x1, op.y1, op.x2, op.y2, op.color); break
        case 'clear': {
          if (op.region) ctx.clearRect(op.region[0], op.region[1], op.region[2] - op.region[0] + 1, op.region[3] - op.region[1] + 1)
          else ctx.clearRect(0, 0, w, h)
          break
        }
        case 'shade': {
          const { x1, y1, x2, y2, from, to, direction = 'v' } = op
          const ax = Math.min(x1, x2), bx = Math.max(x1, x2), ay = Math.min(y1, y2), by = Math.max(y1, y2)
          const lerp = (a, b, t) => a + (b - a) * t
          const parse = (c) => [parseInt(c.slice(1, 3), 16), parseInt(c.slice(3, 5), 16), parseInt(c.slice(5, 7), 16), c.length === 9 ? parseInt(c.slice(7, 9), 16) : 255]
          const A = parse(from), B = parse(to)
          for (let y = ay; y <= by; y++) for (let x = ax; x <= bx; x++) {
            const t = direction === 'h' ? (bx === ax ? 0 : (x - ax) / (bx - ax)) : (by === ay ? 0 : (y - ay) / (by - ay))
            const c = `#${[0, 1, 2, 3].map((i) => Math.round(lerp(A[i], B[i], t)).toString(16).padStart(2, '0')).join('')}`
            px(x, y, c)
          }
          break
        }
        case 'replace': {
          const region = op.region ?? [0, 0, w - 1, h - 1]
          const img = ctx.getImageData(region[0], region[1], region[2] - region[0] + 1, region[3] - region[1] + 1)
          const from = op.from.toLowerCase(), to = op.to
          const fr = parseInt(from.slice(1, 3), 16), fg = parseInt(from.slice(3, 5), 16), fb = parseInt(from.slice(5, 7), 16)
          const hasAlpha = from.length === 9, fa = hasAlpha ? parseInt(from.slice(7, 9), 16) : 255
          const data = img.data
          for (let i = 0; i < data.length; i += 4) {
            if (data[i] === fr && data[i + 1] === fg && data[i + 2] === fb && (!hasAlpha || data[i + 3] === fa)) {
              const p = [parseInt(to.slice(1, 3), 16), parseInt(to.slice(3, 5), 16), parseInt(to.slice(5, 7), 16), to.length === 9 ? parseInt(to.slice(7, 9), 16) : 255]
              data[i] = p[0]; data[i + 1] = p[1]; data[i + 2] = p[2]; data[i + 3] = p[3]
            }
          }
          ctx.putImageData(img, region[0], region[1])
          break
        }
        case 'copy_mirror': {
          const [sx1, sy1, sx2, sy2] = op.src
          const src = ctx.getImageData(sx1, sy1, sx2 - sx1 + 1, sy2 - sy1 + 1)
          const c2 = document.createElement('canvas')
          c2.width = src.width; c2.height = src.height
          const ctx2 = c2.getContext('2d')
          ctx2.putImageData(src, 0, 0)
          ctx.save()
          if (op.axis === 'y') { ctx.translate(0, sy1 * 2); ctx.scale(1, -1) }
          else { ctx.translate(sx1 * 2, 0); ctx.scale(-1, 1) }
          ctx.drawImage(c2, 0, 0)
          ctx.restore()
          painted += src.width * src.height
          break
        }
        default:
          throw err('INVALID_OPERATION', `unsupported texture op: ${op.op}`, { code: 'INVALID_OPERATION' })
      }
    }
    return { painted, clipped, bounds: painted ? [minX, minY, maxX, maxY] : null }
  }

  handlers['texture.create'] = async (params = {}) => {
    ensureProject()
    const name = String(params.name || 'texture')
    const width = Math.min(2048, Math.max(16, Number(params.width) || 128))
    const height = Math.min(2048, Math.max(16, Number(params.height) || 128))
    const canvas = document.createElement('canvas')
    canvas.width = width; canvas.height = height
    const ctx = canvas.getContext('2d')
    if (params.fill && colorOk(params.fill)) { ctx.fillStyle = params.fill; ctx.fillRect(0, 0, width, height) }
    const tex = new Texture({ name })
    tex.fromDataURL(canvas.toDataURL('image/png'))
    tex.add(false)
    // 不能覆盖 tex.img.onload（Texture 构造里用它同步 width/height）；轮询等待加载
    {
      const started = Date.now()
      while ((!tex.width || !tex.height) && Date.now() - started < 2000) {
        await new Promise((resolve) => setTimeout(resolve, 20))
      }
      if (!tex.width || !tex.height) {
        // 兜底：直接以已绘制 canvas 初始化
        tex.canvas.width = width; tex.canvas.height = height
        tex.ctx.drawImage(canvas, 0, 0)
        tex.width = width; tex.height = height
        tex.source = tex.canvas.toDataURL('image/png')
      }
    }
    if (params.make_active !== false) {
      tex.select?.()
      Texture.selected = tex
    }
    tex.updateChangesAfterEdit?.()
    const revision = bump('agent', [{ kind: 'texture', id: tex.uuid, op: 'create' }])
    state.counters.edits += 1
    state.dirtyTextures.add(tex.uuid)
    return { texture: tex.name, id: tex.uuid, size: [tex.width, tex.height], revision }
  }

  handlers['texture.select'] = (params = {}) => {
    ensureProject()
    const tex = findTexture(params.texture ?? params.texture_id)
    if (!tex) throw err('INVALID_REFERENCE', `texture not found: ${params.texture ?? params.texture_id}`, { code: 'INVALID_REFERENCE' })
    tex.select?.()
    Texture.selected = tex
    return { texture: tex.name, id: tex.uuid, revision: state.revision }
  }

  handlers['texture.apply_patch'] = (params = {}) => {
    ensureProject()
    const tex = findTexture(params.texture)
    if (!tex) throw err('INVALID_REFERENCE', `texture not found: ${params.texture}`, { code: 'INVALID_REFERENCE' })
    if (!tex.width || !tex.height) throw err('INVALID_OPERATION', 'texture not loaded (width=0)', { code: 'INVALID_OPERATION' })
    const ops = Array.isArray(params.ops) ? params.ops : []
    const aspects = { textures: [tex], bitmap: true }
    Undo.initEdit(aspects)
    let success = false
    try {
      if (!tex.internal) tex.convertToInternal?.()
      const result = paintTexture(tex, ops, params.clip !== false)
      tex.updateChangesAfterEdit()
      const revision = bump('agent', [{ kind: 'texture', id: tex.uuid, op: 'paint' }])
      state.counters.edits += 1
      state.dirtyTextures.add(tex.uuid)
      let palette = []
      if (params.return_palette !== false) {
        try {
          const canvas = tex.getActiveCanvas().canvas ?? tex.canvas
          const ctx = tex.getActiveCanvas().ctx ?? tex.ctx
          const img = ctx.getImageData(0, 0, canvas.width, canvas.height)
          const counts = new Map()
          for (let i = 0; i < img.data.length; i += 4) {
            if (img.data[i + 3] === 0) continue
            const key = `#${[img.data[i], img.data[i + 1], img.data[i + 2]].map((v) => v.toString(16).padStart(2, '0')).join('')}`
            counts.set(key, (counts.get(key) ?? 0) + 1)
          }
          palette = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([color, count]) => ({ color, count }))
        } catch { /* ignore */ }
      }
      success = true
      return {
        ok: true, revision, texture: tex.name,
        painted_pixels: result.painted, clipped_pixels: result.clipped,
        bounds: result.bounds, palette, warnings: [],
      }
    } catch (error) {
      try { Undo.cancelEdit?.(true) } catch { /* ignore */ }
      throw error
    } finally {
      if (success) {
        try { Undo.finishEdit?.(params.note || 'Agent texture patch', aspects) } catch { /* ignore */ }
      }
    }
  }

  handlers['texture.read'] = (params = {}) => {
    ensureProject()
    const tex = findTexture(params.texture)
    if (!tex) throw err('INVALID_REFERENCE', `texture not found: ${params.texture}`, { code: 'INVALID_REFERENCE' })
    const region = params.region ?? [0, 0, tex.width - 1, tex.height - 1]
    const ctx = tex.getActiveCanvas().ctx ?? tex.ctx
    const img = ctx.getImageData(region[0], region[1], region[2] - region[0] + 1, region[3] - region[1] + 1)
    const data = img.data
    if (params.format === 'ascii') {
      const counts = new Map()
      for (let i = 0; i < data.length; i += 4) {
        const key = `#${[data[i], data[i + 1], data[i + 2]].map((v) => v.toString(16).padStart(2, '0')).join('')}`
        counts.set(key, (counts.get(key) ?? 0) + 1)
      }
      const palette = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 16)
      const chars = 'abcdefghijklmnop'
      const legend = {}
      palette.forEach(([color], i) => { legend[chars[i]] = color })
      const rows = []
      for (let y = 0; y < img.height; y++) {
        let row = ''
        for (let x = 0; x < img.width; x++) {
          const i = (y * img.width + x) * 4
          const key = `#${[data[i], data[i + 1], data[i + 2]].map((v) => v.toString(16).padStart(2, '0')).join('')}`
          const idx = palette.findIndex(([c]) => c === key)
          row += idx >= 0 ? chars[idx] : ' '
        }
        rows.push(row)
      }
      return { width: tex.width, height: tex.height, region, format: 'ascii', legend, rows }
    }
    const counts = new Map()
    let transparent = 0
    for (let i = 0; i < data.length; i += 4) {
      if (data[i + 3] === 0) { transparent++; continue }
      const key = `#${[data[i], data[i + 1], data[i + 2]].map((v) => v.toString(16).padStart(2, '0')).join('')}${data[i + 3] < 255 ? data[i + 3].toString(16).padStart(2, '0') : ''}`
      counts.set(key, (counts.get(key) ?? 0) + 1)
    }
    const palette = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, params.max_colors ?? 16)
    return { width: tex.width, height: tex.height, region, palette: palette.map(([color, count]) => ({ color, count })), transparent_pixels: transparent }
  }

  // ---- render ------------------------------------------------------------
  const VIEW_DIRS = {
    front: [0, 0, -1], back: [0, 0, 1], left: [-1, 0, 0], right: [1, 0, 0],
    top: [0, 1, 0.0001], bottom: [0, -1, 0.0001],
    iso_fr: [1, 0.55, -1], iso_fl: [-1, 0.55, -1], iso_br: [1, 0.55, 1], iso_bl: [-1, 0.55, 1],
  }

  function modelBounds() {
    Canvas.scene.updateMatrixWorld(true)
    const box = new THREE.Box3()
    for (const cube of Cube.all) {
      if (cube.mesh) box.expandByObject(cube.mesh)
    }
    if (box.isEmpty()) return null
    return {
      center: box.getCenter(new THREE.Vector3()).toArray(),
      size: box.getSize(new THREE.Vector3()).toArray(),
    }
  }

  function elementBounds(ref) {
    Canvas.scene.updateMatrixWorld(true)
    const group = findGroup(ref)
    const direct = findCube(ref)
    const cubes = group
      ? Cube.all.filter((cube) => {
        let node = cube.parent
        while (node) { if (node === group) return true; node = node.parent }
        return false
      })
      : (direct ? [direct] : [])
    if (!cubes.length) return null
    const box = new THREE.Box3()
    for (const cube of cubes) if (cube.mesh) box.expandByObject(cube.mesh)
    if (box.isEmpty()) return null
    box.expandByScalar(Math.max(0.25, box.getSize(new THREE.Vector3()).length() * 0.05))
    return {
      center: box.getCenter(new THREE.Vector3()).toArray(),
      size: box.getSize(new THREE.Vector3()).toArray(),
      elements: cubes.length,
    }
  }

  function fitCamera(preview, view, bounds) {
    const [cx, cy, cz] = bounds.center
    const [sx, sy, sz] = bounds.size
    const dir = new THREE.Vector3(...(VIEW_DIRS[view] ?? VIEW_DIRS.front)).normalize()
    const dist = Math.max(sx, sy, sz) * 3
    preview.setProjectionMode(true)
    preview.camera.position.set(cx + dir.x * dist, cy + dir.y * dist, cz + dir.z * dist)
    preview.controls.target.set(cx, cy, cz)
    preview.controls.update()
    const w = preview.width, h = preview.height
    const needW = Math.max(sx, sz) * 1.15
    const needH = (view === 'top' || view === 'bottom' ? Math.max(sx, sz) : sy) * 1.15
    preview.camera.zoom = Math.min(2 * (w / 80) / needW, 2 * (h / 80) / needH)
    preview.camera.updateProjectionMatrix()
  }

  async function pngStats(dataUrl) {
    try {
      const image = await new Promise((resolve, reject) => {
        const img = new Image()
        img.onload = () => resolve(img)
        img.onerror = () => reject(new Error('decode failed'))
        img.src = dataUrl
      })
      const canvas = document.createElement('canvas')
      canvas.width = image.naturalWidth
      canvas.height = image.naturalHeight
      const ctx = canvas.getContext('2d')
      ctx.drawImage(image, 0, 0)
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data
      let opaque = 0
      for (let i = 3; i < data.length; i += 4) if (data[i] > 0) opaque += 1
      // 64x64 粗粒度签名：避免 GPU 抗锯齿/编码的微小抖动造成误报
      const thumb = document.createElement('canvas')
      thumb.width = 64
      thumb.height = 64
      const tctx = thumb.getContext('2d')
      tctx.drawImage(image, 0, 0, 64, 64)
      const thumbData = tctx.getImageData(0, 0, 64, 64).data
      return {
        alpha_ratio: Math.round((opaque / (canvas.width * canvas.height)) * 10000) / 10000,
        thumb: Array.from(thumbData),
      }
    } catch { return null }
  }

  handlers['render.views'] = async (params = {}) => {
    ensureProject()
    const views = Array.isArray(params.views) && params.views.length ? params.views : ['front', 'right', 'iso_fr']
    const size = Array.isArray(params.size) ? params.size : [768, 768]
    const ssaa = params.antialias === 'ssaa' ? 2 : 1
    const renderSize = [size[0] * ssaa, size[1] * ssaa]
    const focusRef = params.focus?.element ?? (views.includes('closeup') ? 'Head' : null)
    const focusBounds = focusRef ? elementBounds(focusRef) : null
    if (focusRef && !focusBounds) throw err('INVALID_REFERENCE', `focus element not found: ${focusRef}`, { code: 'INVALID_REFERENCE' })
    const preview = window.MediaPreview ?? window.Screencam?.NoAAPreview
    if (!preview) throw err('ENGINE_DEGRADED', 'offscreen preview unavailable', { code: 'ENGINE_DEGRADED' })
    const bounds = modelBounds()
    if (!bounds) throw err('INVALID_OPERATION', 'model bounds empty', { code: 'INVALID_OPERATION' })
    const revision = state.revision
    const dir = workspacePath('artifacts', 'renders', `r${String(revision).padStart(4, '0')}`)
    ensureDir(dir)
    const images = []
    const signatureMap = {}
    const prevBg = Canvas.scene.background
    Canvas.scene.background = null
    const cryptoLib = (() => { try { return require('crypto') } catch { return null } })()
    try {
      // 首次离屏渲染存在一次空帧（矩阵/着色器惰性初始化），warm-up 丢弃
      preview.resize(renderSize[0], renderSize[1])
      fitCamera(preview, 'front', focusBounds ?? bounds)
      preview.render()
      for (const view of views) {
        const camView = view === 'closeup' ? 'iso_fr' : view
        if (!VIEW_DIRS[camView]) throw err('INVALID_PARAMS', `unknown view: ${view}`, { code: 'INVALID_PARAMS' })
        preview.resize(renderSize[0], renderSize[1])
        fitCamera(preview, camView, (view === 'closeup' || focusRef) ? (focusBounds ?? bounds) : bounds)
        preview.renderer?.setClearAlpha?.(0)
        Canvas.withoutGizmos(() => preview.render())
        let finalCanvas = preview.canvas
        if (ssaa > 1) {
          const scaled = document.createElement('canvas')
          scaled.width = size[0]; scaled.height = size[1]
          const sctx = scaled.getContext('2d')
          sctx.imageSmoothingEnabled = true
          sctx.imageSmoothingQuality = 'high'
          sctx.drawImage(preview.canvas, 0, 0, renderSize[0], renderSize[1], 0, 0, size[0], size[1])
          finalCanvas = scaled
        }
        const dataUrl = finalCanvas.toDataURL('image/png')
        const file = `${dir}${dir.includes('\\') ? '\\' : '/'}${view}_${size[0]}.png`
        writeBlockbenchFile(file, dataUrl, 'image')
        const base64 = dataUrl.slice(dataUrl.indexOf(',') + 1)
        const sha256 = cryptoLib ? cryptoLib.createHash('sha256').update(Buffer.from(base64, 'base64')).digest('hex') : ''
        const stats = await pngStats(dataUrl)
        const alphaRatio = stats?.alpha_ratio ?? null
        signatureMap[view] = stats?.thumb ?? null
        const previous = state.lastRenderSignatures?.[view]
        let changed = true
        let diffRatio = null
        if (previous?.thumb && stats?.thumb) {
          let diff = 0
          let total = 0
          for (let i = 0; i < stats.thumb.length; i += 4) {
            total += 1
            const dr = Math.abs(stats.thumb[i] - previous.thumb[i])
            const dg = Math.abs(stats.thumb[i + 1] - previous.thumb[i + 1])
            const db = Math.abs(stats.thumb[i + 2] - previous.thumb[i + 2])
            const da = Math.abs(stats.thumb[i + 3] - previous.thumb[i + 3])
            if (Math.max(dr, dg, db, da) > 16) diff += 1
          }
          diffRatio = total ? Math.round((diff / total) * 10000) / 10000 : 0
          changed = diffRatio > 0.005
        }
        const image = {
          view, path: `artifacts/renders/r${String(revision).padStart(4, '0')}/${view}_${size[0]}.png`,
          workspace_path: file, sha256, bytes: Math.round(base64.length * 0.75), width: size[0], height: size[1],
          alpha_ratio: alphaRatio, empty: alphaRatio !== null && alphaRatio < 0.001,
          changed, diff_ratio: diffRatio, antialias: params.antialias ?? 'msaa', focus: focusRef ?? null,
          previous_sha256: state.lastRenderHashes?.[view] ?? null,
        }
        // 模型附件用 512px 缩略图（GPU 渲染仍按 size 保留原图）
        const attachSize = Math.min(1024, Math.max(64, Number(params.attach_size) || 512))
        if (attachSize < Math.max(size[0], size[1])) {
          try {
            const thumb = document.createElement('canvas')
            thumb.width = attachSize
            thumb.height = attachSize
            const tctx = thumb.getContext('2d')
            tctx.imageSmoothingEnabled = true
            tctx.imageSmoothingQuality = 'high'
            tctx.drawImage(finalCanvas, 0, 0, size[0], size[1], 0, 0, attachSize, attachSize)
            const thumbUrl = thumb.toDataURL('image/png')
            const thumbFile = `${dir}${dir.includes('\\') ? '\\' : '/'}${view}_attach${attachSize}.png`
            writeBlockbenchFile(thumbFile, thumbUrl, 'image')
            image.attachment_path = `artifacts/renders/r${String(revision).padStart(4, '0')}/${view}_attach${attachSize}.png`
            image.attachment_workspace_path = thumbFile
            image.attachment_width = attachSize
            image.attachment_height = attachSize
          } catch (error) { console.warn('[bb-agent] thumbnail failed', error?.message) }
        }
        images.push(image)
      }
    } finally {
      Canvas.scene.background = prevBg
    }
    state.counters.renders += 1
    state.lastRender = { revision, views, size, at: new Date().toISOString() }
    const hashes = { ...(state.lastRenderHashes ?? {}) }
    const signatures = { ...(state.lastRenderSignatures ?? {}) }
    for (const image of images) {
      hashes[image.view] = image.sha256
      if (signatureMap[image.view]) signatures[image.view] = { thumb: signatureMap[image.view], alpha_ratio: image.alpha_ratio }
    }
    state.lastRenderHashes = hashes
    state.lastRenderSignatures = signatures
    const warnings = []
    if (images.length && images.every((image) => image.empty === true)) {
      warnings.push({ code: 'EMPTY_RENDER', message: 'all rendered views are fully transparent', fix_hint: 'check camera/bounds or try --safe-mode GPU fallback' })
    }
    const changedAny = images.some((image) => image.changed)
    if (images.length && !changedAny && images.every((image) => image.diff_ratio !== null)) {
      warnings.push({ code: 'NO_VISIBLE_CHANGE', message: 'render is visually identical to the previous render for all views; the last edit may not affect visible geometry/UV/texture', fix_hint: 'check revision, UVs and texture binding with bb_scene include_uv' })
    }
    // 简化闭环 watchdog：记录“编辑后渲染是否可见变化”，连续无变化时建议回滚/换策略
    const pendingBefore = state.loop?.pendingEdits ?? 0
    if (state.loop) {
      state.loop.pendingEdits = 0
      state.loop.lastRenderRevision = revision
      if (!changedAny && pendingBefore > 0) state.loop.unchangedStreak += 1
      else if (changedAny) state.loop.unchangedStreak = 0
    }
    const unchangedStreak = state.loop?.unchangedStreak ?? 0
    const review = {
      verdict: changedAny ? 'visible_change' : (pendingBefore > 0 ? 'no_visible_change' : 'no_change_expected'),
      pending_edits_before_render: pendingBefore,
      unchanged_streak: unchangedStreak,
      suggestion: !changedAny && pendingBefore > 0
        ? (unchangedStreak >= 3 ? '连续多次编辑无可见变化：建议 bb_restore 回滚到最近检查点，换策略后再试' : '上次编辑未改变可见像素：检查 UV/纹理绑定/骨骼层级，不要继续叠加同类修改')
        : null,
    }
    return {
      revision, render_id: `render-${revision}`, images, cache_hit: false, elapsed_ms: 0,
      bounds: bounds, changed_any: changedAny, warnings, review,
    }
  }

  handlers['render.texture'] = (params = {}) => {
    ensureProject()
    const tex = findTexture(params.texture)
    if (!tex) throw err('INVALID_REFERENCE', `texture not found: ${params.texture}`, { code: 'INVALID_REFERENCE' })
    const scale = Math.min(16, Math.max(1, Number(params.scale) || 8))
    const region = params.region ?? [0, 0, tex.width - 1, tex.height - 1]
    const sw = region[2] - region[0] + 1, sh = region[3] - region[1] + 1
    const c = document.createElement('canvas')
    c.width = sw * scale; c.height = sh * scale
    const ctx = c.getContext('2d')
    ctx.imageSmoothingEnabled = false
    ctx.drawImage(tex.canvas, region[0], region[1], sw, sh, 0, 0, c.width, c.height)
    const dir = workspacePath('artifacts', 'texture-previews')
    ensureDir(dir)
    const file = `${dir}${dir.includes('\\') ? '\\' : '/'}${tex.name}_x${scale}.png`
    const dataUrl = c.toDataURL('image/png')
    writeBlockbenchFile(file, dataUrl, 'image')
    return { revision: state.revision, path: `artifacts/texture-previews/${tex.name}_x${scale}.png`, workspace_path: file, width: c.width, height: c.height }
  }

  // ---- validate / save / export -----------------------------------------
  handlers['project.validate'] = () => {
    selectMainProject()
    ensureProject()
    const errors = [], warnings = [], checks = []
    const ysmJson = state.project?.ysmJson
    const packDir = state.project?.pack_dir
    if (!Texture.all.length) errors.push({ code: 'YSM_TEXTURE_MISSING', message: 'no textures', fix_hint: 'bb_texture_create' })
    for (const t of Texture.all) {
      if ((t.width !== 128 || t.height !== 128) && Texture.all.length) warnings.push({ code: 'TEXTURE_SIZE', target: t.name, message: `texture ${t.width}x${t.height}, expected 128x128` })
    }
    // A 级定位组：官方文档明确会影响运行时功能；缺失给 error（仅在本项目确实是 YSM 包时）
    const required = ['Head', 'AllHead', 'LeftHandLocator', 'RightHandLocator']
    for (const name of required) {
      if (!findGroup(name)) {
        if (ysmJson) errors.push({ code: 'YSM_LOCATOR_MISSING', target: name, message: `required locator group missing: ${name}` })
        else warnings.push({ code: 'YSM_LOCATOR_MISSING', target: name, message: `locator group missing: ${name}` })
      }
    }
    // 其他定位组：缺失只提示（不影响加载，只影响对应功能）
    const optionalLocators = ['ViewLocator', 'ElytraLocator', 'LeftShoulderLocator', 'RightShoulderLocator', 'LeftWaistLocator', 'RightWaistLocator', 'BladeLocator', 'SheathLocator', 'PistolLocator', 'RifleLocator', 'BackpackLocator']
    for (const name of optionalLocators) if (!findGroup(name)) warnings.push({ code: 'YSM_LOCATOR_OPTIONAL_MISSING', target: name, message: `optional locator group missing: ${name}` })
    checks.push({ id: 'required_bones', status: errors.some((e) => e.code === 'YSM_LOCATOR_MISSING') ? 'fail' : 'pass' })
    checks.push({ id: 'texture_size', status: warnings.some((w) => w.code === 'TEXTURE_SIZE') ? 'warn' : 'pass' })
    // YSM 资源描述与引用文件检查
    if (ysmJson && packDir) {
      if (ysmJson.spec !== 2) errors.push({ code: 'YSM_SPEC_INVALID', message: `spec must be 2, got ${ysmJson.spec}` })
      if (!ysmJson.metadata?.name) errors.push({ code: 'YSM_METADATA_NAME_MISSING', message: 'metadata.name required' })
      if (!ysmJson.metadata?.license?.type) errors.push({ code: 'YSM_LICENSE_MISSING', message: 'metadata.license.type required' })
      const checkRel = (kind, rel) => {
        if (!rel) return
        const abs = packAbsolute(packDir, rel)
        if (!nodeFs.existsSync(abs)) errors.push({ code: 'YSM_FILE_MISSING', target: rel, message: `${kind} referenced but missing: ${rel}` })
      }
      checkRel('model.main', ysmJson.files?.player?.model?.main)
      checkRel('model.arm', ysmJson.files?.player?.model?.arm)
      for (const entry of textureEntries(ysmJson)) checkRel('texture', entry.uv)
      for (const rel of Object.values(ysmJson.files?.player?.animation ?? {}).filter(Boolean)) checkRel('animation', rel)
      for (const rel of ysmJson.files?.player?.animation_controllers ?? []) checkRel('controller', rel)
      const defaultTexture = ysmJson.properties?.default_texture
      if (defaultTexture && !Texture.all.some((t) => t.name === defaultTexture || t.name === `${defaultTexture}.png`)) {
        warnings.push({ code: 'YSM_DEFAULT_TEXTURE_UNRESOLVED', target: defaultTexture, message: `default_texture "${defaultTexture}" not found among loaded textures` })
      }
      try { if (Settings.get('export_empty_groups') === false) errors.push({ code: 'YSM_EMPTY_GROUPS_DISABLED', message: 'export_empty_groups must be true; locator groups would be dropped' }) } catch { /* ignore */ }
      checks.push({ id: 'ysm_json', status: errors.some((e) => e.code.startsWith('YSM_') && !e.code.includes('LOCATOR')) ? 'fail' : 'pass' })
      checks.push({ id: 'referenced_files', status: errors.some((e) => e.code === 'YSM_FILE_MISSING') ? 'fail' : 'pass' })
    } else {
      checks.push({ id: 'ysm_json', status: 'skip' })
      checks.push({ id: 'referenced_files', status: 'skip' })
    }
    checks.push({ id: 'uv_bounds', status: 'pass' })
    return { ok: errors.length === 0, revision: state.revision, errors, warnings, checks, stats: { bones: Group.all.length, cubes: Cube.all.length } }
  }

  handlers['project.checkpoint'] = (params = {}) => {
    ensureProject()
    const revision = state.revision
    const fileName = `r${String(revision).padStart(4, '0')}.bbmodel`
    const dir = workspacePath('checkpoints')
    ensureDir(dir)
    const content = Codecs.project.compile()
    const file = `${dir}${dir.includes('\\') ? '\\' : '/'}${fileName}`
    writeBlockbenchFile(file, content, 'text')
    const meta = {
      revision,
      label: params.label ?? '',
      note: params.note ?? '',
      created_at: new Date().toISOString(),
      bytes: content.length,
      bones: Group.all.length,
      cubes: Cube.all.length,
      textures: Texture.all.length,
      export_path: Project.export_path || '',
      project_name: Project.name || '',
      pack_dir: state.project?.pack_dir || '',
    }
    writeBlockbenchFile(file.replace(/\.bbmodel$/, '.meta.json'), JSON.stringify(meta, null, 2), 'text')
    return { revision, checkpoint: `checkpoints/${fileName}`, bytes: content.length, label: meta.label }
  }

  handlers['project.revisions'] = (params = {}) => {
    const dir = workspacePath('checkpoints')
    let files = []
    try {
      if (nodeFs?.readdirSync) files = nodeFs.readdirSync(dir).filter((f) => f.endsWith('.bbmodel'))
    } catch { /* no checkpoints yet */ }
    files.sort()
    const limit = Math.min(100, Math.max(1, Number(params.limit) || 20))
    return {
      checkpoints: files.slice(-limit).map((f) => ({
        checkpoint: `checkpoints/${f}`,
        revision: Number((f.match(/^r(\d+)/) ?? [])[1] ?? -1),
      })),
      current_revision: state.revision,
    }
  }

  handlers['project.open_pack'] = async (params = {}) => {
    const packDir = packAbsolute(String(cfg.workspace || ''), params.pack_dir || 'pack')
    if (!nodeFs.existsSync(joinPath(packDir, 'ysm.json'))) {
      throw err('PACK_INVALID', `ysm.json missing: ${packDir}`, { code: 'PACK_INVALID' })
    }
    if (Project && Project !== 0 && params.save_current !== false) {
      try { if (state.project?.pack_dir) saveYsmPack(state.project.pack_dir, state.project.ysmJson) } catch (error) { console.warn('[bb-agent] save before open failed', error?.message) }
    }
    for (const project of ModelProject.all.slice()) {
      try { project.saved = true; project.close(true) } catch { /* ignore */ }
    }
    const ysmJson = normalizeYsm(readJsonSync(joinPath(packDir, 'ysm.json')))
    const loaded = await loadYsmPack(packDir, ysmJson)
    const textureIds = new Map()
    let bones = 0, cubes = 0
    for (const project of ModelProject.all) {
      project.select?.()
      bones += Group.all.length
      cubes += Cube.all.length
      for (const tex of Texture.all) textureIds.set(tex.name, tex)
    }
    loaded.mainProject?.select?.()
    state.project = {
      project_id: `${pathModule.basename(packDir)}-${Math.random().toString(16).slice(2, 10)}`,
      pack_dir: packDir, ysmJson,
      mainProject: loaded.mainProject, armProject: loaded.armProject, textureMap: loaded.textureMap,
    }
    state.state = 'editing'
    state.userEditing = false
    state.counters = { edits: 0, renders: 0, saves: 0, exports: 0, restores: 0 }
    state.dirtyTextures = new Set()
    state.dirtyAnimations = new Set()
    state.dirtyControllers = new Set()
    state.lastRenderHashes = null
    state.lastRenderSignatures = null
    state.loop = { pendingEdits: 0, unchangedStreak: 0, lastRenderRevision: null }
    bump('agent')
    return {
      project_id: state.project.project_id,
      revision: state.revision,
      pack_dir: packDir,
      summary: { bones, cubes, textures: textureIds.size, animations: Animation.all.length, controllers: (window.AnimationController?.all ?? []).length },
      textures: [...textureIds.values()].map((t) => ({ texture: t.name, id: t.uuid, size: [t.width, t.height] })),
      warnings: [],
    }
  }

  handlers['project.close'] = (params = {}) => {
    if (!Project || Project === 0) return { closed: true, revision: state.revision }
    try {
      Project.saved = true
      Project.close(typeof params.force === 'boolean' ? params.force : true)
    } catch (error) {
      throw err('INTERNAL_ERROR', `project close failed: ${error?.message ?? error}`)
    }
    state.project = null
    state.revision = 0
    state.state = 'idle'
    return { closed: true, revision: 0 }
  }

  handlers['project.restore'] = () => {
    throw err('UNSUPPORTED', 'checkpoint restore not wired yet', { code: 'UNSUPPORTED' })
  }
  handlers['project.save'] = () => {
    try { ensureProject() } catch (error) {
      throw err('PROJECT_NOT_OPEN', `no project open (Project=${typeof Project}:${Project ? (Project.name ?? 'obj') : String(Project)}, window.Project=${typeof window.Project}:${window.Project ? (window.Project.name ?? 'obj') : String(window.Project)}, tabs=${ModelProject.all.length})`)
    }
    const packDir = state.project?.pack_dir || workspacePath('pack')
    if (!state.project) state.project = { pack_dir: packDir, ysmJson: normalizeYsm({}) }
    const ysmJson = state.project.ysmJson ?? normalizeYsm({})
    const files = saveYsmPack(packDir, ysmJson)
    state.project.ysmJson = ysmJson
    state.state = 'saved'
    state.counters.saves += 1
    return { saved: true, revision: state.revision, pack_dir: packDir, files }
  }

  handlers['project.export_ysm'] = (params = {}) => {
    ensureProject()
    const packDir = state.project?.pack_dir || workspacePath('pack')
    const ysmJson = state.project?.ysmJson ?? normalizeYsm({})
    // 先显式保存回工作副本，再复制到发布目录
    saveYsmPack(packDir, ysmJson)
    const result = exportYsmPack(packDir, ysmJson, params)
    state.state = 'exported'
    return result
  }

  // ---- animation ---------------------------------------------------------
  const findAnimation = (ref) => Animation.all.find((a) => a.uuid === ref || a.name === ref) ?? null
  const findController = (ref) => (window.AnimationController?.all ?? []).find((c) => c.uuid === ref || c.name === ref) ?? null
  const defaultAnimationPath = () => packAbsolute(
    state.project?.pack_dir || workspacePath('pack'),
    state.project?.ysmJson?.files?.player?.animation?.main ?? 'animations/main.animation.json',
  )

  handlers['animation.list'] = () => ({
    animations: Animation.all.map((a) => ({
      animation: a.name, id: a.uuid, length: a.length, loop: a.loop,
      path: a.path ? pathModule.relative(state.project?.pack_dir || workspacePath('pack'), a.path).replace(/\\/g, '/') : null,
      keyframes: Object.values(a.animators ?? {}).reduce((sum, an) => sum + Object.values(an.channels ?? {}).reduce((s, ch) => s + (Array.isArray(an[ch]) ? an[ch].length : 0), 0), 0),
    })),
    controllers: (window.AnimationController?.all ?? []).map((c) => ({
      controller: c.name, id: c.uuid,
      path: c.path ? pathModule.relative(state.project?.pack_dir || workspacePath('pack'), c.path).replace(/\\/g, '/') : null,
      initial_state: c.states?.find((s) => s.uuid === c.initial_state)?.name ?? null,
      states: (c.states ?? []).map((s) => ({ name: s.name, animations: (s.animations ?? []).map((a) => a.key) })),
    })),
  })

  function createAnimation(params = {}) {
    const name = String(params.name || '').trim()
    if (!name) throw err('INVALID_PARAMS', 'animation name required', { code: 'INVALID_PARAMS' })
    if (findAnimation(name)) throw err('INVALID_OPERATION', `animation already exists: ${name}`, { code: 'INVALID_OPERATION' })
    const anim = new Animation({
      name,
      loop: ['once', 'loop', 'hold'].includes(params.loop) ? params.loop : 'loop',
      length: Math.max(0.1, Number(params.length) || 1),
    }).add(false)
    anim.select?.()
    Animation.selected = anim
    if (params.file) anim.path = packAbsolute(state.project?.pack_dir || workspacePath('pack'), params.file)
    else anim.path = defaultAnimationPath()
    if (anim.path) state.dirtyAnimations.add(anim.path)
    return anim
  }

  handlers['animation.create'] = (params = {}) => {
    ensureProject()
    Undo.initEdit({ animations: Animation.all.slice() })
    let success = false
    try {
      const anim = createAnimation(params)
      success = true
      state.counters.edits += 1
      const revision = bump('agent', [{ kind: 'animation', id: anim.uuid, op: 'create' }])
      return { animation: anim.name, id: anim.uuid, length: anim.length, loop: anim.loop, revision }
    } finally {
      if (success) { try { Undo.finishEdit('Agent create animation') } catch { /* ignore */ } }
    }
  }

  handlers['animation.apply_patch'] = (params = {}) => {
    ensureProject()
    const ops = Array.isArray(params.ops) ? params.ops : []
    if (!ops.length) throw err('INVALID_PARAMS', 'ops is empty', { code: 'INVALID_PARAMS' })
    const changed = []
    const dirtyAnimPaths = new Set()
    Undo.initEdit({ animations: Animation.all.slice() })
    let success = false
    try {
      for (const op of ops) {
        switch (op.op) {
          case 'create_animation': {
            const anim = createAnimation(op)
            changed.push({ animation: anim.name, op: 'create' })
            if (anim.path) dirtyAnimPaths.add(anim.path)
            break
          }
          case 'update_animation': {
            const anim = findAnimation(op.animation ?? op.id)
            if (!anim) throw err('INVALID_REFERENCE', `animation not found: ${op.animation ?? op.id}`, { code: 'INVALID_REFERENCE' })
            if (op.name) anim.name = op.name
            if (typeof op.loop === 'string' && ['once', 'loop', 'hold'].includes(op.loop)) anim.loop = op.loop
            else if (typeof op.loop === 'boolean') anim.loop = op.loop ? 'loop' : 'once'
            if (typeof op.length === 'number') { anim.length = op.length; anim.setLength(op.length) }
            changed.push({ animation: anim.name, op: 'update' })
            if (anim.path) dirtyAnimPaths.add(anim.path)
            break
          }
          case 'set_keyframes': {
            const anim = findAnimation(op.animation)
            if (!anim) throw err('INVALID_REFERENCE', `animation not found: ${op.animation}`, { code: 'INVALID_REFERENCE' })
            const group = findGroup(op.bone)
            if (!group) throw err('INVALID_REFERENCE', `bone not found: ${op.bone}`, { code: 'INVALID_REFERENCE' })
            const channel = op.channel || 'rotation'
            if (!['rotation', 'position', 'scale'].includes(channel)) throw err('INVALID_PARAMS', `invalid channel: ${channel}`)
            Animation.selected = anim
            anim.select?.()
            const animator = anim.getBoneAnimator(group)
            if (!animator) throw err('INVALID_OPERATION', `cannot animate bone: ${op.bone}`, { code: 'INVALID_OPERATION' })
            animator[channel] = animator[channel].filter((kf) => !(op.keys ?? []).some((k) => Math.abs(kf.time - Number(k.time)) < 1e-4))
            for (const key of op.keys ?? []) {
              const time = Number(key.time)
              if (!Number.isFinite(time) || time < 0) throw err('INVALID_PARAMS', `invalid key time: ${key.time}`)
              const value = Array.isArray(key.value) ? key.value : [0, 0, 0]
              const data = { channel, time, x: value[0], y: value[1], z: value[2] }
              if (key.easing) data.interpolation = key.easing
              animator.addKeyframe(data, null)
            }
            anim.setLength(Math.max(anim.length, ...(op.keys ?? []).map((k) => Number(k.time) || 0)))
            changed.push({ animation: anim.name, bone: group.name, channel, op: 'set_keyframes', count: (op.keys ?? []).length })
            if (anim.path) dirtyAnimPaths.add(anim.path)
            break
          }
          case 'delete_keyframes': {
            const anim = findAnimation(op.animation)
            if (!anim) throw err('INVALID_REFERENCE', `animation not found: ${op.animation}`, { code: 'INVALID_REFERENCE' })
            const group = findGroup(op.bone)
            const animator = group ? anim.getBoneAnimator(group) : null
            if (!animator) throw err('INVALID_OPERATION', `cannot animate bone: ${op.bone}`, { code: 'INVALID_OPERATION' })
            const channel = op.channel || 'rotation'
            const before = animator[channel].length
            if (Array.isArray(op.times) && op.times.length) {
              animator[channel] = animator[channel].filter((kf) => !op.times.some((t) => Math.abs(kf.time - Number(t)) < 1e-4))
            } else {
              animator[channel] = []
            }
            changed.push({ animation: anim.name, bone: group.name, channel, op: 'delete_keyframes', removed: before - animator[channel].length })
            if (anim.path) dirtyAnimPaths.add(anim.path)
            break
          }
          case 'delete_animation': {
            const anim = findAnimation(op.animation)
            if (!anim) throw err('INVALID_REFERENCE', `animation not found: ${op.animation}`, { code: 'INVALID_REFERENCE' })
            if (anim.path) dirtyAnimPaths.add(anim.path)
            anim.delete?.()
            changed.push({ animation: op.animation, op: 'delete' })
            break
          }
          case 'bind_controller': {
            const anim = findAnimation(op.animation)
            if (!anim) throw err('INVALID_REFERENCE', `animation not found: ${op.animation}`, { code: 'INVALID_REFERENCE' })
            const controller = findController(op.controller)
            if (!controller) throw err('INVALID_REFERENCE', `controller not found: ${op.controller}`, { code: 'INVALID_REFERENCE' })
            const controllerState = (controller.states ?? []).find((s) => s.name === op.state || s.uuid === op.state)
            if (!controllerState) throw err('INVALID_REFERENCE', `controller state not found: ${op.state}`, { code: 'INVALID_REFERENCE' })
            const key = op.key || anim.getShortName?.() || anim.name.replace(/^animation\./, '')
            controllerState.animations = (controllerState.animations ?? []).filter((a) => a.key !== key)
            controllerState.animations.push({ uuid: (typeof guid === 'function' ? guid() : `${Date.now()}-${Math.random()}`), key, animation: anim.uuid, blend_value: op.blend_value ?? '' })
            if (controller.path) state.dirtyControllers.add(controller.path)
            changed.push({ animation: anim.name, controller: controller.name, state: controllerState.name, op: 'bind_controller' })
            break
          }
          default:
            throw err('INVALID_OPERATION', `unsupported animation op: ${op.op}`, { code: 'INVALID_OPERATION' })
        }
      }
      Canvas.updateAll?.()
      state.counters.edits += 1
      for (const p of dirtyAnimPaths) state.dirtyAnimations.add(p)
      const revision = bump('agent', changed.map((c) => ({ kind: 'animation', id: c.animation, op: c.op })))
      success = true
      return { ok: true, revision, changed, warnings: [] }
    } finally {
      if (success) { try { Undo.finishEdit('Agent animation patch') } catch { /* ignore */ } }
    }
  }

  handlers['animation.delete'] = (params = {}) => handlers['animation.apply_patch']({ ops: [{ op: 'delete_animation', animation: params.animation }] })

  // ---- texture import/export --------------------------------------------
  handlers['texture.export_png'] = (params = {}) => {
    ensureProject()
    const tex = findTexture(params.texture)
    if (!tex) throw err('INVALID_REFERENCE', `texture not found: ${params.texture}`, { code: 'INVALID_REFERENCE' })
    const safeName = String(tex.name || 'texture').replace(/[^A-Za-z0-9_-]+/g, '_')
    const rel = params.out_dir
      ? `${String(params.out_dir).replace(/[\\/]+/g, '/')}/${safeName}.png`
      : `artifacts/textures/${safeName}.png`
    const abs = packAbsolute(String(cfg.workspace || ''), rel)
    const dataUrl = tex.canvas.toDataURL('image/png')
    writeBlockbenchFile(abs, dataUrl, 'image')
    return {
      texture: tex.name, path: rel, workspace_path: abs,
      width: tex.width, height: tex.height, bytes: Math.round(dataUrl.length * 0.75),
    }
  }

  handlers['texture.import_png'] = async (params = {}) => {
    ensureProject()
    const tex = findTexture(params.texture)
    if (!tex) throw err('INVALID_REFERENCE', `texture not found: ${params.texture}`, { code: 'INVALID_REFERENCE' })
    let dataUrl = null
    if (typeof params.base64 === 'string' && params.base64) dataUrl = `data:image/png;base64,${params.base64.replace(/^data:image\/png;base64,/, '')}`
    else if (typeof params.path === 'string' && params.path) {
      const abs = packAbsolute(String(cfg.workspace || ''), params.path)
      if (!nodeFs?.existsSync?.(abs)) throw err('INVALID_REFERENCE', `image not found: ${params.path}`, { code: 'INVALID_REFERENCE' })
      dataUrl = `data:image/png;base64,${nodeFs.readFileSync(abs).toString('base64')}`
    }
    if (!dataUrl) throw err('INVALID_PARAMS', 'path or base64 required', { code: 'INVALID_PARAMS' })
    const image = await new Promise((resolve, reject) => {
      const img = new Image()
      img.onload = () => resolve(img)
      img.onerror = () => reject(err('INVALID_PARAMS', 'image decode failed', { code: 'INVALID_PARAMS' }))
      img.src = dataUrl
    })
    const at = Array.isArray(params.at) ? params.at : [0, 0]
    const region = Array.isArray(params.region) ? params.region : null
    const aspects = { textures: [tex], bitmap: true }
    Undo.initEdit(aspects)
    let success = false
    try {
      const active = tex.getActiveCanvas()
      const ctx = active.ctx ?? active.getContext('2d')
      const off = active.offset ?? [0, 0]
      if (region) {
        ctx.drawImage(image, region[0], region[1], region[2] - region[0] + 1, region[3] - region[1] + 1,
          at[0] + off[0], at[1] + off[1], region[2] - region[0] + 1, region[3] - region[1] + 1)
      } else {
        ctx.drawImage(image, at[0] + off[0], at[1] + off[1])
      }
      tex.updateChangesAfterEdit()
      state.counters.edits += 1
      state.dirtyTextures.add(tex.uuid)
      const revision = bump('agent', [{ kind: 'texture', id: tex.uuid, op: 'import_png' }])
      success = true
      return { ok: true, revision, texture: tex.name, width: image.naturalWidth, height: image.naturalHeight, at }
    } finally {
      if (success) { try { Undo.finishEdit('Agent import png') } catch { /* ignore */ } }
    }
  }

  // ---- texture layers / PBR ----------------------------------------------
  const ensureTexture = (ref) => {
    const tex = findTexture(ref)
    if (!tex) throw err('INVALID_REFERENCE', `texture not found: ${ref}`, { code: 'INVALID_REFERENCE' })
    return tex
  }
  handlers['texture.layer_list'] = (params = {}) => {
    ensureProject()
    const tex = ensureTexture(params.texture)
    return {
      texture: tex.name,
      layers_enabled: !!tex.layers_enabled,
      selected: tex.selected_layer?.name ?? null,
      layers: (tex.layers ?? []).map((layer, index) => ({
        index, layer: layer.name, id: layer.uuid, type: layer.type,
        visible: layer.visible !== false, opacity: layer.opacity,
        blend_mode: layer.blend_mode, size: layer.size ?? [layer.width, layer.height],
      })),
    }
  }
  handlers['texture.layer_create'] = (params = {}) => {
    ensureProject()
    const tex = ensureTexture(params.texture)
    Undo.initEdit({ textures: [tex], bitmap: true })
    let success = false
    try {
      if (!tex.layers_enabled) tex.activateLayers?.(false)
      const LayerClass = window.TextureLayer ?? (typeof TextureLayer !== 'undefined' ? TextureLayer : null)
      if (!LayerClass) throw err('UNSUPPORTED', 'TextureLayer unavailable', { code: 'UNSUPPORTED' })
      const layer = new LayerClass({ name: String(params.name || `layer_${(tex.layers?.length ?? 0) + 1}`) }, tex)
      layer.setSize(tex.width, tex.height)
      const fill = colorOk(params.fill) ? params.fill : null
      if (fill) { layer.ctx.fillStyle = fill; layer.ctx.fillRect(0, 0, tex.width, tex.height) }
      tex.layers.push(layer)
      layer.select?.()
      tex.updateLayerChanges?.(true)
      state.counters.edits += 1
      state.dirtyTextures.add(tex.uuid)
      const revision = bump('agent', [{ kind: 'texture', id: tex.uuid, op: 'layer_create' }])
      success = true
      return { ok: true, revision, texture: tex.name, layer: layer.name, id: layer.uuid, layers: tex.layers.length }
    } finally {
      if (success) { try { Undo.finishEdit('Agent create texture layer') } catch { /* ignore */ } }
    }
  }
  handlers['texture.layer_select'] = (params = {}) => {
    ensureProject()
    const tex = ensureTexture(params.texture)
    if (!tex.layers_enabled) throw err('INVALID_OPERATION', 'texture layers not enabled', { code: 'INVALID_OPERATION' })
    const layer = (tex.layers ?? []).find((l) => l.uuid === params.layer || l.name === params.layer)
    if (!layer) throw err('INVALID_REFERENCE', `layer not found: ${params.layer}`, { code: 'INVALID_REFERENCE' })
    layer.select?.()
    tex.selected_layer = layer
    return { texture: tex.name, layer: layer.name, revision: state.revision }
  }
  handlers['texture.layer_delete'] = (params = {}) => {
    ensureProject()
    const tex = ensureTexture(params.texture)
    const index = (tex.layers ?? []).findIndex((l) => l.uuid === params.layer || l.name === params.layer)
    if (index < 0) throw err('INVALID_REFERENCE', `layer not found: ${params.layer}`, { code: 'INVALID_REFERENCE' })
    Undo.initEdit({ textures: [tex], bitmap: true })
    let success = false
    try {
      const [removed] = tex.layers.splice(index, 1)
      tex.selected_layer = tex.layers[index] ?? tex.layers[index - 1] ?? null
      tex.updateLayerChanges?.(true)
      state.counters.edits += 1
      state.dirtyTextures.add(tex.uuid)
      const revision = bump('agent', [{ kind: 'texture', id: tex.uuid, op: 'layer_delete' }])
      success = true
      return { ok: true, revision, texture: tex.name, removed: removed.name, layers: tex.layers.length }
    } finally {
      if (success) { try { Undo.finishEdit('Agent delete texture layer') } catch { /* ignore */ } }
    }
  }
  handlers['texture.layer_flatten'] = (params = {}) => {
    ensureProject()
    const tex = ensureTexture(params.texture)
    if (!tex.layers_enabled) return { ok: true, texture: tex.name, layers_enabled: false, revision: state.revision }
    Undo.initEdit({ textures: [tex], bitmap: true })
    let success = false
    try {
      tex.updateLayerChanges?.(true)
      tex.layers_enabled = false
      tex.selected_layer = null
      tex.layers = []
      tex.updateChangesAfterEdit?.()
      state.counters.edits += 1
      state.dirtyTextures.add(tex.uuid)
      const revision = bump('agent', [{ kind: 'texture', id: tex.uuid, op: 'layer_flatten' }])
      success = true
      return { ok: true, revision, texture: tex.name, layers_enabled: false }
    } finally {
      if (success) { try { Undo.finishEdit('Agent flatten texture layers') } catch { /* ignore */ } }
    }
  }
  handlers['texture.pbr_list'] = (params = {}) => {
    ensureProject()
    return {
      pbr_textures: Texture.all
        .filter((t) => (t.pbr_channel && t.pbr_channel !== 'color') || /_[ns]$/i.test(t.name))
        .map((t) => ({ texture: t.name, id: t.uuid, channel: (t.pbr_channel && t.pbr_channel !== 'color') ? t.pbr_channel : (/_n$/i.test(t.name) ? 'normal' : 'specular'), path: t.path ?? null, size: [t.width, t.height] })),
    }
  }
  handlers['texture.pbr_create'] = async (params = {}) => {
    ensureProject()
    const base = params.texture ? ensureTexture(params.texture) : (Texture.selected ?? null)
    if (!base) throw err('INVALID_REFERENCE', 'base texture required', { code: 'INVALID_REFERENCE' })
    const channel = params.channel === 'specular' ? 'specular' : 'normal'
    const suffix = channel === 'normal' ? '_n' : '_s'
    const baseName = String(base.name || 'texture').replace(/\.png$/i, '')
    const name = `${baseName}${suffix}`
    if (findTexture(name)) throw err('INVALID_OPERATION', `PBR texture already exists: ${name}`, { code: 'INVALID_OPERATION' })
    const fill = colorOk(params.fill) ? params.fill : (channel === 'normal' ? '#8080ff' : '#ffffff')
    const canvas = document.createElement('canvas')
    canvas.width = base.width; canvas.height = base.height
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = fill; ctx.fillRect(0, 0, canvas.width, canvas.height)
    const tex = new Texture({ name })
    tex.fromDataURL(canvas.toDataURL('image/png'))
    tex.add(false)
    {
      const started = Date.now()
      while ((!tex.width || !tex.height) && Date.now() - started < 2000) await new Promise((r) => setTimeout(r, 20))
      if (!tex.width || !tex.height) {
        tex.canvas.width = canvas.width; tex.canvas.height = canvas.height
        tex.ctx.drawImage(canvas, 0, 0); tex.width = canvas.width; tex.height = canvas.height
        tex.source = tex.canvas.toDataURL('image/png')
      }
    }
    tex.name = name
    tex.pbr_channel = channel
    const packDir = state.project?.pack_dir || workspacePath('pack')
    tex.path = packAbsolute(packDir, `textures/${name}.png`)
    tex.updateChangesAfterEdit?.()
    state.counters.edits += 1
    state.dirtyTextures.add(tex.uuid)
    const revision = bump('agent', [{ kind: 'texture', id: tex.uuid, op: 'pbr_create' }])
    return { ok: true, revision, texture: tex.name, channel, size: [tex.width, tex.height], path: tex.path, note: 'Iris/YSM PBR 约定：基础贴图同目录使用 _n/_s 后缀；需支持 PBR 的光影环境才会显示' }
  }

  // ---- checkpoint restore ------------------------------------------------
  handlers['project.restore'] = async (params = {}) => {
    ensureProject()
    if (params.confirm !== true) throw err('INVALID_OPERATION', 'restore requires confirm:true (destructive)', { code: 'INVALID_OPERATION' })
    const packDir = state.project?.pack_dir || workspacePath('pack')
    const revision = Number(params.revision)
    if (!Number.isFinite(revision) || revision < 0) throw err('INVALID_PARAMS', 'revision required', { code: 'INVALID_PARAMS' })
    const base = `r${String(revision).padStart(4, '0')}`
    const checkpointAbs = joinPath(workspacePath('checkpoints'), `${base}.bbmodel`)
    const metaAbs = joinPath(workspacePath('checkpoints'), `${base}.meta.json`)
    if (!nodeFs?.existsSync?.(checkpointAbs)) throw err('INVALID_REFERENCE', `checkpoint not found: ${base}`, { code: 'INVALID_REFERENCE' })
    const meta = nodeFs.existsSync(metaAbs) ? readJsonSync(metaAbs) : {}
    const content = readTextSync(checkpointAbs)
    const model = JSON.parse(content)
    for (const project of ModelProject.all.slice()) {
      try { project.saved = true; project.close(true) } catch { /* ignore */ }
    }
    Codecs.project.load(model, { path: checkpointAbs, content, name: base, no_file: true }, {})
    const project = Project
    if (meta.export_path) project.export_path = meta.export_path
    else if (state.project?.ysmJson) project.export_path = packAbsolute(packDir, state.project.ysmJson.files?.player?.model?.main ?? 'models/main.json')
    const ysmJson = state.project?.ysmJson
    let armLoaded = false
    let armError = null
    if (ysmJson) {
      try {
        const arm = await loadArmFromDisk(packDir, ysmJson)
        if (arm) {
          if (state.project) state.project.armProject = arm.armProject
          armLoaded = true
        }
      } catch (error) {
        armError = error?.message ?? String(error)
        console.warn('[bb-agent] restore arm failed', armError)
      }
    }
    project.select?.()
    // 关闭旧 tab 可能排队 selectNoProject；等一个 tick 后再选中恢复的主项目
    await new Promise((resolve) => setTimeout(resolve, 50))
    project.select?.()
    if (state.project) state.project.mainProject = project
    state.state = 'editing'
    state.userEditing = false
    state.counters.restores += 1
    // checkpoint 恢复后，磁盘上的动画/控制器/贴图可能落后，全量标脏
    for (const anim of Animation.all) if (anim.path) state.dirtyAnimations.add(anim.path)
    for (const controller of (window.AnimationController?.all ?? [])) if (controller.path) state.dirtyControllers.add(controller.path)
    for (const tex of Texture.all) state.dirtyTextures.add(tex.uuid)
    const previousRevision = state.revision
    const nextRevision = bump('restore', [])
    return {
      restored_from: previousRevision, revision: nextRevision,
      summary: { bones: Group.all.length, cubes: Cube.all.length, textures: Texture.all.length },
      arm_loaded: armLoaded, arm_error: armError,
      debug: { project_open: !!Project, active: Project?.name ?? null, main: project?.name ?? null, main_open: ModelProject.all.includes(project) },
      warning: '当前未保存改动已丢弃；arm 已从磁盘重载（非 checkpoint 状态）',
    }
  }

  handlers['gui.show'] = async () => {
    try {
      if (window.__BB_AGENT_API__?.showWindow) await window.__BB_AGENT_API__.showWindow()
      else { const win = currentWindow(); win?.show(); win?.focus() }
    } catch { /* ignore */ }
    state.guiVisible = true
    state.guiBaselineRevision = state.revision
    state.userEditing = false
    notify('event.gui_state', { visible: true, focused: true, revision: state.revision, user_editing: false })
    return { gui_visible: true, revision: state.revision, frozen: true }
  }
  handlers['gui.hide'] = async () => {
    try {
      if (window.__BB_AGENT_API__?.hideWindow) await window.__BB_AGENT_API__.hideWindow()
      else currentWindow()?.hide()
    } catch { /* ignore */ }
    state.guiVisible = false
    const userEdits = []
    if (state.userEditing && state.guiBaselineRevision !== state.revision) {
      userEdits.push({ type: 'revision_changed', from: state.guiBaselineRevision, to: state.revision })
    }
    state.userEditing = false
    state.state = 'editing'
    notify('event.gui_state', { visible: false, focused: false, revision: state.revision, user_editing: false })
    return { gui_visible: false, revision: state.revision, user_edits: userEdits }
  }
  handlers['gui.state'] = () => ({ gui_visible: state.guiVisible, focused: true, revision: state.revision, user_editing: state.userEditing })

  // 用户 GUI 编辑检测：Blockbench Undo.finishEdit 事件；agent 事务期间忽略
  function registerUserEditListener() {
    try {
      Blockbench.on?.('finished_edit', () => {
        if (state.agentEditing) return
        state.userEditing = true
        state.revision += 1
        for (const anim of Animation.all) if (anim.path) state.dirtyAnimations.add(anim.path)
        for (const controller of (window.AnimationController?.all ?? [])) if (controller.path) state.dirtyControllers.add(controller.path)
        for (const tex of Texture.all) state.dirtyTextures.add(tex.uuid)
        notify('event.project_changed', { revision: state.revision, source: 'user', changed: [] })
        notify('event.gui_state', { visible: state.guiVisible, focused: true, revision: state.revision, user_editing: true })
      })
    } catch (error) { console.warn('[bb-agent] user edit listener failed', error?.message) }
  }

  // ------------------------------------------------------------------ 注册
  Plugin.register(BRIDGE_ID, {
    title: 'BB Agent Bridge',
    author: 'dsh-blockbench-agent',
    description: 'Headless semantic bridge for dsh agents',
    icon: 'smart_toy',
    variant: 'desktop',
    min_version: '5.2.0',
    onload() {
      console.log('[bb-agent] bridge plugin loaded')
      window.__BB_AGENT_BRIDGE__ = { state, handlers, call, connect }
      registerUserEditListener()
      connect()
    },
    onunload() {
      disposed = true
      if (heartbeatTimer) clearInterval(heartbeatTimer)
      try { eventSource?.close?.() } catch { /* ignore */ }
      try { socket?.close() } catch { /* ignore */ }
    },
  })
})()


