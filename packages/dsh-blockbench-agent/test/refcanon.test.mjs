// 官方基准与深度搜索的纯函数测试（不发网络请求）
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildQueries, QUERY_TEMPLATES } from '../lib/refsearch.js'
import { extractNameVariants, trimForLook } from '../lib/refcanon.js'

test('buildQueries fast 只给 6 条，deep 给全部模板', () => {
  const fast = buildQueries('丰川祥子', { depth: 'fast' })
  const deep = buildQueries('丰川祥子', { depth: 'deep' })
  assert.equal(fast.length, 6)
  assert.equal(deep.length, QUERY_TEMPLATES.length)
  assert.ok(deep.length >= 20, `模板太少: ${deep.length}`)
})

test('查询模板覆盖中/日/英三种语言与关键角度', () => {
  const langs = new Set(QUERY_TEMPLATES.map((t) => t.lang ?? 'zh'))
  assert.ok(langs.has('zh') && langs.has('ja') && langs.has('en'))
  const kinds = new Set(QUERY_TEMPLATES.map((t) => t.kind))
  for (const k of ['sheet', 'fullbody', 'back', 'side', 'outfit', 'closeup']) {
    assert.ok(kinds.has(k), `缺 kind: ${k}`)
  }
})

test('deep 查询里中文在前、日文与英文都出现', () => {
  const qs = buildQueries('丰川祥子', { depth: 'deep' }).map((q) => q.q)
  assert.ok(qs[0].includes('丰川祥子'))
  assert.ok(qs.some((q) => q.includes('設定資料集')))
  assert.ok(qs.some((q) => q.includes('character sheet')))
})

test('extractNameVariants 从括号里的拉丁文抽出名字', () => {
  const v = extractNameVariants('丰川祥子（とがわ さきこ / Togawa Sakiko）是登场角色。', '丰川祥子')
  assert.ok(v.includes('Togawa Sakiko'), JSON.stringify(v))
  assert.equal(v[0], '丰川祥子', '中文名应排最前')
})

test('extractNameVariants 从外文名行抽名字', () => {
  const v = extractNameVariants('外文名：Minato Yukari\n身高：155cm', '凑友希那')
  assert.ok(v.includes('Minato Yukari'), JSON.stringify(v))
})

test('extractNameVariants 能借图片文件名补出罗马音（Eiga Sakiko 那类）', () => {
  const v = extractNameVariants('条目正文没有罗马音。File:Eiga Sakiko.png', '丰川祥子')
  assert.ok(v.some((s) => /Sakiko/i.test(s)), JSON.stringify(v))
})

test('extractNameVariants 过滤掉明显的非名字词', () => {
  const v = extractNameVariants('(Anime Season) (The Band)', '角色')
  assert.ok(!v.includes('Anime Season'))
  assert.ok(!v.includes('The Band'))
})

test('trimForLook 优先保留外观相关段落', () => {
  const text = [
    '引言段落，介绍角色身份。',
    '== 剧情 ==\n' + '很长的剧情描述。'.repeat(200),
    '== 外貌 ==\n浅蓝灰长发，琥珀金瞳，演出服为绯红上衣配黑束腰。',
    '== 其他 ==\n' + '无关内容。'.repeat(100),
  ].join('\n\n')
  const out = trimForLook(text, 400)
  assert.ok(out.length <= 400, `超预算: ${out.length}`)
  assert.ok(out.includes('琥珀金瞳'), '外观段落必须保留')
  assert.ok(out.includes('介绍角色身份'), '引言必须保留')
})

test('trimForLook 原文不超预算时原样返回', () => {
  const short = '很短的一段。'
  assert.equal(trimForLook(short, 400), short)
})
