#!/usr/bin/env node
// T2 安装执行器的命令行入口（后台跑用，与 bb_seg_install 走同一套 lib/seginstall.js）
// 用法: node packages/dsh-blockbench-agent/test/run-seg-install.mjs [installDir]

import { runInstall, inspectInstall } from '../lib/seginstall.js'
import path from 'node:path'
import os from 'node:os'

const installDir = process.argv[2] || path.join(os.homedir(), '.dsh-seethrough')
const t0 = Date.now()

function log(...a) {
  const t = ((Date.now() - t0) / 1000).toFixed(1)
  console.log(`[${t}s]`, ...a)
}

log('install dir:', installDir)
const before = await inspectInstall(installDir)
log('before:', JSON.stringify(before))

const r = await runInstall({ installDir, onLog: (...a) => log(...a) })
log('result ok =', r.ok, 'error =', r.error ?? '-')
console.log(JSON.stringify({ ok: r.ok, steps: r.steps, paths: r.paths ?? null, error: r.error ?? null }, null, 2))
process.exit(r.ok ? 0 : 1)
