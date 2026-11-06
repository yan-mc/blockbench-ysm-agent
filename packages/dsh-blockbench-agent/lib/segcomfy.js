/**
 * T2 调用层：通过 ComfyUI HTTP API 跑 See-through 分层（docs/16）。
 *
 * 管道（节点签名来自 `/object_info` 实测）：
 *   LoadImage → GenerateLayers(layerdiff_model) → GenerateDepth(depth_model)
 *             → PostProcess(tblr_split/use_lama) → SaveImage(preview) + SavePSD
 *
 * 注意：**首次运行会下载约 3GB 权重**（节点 auto_download），所以等待时间要给足。
 */

import fs from 'node:fs'
import fsp from 'node:fs/promises'
import path from 'node:path'
import { randomBytes } from 'node:crypto'

export const DEFAULT_RESOLUTION = 832   // 12GB 显存推荐；显存 >=16GB 可上 1024

function url(base, p) { return `${base.replace(/\/+$/, '')}${p}` }

async function jfetch(u, opts = {}, timeoutMs = 60000) {
  const ac = new AbortController()
  const timer = setTimeout(() => ac.abort(), timeoutMs)
  try {
    const res = await fetch(u, { ...opts, signal: ac.signal })
    const text = await res.text()
    let json = null
    try { json = JSON.parse(text) } catch { /* not json */ }
    return { ok: res.ok, status: res.status, json, text }
  } finally { clearTimeout(timer) }
}

/** POST /upload/image：把本地图送进 ComfyUI 的 input 目录。 */
export async function uploadImage(comfyUrl, absPath, { subfolder = 'seethrough', signal } = {}) {
  const buf = await fsp.readFile(absPath)
  const name = `${path.basename(absPath, path.extname(absPath))}-${randomBytes(3).toString('hex')}${path.extname(absPath)}`
  const form = new FormData()
  form.append('image', new Blob([buf]), name)
  form.append('overwrite', 'true')
  form.append('subfolder', subfolder)
  const r = await jfetch(url(comfyUrl, '/upload/image'), { method: 'POST', body: form, signal }, 120000)
  if (!r.ok || !r.json) throw new Error(`upload failed: HTTP ${r.status} ${r.text.slice(0, 200)}`)
  return { name: r.json.name, subfolder: r.json.subfolder ?? '', type: r.json.type ?? 'input' }
}

/**
 * 构建工作流。字符串节点 id 便于定位。
 * @param {object} o
 * @param {string} o.image       LoadImage 用的文件名（含 subfolder 前缀时的写法见 ComfyUI 约定）
 * @param {number} [o.resolution]
 * @param {number} [o.steps]
 * @param {number} [o.seed]
 * @param {boolean} [o.tblrSplit=true]  上/下/左/右拆分
 * @param {boolean} [o.useLama=false]   遮挡补全用 LaMa
 * @param {boolean} [o.headDetail=true] 头部细分（GenerateLayers 的 head 阶段开关在本版本由 PostProcess 控制）
 */
export function buildWorkflow(o = {}) {
  const seed = Number.isFinite(o.seed) ? o.seed : Math.floor(Math.random() * 1e9)
  const resolution = o.resolution ?? DEFAULT_RESOLUTION
  const steps = o.steps ?? 28
  const imageRef = o.subfolder ? `${o.subfolder}/${o.image}` : o.image
  const wf = {
    '1': { class_type: 'LoadImage', inputs: { image: imageRef } },
    '2': {
      class_type: 'SeeThrough_LoadLayerDiffModel',
      inputs: {
        model: o.layerdiffModel ?? 'layerdifforg/seethroughv0.0.2_layerdiff3d',
        quant_mode: o.quantMode ?? 'none',
        cache_tag_embeds: true,
        group_offload: false,
        auto_download: true,
      },
    },
    '3': {
      class_type: 'SeeThrough_LoadDepthModel',
      inputs: {
        model: o.depthModel ?? 'layerdifforg/seethroughv0.0.1_marigold',
        quant_mode: o.quantMode ?? 'none',
        cache_tag_embeds: true,
        group_offload: false,
        auto_download: true,
      },
    },
    '4': {
      class_type: 'SeeThrough_GenerateLayers',
      inputs: {
        image: ['1', 0],
        layerdiff_model: ['2', 0],
        seed,
        resolution,
        num_inference_steps: steps,
      },
    },
    '5': {
      class_type: 'SeeThrough_GenerateDepth',
      inputs: { layers: ['4', 0], depth_model: ['3', 0], seed },
    },
    '6': {
      class_type: 'SeeThrough_PostProcess',
      inputs: { layers_depth: ['5', 0], tblr_split: o.tblrSplit !== false, use_lama: o.useLama === true },
    },
    // 注意：filename_prefix **不要带子目录**。SeeThrough_SavePSD 不会自动建目录，
    // 实测 prefix='seethrough/decomp' 会直接 FileNotFoundError（推理其实已经跑完）。
    '7': { class_type: 'SeeThrough_SavePSD', inputs: { parts: ['6', 0], filename_prefix: o.prefix ?? 'seethrough_decomp' } },
    // 把 PostProcess 的预览接进 SaveImage，才能通过 /history 拿到可下载的图
    '8': { class_type: 'SaveImage', inputs: { images: ['6', 1], filename_prefix: o.previewPrefix ?? 'seethrough_preview' } },
  }
  return { workflow: wf, seed, resolution }
}

/** POST /prompt 入队，返回 prompt_id。 */
export async function queuePrompt(comfyUrl, workflow, { signal } = {}) {
  const clientId = randomBytes(8).toString('hex')
  const r = await jfetch(url(comfyUrl, '/prompt'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt: workflow, client_id: clientId }),
    signal,
  }, 60000)
  if (!r.ok || !r.json?.prompt_id) {
    throw new Error(`queue failed: HTTP ${r.status} ${(r.text || '').slice(0, 400)}`)
  }
  return { promptId: r.json.prompt_id, clientId }
}

/** 轮询 /history 直到完成。 */
export async function waitForPrompt(comfyUrl, promptId, { timeoutMs = 3600000, pollMs = 5000, onLog = () => {}, signal } = {}) {
  const t0 = Date.now()
  let lastNote = 0
  while (Date.now() - t0 < timeoutMs) {
    if (signal?.aborted) throw new Error('aborted')
    const r = await jfetch(url(comfyUrl, `/history/${promptId}`), {}, 30000)
    if (r.ok && r.json && r.json[promptId]) {
      const entry = r.json[promptId]
      const status = entry.status ?? {}
      if (status.status_str === 'error' || status.completed === false && status.messages?.some?.((m) => String(m?.[0]).includes('error'))) {
        throw new Error(`comfyui job error: ${JSON.stringify(status).slice(0, 600)}`)
      }
      if (entry.outputs) return { outputs: entry.outputs, elapsedMs: Date.now() - t0 }
    }
    const sec = Math.round((Date.now() - t0) / 1000)
    if (sec - lastNote >= 30) { onLog(`[comfy] 等待中 ${sec}s（首次运行要下约 3GB 权重）`); lastNote = sec }
    await new Promise((r2) => setTimeout(r2, pollMs))
  }
  throw new Error(`timeout after ${Math.round(timeoutMs / 1000)}s`)
}

/** 从 /history outputs 里挑出保存的图片并下载。 */
export async function fetchOutputImages(comfyUrl, outputs, outDir) {
  await fsp.mkdir(outDir, { recursive: true })
  const saved = []
  for (const [nodeId, out] of Object.entries(outputs ?? {})) {
    for (const im of out.images ?? []) {
      const q = new URLSearchParams({ filename: im.filename, subfolder: im.subfolder ?? '', type: im.type ?? 'output' })
      const res = await fetch(url(comfyUrl, `/view?${q.toString()}`))
      if (!res.ok) continue
      const buf = Buffer.from(await res.arrayBuffer())
      const dest = path.join(outDir, im.filename)
      await fsp.writeFile(dest, buf)
      saved.push({ node: nodeId, filename: im.filename, path: dest, bytes: buf.length })
    }
  }
  return saved
}

/** 探测 ComfyUI 是否活着（轻量）。 */
export async function pingComfy(comfyUrl, { timeoutMs = 5000 } = {}) {
  try {
    const r = await jfetch(url(comfyUrl, '/system_stats'), {}, timeoutMs)
    if (!r.ok || !r.json) return { ok: false, status: r.status }
    return {
      ok: true,
      version: r.json.system?.comfyui_version ?? null,
      devices: r.json.system?.devices ?? r.json.devices ?? null,
    }
  } catch (error) {
    return { ok: false, error: error?.message ?? String(error) }
  }
}

/** 列出已安装的自定义节点（确认 See-through 在不在）。 */
export async function listSeeThroughNodes(comfyUrl) {
  const r = await jfetch(url(comfyUrl, '/object_info'), {}, 60000)
  if (!r.ok || !r.json) return []
  return Object.keys(r.json).filter((k) => k.startsWith('SeeThrough_'))
}
