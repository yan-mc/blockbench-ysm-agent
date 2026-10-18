// 组装 BAE 应用目录：上游 Blockbench 构建产物 + 我们的 agent 三件套 + @electron/remote
// 用法：node packages/bb-agent-runtime/scripts/assemble.mjs [--out=<dir>] [--vendor=<blockbench dir>]

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PACKAGE_ROOT = path.resolve(__dirname, '..')
const REPO_ROOT = path.resolve(PACKAGE_ROOT, '..', '..')

function argValue(name, fallback) {
  const prefix = `--${name}=`
  const found = process.argv.find((a) => a.startsWith(prefix))
  return found ? found.slice(prefix.length) : (process.env[`BB_${name.toUpperCase()}`] ?? fallback)
}

export function assemble(options = {}) {
  const vendor = path.resolve(options.vendor ?? argValue('vendor', path.join(REPO_ROOT, 'vendor', 'blockbench')))
  const out = path.resolve(options.out ?? argValue('out', path.join(REPO_ROOT, 'dist', 'bb-agent-app')))
  const agentSrc = path.join(PACKAGE_ROOT, 'agent')

  const required = ['index.html', 'dist/bundle.js', 'package.json']
  for (const rel of required) {
    if (!fs.existsSync(path.join(vendor, rel))) {
      throw new Error(`vendor build incomplete: ${path.join(vendor, rel)} missing; run pnpm install && pnpm run build-electron in vendor/blockbench`)
    }
  }

  console.log(`[assemble] vendor=${vendor}`)
  console.log(`[assemble] out=${out}`)
  fs.rmSync(out, { recursive: true, force: true })
  fs.mkdirSync(out, { recursive: true })

  const copyList = [
    'index.html', 'dist', 'css', 'font', 'assets', 'icons', 'lib',
    'favicon.png', 'manifest.webmanifest', 'manifest-beta.webmanifest', 'icon.png',
    'LICENSE.MD', 'README.md',
  ]
  for (const rel of copyList) {
    const src = path.join(vendor, rel)
    if (!fs.existsSync(src)) { console.warn(`[assemble] skip missing ${rel}`); continue }
    fs.cpSync(src, path.join(out, rel), { recursive: true })
  }

  // bridge 三件套
  fs.cpSync(agentSrc, path.join(out, 'agent'), { recursive: true })

  // YSM 默认资源包模板（CC0，来自 YSM-Utils-Plugins；用于 project.create_ysm）
  const ysmTemplate = path.join(REPO_ROOT, 'vendor', 'YSM-Utils-Plugins', 'assets', 'default')
  if (fs.existsSync(ysmTemplate)) {
    fs.cpSync(ysmTemplate, path.join(out, 'templates', 'ysm_default'), { recursive: true })
    fs.writeFileSync(path.join(out, 'templates', 'README.md'), [
      '# YSM default template',
      '',
      'Source: YesSteveModel/YSM-Utils-Plugins assets/default (MIT plugin, CC0 default model).',
      'Used by BAE project.create_ysm to scaffold a new YSM pack.',
      '',
    ].join('\n'))
  } else {
    console.warn('[assemble] WARN: YSM default template missing:', ysmTemplate)
  }

  // renderer 必需的唯一外部包（pnpm node_modules 里是符号链接，先 realpath 再复制）
  const remoteSrc = path.join(vendor, 'node_modules', '@electron', 'remote')
  if (!fs.existsSync(remoteSrc)) throw new Error('@electron/remote missing; run pnpm install in vendor/blockbench')
  fs.mkdirSync(path.join(out, 'node_modules', '@electron'), { recursive: true })
  fs.cpSync(fs.realpathSync(remoteSrc), path.join(out, 'node_modules', '@electron', 'remote'), { recursive: true, dereference: true })

  const pkg = JSON.parse(fs.readFileSync(path.join(vendor, 'package.json'), 'utf8'))
  const runtimePkg = {
    name: 'blockbench-agent-runtime',
    version: `${pkg.version}-agent.0`,
    private: true,
    type: 'module',
    main: 'agent/main.js',
    license: 'GPL-3.0-or-later',
    description: 'Unofficial headless Blockbench runtime for dsh agents (derived from Blockbench)',
  }
  fs.writeFileSync(path.join(out, 'package.json'), JSON.stringify(runtimePkg, null, 2) + '\n')
  fs.writeFileSync(path.join(out, 'SOURCE.txt'), [
    'Unofficial Blockbench Agent Runtime (BAE).',
    `Upstream: https://github.com/JannisX11/blockbench tag v${pkg.version}`,
    'License: GPL-3.0-or-later. Modified files: agent/main.js, agent/preload.cjs, agent/bb-agent-bridge.js, agent/selftest.js.',
    'Corresponding source: this repository under packages/bb-agent-runtime/agent plus the upstream source at the URL above.',
    '',
  ].join('\n'))

  const electron = path.join(vendor, 'node_modules', 'electron', 'dist', process.platform === 'win32' ? 'electron.exe' : 'electron')
  if (!fs.existsSync(electron)) console.warn(`[assemble] WARN electron binary not found: ${electron}`)
  console.log(`[assemble] electron=${electron}`)
  console.log('[assemble] done')
  return { out, vendor, electron }
}

if (import.meta.url === `file://${process.argv[1].replace(/\\/g, '/')}` || process.argv[1]?.endsWith('assemble.mjs')) {
  const result = assemble()
  console.log(JSON.stringify(result, null, 2))
}
