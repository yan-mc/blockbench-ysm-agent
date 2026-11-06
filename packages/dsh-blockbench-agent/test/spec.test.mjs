// 建模规格（spec）单元测试：docs/12
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  validateSpec, derivePlan, renderSpecMarkdown, normalizeSpec,
  regionOf, BUDGET_BASELINE, SPEC_VERSION,
} from '../lib/spec.js'

/** 一个"及格"的规格：16 部位、头部占比接近语料中位、有背面参考。 */
function goodSpec(over = {}) {
  return {
    character: { name: '测试角色', source: '测试' },
    references: {
      dir: 'refs/test',
      images: [
        { index: 0, angle: 'front', kind: 'sheet' },
        { index: 1, angle: 'side', kind: 'fullbody' },
        { index: 2, angle: 'back', kind: 'sheet' },
      ],
    },
    palette: [
      { name: 'hair', hex: '#a8b8d8', usage: '头发' },
      { name: 'skin', hex: '#ffe0c8', usage: '肤色' },
      { name: 'cloth', hex: '#e8e8ee', usage: '衬衫' },
    ],
    parts: [
      { id: 'torso', bone: 'UpperBody', cubes: 40, colors: ['cloth'] },
      { id: 'skirt', bone: 'Skirt', cubes: 30, colors: ['cloth'] },
      { id: 'leg', bone: 'LeftLeg', cubes: 20, colors: ['skin'] },
      { id: 'arm', bone: 'LeftArm', cubes: 24, colors: ['skin'] },
      { id: 'head', bone: 'Head', cubes: 30, colors: ['skin'] },
      { id: 'hair', bone: 'Hair', cubes: 90, colors: ['hair'] },
    ],
    budget: { ...BUDGET_BASELINE },
    gaps: [],
    notes: '测试用',
    ...over,
  }
}

test('normalizeSpec 补齐版本与默认值', () => {
  const s = normalizeSpec({})
  assert.equal(s.spec, SPEC_VERSION)
  assert.deepEqual(s.parts, [])
  assert.equal(s.budget.cubesTotal, BUDGET_BASELINE.cubesTotal)
})

test('合法规格通过校验', () => {
  const r = validateSpec(goodSpec())
  assert.equal(r.ok, true, JSON.stringify(r.errors))
  assert.equal(r.errors.length, 0)
})

test('缺角色名报错', () => {
  const r = validateSpec(goodSpec({ character: {} }))
  assert.equal(r.ok, false)
  assert.ok(r.errors.some((e) => e.code === 'CHARACTER_MISSING'))
})

test('parts 为空报错', () => {
  const r = validateSpec(goodSpec({ parts: [] }))
  assert.equal(r.ok, false)
  assert.ok(r.errors.some((e) => e.code === 'PARTS_EMPTY'))
})

test('部位缺骨骼/方块数报错', () => {
  const r = validateSpec(goodSpec({
    parts: [{ id: 'x', bone: '', cubes: 0 }],
  }))
  assert.equal(r.ok, false)
  assert.ok(r.errors.some((e) => e.code === 'PART_BONE_MISSING'))
  assert.ok(r.errors.some((e) => e.code === 'PART_CUBES_INVALID'))
})

test('部位 id 重复报错', () => {
  const r = validateSpec(goodSpec({
    parts: [
      { id: 'a', bone: 'Head', cubes: 10 },
      { id: 'a', bone: 'Head', cubes: 10 },
    ],
  }))
  assert.equal(r.ok, false)
  assert.ok(r.errors.some((e) => e.code === 'PART_ID_DUP'))
})

test('配色 hex 非法报错', () => {
  const r = validateSpec(goodSpec({ palette: [{ name: 'bad', hex: 'red' }] }))
  assert.equal(r.ok, false)
  assert.ok(r.errors.some((e) => e.code === 'PALETTE_HEX_INVALID'))
})

test('部位引用了未定义的色号 -> warning 不是 error', () => {
  const r = validateSpec(goodSpec({
    parts: [{ id: 'torso', bone: 'UpperBody', cubes: 40, colors: ['nope'] }],
  }))
  assert.equal(r.ok, true)
  assert.ok(r.warnings.some((w) => w.code === 'COLOR_UNDEFINED'))
})

test('缺背面参考且 gaps 未记录 -> 直接 error（产品决策）', () => {
  const spec = goodSpec({
    references: {
      dir: 'refs/test',
      images: [{ index: 0, angle: 'front' }, { index: 1, angle: 'side' }],
    },
    gaps: [],
  })
  const r = validateSpec(spec)
  assert.equal(r.ok, false)
  assert.ok(r.errors.some((e) => e.code === 'BACK_REF_MISSING_UNNOTED'))
})

test('缺背面但在 gaps 里写了 -> 通过', () => {
  const spec = goodSpec({
    references: {
      dir: 'refs/test',
      images: [{ index: 0, angle: 'front' }, { index: 1, angle: 'side' }],
    },
    gaps: ['缺背面参考图，裙后摆按对称推测'],
  })
  const r = validateSpec(spec)
  assert.equal(r.ok, true, JSON.stringify(r.errors))
})

test('缺侧面 -> warning', () => {
  const spec = goodSpec({
    references: { dir: 'x', images: [{ index: 0, angle: 'front' }, { index: 2, angle: 'back' }] },
  })
  const r = validateSpec(spec)
  assert.equal(r.ok, true)
  assert.ok(r.warnings.some((w) => w.code === 'SIDE_REF_MISSING'))
})

test('方块数过低/过高给出预算 warning', () => {
  const low = validateSpec(goodSpec({ parts: [{ id: 'a', bone: 'Head', cubes: 20 }] }))
  assert.ok(low.warnings.some((w) => w.code === 'BUDGET_LOW'))
  const high = validateSpec(goodSpec({ parts: [{ id: 'a', bone: 'Head', cubes: 900 }] }))
  assert.ok(high.warnings.some((w) => w.code === 'BUDGET_HIGH'))
})

test('头部占比偏离区间给出 warning', () => {
  // 全部给躯干 -> 头部占比 0
  const r = validateSpec(goodSpec({
    parts: [
      { id: 'torso', bone: 'UpperBody', cubes: 200 },
      { id: 'leg', bone: 'LeftLeg', cubes: 100 },
    ],
  }))
  assert.ok(r.warnings.some((w) => w.code === 'HEAD_SHARE_OFF'))
})

test('regionOf 能认出中文和英文部位名', () => {
  assert.equal(regionOf({ id: 'hair' }), 'hair')
  assert.equal(regionOf({ id: '头发' }), 'hair')
  assert.equal(regionOf({ bone: 'LeftArm' }), 'arm')
  assert.equal(regionOf({ id: '裙摆' }), 'skirt')
  assert.equal(regionOf({ id: '未知部位xyz' }), 'other')
})

test('derivePlan 给出构建顺序、父级与贴图分区', () => {
  const spec = normalizeSpec(goodSpec())
  const plan = derivePlan(spec)
  // 顺序：躯干在头之前，头在发之前
  assert.ok(plan.order.indexOf('torso') < plan.order.indexOf('head'))
  assert.ok(plan.order.indexOf('head') < plan.order.indexOf('hair'))
  // 父级映射
  const head = plan.bones.find((b) => b.bone === 'Head')
  assert.equal(head.parent, 'AllHead')
  const hair = plan.bones.find((b) => b.bone === 'Hair')
  assert.equal(hair.parent, 'Head')
  // 父级不能等于自身（bones=UpperBody 时父级要退到 UpBody）
  for (const b of plan.bones) assert.notEqual(b.parent, b.bone, `${b.part}: parent 不能是自身`)
  // 总量守恒
  const sum = plan.bones.reduce((a, b) => a + b.cubes, 0)
  assert.equal(plan.totals.cubes, sum)
  // 贴图分区占比之和约等于 1
  const shareSum = plan.texture.regions.reduce((a, r) => a + r.share, 0)
  assert.ok(Math.abs(shareSum - 1) < 0.02, `shareSum=${shareSum}`)
})

test('renderSpecMarkdown 含关键小节', () => {
  const spec = normalizeSpec(goodSpec({ gaps: ['缺背面参考图'] }))
  const md = renderSpecMarkdown(spec, derivePlan(spec))
  assert.match(md, /# 建模规格/)
  assert.match(md, /## 配色/)
  assert.match(md, /## 部位与构建顺序/)
  assert.match(md, /## 参考图判读/)
  assert.match(md, /## 信息缺口/)
  assert.match(md, /缺背面参考图/)
})

test('贴图尺寸过小时给 warning', () => {
  const r = validateSpec(goodSpec({ budget: { ...BUDGET_BASELINE, textureSize: 128 } }))
  assert.ok(r.warnings.some((w) => w.code === 'TEXTURE_SMALL'))
})
