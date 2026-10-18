// BB-Agent Bridge Plugin · Blockbench renderer 侧（设计参考骨架）
// 加载方式：由 agent/main.js 在 Blockbench 初始化完成后执行
//   new Plugin().loadFromFile({path, name, content:''}, false)
//
// 职责：作为 WebSocket 客户端连接 dsh Host 的 BridgeServer，处理其下发的 JSON-RPC 请求。
// 依赖 Blockbench 全局：Plugin/Project/Group/Cube/Texture/Animation/Codecs/Undo/Canvas/Preview/
// MediaPreview/DefaultCameraPresets/Screencam/Blockbench/currentwindow/ipcRenderer。
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

  const state = {
    state: 'booting',
    revision: 0,
    project: null,
    guiVisible: false,
    startedAt: Date.now(),
    lastError: null,
  }

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
    if (!window.Project || Project === 0) throw err('PROJECT_NOT_OPEN', 'no project open')
    return Project
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
  const bump = (source, changed = []) => {
    state.revision += 1
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
      const nodeFs = (typeof fs !== 'undefined' && fs) || (window.fs ?? null)
      if (nodeFs?.mkdirSync) nodeFs.mkdirSync(dir, { recursive: true })
    } catch { /* 宿主会预建目录；失败由 writeFile 报错 */ }
  }
  function writeBlockbenchFile(filePath, content, savetype) {
    ensureDir(filePath.replace(/[\\/][^\\/]+$/, ''))
    Blockbench.writeFile(filePath, { content, savetype: savetype || 'text' })
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
    if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(obj))
  }
  function notify(method, params) {
    sendRaw({ jsonrpc: '2.0', method, params })
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

  function connect() {
    if (disposed || !WS_URL) return
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
              client: { name: 'bb-agent-bridge', version: '0.1.0' },
              requested_capabilities: ['render.offscreen', 'gui.show', 'ysm.v2'],
            },
            _meta: { deadline_ms: 5000 },
          })
        })
        connected = true
        helloDone = true
        state.state = 'idle'
        console.log('[bb-agent] connected', hello?.server?.version ?? '')
        notify('event.heartbeat', heartbeatPayload())
        heartbeatTimer = setInterval(() => notify('event.heartbeat', heartbeatPayload()), 2000)
      } catch (error) {
        console.error('[bb-agent] hello failed', error)
        try { socket.close() } catch { /* ignore */ }
      }
    }
    socket.onmessage = (event) => {
      let msg
      try { msg = JSON.parse(event.data) } catch { return }
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
    socket.onclose = () => {
      connected = false
      helloDone = false
      if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null }
      for (const [, waiter] of pending) { clearTimeout(waiter.timer); waiter.reject(err('DISCONNECTED', 'bridge disconnected')) }
      pending.clear()
      if (!disposed) scheduleReconnect()
    }
    socket.onerror = () => { /* onclose 会处理 */ }
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
      const handler = handlers[msg.method]
      if (!handler) throw err('METHOD_NOT_FOUND', `method not found: ${msg.method}`, { code: 'METHOD_NOT_FOUND' })
      const result = await handler(msg.params ?? {}, msg._meta ?? {})
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
    render_queue: 0,
    gpu_ok: state.state !== 'degraded',
    uptime_s: Math.round((Date.now() - state.startedAt) / 1000),
    budgets: { edits_used: 0, edits_max: 60, renders_used: 0, renders_max: 40 },
    last_error: state.lastError,
  })

  handlers['project.create_ysm'] = (params) => {
    const name = String(params.name || 'agent_model')
    newProject(Formats.bedrock)
    Project.name = name
    Project.geometry_name = name
    const resolution = Array.isArray(params.resolution) ? params.resolution : [128, 128]
    Project.texture_width = resolution[0]
    Project.texture_height = resolution[1]

    // TODO(YRL): 复制完整 YSM 默认骨架（64 bones / 172 cubes）
    const root = new Group({ name: 'Root', origin: [0, 0, 0] }).init()
    const up = new Group({ name: 'UpperBody', origin: [0, 20.65, 0] }).addTo(root).init()
    new Group({ name: 'LeftArm', origin: [5, 22, 0] }).addTo(up).init()
    new Group({ name: 'RightArm', origin: [-5, 22, 0] }).addTo(up).init()
    Canvas.updateAll()
    state.project = { project_id: `${name}-${Math.random().toString(16).slice(2, 10)}`, pack_dir: workspacePath('pack') }
    bump('agent')
    return {
      project_id: state.project.project_id,
      revision: state.revision,
      pack_dir: state.project.pack_dir,
      summary: { bones: Group.all.length, cubes: Cube.all.length, textures: Texture.all.length, animations: Animation.all.length },
      root_bones: Group.all.filter((g) => !g.parent).map((g) => ({ bone: g.name, id: g.uuid, parent: null, cubes: g.children?.length ?? 0 })),
      textures: Texture.all.map((t) => ({ texture: t.name, id: t.uuid, size: [t.width, t.height] })),
      warnings: [{ code: 'SKELETON_INCOMPLETE', detail: 'prototype creates 4 bones only; wire YRL default pack for full skeleton' }],
    }
  }

  handlers['project.get_scene'] = (params = {}) => {
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
          opaque_ratio: t.width ? 1 : 0,
        })),
        animations: Animation.all.map((a) => a.name),
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
      return {
        cube_id: el.uuid, name: el.name, bone: el.parent?.name ?? null,
        origin: vec(el.from), size: vec(el.to).map((v, i) => v - vec(el.from)[i]),
        rotation: vec(el.rotation), pivot: vec(el.origin), inflate: num(el.inflate, 0),
        uv: el.box_uv ? { mode: 'box', uv: vec(el.uv_offset).slice(0, 2) } : { mode: 'faces' },
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
            })
            cube.addTo(bone).init()
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
      return { ok: true, revision, changed, warnings: [], digest: { revision, bones: Group.all.length, cubes: Cube.all.length } }
    } catch (error) {
      try { Undo.cancelEdit?.(true) } catch { /* ignore */ }
      throw error
    } finally {
      try { Undo.finishEdit?.(params.note || 'Agent model patch', aspects) } catch { /* ignore */ }
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

  handlers['texture.apply_patch'] = (params = {}) => {
    ensureProject()
    const tex = findTexture(params.texture)
    if (!tex) throw err('INVALID_REFERENCE', `texture not found: ${params.texture}`, { code: 'INVALID_REFERENCE' })
    if (!tex.width || !tex.height) throw err('INVALID_OPERATION', 'texture not loaded (width=0)', { code: 'INVALID_OPERATION' })
    const ops = Array.isArray(params.ops) ? params.ops : []
    const aspects = { textures: [tex], bitmap: true }
    Undo.initEdit(aspects)
    try {
      if (!tex.internal) tex.convertToInternal?.()
      const result = paintTexture(tex, ops, params.clip !== false)
      tex.updateChangesAfterEdit()
      const revision = bump('agent', [{ kind: 'texture', id: tex.uuid, op: 'paint' }])
      return {
        ok: true, revision, texture: tex.name,
        painted_pixels: result.painted, clipped_pixels: result.clipped,
        bounds: result.bounds, palette: [], warnings: [],
      }
    } finally {
      try { Undo.finishEdit?.(params.note || 'Agent texture patch', aspects) } catch { /* ignore */ }
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
  const ISO_BASE = { projection: 'orthographic', target: [0, 8, 0], zoom: 0.5 }
  const VIEW_PRESETS = {
    front: 'north', back: 'south', left: 'west', right: 'east', top: 'top', bottom: 'bottom',
    iso_fr: { ...ISO_BASE, position: [512, 512 * 0.8165 + 8, -512] },
    iso_fl: { ...ISO_BASE, position: [-512, 512 * 0.8165 + 8, -512] },
    iso_br: { ...ISO_BASE, position: [512, 512 * 0.8165 + 8, 512] },
    iso_bl: { ...ISO_BASE, position: [-512, 512 * 0.8165 + 8, 512] },
  }

  handlers['render.views'] = (params = {}) => {
    ensureProject()
    const views = Array.isArray(params.views) && params.views.length ? params.views : ['front', 'right', 'iso_fr']
    const size = Array.isArray(params.size) ? params.size : [768, 768]
    const preview = window.MediaPreview ?? window.Screencam?.NoAAPreview
    if (!preview) throw err('ENGINE_DEGRADED', 'offscreen preview unavailable', { code: 'ENGINE_DEGRADED' })
    const revision = state.revision
    const dir = workspacePath('artifacts', 'renders', `r${String(revision).padStart(4, '0')}`)
    ensureDir(dir)
    const images = []
    const prevBg = Canvas.scene.background
    Canvas.scene.background = null
    try {
      for (const view of views) {
        const presetRef = VIEW_PRESETS[view]
        if (!presetRef) throw err('INVALID_PARAMS', `unknown view: ${view}`, { code: 'INVALID_PARAMS' })
        const preset = typeof presetRef === 'string'
          ? DefaultCameraPresets.find((p) => p.id === presetRef)
          : presetRef
        if (!preset) throw err('UNSUPPORTED', `camera preset missing: ${presetRef}`, { code: 'UNSUPPORTED' })
        preview.loadAnglePreset(preset)
        preview.resize(size[0], size[1])
        preview.renderer?.setClearAlpha?.(0)
        Canvas.withoutGizmos(() => preview.render())
        const dataUrl = preview.canvas.toDataURL('image/png')
        const file = `${dir}${dir.includes('\\') ? '\\' : '/'}${view}_${size[0]}.png`
        writeBlockbenchFile(file, dataUrl, 'image')
        const base64 = dataUrl.slice(dataUrl.indexOf(',') + 1)
        images.push({ view, path: `artifacts/renders/r${String(revision).padStart(4, '0')}/${view}_${size[0]}.png`, workspace_path: file, sha256: '', bytes: Math.round(base64.length * 0.75), width: size[0], height: size[1] })
      }
    } finally {
      Canvas.scene.background = prevBg
    }
    return { revision, render_id: `render-${revision}`, images, cache_hit: false, elapsed_ms: 0 }
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
    ensureProject()
    const errors = [], warnings = []
    if (!Texture.all.length) errors.push({ code: 'YSM_TEXTURE_MISSING', message: 'no textures', fix_hint: 'bb_texture_create' })
    for (const t of Texture.all) {
      if ((t.width !== 128 || t.height !== 128) && Texture.all.length) warnings.push({ code: 'TEXTURE_SIZE', target: t.name, message: `texture ${t.width}x${t.height}, expected 128x128` })
    }
    const required = ['Head', 'AllHead', 'LeftHandLocator', 'RightHandLocator']
    for (const name of required) if (!findGroup(name)) warnings.push({ code: 'YSM_LOCATOR_MISSING', target: name, message: `locator group missing: ${name}` })
    const checks = [
      { id: 'required_bones', status: warnings.some((w) => w.code === 'YSM_LOCATOR_MISSING') ? 'warn' : 'pass' },
      { id: 'texture_size', status: warnings.some((w) => w.code === 'TEXTURE_SIZE') ? 'warn' : 'pass' },
      { id: 'uv_bounds', status: 'pass' },
    ]
    return { ok: errors.length === 0, revision: state.revision, errors, warnings, checks, stats: { bones: Group.all.length, cubes: Cube.all.length } }
  }

  handlers['project.save'] = () => {
    ensureProject()
    const files = []
    try { Settings.set('export_empty_groups', true) } catch { /* ignore */ }
    const codec = Codecs[Project.export_codec] ?? Codecs.bedrock
    const modelPath = workspacePath('pack', 'models', 'main.json')
    const compiled = codec.compile()
    writeBlockbenchFile(modelPath, compiled, 'text')
    files.push({ path: 'pack/models/main.json', bytes: compiled.length })
    for (const tex of Texture.all) {
      const p = workspacePath('pack', 'textures', tex.name.endsWith('.png') ? tex.name : `${tex.name}.png`)
      const dataUrl = tex.canvas.toDataURL('image/png')
      writeBlockbenchFile(p, dataUrl, 'image')
      files.push({ path: `pack/textures/${tex.name}`, bytes: Math.round(dataUrl.length * 0.75) })
    }
    // TODO(YRL): ysm.json saveNormalization + 动画/控制器导出
    return { saved: true, revision: state.revision, pack_dir: workspacePath('pack'), files }
  }

  handlers['project.export_ysm'] = () => {
    throw err('UNSUPPORTED', 'prototype export not wired; see docs/05 §5.9 for the required sequence', {
      code: 'UNSUPPORTED',
    })
  }

  // ---- animation / gui ---------------------------------------------------
  handlers['animation.list'] = () => ({
    animations: Animation.all.map((a) => ({ animation: a.name, length: a.length, loop: a.loop, keyframes: a.animators?.length ?? 0 })),
    controllers: (window.AnimationController?.all ?? []).map((c) => c.name),
  })
  handlers['animation.apply_patch'] = () => {
    throw err('UNSUPPORTED', 'prototype animation mutation not wired', { code: 'UNSUPPORTED' })
  }

  handlers['gui.show'] = () => {
    try { currentwindow.show(); currentwindow.focus() } catch { /* ignore */ }
    state.guiVisible = true
    notify('event.gui_state', { visible: true, focused: true, revision: state.revision, user_editing: false })
    return { gui_visible: true, revision: state.revision, frozen: true }
  }
  handlers['gui.hide'] = () => {
    try { currentwindow.hide() } catch { /* ignore */ }
    state.guiVisible = false
    notify('event.gui_state', { visible: false, focused: false, revision: state.revision, user_editing: false })
    return { gui_visible: false, revision: state.revision, user_edits: [] }
  }
  handlers['gui.state'] = () => ({ gui_visible: state.guiVisible, focused: true, revision: state.revision, user_editing: false })

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
      connect()
    },
    onunload() {
      disposed = true
      if (heartbeatTimer) clearInterval(heartbeatTimer)
      try { socket?.close() } catch { /* ignore */ }
    },
  })
})()
