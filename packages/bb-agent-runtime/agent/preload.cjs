// BAE preload：在页面脚本执行前注入运行时配置与受控控制面。
// contextIsolation=false + nodeIntegration=true 与上游 Blockbench 保持一致；
// 这里不使用 contextBridge，直接挂 window.__BB_AGENT__ / __BB_AGENT_API__。
const prefix = '--bb-agent-config='
const raw = process.argv.find((arg) => arg.startsWith(prefix))
let config = null
if (raw) {
  try { config = JSON.parse(decodeURIComponent(raw.slice(prefix.length))) } catch { config = null }
}
window.__BB_AGENT__ = config ?? {
  rpcUrl: process.env.BB_AGENT_RPC_URL ?? '',
  token: process.env.BB_AGENT_TOKEN ?? '',
  workspace: process.env.BB_AGENT_WORKSPACE ?? '',
  pluginPath: process.env.BB_AGENT_PLUGIN ?? '',
  bridgeId: 'bb-agent-bridge',
}
window.__BB_AGENT_PRELOADED__ = true

// 受控控制面：只暴露窗口显示/隐藏等少量能力，避免在 executeJavaScript 里依赖 require。
try {
  const { ipcRenderer } = require('electron')
  window.__BB_AGENT_API__ = {
    showWindow: () => ipcRenderer.invoke('bb-agent:window', 'show'),
    hideWindow: () => ipcRenderer.invoke('bb-agent:window', 'hide'),
    windowState: () => ipcRenderer.invoke('bb-agent:window', 'state'),
    shutdown: () => ipcRenderer.send('bb-agent:shutdown'),
  }
} catch (error) {
  window.__BB_AGENT_API__ = null
}
