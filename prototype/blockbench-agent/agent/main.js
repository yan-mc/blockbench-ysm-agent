// Blockbench Agent Runtime (BAE) · Electron 主进程（设计参考骨架）
// 启动示例：
//   electron <appRoot> --workspace=F:\...\workspace\demo --rpc-url=ws://127.0.0.1:12345/bb-agent/v1 --token=xxx
// 关键改动（相对上游 electron/main.js）：
//   1) 窗口 show:false 且不再调用 win.show()/maximize()
//   2) webPreferences.backgroundThrottling:false
//   3) 页面就绪后注入 bridge 插件；拦截外部网络；关闭事件改为 hide
//
// 注意：本文件是设计参考实现，未在目标 Electron/Blockbench 版本上完整跑通；
// 接入真实项目时请按 research/blockbench-core.md §1/§4 的验证清单逐项确认。

import { app, BrowserWindow, session, ipcMain } from 'electron'
import path from 'node:path'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const APP_ROOT = path.resolve(__dirname, '..')          // 含 index.html 的 Blockbench 构建目录
const EXIT_INSTANCE_CONFLICT = 3
const EXIT_RENDERER_LOST = 4

function arg(name, fallback = undefined) {
  const prefix = `--${name}=`
  const found = process.argv.find((a) => a.startsWith(prefix))
  return found ? found.slice(prefix.length) : (process.env[`BB_AGENT_${name.toUpperCase()}`] ?? fallback)
}

const workspace = path.resolve(arg('workspace', process.cwd()))
const rpcUrl = arg('rpc-url', '')
const token = arg('token', '')
const userData = path.resolve(arg('user-data', path.join(workspace, '.bb', 'userdata')))
const pluginPath = path.resolve(arg('plugin', path.join(APP_ROOT, 'agent', 'bb-agent-bridge.js')))
const safeMode = process.argv.includes('--safe-mode')
const offline = !process.argv.includes('--online')

for (const dir of [workspace, userData]) fs.mkdirSync(dir, { recursive: true })
app.setPath('userData', userData)

// 与上游一致的 GPU 开关；safe-mode 强制软件渲染
app.commandLine.appendSwitch('ignore-gpu-blacklist')
app.commandLine.appendSwitch('ignore-gpu-blocklist')
app.commandLine.appendSwitch('enable-accelerated-video')
if (safeMode) {
  app.disableHardwareAcceleration()
  app.commandLine.appendSwitch('disable-gpu')
  app.commandLine.appendSwitch('enable-unsafe-swiftshader') // Windows 上游不会自动加
}

if (!app.requestSingleInstanceLock()) {
  console.error('[bb-agent] another instance holds the userData lock:', userData)
  app.exit(EXIT_INSTANCE_CONFLICT)
}

let win = null
let shuttingDown = false
let injected = false

function log(line) {
  const text = `[${new Date().toISOString()}] ${line}\n`
  process.stdout.write(text)
  try { fs.appendFileSync(path.join(workspace, 'logs', 'agent.log'), text) } catch { /* ignore */ }
}
try { fs.mkdirSync(path.join(workspace, 'logs'), { recursive: true }) } catch { /* ignore */ }

function blockExternalNetwork() {
  if (!offline) return
  try {
    session.defaultSession.webRequest.onBeforeRequest(
      { urls: ['http://*/*', 'https://*/*'] },
      (details, callback) => {
        try {
          const host = new URL(details.url).hostname
          const local = host === '127.0.0.1' || host === 'localhost'
          callback({ cancel: !local })
        } catch {
          callback({ cancel: true })
        }
      },
    )
    log('external network blocked (offline profile)')
  } catch (error) {
    log(`network block failed: ${error?.message}`)
  }
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
        rpcUrl, token, workspace, pluginPath, bridgeId: 'bb-agent-bridge',
      }))}`],
    },
  })

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

/** 等 Blockbench 初始化完成（boot_loader 末尾置 setup_successful=true） */
async function waitForBlockbench(timeoutMs = 20000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      const ready = await win.webContents.executeJavaScript(
        'typeof Blockbench !== "undefined" && !!Blockbench.setup_successful',
      )
      if (ready) return true
    } catch { /* page not ready yet */ }
    await new Promise((r) => setTimeout(r, 100))
  }
  return false
}

async function injectBridge() {
  if (injected) return true
  if (!fs.existsSync(pluginPath)) throw new Error(`bridge plugin missing: ${pluginPath}`)
  const payload = { path: pluginPath, name: 'bb-agent-bridge.js', content: '' }
  const result = await win.webContents.executeJavaScript(`(() => {
    if (window.Plugins?.registered?.['bb-agent-bridge']) return 'already';
    new Plugin().loadFromFile(${JSON.stringify(payload)}, false);
    return 'injected';
  })()`)
  injected = result === 'injected' || result === 'already'
  log(`bridge plugin: ${result}`)
  return injected
}

ipcMain.on('bb-agent:shutdown', () => {
  log('shutdown requested by bridge')
  shuttingDown = true
  try { win?.destroy() } catch { /* ignore */ }
  app.quit()
})

ipcMain.handle('bb-agent:workspace', () => workspace)

app.whenReady().then(async () => {
  blockExternalNetwork()
  createWindow()
  const ready = await waitForBlockbench()
  if (!ready) {
    log('Blockbench did not become ready within timeout')
    app.exit(6)
    return
  }
  try {
    const ok = await injectBridge()
    if (!ok) app.exit(7)
  } catch (error) {
    log(`bridge inject failed: ${error?.message}`)
    app.exit(7)
    return
  }
  log(`ready: workspace=${workspace} rpc=${rpcUrl ? 'configured' : 'missing'}`)
})

app.on('window-all-closed', () => { /* 常驻后台：不退出 */ })
app.on('second-instance', () => { if (win) win.show() })
