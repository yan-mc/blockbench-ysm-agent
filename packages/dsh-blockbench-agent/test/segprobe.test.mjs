// 分层能力分级（P3）单元测试：不依赖真实 GPU，用纯函数 computeTiers
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { computeTiers, planInstall, SIZE_ESTIMATE, COMFY_PORTABLE, SEETHROUGH_NODE } from '../lib/segprobe.js'

const RTX4080 = { name: 'NVIDIA GeForce RTX 4080 Laptop GPU', vramMiB: 12282, vramGB: 12, driver: '621.14', legacy: false }
const RTX3060 = { name: 'NVIDIA GeForce RTX 3060', vramMiB: 12288, vramGB: 12, driver: '5xx', legacy: false }
const RTX2060 = { name: 'NVIDIA GeForce RTX 2060', vramMiB: 6144, vramGB: 6, driver: '5xx', legacy: false }
const GTX1060 = { name: 'NVIDIA GeForce GTX 1060', vramMiB: 6144, vramGB: 6, driver: '4xx', legacy: true }

test('有足够显存 + 磁盘 + Windows -> T2 可用', () => {
  const r = computeTiers({ gpus: [RTX4080], diskGB: 400, platform: 'win32' })
  assert.equal(r.tiers.t2.ok, true, JSON.stringify(r.tiers.t2.reasons))
  assert.equal(r.recommendedTier, 't2')
  assert.equal(r.tiers.t2.recommendedResolution, 1024)
})

test('没有 N 卡 -> T2 不可用，退回 T0', () => {
  const r = computeTiers({ gpus: [], diskGB: 400, platform: 'win32' })
  assert.equal(r.tiers.t2.ok, false)
  assert.equal(r.recommendedTier, 't0')
  assert.ok(r.tiers.t2.reasons.some((s) => /NVIDIA/.test(s)))
})

test('Pascal（GTX 10xx）被拒绝（NF4 量化不支持）', () => {
  const r = computeTiers({ gpus: [GTX1060], diskGB: 400, platform: 'win32' })
  assert.equal(r.tiers.t2.ok, false)
  assert.ok(r.tiers.t2.reasons.some((s) => /Pascal/.test(s)))
})

test('显存不足 6GB 被拒绝', () => {
  const small = { name: 'NVIDIA GeForce RTX 3050', vramMiB: 4096, vramGB: 4, driver: '5xx', legacy: false }
  const r = computeTiers({ gpus: [small], diskGB: 400, platform: 'win32' })
  assert.equal(r.tiers.t2.ok, false)
  assert.ok(r.tiers.t2.reasons.some((s) => /显存/.test(s)))
})

test('磁盘不足被拒绝', () => {
  const r = computeTiers({ gpus: [RTX4080], diskGB: 5, platform: 'win32' })
  assert.equal(r.tiers.t2.ok, false)
  assert.ok(r.tiers.t2.reasons.some((s) => /剩余/.test(s)))
})

test('非 Windows 被拒绝（内置安装器只覆盖 Windows）', () => {
  const r = computeTiers({ gpus: [RTX4080], diskGB: 400, platform: 'linux' })
  assert.equal(r.tiers.t2.ok, false)
  assert.ok(r.tiers.t2.reasons.some((s) => /Windows/.test(s)))
})

test('显存区间决定推荐分辨率', () => {
  assert.equal(computeTiers({ gpus: [RTX4080], diskGB: 400, platform: 'win32' }).tiers.t2.recommendedResolution, 1024)
  const mid = { name: 'RTX 3070', vramMiB: 8192, vramGB: 8, legacy: false }
  assert.equal(computeTiers({ gpus: [mid], diskGB: 400, platform: 'win32' }).tiers.t2.recommendedResolution, 768)
  assert.equal(computeTiers({ gpus: [RTX2060], diskGB: 400, platform: 'win32' }).tiers.t2.recommendedResolution, 512)
})

test('T0/T1 永远可用', () => {
  const r = computeTiers({ gpus: [], diskGB: 1, platform: 'darwin' })
  assert.equal(r.tiers.t0.ok, true)
  assert.equal(r.tiers.t1.ok, true)
})

test('T3（云端）配置了 key 时优先级高于 T2：recommendedTier=t3', () => {
  const r = computeTiers({ gpus: [RTX4080], diskGB: 400, platform: 'win32', t3: { ok: true, model: 'gemini-3-pro-image' } })
  assert.equal(r.tiers.t3.ok, true)
  assert.equal(r.tiers.t2.ok, true)
  assert.equal(r.recommendedTier, 't3')
})

test('T3 没 key 时回落本地 T2；T2 也没有则继续回落', () => {
  const withGpu = computeTiers({ gpus: [RTX4080], diskGB: 400, platform: 'win32', t3: { ok: false, reasons: ['no key'] } })
  assert.equal(withGpu.tiers.t3.ok, false)
  assert.equal(withGpu.recommendedTier, 't2')
  assert.match(withGpu.tiers.t3.reasons[0], /no key/)

  const noGpu = computeTiers({ gpus: [], diskGB: 400, platform: 'win32' })
  assert.equal(noGpu.tiers.t3.ok, false)
  assert.equal(noGpu.recommendedTier, 't0')
})

test('planInstall 给出完整步骤与体积估算', () => {
  const probe = {
    platform: 'win32',
    disk: { target: 'D:\\ai', freeGB: 400 },
    bestGpu: { name: RTX4080.name, vramGB: 12 },
    tiers: { t2: { ok: true, reasons: [] } },
  }
  const plan = planInstall(probe)
  assert.equal(plan.canInstall, true)
  assert.equal(plan.installDir, 'D:\\ai')
  const ids = plan.steps.map((s) => s.id)
  for (const want of ['check', 'download-comfy', 'extract', 'install-node', 'install-deps', 'register', 'first-run']) {
    assert.ok(ids.includes(want), `缺步骤 ${want}`)
  }
  // 权重是首次运行时下载，不应算进安装体积步骤里重复计
  assert.ok(plan.totalGB >= SIZE_ESTIMATE.comfyPortable + SIZE_ESTIMATE.seeThroughWeights)
  assert.match(COMFY_PORTABLE.win32, /ComfyUI_windows_portable_nvidia\.7z$/)
  assert.match(SEETHROUGH_NODE, /ComfyUI-See-through/)
})

test('planInstall 在环境不支持时给 blockers 且 canInstall=false', () => {
  const probe = { platform: 'linux', disk: { target: '/opt/x', freeGB: 10 }, bestGpu: null, tiers: { t2: { ok: false, reasons: ['未检测到 NVIDIA GPU'] } } }
  const plan = planInstall(probe)
  assert.equal(plan.canInstall, false)
  assert.ok(plan.blockers.length > 0)
})
