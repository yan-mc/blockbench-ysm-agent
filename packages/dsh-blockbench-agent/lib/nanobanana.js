/**
 * T3：Nano Banana Pro（Gemini 3 Pro Image）云端拆解/三视图生成。
 *
 * 定位（docs/25）：T3 是**云端增强层**，优先级高于本地 T2/T1：
 *   T3 Nano Banana Pro → 多参考图生成三视图 / 全景拆解板（生成式推断，需付费 API）
 *   T2 See-through    → 本地 23–29 层语义分层 + 遮挡补全
 *   T1 SAM2           → 本地轻量部件分割（只给可见区域）
 *
 * 约束（写进代码与文档，避免"把生成当还原"）：
 *   - 需要付费 API key；支持官方 Gemini API，也支持兼容 Gemini 格式的中转站
 *     （如 APIYI：baseUrl https://api.apiyi.com/v1beta，Bearer 鉴权）。
 *   - Pro Image 无免费层；中转站价格以服务商为准，本模块只按 Google 官方价估算。
 *   - 生成结果含 SynthID 水印；上传参考图视为把素材发给 Google，注意版权/隐私。
 *   - 输出是**推断**：背面、内侧、被遮挡部件都是模型脑补，必须人工复核并记入 spec.gaps。
 *   - 不替代本地流水线：没有 key / 调用失败时降级 T2。
 *
 * 本模块只做纯逻辑（配置、提示词、请求体、响应解析、成本估算），
 * 网络与文件落盘在 index.js 的工具 handler 里完成，便于单测。
 */

export const T3_DEFAULT_MODEL = 'gemini-3-pro-image'
export const T3_DEFAULT_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta'
export const T3_DEFAULT_ASPECT = '16:9'
export const T3_DEFAULT_IMAGE_SIZE = '2K'

/** 官方 Gemini API 文档（2026-11）列出的图像模型。 */
export const T3_MODELS = {
  'gemini-3-pro-image': {
    label: 'Nano Banana Pro（Gemini 3 Pro Image）',
    note: '复杂指令/一致性/高保真文字最强；推荐用于拆解板',
    pricePerImage: { '1K': 0.134, '2K': 0.134, '4K': 0.24 },
  },
  'gemini-nano-banana-2.1': {
    label: 'Nano Banana 2.1',
    note: '高性价比工作马；多参考图一致性略逊于 Pro',
    pricePerImage: null, // 以官方 pricing 页为准；不猜数字
  },
  'gemini-3.1-flash-image': {
    label: 'Nano Banana 2（Gemini 3.1 Flash Image）',
    note: '上一代高性价比模型；支持多参考图/4K',
    pricePerImage: null,
  },
  'gemini-2.5-flash-image': {
    label: 'Nano Banana（Gemini 2.5 Flash Image，旧版）',
    note: '旧版；仅作兜底',
    pricePerImage: null,
  },
}

export const T3_ASPECTS = ['1:1', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4', '9:16', '16:9', '21:9']
export const T3_IMAGE_SIZES = ['1K', '2K', '4K']
export const T3_MODES = ['turnaround', 'breakdown', 'custom']

/**
 * 服务商预设：官方 Gemini / APIYI 中转站 / 自定义。
 * APIYI 文档（https://docs.apiyi.com/api-capabilities/nano-banana-image/image-edit）
 * 使用 `Authorization: Bearer <token>` + 与官方一致的 generateContent body
 * （camelCase inlineData/mimeType）；baseUrl 为 https://api.apiyi.com/v1beta。
 */
export const T3_PRESETS = {
  official: {
    label: 'Google Gemini 官方',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta',
    auth: 'query',
    bodyStyle: 'camel',
    responseModalities: ['IMAGE'],
    model: 'gemini-3-pro-image',
  },
  apiyi: {
    label: 'APIYI 中转站',
    baseUrl: 'https://api.apiyi.com/v1beta',
    auth: 'bearer',
    bodyStyle: 'camel',
    responseModalities: ['IMAGE'],
    model: 'gemini-3-pro-image',
  },
  custom: {
    label: '自定义中转站',
    baseUrl: '',
    auth: 'bearer',
    bodyStyle: 'camel',
    responseModalities: ['IMAGE'],
    model: 'gemini-3-pro-image',
  },
}

/** 把配置 + 环境变量归一成 T3 运行配置。 */
export function resolveT3Config(config = {}, env = process.env) {
  const nb = config?.nanoBanana && typeof config.nanoBanana === 'object' ? config.nanoBanana : {}
  const pick = (...vals) => vals.find((v) => typeof v === 'string' && v.trim()) ?? ''
  const provider = pick(nb.provider, config?.nanoBananaProvider, 'official').toLowerCase()
  const preset = T3_PRESETS[provider] ?? T3_PRESETS.official
  const apiKey = pick(nb.apiKey, config?.nanoBananaApiKey, env?.GEMINI_API_KEY, env?.GOOGLE_API_KEY, env?.NANO_BANANA_API_KEY)
  const apiKeySource = nb.apiKey ? 'nanoBanana.apiKey'
    : config?.nanoBananaApiKey ? 'nanoBananaApiKey'
      : env?.GEMINI_API_KEY ? 'env:GEMINI_API_KEY'
        : env?.GOOGLE_API_KEY ? 'env:GOOGLE_API_KEY'
          : env?.NANO_BANANA_API_KEY ? 'env:NANO_BANANA_API_KEY'
            : ''
  const model = pick(nb.model, config?.nanoBananaModel, preset.model, T3_DEFAULT_MODEL)
  const baseUrl = pick(nb.baseUrl, config?.nanoBananaBaseUrl, preset.baseUrl, T3_DEFAULT_BASE_URL).replace(/\/+$/, '')
  const auth = pick(nb.auth, config?.nanoBananaAuth, preset.auth, 'query').toLowerCase() === 'bearer' ? 'bearer' : 'query'
  const bodyStyle = pick(nb.bodyStyle, config?.nanoBananaBodyStyle, preset.bodyStyle, 'camel').toLowerCase() === 'snake' ? 'snake' : 'camel'
  const rm = Array.isArray(nb.responseModalities) ? nb.responseModalities
    : Array.isArray(config?.nanoBananaResponseModalities) ? config.nanoBananaResponseModalities
      : (preset.responseModalities ?? ['IMAGE'])
  const imageSize = pick(nb.imageSize, config?.nanoBananaImageSize, T3_DEFAULT_IMAGE_SIZE).toUpperCase()
  const aspectRatio = pick(nb.aspectRatio, config?.nanoBananaAspectRatio, T3_DEFAULT_ASPECT)
  const maxReferences = clampInt(nb.maxReferences ?? config?.nanoBananaMaxReferences, 1, 14, 6)
  const timeoutMs = clampInt(nb.timeoutMs ?? config?.nanoBananaTimeoutMs, 10000, 600000, 180000)
  return {
    configured: Boolean(apiKey),
    apiKey,
    apiKeySource,
    provider,
    providerLabel: preset.label,
    model,
    baseUrl,
    auth,
    bodyStyle,
    responseModalities: rm.length ? rm : ['IMAGE'],
    imageSize: T3_IMAGE_SIZES.includes(imageSize) ? imageSize : T3_DEFAULT_IMAGE_SIZE,
    aspectRatio: T3_ASPECTS.includes(aspectRatio) ? aspectRatio : T3_DEFAULT_ASPECT,
    maxReferences,
    timeoutMs,
    modelInfo: T3_MODELS[model] ?? null,
  }
}

function clampInt(v, min, max, fallback) {
  const n = Number(v)
  if (!Number.isFinite(n)) return fallback
  return Math.max(min, Math.min(max, Math.round(n)))
}

/** 给 bb_seg_probe 用：T3 是否可用（只看配置，不发网络请求、不消耗额度）。 */
export function inspectT3Availability(config = {}, env = process.env) {
  const c = resolveT3Config(config, env)
  const reasons = []
  if (!c.configured) reasons.push('未配置 API key（nanoBanana.apiKey / nanoBananaApiKey / 环境变量 GEMINI_API_KEY）')
  return {
    ok: c.configured,
    label: 'T3 云端拆解（Nano Banana Pro）',
    desc: '多参考图 → 严格三视图 + 部件分解图 / 全展开拆解板；生成式推断，需付费 API',
    provider: c.provider,
    provider_label: c.providerLabel,
    model: c.model,
    model_label: c.modelInfo?.label ?? c.model,
    base_url: c.baseUrl,
    auth: c.auth,
    body_style: c.bodyStyle,
    api_key_source: c.apiKeySource || null,
    image_size: c.imageSize,
    aspect_ratio: c.aspectRatio,
    max_references: c.maxReferences,
    price_per_image_usd: c.modelInfo?.pricePerImage?.[c.imageSize] ?? null,
    reasons,
    fallback: c.configured ? null : 't2',
    note: c.configured
      ? `会调用 ${c.providerLabel}（${c.baseUrl}）；参考图会上传给服务商；生成图结果必须人工复核`
      : '没有 key 时降级用 T2（bb_seg_run，本地 See-through）',
  }
}

const TURNAROUND_PROMPT = [
  '你是资深游戏角色概念设计师，正在为 3D 建模制作角色设定图。',
  '以用户提供的参考图（同一角色的官方立绘/设定图，可能有多张多角度）作为**唯一身份依据**，',
  '生成一张排版清晰、等比例、可量尺寸的**正交三视图 + 部件分解图**。',
  '',
  '一、三视图（必须清晰、完整）',
  '- 横向并排：严格正面、严格 90° 正侧面、严格背面，三个完整全身视图；',
  '- 三视图等高等比例，头顶与脚底分别对齐同一条水平基线；',
  '- 中性站立姿势（A-pose 或双臂自然下垂），不保留参考图的坐姿/动作/舞蹈姿势；',
  '- 纯白或极浅灰背景；无场景、无道具、无特效、无水印、无多余装饰文字；',
  '- 严格保持脸型、五官、瞳色、发型、角/兽耳、服装结构、层次、配色、纹样与配饰；',
  '',
  '二、单独部位图（必须逐项画出，不要只画全身）',
  '- 头部：正面、侧面、背面特写，清晰画出五官、发型、角/耳、发饰；',
  '- 上半身：正面、侧面（躯干 + 手臂 + 上衣结构）；',
  '- 下半身：正面、侧面（腰胯 + 腿 + 鞋/靴）；',
  '- 手部：正/背/侧面（被袖子遮挡时画出袖口连接结构）；',
  '- 脚部/鞋：正面、侧面、鞋底；',
  '- 服装拆解：把每件衣服和配饰拆成独立单品平铺展示（外套、上衣、裙/裤、腰带/绑带、袖套、手套、鞋、发饰、胸针、角环等），一件一张，保持原配色与纹样；',
  '- 对应关系：可用细线/编号把拆解单品连到三视图上的对应位置（编号少而清晰）。',
  '',
  '三、约束',
  '- 只出现参考图里的这一个角色；不添加参考图没有的配饰、花纹、道具、内着或其他物品；',
  '- 不画参考图原有的背景、家具、乐器、特效；',
  '- 参考图缺少背面/侧面信息时，按可见结构做合理推断，三视图与拆解件之间必须自洽；',
  '- 只输出一张图，不要输出大段文字说明。',
].join('\n')

const BREAKDOWN_PROMPT = [
  '你是资深游戏角色概念设计师，正在制作**角色部件拆解设定图**（用于 3D 建模）。',
  '以用户提供的同一角色参考图（可多张多角度）作为唯一设计依据，生成一张"全展开部件设定板"。',
  '',
  '1. 中心位：角色全身中性站姿（正面），可在旁边加正/侧/背三视图小图；',
  '2. 拆解部件：把角色拆成独立部件，按区域整齐排开，互不遮挡、平铺摆放：',
  '- 头部：正/侧/背特写（五官、发型、角/兽耳、发饰分别画出）；',
  '- 躯干：正面/背面（上衣、胸饰、腰带逐件分开）；',
  '- 双臂与手：左右分开，画清袖口与手套连接；',
  '- 双腿与脚：左右分开，画清裤/袜/鞋的结构与鞋底；',
  '- 每件服装单品：外套、上衣、裙/裤、袖套、腰带/绑带、鞋/靴逐件平铺；',
  '- 每件配饰/道具：发饰、胸针、角环、挂件等逐个放大展示。',
  '3. 标注：用细编号或短标签说明部件名称/连接关系；保持原设计、配色、纹样、材质；',
  '4. 约束：只拆参考图中**确实存在**的部件；不添加参考图没有的服装、道具、内着、花纹或生活物品；',
  '被遮挡的结构可按可见设计语言补全，但必须与原设计一致；',
  '纯白或浅灰背景，只输出一张排版清晰的设计图，不要大段文字。',
].join('\n')

const COMMON_GUARD = [
  '重要约束：',
  '- 只能出现参考图里的这一个角色，不要添加其他人物、logo、签名或与角色无关的文字；',
  '- 不要画参考图原图里的背景、家具、乐器、特效等场景元素；',
  '- 不要虚构参考图里不存在的服装、配饰、道具、内着或生活物品；',
  '- 如果参考图是复杂动作，先把角色还原成中性站姿再拆解。',
].join('\n')

/**
 * 构造 T3 提示词。
 * @param {object} p
 * @param {'turnaround'|'breakdown'|'custom'} [p.mode]
 * @param {string} [p.character] 角色名（可选，只用于提示词身份锚定）
 * @param {string} [p.prompt]    custom 模式或追加说明
 */
export function buildSheetPrompt({ mode = 'turnaround', character = '', prompt = '' } = {}) {
  const m = T3_MODES.includes(mode) ? mode : 'turnaround'
  const head = character ? `角色：${character}。\n` : ''
  if (m === 'custom') {
    const custom = String(prompt || '').trim()
    if (!custom) {
      const err = new Error('custom 模式必须给 prompt')
      err.code = 'INVALID_PARAMS'
      throw err
    }
    return `${head}${custom}`
  }
  const base = m === 'breakdown' ? BREAKDOWN_PROMPT : TURNAROUND_PROMPT
  const extra = String(prompt || '').trim()
  return `${head}${base}\n\n${COMMON_GUARD}${extra ? `\n\n补充要求：\n${extra}` : ''}`
}

/**
 * 构造 generateContent REST 请求体（Gemini API v1beta）。
 * @param {object} p
 * @param {string} p.prompt
 * @param {Array<{mimeType:string,data:string}>} p.images base64
 * @param {string} [p.aspectRatio]
 * @param {string} [p.imageSize]
 */
export function buildT3RequestBody({
  prompt, images = [], aspectRatio = T3_DEFAULT_ASPECT, imageSize = T3_DEFAULT_IMAGE_SIZE,
  bodyStyle = 'camel', responseModalities = ['IMAGE'],
} = {}) {
  const parts = [{ text: String(prompt || '') }]
  for (const img of images) {
    if (!img?.data) continue
    const mime = img.mimeType || 'image/png'
    parts.push(bodyStyle === 'snake'
      ? { inline_data: { mime_type: mime, data: img.data } }
      : { inlineData: { mimeType: mime, data: img.data } })
  }
  const rm = Array.isArray(responseModalities) && responseModalities.length ? responseModalities : ['IMAGE']
  return {
    // 不写 role：官方与 APIYI 文档示例均为 {"contents":[{"parts":[...]}]}，兼容性最好
    contents: [{ parts }],
    generationConfig: {
      responseModalities: rm,
      imageConfig: {
        aspectRatio: T3_ASPECTS.includes(aspectRatio) ? aspectRatio : T3_DEFAULT_ASPECT,
        imageSize: T3_IMAGE_SIZES.includes(imageSize) ? imageSize : T3_DEFAULT_IMAGE_SIZE,
      },
    },
  }
}

/** 从 generateContent 响应中提取所有图片与文字。 */
export function extractT3Result(json) {
  const images = []
  const texts = []
  const candidates = Array.isArray(json?.candidates) ? json.candidates : []
  for (const cand of candidates) {
    const parts = cand?.content?.parts
    if (!Array.isArray(parts)) continue
    for (const part of parts) {
      const inline = part?.inlineData ?? part?.inline_data
      if (inline?.data) {
        images.push({ data: inline.data, mimeType: inline.mimeType ?? inline.mime_type ?? 'image/png' })
      } else if (typeof part?.text === 'string' && part.text.trim()) {
        texts.push(part.text)
      }
    }
  }
  const blockReason = json?.promptFeedback?.blockReason ?? null
  const finishReason = candidates[0]?.finishReason ?? null
  return { images, texts, blockReason, finishReason, usage: json?.usageMetadata ?? null }
}

/** 官方价估算（输出图 + 粗估图片输入 token；只用于调用前提示，非账单）。 */
export function estimateCostUsd({ model = T3_DEFAULT_MODEL, imageSize = T3_DEFAULT_IMAGE_SIZE, variants = 1, referenceCount = 0 } = {}) {
  const info = T3_MODELS[model]
  const per = info?.pricePerImage?.[imageSize]
  if (!Number.isFinite(per)) return null
  const input = Math.max(0, referenceCount) * 0.0011 // 官方：约 $0.0011/张输入图
  const text = 0.002
  return +(input + text + per * Math.max(1, variants)).toFixed(4)
}

/** Gemini REST 错误 → 可读的 T3 错误。 */
export function mapT3Error(status, body, { model, baseUrl } = {}) {
  const detail = (() => {
    try {
      const j = typeof body === 'string' ? JSON.parse(body) : body
      return j?.error?.message || j?.message || (typeof body === 'string' ? body.slice(0, 500) : '')
    } catch { return typeof body === 'string' ? body.slice(0, 500) : '' }
  })()
  const mk = (code, message, hint) => {
    const e = new Error(message)
    e.code = code
    if (hint) e.hint = hint
    return e
  }
  if (status === 401 || status === 403) {
    return mk('T3_AUTH', `T3 API 鉴权失败（HTTP ${status}）: ${detail || 'API key 无效或无权限'}`,
      '检查 nanoBanana.apiKey / GEMINI_API_KEY；Pro Image 需要启用计费的项目')
  }
  if (status === 429) {
    return mk('T3_QUOTA', `T3 触发限流/配额（HTTP 429）: ${detail || 'rate limited'}`,
      '降低 variants、换时间重试，或改用 gemini-nano-banana-2.1；降级 T2 也可')
  }
  if (status === 400) {
    return mk('T3_BAD_REQUEST', `T3 请求被拒（HTTP 400）: ${detail || '参数错误'}`,
      '检查参考图格式/大小、宽高比、image_size；参考图过多时减少数量')
  }
  if (status === 404) {
    return mk('T3_MODEL_NOT_FOUND', `T3 模型/接口不存在（HTTP 404）: ${detail || model || ''}`,
      `检查模型 id（当前 ${model}）与 baseUrl（${baseUrl}）`)
  }
  return mk('T3_API_ERROR', `T3 生成失败（HTTP ${status}）: ${detail || 'unknown error'}`, '可重试一次；仍失败则降级 T2')
}

/**
 * 调用 Gemini generateContent 生成图片。
 * 依赖注入 fetchImpl 便于单测。
 * @returns {Promise<{images:Array,texts:string[],usage:object|null,model:string,elapsedMs:number}>}
 */
export async function callT3({
  config, prompt, images = [], aspectRatio, imageSize, timeoutMs, fetchImpl = globalThis.fetch, signal,
} = {}) {
  const c = config ?? resolveT3Config({})
  if (!c.configured) {
    const e = new Error('T3 未配置 API key')
    e.code = 'T3_NOT_CONFIGURED'
    e.hint = '配置 nanoBanana.apiKey（或环境变量 GEMINI_API_KEY），没有 key 时用 bb_seg_run（T2）'
    throw e
  }
  if (typeof fetchImpl !== 'function') {
    const e = new Error('当前运行环境没有 fetch')
    e.code = 'T3_NO_FETCH'
    throw e
  }
  const endpoint = `${c.baseUrl}/models/${encodeURIComponent(c.model)}:generateContent`
  const url = c.auth === 'bearer' ? endpoint : `${endpoint}?key=${encodeURIComponent(c.apiKey)}`
  const body = buildT3RequestBody({
    prompt,
    images,
    aspectRatio: aspectRatio ?? c.aspectRatio,
    imageSize: imageSize ?? c.imageSize,
    bodyStyle: c.bodyStyle,
    responseModalities: c.responseModalities,
  })
  const headers = { 'content-type': 'application/json' }
  if (c.auth === 'bearer') headers.authorization = `Bearer ${c.apiKey}`
  const ac = new AbortController()
  const timer = setTimeout(() => ac.abort(new Error('T3 timeout')), timeoutMs ?? c.timeoutMs)
  const onAbort = () => ac.abort(signal.reason ?? new Error('aborted'))
  if (signal) {
    if (signal.aborted) onAbort()
    else signal.addEventListener('abort', onAbort, { once: true })
  }
  const t0 = Date.now()
  try {
    const res = await fetchImpl(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal: ac.signal,
    })
    const text = await res.text()
    if (!res.ok) throw mapT3Error(res.status, text, c)
    let json
    try { json = JSON.parse(text) } catch {
      const e = new Error('T3 返回不是合法 JSON')
      e.code = 'T3_BAD_RESPONSE'
      throw e
    }
    const parsed = extractT3Result(json)
    if (!parsed.images.length) {
      const reason = parsed.blockReason || parsed.finishReason || (parsed.texts[0] ?? '').slice(0, 300) || '模型未返回图片'
      const e = new Error(`T3 未返回图片：${reason}`)
      e.code = 'T3_NO_IMAGE'
      e.hint = parsed.blockReason ? '内容被安全策略拦截；换参考图/去掉敏感描述后重试' : '可重试或降级 T2'
      throw e
    }
    return { ...parsed, model: c.model, elapsedMs: Date.now() - t0 }
  } catch (error) {
    if (error?.code) throw error
    if (ac.signal.aborted) {
      const e = new Error('T3 请求超时/被取消')
      e.code = 'T3_TIMEOUT'
      e.hint = '重试一次；仍失败则降级 T2（bb_seg_run）'
      throw e
    }
    const e = new Error(`T3 网络请求失败: ${error?.message ?? String(error)}`)
    e.code = 'T3_NETWORK'
    e.hint = '检查网络/代理/nanoBananaBaseUrl；重试或降级 T2'
    throw e
  } finally {
    clearTimeout(timer)
    if (signal) signal.removeEventListener('abort', onAbort)
  }
}
