// T3（Nano Banana Pro / APIYI 中转站）纯逻辑单测：不发真实请求、不需要 API key。
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  resolveT3Config, inspectT3Availability, buildSheetPrompt, buildT3RequestBody,
  extractT3Result, extractImageUrls, sniffImageMime, estimateCostUsd, mapT3Error, callT3,
  T3_DEFAULT_MODEL, T3_MODELS, T3_PRESETS,
} from '../lib/nanobanana.js'

test('resolveT3Config：无 key -> configured=false，默认官方/query/camel/IMAGE', () => {
  const c = resolveT3Config({}, {})
  assert.equal(c.configured, false)
  assert.equal(c.model, T3_DEFAULT_MODEL)
  assert.equal(c.provider, 'official')
  assert.equal(c.baseUrl, 'https://generativelanguage.googleapis.com/v1beta')
  assert.equal(c.auth, 'query')
  assert.equal(c.bodyStyle, 'camel')
  assert.deepEqual(c.responseModalities, ['IMAGE'])
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

test('resolveT3Config：APIYI 预设（bearer + api.apiyi.com + gemini-3-pro-image）', () => {
  const c = resolveT3Config({ nanoBananaProvider: 'apiyi', nanoBananaApiKey: 'k' }, {})
  assert.equal(c.provider, 'apiyi')
  assert.equal(c.baseUrl, 'https://api.apiyi.com/v1beta')
  assert.equal(c.auth, 'bearer')
  assert.equal(c.bodyStyle, 'camel')
  assert.equal(c.model, 'gemini-3-pro-image')
  assert.equal(T3_PRESETS.apiyi.baseUrl, 'https://api.apiyi.com/v1beta')
})

test('resolveT3Config：默认 auto 不能覆盖 provider 预设（APIYI 仍 bearer）', () => {
  const c = resolveT3Config({
    nanoBananaProvider: 'apiyi',
    nanoBananaApiKey: 'k',
    nanoBananaAuth: 'auto',
    nanoBananaBodyStyle: 'auto',
  }, {})
  assert.equal(c.auth, 'bearer')
  assert.equal(c.bodyStyle, 'camel')
})

test('resolveT3Config：config 优先于 env；尺寸/比例/上限被规整', () => {
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

test('resolveT3Config：可覆盖 auth/bodyStyle；非法尺寸/比例回落', () => {
  const c = resolveT3Config({
    nanoBananaProvider: 'custom',
    nanoBananaApiKey: 'k',
    nanoBananaBaseUrl: 'https://relay.example.com/v1beta/',
    nanoBananaAuth: 'query',
    nanoBananaBodyStyle: 'snake',
    nanoBananaImageSize: '8K',
    nanoBananaAspectRatio: '7:3',
  }, {})
  assert.equal(c.baseUrl, 'https://relay.example.com/v1beta')
  assert.equal(c.auth, 'query')
  assert.equal(c.bodyStyle, 'snake')
  assert.equal(c.imageSize, '2K')
  assert.equal(c.aspectRatio, '16:9')
})

test('inspectT3Availability：无 key 给出 reason 与 fallback=t2；有 key 时带 provider/baseUrl', () => {
  const no = inspectT3Availability({}, {})
  assert.equal(no.ok, false)
  assert.equal(no.fallback, 't2')
  assert.match(no.reasons[0], /GEMINI_API_KEY|apiKey/)

  const yes = inspectT3Availability({ nanoBananaProvider: 'apiyi', nanoBananaApiKey: 'k' }, {})
  assert.equal(yes.ok, true)
  assert.equal(yes.fallback, null)
  assert.equal(yes.provider, 'apiyi')
  assert.equal(yes.provider_label, 'APIYI 中转站')
  assert.equal(yes.auth, 'bearer')
  assert.equal(yes.price_per_image_usd, 0.134)
})

test('buildSheetPrompt：turnaround 要三视图 + 头/上身/下身/手/脚/服装拆解', () => {
  const turn = buildSheetPrompt({ mode: 'turnaround', character: '丰川祥子' })
  for (const kw of ['三视图', '正面', '侧面', '背面', '头部', '上半身', '下半身', '手部', '脚部', '服装拆解']) {
    assert.ok(turn.includes(kw), `turnaround 缺关键词: ${kw}`)
  }
  assert.match(turn, /丰川祥子/)
  assert.match(turn, /不添加参考图没有/)
})

test('buildSheetPrompt：breakdown 只拆存在的部件，去掉编造/私密提示', () => {
  const br = buildSheetPrompt({ mode: 'breakdown' })
  assert.match(br, /拆解/)
  assert.match(br, /平铺/)
  assert.match(br, /不要虚构/)
  for (const bad of ['私密', '生活切片', '表情集', '脑补']) {
    assert.ok(!br.includes(bad), `breakdown 不应包含: ${bad}`)
  }
  assert.throws(() => buildSheetPrompt({ mode: 'custom' }), (e) => e.code === 'INVALID_PARAMS')
  assert.match(buildSheetPrompt({ mode: 'custom', prompt: '只画正面' }), /只画正面/)
})

test('buildT3RequestBody：默认 camelCase inlineData + IMAGE modality', () => {
  const body = buildT3RequestBody({
    prompt: 'hello',
    images: [{ mimeType: 'image/png', data: 'AAA' }, { mimeType: 'image/jpeg', data: 'BBB' }],
    aspectRatio: '16:9',
    imageSize: '2K',
  })
  const parts = body.contents[0].parts
  assert.equal(parts.length, 3)
  assert.equal(parts[0].text, 'hello')
  assert.equal(parts[1].inlineData.mimeType, 'image/png')
  assert.equal(parts[1].inlineData.data, 'AAA')
  assert.deepEqual(body.generationConfig.responseModalities, ['IMAGE'])
  assert.deepEqual(body.generationConfig.imageConfig, { aspectRatio: '16:9', imageSize: '2K' })
})

test('buildT3RequestBody：snake 风格 + 自定义 responseModalities', () => {
  const body = buildT3RequestBody({
    prompt: 'x', images: [{ mimeType: 'image/webp', data: 'CC' }],
    bodyStyle: 'snake', responseModalities: ['TEXT', 'IMAGE'],
  })
  assert.equal(body.contents[0].parts[1].inline_data.mime_type, 'image/webp')
  assert.deepEqual(body.generationConfig.responseModalities, ['TEXT', 'IMAGE'])
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

test('extractImageUrls：从 APIYI 文本里识别签名图片 URL', () => {
  const t = '生成的图片：https://mycdn-gg.oss-us-west-1.aliyuncs.com/response_images/97713/2026/11/08/x.png?X-Amz-Signature=abc 。'
  const urls = extractImageUrls(t)
  assert.equal(urls.length, 1)
  assert.match(urls[0], /^https:\/\/mycdn-gg\.oss-us-west-1\.aliyuncs\.com\/response_images\//)
  assert.equal(extractImageUrls('no url here').length, 0)
})

test('callT3：中转站把图放在 text URL 时自动下载成 base64', async () => {
  const imageUrl = 'https://mycdn-gg.oss-us-west-1.aliyuncs.com/response_images/1/x.png?X-Amz-Signature=abc'
  const calls = []
  const fakeFetch = async (url, init) => {
    calls.push(url)
    if (calls.length === 1) {
      return {
        ok: true, status: 200,
        text: async () => JSON.stringify({
          candidates: [{ finishReason: 'STOP', content: { parts: [{ text: imageUrl }] } }],
        }),
      }
    }
    assert.equal(url, imageUrl)
    return {
      ok: true, status: 200,
      headers: { get: () => 'image/png' },
      arrayBuffer: async () => Uint8Array.from([137, 80, 78, 71]).buffer,
    }
  }
  const cfg = resolveT3Config({ nanoBananaProvider: 'apiyi', nanoBananaApiKey: 'k' }, {})
  const r = await callT3({ config: cfg, prompt: 'p', fetchImpl: fakeFetch })
  assert.equal(r.images.length, 1)
  assert.equal(r.images[0].mimeType, 'image/png')
  assert.equal(r.images[0].data, Buffer.from([137, 80, 78, 71]).toString('base64'))
})

test('sniffImageMime：按文件头识别 png/jpeg/webp（中转站 content-type 可能不准）', () => {
  assert.equal(sniffImageMime(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0])), 'image/png')
  assert.equal(sniffImageMime(Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0, 0, 0, 0, 0, 0, 0, 0])), 'image/jpeg')
  assert.equal(sniffImageMime(Buffer.from('RIFF0000WEBPVP8 ', 'ascii')), 'image/webp')
  assert.equal(sniffImageMime(Buffer.from('not-an-image')), null)
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

test('callT3：官方 query 鉴权，mock fetch 解析图片', async () => {
  const calls = []
  const fakeFetch = async (url, init) => {
    calls.push({ url, init })
    const body = JSON.parse(init.body)
    assert.equal(body.contents[0].parts.length, 2)
    assert.equal(body.contents[0].parts[1].inlineData.data, 'AAA')
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
  assert.match(calls[0].url, /gemini-3-pro-image:generateContent\?key=k/)
  assert.equal(calls[0].init.headers.authorization, undefined)
})

test('callT3：APIYI bearer 鉴权，URL 不带 key', async () => {
  const calls = []
  const fakeFetch = async (url, init) => {
    calls.push({ url, init })
    return { ok: true, status: 200, text: async () => JSON.stringify({ candidates: [{ content: { parts: [{ inlineData: { mimeType: 'image/png', data: 'QQ==' } }] } }] }) }
  }
  const cfg = resolveT3Config({ nanoBananaProvider: 'apiyi', nanoBananaApiKey: 'relay-key' }, {})
  await callT3({ config: cfg, prompt: 'p', fetchImpl: fakeFetch })
  assert.equal(calls[0].url, 'https://api.apiyi.com/v1beta/models/gemini-3-pro-image:generateContent')
  assert.equal(calls[0].init.headers.authorization, 'Bearer relay-key')
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
