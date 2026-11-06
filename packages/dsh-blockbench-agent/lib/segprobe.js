/**
 * See-through 分层能力探测与安装规划（docs/13）。
 *
 * 背景：See-through 能把单张立绘拆成带深度序的分层（body 13 层 + head 11 层），
 * 但它是 SDXL 级扩散管线，需要 NVIDIA GPU + 十几 GB 磁盘。插件要能给别人用，
 * 所以必须**先探测再决定**，而不是假设所有人都有卡。
 *
 * 能力分级（对应产品决策"可选增强"）：
 *   T0  零依赖：模型直接看立绘判断部件
 *   T1  轻量分割：SAM2 ONNX（约 50MB，CPU 可跑），只给可见部件掩膜
 *   T2  See-through：ComfyUI + LayerDiff/Marigold 权重，完整分层 + 遮挡补全
 *
 * 实测数据来源（社区文档）：
 *   512 → 约 5GB VRAM；768 → 约 5.5GB；1024 → 约 7GB；1280 → 约 9GB
 *   NF4 量化需要 Turing 及以后（RTX 20xx+ / GTX 16xx）；GTX 10xx 及更早不支持
 */

import fs from 'node:fs'
import fsp from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { execFile } from 'node:child_process'

/** ComfyUI Windows 便携版（官方 releases 直链）。 */
export const COMFY_PORTABLE = {
  win32: 'https://github.com/comfyanonymous/ComfyUI/releases/latest/download/ComfyUI_windows_portable_nvidia.7z',
  // 非 Windows 不内置安装，只提示手动方案
}
export const SEETHROUGH_NODE = 'https://github.com/jtydhr88/ComfyUI-See-through.git'
/** 估算体积（GB），用于磁盘检查与用户预期。 */
export const SIZE_ESTIMATE = {
  comfyPortable: 1.8,
  seeThroughWeights: 3.0,
  pythonDeps: 2.0,
  total: 7.0,
}

/** Pascal 及更早（GTX 10xx / 9xx / MX）不支持 NF4 量化。 */
const OLD_GPU = /\b(GTX\s*10\d\d|GTX\s*9\d\d|GT\s*\d{3}|MX\s*\d{3}|Quadro\s*[KMP]\d{3,4})\b/i

function run(cmd, args, { timeoutMs = 8000 } = {}) {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout: timeoutMs, windowsHide: true }, (error, stdout, stderr) => {
      resolve({ ok: !error, stdout: String(stdout ?? ''), stderr: String(stderr ?? ''), error })
    })
  })
}

/** nvidia-smi 查显卡。不存在/不是 N 卡时返回空数组。 */
export async function probeNvidia() {
  const r = await run('nvidia-smi', ['--query-gpu=name,memory.total,driver_version', '--format=csv,noheader,nounits'])
  if (!r.ok || !r.stdout.trim()) return []
  const gpus = []
  for (const line of r.stdout.trim().split(/\r?\n/)) {
    const parts = line.split(',').map((s) => s.trim())
    if (parts.length < 3) continue
    const vramMiB = Number(parts[1])
    if (!Number.isFinite(vramMiB)) continue
    gpus.push({
      name: parts[0],
      vramMiB,
      vramGB: +(vramMiB / 1024).toFixed(1),
      driver: parts[2],
      legacy: OLD_GPU.test(parts[0]),
    })
  }
  return gpus
}

/** 目标盘剩余空间（GB）；statfs 不可用时返回 null。 */
export async function freeDiskGB(dir) {
  try {
    let probe = dir
    while (probe && !fs.existsSync(probe)) probe = path.dirname(probe)
    if (!probe) return null
    const st = await fsp.statfs(probe)
    return +((st.bavail * st.bsize) / 1024 ** 3).toFixed(1)
  } catch {
    return null
  }
}

/** ComfyUI 是否可达（配置里的地址）。 */
export async function probeComfy(url, { timeoutMs = 3000 } = {}) {
  if (!url) return { configured: false, reachable: false }
  const base = String(url).replace(/\/+$/, '')
  try {
    const ac = new AbortController()
    const timer = setTimeout(() => ac.abort(), timeoutMs)
    try {
      const res = await fetch(`${base}/system_stats`, { signal: ac.signal })
      if (!res.ok) return { configured: true, reachable: false, url: base, status: res.status }
      const data = await res.json().catch(() => null)
      return {
        configured: true,
        reachable: true,
        url: base,
        devices: data?.devices?.map((d) => ({
          name: d.name, vramTotal: d.vram_total, vramFree: d.vram_free,
        })) ?? null,
        comfyVersion: data?.system?.comfyui_version ?? null,
      }
    } finally { clearTimeout(timer) }
  } catch (error) {
    return { configured: true, reachable: false, url: base, error: error?.message ?? String(error) }
  }
}

/**
 * 纯函数：由观测事实推导能力分级。抽出来是为了可单测（不依赖真实 GPU）。
 * @param {object} f
 * @param {Array} [f.gpus]       probeNvidia() 结果
 * @param {number|null} [f.diskGB]
 * @param {string} [f.platform]
 * @param {object} [f.comfy]     probeComfy() 结果
 */
export function computeTiers(f = {}) {
  const gpus = Array.isArray(f.gpus) ? f.gpus : []
  const diskGB = f.diskGB ?? null
  const platform = f.platform ?? process.platform

  const best = gpus.slice().sort((a, b) => (b.vramMiB ?? 0) - (a.vramMiB ?? 0))[0] ?? null
  const isNvidia = Boolean(best)
  const legacy = best?.legacy ?? false
  const vramGB = best?.vramGB ?? 0

  const reasons = []
  if (!isNvidia) reasons.push('未检测到 NVIDIA GPU（nvidia-smi 不可用）')
  if (isNvidia && legacy) reasons.push(`显卡 ${best.name} 属 Pascal 或更早，不支持 NF4 量化`)
  if (isNvidia && vramGB > 0 && vramGB < 6) reasons.push(`显存 ${vramGB}GB 低于最低 6GB`)
  if (diskGB !== null && diskGB < SIZE_ESTIMATE.total + 5) {
    reasons.push(`目标盘剩余 ${diskGB}GB，不足（约需 ${SIZE_ESTIMATE.total}GB + 余量）`)
  }
  if (platform !== 'win32') reasons.push('内置安装器目前只覆盖 Windows（Linux/macOS 需手动装 ComfyUI）')

  const tier2ok = reasons.length === 0
  const recommendedResolution = vramGB >= 11 ? 1024 : vramGB >= 7 ? 768 : 512

  const tiers = {
    t0: { ok: true, label: '零依赖', desc: '模型直接看立绘判断部件（无分层）' },
    t1: {
      ok: true,
      label: '轻量分割',
      desc: 'SAM2 ONNX 约 50MB，只给可见部件掩膜，遮挡处靠对称推断',
      note: '可随时加装，无需 GPU 专属能力',
    },
    t2: {
      ok: tier2ok,
      label: 'See-through 完整分层',
      desc: '24 层（body 13 + head 11）+ 深度序 + 遮挡补全 + PSD',
      reasons,
      recommendedResolution,
      estimateGB: SIZE_ESTIMATE.total,
    },
  }

  return {
    tiers,
    bestGpu: best ? { name: best.name, vramGB, driver: best.driver, legacy } : null,
    recommendedTier: tier2ok ? 't2' : (isNvidia ? 't1' : 't0'),
  }
}

/**
 * 综合探测。
 * @param {object} p
 * @param {string} p.installDir   计划安装目录（用于磁盘检查）
 * @param {string} [p.comfyUrl]
 * @returns {Promise<object>} 报告
 */
export async function probeEnvironment(p = {}) {
  const installDir = p.installDir || path.join(os.homedir(), '.dsh-seethrough')
  const [gpus, diskGB, comfy] = await Promise.all([
    probeNvidia(),
    freeDiskGB(installDir),
    probeComfy(p.comfyUrl),
  ])

  const { tiers, bestGpu, recommendedTier } = computeTiers({ gpus, diskGB, platform: process.platform })

  return {
    ok: true,
    platform: process.platform,
    arch: process.arch,
    node: process.version,
    gpus,
    bestGpu,
    disk: { target: installDir, freeGB: diskGB },
    comfy,
    tiers,
    recommendedTier,
    hint: tiers.t2.ok
      ? '可以直接装 T2；也可以先用 T0 建，需要精细分层时再装'
      : 'T2 不可用，走 T1/T0；如需分层请在支持 NVIDIA 的机器上安装',
  }
}

/**
 * 生成安装计划（不执行）。
 * @param {object} probe  probeEnvironment 的结果
 * @param {object} [opt]
 * @param {string} [opt.installDir]
 */
export function planInstall(probe, opt = {}) {
  const installDir = opt.installDir || probe?.disk?.target || path.join(os.homedir(), '.dsh-seethrough')
  const steps = [
    {
      id: 'check',
      title: '环境复核',
      detail: `平台 ${probe.platform}/${probe.arch}；显存 ${probe.bestGpu?.vramGB ?? 0}GB；剩余磁盘 ${probe.disk?.freeGB ?? '?'}GB`,
      sizeGB: 0,
    },
    {
      id: 'download-comfy',
      title: '下载 ComfyUI 便携版',
      detail: COMFY_PORTABLE.win32,
      sizeGB: SIZE_ESTIMATE.comfyPortable,
      note: '官方 releases 直链；解压后自带 python_embeded，不需要单独装 Python',
    },
    {
      id: 'extract',
      title: '解压到安装目录',
      detail: `${installDir}`,
      sizeGB: 0,
      note: 'Windows 11 自带 tar(bsdtar) 支持 7z；不可用时提示手动解压',
    },
    {
      id: 'install-node',
      title: '安装 See-through 自定义节点',
      detail: `git clone ${SEETHROUGH_NODE} 到 ComfyUI/custom_nodes/ComfyUI-See-through`,
      sizeGB: 0.1,
    },
    {
      id: 'install-deps',
      title: '安装节点依赖',
      detail: 'python_embeded\\python.exe -m pip install -r requirements.txt（diffusers/accelerate 等 4 个包）',
      sizeGB: SIZE_ESTIMATE.pythonDeps,
    },
    {
      id: 'register',
      title: '写入插件配置',
      detail: 'comfyUrl = http://127.0.0.1:8188，安装路径写入 segInstallDir',
      sizeGB: 0,
    },
    {
      id: 'first-run',
      title: '首次运行下载权重（约 3GB，自动）',
      detail: 'ComfyUI-See-through 节点首次使用时自动从 HuggingFace 拉 LayerDiff(SDXL) 与 Marigold 深度权重',
      sizeGB: SIZE_ESTIMATE.seeThroughWeights,
      note: '这一步发生在真正跑分层时，不占安装时间',
    },
  ]
  return {
    ok: probe?.tiers?.t2?.ok !== false,
    installDir,
    steps,
    totalGB: SIZE_ESTIMATE.total,
    canInstall: probe?.tiers?.t2?.ok === true,
    blockers: probe?.tiers?.t2?.ok ? [] : (probe?.tiers?.t2?.reasons ?? ['环境不支持']),
  }
}
