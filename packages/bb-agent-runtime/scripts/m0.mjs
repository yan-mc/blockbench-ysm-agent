// M0 Spike 编排：组装 BAE → 启动隐藏窗口 → 渲染自检 → 校验 PNG → 写 M0 报告
// 用法：
//   node packages/bb-agent-runtime/scripts/m0.mjs [--safe-mode] [--skip-assemble]
//   node packages/bb-agent-runtime/scripts/m0.mjs --safe-mode   # 无 GPU 降级验证

import fs from 'node:fs'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { assemble } from './assemble.mjs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PACKAGE_ROOT = path.resolve(__dirname, '..')
const REPO_ROOT = path.resolve(PACKAGE_ROOT, '..', '..')
const has = (name) => process.argv.includes(`--${name}`)
const safeMode = has('safe-mode')
const skipAssemble = has('skip-assemble')

const appDir = path.join(REPO_ROOT, 'dist', 'bb-agent-app')
const workspace = path.join(REPO_ROOT, 'workspace', safeMode ? '_m0-safe' : '_m0')
const packDir = path.join(REPO_ROOT, 'vendor', 'YSM-Utils-Plugins', 'assets', 'default')
const electronExe = path.join(REPO_ROOT, 'vendor', 'blockbench', 'node_modules', 'electron', 'dist', process.platform === 'win32' ? 'electron.exe' : 'electron')

if (!skipAssemble) assemble({ out: appDir })
if (!fs.existsSync(electronExe)) throw new Error(`electron binary missing: ${electronExe}`)
if (!fs.existsSync(path.join(packDir, 'models', 'main.json'))) throw new Error(`YSM default pack missing: ${packDir}`)

fs.rmSync(workspace, { recursive: true, force: true })
fs.mkdirSync(path.join(workspace, 'logs'), { recursive: true })

const args = [
  appDir,
  '--self-test',
  `--workspace=${workspace}`,
  `--plugin=${path.join(appDir, 'agent', 'bb-agent-bridge.js')}`,
  `--user-data=${path.join(workspace, '.bb', 'userdata')}`,
  `--selftest-pack=${packDir}`,
]
if (safeMode) args.push('--safe-mode')

console.log(`[m0] electron: ${electronExe}`)
console.log(`[m0] app: ${appDir}`)
console.log(`[m0] workspace: ${workspace}`)
console.log(`[m0] args: ${args.join(' ')}`)

const childEnv = { ...process.env, ELECTRON_ENABLE_LOGGING: '1' }
delete childEnv.ELECTRON_RUN_AS_NODE // 关键：否则 Electron 以纯 Node 模式启动，require('electron') 失败
const child = spawn(electronExe, args, {
  cwd: appDir,
  windowsHide: true,
  env: childEnv,
})
const logPath = path.join(workspace, 'logs', 'm0-electron.log')
const logStream = fs.createWriteStream(logPath, { flags: 'a' })
const timeoutMs = 240000
const timeout = setTimeout(() => {
  console.error('[m0] TIMEOUT, killing electron')
  try { child.kill('SIGKILL') } catch { /* ignore */ }
}, timeoutMs)

child.stdout.on('data', (d) => { process.stdout.write(d); logStream.write(d) })
child.stderr.on('data', (d) => { process.stderr.write(d); logStream.write(d) })

const exitCode = await new Promise((resolve) => child.on('exit', (code, signal) => resolve(code ?? (signal ? 1 : 0))))
clearTimeout(timeout)
logStream.end()

const verifiedPath = path.join(workspace, 'artifacts', 'm0', 'm0-verified.json')
const resultPath = path.join(workspace, 'artifacts', 'm0', 'm0-result.json')
let verified = null
try { verified = JSON.parse(fs.readFileSync(verifiedPath, 'utf8')) } catch { /* ignore */ }
let result = null
try { result = JSON.parse(fs.readFileSync(resultPath, 'utf8')) } catch { /* ignore */ }

const pass = exitCode === 0 && verified?.ok === true
console.log(`\n[m0] exit=${exitCode} pass=${pass}`)
if (verified) {
  console.log('[m0] checks:', JSON.stringify(verified.checks, null, 2))
  if (verified.problems) console.log('[m0] problems:', JSON.stringify(verified.problems))
} else {
  console.log('[m0] no m0-verified.json; see', logPath)
}

// 写 M0 报告（docs/M0-report.md）
try {
  const docsDir = path.join(REPO_ROOT, 'docs')
  fs.mkdirSync(docsDir, { recursive: true })
  const lines = []
  lines.push('# M0 · 可行性 Spike 报告（自动生成）', '')
  lines.push(`- 执行时间：${new Date().toISOString()}`)
  lines.push(`- 模式：${safeMode ? 'safe-mode（禁用 GPU）' : '正常 GPU'}`)
  lines.push(`- Electron：\`${electronExe}\``)
  lines.push(`- 结论：**${pass ? 'Go' : 'No-Go'}**（exit=${exitCode}）`)
  lines.push(`- selftest.ok：${result?.ok}；show/hide 后仍可渲染：${result?.show_hide_ok}`)
  if (result?.error) lines.push(`- renderer error：\`${String(result.error).split('\n')[0]}\``)
  lines.push('', '## 渲染校验', '')
  lines.push('| view | ok | size | alpha_ratio | luminance_variance |')
  lines.push('|---|---|---|---|---|')
  for (const c of verified?.checks ?? []) {
    lines.push(`| ${c.view} | ${c.ok} | ${c.width}x${c.height} | ${c.alpha_ratio?.toFixed(3) ?? '-'} | ${c.luminance_variance ?? '-'} |`)
  }
  lines.push('', '## 渲染器指标', '')
  lines.push('```json')
  lines.push(JSON.stringify(result?.timings ?? {}, null, 2))
  lines.push('```')
  lines.push('', '## WebGL', '', '```json')
  lines.push(JSON.stringify(result?.gl ?? {}, null, 2))
  lines.push('```')
  lines.push('', '## Project', '', '```json')
  lines.push(JSON.stringify(result?.project ?? {}, null, 2))
  lines.push('```')
  if (result?.error) lines.push('', '## Error', '', '```', String(result.error), '```')
  lines.push('', `日志：\`${logPath}\``, `产物：\`${path.dirname(verifiedPath)}\``)
  fs.writeFileSync(path.join(docsDir, safeMode ? 'M0-report-safe.md' : 'M0-report.md'), lines.join('\n') + '\n')
  console.log(`[m0] report written: docs/${safeMode ? 'M0-report-safe.md' : 'M0-report.md'}`)
} catch (error) {
  console.warn('[m0] report write failed:', error?.message)
}

process.exit(pass ? 0 : 1)
