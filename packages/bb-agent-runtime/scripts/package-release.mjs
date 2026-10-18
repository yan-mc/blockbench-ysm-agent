// 构建发布包：BAE dist + dsh Host 插件 + 文档 + 契约 + 校验和 + zip
// 用法：node packages/bb-agent-runtime/scripts/package-release.mjs [--version 0.2.0]
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { createZipFromDir } from './lib/zip.mjs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PACKAGE_ROOT = path.resolve(__dirname, '..')
const REPO_ROOT = path.resolve(PACKAGE_ROOT, '..', '..')
const pluginRoot = path.join(REPO_ROOT, 'packages', 'dsh-blockbench-agent')
const distApp = path.join(REPO_ROOT, 'dist', 'bb-agent-app')
const releaseRoot = path.join(REPO_ROOT, 'release')

const argVersion = process.argv.indexOf('--version')
const pluginPkg = JSON.parse(fs.readFileSync(path.join(pluginRoot, 'package.json'), 'utf8'))
const version = argVersion >= 0 ? process.argv[argVersion + 1] : pluginPkg.version
const stamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 12)
const bundleDir = path.join(releaseRoot, `bb-agent-${version}`)
const zipPath = path.join(releaseRoot, `bb-agent-${version}-${stamp}.zip`)

if (!fs.existsSync(path.join(distApp, 'agent', 'bb-agent-bridge.js'))) {
  throw new Error(`dist app incomplete: ${distApp} (run assemble.mjs first)`)
}

fs.rmSync(bundleDir, { recursive: true, force: true })
fs.mkdirSync(bundleDir, { recursive: true })

const copyDir = (src, dst, filter) => fs.cpSync(src, dst, { recursive: true, filter: (s) => filter ? filter(s) : true })
copyDir(distApp, path.join(bundleDir, 'bb-agent-app'), (src) => {
  const rel = path.relative(distApp, src)
  return !rel.startsWith('.git') && !rel.startsWith('node_modules\\.cache')
})

const pluginBundle = path.join(bundleDir, 'dsh-blockbench-agent')
fs.mkdirSync(pluginBundle, { recursive: true })
for (const entry of ['package.json', 'index.js', 'client.js', 'cordis.patch.yml', 'icon.svg', 'README.md']) {
  const src = path.join(pluginRoot, entry)
  if (fs.existsSync(src)) fs.copyFileSync(src, path.join(pluginBundle, entry))
}
for (const dir of ['lib', 'locale', 'skills']) {
  const src = path.join(pluginRoot, dir)
  if (fs.existsSync(src)) copyDir(src, path.join(pluginBundle, dir))
}

const docsDir = path.join(bundleDir, 'docs')
fs.mkdirSync(docsDir, { recursive: true })
for (const entry of ['ENGINEERING.md', 'MANUAL.md', 'FOLDER-MAP.md', 'docs/M0-report.md', 'docs/M0-report-safe.md', 'docs/assets/cover.png', 'packages/README.md', 'spec/tool-manifest.json', 'spec/bridge-methods.json', 'spec/generate_spec.py']) {
  const src = path.join(REPO_ROOT, entry)
  if (!fs.existsSync(src)) continue
  const dst = path.join(docsDir, entry.replace(/[\\/]/g, '__'))
  fs.copyFileSync(src, dst)
}

const installMd = `# BB-Agent 发布包 ${version}

包含：

- \`bb-agent-app/\`：BAE（隐藏 Blockbench Agent Runtime，含 agent 插件、YSM 默认模板、GPL SOURCE.txt）。
- \`dsh-blockbench-agent/\`：dsh Host 插件 bundle（30 个 bb_* 工具、命令、Skill、Client UI 状态 pill）。
- \`docs/\`：工程状态、M0 报告、契约文件。

## 安装（dsh）

1. 把 \`dsh-blockbench-agent/\` 放到一个固定目录（本包已带）。
2. 在 dsh 中安装 bundle：

   \`\`\`
   plugin_manager install_bundle target="<绝对路径>/dsh-blockbench-agent"
   \`\`\`

3. 如果 \`cordis.patch.yml\` 中的路径与本机不一致，修改后禁用/启用插件行重载：
   - \`workspaceRoot\`：项目工作区
   - \`executable\`：Electron 可执行文件
   - \`appPath\`：本包 \`bb-agent-app\` 的绝对路径
   - \`pluginPath\`：\`bb-agent-app/agent/bb-agent-bridge.js\`
4. 启用后运行 \`/bb-start\`，再调用 \`bb_session_start\`。

## 许可

BAE 包含 Blockbench（GPL-3.0）构建产物；源码与构建说明见 \`bb-agent-app/SOURCE.txt\` 与 Blockbench 官方仓库。dsh 插件部分为 MIT。
`
fs.writeFileSync(path.join(bundleDir, 'INSTALL.md'), installMd, 'utf8')

// SHA256SUMS
const allFiles = []
const walk = (dir) => {
  for (const entry of fs.readdirSync(dir)) {
    const abs = path.join(dir, entry)
    const stat = fs.statSync(abs)
    if (stat.isDirectory()) walk(abs)
    else allFiles.push(abs)
  }
}
walk(bundleDir)
const sums = allFiles
  .map((abs) => `${crypto.createHash('sha256').update(fs.readFileSync(abs)).digest('hex')}  ${path.relative(bundleDir, abs).replace(/\\/g, '/')}`)
  .sort()
fs.writeFileSync(path.join(bundleDir, 'SHA256SUMS.txt'), sums.join('\n') + '\n', 'utf8')

const zip = createZipFromDir(bundleDir, zipPath)
const summary = {
  version,
  bundle_dir: bundleDir,
  zip_path: zip.path,
  files: zip.files,
  bytes: zip.bytes,
  mb: Math.round((zip.bytes / 1048576) * 10) / 10,
  includes: ['bb-agent-app', 'dsh-blockbench-agent', 'docs', 'INSTALL.md', 'SHA256SUMS.txt'],
}
fs.writeFileSync(path.join(releaseRoot, 'release-result.json'), JSON.stringify(summary, null, 2) + '\n', 'utf8')
console.log(JSON.stringify(summary, null, 2))


