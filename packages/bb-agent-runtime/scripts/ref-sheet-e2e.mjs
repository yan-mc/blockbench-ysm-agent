#!/usr/bin/env node
// 参考图拼版（bridge `ref.sheet`）独立验证：起一台 BAE，把本地图拼成对照表 + 算 dHash。
// 用法: node packages/bb-agent-runtime/scripts/ref-sheet-e2e.mjs <图片目录> [输出png]

import fs from 'node:fs'
import fsp from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { createWsServer } from '../../dsh-blockbench-agent/lib/ws-server.js'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(HERE, '..', '..', '..')
const APP = path.join(REPO_ROOT, 'dist', 'bb-agent-app')
const ELECTRON = path.join(REPO_ROOT, 'vendor', 'blockbench', 'node_modules', 'electron', 'dist',
  process.platform === 'win32' ? 'electron.exe' : 'electron')
const WORKSPACE = path.join(REPO_ROOT, 'workspace', '_refsheet-e2e')

function log(...a) { console.log('[refsheet]', ...a) }

function hammingHex(a, b) {
  const x = BigInt(`0x${a}`) ^ BigInt(`0x${b}`)
  let n = 0n, v = x
  while (v > 0n) { if (v & 1n) n += 1n; v >>= 1n }
  return Number(n)
}

async function main() {
  const srcDir = process.argv[2]
  const outPng = process.argv[3] || path.join(WORKSPACE, 'sheet.png')
  if (!srcDir || !fs.existsSync(srcDir)) {
    console.error('用法: node ref-sheet-e2e.mjs <图片目录> [输出png]')
    process.exit(2)
  }

  fs.rmSync(WORKSPACE, { recursive: true, force: true })
  fs.mkdirSync(path.join(WORKSPACE, 'logs'), { recursive: true })
  fs.mkdirSync(path.join(WORKSPACE, 'refs'), { recursive: true })

  // 拷进 workspace（bridge 只接受 workspace 相对路径）
  const files = fs.readdirSync(srcDir).filter((f) => /\.(png|jpe?g|webp)$/i.test(f)).slice(0, 18)
  for (const f of files) fs.copyFileSync(path.join(srcDir, f), path.join(WORKSPACE, 'refs', f))
  log(`拷入 ${files.length} 张图`)

  const token = randomBytes(24).toString('base64url')
  let signalConnected
  const connected = new Promise((res) => { signalConnected = res })
  const server = createWsServer({
    token,
    defaultTimeoutMs: 180000,
    onConnection: () => signalConnected(true),
    methods: {
      'system.hello': () => ({
        protocol: 'bb-agent/1', transport: 'ws',
        server: { name: 'bb-agent-runtime', version: 'refsheet-e2e', blockbench: '5.2.2' },
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
    `--rpc-url=${url}`, `--token=${token}`, '--transport=ws',
  ], { cwd: APP, windowsHide: true, env })
  const logStream = fs.createWriteStream(path.join(WORKSPACE, 'logs', 'electron.log'), { flags: 'a' })
  child.stdout.on('data', (d) => logStream.write(d))
  child.stderr.on('data', (d) => logStream.write(d))
  const cleanup = () => {
    try { child.kill('SIGKILL') } catch { /* ignore */ }
    try { server.close?.() } catch { /* ignore */ }
    logStream.end()
  }
  const hard = setTimeout(() => { console.error('[refsheet] TIMEOUT'); cleanup(); process.exit(2) }, 180000)
  hard.unref?.()

  await connected
  const call = (m, p, t = 120000) => server.request(m, p, { timeoutMs: t })

  const rel = files.map((f) => `refs/${f}`)
  const t0 = Date.now()
  const res = await call('ref.sheet', {
    files: rel, cell: 200, background: '#141418', labels: true, hash: true,
  }, 120000)
  log(`ref.sheet 用时 ${Date.now() - t0}ms  ${res.width}x${res.height}  loaded=${res.loaded}/${res.count}`)

  const png = Buffer.from(res.png, 'base64')
  await fsp.writeFile(outPng, png)
  log(`PNG -> ${outPng} (${(png.length / 1024).toFixed(0)} KB)`)

  const withHash = res.images.filter((r) => r.dhash)
  log(`dHash 成功 ${withHash.length}/${res.count}`)
  for (const r of res.images.slice(0, 6)) {
    log(`  #${r.index} ${r.file.padEnd(24)} ${r.width}x${r.height} ratio=${r.ratio} dhash=${r.dhash ?? '-'}`)
  }

  // 感知去重分组（汉明距离 <= 6）
  const groups = []
  for (const r of withHash) {
    const g = groups.find((grp) => hammingHex(grp[0].dhash, r.dhash) <= 6)
    if (g) g.push(r); else groups.push([r])
  }
  const dupGroups = groups.filter((g) => g.length > 1)
  log(`感知去重: ${withHash.length} 张 → ${groups.length} 组，其中重复组 ${dupGroups.length}`)
  for (const g of dupGroups) log(`   重复: ${g.map((x) => path.basename(x.file)).join(', ')}`)

  cleanup()
  const pass = res.ok && res.loaded === res.count && withHash.length === res.count && png.length > 10000
  log(pass ? 'PASS: ref.sheet 可用' : 'FAIL: 有图未成功加载或哈希缺失')
  process.exit(pass ? 0 : 1)
}

main().catch((e) => { console.error('[refsheet] ERROR', e); process.exit(3) })

