#!/usr/bin/env node
// P1 自测：多源搜索 + 下载 + 去重（纯 Node，不依赖 DSH / BAE）
// 用法: node packages/dsh-blockbench-agent/test/ref-pipeline.mjs [角色名]

import fsp from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import { searchRefs, sortCandidates, SOURCES } from '../lib/refsearch.js'
import { collectRefs, sniffImage, readSize } from '../lib/refcollect.js'

const character = process.argv[2] || '丰川祥子'

function line(s = '') { console.log(s) }

const t0 = Date.now()
line(`=== 1. 多源搜索: ${character} ===`)
line(`已注册源: ${SOURCES.map((s) => s.id).join(', ')}`)

const res = await searchRefs({
  character,
  maxQueries: 5,
  perSource: 30,
  timeoutMs: 20000,
  onLog: (m) => line(`   ${m}`),
})

line('')
line('源状态:')
for (const s of res.sources) {
  line(`  ${s.id.padEnd(10)} ${s.ok ? 'OK ' : 'FAIL'}  ${String(s.count).padStart(3)} 条  ${s.error ?? ''}`)
}
line(`查询词: ${res.queries.join(' | ')}`)
line(`候选总数: ${res.candidates.length}  用时 ${Date.now() - t0}ms`)

const sorted = sortCandidates(res.candidates)
line('')
line('先验排序后前 10:')
for (const c of sorted.slice(0, 10)) {
  line(`  [${(c.kind || '').padEnd(8)}] ${c.source.padEnd(8)} ${c.url.slice(0, 96)}`)
}

line('')
line('=== 2. 下载 + 去重 ===')
const outDir = path.join(os.tmpdir(), 'dsh-ref-test', Date.now().toString())
const t1 = Date.now()
const collected = await collectRefs({
  candidates: sorted,
  outDir,
  fsp,
  maxImages: 12,
  concurrency: 6,
  timeoutMs: 15000,
  onLog: (m) => line(`   ${m}`),
})
line(`尝试 ${collected.attempted}，成功 ${collected.images.length}，用时 ${Date.now() - t1}ms`)
line(`落盘目录: ${outDir}`)

let okSniff = 0
for (const im of collected.images) {
  const buf = await fsp.readFile(im.file)
  const kind = sniffImage(buf)
  const size = readSize(buf, kind?.ext)
  if (kind) okSniff += 1
  line(`  ${im.name.padEnd(12)} ${String(im.bytes).padStart(8)}B  ${size ? `${size.width}x${size.height}` : '?'}  ${im.source ?? ''}`)
}
line('')
line(`校验: ${okSniff}/${collected.images.length} 张魔数可识别`)

const total = collected.images.reduce((a, b) => a + b.bytes, 0)
line(`合计 ${(total / 1048576).toFixed(1)} MB`)
line('')
line(collected.images.length >= 6 ? 'PASS: 管线可用' : 'PARTIAL: 下载量偏少')
