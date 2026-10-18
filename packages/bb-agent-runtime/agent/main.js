// BAE · Blockbench Agent Runtime 主进程（真实实现起点）
// 与上游 electron/main.js 的差异：
//   1) 窗口 show:false 且永不自动 show()；关闭改为 hide
//   2) webPreferences.backgroundThrottling:false（隐藏窗口保持渲染）
//   3) 渲染进程初始化完成后注入 bridge 插件（source:'file' 自持久化）
//   4) agent profile 离线化：拦截外部 http(s)、关闭自动更新（不引用 updater）
//   5) --self-test：执行 M0 渲染自检，输出 m0-result.json 并由主进程校验 PNG
//
// 启动参数：
//   --workspace=<dir> --rpc-url=ws://... --token=... --plugin=<bridge abs path>
//   --user-data=<dir> [--online] [--safe-mode] [--self-test] [--selftest-pack=<ysm default dir>]

import path from 'node:path'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { app, BrowserWindow, session, ipcMain, nativeImage } = require('electron')
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const APP_ROOT = path.resolve(__dirname, '..')
const EXIT_INSTANCE_CONFLICT = 3
const EXIT_RENDERER_LOST = 4
const EXIT_SELFTEST_FAILED = 10

function arg(name, fallback = undefined) {
  const prefix = `--${name}=`
  const found = process.argv.find((a) => a.startsWith(prefix))
  return found ? found.slice(prefix.length) : (process.env[`BB_AGENT_${name.toUpperCase().replace(/-/g, '_')}`] ?? fallback)
}
const flag = (name) => process.argv.includes(`--${name}`)

const workspace = path.resolve(arg('workspace', path.join(APP_ROOT, 'workspace')))
const rpcUrl = arg('rpc-url', '')
const token = arg('token', '')
const transport = arg('transport', 'auto')
const userData = path.resolve(arg('user-data', path.join(workspace, '.bb', 'userdata')))
const pluginPath = path.resolve(arg('plugin', path.join(APP_ROOT, 'agent', 'bb-agent-bridge.js')))
const selftest = flag('self-test')
const safeMode = flag('safe-mode')
const offline = !flag('online')
const selftestPack = path.resolve(arg('selftest-pack', ''))
const selftestOut = path.join(workspace, 'artifacts', 'm0')

for (const dir of [workspace, userData, path.join(workspace, 'logs'), selftestOut, path.join(userData, 'thumbnails')]) fs.mkdirSync(dir, { recursive: true })
// 预授权 bridge 插件的 fs 权限，避免 BB5 首次 requireNativeModule('fs') 弹原生权限框
try {
  fs.writeFileSync(path.join(userData, 'plugin_permissions.json'), JSON.stringify({
    'bb-agent-bridge': { allowed: { fs: true } },
  }, null, 2))
} catch { /* ignore */ }
app.setPath('userData', userData)

app.commandLine.appendSwitch('ignore-gpu-blacklist')
app.commandLine.appendSwitch('ignore-gpu-blocklist')
app.commandLine.appendSwitch('enable-accelerated-video')
if (safeMode) {
  app.disableHardwareAcceleration()
  app.commandLine.appendSwitch('disable-gpu')
  app.commandLine.appendSwitch('enable-unsafe-swiftshader') // Windows 上游不会自动加
}

function log(line) {
  const text = `[${new Date().toISOString()}] ${line}\n`
  process.stdout.write(text)
  try { fs.appendFileSync(path.join(workspace, 'logs', 'agent.log'), text) } catch { /* ignore */ }
}

if (!app.requestSingleInstanceLock()) {
  log(`instance conflict for userData=${userData}`)
  app.exit(EXIT_INSTANCE_CONFLICT)
}

// @electron/remote：Blockbench renderer 的 native_apis 依赖它
let remoteMain = null
try {
  remoteMain = require('@electron/remote/main')
  remoteMain.initialize()
} catch (error) {
  log(`@electron/remote unavailable: ${error?.message}`)
}

let win = null
let shuttingDown = false
let injected = false

function blockExternalNetwork() {
  if (!offline) return
  try {
    session.defaultSession.webRequest.onBeforeRequest(
      { urls: ['http://*/*', 'https://*/*'] },
      (details, callback) => {
        try {
          const host = new URL(details.url).hostname
          callback({ cancel: !(host === '127.0.0.1' || host === 'localhost') })
        } catch { callback({ cancel: true }) }
      },
    )
    log('offline profile: external http(s) blocked')
  } catch (error) {
    log(`network block failed: ${error?.message}`)
  }
}

function attachConsole() {
  try {
    win.webContents.on('console-message', (...args) => {
      const details = args[1]
      const message = typeof details === 'object' && details ? details.message : args[2]
      const level = typeof details === 'object' && details ? details.level : args[1]
      log(`[renderer:${level}] ${message}`)
    })
  } catch { /* ignore */ }
}

function createWindow() {
  win = new BrowserWindow({
    show: false,
    width: 1280,
    height: 800,
    minWidth: 640,
    minHeight: 480,
    skipTaskbar: true,
    backgroundColor: '#21252b',
    webPreferences: {
      webgl: true,
      webSecurity: true,
      nodeIntegration: true,
      contextIsolation: false,
      backgroundThrottling: false,
      preload: path.join(__dirname, 'preload.cjs'),
      additionalArguments: [`--bb-agent-config=${encodeURIComponent(JSON.stringify({
        rpcUrl,
        token,
        transport,
        workspace,
        pluginPath,
        bridgeId: 'bb-agent-bridge',
        appRoot: APP_ROOT,
        selfTest: selftest ? { packDir: selftestPack, outDir: selftestOut } : null,
      }))}`],
    },
  })

  try { remoteMain?.enable(win.webContents) } catch (error) { log(`remote.enable failed: ${error?.message}`) }
  attachConsole()
  win.on('close', (event) => {
    if (shuttingDown) return
    event.preventDefault()
    win.hide()
    log('window close intercepted -> hidden')
  })
  win.webContents.on('render-process-gone', (_event, details) => {
    log(`renderer gone: ${JSON.stringify(details)}`)
    app.exit(EXIT_RENDERER_LOST)
  })
  win.loadFile(path.join(APP_ROOT, 'index.html'))
    .then(() => log('index.html loaded'))
    .catch((error) => { log(`load failed: ${error?.message}`); app.exit(5) })
}

async function waitForBlockbench(timeoutMs = 30000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      const ready = await win.webContents.executeJavaScript(
        'typeof Blockbench !== "undefined" && !!Blockbench.setup_successful',
      )
      if (ready) return true
    } catch { /* page not ready */ }
    await new Promise((r) => setTimeout(r, 100))
  }
  return false
}

async function injectBridge() {
  if (injected) return true
  if (!fs.existsSync(pluginPath)) throw new Error(`bridge plugin missing: ${pluginPath}`)
  const payload = { path: pluginPath, name: path.basename(pluginPath), content: '' }
  const result = await win.webContents.executeJavaScript(`(() => {
    if (window.Plugins?.registered?.['bb-agent-bridge']) return 'already';
    new Plugin().loadFromFile(${JSON.stringify(payload)}, false);
    return 'injected';
  })()`)
  injected = result === 'injected' || result === 'already'
  log(`bridge plugin: ${result}`)
  return injected
}

// ---------------------------------------------------------------- M0 self-test
function validatePng(filePath) {
  const image = nativeImage.createFromPath(filePath)
  if (image.isEmpty()) return { ok: false, error: 'empty image', path: filePath }
  const size = image.getSize()
  const bitmap = image.toBitmap() // BGRA
  let alphaNonZero = 0, luminanceSum = 0, luminanceSq = 0, n = 0
  const stride = Math.max(1, Math.floor(bitmap.length / 4 / 20000)) // 采样约 2 万点
  for (let i = 0; i < bitmap.length; i += 4 * stride) {
    const b = bitmap[i], g = bitmap[i + 1], r = bitmap[i + 2], a = bitmap[i + 3]
    if (a !== 0) alphaNonZero++
    const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    luminanceSum += lum; luminanceSq += lum * lum; n++
  }
  const mean = luminanceSum / Math.max(n, 1)
  const variance = luminanceSq / Math.max(n, 1) - mean * mean
  return {
    ok: size.width > 0 && size.height > 0 && alphaNonZero > 0,
    path: filePath, width: size.width, height: size.height,
    alpha_ratio: alphaNonZero / Math.max(n, 1),
    luminance_mean: Number(mean.toFixed(3)),
    luminance_variance: Number(variance.toFixed(3)),
  }
}

async function runSelfTest() {
  log('M0 self-test starting')
  const selftestPath = path.join(__dirname, 'selftest.js')
  if (!fs.existsSync(selftestPath)) throw new Error(`selftest.js missing: ${selftestPath}`)
  if (!selftestPack || !fs.existsSync(selftestPack)) throw new Error(`selftest pack missing: ${selftestPack}`)
  const code = fs.readFileSync(selftestPath, 'utf8')
  const result = await win.webContents.executeJavaScript(`(async () => { ${code} })()`)
  const resultPath = path.join(selftestOut, 'm0-result.json')
  if (!fs.existsSync(resultPath)) throw new Error(`renderer did not write ${resultPath}`)
  const report = JSON.parse(fs.readFileSync(resultPath, 'utf8'))
  const checks = []
  for (const view of report.views ?? []) {
    const v = validatePng(path.join(selftestOut, view.file))
    checks.push({ view: view.view, ...v })
  }
  const failed = checks.filter((c) => !c.ok || c.width !== report.size?.[0] || c.height !== report.size?.[1])
  const lowAlpha = checks.filter((c) => (c.alpha_ratio ?? 0) < 0.005)
  const flat = checks.filter((c) => (c.luminance_variance ?? 0) < 5)
  const verification = {
    ok: result?.ok === true && failed.length === 0 && lowAlpha.length === 0 && flat.length === 0,
    selftest_ok: result?.ok === true,
    selftest_error: result?.error ?? null,
    checked_at: new Date().toISOString(),
    checks,
    problems: {
      invalid: failed.map((c) => c.view),
      low_alpha: lowAlpha.map((c) => c.view),
      flat: flat.map((c) => c.view),
    },
    renderer: result,
  }
  fs.writeFileSync(path.join(selftestOut, 'm0-verified.json'), JSON.stringify(verification, null, 2))
  process.stdout.write(`BB_AGENT_M0_RESULT: ${JSON.stringify({ ok: verification.ok, problems: verification.problems, checks })}\n`)
  return verification
}

ipcMain.on('bb-agent:shutdown', () => {
  log('shutdown requested by bridge')
  shuttingDown = true
  try { win?.destroy() } catch { /* ignore */ }
  app.quit()
})

ipcMain.handle('bb-agent:window', (_event, action) => {
  try {
    if (!win) return { ok: false, visible: false }
    if (action === 'show') { win.show(); win.focus() }
    else if (action === 'hide') { win.hide() }
    return { ok: true, visible: win.isVisible() }
  } catch (error) {
    log(`window ${action} failed: ${error?.message}`)
    return { ok: false, error: String(error?.message ?? error) }
  }
})

app.whenReady().then(async () => {
  try {
    fs.writeFileSync(path.join(workspace, '.bb', 'runtime.json'), JSON.stringify({
      pid: process.pid, workspace, rpcUrl: rpcUrl ? 'configured' : '', startedAt: new Date().toISOString(),
    }, null, 2))
  } catch { /* ignore */ }
  blockExternalNetwork()
  createWindow()
  const ready = await waitForBlockbench()
  if (!ready) { log('Blockbench not ready within timeout'); app.exit(6); return }
  log('Blockbench ready')
  if (!(await injectBridge())) { log('bridge injection failed'); app.exit(7); return }
  if (selftest) {
    try {
      const verification = await runSelfTest()
      log(`M0 self-test ${verification.ok ? 'PASSED' : 'FAILED'}`)
      shuttingDown = true
      app.exit(verification.ok ? 0 : EXIT_SELFTEST_FAILED)
    } catch (error) {
      log(`M0 self-test error: ${error?.stack ?? error?.message ?? error}`)
      shuttingDown = true
      app.exit(EXIT_SELFTEST_FAILED)
    }
  }
})

app.on('window-all-closed', () => { /* 常驻：不退出 */ })
app.on('second-instance', () => { if (win && !selftest) win.show() })
