// 工具参数 schema 静态校验（不需要 BAE / Electron，秒级）。
//
// 存在的理由：DSH 对工具参数 schema 有硬性要求，只要**一个参数**不合法，
// 整条插件 fiberPhase 就是 failed —— 现象是"所有 bb_* 工具和技能一起消失"。
// 实测踩过两次（camera、spec），且 host-smoke 的 stub defineTool 不校验，拦不住。
//
// 这里直接对生成出来的契约 `spec/tool-manifest.json` 做同一套检查。
import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { lintTools, lintSchema } from '../lib/toolschema.js'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const REPO = path.resolve(HERE, '..', '..', '..')
const MANIFEST = path.join(REPO, 'spec', 'tool-manifest.json')

function loadManifest() {
  assert.ok(fs.existsSync(MANIFEST), `契约不存在: ${MANIFEST}（先跑 python spec/generate_spec.py）`)
  return JSON.parse(fs.readFileSync(MANIFEST, 'utf8'))
}

test('契约里所有工具的 parameters 通过 schema lint', () => {
  const m = loadManifest()
  const r = lintTools(m.tools)
  assert.equal(r.ok, true, r.errors.map((e) => `${e.tool}: ${e.message}`).join('\n'))
  assert.ok(r.checked > 30, `工具数量异常: ${r.checked}`)
})

test('lint 能抓到 object 缺 additionalProperties（回归：曾导致整插件失效）', () => {
  const bad = { name: 'x', parameters: { spec: { type: 'object' } } }
  const r = lintTools([bad])
  assert.equal(r.ok, false)
  assert.match(r.errors[0].message, /additionalProperties/)
})

test('lint 把「数组缺 items」当提示而不是错误（DSH 实际接受）', () => {
  const r = lintTools([{ name: 'y', parameters: { list: { type: 'array' } } }])
  assert.equal(r.ok, true)
  assert.ok(r.warnings.some((w) => /items/.test(w.message)))
})

test('lint 对合法 schema 不误报', () => {
  const good = {
    name: 'z',
    parameters: {
      spec: { type: 'object', properties: {}, additionalProperties: true },
      urls: { type: 'array', items: { type: 'string' } },
      mode: { type: 'string', enum: ['a', 'b'] },
      n: { type: 'number', required: true },
    },
  }
  const r = lintTools([good])
  assert.equal(r.ok, true, r.errors.map((e) => e.message).join('\n'))
})

test('嵌套 object 里的问题也能抓到', () => {
  const r = lintSchema({
    type: 'object',
    additionalProperties: false,
    properties: { inner: { type: 'object' } },
  }, 'parameters.x')
  assert.ok(r.errors.some((e) => /inner\.additionalProperties/.test(e)))
})
