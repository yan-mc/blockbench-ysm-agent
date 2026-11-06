/**
 * T2 安装执行器：内置 ComfyUI 便携版 + See-through 节点（docs/15）。
 *
 * 设计原则：
 *   1. **可恢复**：每步先检查产物是否已存在，存在就跳过（中断后可续）。
 *   2. **可预演**：默认只返回计划；必须显式 confirm 才真下载。
 *   3. **不静默失败**：每步失败都带回具体命令、退出码与输出尾部。
 *   4. **权重不在这里下**：See-through 权重由 ComfyUI 节点首次运行时自行从 HF 拉。
 *
 * 下载体积：ComfyUI 便携版约 1.8GB，pip 依赖约 2GB，节点几十 MB。
 */

import fs from 'node:fs'
import fsp from 'node:fs/promises'
import path from 'node:path'
import { execFile } from 'node:child_process'

export const COMFY_ZIP = 'https://github.com/comfyanonymous/ComfyUI/releases/latest/download/ComfyUI_windows_portable_nvidia.7z'
export const NODE_ZIP = 'https://github.com/jtydhr88/ComfyUI-See-through/archive/refs/heads/main.zip'
export const NODE_GIT = 'https://github.com/jtydhr88/ComfyUI-See-through.git'

/** 便携版解压后的根目录名（7z 内层）。 */
const PORTABLE_INNER = 'ComfyUI_windows_portable'

function run(cmd, args, opts = {}) {
  return new Promise((resolve) => {
    execFile(cmd, args, {
      timeout: opts.timeoutMs ?? 600000,
      cwd: opts.cwd,
      windowsHide: true,
      maxBuffer: 8 * 1024 * 1024,
    }, (error, stdout, stderr) => resolve({
      ok: !error,
      code: error?.code ?? 0,
      stdout: String(stdout ?? ''),
      stderr: String(stderr ?? ''),
      error: error ?? null,
    }))
  })
}

async function exists(p) { try { await fsp.access(p); return true } catch { return false } }

/** 下载到文件（带进度回调；支持已存在则跳过）。 */
async function download(url, dest, { onLog = () => {}, signal, expectMB } = {}) {
  if (await exists(dest)) {
    const st = await fsp.stat(dest)
    if (st.size > 1024) {
      onLog(`[install] 已存在，跳过下载: ${path.basename(dest)} (${(st.size / 1048576).toFixed(1)}MB)`)
      return { skipped: true, path: dest, bytes: st.size }
    }
  }
  await fsp.mkdir(path.dirname(dest), { recursive: true })
  onLog(`[install] 下载 ${url}${expectMB ? ` (~${expectMB}MB)` : ''}`)
  const res = await fetch(url, { signal, redirect: 'follow' })
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`)
  const total = Number(res.headers.get('content-length') || 0)
  const tmp = `${dest}.part`
  const fh = await fsp.open(tmp, 'w')
  let got = 0
  let lastLog = 0
  try {
    for await (const chunk of res.body) {
      await fh.write(chunk)
      got += chunk.length
      const mb = got / 1048576
      if (mb - lastLog >= 50) { onLog(`[install]   ${mb.toFixed(0)}MB${total ? ` / ${(total / 1048576).toFixed(0)}MB` : ''}`); lastLog = mb }
    }
  } finally {
    await fh.close()
  }
  await fsp.rename(tmp, dest)
  onLog(`[install] 完成 ${path.basename(dest)} (${(got / 1048576).toFixed(1)}MB)`)
  return { skipped: false, path: dest, bytes: got }
}

/** 探测已装好的产物。 */
export async function inspectInstall(installDir) {
  const portable = path.join(installDir, PORTABLE_INNER)
  const python = path.join(portable, 'python_embeded', 'python.exe')
  const comfyMain = path.join(portable, 'ComfyUI', 'main.py')
  const nodeDir = path.join(portable, 'ComfyUI', 'custom_nodes', 'ComfyUI-See-through')
  return {
    dir: installDir,
    portableExists: await exists(portable),
    pythonExists: await exists(python),
    comfyExists: await exists(comfyMain),
    nodeExists: await exists(nodeDir),
    python, comfyMain, nodeDir, portable,
  }
}

/**
 * 执行安装。逐步骤推进，已有产物跳过。
 * @returns {Promise<{ok:boolean, steps:object[], paths:object, error?:string}>}
 */
export async function runInstall(p = {}) {
  const installDir = p.installDir
  const onLog = p.onLog ?? (() => {})
  const steps = []
  const push = (id, ok, detail) => { steps.push({ id, ok, ...detail }); onLog(`[install] ${ok ? '✓' : '✗'} ${id} ${JSON.stringify(detail).slice(0, 200)}`); return ok }
  if (!installDir) return { ok: false, steps, error: 'installDir required' }

  try {
    await fsp.mkdir(installDir, { recursive: true })
    const st0 = await inspectInstall(installDir)

    // 1) 下载 ComfyUI 便携版
    const archive = path.join(installDir, 'ComfyUI_windows_portable_nvidia.7z')
    if (!st0.portableExists) {
      await download(COMFY_ZIP, archive, { onLog, signal: p.signal, expectMB: 1800 })
      push('download-comfy', true, { file: path.basename(archive) })
    } else {
      push('download-comfy', true, { skipped: true, reason: 'portable 已存在' })
    }

    // 2) 解压
    const st1 = await inspectInstall(installDir)
    if (!st1.portableExists) {
      onLog('[install] 解压（tar/bsdtar 支持 7z；不支持则需手动解压）...')
      const ex = await run('tar', ['-xf', archive, '-C', installDir], { timeoutMs: 1800000 })
      if (!ex.ok) {
        push('extract', false, { code: ex.code, stderr: ex.stderr.slice(-500) })
        return { ok: false, steps, paths: st1, error: '解压失败：Windows 自带 tar 不支持 7z 时请手动解压或用 7-Zip' }
      }
      push('extract', true, {})
    } else {
      push('extract', true, { skipped: true })
    }

    const st2 = await inspectInstall(installDir)
    if (!st2.comfyExists) {
      push('verify-comfy', false, { expect: st2.comfyMain })
      return { ok: false, steps, paths: st2, error: '解压后没找到 ComfyUI/main.py' }
    }
    push('verify-comfy', true, {})

    // 3) See-through 节点（优先 git clone，退回 zip）
    if (!st2.nodeExists) {
      const git = await run('git', ['clone', '--depth', '1', NODE_GIT, st2.nodeDir], { timeoutMs: 300000 })
      if (git.ok) {
        push('install-node', true, { method: 'git' })
      } else {
        onLog('[install] git 不可用，改用 zip 下载节点')
        const nodeZip = path.join(installDir, 'ComfyUI-See-through.zip')
        await download(NODE_ZIP, nodeZip, { onLog, signal: p.signal })
        const ex = await run('tar', ['-xf', nodeZip, '-C', installDir], { timeoutMs: 300000 })
        if (!ex.ok) { push('install-node', false, { stderr: ex.stderr.slice(-300) }); return { ok: false, steps, paths: st2, error: '节点解压失败' } }
        const src = path.join(installDir, 'ComfyUI-See-through-main')
        await fsp.mkdir(path.dirname(st2.nodeDir), { recursive: true })
        await fsp.rename(src, st2.nodeDir).catch(async () => {
          await fsp.cp(src, st2.nodeDir, { recursive: true })
          await fsp.rm(src, { recursive: true, force: true })
        })
        push('install-node', true, { method: 'zip' })
      }
    } else {
      push('install-node', true, { skipped: true })
    }

    // 4) 依赖
    const req = path.join(st2.nodeDir, 'requirements.txt')
    if (await exists(req)) {
      onLog('[install] pip install（diffusers/accelerate 等，约 2GB）...')
      const pip = await run(st2.python, ['-m', 'pip', 'install', '--quiet', '-r', req], { timeoutMs: 3600000, cwd: st2.nodeDir })
      push('install-deps', pip.ok, pip.ok ? {} : { stderr: pip.stderr.slice(-500) })
      if (!pip.ok) return { ok: false, steps, paths: st2, error: 'pip install 失败' }
    } else {
      push('install-deps', true, { skipped: true, reason: '无 requirements.txt' })
    }

    const st3 = await inspectInstall(installDir)
    return {
      ok: true,
      steps,
      paths: {
        ...st3,
        startCommand: `"${path.join(st3.portable, 'python_embeded', 'python.exe')}" -s "${st3.comfyMain}" --listen 127.0.0.1 --port 8188`,
        comfyUrl: 'http://127.0.0.1:8188',
      },
    }
  } catch (error) {
    return { ok: false, steps, error: error?.message ?? String(error) }
  }
}
