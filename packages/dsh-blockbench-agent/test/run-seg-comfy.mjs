#!/usr/bin/env node
// T2 分层端到端正测（后台跑用，与 bb_seg_run 同一套 lib/segcomfy.js）
// 用法: node packages/dsh-blockbench-agent/test/run-seg-comfy.mjs <图片绝对路径> [分辨率]

import fs from 'node:fs'
import fsp from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  pingComfy, listSeeThroughNodes, uploadImage, buildWorkflow,
  queuePrompt, waitForPrompt, fetchOutputImages,
} from '../lib/segcomfy.js'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const REPO = path.resolve(HERE, '..', '..', '..')
const COMFY = process.env.COMFY_URL || 'http://127.0.0.1:8188'
const OUT = path.join(REPO, 'workspace', '_seethrough')

const image = process.argv[2]
const resolution = Number(process.argv[3]) || 832
if (!image || !fs.existsSync(image)) { console.error('图片不存在:', image); process.exit(2) }

const t0 = Date.now()
const log = (...a) => console.log(`[${((Date.now() - t0) / 1000).toFixed(1)}s]`, ...a)

log('comfy:', COMFY)
const ping = await pingComfy(COMFY)
log('ping:', JSON.stringify(ping))
if (!ping.ok) { console.error('ComfyUI 不可达'); process.exit(3) }

const nodes = await listSeeThroughNodes(COMFY)
log('SeeThrough 节点:', nodes.length, nodes.join(', '))
if (!nodes.length) { console.error('没装 See-through 节点'); process.exit(4) }

const up = await uploadImage(COMFY, image, { subfolder: 'seethrough' })
log('uploaded:', JSON.stringify(up))

const { workflow, seed, resolution: res } = buildWorkflow({
  image: up.name, subfolder: up.subfolder, resolution,
})
log(`workflow: ${Object.keys(workflow).length} 节点, seed=${seed}, resolution=${res}`)

const { promptId } = await queuePrompt(COMFY, workflow)
log('queued:', promptId)

const { outputs, elapsedMs } = await waitForPrompt(COMFY, promptId, {
  timeoutMs: 3600000, pollMs: 5000, onLog: (m) => log(m),
})
log(`完成，用时 ${(elapsedMs / 1000).toFixed(1)}s`)
log('outputs 节点:', Object.keys(outputs).join(', '))

const images = await fetchOutputImages(COMFY, outputs, OUT)
log('下载图片:', images.length)
for (const im of images) log('  ', im.filename, `${(im.bytes / 1024).toFixed(0)}KB`)

// 列出 ComfyUI 输出目录里的分层产物（SavePSD 写盘，不在 /history 里）
const outDir = path.join('C:\\Users\\28988\\.dsh-seethrough\\ComfyUI_windows_portable\\ComfyUI', 'output', 'seethrough')
let files = []
try {
  files = (await fsp.readdir(outDir)).slice(0, 60)
} catch { /* ignore */ }
log('SavePSD 输出目录文件数:', files.length)

console.log(JSON.stringify({
  ok: true, promptId, seed, resolution: res, elapsedMs,
  images: images.map((i) => ({ filename: i.filename, path: i.path, bytes: i.bytes })),
  outputFiles: files,
}, null, 2))
process.exit(0)
