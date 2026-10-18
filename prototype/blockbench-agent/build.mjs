// BAE 构建脚本（设计参考骨架，未在目标环境完整执行）
// 目标：从固定 tag 的上游 Blockbench 构建渲染层，组装出一个可被 dsh 启动的 Electron 应用目录。
//
// 用法：
//   node build.mjs --blockbench=F:\Deepseek_harness\blockbench\vendor\blockbench --out=..\..\dist\blockbench-agent
//
// 产物：
//   <out>/index.html, css/, font/, assets/, icons/, lib/, dist/, package.json, agent/
//   <out>/node_modules/@electron/remote （renderer 必须；其余上游生产依赖按需复制）

import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const args = new Map(process.argv.slice(2).map((a) => a.replace(/^--/, '').split('=')))
const bbRoot = path.resolve(args.get('blockbench') ?? path.resolve(__dirname, '..', '..', 'vendor', 'blockbench'))
const outRoot = path.resolve(args.get('out') ?? path.resolve(__dirname, '..', '..', 'dist', 'blockbench-agent'))
const expectedVersion = '5.2.2'

const pkg = JSON.parse(fs.readFileSync(path.join(bbRoot, 'package.json'), 'utf8'))
if (pkg.version !== expectedVersion) {
  throw new Error(`Blockbench version mismatch: expected ${expectedVersion}, got ${pkg.version}`)
}

console.log('[bae] building upstream renderer...')
execFileSync(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['ci'], { cwd: bbRoot, stdio: 'inherit' })
execFileSync(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'build-electron'], { cwd: bbRoot, stdio: 'inherit' })

console.log('[bae] assembling app dir:', outRoot)
fs.rmSync(outRoot, { recursive: true, force: true })
fs.mkdirSync(outRoot, { recursive: true })

const copyList = ['index.html', 'dist', 'css', 'font', 'assets', 'icons', 'lib']
for (const entry of copyList) {
  const src = path.join(bbRoot, entry)
  if (!fs.existsSync(src)) { console.warn('[bae] skip missing', entry); continue }
  fs.cpSync(src, path.join(outRoot, entry), { recursive: true })
}

// bridge 三件套
fs.cpSync(path.join(__dirname, 'agent'), path.join(outRoot, 'agent'), { recursive: true })

// renderer 必需生产依赖：@electron/remote（native_apis.ts 直接 require）
const remoteSrc = path.join(bbRoot, 'node_modules', '@electron', 'remote')
if (fs.existsSync(remoteSrc)) {
  fs.mkdirSync(path.join(outRoot, 'node_modules', '@electron'), { recursive: true })
  fs.cpSync(remoteSrc, path.join(outRoot, 'node_modules', '@electron', 'remote'), { recursive: true })
} else {
  console.warn('[bae] WARN: @electron/remote not found in upstream node_modules; run npm ci first')
}

// 写运行时 package.json（main 指向 agent/main.js）
const runtimePkg = {
  name: 'blockbench-agent-runtime',
  version: `${expectedVersion}-agent.0`,
  private: true,
  type: 'module',
  main: 'agent/main.js',
  license: 'GPL-3.0-or-later',
  description: 'Unofficial headless Blockbench runtime for dsh agents',
}
fs.writeFileSync(path.join(outRoot, 'package.json'), JSON.stringify(runtimePkg, null, 2) + '\n')

// GPL 合规：保留上游许可证与源码来源说明
for (const file of ['LICENSE.MD', 'README.md']) {
  const src = path.join(bbRoot, file)
  if (fs.existsSync(src)) fs.cpSync(src, path.join(outRoot, file))
}
fs.writeFileSync(path.join(outRoot, 'SOURCE.txt'), [
  'This distribution contains an unofficial build derived from Blockbench.',
  `Upstream: https://github.com/JannisX11/blockbench tag v${expectedVersion}`,
  'License: GPL-3.0-or-later. Source is available from the upstream repository and the agent patch files in agent/.',
  '',
].join('\n'))

console.log('[bae] done. next: electron . --workspace=... --rpc-url=... --token=...')
