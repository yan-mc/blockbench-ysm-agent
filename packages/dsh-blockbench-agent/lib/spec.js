/**
 * 建模规格（model spec）：把「看参考图得到的结论」固化成可校验、可复用、可驱动建模的结构化数据。
 *
 * 设计要点（docs/12）：
 *   1. spec 是**显式中间产物** —— 错了改 spec，不用重跑搜索/看图。
 *   2. 校验规则来自语料实测（docs/08）与操作规范（playbook），不是拍脑袋。
 *   3. `derivePlan` 把 spec 变成"按什么顺序建、每个骨骼给多少方块"，直接喂给 bb_* 工具。
 *   4. 缺背面参考时必须显式记录到 gaps —— 这条是产品决策，不是可选。
 */

export const SPEC_VERSION = 'ysm-model-spec/1'

/** 语料实测基线（docs/08）：人物方块中位 306，头部占比中位 33.2%。 */
export const BUDGET_BASELINE = {
  cubesTotal: 306,
  cubesMin: 50,
  cubesMax: 600,
  headShare: 0.332,
  headShareMin: 0.28,
  headShareMax: 0.48,
  textureSize: 512,
}

const HEX = /^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/

/** 部位 → 区域（用于算头部占比 / 决定构建顺序）。 */
const REGION_BY_ID = [
  [/hair|发|马尾|刘海/i, 'hair'],
  [/head|face|eye|brow|mouth|耳|头|脸|眼/i, 'head'],
  [/neck|颈/i, 'neck'],
  [/torso|body|chest|breast|waist|躯干|胸|腰/i, 'torso'],
  [/skirt|dress|coat|cloak|cape|裙|外套|披风/i, 'skirt'],
  [/arm|hand|sleeve|arm|袖|手|臂/i, 'arm'],
  [/leg|thigh|foot|shoe|sock|腿|脚|鞋|袜/i, 'leg'],
  [/accessor|ribbon|hat|earring|饰品|发饰|丝带/i, 'accessory'],
]

export function regionOf(part) {
  const hay = `${part.id ?? ''} ${part.bone ?? ''} ${part.name ?? ''}`
  for (const [re, region] of REGION_BY_ID) if (re.test(hay)) return region
  return part.region || 'other'
}

/** 构建顺序：先大形体，后细节，最后饰品。 */
const BUILD_ORDER = ['torso', 'leg', 'arm', 'head', 'hair', 'skirt', 'accessory', 'neck', 'other']

/** 部位 → 推荐父骨骼（YSM 标准骨架，见 playbook §4）。 */
const PARENT_BY_REGION = {
  torso: 'UpperBody',
  leg: 'DownBody',
  arm: 'UpBody',
  head: 'AllHead',
  hair: 'Head',
  skirt: 'DownBody',
  accessory: 'Head',
  neck: 'UpBody',
  other: 'Root',
}

function arr(v) { return Array.isArray(v) ? v : [] }

/** 规整 spec：补默认值、去 undefined、统一字段名。 */
export function normalizeSpec(input = {}) {
  const s = { ...input }
  s.spec = SPEC_VERSION
  s.character = { name: '', source: '', ...(s.character ?? {}) }
  s.references = { dir: '', images: [], ...(s.references ?? {}) }
  s.palette = arr(s.palette)
  s.parts = arr(s.parts).map((p) => ({
    id: String(p.id ?? ''),
    bone: String(p.bone ?? ''),
    cubes: Number(p.cubes) || 0,
    shape: p.shape ?? '',
    colors: arr(p.colors),
    refs: arr(p.refs).map(Number).filter((n) => Number.isFinite(n)),
    region: p.region ?? null,
  }))
  s.budget = { ...BUDGET_BASELINE, ...(s.budget ?? {}) }
  s.gaps = arr(s.gaps)
  s.notes = s.notes ?? ''
  return s
}

/**
 * 校验 spec。errors 阻碍建模；warnings 只是提醒。
 * @returns {{ok:boolean, errors:object[], warnings:object[], spec:object}}
 */
export function validateSpec(input = {}) {
  const spec = normalizeSpec(input)
  const errors = []
  const warnings = []

  if (!spec.character.name) errors.push({ code: 'CHARACTER_MISSING', message: 'character.name 必填' })
  if (!spec.parts.length) errors.push({ code: 'PARTS_EMPTY', message: 'parts 不能为空' })

  // 每个部位
  const seenId = new Set()
  for (const [i, p] of spec.parts.entries()) {
    if (!p.id) errors.push({ code: 'PART_ID_MISSING', message: `parts[${i}] 缺 id` })
    else if (seenId.has(p.id)) errors.push({ code: 'PART_ID_DUP', message: `parts[${i}] id 重复: ${p.id}` })
    else seenId.add(p.id)
    if (!p.bone) errors.push({ code: 'PART_BONE_MISSING', message: `parts[${i}](${p.id}) 缺 bone` })
    if (!(p.cubes > 0)) errors.push({ code: 'PART_CUBES_INVALID', message: `parts[${i}](${p.id}) cubes 必须 > 0` })
    for (const c of p.colors) {
      if (!spec.palette.some((x) => x.name === c)) {
        warnings.push({ code: 'COLOR_UNDEFINED', message: `parts[${i}](${p.id}) 引用了未在 palette 定义的色号 ${c}` })
      }
    }
    for (const r of p.refs) {
      if (!spec.references.images.length) break
      if (!spec.references.images.some((im) => Number(im.index) === r)) {
        warnings.push({ code: 'REF_INDEX_UNKNOWN', message: `parts[${i}](${p.id}) 引用了不存在的参考图 #${r}` })
      }
    }
  }

  // palette
  for (const [i, c] of spec.palette.entries()) {
    if (!c.name) errors.push({ code: 'PALETTE_NAME_MISSING', message: `palette[${i}] 缺 name` })
    if (!HEX.test(String(c.hex ?? ''))) errors.push({ code: 'PALETTE_HEX_INVALID', message: `palette[${i}](${c.name}) hex 非法: ${c.hex}` })
  }

  // 方块预算（对照语料）
  const total = spec.parts.reduce((a, p) => a + p.cubes, 0)
  const b = spec.budget
  if (total < b.cubesMin) warnings.push({ code: 'BUDGET_LOW', message: `方块总数 ${total} 低于语料下限 ${b.cubesMin}，细节可能不足` })
  if (total > b.cubesMax) warnings.push({ code: 'BUDGET_HIGH', message: `方块总数 ${total} 超过语料上限 ${b.cubesMax}，考虑"概括"而不是"雕"` })
  if (b.cubesTotal && Math.abs(total - b.cubesTotal) / b.cubesTotal > 0.4) {
    warnings.push({ code: 'BUDGET_DRIFT', message: `方块总数 ${total} 与预算 ${b.cubesTotal} 偏离超过 40%` })
  }

  // 头部占比（成品感主要来自头部）
  const headCubes = spec.parts.filter((p) => ['head', 'hair'].includes(regionOf(p))).reduce((a, p) => a + p.cubes, 0)
  const headShare = total ? headCubes / total : 0
  if (total && (headShare < b.headShareMin || headShare > b.headShareMax)) {
    warnings.push({
      code: 'HEAD_SHARE_OFF',
      message: `头部区域占比 ${(headShare * 100).toFixed(1)}%，语料区间 ${(b.headShareMin * 100).toFixed(0)}–${(b.headShareMax * 100).toFixed(0)}%（中位 ${(b.headShare * 100).toFixed(1)}%）；成品感主要来自头部`,
    })
  }

  // 贴图尺寸
  if (b.textureSize && b.textureSize < 256) {
    warnings.push({ code: 'TEXTURE_SMALL', message: `贴图 ${b.textureSize}px 偏小；语料主流是 512，128 只占 21.5%` })
  }

  // 参考图角度覆盖 —— 缺背面必须显式记录
  const angles = spec.references.images.map((im) => String(im.angle ?? '').toLowerCase())
  const hasBack = angles.some((a) => /back|背面|后/.test(a))
  const hasSide = angles.some((a) => /side|侧/.test(a))
  if (spec.references.images.length && !hasBack) {
    const noted = spec.gaps.some((g) => /背|back/i.test(String(g)))
    if (!noted) {
      errors.push({
        code: 'BACK_REF_MISSING_UNNOTED',
        message: '没有背面参考图，且 gaps 里没有记录这件事',
        hint: '按既定策略：继续做、背面靠推测，但必须在 gaps 写明"缺背面参考"，最终要告知用户',
      })
    }
  }
  if (spec.references.images.length && !hasSide) {
    warnings.push({ code: 'SIDE_REF_MISSING', message: '没有侧面参考，厚度/侧轮廓只能推测' })
  }

  return { ok: errors.length === 0, errors, warnings, spec }
}

/**
 * spec → 构建计划：按什么顺序建、每个骨骼给多少方块、贴图怎么分。
 * @returns {{order:string[], bones:object[], regions:object, texture:object, totals:object}}
 */
export function derivePlan(input = {}) {
  const spec = input.spec?.parts ? input.spec : normalizeSpec(input)
  const parts = [...spec.parts].map((p) => ({ ...p, region: regionOf(p) }))

  const order = BUILD_ORDER.filter((r) => parts.some((p) => p.region === r))
  const sorted = [...parts].sort((a, b) => order.indexOf(a.region) - order.indexOf(b.region))

  const bones = sorted.map((p) => ({
    part: p.id,
    bone: p.bone,
    parent: PARENT_BY_REGION[p.region] ?? 'Root',
    cubes: p.cubes,
    region: p.region,
    colors: p.colors,
    shape: p.shape,
    refs: p.refs,
  }))

  const regions = {}
  for (const p of parts) regions[p.region] = (regions[p.region] ?? 0) + p.cubes
  const total = parts.reduce((a, p) => a + p.cubes, 0)

  // 贴图分区：按方块数比例分配面积（经验值，实际 UV 仍要看方块尺寸）
  const texSize = spec.budget.textureSize || 512
  const area = texSize * texSize
  const texRegions = Object.entries(regions)
    .sort((a, b) => b[1] - a[1])
    .map(([region, cubes]) => ({
      region,
      share: +(cubes / Math.max(1, total)).toFixed(3),
      areaPx: Math.round((cubes / Math.max(1, total)) * area),
    }))

  return {
    order,
    bones,
    regions,
    texture: { size: texSize, regions: texRegions },
    totals: {
      cubes: total,
      headShare: +((((regions.head ?? 0) + (regions.hair ?? 0)) / Math.max(1, total))).toFixed(3),
      parts: parts.length,
    },
  }
}

/** 人读版 spec（给模型/用户看，也可直接写进 docs）。 */
export function renderSpecMarkdown(spec, plan) {
  const p = plan ?? derivePlan(spec)
  const L = []
  L.push(`# 建模规格：${spec.character?.name || '(未命名)'}`)
  if (spec.character?.source) L.push(`> 来源：${spec.character.source}`)
  L.push('')
  L.push(`- 方块总数 **${p.totals.cubes}**（语料中位 ${BUDGET_BASELINE.cubesTotal}）`)
  L.push(`- 头部区域占比 **${(p.totals.headShare * 100).toFixed(1)}%**（语料中位 ${(BUDGET_BASELINE.headShare * 100).toFixed(1)}%）`)
  L.push(`- 贴图 **${p.texture.size}px**`)
  L.push('')
  if (spec.palette?.length) {
    L.push('## 配色')
    L.push('| 色号 | 颜色 | 用途 |')
    L.push('|---|---|---|')
    for (const c of spec.palette) L.push(`| ${c.name} | \`${c.hex}\` | ${c.usage ?? ''} |`)
    L.push('')
  }
  L.push('## 部位与构建顺序')
  L.push('| 顺序 | 部位 | 骨骼 | 父级 | 方块 | 区域 | 形状 | 参考图 |')
  L.push('|---|---|---|---|---|---|---|---|')
  p.bones.forEach((b, i) => {
    L.push(`| ${i + 1} | ${b.part} | ${b.bone} | ${b.parent} | ${b.cubes} | ${b.region} | ${b.shape || ''} | ${b.refs?.length ? b.refs.map((r) => `#${r}`).join(' ') : ''} |`)
  })
  L.push('')
  if (spec.references?.images?.length) {
    L.push('## 参考图判读')
    L.push('| # | 角度 | 类型 | 备注 |')
    L.push('|---|---|---|---|')
    for (const im of spec.references.images) L.push(`| ${im.index} | ${im.angle ?? '?'} | ${im.kind ?? '?'} | ${im.note ?? ''} |`)
    L.push('')
  }
  if (spec.gaps?.length) {
    L.push('## 信息缺口（必须告知用户）')
    for (const g of spec.gaps) L.push(`- ${g}`)
    L.push('')
  }
  if (spec.notes) {
    L.push('## 备注')
    L.push(spec.notes)
    L.push('')
  }
  return L.join('\n')
}
