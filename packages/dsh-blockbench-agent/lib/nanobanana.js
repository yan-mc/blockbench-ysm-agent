/**
 * T3：Nano Banana Pro（Gemini 3 Pro Image）云端拆解/三视图生成。
 *
 * 定位（docs/25）：T3 是**云端增强层**，优先级高于本地 T2/T1：
 *   T3 Nano Banana Pro → 多参考图生成三视图 / 全景拆解板（生成式推断，需付费 API）
 *   T2 See-through    → 本地 23–29 层语义分层 + 遮挡补全
 *   T1 SAM2           → 本地轻量部件分割（只给可见区域）
 *
 * 约束（写进代码与文档，避免"把生成当还原"）：
 *   - 需要 Google Gemini API key（付费层；Pro Image 无免费层）。
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

/** 把配置 + 环境变量归一成 T3 运行配置。 */
export function resolveT3Config(config = {}, env = process.env) {
  const nb = config?.nanoBanana && typeof config.nanoBanana === 'object' ? config.nanoBanana : {}
  const pick = (...vals) => vals.find((v) => typeof v === 'string' && v.trim()) ?? ''
  const apiKey = pick(nb.apiKey, config?.nanoBananaApiKey, env?.GEMINI_API_KEY, env?.GOOGLE_API_KEY, env?.NANO_BANANA_API_KEY)
  const apiKeySource = nb.apiKey ? 'nanoBanana.apiKey'
    : config?.nanoBananaApiKey ? 'nanoBananaApiKey'
      : env?.GEMINI_API_KEY ? 'env:GEMINI_API_KEY'
        : env?.GOOGLE_API_KEY ? 'env:GOOGLE_API_KEY'
          : env?.NANO_BANANA_API_KEY ? 'env:NANO_BANANA_API_KEY'
            : ''
  const model = pick(nb.model, config?.nanoBananaModel, T3_DEFAULT_MODEL)
  const baseUrl = pick(nb.baseUrl, config?.nanoBananaBaseUrl, T3_DEFAULT_BASE_URL).replace(/\/+$/, '')
  const imageSize = pick(nb.imageSize, config?.nanoBananaImageSize, T3_DEFAULT_IMAGE_SIZE).toUpperCase()
  const aspectRatio = pick(nb.aspectRatio, config?.nanoBananaAspectRatio, T3_DEFAULT_ASPECT)
  const maxReferences = clampInt(nb.maxReferences ?? config?.nanoBananaMaxReferences, 1, 14, 6)
  const timeoutMs = clampInt(nb.timeoutMs ?? config?.nanoBananaTimeoutMs, 10000, 600000, 180000)
  return {
    configured: Boolean(apiKey),
    apiKey,
    apiKeySource,
    model,
    baseUrl,
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
  if (!c.configured) reasons.push('未配置 Gemini API key（nanoBanana.apiKey / nanoBananaApiKey / 环境变量 GEMINI_API_KEY）')
  return {
    ok: c.configured,
    label: 'T3 云端拆解（Nano Banana Pro）',
    desc: '多参考图 → 严格三视图 / 全景式深度拆解板；生成式推断，需付费 API',
    model: c.model,
    model_label: c.modelInfo?.label ?? c.model,
    api_key_source: c.apiKeySource || null,
    image_size: c.imageSize,
    aspect_ratio: c.aspectRatio,
    max_references: c.maxReferences,
    price_per_image_usd: c.modelInfo?.pricePerImage?.[c.imageSize] ?? null,
    reasons,
    fallback: c.configured ? null : 't2',
    note: c.configured
      ? '会调用 Google Gemini API；参考图会上传，生成图含 SynthID 水印；结果必须人工复核'
      : '没有 key 时降级用 T2（bb_seg_run，本地 See-through）',
  }
}

const TURNAROUND_PROMPT = [
  '你是资深游戏角色概念设计师，正在为 3D 建模制作严格三视图。',
  '以用户提供的参考图（同一角色的官方立绘 / 设定图，可能有多张多角度）作为**唯一身份依据**，生成一张横向三视图：',
  '- 从左到右：严格正面、严格 90° 正侧面、严格背面，三个完整全身视图；',
  '- 三视图等高等比例，头顶与脚底分别对齐同一条水平基线；',
  '- 中性站立姿势（A-pose 或双臂自然下垂），不要保留参考图里的坐姿、动作、舞蹈姿势；',
  '- 纯白或极浅灰背景；无场景、无道具、无特效、无水印、无多余装饰文字；',
  '- 严格保持脸型、五官、瞳色、发型、角 / 兽耳、服装结构、层次、配色、纹样与配饰；不得新增参考图里没有的元素；',
  '- 参考图缺少背面 / 侧面信息时，按可见结构与设计语言做合理推断，三个视图之间必须自洽；',
  '- 只输出一张图，不要输出文字说明。',
].join('\n')

const BREAKDOWN_PROMPT = [
  '你是一位顶尖的游戏与动漫概念美术设计大师，擅长制作详尽的角色设定图，并具备"像素级拆解"能力：',
  '能透视角色的穿着层级、捕捉微表情变化，把与角色相关的物品具象化还原。',
  '',
  '任务：根据用户提供的同一角色参考图（可能有多张多角度），生成一张"全景式角色深度概念分解图"。',
  '',
  '1. 构图布局：中心位放角色全身立绘（以参考图为准，保持身份特征与服装），作为视觉锚点；',
  '环绕位在四周空白处有序排列拆解元素；用手绘箭头或引导线把拆解物连到中心人物对应部位。',
  '2. 拆解内容：',
  '- 三视图：正面、90° 侧面、背面三个完整全身视图，等高等比例；',
  '- 服装分层：把服装拆成单品展示；多层穿搭要展示脱下外套后的内层状态；',
  '- 表情集：角落画 3–4 个头部特写，展示不同情绪；',
  '- 材质特写：选 1–2 个关键部位放大（布料/皮革/金属/蕾丝等质感）；',
  '- 核心道具与配饰：完整展示，被手挡住或过小的配件单独放大；',
  '- 随身物品：符合角色职业、爱好、性格的日常物件（包袋内容物、小物等），不要低俗内容。',
  '3. 风格与注释：高质量 2D 插画 / 概念设计草图风格，线条干净；米黄、羊皮纸或浅灰设计稿背景；',
  '每个拆解元素旁可加简短手写注释（材质/结构），文字用中文。',
  '',
  '一致性要求：所有视图、拆解单品和中心人物必须是同一个角色、同一套设计；不得改变发色/瞳色/角/服装结构；',
  '参考图里没有明确画出的背面与内侧结构，按设计语言做合理推断，并在画面里保持自洽。',
  '只输出一张图。',
].join('\n')

const COMMON_GUARD = [
  '重要约束：',
  '- 只能出现参考图里的这一个角色，不要添加其他人物、 logo、签名或与角色无关的文字；',
  '- 不要画参考图原图里的背景、家具、乐器、特效等场景元素（拆解板的"道具"区除外）；',
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
export function buildT3RequestBody({ prompt, images = [], aspectRatio = T3_DEFAULT_ASPECT, imageSize = T3_DEFAULT_IMAGE_SIZE } = {}) {
  const parts = [{ text: String(prompt || '') }]
  for (const img of images) {
    if (!img?.data) continue
    parts.push({ inline_data: { mime_type: img.mimeType || 'image/png', data: img.data } })
  }
  return {
    contents: [{ role: 'user', parts }],
    generationConfig: {
      responseModalities: ['TEXT', 'IMAGE'],
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
  const url = `${c.baseUrl}/models/${encodeURIComponent(c.model)}:generateContent?key=${encodeURIComponent(c.apiKey)}`
  const body = buildT3RequestBody({
    prompt,
    images,
    aspectRatio: aspectRatio ?? c.aspectRatio,
    imageSize: imageSize ?? c.imageSize,
  })
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
      headers: { 'content-type': 'application/json' },
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
