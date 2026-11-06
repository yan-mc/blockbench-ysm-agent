// viewsheet 单测：token 公式、网格规划、预算降级。
// 运行：node --test packages/dsh-blockbench-agent/test/viewsheet.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  imageTokens, planGrid, cellRects, planWithinBudget, clamp,
  IMAGE_CELL, IMAGE_TOKEN_CAP,
} from '../lib/viewsheet.js'

test('token 公式与官方口径一致（已知点）', () => {
  // 42px 一格的阶梯：rows×(cols+1)+2
  // 800×450 → 11 行 × 21 列 → 11×22+2 = 244（含向上对齐）
  const t = imageTokens(798, 462)
  assert.ok(t > 180 && t <= IMAGE_TOKEN_CAP, `798x462 tokens=${t}`)
  // 更大的图 token 更多
  assert.ok(imageTokens(1600, 900) > imageTokens(800, 450))
  // 小图有计费地板（放大到 544² 计价）
  assert.ok(imageTokens(100, 100) >= 100)
  // 非法尺寸
  assert.equal(imageTokens(0, 100), 0)
  assert.equal(imageTokens(-5, 10), 0)
})

test('cell 常量为 42', () => {
  assert.equal(IMAGE_CELL, 42)
})

test('planGrid 为 2 帧选出接近 4:3 的布局', () => {
  const p = planGrid(2, { aspect: 4 / 3 })
  assert.equal(p.count, 2)
  assert.ok(p.cols * p.rows >= 2)
  assert.ok(p.cell % 14 === 0, 'cell 对齐到 14px patch')
  assert.ok(p.width > 0 && p.height > 0)
})

test('planGrid 为 8 帧选出方形布局', () => {
  const p = planGrid(8, { aspect: 1 })
  assert.equal(p.count, 8)
  assert.ok(p.cols * p.rows >= 8)
})

test('planWithinBudget 在预算内或返回最接近的方案', () => {
  const p = planWithinBudget(4, { budget: 260 })
  assert.ok(p.tokens <= 260, `tokens=${p.tokens} 超出预算`)
  assert.ok(p.cell >= 64)
})

test('cellRects 覆盖全部格子且不重叠', () => {
  const p = planGrid(4, { aspect: 1 })
  const rects = cellRects(p)
  assert.equal(rects.length, 4)
  for (const r of rects) {
    assert.ok(r.w > 0 && r.h > 0)
    assert.ok(r.x + r.w <= p.width + p.cell)
    assert.ok(r.y + r.h <= p.height + p.cell)
  }
  // 两两不重叠
  for (let i = 0; i < rects.length; i++) {
    for (let j = i + 1; j < rects.length; j++) {
      const a = rects[i], b = rects[j]
      const overlap = a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h
      assert.equal(overlap, false, `rect ${i} 与 ${j} 重叠`)
    }
  }
})

test('clamp 处理非法输入', () => {
  assert.equal(clamp(5, 1, 10, 3), 5)
  assert.equal(clamp(0, 1, 10, 3), 1)
  assert.equal(clamp(99, 1, 10, 3), 10)
  assert.equal(clamp('abc', 1, 10, 3), 3)
  assert.equal(clamp(undefined, 1, 10, 3), 3)
})

test('拼图比多张单图省 token', () => {
  // 3 张 512² 分开传
  const three = imageTokens(512, 512) * 3
  // 一张 4 格 640 拼图
  const sheet = planWithinBudget(4, { budget: 260 })
  assert.ok(sheet.tokens < three, `拼图 ${sheet.tokens} 应少于 3 张单图 ${three}`)
})
