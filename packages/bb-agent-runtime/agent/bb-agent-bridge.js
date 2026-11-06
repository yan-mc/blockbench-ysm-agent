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
    suppressUserEdit: false,
    startedAt: Date.now(),
    lastError: null,
    counters: { edits: 0, renders: 0, saves: 0, exports: 0, restores: 0 },
    limits: { edits: 60, renders: 40, restores: 2 },
    // 视口反馈方法（preview/sheet/turntable/...）的高频、轻量、只读，
    // 不该跟 render.views 共用那 40 次预算，否则自动附图几次就耗尽。
    // 单独放宽，但仍保留上限以防无限制刷渲染。
    lookLimits: { renders: 400 },
    lastRender: null,
    loop: { pendingEdits: 0, unchangedStreak: 0, lastRenderRevision: null },
    dirtyTextures: new Set(),
    dirtyAnimations: new Set(),
    dirtyAnimationNames: new Set(),
    deletedAnimations: new Map(),
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

  /**
   * 收敛 pack_dir，防止「workspace 被拼了两次」。
   *
   * 实测事故：调用方传了仓库根相对的 `models/<项目>/sakiko`，它被当成 workspace 相对路径
   * 再拼一次 workspace，得到 `.../models/<项目>/models/<项目>/sakiko`。
   * bb_save_project 于是每次都往这个陈旧双拼路径写一份旧内容 —— 不报错，只污染工作区。
   *
   * 判定依据：路径里 workspace 尾段再次出现，且其后紧跟 `models` 段（重复拼接的signature）。
   */
  function normalizePackDir(input) {
    const ws = String(cfg.workspace || '')
    const raw = String(input ?? 'pack')
    const abs = (pathModule && pathModule.isAbsolute(raw)) ? raw : packAbsolute(ws, raw)
    if (!ws || !pathModule) return abs
    const sep = abs.includes('\\') ? '\\' : '/'
    const parts = abs.split(/[\\/]+/).filter(Boolean)
    const wsParts = ws.split(/[\\/]+/).filter(Boolean)
    const tail = wsParts[wsParts.length - 1]
    const hits = []
    for (let i = 0; i < parts.length; i++) if (parts[i] === tail) hits.push(i)
    // 只有出现 ≥2 次、且第二次之后紧跟 models 才是双拼
    const dup = hits.length >= 2 && parts[hits[1] + 1] === 'models'
    if (!dup) return abs
    const fixed = [...wsParts, ...parts.slice(hits[hits.length - 1] + 1)].join(sep)
    console.warn(`[bb-agent] pack_dir 双拼已收敛: ${abs} -> ${fixed}`)
    return fixed
  }

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

  async function loadArmFromSnapshot(snapshotAbs, packDir, ysmJson) {
    if (!nodeFs?.existsSync?.(snapshotAbs)) return null
    loadModelFile({ path: snapshotAbs, content: readTextSync(snapshotAbs), name: pathModule.basename(snapshotAbs) })
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

  async function loadArmFromContent(packDir, ysmJson, content, name) {
    const rel = ysmJson?.files?.player?.model?.arm
    const abs = rel ? packAbsolute(packDir, rel) : joinPath(packDir, 'models', 'arm.json')
    loadModelFile({ path: abs, content, name: name || pathModule.basename(abs) })
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

  async function drawTextureDataUrl(tex, dataUrl) {
    const image = new Image()
    await new Promise((resolve, reject) => {
      image.onload = () => resolve()
      image.onerror = () => reject(new Error('image load failed'))
      image.src = dataUrl
    })
    const canvas = tex.canvas ?? document.createElement('canvas')
    canvas.width = image.width
    canvas.height = image.height
    tex.canvas = canvas
    tex.ctx = canvas.getContext('2d')
    tex.ctx.clearRect(0, 0, canvas.width, canvas.height)
    tex.ctx.drawImage(image, 0, 0)
    tex.width = image.width
    tex.height = image.height
    tex.img = image
    tex.source = dataUrl
    tex.updateChangesAfterEdit?.()
  }

  // checkpoint 的贴图快照：只覆盖 .bbmodel 里已经存在的 Texture（按 uuid/ordinal 对齐），
  // 不新建 Texture、不改写 Project.textures，避免 restore 破坏项目状态。
  async function applyCheckpointTextures(base, snapshots = [], targetProject = null) {
    if (!snapshots.length) return { restored: 0, created: 0, missing: 0 }
    const dir = joinPath(workspacePath('checkpoints'), `${base}.textures`)
    let restored = 0, missing = 0
    for (const snap of snapshots) {
      if (targetProject && snap.project && snap.project !== targetProject.name) continue
      const abs = joinPath(dir, snap.file)
      if (!nodeFs?.existsSync?.(abs)) { missing += 1; continue }
      const wanted = String(snap.name || '').replace(/\.png$/i, '').toLowerCase()
      let target = snap.id ? Texture.all.find((t) => t.uuid === snap.id) : null
      if (!target) {
        const candidates = Texture.all.filter((t) => String(t.name || '').replace(/\.png$/i, '').toLowerCase() === wanted)
        target = candidates[Number(snap.ordinal) || 0] ?? candidates[0] ?? null
      }
      if (!target) { missing += 1; continue }
      try {
        const dataUrl = `data:image/png;base64,${nodeFs.readFileSync(abs).toString('base64')}`
        await drawTextureDataUrl(target, dataUrl)
        state.dirtyTextures.add(target.uuid)
        restored += 1
      } catch (error) { console.warn('[bb-agent] restore texture failed', snap.name, error?.message) }
    }
    return { restored, created: 0, missing }
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
  function stableJson(value) {
    if (Array.isArray(value)) return `[${value.map(stableJson).join(',')}]`
    if (value && typeof value === 'object') return `{${Object.keys(value).sort().map((k) => `${JSON.stringify(k)}:${stableJson(value[k])}`).join(',')}}`
    return JSON.stringify(value)
  }

  // 动画文件合并：保留原文件中未被修改的动画条目与顺序，只替换发生语义变化的动画、追加新增、移除删除。
  // 这解决 Blockbench 整文件导出导致的动画重排/膨胀，是“YSM 保存规范化 v1”的核心。
  function mergeAnimationJson(original, exported, dirtyNames = new Set(), deletedNames = new Set()) {
    if (!original || typeof original !== 'object' || !original.animations) return exported
    const origAnims = original.animations ?? {}
    const newAnims = exported?.animations ?? {}
    const mergedAnims = {}
    for (const [name, origAnim] of Object.entries(origAnims)) {
      if (deletedNames.has(name)) continue
      const next = newAnims[name]
      // 未编辑的动画一律保留原始对象/顺序，避免 codec 的时间量化/字段重排污染整个文件
      mergedAnims[name] = dirtyNames.has(name) && next !== undefined ? next : origAnim
    }
    for (const [name, next] of Object.entries(newAnims)) {
      if (name in mergedAnims) continue
      if (dirtyNames.size === 0 || dirtyNames.has(name)) mergedAnims[name] = next
    }
    return { ...original, animations: mergedAnims }
  }

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
        const original = nodeFs?.existsSync?.(animPath) ? readJsonSync(animPath) : null
        AnimationCodec.codecs.bedrock.exportFile(animPath)
        const exported = readJsonSync(animPath)
        const deleted = state.deletedAnimations.get(animPath) ?? new Set()
        const merged = mergeAnimationJson(original, exported, state.dirtyAnimationNames, deleted)
        writeBlockbenchFile(animPath, JSON.stringify(merged, null, '\t'), 'text')
        state.dirtyAnimations.delete(animPath)
        state.deletedAnimations.delete(animPath)
        files.push({ path: animPath })
      } catch (error) {
        console.warn('[bb-agent] animation save failed', animPath, error?.message)
        files.push({ path: animPath, error: error?.message ?? String(error) })
      }
    }
    state.dirtyAnimationNames.clear()
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
              client: { name: 'bb-agent-bridge', version: '0.4.0' },
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
    socket.onclose = (ev) => {
      console.warn('[bb-agent] socket closed', ev?.code, ev?.reason, 'bufferedAmount=', socket?.bufferedAmount)
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
          client: { name: 'bb-agent-bridge', version: '0.4.0', transport: 'http-sse' },
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
  // 渲染串行化：离屏 preview 只有一个 canvas/renderer，并发调用（尤其 async 的
  // render.sheet / render.animation_frame）会互相踩状态导致 renderer 崩溃断连。
  // 这里用一条 Promise 链把**所有渲染类方法**串起来执行（docs/07 R6）。
  const RENDER_METHODS = new Set([
    'render.views', 'render.preview', 'render.sheet', 'render.turntable',
    'render.animation_frame', 'render.texture', 'render.texture_sheet',
  ])
  let renderChain = Promise.resolve()
  function serializeRender(fn) {
    const run = renderChain.then(fn, fn)
    // 无论成功失败都让链继续，避免一次失败卡死后续调用
    renderChain = run.then(() => undefined, () => undefined)
    return run
  }

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
      const result = RENDER_METHODS.has(method)
        ? await serializeRender(() => {
          // 所有渲染方法统一计入预算（以前只有 render.views 会计数，
          // 于是 bb_look / bb_orbit / 自动附图可以无限刷渲染而不受任何约束）。
          // render.views 沿用 renders 预算；视口反馈类走更宽的 lookLimits。
          if (method !== 'render.views') {
            if (state.counters.renders >= state.limits.renders + (state.lookLimits?.renders ?? 400)) {
              throw err('RESOURCE_LIMIT', `render budget exhausted (${state.limits.renders + (state.lookLimits?.renders ?? 400)})`, {
                code: 'RESOURCE_LIMIT', recoverable: true,
                hint: 'restart the runtime, or reduce autolook frequency',
              })
            }
            state.counters.renders += 1
          }
          return handler(params, msg._meta ?? {})
        })
        : await handler(params, msg._meta ?? {})
      sendRaw({ jsonrpc: '2.0', id, result })
    } catch (error) {
      state.lastError = { code: error?.bbCode ?? 'INTERNAL_ERROR', message: error?.message ?? String(error) }
      sendRaw({
        jsonrpc: '2.0', id,
        error: {
          code: error?.rpc?.code ?? -32603,
          message: error?.message ?? 'internal error',
          data: {
            code: error?.bbCode ?? 'INTERNAL_ERROR',
            ...(error?.bbData ?? {}),
            ...(error?.stack ? { stack: String(error.stack).split('\n').slice(0, 6).join('\n') } : {}),
            recoverable: true,
          },
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
      renders_max_total: state.limits.renders + (state.lookLimits?.renders ?? 400),
      restores_used: state.counters.restores, restores_max: state.limits.restores,
    },
    last_error: state.lastError,
    last_render: state.lastRender,
    loop: state.loop,
  })

  handlers['project.create_ysm'] = async (params = {}) => {
    const name = String(params.name || 'agent_model')
    const packDir = params.pack_dir ? normalizePackDir(params.pack_dir) : workspacePath('pack')
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
    const warnings = []
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
              origin: op.pivot ? vec(op.pivot) : [0, 0, 0],
              uv_offset: [0, 0],
              autouv: op.autouv === false ? 0 : 1,
            })
            if (op.name) cube.name = op.name
            if (op.rotation) cube.rotation = vec(op.rotation)
            if (op.inflate !== undefined) cube.inflate = Math.max(0, Math.min(16, Number(op.inflate) || 0))
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
              const faceSize = {
                north: [size[0], size[1]], south: [size[0], size[1]],
                east: [size[2], size[1]], west: [size[2], size[1]],
                up: [size[0], size[2]], down: [size[0], size[2]],
              }
              for (const [face, uv] of Object.entries(op.uv.faces)) {
                if (cube.faces?.[face] && Array.isArray(uv)) {
                  const override = op.uv.sizes?.[face] ?? op.uv_size
                  cube.faces[face].uv = [uv[0], uv[1]]
                  cube.faces[face].uv_size = Array.isArray(override) ? override.slice(0, 2) : faceSize[face]
                }
              }
            }
            changed.push({ kind: 'cube', id: cube.uuid, op: 'add', bone: bone.name })
            break
          }
          case 'update_cube': {
            const cube = findCube(op.cube_id ?? op.id ?? op.cube)
            if (!cube) throw err('INVALID_REFERENCE', `cube not found: ${op.cube_id ?? op.id ?? op.cube}`, { code: 'INVALID_REFERENCE' })
            if (op.origin) cube.from = vec(op.origin)
            if (op.size) {
              const from = vec(cube.from)
              cube.to = [from[0] + op.size[0], from[1] + op.size[1], from[2] + op.size[2]]
            }
            if (op.rotation) cube.rotation = vec(op.rotation)
            if (op.pivot) cube.origin = vec(op.pivot)
            if (op.inflate !== undefined) cube.inflate = Math.max(0, Math.min(16, Number(op.inflate) || 0))
            if (op.texture) {
              const tex = findTexture(op.texture)
              if (tex) for (const faceName of Object.keys(cube.faces ?? {})) if (cube.faces[faceName]) cube.faces[faceName].texture = tex.uuid
            }
            changed.push({ kind: 'cube', id: cube.uuid, op: 'update' })
            break
          }
          case 'update_bone': {
            const bone = findGroup(op.bone ?? op.bone_id ?? op.id)
            if (!bone) throw err('INVALID_REFERENCE', `bone not found: ${op.bone ?? op.bone_id ?? op.id}`, { code: 'INVALID_REFERENCE' })
            // 未知字段必须报错，不能静默忽略。
            // 实战教训：调用方传 {op:'update_bone', scale:[0.8,1,1]} 想收窄发团，
            // 返回 ok 且 revision+1，但骨骼 scale 不进渲染/导出，渲染 sha256 完全不变
            // —— 界面上「改成功了」，实际是空操作，白白浪费一轮迭代。
            const KNOWN = new Set(['op', 'bone', 'bone_id', 'id', 'pivot', 'rotation', 'name'])
            const unknown = Object.keys(op).filter((k) => !KNOWN.has(k))
            if (unknown.length) {
              const hint = unknown.includes('scale')
                ? '骨骼 scale 不被 Blockbench 渲染/导出支持；要改体量请用 update_cube 改方块几何，或加一根中间骨骼再改其子方块'
                : '可用字段: pivot / rotation / name'
              throw err('UNSUPPORTED_FIELD', `update_bone 不支持字段: ${unknown.join(', ')}`, {
                code: 'UNSUPPORTED_FIELD', fields: unknown, hint,
              })
            }
            if (op.pivot) bone.origin = vec(op.pivot)
            if (op.rotation) bone.rotation = vec(op.rotation)
            if (op.name) bone.name = op.name
            changed.push({ kind: 'bone', id: bone.uuid, op: 'update' })
            break
          }
          case 'set_uv': {
            const ids = Array.isArray(op.ids) ? op.ids : [op.id ?? op.cube_id]
            for (const id of ids.filter(Boolean)) {
              const cube = findCube(id)
              if (!cube) throw err('INVALID_REFERENCE', `cube not found: ${id}`, { code: 'INVALID_REFERENCE' })
              if (op.mode === 'box' || (!op.faces && op.uv)) {
                cube.box_uv = true
                cube.uv_offset = vec(op.uv ?? [0, 0])
                // box 模式此前只写 uv_offset，uv_size 被静默忽略 —— 调用方以为
                // 指定了贴图区域，实际仍按几何尺寸从 uv_offset 开始取样，导致
                // "UV 设置成功但外观没变"。这里补上显式尺寸支持。
                const boxSize = op.uv_size ?? op.size
                if (Array.isArray(boxSize) && boxSize.length >= 2) {
                  cube.stretch_uv = false
                  // Blockbench 的 box UV 尺寸由 faces 的 uv_size 承载，逐面写入
                  const from = vec(cube.from)
                  const to = vec(cube.to)
                  const dims = [to[0] - from[0], to[1] - from[1], to[2] - from[2]]
                  const faceSize = {
                    north: [dims[0], dims[1]], south: [dims[0], dims[1]],
                    east: [dims[2], dims[1]], west: [dims[2], dims[1]],
                    up: [dims[0], dims[2]], down: [dims[0], dims[2]],
                  }
                  const scaleX = Number(boxSize[0]) / Math.max(1e-6, Math.max(dims[0], dims[2]))
                  const scaleY = Number(boxSize[1]) / Math.max(1e-6, dims[1])
                  for (const faceName of ['north', 'south', 'east', 'west', 'up', 'down']) {
                    const f = cube.faces?.[faceName]
                    if (!f) continue
                    const base = faceSize[faceName] ?? [dims[0], dims[1]]
                    const sx = (faceName === 'east' || faceName === 'west') ? scaleX : scaleX
                    const sy = (faceName === 'up' || faceName === 'down') ? scaleX : scaleY
                    f.uv_size = [base[0] * sx, base[1] * sy].map((v) => Math.max(0.01, Math.round(v * 10000) / 10000))
                  }
                }
              } else if (op.faces) {
                cube.box_uv = false
                const from = vec(cube.from)
                const size = [vec(cube.to)[0] - from[0], vec(cube.to)[1] - from[1], vec(cube.to)[2] - from[2]]
                const faceSize = {
                  north: [size[0], size[1]], south: [size[0], size[1]],
                  east: [size[2], size[1]], west: [size[2], size[1]],
                  up: [size[0], size[2]], down: [size[0], size[2]],
                }
                const sizeOverrides = op.uv_size ?? op.sizes ?? {}
                for (const [faceName, uv] of Object.entries(op.faces)) {
                  if (!cube.faces?.[faceName] || !Array.isArray(uv)) continue
                  cube.faces[faceName].uv = [uv[0], uv[1]]
                  const override = sizeOverrides[faceName] ?? (Array.isArray(sizeOverrides) ? sizeOverrides : null)
                  if (Array.isArray(override)) {
                    cube.faces[faceName].uv_size = override.slice(0, 2)
                  } else {
                    cube.faces[faceName].uv_size = faceSize[faceName] ?? [size[0], size[1]]
                    // up/down 的内部约定：Y 方向取负（与默认模型一致）
                    if (faceName === 'up' || faceName === 'down') cube.faces[faceName].uv_size = [size[0], -size[2]]
                  }
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
            // 两种写法都接受：
            //   {op:'delete', refs:[{kind,id}, ...]}   ← 正式语法
            //   {op:'delete', kind:'cube', id:'...'}   ← 单目标简写
            // 之前只认 refs，用简写会被静默当成「没有要删的东西」而返回 ok，
            // 实测导致「以为删掉了、其实还在」的错误状态被后续操作继承。
            let refs = op.refs
            if (!Array.isArray(refs) || refs.length === 0) {
              if (op.id) refs = [{ kind: op.kind ?? 'cube', id: op.id }]
              else {
                throw err('INVALID_PARAMS',
                  'delete 需要 refs:[{kind,id}] 或 id（+可选 kind）',
                  { code: 'INVALID_PARAMS' })
              }
            }
            const missed = []
            for (const ref of refs) {
              const el = ref.kind === 'bone' ? findGroup(ref.id) : findCube(ref.id)
              if (!el) { missed.push(ref); continue }
              try { el.remove?.() } catch { /* ignore */ }
              changed.push({ kind: ref.kind, id: ref.id, op: 'delete' })
            }
            // 目标不存在时不能静默成功：明确报出来，调用方才知道状态没变
            if (missed.length && changed.length === 0) {
              throw err('INVALID_REFERENCE',
                `delete 目标都不存在: ${missed.map((r) => `${r.kind}:${r.id}`).join(', ')}`,
                { code: 'INVALID_REFERENCE' })
            }
            if (missed.length) {
              warnings.push({ code: 'DELETE_PARTIAL', message: `部分目标不存在: ${missed.map((r) => r.id).join(', ')}` })
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
      return { ok: true, revision, changed, warnings, digest: { revision, bones: Group.all.length, cubes: Cube.all.length } }
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
      let minX = canvas.width, minY = canvas.height, maxX = -1, maxY = -1
      for (let y = 0; y < canvas.height; y++) {
        for (let x = 0; x < canvas.width; x++) {
          const alpha = data[(y * canvas.width + x) * 4 + 3]
          if (alpha === 0) continue
          opaque += 1
          if (x < minX) minX = x
          if (y < minY) minY = y
          if (x > maxX) maxX = x
          if (y > maxY) maxY = y
        }
      }
      const bbox = maxX >= minX && maxY >= minY
        ? [minX / canvas.width, minY / canvas.height, maxX / canvas.width, maxY / canvas.height].map((v) => Math.round(v * 10000) / 10000)
        : null
      const edgeTouch = bbox ? (bbox[0] <= 0.002 || bbox[1] <= 0.002 || bbox[2] >= 0.998 || bbox[3] >= 0.998) : false
      // 64x64 粗粒度签名：避免 GPU 抗锯齿/编码的微小抖动造成误报
      const thumb = document.createElement('canvas')
      thumb.width = 64
      thumb.height = 64
      const tctx = thumb.getContext('2d')
      tctx.drawImage(image, 0, 0, 64, 64)
      const thumbData = tctx.getImageData(0, 0, 64, 64).data
      return {
        alpha_ratio: Math.round((opaque / (canvas.width * canvas.height)) * 10000) / 10000,
        bbox,
        edge_touch: edgeTouch,
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
    // focus.padding：外扩聚焦包围盒（以前这个参数被声明但完全没用，导致 closeup 总是触边）
    const focusPadding = Math.max(0, Math.min(4, Number(params.focus?.padding) || 0))
    let focusBounds = focusRef ? elementBounds(focusRef) : null
    if (focusBounds && focusPadding > 0) {
      const padUnits = Math.max(focusBounds.size[0], focusBounds.size[1], focusBounds.size[2]) * focusPadding
      focusBounds = {
        ...focusBounds,
        size: focusBounds.size.map((v) => v + padUnits * 2),
      }
    }
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
          alpha_ratio: alphaRatio, bbox: stats?.bbox ?? null, edge_touch: !!stats?.edge_touch,
          empty: alphaRatio !== null && alphaRatio < 0.001,
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
    const allEmpty = images.length > 0 && images.every((image) => image.empty === true)
    const edgeViews = images.filter((image) => image.edge_touch && image.empty !== true).map((image) => image.view)
    const changedCount = images.filter((image) => image.changed).length
    const verdict = allEmpty ? 'empty_render'
      : (!changedAny && pendingBefore > 0 ? 'no_visible_change'
        : (changedAny && edgeViews.length ? 'visible_change_clipped'
          : (changedAny ? 'visible_change' : 'no_change_expected')))
    const suggestions = []
    if (verdict === 'empty_render') suggestions.push('整张渲染全透明：检查相机 bounds/模型可见性；必要时 GPU safe-mode 重试')
    if (verdict === 'no_visible_change') {
      suggestions.push(unchangedStreak >= 3
        ? '连续多次编辑无可见变化：建议 bb_restore 回滚到最近检查点，换策略后再试'
        : '上次编辑未改变可见像素：检查 UV/纹理绑定/骨骼层级，不要继续叠加同类修改')
    }
    if (edgeViews.length) suggestions.push(`画面可能被裁切：${edgeViews.join(', ')} 触到画布边缘；用 bb_render_views({focus}) 或缩小 zoom`)
    if (unchangedStreak >= 3) suggestions.push('unchanged_streak >= 3，触发 no-progress watchdog：停止同类编辑，回滚或换方案')
    const review = {
      schema_version: 'watchdog-v2',
      mode: 'rule-based-v1 + external VLM image review',
      verdict,
      pending_edits_before_render: pendingBefore,
      unchanged_streak: unchangedStreak,
      changed_views: changedCount,
      metrics: {
        views: images.length,
        empty_views: images.filter((image) => image.empty).length,
        edge_touch_views: edgeViews,
        alpha_ratios: Object.fromEntries(images.map((image) => [image.view, image.alpha_ratio])),
        bboxes: Object.fromEntries(images.map((image) => [image.view, image.bbox])),
        diff_ratios: Object.fromEntries(images.map((image) => [image.view, image.diff_ratio])),
      },
      checks: [
        { id: 'not_empty', status: allEmpty ? 'fail' : 'pass' },
        { id: 'not_clipped', status: edgeViews.length ? 'warn' : 'pass' },
        { id: 'edit_visible', status: (!changedAny && pendingBefore > 0) ? 'fail' : 'pass' },
      ],
      suggestion: suggestions[0] ?? null,
      suggestions,
      vlm_hint: '把 images 附件交给视觉模型时，只判断造型/配色/纹理是否符合用户意图；结构错误优先看 bbox/alpha_ratio/edge_touch。',
    }
    return {
      revision, render_id: `render-${revision}`, images, cache_hit: false, elapsed_ms: 0,
      bounds: bounds, changed_any: changedAny, warnings, review,
    }
  }

  // ---- 视口实时反馈 v1.0（docs/07）----------------------------------------
  // 设计约束（务必保持）：
  //   1) 全部为**只读**方法：不进 MUTATING_METHODS、不吃 edit 预算、不 bump revision。
  //   2) 默认**不落盘**、不做 pngStats、不生成缩略图 —— 只为"快"。
  //   3) 相机定义与 fitCamera 的 zoom-to-fit 数学保持一致，避免两个视图不一致。

  /** 相机参数默认值。azimuth: 0=正前(-Z)，顺时针为正；elevation: 0=水平、90=正上。 */
  const CAMERA_DEFAULTS = { azimuth: 0, elevation: 0, distance: null, projection: 'ortho', fov: 40, padding: 0.05 }

  /** 由方位/俯仰角生成单位方向向量（与 VIEW_DIRS 的 front=[0,0,-1] 对齐）。 */
  function camDir(azimuthDeg, elevationDeg) {
    const az = (num(azimuthDeg, 0) * Math.PI) / 180
    const el = (num(elevationDeg, 0) * Math.PI) / 180
    return new THREE.Vector3(
      Math.sin(az) * Math.cos(el),
      Math.sin(el),
      -Math.cos(az) * Math.cos(el),
    ).normalize()
  }

  /**
   * 按相机描述摆放离屏 preview 的相机。复用既有 fitCamera 的 zoom-to-fit 公式，
   * 但允许显式给 azimuth/elevation/distance，并支持透视投影。
   */
  function applyCamera(preview, camIn, bounds) {
    const cam = { ...CAMERA_DEFAULTS, ...(camIn || {}) }
    const [cx, cy, cz] = bounds.center
    const [sx, sy, sz] = bounds.size
    const dir = camDir(cam.azimuth, cam.elevation)
    const autoDist = Math.max(sx, sy, sz) * 3
    const dist = Number.isFinite(cam.distance) ? Math.max(0.001, cam.distance) : autoDist

    const persp = cam.projection === 'persp'
    preview.setProjectionMode(!persp)
    preview.camera.position.set(cx + dir.x * dist, cy + dir.y * dist, cz + dir.z * dist)
    preview.controls.target.set(cx, cy, cz)
    preview.controls.update()

    const w = preview.width, h = preview.height
    const pad = Math.max(0, num(cam.padding, 0.05))
    const k = 1 + pad
    // 侧向包围盒随方位角变化：用与视线垂直的两个轴向尺寸近似
    const upAxis = Math.abs(dir.y) > 0.95 ? Math.max(sx, sz) : sy
    const sideAxis = Math.max(sx, sz)
    const needW = sideAxis * k
    const needH = upAxis * k
    if (persp) {
      preview.camera.fov = Math.max(5, Math.min(120, num(cam.fov, 40)))
      preview.camera.zoom = 1
      preview.camera.updateProjectionMatrix()
    } else {
      preview.camera.zoom = Math.min((2 * (w / 80)) / Math.max(needW, 0.001), (2 * (h / 80)) / Math.max(needH, 0.001))
      preview.camera.updateProjectionMatrix()
    }
    return {
      azimuth: +num(cam.azimuth, 0).toFixed(2),
      elevation: +num(cam.elevation, 0).toFixed(2),
      distance: +dist.toFixed(3),
      position: preview.camera.position.toArray().map((v) => +v.toFixed(3)),
      target: [cx, cy, cz].map((v) => +v.toFixed(3)),
      zoom: +(preview.camera.zoom ?? 1).toFixed(4),
      fov: +(preview.camera.fov ?? 40).toFixed(2),
      projection: persp ? 'persp' : 'ortho',
    }
  }

  /** 渲染一帧并以**同步**方式画进目标 2D 上下文（不经过 Image 异步解码）。 */
  function drawFrameInto(ctx2d, preview, size, background, dx, dy) {
    const prevBg = Canvas.scene.background
    try {
      if (background === null || background === undefined) {
        Canvas.scene.background = null
        preview.renderer?.setClearAlpha?.(0)
      } else if (colorOk(background)) {
        Canvas.scene.background = new THREE.Color(background)
        preview.renderer?.setClearAlpha?.(1)
      }
      const t0 = (typeof performance !== 'undefined' ? performance.now() : Date.now())
      Canvas.withoutGizmos(() => preview.render())
      // 关键：用 drawImage(canvas) 同步取像素，不能用 new Image() + onload
      ctx2d.drawImage(preview.canvas, 0, 0, preview.canvas.width, preview.canvas.height,
        dx, dy, size[0], size[1])
      const t1 = (typeof performance !== 'undefined' ? performance.now() : Date.now())
      return +(t1 - t0).toFixed(2)
    } finally {
      Canvas.scene.background = prevBg
    }
  }

  /**
   * 检测一帧是否"基本为空"（只有底色/全透明）。
   * 采样 64×64 缩略图的颜色多样性：<=1 种颜色视为空帧。
   * 用于离屏 preview 首次 resize 后的空帧自愈。
   */
  function frameLooksEmpty(canvas) {
    try {
      const c = document.createElement('canvas')
      c.width = 64; c.height = 64
      const cx = c.getContext('2d', { willReadFrequently: true })
      cx.drawImage(canvas, 0, 0, canvas.width, canvas.height, 0, 0, 64, 64)
      const d = cx.getImageData(0, 0, 64, 64).data
      const seen = new Set()
      let opaque = 0
      for (let i = 0; i < d.length; i += 4) {
        if (d[i + 3] > 8) opaque += 1
        if (seen.size < 32) seen.add((d[i] << 16) | (d[i + 1] << 8) | d[i + 2])
      }
      return { empty: seen.size <= 1, colors: seen.size, opaqueRatio: +(opaque / (64 * 64)).toFixed(3) }
    } catch {
      return { empty: false, colors: -1, opaqueRatio: null }
    }
  }

  /**
   * 渲染一帧并编码为 dataURL。不落盘、不统计。
   *
   * 注意：这里**先同步 drawImage 到 2D canvas 再 toDataURL**，而不是直接
   * `preview.canvas.toDataURL()`。离屏 preview 在尺寸/投影变化后，
   * 直接读 WebGL canvas 偶尔会拿到上一帧（或空 buffer）；经由 2D canvas
   * 中转能拿到确定的最新像素（与 render.sheet 走同一条路径）。
   */
  /**
   * 一次性全局预热：离屏 preview 在本进程内的**第一次**真正渲染必然是空帧，
   * 与尺寸/相机/参数都无关（实测：同一张 sheet 的第 1 格空、第 2 格正常）。
   * 每个渲染类 handler 入口调用此函数，确保"第一格"不白给。
   */
  /**
   * 预热离屏 preview。
   *
   * 实测事实：`preview.resize()` 之后（以及本进程的首次渲染）第一帧是空帧，
   * 第二帧才有内容。这里**每次都渲两帧**并丢弃，代价约 1-2ms，
   * 换取"调用方永远拿到有内容的图"。不做全局门控 —— resize 会重置状态。
   */
  /**
   * 强制离屏 preview 重绘一帧。
   *
   * 实测事实（关键）：离屏 preview 的 `render()` 只在**相机位姿相对上次发生变化**
   * 时才真正重绘；位姿不变时反复 `render()` 会得到空 buffer（sheet 里“第 1 格渲
   * 4 次都空、第 2 格一次就成”就是这么来的）。
   * 因此这里先微移相机、再摆回目标位姿，制造一次真实变化。
   */
  function forceRedraw(preview, camSpec, bounds) {
    try {
      const cam = preview.camera
      const p = cam.position
      const dx = p.x + 0.013, dy = p.y + 0.011, dz = p.z + 0.017
      cam.position.set(dx, dy, dz)
      cam.updateMatrixWorld(true)
      preview.render()
    } catch { /* ignore */ }
    return applyCamera(preview, camSpec || {}, bounds)
  }

  /**
   * 渲染一帧到目标 2D 上下文，并保证拿到**非空**结果。
   *
   * 实测事实（踩坑记录）：离屏 preview 在**本进程内的首次渲染**必然为空帧，
   * 与尺寸/相机/参数都无关；第二次起就正常。所以这里做"空则再来一遍"的
   * 有界重试（最多 4 遍，单遍约 1-2ms），保证调用方永远拿到有内容的图。
   *
   * @returns {{ms:number, probe:{empty:boolean,colors:number}, passes:number}}
   */
  /**
   * 检测 2D canvas 上**某个矩形区域**是否基本为空。
   *
   * 拼图必须按格检查：整张 sheet 有别的格子撑着，检查整张永远返回"不空"，
   * 于是第一格空了也发现不了 —— 这就是"自动附图第 1 格全空"的成因。
   */
  function regionLooksEmpty(canvas, x, y, w, h) {
    try {
      const sw = Math.max(1, Math.min(64, Math.floor(w)))
      const sh = Math.max(1, Math.min(64, Math.floor(h)))
      const c = document.createElement('canvas')
      c.width = sw
      c.height = sh
      const cx = c.getContext('2d', { willReadFrequently: true })
      cx.drawImage(canvas, x, y, w, h, 0, 0, sw, sh)
      const d = cx.getImageData(0, 0, sw, sh).data
      const seen = new Set()
      let opaque = 0
      for (let i = 0; i < d.length; i += 4) {
        if (d[i + 3] > 8) opaque += 1
        if (seen.size < 32) seen.add((d[i] << 16) | (d[i + 1] << 8) | d[i + 2])
      }
      return { empty: seen.size <= 1, colors: seen.size, opaqueRatio: +(opaque / (sw * sh)).toFixed(3) }
    } catch {
      return { empty: false, colors: -1, opaqueRatio: null }
    }
  }

  function drawFrameReliably(ctx2d, preview, size, background, dx, dy, prepare) {
    let ms = 0
    let probe = { empty: true, colors: 0, opaqueRatio: null }
    let passes = 0
    while (passes < 3) {
      passes += 1
      if (typeof prepare === 'function') { try { prepare() } catch { /* ignore */ } }
      ms = drawFrameInto(ctx2d, preview, size, background, dx, dy)
      // 必须按**格子区域**判定：整张 sheet 有别的格子撑着，永远"不空"
      probe = regionLooksEmpty(ctx2d.canvas, dx, dy, size[0], size[1])
      if (!probe.empty) break
    }
    return { ms, probe, passes }
  }

  /**
   * 渲染单帧并保证有内容（单图路径，与 render.sheet 的每格共用同一套重试逻辑）。
   *
   * 复用同一块 scratch canvas：每次新建 canvas 反而拿不到内容；
   * 并复用 drawFrameReliably 的"按区域判空 + 每次重试重跑 resize/applyCamera"。
   */
  let scratchCanvas = null
  let scratchCtx = null
  function renderFrameReliably(preview, w, h, background, camSpec, bounds) {
    if (!scratchCanvas) {
      scratchCanvas = document.createElement('canvas')
      scratchCtx = scratchCanvas.getContext('2d')
    }
    if (scratchCanvas.width !== w) scratchCanvas.width = w
    if (scratchCanvas.height !== h) scratchCanvas.height = h
    const prepare = () => {
      preview.resize(w, h)
      applyCamera(preview, camSpec || {}, bounds)
    }
    const { ms, probe, passes } = drawFrameReliably(
      scratchCtx, preview, [w, h], background, 0, 0, prepare,
    )
    return { canvas: scratchCanvas, ms, probe, passes }
  }

  function renderOneFrame(preview, size, background) {
    const prevBg = Canvas.scene.background
    try {
      if (background === null || background === undefined) {
        Canvas.scene.background = null
        preview.renderer?.setClearAlpha?.(0)
      } else if (colorOk(background)) {
        Canvas.scene.background = new THREE.Color(background)
        preview.renderer?.setClearAlpha?.(1)
      }
      const t0 = (typeof performance !== 'undefined' ? performance.now() : Date.now())
      Canvas.withoutGizmos(() => preview.render())

      const out = document.createElement('canvas')
      out.width = Math.round(size[0])
      out.height = Math.round(size[1])
      const octx = out.getContext('2d')
      octx.drawImage(preview.canvas, 0, 0, preview.canvas.width, preview.canvas.height,
        0, 0, out.width, out.height)
      const dataUrl = out.toDataURL('image/png')
      const t1 = (typeof performance !== 'undefined' ? performance.now() : Date.now())

      // 让调用方可以对这个 2D canvas 做空帧检测（与 pixel 同源，最可靠）
      return { dataUrl, ms: +(t1 - t0).toFixed(2), canvas: out }
    } finally {
      Canvas.scene.background = prevBg
    }
  }

  /** 取离屏 preview；不可用则抛 ENGINE_DEGRADED。 */
  function offscreenPreview() {
    const preview = window.MediaPreview ?? window.Screencam?.NoAAPreview
    if (!preview) throw err('ENGINE_DEGRADED', 'offscreen preview unavailable', { code: 'ENGINE_DEGRADED' })
    return preview
  }

  /** 解析 focus/bounds：focus 元素存在则用元素包围盒，否则用整模型包围盒。 */
  function resolveBounds(focusRef) {
    const modelB = modelBounds()
    if (!modelB) throw err('INVALID_OPERATION', 'model bounds empty', { code: 'INVALID_OPERATION' })
    if (!focusRef) return modelB
    const fb = elementBounds(focusRef)
    if (!fb) throw err('INVALID_REFERENCE', `focus element not found: ${focusRef}`, { code: 'INVALID_REFERENCE' })
    return fb
  }

  /** camera.get：读当前位姿。优先读用户主视口（若可用），否则读离屏 preview。 */
  handlers['camera.get'] = (params = {}) => {
    ensureProject()
    const wantSource = params.source === 'main' ? 'main' : 'offscreen'
    let preview = null
    let source = wantSource
    if (wantSource === 'main') {
      try {
        const main = (typeof Preview !== 'undefined' ? Preview : window.Preview)
        if (main?.camera) preview = main
        else { source = 'offscreen' }
      } catch { source = 'offscreen' }
    }
    if (!preview) {
      preview = offscreenPreview()
      source = 'offscreen'
    }
    const cam = preview.camera
    const tgt = preview.controls?.target
    const b = modelBounds()
    const center = b ? b.center : [0, 0, 0]
    const pos = cam.position.toArray()
    let azimuth = 0, elevation = 0
    if (tgt) {
      const d = new THREE.Vector3(pos[0] - tgt.x, pos[1] - tgt.y, pos[2] - tgt.z)
      const horiz = Math.hypot(d.x, d.z)
      elevation = (Math.atan2(d.y, horiz) * 180) / Math.PI
      // 反解 camDir：x=sin(az)cos(el), z=-cos(az)cos(el)
      azimuth = (Math.atan2(d.x, -d.z) * 180) / Math.PI
    }
    return {
      ok: true,
      source,
      azimuth: +azimuth.toFixed(2),
      elevation: +elevation.toFixed(2),
      distance: +new THREE.Vector3(pos[0] - (tgt?.x ?? center[0]), pos[1] - (tgt?.y ?? center[1]), pos[2] - (tgt?.z ?? center[2])).length().toFixed(3),
      position: pos.map((v) => +v.toFixed(3)),
      target: tgt ? [tgt.x, tgt.y, tgt.z].map((v) => +v.toFixed(3)) : center,
      zoom: +(cam.zoom ?? 1).toFixed(4),
      fov: +(cam.fov ?? 40).toFixed(2),
      projection: cam.isOrthographicCamera ? 'ortho' : 'persp',
      revision: state.revision,
      note: source === 'main' ? '用户主视口（只读镜像，不影响用户操作）' : '离屏 preview（AI 自己的视图）',
    };
  }

  /** camera.set：设置离屏相机位姿并回读实际值。纯内部状态，不改文档、不 bump revision。 */
  handlers['camera.set'] = (params = {}) => {
    ensureProject()
    const preview = offscreenPreview()
    const size = Array.isArray(params.size) ? params.size : [preview.width || 640, preview.height || 640]
    preview.resize(size[0], size[1])
    const bounds = resolveBounds(params.focus)
    const camera = applyCamera(preview, params, bounds)
    return { ok: true, size, camera, revision: state.revision, pending_render: true }
  }

  /**
   * render.preview：单帧预览。
   * 与 render.views 的区别：不落盘、不做 pngStats/缩略图、不参与 changed 判定、elapsed_ms 真实。
   */
  handlers['render.preview'] = (params = {}) => {
    ensureProject()
    const tStart = (typeof performance !== 'undefined' ? performance.now() : Date.now())
    const preview = offscreenPreview()
    const size = Array.isArray(params.size) ? params.size : [640, 640]
    const w = Math.max(64, Math.min(4096, Math.round(num(size[0], 640))))
    const h = Math.max(64, Math.min(4096, Math.round(num(size[1], 640))))
    const bounds = resolveBounds(params.focus)

    // 关键顺序（踩过的坑）：
    //   1) resize 必须在 applyCamera 之前（resize 会重置相机与 controls）；
    //   2) applyCamera 之后必须 primePreview（渲两帧丢弃），
    //      否则第一帧是空帧，整张图只有底色。
    preview.resize(w, h)

    const camera = forceRedraw(preview, params.camera || params, bounds)
    const { canvas: out, ms: renderMs, probe, passes } = renderFrameReliably(preview, w, h, params.background, params.camera || params, bounds)
    const dataUrl = out.toDataURL('image/png')

    const base64 = dataUrl.slice(dataUrl.indexOf(',') + 1)
    const tEnd = (typeof performance !== 'undefined' ? performance.now() : Date.now())

    return {
      ok: true,
      png: base64,
      width: w, height: h,
      bytes: Math.round(base64.length * 0.75),
      revision: state.revision,
      camera,
      focus: params.focus ?? null,
      render_ms: renderMs,
      frames_color_probe: probe,
      render_passes: passes,
      elapsed_ms: +(tEnd - tStart).toFixed(2),
    }
  }

  /**
   * render.turntable：绕轴转一圈，返回 N 帧。
   * 用于"自由转头看模型"，替代三视图脑补。默认不落盘。
   */
  handlers['render.turntable'] = (params = {}) => {
    ensureProject()
    const tStart = (typeof performance !== 'undefined' ? performance.now() : Date.now())
    const preview = offscreenPreview()
    const size = Array.isArray(params.size) ? params.size : [320, 320]
    const w = Math.max(64, Math.min(2048, Math.round(num(size[0], 320))))
    const h = Math.max(64, Math.min(2048, Math.round(num(size[1], 320))))
    const steps = Math.max(2, Math.min(24, Math.round(num(params.steps, 8))))
    const from = num(params.from, 0)
    const to = num(params.to, 360)
    const elevation = num(params.elevation, 15)
    const axis = params.axis === 'x' ? 'x' : 'y'
    const bounds = resolveBounds(params.focus)

    preview.resize(w, h)

    const frames = []
    for (let i = 0; i < steps; i++) {
      const t = steps === 1 ? 0 : i / steps   // 不重复首尾
      const angle = from + (to - from) * t
      const cam = axis === 'y'
        ? { azimuth: angle, elevation, projection: params.projection, padding: params.padding }
        : { azimuth: num(params.azimuth, 0), elevation: angle, projection: params.projection, padding: params.padding }
      const camActual = applyCamera(preview, cam, bounds)
      const frame = renderOneFrame(preview, [w, h], params.background)
      const b64 = frame.dataUrl.slice(frame.dataUrl.indexOf(',') + 1)
      frames.push({
        index: i,
        azimuth: camActual.azimuth,
        elevation: camActual.elevation,
        png: b64,
        bytes: Math.round(b64.length * 0.75),
        render_ms: frame.ms,
      })
    }
    const tEnd = (typeof performance !== 'undefined' ? performance.now() : Date.now())
    return {
      ok: true,
      axis, from, to, steps, elevation,
      width: w, height: h,
      revision: state.revision,
      frames,
      total_bytes: frames.reduce((n, f) => n + f.bytes, 0),
      elapsed_ms: +(tEnd - tStart).toFixed(2),
    }
  }

  /**
   * render.animation_frame：在指定动画的时间轴上采样若干帧。
   *
   * 风险（docs/07 R5）：Timeline.time / Animation.selected 是 GUI 全局状态，
   * 因此全程保存并恢复，且 GUI 可见时直接拒绝（不抢占用户的视图与状态）。
   */
  handlers['render.animation_frame'] = (params = {}) => {
    ensureProject()
    if (state.guiVisible) {
      throw err('GUI_BUSY', 'user is inspecting Blockbench; hide the GUI first', { code: 'GUI_BUSY', hint: 'run /hide then retry' })
    }
    const tStart = (typeof performance !== 'undefined' ? performance.now() : Date.now())
    const preview = offscreenPreview()

    const animName = params.animation ?? params.name ?? null
    const anim = animName
      ? (Animation.all.find((a) => a.name === animName || a.uuid === animName) ?? null)
      : Animation.selected
    if (!anim) throw err('INVALID_REFERENCE', `animation not found: ${animName}`, { code: 'INVALID_REFERENCE' })

    const size = Array.isArray(params.size) ? params.size : [320, 320]
    const w = Math.max(64, Math.min(2048, Math.round(num(size[0], 320))))
    const h = Math.max(64, Math.min(2048, Math.round(num(size[1], 320))))
    const samples = Math.max(2, Math.min(16, Math.round(num(params.samples, 4))))
    const len = Math.max(0.001, num(anim.length, 1))
    const t0s = num(params.from, 0)
    const t1s = num(params.to, len)
    const bounds = resolveBounds(params.focus)

    preview.resize(w, h)

    // ---- 保存 GUI 全局状态
    const savedTime = Timeline.time
    const savedSelected = Animation.selected
    const savedPlaying = Animation.all.filter((a) => a.playing).map((a) => a.uuid)
    state.suppressUserEdit = true

    const frames = []
    try {
      anim.select?.()
      try { Canvas.withoutGizmos(() => preview.render()) } catch { /* warm-up */ }

      for (let i = 0; i < samples; i++) {
        const frac = samples === 1 ? 0 : i / (samples - 1)
        const time = t0s + (t1s - t0s) * frac
        Timeline.time = time
        try {
          Animator.showDefaultPose(true)
          Animator.stackAnimations([anim], false)
          Animator.displayMeshDeformation?.()
        } catch { /* 部分格式无骨骼变形 */ }
        const frame = renderOneFrame(preview, [w, h], params.background)
        const b64 = frame.dataUrl.slice(frame.dataUrl.indexOf(',') + 1)
        frames.push({
          index: i,
          time: +time.toFixed(3),
          png: b64,
          bytes: Math.round(b64.length * 0.75),
          render_ms: frame.ms,
        })
      }
    } finally {
      // ---- 恢复 GUI 全局状态（即使中途抛错）
      try { Timeline.time = savedTime } catch { /* ignore */ }
      try {
        if (savedSelected) savedSelected.select?.()
        Animator.showDefaultPose(true)
        Animator.stackAnimations(
          Animation.all.filter((a) => savedPlaying.includes(a.uuid)),
          false,
        )
        Animator.displayMeshDeformation?.()
      } catch { /* ignore */ }
      state.suppressUserEdit = false
    }

    const tEnd = (typeof performance !== 'undefined' ? performance.now() : Date.now())
    return {
      ok: true,
      animation: anim.name,
      length: +len.toFixed(3),
      from: +t0s.toFixed(3), to: +t1s.toFixed(3), samples,
      width: w, height: h,
      revision: state.revision,
      frames,
      total_bytes: frames.reduce((n, f) => n + f.bytes, 0),
      elapsed_ms: +(tEnd - tStart).toFixed(2),
    }
  }

  /**
   * render.sheet：**一次性把 N 个视角/时刻渲染并合成为一张 PNG**。
   *
   * 为什么在 renderer 内合成（而不是 Host 侧）：
   *   1) 只回传 1 张 PNG，而不是 N 张 —— WS 是 text JSON、单条上限 8MB；
   *   2) Host 侧（纯 Node 测试环境）没有 canvas，合成要额外依赖；
   *   3) 一张图装 4 帧与装 1 帧 token 同价，"多留一帧"几乎免费。
   *
   * cells 每项支持三种来源（可混用）：
   *   { view: 'front' }                        固定机位
   *   { camera: { azimuth, elevation, ... } }  参数化相机
   *   { time: 0.5 }                            动画时间点（需 animation 参数）
   *   { texture: { name, scale, region } }     贴图放大（type:'texture' 时）
   */
  handlers['render.sheet'] = async (params = {}) => {
    ensureProject()
    const tStart = (typeof performance !== 'undefined' ? performance.now() : Date.now())
    const preview = offscreenPreview()

    const cellsIn = Array.isArray(params.cells) && params.cells.length
      ? params.cells.slice(0, 16)
      : [{ view: 'front' }, { view: 'iso_fr' }]

    const count = cellsIn.length
    const gap = Math.max(0, Math.min(8, Math.round(num(params.gap, 1))))
    const cellPx = Math.max(64, Math.min(1024, Math.round(num(params.cell, 320))))

    // 布局：默认按接近 4:3 排（ceil(sqrt(n*1.33)) 列），而不是竖排长条
    let cols = Math.max(1, Math.round(num(params.cols, 0)))
    if (!cols) cols = Math.max(1, Math.ceil(Math.sqrt(count * 1.33)))
    cols = Math.min(cols, count)
    const rows = Math.ceil(count / cols)

    const sheetW = cols * cellPx
    const sheetH = rows * cellPx
    const sheet = document.createElement('canvas')
    sheet.width = sheetW
    sheet.height = sheetH
    const sctx = sheet.getContext('2d')
    sctx.imageSmoothingEnabled = true
    sctx.imageSmoothingQuality = 'high'

    // 底色：不透明底色能避免"透明=黑"被误读，也让多格之间有清晰边界
    const bg = colorOk(params.background) ? params.background : null
    if (bg) { sctx.fillStyle = bg; sctx.fillRect(0, 0, sheetW, sheetH) }

    // 动画准备（所有 cell 共用同一个动画上下文）
    const animName = params.animation ?? null
    let anim = null
    if (cellsIn.some((c) => c && c.time !== undefined)) {
      if (state.guiVisible) throw err('GUI_BUSY', 'user is inspecting Blockbench; hide the GUI first', { code: 'GUI_BUSY', hint: 'run /hide then retry' })
      anim = animName
        ? (Animation.all.find((a) => a.name === animName || a.uuid === animName) ?? null)
        : Animation.selected
      if (!anim) throw err('INVALID_REFERENCE', `animation not found: ${animName}`, { code: 'INVALID_REFERENCE' })
    }

    const bounds = resolveBounds(params.focus)
    const savedTime = (typeof Timeline !== 'undefined') ? Timeline.time : 0
    const savedSelected = (typeof Animation !== 'undefined') ? Animation.selected : null
    const savedPlaying = (typeof Animation !== 'undefined') ? Animation.all.filter((a) => a.playing).map((a) => a.uuid) : []
    if (anim) state.suppressUserEdit = true

    const cells = []
    try {
      preview.resize(cellPx, cellPx)
        if (anim) { try { anim.select?.() } catch { /* ignore */ } }

      for (let i = 0; i < count; i++) {
        const cell = cellsIn[i] || {}
        const r = Math.floor(i / cols)
        const c = i % cols
        const dx = c * cellPx, dy = r * cellPx

        // 动画姿势
        if (anim && cell.time !== undefined) {
          try {
            Timeline.time = cell.time
            Animator.showDefaultPose(true)
            Animator.stackAnimations([anim], false)
            Animator.displayMeshDeformation?.()
          } catch { /* 部分格式无骨骼变形 */ }
        }

        // 相机：view 优先，其次 camera
        let camSpec = cell.camera || null
        if (!camSpec && cell.view && VIEW_DIRS[cell.view]) {
          const [vx, vy, vz] = VIEW_DIRS[cell.view]
          // 由方向向量反解方位/俯仰，保持与 camDir 一致
          const horiz = Math.hypot(vx, vz) || 1e-9
          camSpec = {
            azimuth: (Math.atan2(vx, -vz) * 180) / Math.PI,
            elevation: (Math.atan2(vy, horiz) * 180) / Math.PI,
            projection: params.projection,
            padding: params.padding,
          }
        }
        // 关键顺序（踩过的坑）：resize 与 applyCamera 必须**紧贴**在 draw 之前，
        // 中间插任何别的调用都会拿到空 buffer。所以把这两步包成 prepare，
        // 交给 drawFrameReliably 在每次重试前重跑。
        const cellBounds = cell.focus ? resolveBounds(cell.focus) : bounds
        const prepareCell = () => {
          preview.resize(cellPx, cellPx)
          return applyCamera(preview, camSpec || {}, cellBounds)
        }
        let camActual = prepareCell()
        const { ms: coreMs, probe: cellProbe, passes: cellPasses } =
          drawFrameReliably(sctx, preview, [cellPx, cellPx], bg, dx, dy, () => { camActual = prepareCell() })

        // 格号（左上角），便于模型引用"第几格"
        if (params.labels !== false) {
          const label = String(i + 1)
          sctx.font = `${Math.max(10, Math.round(cellPx * 0.06))}px sans-serif`
          const tw = sctx.measureText(label).width
          sctx.fillStyle = 'rgba(0,0,0,0.55)'
          sctx.fillRect(dx + 2, dy + 2, tw + 8, Math.round(cellPx * 0.09) + 4)
          sctx.fillStyle = '#ffffff'
          sctx.fillText(label, dx + 6, dy + Math.round(cellPx * 0.09))
        }

        cells.push({
          index: i,
          view: cell.view ?? null,
          time: cell.time ?? null,
          camera: camActual,
          render_ms: coreMs,
          colors: cellProbe.colors,
          empty: cellProbe.empty,
          passes: cellPasses,
        })

        // 格间细线
        if (gap > 0 && c < cols - 1) {
          sctx.fillStyle = 'rgba(255,255,255,0.15)'
          sctx.fillRect(dx + cellPx - gap, dy, gap, cellPx)
        }
      }
    } finally {
      if (anim) {
        try { Timeline.time = savedTime } catch { /* ignore */ }
        try {
          if (savedSelected) savedSelected.select?.()
          Animator.showDefaultPose(true)
          Animator.stackAnimations(Animation.all.filter((a) => savedPlaying.includes(a.uuid)), false)
          Animator.displayMeshDeformation?.()
        } catch { /* ignore */ }
        state.suppressUserEdit = false
      }
    }

    const dataUrl = sheet.toDataURL('image/png')
    const base64 = dataUrl.slice(dataUrl.indexOf(',') + 1)
    const tEnd = (typeof performance !== 'undefined' ? performance.now() : Date.now())

    return {
      ok: true,
      png: base64,
      width: sheetW, height: sheetH,
      bytes: Math.round(base64.length * 0.75),
      cols, rows, cell: cellPx,
      count,
      animation: anim ? anim.name : null,
      revision: state.revision,
      cells,
      elapsed_ms: +(tEnd - tStart).toFixed(2),
    }
  }

  /**
   * render.texture_sheet：贴图区域的像素级放大，可多块拼一张。
   * 用于"精修核对"——小改动往往只有几个像素，整模型渲染看不出来。
   */
  handlers['render.texture_sheet'] = (params = {}) => {
    ensureProject()
    const tStart = (typeof performance !== 'undefined' ? performance.now() : Date.now())
    const regions = Array.isArray(params.regions) && params.regions.length
      ? params.regions.slice(0, 8)
      : [params.region ?? null]
    const scale = Math.max(1, Math.min(16, Math.round(num(params.scale, 8))))
    const bg = colorOk(params.background) ? params.background : null

    const panels = []
    for (const spec of regions) {
      const tex = findTexture(spec?.texture ?? params.texture)
      if (!tex) throw err('INVALID_REFERENCE', `texture not found: ${spec?.texture ?? params.texture}`, { code: 'INVALID_REFERENCE' })
      const region = spec?.region ?? spec ?? [0, 0, tex.width - 1, tex.height - 1]
      const sw = Math.max(1, region[2] - region[0] + 1)
      const sh = Math.max(1, region[3] - region[1] + 1)
      panels.push({ tex, region, sw, sh })
    }

    // 所有面板统一缩放到同一格边（保住"像素放大"观感，用最近邻）
    const maxSide = Math.max(...panels.map((p) => Math.max(p.sw, p.sh)))
    const cell = Math.max(64, Math.min(1024, maxSide * scale))
    const cols = Math.max(1, Math.round(num(params.cols, panels.length > 2 ? 2 : panels.length)))
    const rows = Math.ceil(panels.length / cols)

    const sheet = document.createElement('canvas')
    sheet.width = cols * cell
    sheet.height = rows * cell
    const ctx = sheet.getContext('2d')
    ctx.imageSmoothingEnabled = false   // 像素放大必须最近邻
    if (bg) { ctx.fillStyle = bg; ctx.fillRect(0, 0, sheet.width, sheet.height) }

    panels.forEach((p, i) => {
      const r = Math.floor(i / cols), c = i % cols
      const dx = c * cell, dy = r * cell
      // 等比放大，居中
      const s = Math.min(cell / p.sw, cell / p.sh)
      const w = Math.round(p.sw * s), h = Math.round(p.sh * s)
      const ox = dx + Math.round((cell - w) / 2)
      const oy = dy + Math.round((cell - h) / 2)
      ctx.drawImage(p.tex.canvas, p.region[0], p.region[1], p.sw, p.sh, ox, oy, w, h)
      if (params.labels !== false) {
        ctx.font = `${Math.max(10, Math.round(cell * 0.055))}px sans-serif`
        ctx.fillStyle = 'rgba(0,0,0,0.6)'
        const label = `${i + 1}:${p.tex.name}`
        const tw = ctx.measureText(label).width
        ctx.fillRect(dx + 2, dy + 2, tw + 6, Math.round(cell * 0.075) + 4)
        ctx.fillStyle = '#fff'
        ctx.fillText(label, dx + 5, dy + Math.round(cell * 0.075))
      }
    })

    const dataUrl = sheet.toDataURL('image/png')
    const base64 = dataUrl.slice(dataUrl.indexOf(',') + 1)
    const tEnd = (typeof performance !== 'undefined' ? performance.now() : Date.now())

    return {
      ok: true,
      png: base64,
      width: sheet.width, height: sheet.height,
      bytes: Math.round(base64.length * 0.75),
      cols, rows, cell, count: panels.length,
      panels: panels.map((p, i) => ({ index: i, texture: p.tex.name, region: p.region, w: p.sw, h: p.sh })),
      revision: state.revision,
      elapsed_ms: +(tEnd - tStart).toFixed(2),
    }
  }

  // ------------------------------------------------------------ 参考图工具
  // 把磁盘上的参考图拼成一张带编号的对照表，顺带算 dHash 供感知去重。
  // 放在 bridge 而不是 host 的原因：只有 renderer 有 canvas 能解码 PNG/JPEG，
  // host 侧无原生图像库（见 docs/11）。

  function refImageMime(p) {
    const low = String(p || '').toLowerCase()
    if (low.endsWith('.png')) return 'image/png'
    if (low.endsWith('.webp')) return 'image/webp'
    if (low.endsWith('.gif')) return 'image/gif'
    if (low.endsWith('.bmp')) return 'image/bmp'
    return 'image/jpeg'
  }

  function loadImageFromFile(abs) {
    return new Promise((resolve, reject) => {
      let buf = null
      try { buf = nodeFs.readFileSync(abs) } catch (error) { reject(error); return }
      if (!buf || !buf.length) { reject(new Error('empty file')); return }
      const dataUrl = `data:${refImageMime(abs)};base64,${buf.toString('base64')}`
      const img = new Image()
      img.onload = () => resolve(img)
      img.onerror = () => reject(new Error('image decode failed'))
      img.src = dataUrl
    })
  }

  /** 64 位 dHash（9x8 灰度水平差分）→ 16 进制。用于发现"同一张图不同来源"。 */
  function dHashOf(img) {
    try {
      const c = document.createElement('canvas')
      c.width = 9; c.height = 8
      const ctx1 = c.getContext('2d')
      ctx1.drawImage(img, 0, 0, 9, 8)
      const d = ctx1.getImageData(0, 0, 9, 8).data
      const gray = new Array(72)
      for (let i = 0; i < 72; i++) {
        gray[i] = 0.299 * d[i * 4] + 0.587 * d[i * 4 + 1] + 0.114 * d[i * 4 + 2]
      }
      let bits = ''
      for (let y = 0; y < 8; y++) {
        for (let x = 0; x < 8; x++) bits += gray[y * 9 + x] > gray[y * 9 + x + 1] ? '1' : '0'
      }
      return { bits, hex: BigInt(`0b${bits}`).toString(16).padStart(16, '0') }
    } catch { return null }
  }

  handlers['ref.sheet'] = async (params = {}) => {
    const files = (Array.isArray(params.files) ? params.files : []).filter(Boolean).map(String)
    if (!files.length) throw err('INVALID_PARAMS', 'files required', { code: 'INVALID_PARAMS' })
    const cellPx = Math.min(1024, Math.max(96, Number(params.cell) || 240))
    // 注意：Number(undefined) 是 NaN，而 `NaN ?? 6` 仍是 NaN —— 必须显式判有限。
    const gapRaw = Number(params.gap)
    const gap = Number.isFinite(gapRaw) ? Math.min(24, Math.max(0, gapRaw)) : 6
    const cols = Math.min(12, Math.max(1, Number(params.cols) || Math.min(6, Math.ceil(Math.sqrt(files.length * 1.4)))))
    const rows = Math.ceil(files.length / cols)
    const withLabels = params.labels !== false
    const wantHash = params.hash !== false
    const tStart = (typeof performance !== 'undefined' ? performance.now() : Date.now())

    const sheet = document.createElement('canvas')
    sheet.width = cols * (cellPx + gap) - gap
    sheet.height = rows * (cellPx + gap) - gap
    const sctx = sheet.getContext('2d')
    if (colorOk(params.background)) {
      sctx.fillStyle = params.background
      sctx.fillRect(0, 0, sheet.width, sheet.height)
    }

    const images = []
    // 关键：逐张 load → draw → hash → 丢弃引用。4000px 的设定集原图若一次性全留在内存，
    // 24 张就能吃掉 1GB+，所以不能先全载入再画。
    for (let i = 0; i < files.length; i++) {
      const cx = (i % cols) * (cellPx + gap)
      const cy = Math.floor(i / cols) * (cellPx + gap)
      const rec = { index: i, file: files[i], ok: false }
      try {
        const abs = packAbsolute(String(cfg.workspace || ''), files[i])
        const img = await loadImageFromFile(abs)
        const w = img.naturalWidth || img.width
        const h = img.naturalHeight || img.height
        const s = Math.min(cellPx / Math.max(1, w), cellPx / Math.max(1, h))
        const dw = Math.max(1, Math.round(w * s))
        const dh = Math.max(1, Math.round(h * s))
        const dx = cx + Math.floor((cellPx - dw) / 2)
        const dy = cy + Math.floor((cellPx - dh) / 2)
        // 透明底垫一层，避免 PNG 透明区在深色底上看起来像"缺块"
        sctx.fillStyle = '#141418'
        sctx.fillRect(cx, cy, cellPx, cellPx)
        sctx.drawImage(img, dx, dy, dw, dh)
        if (withLabels) {
          const label = String(i)
          sctx.font = `${Math.max(11, Math.round(cellPx * 0.075))}px sans-serif`
          const tw = sctx.measureText(label).width
          sctx.fillStyle = 'rgba(0,0,0,0.6)'
          sctx.fillRect(cx + 2, cy + 2, tw + 8, Math.round(cellPx * 0.1) + 2)
          sctx.fillStyle = '#ffd84d'
          sctx.fillText(label, cx + 6, cy + Math.round(cellPx * 0.09))
        }
        rec.ok = true
        rec.width = w
        rec.height = h
        rec.ratio = +(w / Math.max(1, h)).toFixed(3)
        if (wantHash) {
          const hash = dHashOf(img)
          if (hash) { rec.dhash = hash.hex; rec.dhash_bits = hash.bits }
        }
      } catch (error) {
        rec.error = error?.message ?? String(error)
        sctx.fillStyle = '#2a1d1d'
        sctx.fillRect(cx, cy, cellPx, cellPx)
        sctx.fillStyle = '#b06060'
        sctx.font = `${Math.max(10, Math.round(cellPx * 0.06))}px sans-serif`
        sctx.fillText('load failed', cx + 6, cy + cellPx / 2)
      }
      images.push(rec)
    }

    const dataUrl = sheet.toDataURL('image/png')
    const base64 = dataUrl.slice(dataUrl.indexOf(',') + 1)
    const tEnd = (typeof performance !== 'undefined' ? performance.now() : Date.now())
    return {
      ok: true,
      png: base64,
      width: sheet.width,
      height: sheet.height,
      bytes: Math.round(base64.length * 0.75),
      cols, rows, cell: cellPx, gap,
      count: files.length,
      loaded: images.filter((x) => x.ok).length,
      images,
      elapsed_ms: +(tEnd - tStart).toFixed(1),
    }
  }

  handlers['render.texture'] = (params = {}) => {
    ensureProject()
    const tex = findTexture(params.texture)
    if (!tex) throw err('INVALID_REFERENCE', `texture not found: ${params.texture}`, { code: 'INVALID_REFERENCE' })
    const scale = Math.min(16, Math.max(1, Number(params.scale) || 8))
    const region = params.region ?? [0, 0, tex.width - 1, tex.height - 1]
    const sw = Math.max(1, region[2] - region[0] + 1), sh = Math.max(1, region[3] - region[1] + 1)
    const c = document.createElement('canvas')
    c.width = sw * scale; c.height = sh * scale
    const ctx = c.getContext('2d')
    ctx.imageSmoothingEnabled = false
    // 透明区域垫一层深色底，否则拼图/观察时"透明=黑"会误判为缺像素
    if (colorOk(params.background)) {
      ctx.fillStyle = params.background
      ctx.fillRect(0, 0, c.width, c.height)
    }
    ctx.drawImage(tex.canvas, region[0], region[1], sw, sh, 0, 0, c.width, c.height)
    const dataUrl = c.toDataURL('image/png')

    // inline=true：不落盘、直接回 base64（供 bb_render_texture 拼图与"精修核对"用）
    if (params.inline === true) {
      const base64 = dataUrl.slice(dataUrl.indexOf(',') + 1)
      return {
        ok: true,
        inline: true,
        texture: tex.name,
        png: base64,
        width: c.width, height: c.height,
        bytes: Math.round(base64.length * 0.75),
        scale, region,
        revision: state.revision,
      }
    }

    const dir = workspacePath('artifacts', 'texture-previews')
    ensureDir(dir)
    const file = `${dir}${dir.includes('\\') ? '\\' : '/'}${tex.name}_x${scale}.png`
    writeBlockbenchFile(file, dataUrl, 'image')
    return { revision: state.revision, path: `artifacts/texture-previews/${tex.name}_x${scale}.png`, workspace_path: file, width: c.width, height: c.height, scale, region }
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
    const base = `r${String(revision).padStart(4, '0')}`
    const fileName = `${base}.bbmodel`
    const dir = workspacePath('checkpoints')
    ensureDir(dir)
    // .bbmodel 的 textures[].source 是 compile 时的快照来源；画布编辑后 source 可能是旧值，
    // 先同步回 canvas，再 compile，checkpoint 内嵌的就是当前像素（B1 根因修复）。
    for (const tex of Texture.all) {
      try { if (tex.canvas?.toDataURL) tex.source = tex.canvas.toDataURL('image/png') } catch { /* ignore */ }
    }
    const content = Codecs.project.compile()
    const file = `${dir}${dir.includes('\\') ? '\\' : '/'}${fileName}`
    writeBlockbenchFile(file, content, 'text')
    // 贴图快照：.bbmodel 只存几何，checkpoint 必须额外保存画布位图，否则恢复后贴图退回磁盘旧版
    const textureDir = joinPath(dir, `${base}.textures`)
    ensureDir(textureDir)
    const textureSnapshots = []
    const nameCounts = new Map()
    for (const tex of Texture.all) {
      try {
        const owner = ModelProject.all.find((p) => Array.isArray(p.textures) && p.textures.includes(tex)) ?? Project
        const ownerName = String(owner?.name ?? 'main').replace(/[^a-zA-Z0-9_.-]/g, '_')
        const texName = String(tex.name || 'texture').replace(/[^a-zA-Z0-9_.-]/g, '_')
        const ordinal = nameCounts.get(texName) ?? 0
        nameCounts.set(texName, ordinal + 1)
        const uuidShort = String(tex.uuid || '').replace(/[^a-zA-Z0-9]/g, '').slice(0, 8) || `${ordinal}`
        const safeName = `${ownerName}-${ordinal}-${texName}-${uuidShort}.png`
        const dataUrl = tex.canvas.toDataURL('image/png')
        writeBlockbenchFile(joinPath(textureDir, safeName), dataUrl, 'image')
        textureSnapshots.push({ id: tex.uuid, name: tex.name, ordinal, project: owner?.name ?? 'main', file: safeName, size: [tex.width, tex.height], bytes: Math.round(dataUrl.length * 0.75) })
      } catch (error) { console.warn('[bb-agent] checkpoint texture snapshot failed', tex.name, error?.message) }
    }
    // 第一人称手臂是独立 ModelProject，单独快照；否则 restore 会退回磁盘旧版
    let armCheckpoint = null
    try {
      const armProject = state.project?.armProject
      if (armProject && ModelProject.all.includes(armProject)) {
        const mainProject = state.project?.mainProject ?? Project
        armProject.select?.()
        for (const tex of Texture.all) {
          try { if (tex.canvas?.toDataURL) tex.source = tex.canvas.toDataURL('image/png') } catch { /* ignore */ }
        }
        const armContent = Codecs.project.compile()
        armProject.select?.()
        const armFile = `${base}.arm.bbmodel`
        writeBlockbenchFile(joinPath(dir, armFile), armContent, 'text')
        armCheckpoint = `checkpoints/${armFile}`
        mainProject?.select?.()
      }
    } catch (error) { console.warn('[bb-agent] checkpoint arm snapshot failed', error?.message) }
    const meta = {
      revision,
      label: params.label ?? '',
      note: params.note ?? '',
      created_at: new Date().toISOString(),
      bytes: content.length,
      bones: Group.all.length,
      cubes: Cube.all.length,
      textures: Texture.all.length,
      texture_snapshots: textureSnapshots,
      arm_checkpoint: armCheckpoint,
      export_path: Project.export_path || '',
      project_name: Project.name || '',
      pack_dir: state.project?.pack_dir || '',
    }
    writeBlockbenchFile(file.replace(/\.bbmodel$/, '.meta.json'), JSON.stringify(meta, null, 2), 'text')
    return { revision, checkpoint: `checkpoints/${fileName}`, bytes: content.length, label: meta.label, textures: textureSnapshots.length, arm: !!armCheckpoint }
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
    const packDir = normalizePackDir(params.pack_dir || 'pack')
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
    const packDir = normalizePackDir(state.project?.pack_dir || workspacePath('pack'))
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
    const packDir = normalizePackDir(state.project?.pack_dir || workspacePath('pack'))
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
    state.dirtyAnimationNames.add(anim.name)
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
            const oldName = anim.name
            if (op.name) anim.name = op.name
            if (typeof op.loop === 'string' && ['once', 'loop', 'hold'].includes(op.loop)) anim.loop = op.loop
            else if (typeof op.loop === 'boolean') anim.loop = op.loop ? 'loop' : 'once'
            if (typeof op.length === 'number') { anim.length = op.length; anim.setLength(op.length) }
            changed.push({ animation: anim.name, op: 'update' })
            if (anim.path) dirtyAnimPaths.add(anim.path)
            if (op.name && oldName !== anim.name) {
              if (anim.path) {
                if (!state.deletedAnimations.has(anim.path)) state.deletedAnimations.set(anim.path, new Set())
                state.deletedAnimations.get(anim.path).add(oldName)
              }
            }
            state.dirtyAnimationNames.add(anim.name)
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
            state.dirtyAnimationNames.add(anim.name)
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
            state.dirtyAnimationNames.add(anim.name)
            break
          }
          case 'delete_animation': {
            const anim = findAnimation(op.animation)
            if (!anim) throw err('INVALID_REFERENCE', `animation not found: ${op.animation}`, { code: 'INVALID_REFERENCE' })
            if (anim.path) {
              dirtyAnimPaths.add(anim.path)
              if (!state.deletedAnimations.has(anim.path)) state.deletedAnimations.set(anim.path, new Set())
              state.deletedAnimations.get(anim.path).add(anim.name)
            }
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
    const packDir = normalizePackDir(state.project?.pack_dir || workspacePath('pack'))
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
    // 载入 checkpoint 会触发 Blockbench 的 finished_edit；这不是用户编辑，屏蔽后避免把全部动画标脏
    state.suppressUserEdit = true
    setTimeout(() => { state.suppressUserEdit = false }, 2000)
    if (params.confirm !== true) throw err('INVALID_OPERATION', 'restore requires confirm:true (destructive)', { code: 'INVALID_OPERATION' })
    const packDir = normalizePackDir(state.project?.pack_dir || workspacePath('pack'))
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
    project.select?.()
    if (meta.export_path) project.export_path = meta.export_path
    else if (state.project?.ysmJson) project.export_path = packAbsolute(packDir, state.project.ysmJson.files?.player?.model?.main ?? 'models/main.json')
    const ysmJson = state.project?.ysmJson
    // .bbmodel 已内嵌贴图 source（checkpoint 前已同步 canvas）；sidecar 仅作为辅助证据，不再覆盖画布
    const textureRestore = { restored: 0, created: 0, missing: 0, embedded: true }
    let armLoaded = false
    let armError = null
    let armFromCheckpoint = false
    if (ysmJson) {
      try {
        // arm 是独立 tab。checkpoint 有 arm 快照时用 .bbmodel 直接加载（保留格式），失败再回退磁盘 arm.json
        const armSnapshot = meta.arm_checkpoint ? joinPath(workspacePath('checkpoints'), pathModule.basename(meta.arm_checkpoint)) : null
        let arm = null
        if (armSnapshot && nodeFs?.existsSync?.(armSnapshot)) {
          try {
            arm = await loadArmFromSnapshot(armSnapshot, packDir, ysmJson)
            armFromCheckpoint = !!arm
          } catch (error) {
            console.warn('[bb-agent] arm snapshot load failed, fallback disk', error?.message)
            arm = null
          }
        }
        if (!arm) arm = await loadArmFromDisk(packDir, ysmJson)
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
    // checkpoint 恢复后，贴图已从快照恢复，但仍需让保存路径写回磁盘
    for (const anim of Animation.all) if (anim.path) state.dirtyAnimations.add(anim.path)
    for (const controller of (window.AnimationController?.all ?? [])) if (controller.path) state.dirtyControllers.add(controller.path)
    for (const tex of Texture.all) state.dirtyTextures.add(tex.uuid)
    const previousRevision = state.revision
    const nextRevision = bump('restore', [])
    return {
      restored_from: previousRevision, revision: nextRevision,
      summary: { bones: Group.all.length, cubes: Cube.all.length, textures: Texture.all.length },
      textures_restored: textureRestore.restored,
      arm_loaded: armLoaded, arm_error: armError, arm_from_checkpoint: armFromCheckpoint,
      debug: { project_open: !!Project, active: Project?.name ?? null, main: project?.name ?? null, main_open: ModelProject.all.includes(project) },
      warning: '当前未保存改动已丢弃；checkpoint 已内嵌贴图；arm 从磁盘重载（非 checkpoint 状态）',
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
        if (state.agentEditing || state.suppressUserEdit) return
        state.userEditing = true
        state.revision += 1
        for (const anim of Animation.all) if (anim.path) state.dirtyAnimations.add(anim.path)
        for (const anim of Animation.all) state.dirtyAnimationNames.add(anim.name)
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



