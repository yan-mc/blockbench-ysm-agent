// 图史压缩器（docs/07 §4.2 L1）：把历史 tool result 里的 image block
// 换成占位文本，从而让旧图**从模型的上下文里消失**，且**不花任何模型调用**。
//
// 实现照抄官方 pruner（@deepseek-ai/dsh-compaction-tool-result-pruner/lib/index.js:155-184）：
//   session.append('compaction/prune', {...shadow...})           // 先记影子价格
//   session.append('tool/result', {...data, message}, {          // 再替换节点
//     surfaceOp: { op:'replace', startSeq, endSeq },
//     sourceEventSeqs: [seq],
//   })
//
// 与 pruner 的唯一区别：变换的是 image block（不是裁 text）。

/** 占位文本前缀，便于模型与统计识别。 */
export const OFFLOAD_MARKER = '[已压缩渲染图]'

/**
 * 把一条 tool result 的 content 中的 image block 换成一条 text 占位。
 *
 * @param {readonly object[]} blocks 原始 content
 * @param {{reason?: string, keepInNode?: number}} [opts]
 *   keepInNode：本条内**保留**的图片数（0 = 全剥）。用于"某节点跨在保留边界上"的情况，
 *   保留该节点内**最靠后**的 keepInNode 张（它们最接近当前渲染结果）。
 * @returns {{content: object[]|null, removed: number}} removed=0 表示无需改动
 */
export function stripImages(blocks, opts = {}) {
  if (!Array.isArray(blocks) || !blocks.length) return { content: null, removed: 0 }
  const total = blocks.filter((b) => b && b.type === 'image').length
  if (!total) return { content: null, removed: 0 }

  const keep = Math.max(0, Math.min(total, Math.round(Number(opts.keepInNode) || 0)))
  const removeCount = total - keep
  if (removeCount <= 0) return { content: null, removed: 0 }

  // 找出要保留的图片对象（本条内最靠后的 keep 张）
  const imageRefs = blocks.filter((b) => b && b.type === 'image')
  const keepSet = new Set(imageRefs.slice(imageRefs.length - keep))

  const reason = opts.reason ? `（${opts.reason}）` : ''
  const placeholder = {
    type: 'text',
    text: `${OFFLOAD_MARKER} 此处原有 ${removeCount} 张渲染图${reason}，为控制上下文已省略；`
      + '如需重新查看，可再次调用 bb_look / bb_orbit / bb_render_texture。',
  }

  // 保留原有 block 顺序：在**第一张被剥离的图的位置**放占位
  const out = []
  let placed = false
  for (const b of blocks) {
    if (b && b.type === 'image') {
      if (keepSet.has(b)) { out.push(b); continue }
      if (!placed) { out.push(placeholder); placed = true }
      continue
    }
    out.push(b)
  }
  return { content: out, removed: removeCount }
}

/**
 * 在一条会话 surface 上执行图片剥离。
 *
 * 安全约束（全部必须满足才动手）：
 *   1) 只处理当前 surface 上的 `tool/result` 节点；
 *   2) 永远保留最新 `keepImages` 张图；
 *   3) 永远不碰 `protectSeqs` 里的节点（通常是当前 step 的图片）；
 *   4) 每次最多处理 `maxNodes` 条，避免一次性改写过多导致前缀缓存全失效。
 *
 * @param {object} p
 * @param {object} p.session       Session 实例
 * @param {object} p.tokenMeter    ctx.tokenMeter（估算影子价格；缺失则记 0）
 * @param {object} p.freezeMessage dsh-llm 的 freezeMessage（缺失则用恒等）
 * @param {number} [p.keepImages=2]
 * @param {number} [p.maxNodes=4]
 * @param {Set<number>} [p.protectSeqs]
 * @returns {{offloaded: Array, imagesRemoved: number, nodesRewritten: number}}
 */
export function offloadSessionImages(p) {
  const {
    session, tokenMeter, freezeMessage = (m) => m,
    keepImages = 2, maxNodes = 4, protectSeqs = new Set(),
  } = p || {}
  if (!session?.surface || typeof session.append !== 'function') {
    return { offloaded: [], imagesRemoved: 0, nodesRewritten: 0, skipped: 'no-session' }
  }

  // 1) 收集所有带图节点（按 surface 顺序，即模型请求顺序）
  const withImages = []
  for (const seq of [...session.surface.nodes]) {
    if (protectSeqs.has(seq)) continue
    const event = session.eventAt(seq)
    if (event?.type !== 'tool/result') continue
    let msg = null
    try { msg = session.deriveEventMessage(event) } catch { msg = null }
    if (!msg?.content) continue
    const n = msg.content.filter((b) => b && b.type === 'image').length
    if (n > 0) withImages.push({ seq, event, message: msg, count: n })
  }

  if (!withImages.length) {
    return { offloaded: [], imagesRemoved: 0, nodesRewritten: 0 }
  }

  // 2) 按**图片粒度**规划：从最新往前数，前 keepImages 张保留；
  //    边界节点可能"只保一部分"，这由 stripImages 的 keepInNode 处理。
  let budget = Math.max(0, Math.round(keepImages))
  const plans = []   // { seq, event, message, total, keepInNode }
  for (let i = withImages.length - 1; i >= 0; i--) {
    const node = withImages[i]
    const keepInNode = Math.max(0, Math.min(node.count, budget))
    budget -= keepInNode
    const willRemove = node.count - keepInNode
    if (willRemove > 0) plans.push({ ...node, keepInNode, willRemove })
  }
  if (!plans.length) return { offloaded: [], imagesRemoved: 0, nodesRewritten: 0 }

  // 从最老的开始剥（保持模型请求顺序上前缀尽早稳定）
  plans.reverse()
  const chosen = plans.slice(0, Math.max(0, maxNodes))
  if (!chosen.length) return { offloaded: [], imagesRemoved: 0, nodesRewritten: 0 }

  // 3) 逐条替换
  const offloaded = []
  let imagesRemoved = 0
  let nodesRewritten = 0

  for (const { seq, event, message, keepInNode } of chosen) {
    try {
      const { content, removed } = stripImages(message.content, { keepInNode })
      if (!content || !removed) continue

      const replacementMessage = freezeMessage({ ...message, content })

      // 影子价格：让 token meter 能扣掉被替换节点的旧价格
      let shadowTokens = 0
      try { shadowTokens = tokenMeter?.estimateMessage?.(message) ?? 0 } catch { shadowTokens = 0 }
      session.append('compaction/prune', {
        shadowedRange: { start: seq, end: seq },
        shadowedSeqs: [seq],
        shadowedTokenCount: shadowTokens,
      })

      session.append('tool/result', {
        ...event.data,
        message: replacementMessage,
      }, {
        surfaceOp: { op: 'replace', startSeq: seq, endSeq: seq },
        sourceEventSeqs: [seq],
      })

      offloaded.push({ seq, images: removed })
      imagesRemoved += removed
      nodesRewritten += 1
    } catch {
      // 单条失败不影响其它条；也不重试（docs/07 R2）
    }
  }

  return { offloaded, imagesRemoved, nodesRewritten }
}

/**
 * 统计会话当前的"活的图片数"（未被 offload 且有 image block 的节点）。
 * 用于 /bb-status 与预算判断。
 */
export function countLiveImages(session) {
  if (!session?.surface) return { images: 0, nodes: 0 }
  let images = 0
  let nodes = 0
  for (const seq of [...session.surface.nodes]) {
    const event = session.eventAt(seq)
    if (event?.type !== 'tool/result') continue
    let msg = null
    try { msg = session.deriveEventMessage(event) } catch { continue }
    if (!msg?.content) continue
    const n = msg.content.filter((b) => b && b.type === 'image' && !b.offloaded).length
    if (n) { images += n; nodes += 1 }
  }
  return { images, nodes }
}
