/**
 * 「官方基准」：在搜大量同人图之前，先拿到权威说法与少量官方参考图。
 *
 * 为什么要先做这一步（docs/18）：
 *   图搜结果里混着同人图、别的角色、AI 图。没有基准时，模型只能靠"看起来像"判断，
 *   实测踩过：验收那次 15 张里有 1 张是**另一个角色**（鹿島神），靠人肉识别才发现。
 *   先拿到百科文字（发色/瞳色/服装/身高）+ 官方图，后面每张候选都能对得上/对不上。
 *
 * 这里只用公开的 MediaWiki API（萌娘百科 / 维基百科），不抓页面 HTML。
 */

import { normalizeUrl, looksLikeImageUrl } from './refsearch.js'

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36'

/** 权威源（按优先级）。 */
export const CANON_SOURCES = [
  { id: 'moegirl', label: '萌娘百科', api: 'https://zh.moegirl.org.cn/api.php' },
  { id: 'wikipedia', label: '维基百科（中文）', api: 'https://zh.wikipedia.org/w/api.php' },
]

async function jget(url, { timeoutMs = 20000, signal } = {}) {
  const ac = new AbortController()
  const timer = setTimeout(() => ac.abort(), timeoutMs)
  const onAbort = () => ac.abort()
  if (signal) signal.addEventListener('abort', onAbort, { once: true })
  try {
    const res = await fetch(url, {
      headers: { 'User-Agent': UA, 'Accept-Language': 'zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.7' },
      signal: ac.signal,
    })
    const text = await res.text()
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return JSON.parse(text)
  } finally {
    clearTimeout(timer)
    if (signal) signal.removeEventListener('abort', onAbort)
  }
}

/** 取条目正文（纯文本）。full=true 取全文，否则只取引言。 */
export async function wikiExtract(api, title, { signal, full = false } = {}) {
  const url = `${api}?action=query&prop=extracts&explaintext=1&redirects=1`
    + (full ? '' : '&exintro=1')
    + `&titles=${encodeURIComponent(title)}&format=json&formatversion=2`
  const data = await jget(url, { signal })
  const page = data?.query?.pages?.[0]
  if (!page || page.missing) return null
  return { title: page.title, extract: String(page.extract ?? '').trim() }
}

/** 与外观最相关的段落关键词（优先保留）。 */
const LOOK_KEYS = ['外貌', '外观', '形象设计', '人设', '服装', '演出服', '制服', '私服', '发型', '发色', '瞳色', '身高', '三围']
/** 明显是剧情/关系/战绩的段落（不要占外观预算）。 */
const PLOT_KEYS = ['经历', '剧情', '历代形象', '关系', '萌战', '战绩', '评价', '语录', '轶事', '社媒']

/**
 * 从全文里挑与外观相关的片段，压到 budget 字以内。
 * 目的：给模型一份「官方对外观的描述」，而不是让它在几千字剧情里自己找。
 */
export function trimForLook(text, budget = 1800) {
  const src = String(text || '')
  if (src.length <= budget) return src
  const paras = src.split(/\n{2,}/).map((s) => s.trim()).filter(Boolean)
  const headingOf = (p) => {
    const m = p.match(/^=+\s*(.+?)\s*=+\s*$/m)
    return m ? m[1] : ''
  }
  const isPlot = (p) => {
    const h = headingOf(p)
    return h ? PLOT_KEYS.some((k) => h.includes(k)) : false
  }
  const score = (p) => {
    if (isPlot(p)) return -1
    let s = 0
    for (const k of LOOK_KEYS) if (p.includes(k)) s += 3
    const h = headingOf(p)
    if (h && LOOK_KEYS.some((k) => h.includes(k))) s += 5   // 标题命中最重
    if (/^==+/.test(p)) s -= 1                              // 纯标题块
    return s
  }
  const ranked = paras
    .map((p, i) => ({ p, i, s: i === 0 ? 100 : score(p) }))
    .filter((x) => x.s > 0)
    .sort((a, b) => b.s - a.s || a.i - b.i)

  const picked = []
  let used = 0
  for (const { p, i } of ranked) {
    if (used >= budget) break
    const add = picked.length ? 2 + p.length : p.length
    if (used + add > budget) continue
    picked.push({ p, i })
    used += add
  }
  // 按原文顺序还原，读起来连贯
  picked.sort((a, b) => a.i - b.i)
  return picked.map((x) => x.p).join('\n\n')
}

const BAD_IMG = /(icon|logo|symbol|stub|disambig|ambox|navbox|template|button|sprite|banner|placeholder|question|edit\.png|\bbg\b|背景)/i

/**
 * 取条目引用的图片，并按「与角色名相关度 + 大小」排序。
 *
 * 坑：匿名调 `titles=File:xxx&prop=imageinfo` 会被 moegirl 拒绝（action-notallowed），
 * 但 `generator=images` 是允许的 —— 所以用后者一次拿到直链与尺寸。
 */
export async function wikiImages(api, title, { limit = 30, signal } = {}) {
  const url = `${api}?action=query&generator=images&gimlimit=${limit}&titles=${encodeURIComponent(title)}`
    + `&prop=imageinfo&iiprop=url%7Csize%7Cmime&redirects=1&format=json&formatversion=2`
  const data = await jget(url, { signal })
  const pages = data?.query?.pages ?? []
  const out = []
  for (const p of pages) {
    const info = p?.imageinfo?.[0]
    if (!info?.url) continue
    if (BAD_IMG.test(p.title ?? '')) continue
    if (!/\.(png|jpe?g|webp|gif)$/i.test(info.url)) continue
    out.push({
      url: normalizeUrl(info.url),
      pageUrl: `https://zh.moegirl.org.cn/${encodeURIComponent(p.title ?? '')}`,
      title: p.title,
      width: info.width,
      height: info.height,
      mime: info.mime,
      source: 'canon',
    })
  }
  return out
}

/** 从正文里抽可能的外文名（booru 系要罗马音才搜得到）。 */
export function extractNameVariants(extract, character) {
  const text = String(extract || '')
  const out = new Set()
  // 1) 常见的「外文名」行
  for (const m of text.matchAll(/(?:外文名|英文名|日文名|罗马字)[：:\s]*([^\n]{2,60})/g)) {
    for (const w of m[1].matchAll(/[A-Za-z][A-Za-z'’\-]*(?:\s+[A-Za-z][A-Za-z'’\-]*)*/g)) out.add(w[0].trim())
  }
  // 2) 括号里的拉丁文（常见于首句：丰川祥子（とがわ さきこ / Togawa Sakiko））
  for (const m of text.matchAll(/[（(]([^()（）]{2,80})[)）]/g)) {
    const inner = m[1]
    if (!/[A-Za-z]{3}/.test(inner)) continue
    for (const w of inner.matchAll(/[A-Za-z][A-Za-z'’\-]*(?:\s+[A-Za-z][A-Za-z'’\-]*)*/g)) {
      const v = w[0].trim()
      if (v.length >= 3) out.add(v)
    }
  }
  // 3) 正文里出现的连续英文词（限制长度，避免抓到整句）
  for (const m of text.matchAll(/\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,2}\b/g)) out.add(m[0])
  const list = [...out]
    .map((s) => s.replace(/\s+/g, ' ').trim())
    .filter((s) => s.length >= 3 && s.length <= 40 && /[A-Za-z]/.test(s))
  // 过滤明显的非名字：只要有一个词是"常见非人名词"以外的实词才算候选。
  // 这样 "Anime Season" / "The Band" / "Staff A" 会被丢掉，
  // 而 "Togawa Sakiko" / "Eiga Sakiko" 保留。
  const STOP = new Set([
    'the', 'a', 'an', 'this', 'that', 'also', 'and', 'or', 'of', 'in', 'on', 'for',
    'japanese', 'english', 'chinese', 'anime', 'manga', 'novel', 'game', 'film', 'movie',
    'series', 'season', 'episode', 'chapter', 'volume', 'band', 'dream', 'staff',
    'voice', 'actor', 'actress', 'character', 'cast', 'list', 'main', 'other',
  ])
  const isNamey = (s) => s.split(/\s+/).some((w) => !STOP.has(w.toLowerCase().replace(/[^a-z]/g, '')))
  const filtered = list.filter(isNamey)
  // 同名（中文名本身）放最前
  const seen = new Set()
  const uniq = []
  for (const s of [character, ...filtered]) {
    const k = s.toLowerCase()
    if (seen.has(k)) continue
    seen.add(k)
    uniq.push(s)
  }
  return uniq
}

/**
 * 取官方基准：文字 + 官方图候选。
 * @returns {Promise<{facts:Array, name_variants:string[], images:Array, sources:Array}>}
 */
export async function canonLookup({ character, signal, maxImages = 8 }) {
  const name = String(character || '').trim()
  if (!name) throw Object.assign(new Error('character required'), { code: 'INVALID_PARAMS' })

  const facts = []
  const rawImages = []
  const stats = []

  for (const src of CANON_SOURCES) {
    let hit = null
    try {
      hit = await wikiExtract(src.api, name, { signal, full: true })
    } catch (error) {
      stats.push({ id: src.id, label: src.label, ok: false, error: error?.message ?? String(error) })
      continue
    }
    if (!hit) {
      stats.push({ id: src.id, label: src.label, ok: false, error: '条目不存在' })
      continue
    }
    const look = trimForLook(hit.extract, 1800)
    facts.push({ source: src.id, source_label: src.label, title: hit.title, extract: look, full_chars: hit.extract.length })
    stats.push({ id: src.id, label: src.label, ok: true, title: hit.title, chars: hit.extract.length })

    try {
      const imgs = await wikiImages(src.api, hit.title, { signal })
      rawImages.push(...imgs)
    } catch { /* 图失败不影响文字 */ }
    if (facts.length >= 1 && rawImages.length >= 3) break
  }

  const primary = facts[0]
  const nameVariants = extractNameVariants((primary?.extract ?? '') + '\n' + rawImages.map((i) => i.title).join('\n'), name)

  // 按「文件名命中角色名」优先，再按面积排序：这样能捞出官方立绘，
  // 而不是乐队 logo / 别人的图。
  const tokens = nameVariants.map((v) => v.toLowerCase()).filter((v) => /[a-z]{3}/.test(v))
  const scored = rawImages.map((img) => {
    const t = String(img.title ?? '').toLowerCase()
    const hits = tokens.filter((tok) => t.includes(tok)).length
    return { ...img, _score: hits * 1e9 + (img.width ?? 0) * (img.height ?? 0) }
  }).sort((a, b) => b._score - a._score)
  const images = scored.slice(0, maxImages).map(({ _score, ...rest }) => rest)

  return {
    facts,
    name_variants: nameVariants,
    images,
    image_pool: rawImages.length,
    sources: stats,
    hint: images.length
      ? '这是官方/百科条目自带的图，作为**校验基准**用：先看它确认发色/瞳色/服装，再去判断后面大量搜到的图'
      : '没拿到官方图，只能靠文字描述做基准',
  }
}
