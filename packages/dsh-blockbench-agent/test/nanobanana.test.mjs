// T3（Nano Banana Pro）纯逻辑单测：不发真实请求、不需要 API key。
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  resolveT3Config, inspectT3Availability, buildSheetPrompt, buildT3RequestBody,
  extractT3Result, estimateCostUsd, mapT3Error, callT3,
  T3_DEFAULT_MODEL, T3_MODELS,
} from '../lib/nanobanana.js'

test('resolveT3Config：无 key 时 configured=false，默认 Pro 模型', () => {
  const c = resolveT3Config({}, {})
  assert.equal(c.configured, false)
  assert.equal(c.model, T3_DEFAULT_MODEL)
  assert.equal(c.apiKeySource, '')
  assert.equal(c.imageSize, '2K')
  assert.equal(c.aspectRatio, '16:9')
})

test('resolveT3Config：环境变量 GEMINI_API_KEY 可启用，且标注来源', () => {
  const c = resolveT3Config({}, { GEMINI_API_KEY: 'sk-test-env' })
  assert.equal(c.configured, true)
  assert.equal(c.apiKey, 'sk-test-env')
  assert.equal(c.apiKeySource, 'env:GEMINI_API_KEY')
})

test('resolveT3Config：config 优先于 env；模型/尺寸/比例/上限被规整', () => {
  const c = resolveT3Config({
    nanoBananaApiKey: 'cfg-key',
    nanoBananaModel: 'gemini-nano-banana-2.1',
    nanoBananaImageSize: '4k',
    nanoBananaAspectRatio: '21:9',
    nanoBananaMaxReferences: 99,
    nanoBananaTimeoutMs: 1000,
  }, { GEMINI_API_KEY: 'env-key' })
  assert.equal(c.apiKey, 'cfg-key')
  assert.equal(c.model, 'gemini-nano-banana-2.1')
  assert.equal(c.imageSize, '4K')
  assert.equal(c.aspectRatio, '21:9')
  assert.equal(c.maxReferences, 14)
  assert.equal(c.timeoutMs, 10000)
})

test('resolveT3Config：非法尺寸/比例回落到默认', () => {
  const c = resolveT3Config({ nanoBananaApiKey: 'k', nanoBananaImageSize: '8K', nanoBananaAspectRatio: '7:3' }, {})
  assert.equal(c.imageSize, '2K')
  assert.equal(c.aspectRatio, '16:9')
})

test('inspectT3Availability：无 key 给出 reason 与 fallback=t2；有 key 时 ok', () => {
  const no = inspectT3Availability({}, {})
  assert.equal(no.ok, false)
  assert.equal(no.fallback, 't2')
  assert.match(no.reasons[0], /GEMINI_API_KEY|apiKey/)

  const yes = inspectT3Availability({ nanoBananaApiKey: 'k' }, {})
  assert.equal(yes.ok, true)
  assert.equal(yes.fallback, null)
  assert.equal(yes.price_per_image_usd, 0.134)
})

test('buildSheetPrompt：三种模式的关键词与身份锚定', () => {
  const turn = buildSheetPrompt({ mode: 'turnaround', character: '丰川祥子' })
  assert.match(turn, /三视图/)
  assert.match(turn, /正面/)
  assert.match(turn, /背面/)
  assert.match(turn, /丰川祥子/)
  assert.match(turn, /参考图/)

  const br = buildSheetPrompt({ mode: 'breakdown' })
  assert.match(br, /全景式/)
  assert.match(br, /服装分层/)
  assert.match(br, /表情/)

  assert.throws(() => buildSheetPrompt({ mode: 'custom' }), (e) => e.code === 'INVALID_PARAMS')
  const custom = buildSheetPrompt({ mode: 'custom', prompt: '只画正面' })
  assert.match(custom, /只画正面/)
})

test('buildT3RequestBody：图片作为 inline_data，输出 modalities/imageConfig 正确', () => {
  const body = buildT3RequestBody({
    prompt: 'hello',
    images: [{ mimeType: 'image/png', data: 'AAA' }, { mimeType: 'image/jpeg', data: 'BBB' }],
    aspectRatio: '16:9',
    imageSize: '2K',
  })
  const parts = body.contents[0].parts
  assert.equal(parts.length, 3)
  assert.equal(parts[0].text, 'hello')
  assert.equal(parts[1].inline_data.mime_type, 'image/png')
  assert.equal(parts[1].inline_data.data, 'AAA')
  assert.deepEqual(body.generationConfig.responseModalities, ['TEXT', 'IMAGE'])
  assert.deepEqual(body.generationConfig.imageConfig, { aspectRatio: '16:9', imageSize: '2K' })
})

test('extractT3Result：兼容 inlineData/inline_data，收集文字与 blockReason', () => {
  const json = {
    candidates: [{
      finishReason: 'STOP',
      content: { parts: [
        { text: 'ok' },
        { inlineData: { mimeType: 'image/png', data: 'AAA' } },
        { inline_data: { mime_type: 'image/jpeg', data: 'BBB' } },
      ] },
    }],
    promptFeedback: {},
  }
  const r = extractT3Result(json)
  assert.equal(r.images.length, 2)
  assert.equal(r.images[0].mimeType, 'image/png')
  assert.equal(r.images[1].mimeType, 'image/jpeg')
  assert.deepEqual(r.texts, ['ok'])
  assert.equal(r.finishReason, 'STOP')
  assert.equal(r.blockReason, null)
})

test('estimateCostUsd：按官方价估算；未知模型返回 null', () => {
  assert.equal(estimateCostUsd({ imageSize: '2K', variants: 1 }), 0.136)
  assert.equal(estimateCostUsd({ imageSize: '2K', variants: 1, referenceCount: 1 }), 0.1371)
  assert.equal(estimateCostUsd({ imageSize: '4K', variants: 2 }), 0.482)
  assert.equal(estimateCostUsd({ model: 'gemini-nano-banana-2.1' }), null)
  assert.ok(T3_MODELS['gemini-3-pro-image'].pricePerImage['4K'] === 0.24)
})

test('mapT3Error：鉴权/配额/参数/模型/未知分别映射', () => {
  assert.equal(mapT3Error(401, { error: { message: 'bad key' } }).code, 'T3_AUTH')
  assert.equal(mapT3Error(429, '').code, 'T3_QUOTA')
  assert.equal(mapT3Error(400, '').code, 'T3_BAD_REQUEST')
  assert.equal(mapT3Error(404, '').code, 'T3_MODEL_NOT_FOUND')
  assert.equal(mapT3Error(500, '').code, 'T3_API_ERROR')
  const e = mapT3Error(401, 'x', { model: 'm', baseUrl: 'b' })
  assert.ok(!String(e.message).includes('key='))
})

test('callT3：mock fetch 成功路径解析图片并带出 usage', async () => {
  const calls = []
  const fakeFetch = async (url, init) => {
    calls.push({ url, init })
    const body = JSON.parse(init.body)
    assert.equal(body.contents[0].parts.length, 2)
    return {
      ok: true, status: 200,
      text: async () => JSON.stringify({
        candidates: [{ finishReason: 'STOP', content: { parts: [{ inlineData: { mimeType: 'image/png', data: 'QUJD' } }] } }],
        usageMetadata: { totalTokenCount: 42 },
      }),
    }
  }
  const cfg = resolveT3Config({ nanoBananaApiKey: 'k' }, {})
  const r = await callT3({ config: cfg, prompt: 'p', images: [{ mimeType: 'image/png', data: 'AAA' }], fetchImpl: fakeFetch })
  assert.equal(r.images.length, 1)
  assert.equal(r.images[0].data, 'QUJD')
  assert.equal(calls.length, 1)
  assert.match(calls[0].url, /gemini-3-pro-image:generateContent/)
  assert.match(calls[0].url, /key=k/)
})

test('callT3：401 抛 T3_AUTH；无图片抛 T3_NO_IMAGE；未配置抛 T3_NOT_CONFIGURED', async () => {
  const cfg = resolveT3Config({ nanoBananaApiKey: 'k' }, {})
  await assert.rejects(
    callT3({ config: cfg, prompt: 'p', fetchImpl: async () => ({ ok: false, status: 401, text: async () => '{"error":{"message":"x"}}' }) }),
    (e) => e.code === 'T3_AUTH',
  )
  await assert.rejects(
    callT3({ config: cfg, prompt: 'p', fetchImpl: async () => ({ ok: true, status: 200, text: async () => JSON.stringify({ candidates: [{ content: { parts: [{ text: 'blocked' }] } }] }) }) }),
    (e) => e.code === 'T3_NO_IMAGE',
  )
  await assert.rejects(callT3({ config: resolveT3Config({}, {}), prompt: 'p' }), (e) => e.code === 'T3_NOT_CONFIGURED')
})
