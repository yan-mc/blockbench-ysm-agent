/**
 * T1 轻量分割：SAM2.1 ONNX 自动部件分割（docs/14）。
 *
 * 架构选择：**跑 Python，而不是给插件加原生 Node 依赖**。
 *   - `onnxruntime-node` 是原生模块（含多平台二进制，100MB+），分发到别人机器上容易炸；
 *   - DSH 自带 Python，`pip install onnxruntime` 约 15MB，跨平台稳；
 *   - 走子进程 + JSON，边界清晰，失败不影响宿主。
 *
 * 模型（SAM2.1 hiera-tiny int8，共约 59MB）**不在包里**，首次使用下载到用户缓存目录。
 */

import fs from 'node:fs'
import fsp from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { execFile, spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
/** 插件根（lib/ 的上一级）。 */
export const PLUGIN_ROOT = path.resolve(HERE, '..')
export const SEG_SCRIPT = path.join(PLUGIN_ROOT, 'assets', 'seg_sam2.py')

const HF = 'https://huggingface.co/onnx-community/sam2.1-hiera-tiny-ONNX/resolve/main/onnx'
/** 需要下载的模型文件（相对路径: 目标文件名）。 */
export const SEG_MODEL_FILES = [
  ['vision_encoder_int8.onnx', 0.4],
  ['vision_encoder_int8.onnx_data', 50.1],
  ['prompt_encoder_mask_decoder_int8.onnx', 0.3],
  ['prompt_encoder_mask_decoder_int8.onnx_data', 8.3],
]
export const SEG_MODEL_TOTAL_MB = SEG_MODEL_FILES.reduce((a, [, mb]) => a + mb, 0)

/** 常见 Python 位置（DSH 自带优先）。 */
export function pythonCandidates() {
  const list = []
  if (process.env.DSH_PYTHON) list.push(process.env.DSH_PYTHON)
  // DSH 运行时自带的 python
  const dshRoot = process.env.DSH_RUNTIME_ROOT
  if (dshRoot) list.push(path.join(dshRoot, 'dependencies', 'python', 'python.exe'))
  const home = os.homedir()
  list.push(
    path.join(home, '.dsh', 'dsh-runtimes', 'dsh-primary-runtime', 'dependencies', 'python', 'python.exe'),
    path.join(home, '.dsh', 'dsh-runtimes', 'dsh-primary-runtime', 'dependencies', 'python', 'bin', 'python3'),
    'python.exe', 'python3', 'python',
  )
  return list
}

function runFile(cmd, args, opts = {}) {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout: opts.timeoutMs ?? 20000, windowsHide: true, maxBuffer: 4 * 1024 * 1024 },
      (error, stdout, stderr) => resolve({
        ok: !error, code: error?.code ?? 0, stdout: String(stdout ?? ''), stderr: String(stderr ?? ''),
        error: error ?? null,
      }))
  })
}

/** 找到一个可用且装了 onnxruntime 的 python。 */
export async function findPython(explicit) {
  const cands = explicit ? [explicit, ...pythonCandidates()] : pythonCandidates()
  for (const c of cands) {
    if (!c) continue
    if ((c.includes(path.sep) || c.endsWith('.exe')) && !fs.existsSync(c)) continue
    const r = await runFile(c, ['-c', 'import sys,onnxruntime,numpy,PIL;print(sys.executable);print(onnxruntime.__version__)'])
    if (r.ok) {
      const [exe, ortVersion] = r.stdout.trim().split(/\r?\n/)
      return { ok: true, exe: exe || c, ortVersion: ortVersion ?? null }
    }
  }
  return { ok: false }
}

/** 模型是否已下载完整。 */
export async function modelsReady(dir) {
  for (const [name] of SEG_MODEL_FILES) {
    const p = path.join(dir, name)
    if (!fs.existsSync(p)) return { ok: false, missing: name }
  }
  return { ok: true }
}

/** 下载缺失模型（带进度日志）。 */
export async function downloadModels(dir, { onLog = () => {}, signal } = {}) {
  await fsp.mkdir(dir, { recursive: true })
  const fetched = []
  for (const [name, mb] of SEG_MODEL_FILES) {
    const out = path.join(dir, name)
    if (fs.existsSync(out) && fs.statSync(out).size > 1024) { fetched.push({ name, skipped: true }); continue }
    onLog(`[sam2] 下载 ${name} (${mb}MB)...`)
    const res = await fetch(`${HF}/${name}`, { signal })
    if (!res.ok) throw new Error(`下载 ${name} 失败: HTTP ${res.status}`)
    const buf = Buffer.from(await res.arrayBuffer())
    await fsp.writeFile(out, buf)
    fetched.push({ name, bytes: buf.length })
    onLog(`[sam2] ${name} ok (${(buf.length / 1048576).toFixed(1)}MB)`)
  }
  return fetched
}

/** pip 安装 onnxruntime（有时是首次使用）。 */
export async function ensureOnnxruntime(pythonExe, { onLog = () => {} } = {}) {
  const probe = await runFile(pythonExe, ['-c', 'import onnxruntime;print(onnxruntime.__version__)'])
  if (probe.ok) return { ok: true, version: probe.stdout.trim(), installed: false }
  onLog('[sam2] 安装 onnxruntime ...')
  const r = await runFile(pythonExe, ['-m', 'pip', 'install', '--quiet', 'onnxruntime'], { timeoutMs: 600000 })
  if (!r.ok) return { ok: false, error: r.stderr.slice(-400) }
  const again = await runFile(pythonExe, ['-c', 'import onnxruntime;print(onnxruntime.__version__)'])
  return again.ok ? { ok: true, version: again.stdout.trim(), installed: true } : { ok: false, error: again.stderr.slice(-400) }
}

/**
 * 跑一次分割。
 * @returns {Promise<object>} 脚本输出的 JSON（含 parts / montage）
 */
export function runSegmentation(p = {}) {
  const args = [
    SEG_SCRIPT,
    '--model-dir', p.modelDir,
    '--image', p.image,
    '--out-dir', p.outDir,
    '--grid', String(p.grid ?? 12),
    '--max-parts', String(p.maxParts ?? 9),
  ]
  if (p.threads) args.push('--threads', String(p.threads))
  if (p.minArea != null) args.push('--min-area', String(p.minArea))
  if (p.minIou != null) args.push('--min-iou', String(p.minIou))
  return new Promise((resolve) => {
    const child = spawn(p.python, args, { windowsHide: true })
    let out = ''
    let err = ''
    const cap = 4 * 1024 * 1024
    child.stdout.on('data', (d) => { if (out.length < cap) out += d })
    child.stderr.on('data', (d) => { if (err.length < cap) err += d })
    if (p.signal) p.signal.addEventListener('abort', () => { try { child.kill('SIGKILL') } catch { /* ignore */ } }, { once: true })
    child.on('error', (e) => resolve({ ok: false, error: e?.message ?? String(e), stderr: err }))
    child.on('exit', (code) => {
      const line = out.trim().split(/\r?\n/).filter(Boolean).pop() ?? ''
      try {
        const json = JSON.parse(line)
        resolve({ ok: true, ...json, stderr: err })
      } catch {
        resolve({ ok: false, code, error: `无法解析脚本输出（exit ${code}）`, stdout: out.slice(-800), stderr: err.slice(-1200) })
      }
    })
  })
}
