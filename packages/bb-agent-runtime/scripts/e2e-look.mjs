// 视口实时反馈 E2E 验证（docs/07 S1/S2/S3）
// 用法：node packages/bb-agent-runtime/scripts/e2e-look.mjs [--keep]
//
// 真实验证项：
//   L1  camera.get 能读到相机位姿
//   L2  render.preview 不落盘、返回 base64、耗时
//   L3  render.sheet  多格合成一张图（自动附图的底层）
//   L4  render.sheet  转台 8 角度
//   L5  render.texture_sheet 贴图像素放大
//   L6  render.sheet  动画时间点采样（若项目内有动画）
//   L7  产物 PNG 可解码、格子数一致、非全黑

import fs from 'node:fs'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { randomBytes } from 'node:crypto'
import { createWsServer } from '../../dsh-blockbench-agent/lib/ws-server.js'
import { imageTokens } from '../../dsh-blockbench-agent/lib/viewsheet.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..')
const APP = path.join(REPO_ROOT, 'dist', 'bb-agent-app')
const WORKSPACE = path.join(REPO_ROOT, 'workspace', '_e2e-look')
const ELECTRON = path.join(REPO_ROOT, 'vendor', 'blockbench', 'node_modules', 'electron', 'dist',
  process.platform === 'win32' ? 'electron.exe' : 'electron')
const KEEP = process.argv.includes('--keep')

const results = []
const check = (name, ok, detail) => {
  results.push({ name, ok, detail })
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  ' + JSON.stringify(detail) : ''}`)
}

/** 用最小 PNG 头校验 + 粗略解码校验（不引入依赖）。 */
function pngInfo(buf) {
  if (buf.length < 24) return null
  const sig = buf.subarray(0, 8).toString('hex')
  if (sig !== '89504e470d0a1a0a') return null
  // IHDR 在偏移 8：4 字节长度 + 'IHDR' + width + height
  const width = buf.readUInt32BE(16)
  const height = buf.readUInt32BE(20)
  return { width, height, bytes: buf.length }
}

/** 粗略判断是否"全黑/全空"：统计 PNG 原始字节的熵（压缩后全黑会非常小）。 */
function looksEmpty(buf) {
  return buf.length < 800
}

async function main() {
  fs.rmSync(WORKSPACE, { recursive: true, force: true })
  fs.mkdirSync(path.join(WORKSPACE, 'logs'), { recursive: true })
  fs.mkdirSync(path.join(WORKSPACE, 'out'), { recursive: true })

  const token = randomBytes(24).toString('base64url')
  let signalConnected
  const connected = new Promise((res) => { signalConnected = res })
  const server = createWsServer({
    token,
    defaultTimeoutMs: 180000,
    onConnection: () => signalConnected(true),
    methods: {
      'system.hello': () => ({
        protocol: 'bb-agent/1',
        transport: 'ws',
        server: { name: 'bb-agent-runtime', version: 'e2e-look', blockbench: '5.2.2' },
        capabilities: { render: { offscreen: true, transparent: true }, gui: { show: true }, eval: false },
        limits: { max_message_bytes: 8388608, max_batch: 64, max_patch_ops: 4096, max_inflight: 8 },
        session: { project_id: null, revision: 0, state: 'idle' },
      }),
    },
  })
  const { port } = await server.listen(0)
  const url = `ws://127.0.0.1:${port}/bb-agent/v1`


  const env = { ...process.env, ELECTRON_ENABLE_LOGGING: '1' }
  delete env.ELECTRON_RUN_AS_NODE

  const child = spawn(ELECTRON, [
    APP,
    `--workspace=${WORKSPACE}`,
    `--plugin=${path.join(APP, 'agent', 'bb-agent-bridge.js')}`,
    `--user-data=${path.join(WORKSPACE, '.bb', 'userdata')}`,
    `--rpc-url=${url}`,
    `--token=${token}`,
    '--transport=ws',
  ], { cwd: APP, windowsHide: true, env })

  const logStream = fs.createWriteStream(path.join(WORKSPACE, 'logs', 'electron.log'), { flags: 'a' })
  child.stdout.on('data', (d) => logStream.write(d))
  child.stderr.on('data', (d) => logStream.write(d))

  const cleanup = () => {
    try { child.kill('SIGKILL') } catch { /* ignore */ }
    try { server.close?.() } catch { /* ignore */ }
    logStream.end()
  }

  const hardTimeout = setTimeout(() => {
    console.error('[e2e-look] TIMEOUT')
    cleanup()
    process.exit(2)
  }, 300000)
  hardTimeout.unref?.()

  await connected
  console.log('[e2e-look] BAE connected')

  const call = (m, p, t = 120000) => server.request(m, p, { timeoutMs: t })

  /**
   * 带重连的调用：bridge 在极端情况下会被 ws-server 以 1009（消息过大）关闭并自动重连，
   * 这里把"连接关闭"当成可重试错误，避免一次断连毁掉整轮验证。
   */
  async function callRetry(m, p, t = 120000, tries = 3) {
    let last = null
    for (let i = 0; i < tries; i++) {
      try {
        return await call(m, p, t)
      } catch (e) {
        last = e
        const msg = String(e?.message ?? e)
        if (!/connection closed|not connected|DISCONNECTED/i.test(msg)) throw e
        // 等 bridge 重连
        await new Promise((r) => setTimeout(r, 1200))
        // 重开后需要重新打开项目
        try { await call('project.open_pack', { pack_dir: 'pack' }, 60000) } catch { /* ignore */ }
      }
    }
    throw last
  }

  try {
    // ---- 准备项目：bridge 只接受 workspace 内的相对路径，先把默认 YSM 包拷进来
    const srcPack = path.join(REPO_ROOT, 'vendor', 'YSM-Utils-Plugins', 'assets', 'default')
    const dstPack = path.join(WORKSPACE, 'pack')
    fs.cpSync(srcPack, dstPack, { recursive: true })
    const open = await call('project.open_pack', { pack_dir: 'pack' }, 120000)
    if (!open || open.ok === false) throw new Error(`open_pack failed: ${JSON.stringify(open)?.slice(0, 300)}`)
    console.log('[e2e-look] project opened, revision=', open.revision)

    // ---- L1 camera.get
    const cam = await call('camera.get', { source: 'offscreen' }, 10000)
    check('L1 camera.get', cam?.ok === true && Array.isArray(cam.position), {
      azimuth: cam?.azimuth, elevation: cam?.elevation, projection: cam?.projection,
    })

    // ---- L2 render.preview 单帧 + 计时（跑 5 次取 p50）
    const previews = []
    for (let i = 0; i < 5; i++) {
      const r = await callRetry('render.preview', {
        camera: { azimuth: i * 45, elevation: 15, projection: 'ortho' },
        size: [640, 640],
        background: '#1b1b1b',
      }, 60000)
      previews.push(r)
    }
    const ok2 = previews.every((r) => r?.ok && r.png)
    const times = previews.map((r) => r.elapsed_ms).sort((a, b) => a - b)
    const p50 = times[Math.floor(times.length / 2)]
    const first = previews[0]
    const buf = Buffer.from(first?.png ?? '', 'base64')
    const info = pngInfo(buf)
    if (info) fs.writeFileSync(path.join(WORKSPACE, 'out', 'preview-0.png'), buf)
    check('L2 render.preview 返回可解码 PNG', ok2 && !!info, {
      ...info, elapsed: times, p50, bytes_kb: Math.round(buf.length / 1024),
    })
    check('L2b render.preview 不落盘（workspace 里没有 renders 目录）',
      !fs.existsSync(path.join(WORKSPACE, 'artifacts', 'renders')), {})
    check('L2c render.preview 单帧 p50 ≤ 120ms（可接受）', p50 <= 120, { p50 })

    // ---- L3 render.sheet 多格合成
    const t3 = Date.now()
    const sheet = await callRetry('render.sheet', {
      cells: [{ view: 'front' }, { view: 'iso_fr' }],
      cell: 320,
      background: '#1b1b1b',
    }, 60000)
    const sheetBuf = Buffer.from(sheet?.png ?? '', 'base64')
    const sheetInfo = pngInfo(sheetBuf)
    if (sheetInfo) fs.writeFileSync(path.join(WORKSPACE, 'out', 'sheet-2.png'), sheetBuf)
    check('L3 render.sheet 2 格合成', sheet?.ok === true && sheet?.count === 2 && !!sheetInfo, {
      ...sheetInfo, cells: sheet?.count, elapsed_ms: sheet?.elapsed_ms, total_ms: Date.now() - t3,
      tokens: sheetInfo ? imageTokens(sheetInfo.width, sheetInfo.height) : null,
    })
    check('L3b 合成图非空（不是全黑占位）', !looksEmpty(sheetBuf), { bytes: sheetBuf.length })

    // ---- L4 转台 8 角度
    const orbitCells = []
    for (let i = 0; i < 8; i++) orbitCells.push({ camera: { azimuth: (360 / 8) * i, elevation: 15 } })
    const t4 = Date.now()
    const orbit = await callRetry('render.sheet', {
      cells: orbitCells, cell: 320, background: '#1b1b1b', cols: 4,
    }, 120000)
    const orbitBuf = Buffer.from(orbit?.png ?? '', 'base64')
    const orbitInfo = pngInfo(orbitBuf)
    if (orbitInfo) fs.writeFileSync(path.join(WORKSPACE, 'out', 'orbit-8.png'), orbitBuf)
    check('L4 转台 8 角度合成为一张', orbit?.ok === true && orbit?.count === 8 && !!orbitInfo, {
      ...orbitInfo, cols: orbit?.cols, rows: orbit?.rows,
      elapsed_ms: orbit?.elapsed_ms, total_ms: Date.now() - t4,
      tokens: orbitInfo ? imageTokens(orbitInfo.width, orbitInfo.height) : null,
    })

    // ---- L5 贴图像素放大
    const texSheet = await callRetry('render.texture_sheet', {
      regions: [{ region: [0, 0, 15, 15] }, { region: [16, 0, 31, 15] }],
      scale: 8, background: '#1b1b1b', cols: 2,
    }, 30000).catch((e) => ({ __error: String(e?.message ?? e) }))
    if (texSheet.__error) {
      check('L5 render.texture_sheet', false, { error: texSheet.__error })
    } else {
      const tb = Buffer.from(texSheet.png ?? '', 'base64')
      const ti = pngInfo(tb)
      if (ti) fs.writeFileSync(path.join(WORKSPACE, 'out', 'texture-sheet.png'), tb)
      check('L5 render.texture_sheet 像素放大合成', texSheet.ok === true && !!ti, {
        ...ti, panels: texSheet.count, elapsed_ms: texSheet.elapsed_ms,
      })
    }

    // ---- L6 动画采样
    const animList = await call('animation.list', {}, 30000).catch(() => null)
    const anims = animList?.animations ?? animList?.items ?? []
    if (anims.length) {
      const target = anims.find((a) => (a.length ?? 0) > 0.2) ?? anims[0]
      const targetName = target.animation ?? target.name
      const len = Number(target.length) || 1
      const animCells = []
      for (let i = 0; i < 4; i++) animCells.push({ time: +((len * i) / 3).toFixed(3), camera: { azimuth: 135, elevation: 15 } })
      const animSheet = await callRetry('render.sheet', {
        cells: animCells, cell: 320, background: '#1b1b1b', animation: targetName, cols: 4,
      }, 120000).catch((e) => ({ __error: String(e?.message ?? e) }))
      if (animSheet.__error) {
        check('L6 动画时间点采样', false, { error: animSheet.__error })
      } else {
        const ab = Buffer.from(animSheet.png ?? '', 'base64')
        const ai = pngInfo(ab)
        if (ai) fs.writeFileSync(path.join(WORKSPACE, 'out', 'anim-4.png'), ab)
        check('L6 动画时间点采样合成', animSheet.ok === true && animSheet.count === 4 && !!ai, {
          ...ai, animation: animSheet.animation, elapsed_ms: animSheet.elapsed_ms,
        })
      }
    } else {
      check('L6 动画时间点采样', true, { skipped: '项目内没有动画可测' })
    }

    // ---- L7 camera.set 生效
    const setCam = await callRetry('camera.set', { azimuth: 90, elevation: 30, projection: 'persp', fov: 50 }, 15000)
    check('L7 camera.set 回读位姿', setCam?.ok === true && setCam?.camera?.azimuth === 90
      && setCam?.camera?.projection === 'persp', { camera: setCam?.camera })

  } catch (error) {
    check('E2E 运行', false, { error: String(error?.message ?? error) })
  }

  clearTimeout(hardTimeout)
  cleanup()

  const passed = results.filter((r) => r.ok).length
  const summary = { at: new Date().toISOString(), passed, total: results.length, results }
  fs.writeFileSync(path.join(WORKSPACE, 'out', 'e2e-look-result.json'), JSON.stringify(summary, null, 2))
  console.log(`\n[e2e-look] ${passed}/${results.length} PASSED`)
  console.log(`[e2e-look] 产物：${path.join(WORKSPACE, 'out')}`)

  if (!KEEP) {
    // 保留 out 供人工查看；userData 目录可能仍被进程占用，尽力而为
    try {
      child.kill('SIGKILL')
    } catch { /* ignore */ }
    await new Promise((r) => setTimeout(r, 1500))
    try { fs.rmSync(path.join(WORKSPACE, '.bb'), { recursive: true, force: true }) } catch { /* 忽略占用 */ }
  }
  process.exit(passed === results.length ? 0 : 1)
}

main().catch((e) => { console.error(e); process.exit(1) })
