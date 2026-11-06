// 拼图与 token 预算（Host 侧，纯函数、零依赖、可直接单测）。
//
// 设计依据：docs/07-视口实时反馈方案-冻结.md §4.4
//   - 一张拼图装 4 帧与装 1 帧同价（token 由画布尺寸决定，不由帧数决定）
//   - 所以"多留一帧"几乎免费，"漏掉一帧"才贵
//
// token 公式来自 DSH 图像计费口径（14px patch 向上对齐 → 42px 一格 → rows×(cols+1)+2），
// 与 dsh-see-now 的 tokens.js 一致；这里独立实现，不引入依赖。

export const IMAGE_PATCH = 14
export const IMAGE_DOWNSAMPLE = 3
export const IMAGE_CELL = IMAGE_PATCH * IMAGE_DOWNSAMPLE // 42
export const IMAGE_TOKEN_CAP = 1024
export const IMAGE_UPSCALE_AREA = 544 * 544

const intDiv = (v, d) => Math.floor(v / d)
const ceilDiv = (v, d) => Math.floor((v + d - 1) / d)
const padToPatch = (px) => ceilDiv(px, IMAGE_PATCH) * IMAGE_PATCH
const gridCells = (padded) => ceilDiv(intDiv(padded, IMAGE_PATCH), IMAGE_DOWNSAMPLE)
const gridTokens = (rows, cols) => rows * (cols + 1) + 2

function projectSize(W, H, cap) {
  const tw = gridTokens(gridCells(padToPatch(H)), gridCells(padToPatch(W)))
  if (tw <= cap) return { W, H, tokens: tw }
  const aspect = H / W
  const idealW = Math.sqrt((cap - 2) / aspect + 0.25) - 0.5
  let solvedW = Math.trunc(idealW)
  let solvedH = Math.trunc(idealW * aspect)
  if (solvedW < 1) { solvedW = 1; solvedH = intDiv(cap - 2, 2) }
  else if (solvedH < 1) { solvedH = 1; solvedW = intDiv(cap - 2, solvedH) - 1 }
  const scale = Math.min((solvedW * IMAGE_CELL) / W, (solvedH * IMAGE_CELL) / H)
  const bw = Math.trunc((W * scale) / IMAGE_PATCH) * IMAGE_PATCH
  const bh = Math.trunc((H * scale) / IMAGE_PATCH) * IMAGE_PATCH
  return { W: bw, H: bh, tokens: gridTokens(gridCells(bh), gridCells(bw)) }
}

/** 像素尺寸 → 估算视觉 token（≤1024）。 */
export function imageTokens(w, h) {
  let W = Math.round(Number(w) || 0)
  let H = Math.round(Number(h) || 0)
  if (W <= 0 || H <= 0) return 0
  const px = W * H
  if (px < IMAGE_UPSCALE_AREA) {
    const s = Math.sqrt(IMAGE_UPSCALE_AREA / px)
    W = Math.max(1, Math.trunc(W * s))
    H = Math.max(1, Math.trunc(H * s))
  }
  let cur = projectSize(W, H, IMAGE_TOKEN_CAP)
  for (let i = 0; i < 10; i++) {
    const next = projectSize(cur.W, cur.H, IMAGE_TOKEN_CAP)
    if (next.tokens === cur.tokens && next.W === cur.W && next.H === cur.H) return cur.tokens
    cur = next
  }
  return cur.tokens
}

// ---------------------------------------------------------------- 网格规划

/**
 * 为 n 帧挑选列数×行数，使整体画布最接近目标宽高比且浪费最小。
 * 画布按 42px 步进，以踩在 token 阶梯的低点上（差 1.5% 像素可能差一整行 token）。
 */
export function planGrid(n, { aspect = 4 / 3, minCell = 200, maxSide = 1600 } = {}) {
  const count = Math.max(1, Math.round(n))
  let best = null
  for (let cols = 1; cols <= count; cols++) {
    const rows = Math.ceil(count / cols)
    if (cols * rows < count) continue
    // 画布宽高比 = (cols*cell) / (rows*cell) = cols/rows
    const score = Math.abs(Math.log(cols / rows / aspect))
    if (!best || score < best.score) best = { cols, rows, score }
  }
  if (!best) best = { cols: count, rows: 1, score: 0 }

  // 单元格边长：满足 minCell 且不超过 maxSide
  const longest = Math.max(best.cols, best.rows)
  let cell = Math.max(minCell, Math.round(maxSide / longest))
  cell = Math.max(64, Math.min(maxSide, cell))
  // 对齐到 14 的倍数（patch 网格），减少阶梯浪费
  cell = Math.max(IMAGE_PATCH, Math.round(cell / IMAGE_PATCH) * IMAGE_PATCH)

  const width = best.cols * cell
  const height = best.rows * cell
  return {
    cols: best.cols, rows: best.rows, cell,
    width: Math.min(width, maxSide), height: Math.min(height, maxSide),
    count,
    tokens: imageTokens(Math.min(width, maxSide), Math.min(height, maxSide)),
  }
}

/**
 * 计算每个格子的像素矩形（含 1px 缝，便于肉眼分辨边界）。
 * 返回 [{x,y,w,h}]，按行优先。
 */
export function cellRects(plan, gap = 1) {
  const rects = []
  const inner = plan.cell - gap
  for (let i = 0; i < plan.count; i++) {
    const r = Math.floor(i / plan.cols)
    const c = i % plan.cols
    rects.push({
      x: c * plan.cell + gap,
      y: r * plan.cell + gap,
      w: inner,
      h: inner,
    })
  }
  return rects
}

/**
 * 预算守卫：给定帧数与期望画布，返回可用的 plan 或降级后的 plan。
 * 目标：单张拼图 token ≤ budget，且单元格不小到看不清模型形状。
 */
export function planWithinBudget(n, { budget = 260, aspect = 4 / 3, minCell = 180 } = {}) {
  let plan = planGrid(n, { aspect, minCell })
  if (plan.tokens <= budget) return plan
  // 逐级缩小单元格直到进入预算
  for (let cell = plan.cell - IMAGE_PATCH; cell >= 64; cell -= IMAGE_PATCH) {
    const candidate = {
      ...plan,
      cell,
      width: plan.cols * cell,
      height: plan.rows * cell,
      tokens: imageTokens(plan.cols * cell, plan.rows * cell),
    }
    if (candidate.tokens <= budget) return candidate
  }
  return plan
}

// ---------------------------------------------------------------- 预设

/** 常用预设：自动附图 / 转台 / 贴图放大。 */
export const LOOK_PRESETS = {
  /** 写操作自动附图：2 帧（front + iso），小画布，最省 */
  autolook: { views: ['front', 'iso_fr'], cell: 320, background: '#1b1b1b' },
  /** 自由看：单帧，较大 */
  single: { cell: 640, background: null },
  /** 转台：8 角度 */
  turntable: { steps: 8, cell: 320, background: '#1b1b1b' },
  /** 贴图精修：像素放大不缩放 */
  texture: { cell: 0, background: '#1b1b1b' },
}

/** 有界数值工具 */
export const clamp = (v, lo, hi, dflt) => {
  const n = Number(v)
  if (!Number.isFinite(n)) return dflt
  return Math.max(lo, Math.min(hi, n))
}
