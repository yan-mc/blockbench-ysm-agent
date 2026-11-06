// imageprune 单测：验证只保留最新 N 张、不动受保护节点、失败不抛出。
import test from 'node:test'
import assert from 'node:assert/strict'
import { stripImages, offloadSessionImages, countLiveImages, OFFLOAD_MARKER } from '../lib/imageprune.js'

/** 造一个最小 fake session：surface.nodes + eventAt + deriveEventMessage + append */
function fakeSession(nodeMap, opts = {}) {
  const events = new Map()
  const appended = []
  for (const [seq, blocks] of nodeMap) {
    events.set(seq, { type: 'tool/result', seq, data: { message: { content: blocks } } })
  }
  const session = {
    surface: { nodes: [...nodeMap.keys()] },
    eventAt: (seq) => events.get(seq),
    deriveEventMessage: (ev) => ({ role: 'tool', content: ev.data.message.content, toolCallId: `c${ev.seq}` }),
    append: (type, data, intent) => {
      appended.push({ type, data, intent })
      if (type === 'tool/result' && intent?.surfaceOp) {
        // 模拟 replace：把新内容写回，并加入新节点
        const seq = intent.surfaceOp.startSeq
        events.set(seq, { type: 'tool/result', seq, data })
        // 真实实现会新增一个节点；这里保持 surface 不变以便测试语义
      }
      return { seq: 999 }
    },
  }
  if (opts.failOn) session.append = () => { throw new Error('rejected by session') }
  return { session, appended }
}

const img = (id) => ({ type: 'image', attachment: { attachmentId: `sha256:${id}`, mediaType: 'image/png', bytes: 1, width: 2, height: 2 } })
const txt = (t) => ({ type: 'text', text: t })

test('stripImages 把图片换成一条占位，保留文本', () => {
  const blocks = [txt('结果'), img('a'), img('b')]
  const { content, removed } = stripImages(blocks)
  assert.equal(removed, 2)
  assert.equal(content.length, 2)               // 1 text + 1 placeholder
  assert.equal(content[0].text, '结果')
  assert.ok(content[1].text.includes(OFFLOAD_MARKER))
  assert.ok(content[1].text.includes('2 张'))
  assert.equal(content.filter((b) => b.type === 'image').length, 0)
})

test('stripImages 无图时返回 null（不改动）', () => {
  const { content, removed } = stripImages([txt('只有文本')])
  assert.equal(content, null)
  assert.equal(removed, 0)
})

test('stripImages 处理空输入', () => {
  assert.equal(stripImages(null).removed, 0)
  assert.equal(stripImages([]).removed, 0)
})

test('保留最新 keepImages 张图，只剥更老的', () => {
  // 3 个节点，各 1 张图；keepImages=1 → 应只剥前 2 个
  const map = new Map([[1, [img('a')]], [2, [img('b')]], [3, [img('c')]]])
  const { session, appended } = fakeSession(map)
  const r = offloadSessionImages({ session, keepImages: 1, maxNodes: 10 })
  assert.equal(r.nodesRewritten, 2)
  assert.equal(r.imagesRemoved, 2)
  // 最新节点（seq=3）不应被替换
  const replaced = appended.filter((a) => a.type === 'tool/result').map((a) => a.intent.surfaceOp.startSeq)
  assert.deepEqual(replaced.sort(), [1, 2])
})

test('keepImages 覆盖多个节点里的多张图', () => {
  // seq1 有 3 张图，seq2 有 1 张；keepImages=2 → seq2 的 1 张必须留，
  // seq1 只留 1 张、剥 2 张
  const map = new Map([[1, [img('a'), img('b'), img('c')]], [2, [img('d')]]])
  const { session } = fakeSession(map)
  const r = offloadSessionImages({ session, keepImages: 2, maxNodes: 10 })
  assert.equal(r.nodesRewritten, 1)
  assert.equal(r.imagesRemoved, 2)
})

test('protectSeqs 里的节点永不处理', () => {
  const map = new Map([[1, [img('a')]], [2, [img('b')]], [3, [img('c')]]])
  const { session, appended } = fakeSession(map)
  const r = offloadSessionImages({ session, keepImages: 0, maxNodes: 10, protectSeqs: new Set([3]) })
  const replaced = appended.filter((a) => a.type === 'tool/result').map((a) => a.intent.surfaceOp.startSeq)
  assert.equal(replaced.includes(3), false)
  assert.equal(r.nodesRewritten, 2)
})

test('maxNodes 限制单次剥离条数', () => {
  const map = new Map([[1, [img('a')]], [2, [img('b')]], [3, [img('c')]], [4, [img('d')]]])
  const { session } = fakeSession(map)
  const r = offloadSessionImages({ session, keepImages: 0, maxNodes: 2 })
  assert.equal(r.nodesRewritten, 2)
})

test('先 append compaction/prune 影子价格，再 append tool/result 替换', () => {
  const map = new Map([[1, [img('a')]], [2, [img('b')]]])
  const { session, appended } = fakeSession(map)
  offloadSessionImages({ session, keepImages: 0, maxNodes: 10 })
  const types = appended.map((a) => a.type)
  assert.deepEqual(types, ['compaction/prune', 'tool/result', 'compaction/prune', 'tool/result'])
  // 替换必须带 surfaceOp 与 sourceEventSeqs
  const replaces = appended.filter((a) => a.type === 'tool/result')
  for (const r of replaces) {
    assert.equal(r.intent.surfaceOp.op, 'replace')
    assert.deepEqual(r.intent.sourceEventSeqs, [r.intent.surfaceOp.startSeq])
  }
})

test('session 拒绝时不抛出（docs/07 R2）', () => {
  const map = new Map([[1, [img('a')]], [2, [img('b')]]])
  const { session } = fakeSession(map, { failOn: true })
  const r = offloadSessionImages({ session, keepImages: 0, maxNodes: 10 })
  assert.equal(r.nodesRewritten, 0)
})

test('图数不超过 keepImages 时什么都不做', () => {
  const map = new Map([[1, [img('a')]]])
  const { session, appended } = fakeSession(map)
  const r = offloadSessionImages({ session, keepImages: 2 })
  assert.equal(r.nodesRewritten, 0)
  assert.equal(appended.length, 0)
})

test('边界节点只剥一部分，保留其最靠后的图', () => {
  // 单节点 4 张图，keepImages=2 → 剥掉前 2 张，保留后 2 张
  const map = new Map([[1, [img('a'), img('b'), img('c'), img('d')]]])
  const { session } = fakeSession(map)
  const r = offloadSessionImages({ session, keepImages: 2, maxNodes: 10 })
  assert.equal(r.imagesRemoved, 2)
  assert.equal(r.nodesRewritten, 1)
  // 直接验 stripImages 的语义
  const blocks = [img('a'), img('b'), img('c'), img('d')]
  const { content, removed } = stripImages(blocks, { keepInNode: 2 })
  assert.equal(removed, 2)
  const keptIds = content.filter((b) => b.type === 'image').map((b) => b.attachment.attachmentId)
  assert.deepEqual(keptIds, ['sha256:c', 'sha256:d'])
  assert.equal(content[0].type, 'text')   // 占位在最老的图位置
})

test('countLiveImages 统计当前在册的图片', () => {
  const map = new Map([[1, [img('a'), img('b')]], [2, [txt('x')]]])
  const { session } = fakeSession(map)
  assert.deepEqual(countLiveImages(session), { images: 2, nodes: 1 })
})

test('无 session 时安全返回', () => {
  assert.equal(offloadSessionImages({}).nodesRewritten, 0)
  assert.deepEqual(countLiveImages(null), { images: 0, nodes: 0 })
})
