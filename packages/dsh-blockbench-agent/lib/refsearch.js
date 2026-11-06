/**
 * 参考图多源搜索。
 *
 * 设计约束（见 docs/11）：
 *   1. 纯 Node，无第三方依赖 —— 插件要能直接分发给别人。
 *   2. 每个源一个 adapter，加源不改核心。
 *   3. **失败不抛**：单源失败只记录状态，其它源照常返回（站点会封、会改版）。
 *   4. 不内置任何密钥；只用公开接口。
 *
 * 已实测可用：
 *   - bing     https://www.bing.com/images/async        一次 ~34 条，最稳
 *   - so360    https://image.so.com/j                   一次 ~30 条，JSON
 *   - moegirl  https://commons.moegirl.org.cn/api.php   MediaWiki，官方图多
 *
 * 实测不可用（保留探针，失败自动跳过）：
 *   - baidu / sogou / yandex：反爬页
 *   - duckduckgo：vqd 流程已变
 *   - danbooru / konachan：403/503（国内网络）
 */

const DEFAULT_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36';

/** 查询词模板：中文 / 日文 / 英文三路，覆盖「设定集」这类高价值词。 */
export const QUERY_TEMPLATES = [
  { kind: 'base', suffix: '' },
  { kind: 'sheet', suffix: ' 设定集' },
  { kind: 'sheet', suffix: ' 三视图' },
  { kind: 'fullbody', suffix: ' 全身立绘' },
  { kind: 'back', suffix: ' 背面' },
  { kind: 'sheet', suffix: ' 設定資料集', lang: 'ja' },
  { kind: 'fullbody', suffix: ' 立ち絵', lang: 'ja' },
  { kind: 'sheet', suffix: ' character sheet', lang: 'en' },
  { kind: 'fullbody', suffix: ' full body', lang: 'en' },
  { kind: 'back', suffix: ' back view', lang: 'en' },
];

/** 按角色名生成查询列表。默认只要 5 条：base+sheet×2+fullbody+back，兼顾覆盖面与耗时。 */
export function buildQueries(character, opts = {}) {
  const name = String(character || '').trim();
  if (!name) return [];
  const extra = Array.isArray(opts.extraQueries) ? opts.extraQueries.filter(Boolean) : [];
  if (extra.length) {
    return [...extra.map((q) => ({ q: String(q), kind: 'custom' }))];
  }
  const max = Math.max(1, Math.min(QUERY_TEMPLATES.length, opts.maxQueries ?? 6));
  // 优先取中文高价值词，再按需补日/英
  const order = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];
  return order.slice(0, max).map((i) => {
    const t = QUERY_TEMPLATES[i];
    return { q: `${name}${t.suffix}`, kind: t.kind, lang: t.lang ?? 'zh' };
  });
}

function decodeEntities(s) {
  return String(s || '')
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&#(\d+);/g, (_, d) => String.fromCharCode(Number(d)))
    .replace(/\\\//g, '/');
}

async function httpGet(url, { headers = {}, timeoutMs = 15000, signal } = {}) {
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), timeoutMs);
  const onAbort = () => ac.abort();
  if (signal) signal.addEventListener('abort', onAbort, { once: true });
  try {
    const res = await fetch(url, {
      headers: { 'User-Agent': DEFAULT_UA, 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8', ...headers },
      signal: ac.signal,
      redirect: 'follow',
    });
    const text = await res.text();
    return { ok: res.ok, status: res.status, text, headers: res.headers };
  } finally {
    clearTimeout(timer)
    if (signal) signal.removeEventListener('abort', onAbort)
  }
}

// ---------------------------------------------------------------- adapters

/** Bing 图片（异步接口，一次约 34 条）。 */
const bing = {
  id: 'bing',
  label: 'Bing 图片',
  async search(query, { count = 35, signal } = {}) {
    const url = `https://www.bing.com/images/async?q=${encodeURIComponent(query)}`
      + `&first=1&count=${count}&mkt=zh-CN&adlt=off`
    const r = await httpGet(url, {
      headers: { Accept: 'text/javascript,text/html,*/*', Referer: 'https://www.bing.com/images/search' },
      signal,
    })
    if (!r.ok) throw new Error(`bing ${r.status}`)
    const html = r.text
    const out = []
    // Bing 把结果塞在 m="{...&quot;murl&quot;:&quot;...}" 里
    const re = /murl&quot;:&quot;(https?:\/\/[^&"]+?)&quot;/g
    let m
    const pages = []
    const pre = /purl&quot;:&quot;(https?:\/\/[^&"]+?)&quot;/g
    let p
    while ((p = pre.exec(html)) && pages.length < 200) pages.push(decodeEntities(p[1]))
    while ((m = re.exec(html))) out.push({ url: decodeEntities(m[1]) })
    pages.forEach((pu, i) => { if (out[i]) out[i].pageUrl = pu })
    return out
  },
}

/** 360 图片（JSON 接口）。 */
const so360 = {
  id: 'so360',
  label: '360 图片',
  async search(query, { count = 30, signal } = {}) {
    const url = `https://image.so.com/j?q=${encodeURIComponent(query)}&pn=0&rn=${count}&src=srp`
    const r = await httpGet(url, {
      headers: { Accept: 'application/json,*/*', Referer: `https://image.so.com/i?q=${encodeURIComponent(query)}` },
      signal,
    })
    if (!r.ok) throw new Error(`so360 ${r.status}`)
    let data
    try { data = JSON.parse(r.text) } catch { throw new Error('so360 json parse failed') }
    return (data.list || [])
      .map((it) => ({
        url: decodeEntities(it.img || it.thumb || ''),
        pageUrl: it.link ? decodeEntities(it.link) : undefined,
        title: it.title,
        site: it.site,
        width: Number(it.width) || undefined,
        height: Number(it.height) || undefined,
      }))
      .filter((x) => /^https?:\/\//.test(x.url))
  },
}

/** MediaWiki 图库（萌娘百科 Commons 等），按分类或全文搜文件。 */
function mediaWikiAdapter({ id, label, api, categoryPrefix = '' }) {
  return {
    id,
    label,
    async search(query, { count = 30, signal } = {}) {
      const props = 'prop=imageinfo&iiprop=url|size|mime&format=json&formatversion=2'
      const attempts = []
      if (categoryPrefix) {
        attempts.push(`${api}?action=query&generator=categorymembers&gcmtitle=${encodeURIComponent(categoryPrefix + query)}`
          + `&gcmtype=file&gcmlimit=${count}&${props}`)
      }
      attempts.push(`${api}?action=query&generator=search&gsrsearch=${encodeURIComponent(query)}`
        + `&gsrnamespace=6&gsrlimit=${count}&${props}`)
      let lastErr = null
      for (const url of attempts) {
        try {
          const r = await httpGet(url, { headers: { Accept: 'application/json' }, signal })
          if (!r.ok) { lastErr = new Error(`${id} ${r.status}`); continue }
          const data = JSON.parse(r.text)
          const pages = data?.query?.pages
          if (!pages || typeof pages !== 'object') continue
          const list = Object.values(pages)
            .map((pg) => {
              const ii = Array.isArray(pg.imageinfo) ? pg.imageinfo[0] : null
              if (!ii?.url) return null
              return {
                url: ii.url,
                pageUrl: ii.descriptionurl,
                title: pg.title,
                width: ii.width,
                height: ii.height,
                mime: ii.mime,
              }
            })
            .filter(Boolean)
          if (list.length) return list
        } catch (error) {
          lastErr = error
        }
      }
      if (lastErr) throw lastErr
      return []
    },
  }
}

const moegirl = mediaWikiAdapter({
  id: 'moegirl',
  label: '萌娘百科图库',
  api: 'https://commons.moegirl.org.cn/api.php',
  categoryPrefix: 'Category:',
})

/** 已注册源。加源只需往这里 push 一个 {id,label,search}。 */
export const SOURCES = [bing, so360, moegirl]

export function sourceById(id) {
  return SOURCES.find((s) => s.id === id) ?? null
}

/** 图片 URL 粗筛：明显不是图片的站内资源直接丢。 */
const BAD_URL = /(\.svg($|\?)|\.gif($|\?)|sprite|logo|icon|avatar|favicon|\/rp\/|blank\.)/i

/**
 * 归一化 URL：去掉 HTML 残留引号，把非 ASCII / 空格百分号编码。
 * Node fetch 对原始 CJK 字符会抛 "Cannot convert argument to a ByteString"。
 */
export function normalizeUrl(u) {
  let s = String(u || '').trim()
  if (!s) return ''
  s = s.replace(/["'<>]/g, '')
  return s.replace(/[^\x21-\x7E]/g, (ch) => encodeURIComponent(ch))
}

export function looksLikeImageUrl(url) {
  if (!/^https?:\/\//i.test(String(url || ''))) return false
  if (BAD_URL.test(url)) return false
  return true
}

/**
 * 多源并发搜索。
 *
 * @param {object} p
 * @param {string} p.character
 * @param {string[]} [p.queries]     自定义查询，省略则用模板
 * @param {string[]} [p.sources]     源 id 白名单，省略用全部
 * @param {number} [p.perSource=30]
 * @param {number} [p.timeoutMs=20000]
 * @param {AbortSignal} [p.signal]
 * @param {(msg:string)=>void} [p.onLog]
 * @returns {Promise<{candidates:object[], sources:object[]}>}
 */
export async function searchRefs(p = {}) {
  const queries = Array.isArray(p.queries) && p.queries.length
    ? p.queries.map((q) => ({ q: String(q), kind: 'custom' }))
    : buildQueries(p.character, { extraQueries: p.extraQueries, maxQueries: p.maxQueries })
  if (!queries.length) throw Object.assign(new Error('character or queries required'), { code: 'INVALID_PARAMS' })

  const wanted = new Set(Array.isArray(p.sources) && p.sources.length ? p.sources : SOURCES.map((s) => s.id))
  const active = SOURCES.filter((s) => wanted.has(s.id))
  const perSource = Math.max(5, Math.min(50, p.perSource ?? 30))
  const timeoutMs = p.timeoutMs ?? 20000

  const seen = new Set()
  const candidates = []
  const sourceStats = active.map((s) => ({ id: s.id, label: s.label, ok: false, count: 0, errors: [] }))

  const tasks = []
  active.forEach((src, si) => {
    queries.forEach((q) => {
      tasks.push((async () => {
        const stat = sourceStats[si]
        try {
          const list = await src.search(q.q, { count: perSource, signal: p.signal, timeoutMs })
          let added = 0
          for (const it of list) {
            const url = normalizeUrl(it.url)
            if (!looksLikeImageUrl(url)) continue
            const key = url.replace(/[?#].*$/, '')
            if (seen.has(key)) continue
            seen.add(key)
            candidates.push({
              url,
              pageUrl: it.pageUrl ? normalizeUrl(it.pageUrl) : undefined,
              title: it.title,
              site: it.site,
              width: it.width,
              height: it.height,
              mime: it.mime,
              source: src.id,
              query: q.q,
              kind: q.kind,
            })
            added += 1
          }
          stat.ok = true
          stat.count += added
          p.onLog?.(`[ref] ${src.id} «${q.q}» +${added}`)
        } catch (error) {
          if (p.signal?.aborted) return
          stat.errors.push(`${q.q}: ${error?.message ?? error}`)
          p.onLog?.(`[ref] ${src.id} «${q.q}» 失败: ${error?.message ?? error}`)
        }
      })())
    })
  })

  await Promise.allSettled(tasks)
  // 去掉只有错误的源状态
  const sources = sourceStats.map((s) => ({
    id: s.id,
    label: s.label,
    ok: s.ok,
    count: s.count,
    error: s.ok ? null : (s.errors[0] ?? 'no result'),
  }))
  return { candidates, sources, queries: queries.map((q) => q.q) }
}

/** 按「信息密度」先验排序：设定集/立绘 > 一般图；有明确尺寸且偏竖图加分。 */
export function priorScore(c) {
  let s = 0
  const kind = c.kind || 'base'
  if (kind === 'sheet') s += 40
  else if (kind === 'fullbody') s += 25
  else if (kind === 'back') s += 20
  if (c.width && c.height) {
    const ar = c.height / c.width
    if (ar >= 1.2) s += 12            // 全身立绘多为竖图
    if (c.width >= 800 && c.height >= 800) s += 8
    if (c.width < 200 || c.height < 200) s -= 20
  }
  if (/moegirl|bang-dream|fandom|wiki/i.test(c.url)) s += 15
  if (/hdslb|bilibili|acfun/i.test(c.url)) s += 5
  if (/avatar|icon|head|logo/i.test(c.url)) s -= 25
  return s
}

export function sortCandidates(list) {
  return [...list].sort((a, b) => priorScore(b) - priorScore(a))
}
