// M0 renderer self-test body（由 agent/main.js 以 async IIFE 执行）
// 目标：加载真实 YSM 默认模型 + 贴图 → 5 机位离屏渲染 → 50 次稳定性 → show/hide → 输出指标。
// 约束：必须返回可序列化对象；PNG/JSON 通过 Blockbench.writeFile 落盘到 cfg.selfTest.outDir。

const cfg = window.__BB_AGENT__
const selfTest = cfg?.selfTest
if (!selfTest?.packDir || !selfTest?.outDir) throw new Error('selfTest config missing')
const { packDir, outDir } = selfTest
const SIZE = [768, 768]
const VIEWS = ['front', 'back', 'left', 'right', 'iso_fr']
const RESULTS = { ok: false, size: SIZE, views: [], timings: {}, project: {}, gl: {}, logs: [] }
const log = (...args) => {
  const line = args.map((a) => (typeof a === 'string' ? a : JSON.stringify(a))).join(' ')
  RESULTS.logs.push(line)
  console.log('[m0]', line)
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const winPath = (...parts) => parts.join('\\').replace(/\\+/g, '\\')

function readFileAsync(filePath, readtype) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`readFile timeout: ${filePath}`)), 15000)
    try {
      Blockbench.readFile([filePath], { readtype, errorbox: false }, (files) => {
        clearTimeout(timer)
        resolve(files?.[0] ?? null)
      })
    } catch (error) {
      clearTimeout(timer)
      reject(error)
    }
  })
}
async function writeFileAsync(filePath, content, savetype) {
  return Blockbench.writeFile(filePath, { content, savetype: savetype ?? 'text' })
}

const VIEW_DIRS = {
  front: [0, 0, -1], back: [0, 0, 1], left: [-1, 0, 0], right: [1, 0, 0],
  top: [0, 1, 0.0001], bottom: [0, -1, 0.0001],
  iso_fr: [1, 0.55, -1], iso_fl: [-1, 0.55, -1],
}

function modelBounds() {
  Canvas.scene.updateMatrixWorld(true)
  const box = new THREE.Box3()
  for (const cube of Cube.all) {
    if (cube.mesh) box.expandByObject(cube.mesh)
  }
  if (box.isEmpty()) return null
  const center = box.getCenter(new THREE.Vector3())
  const size = box.getSize(new THREE.Vector3())
  return { center: center.toArray(), size: size.toArray() }
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
  const zoom = Math.min(2 * (w / 80) / needW, 2 * (h / 80) / needH)
  preview.camera.zoom = zoom
  preview.camera.updateProjectionMatrix()
}

function renderView(view, size = SIZE, bounds = null) {
  const preview = window.MediaPreview
  if (!preview) throw new Error('MediaPreview unavailable')
  preview.resize(size[0], size[1])
  const b = bounds ?? modelBounds()
  if (!b) throw new Error('model bounds empty')
  fitCamera(preview, view, b)
  const prevBg = Canvas.scene.background
  Canvas.scene.background = null
  try {
    preview.renderer?.setClearAlpha?.(0)
    Canvas.withoutGizmos(() => preview.render())
    const dataUrl = preview.canvas.toDataURL('image/png')
    return { dataUrl, canvas: preview.canvas, metrics: sampleCanvas(preview.canvas), bounds: b }
  } finally {
    Canvas.scene.background = prevBg
  }
}

function sampleCanvas(canvas) {
  const c = document.createElement('canvas')
  c.width = 64; c.height = 64
  const ctx = c.getContext('2d')
  ctx.drawImage(canvas, 0, 0, 64, 64)
  const data = ctx.getImageData(0, 0, 64, 64).data
  let nonAlpha = 0, sum = 0, sq = 0
  const n = 64 * 64
  for (let i = 0; i < data.length; i += 4) {
    if (data[i + 3] > 0) nonAlpha++
    const lum = 0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2]
    sum += lum; sq += lum * lum
  }
  const mean = sum / n
  return { alpha_ratio: nonAlpha / n, luminance_mean: mean, luminance_variance: sq / n - mean * mean }
}



try {
  log('packDir', packDir)
  // 1) 加载 YSM 默认主模型
  const t0 = performance.now()
  const modelFile = await readFileAsync(winPath(packDir, 'models', 'main.json'), 'text')
  if (!modelFile) throw new Error('main.json read failed')
  loadModelFile(modelFile)
  await sleep(300)
  if (!Project || Project === 0) throw new Error('project not created by loadModelFile')
  const loadMs = performance.now() - t0
  RESULTS.timings.load_ms = Math.round(loadMs)
  log(`model loaded in ${Math.round(loadMs)}ms: bones=${Group.all.length}, cubes=${Cube.all.length}`)

  // 2) 加载默认贴图并绑定到所有 cube 面（bedrock 单贴图格式）
  const texFile = await readFileAsync(winPath(packDir, 'textures', 'default.png'), 'image')
  if (!texFile) throw new Error('default.png read failed')
  const tex = new Texture().fromFile(texFile).add()
  let waited = 0
  while ((!tex.width || tex.width === 0) && waited < 3000) { await sleep(50); waited += 50 }
  tex.select?.()
  if (typeof Texture !== 'undefined') Texture.selected = tex
  for (const cube of Cube.all) {
    for (const faceName of Object.keys(cube.faces ?? {})) {
      if (cube.faces[faceName]) cube.faces[faceName].texture = tex.uuid
    }
  }
  Canvas.updateAllFaces?.()
  Canvas.updateAll?.()
  await sleep(100)
  RESULTS.project = {
    bones: Group.all.length,
    cubes: Cube.all.length,
    textures: Texture.all.length,
    texture_size: [tex.width, tex.height],
    animations: (window.Animation?.all ?? []).length,
    bounds: modelBounds(),
  }
  const bounds = RESULTS.project.bounds
  log('project', RESULTS.project)

  // 首次离屏渲染存在一次空帧（shader/几何/矩阵惰性初始化），先做一次 warm-up 丢弃
  {
    const preview = window.MediaPreview
    preview.resize(SIZE[0], SIZE[1])
    fitCamera(preview, 'front', bounds)
    preview.render()
  }

  // 3) 5 机位渲染 + PNG 落盘
  const t1 = performance.now()
  for (const view of VIEWS) {
    const t = performance.now()
    const out = renderView(view, SIZE, bounds)
    const cam = window.MediaPreview.camera
    out.camera_debug = {
      position: cam.position.toArray().map((n) => Number(n.toFixed(2))),
      target: window.MediaPreview.controls.target.toArray().map((n) => Number(n.toFixed(2))),
      zoom: Number(cam.zoom.toFixed(4)),
      isOrtho: window.MediaPreview.isOrtho,
    }
    const file = `${view}_${SIZE[0]}.png`
    await writeFileAsync(winPath(outDir, file), out.dataUrl, 'image')
    RESULTS.views.push({
      view, file, width: SIZE[0], height: SIZE[1],
      bytes: Math.round(out.dataUrl.length * 0.75),
      elapsed_ms: Math.round(performance.now() - t),
      ...out.metrics,
      camera: out.camera_debug,
    })
    log(`render ${view} ${Math.round(performance.now() - t)}ms alpha=${out.metrics.alpha_ratio.toFixed(3)} var=${out.metrics.luminance_variance.toFixed(1)}`)
  }
  RESULTS.timings.render_views_ms = Math.round(performance.now() - t1)

  // 4) 50 次稳定性
  const loops = []
  for (let i = 0; i < 50; i++) {
    const t = performance.now()
    renderView('front', SIZE, bounds)
    loops.push(performance.now() - t)
  }
  loops.sort((a, b) => a - b)
  RESULTS.timings.loop_50 = {
    count: loops.length,
    p50_ms: Math.round(loops[Math.floor(loops.length * 0.5)]),
    p95_ms: Math.round(loops[Math.floor(loops.length * 0.95)]),
    max_ms: Math.round(loops[loops.length - 1]),
  }
  log('50 loops', RESULTS.timings.loop_50)

  // 5) show/hide 往返后仍可渲染
  const t2 = performance.now()
  const windowApi = window.__BB_AGENT_API__
  if (!windowApi?.showWindow) throw new Error('window control API unavailable')
  await windowApi.showWindow()
  await sleep(250)
  await windowApi.hideWindow()
  await sleep(250)
  const afterShowHide = renderView('front', SIZE, bounds)
  RESULTS.timings.show_hide_ms = Math.round(performance.now() - t2)
  RESULTS.show_hide_ok = afterShowHide.metrics.alpha_ratio > 0.005
  log(`show/hide ok=${RESULTS.show_hide_ok} in ${RESULTS.timings.show_hide_ms}ms`)

  // 6) WebGL 信息（放在 show/hide 之前采集，避免窗口状态影响）
  try {
    const gl = window.MediaPreview.renderer.getContext()
    const dbg = gl.getExtension('WEBGL_debug_renderer_info')
    RESULTS.gl = {
      version: gl.getParameter(gl.VERSION),
      renderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
      vendor: dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR),
      antialias: gl.getContextAttributes?.().antialias ?? null,
    }
  } catch (error) { RESULTS.gl = { error: String(error?.message ?? error) } }

  RESULTS.ok = RESULTS.views.every((v) => v.alpha_ratio > 0.005 && v.luminance_variance > 5) && RESULTS.show_hide_ok
  RESULTS.timings.total_ms = Math.round(performance.now() - t0)
} catch (error) {
  RESULTS.ok = false
  RESULTS.error = String(error?.stack ?? error?.message ?? error)
  log('ERROR', RESULTS.error)
}

await writeFileAsync(winPath(outDir, 'm0-result.json'), JSON.stringify(RESULTS, null, 2))
return RESULTS
