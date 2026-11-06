/**
 * 参考图下载器：并发抓取 + 格式校验 + 精确去重 + 落盘。
 *
 * 不做感知去重（需要解码图像）；感知去重交给桥接端 `ref.sheet` 一并算 dHash，
 * 这里只负责拿到「像样的图片字节」。
 */

import { createHash } from 'node:crypto'

const DEFAULT_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36'

const MAX_BYTES = 12 * 1024 * 1024   // 单图上限
const MIN_BYTES = 6 * 1024           // 小于此基本是占位图/图标

/** 按魔数判断真实图片类型，不信任 content-type 与扩展名。 */
export function sniffImage(buf) {
  if (!buf || buf.length < 12) return null
  if (buf[0] === 0x89 && buf[1] === 0x50 && buf[2] === 0x4e && buf[3] === 0x47) return { ext: 'png', mime: 'image/png' }
  if (buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff) return { ext: 'jpg', mime: 'image/jpeg' }
  if (buf[0] === 0x52 && buf[1] === 0x49 && buf[2] === 0x46 && buf[3] === 0x46
    && buf[8] === 0x57 && buf[9] === 0x45 && buf[10] === 0x42 && buf[11] === 0x50) return { ext: 'webp', mime: 'image/webp' }
  if (buf[0] === 0x47 && buf[1] === 0x49 && buf[2] === 0x46) return { ext: 'gif', mime: 'image/gif' }
  if (buf[0] === 0x42 && buf[1] === 0x4d) return { ext: 'bmp', mime: 'image/bmp' }
  return null
}

/** 读 PNG/JPEG/WebP 的宽高（够用就行，不引入解码库）。 */
export function readSize(buf, kind) {
  try {
    if (kind === 'png') {
      // IHDR：8 字节签名 + 4 len + 4 type，然后 w/h 各 4 字节大端
      if (buf.length < 24) return null
      return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) }
    }
    if (kind === 'jpg') {
      let i = 2
      while (i + 9 < buf.length) {
        if (buf[i] !== 0xff) { i += 1; continue }
        const marker = buf[i + 1]
        // SOF0..SOF15（排除 DHT/JPG/DAC）
        if (marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc) {
          return { height: buf.readUInt16BE(i + 5), width: buf.readUInt16BE(i + 7) }
        }
        const len = buf.readUInt16BE(i + 2)
        if (len < 2) break
        i += 2 + len
      }
      return null
    }
    if (kind === 'webp') {
      const fourcc = buf.toString('ascii', 12, 16)
      if (fourcc === 'VP8X') {
        const w = 1 + (((buf[24] | (buf[25] << 8) | (buf[26] << 16)) & 0xffffff))
        const h = 1 + (((buf[27] | (buf[28] << 8) | (buf[29] << 16)) & 0xffffff))
        return { width: w, height: h }
      }
      if (fourcc === 'VP8 ') {
        return { width: buf.readUInt16LE(26) & 0x3fff, height: buf.readUInt16LE(28) & 0x3fff }
      }
      if (fourcc === 'VP8L' && buf.length >= 25) {
        const b = buf[21] | (buf[22] << 8) | (buf[23] << 16) | (buf[24] << 24)
        return { width: (b & 0x3fff) + 1, height: ((b >> 14) & 0x3fff) + 1 }
      }
    }
  } catch { /* ignore */ }
  return null
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)) }

/**
 * Node 的 fetch 会把 URL 当 ByteString 校验，原始 CJK 字符直接抛错
 * （实测百度图床 `?x-bce-process=...` 这类查询串里带中文就会炸）。
 * 这里只对非 ASCII 与空格做百分号编码，已有的 %XX 保持不动。
 */
export function safeUrl(u) {
  const s = String(u || '')
  if (!s) return s
  return s.replace(/[^\x21-\x7E]/g, (ch) => encodeURIComponent(ch))
}

function originOf(u) {
  try { return new URL(safeUrl(u)).origin + '/' } catch { return undefined }
}

/** 某些 CDN 只认自家站点 Referer（实测 bilibili 的 hdslb 不带就 403）。 */
const REFERER_HINTS = [
  [/hdslb\.com/i, 'https://www.bilibili.com/'],
  [/bcebos\.com|bdstatic\.com|baidu\.com/i, 'https://image.baidu.com/'],
  [/hdslb|bilibili/i, 'https://www.bilibili.com/'],
  [/duitang\.com|dtstatic\.com/i, 'https://www.duitang.com/'],
  [/zhimg\.com/i, 'https://www.zhihu.com/'],
  [/moegirl\.org\.cn/i, 'https://zh.moegirl.org.cn/'],
]

function refererFor(url, explicit) {
  for (const [re, ref] of REFERER_HINTS) if (re.test(url)) return ref
  return explicit || originOf(url)
}

async function fetchOne(item, { timeoutMs, referer, signal }) {
  const ac = new AbortController()
  const timer = setTimeout(() => ac.abort(), timeoutMs)
  const onAbort = () => ac.abort()
  if (signal) signal.addEventListener('abort', onAbort, { once: true })
  const url = safeUrl(item.url)
  const ref = refererFor(url, referer)
  try {
    const res = await fetch(url, {
      headers: {
        'User-Agent': DEFAULT_UA,
        Accept: 'image/avif,image/webp,image/png,image/jpeg,*/*',
        ...(ref ? { Referer: ref } : {}),
      },
      signal: ac.signal,
      redirect: 'follow',
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const len = Number(res.headers.get('content-length') || 0)
    if (len > MAX_BYTES) throw new Error(`too large (${(len / 1048576).toFixed(1)}MB)`)
    const buf = Buffer.from(await res.arrayBuffer())
    if (buf.length < MIN_BYTES) throw new Error(`too small (${buf.length}B)`)
    if (buf.length > MAX_BYTES) throw new Error('too large')
    const kind = sniffImage(buf)
    if (!kind) throw new Error('not an image')
    return { buf, kind }
  } finally {
    clearTimeout(timer)
    if (signal) signal.removeEventListener('abort', onAbort)
  }
}

/**
 * 并发下载一批候选图。
 *
 * @param {object} p
 * @param {object[]} p.candidates   {url, pageUrl?, source?, kind?, ...}
 * @param {string} p.outDir         绝对目录
 * @param {import('node:fs/promises')} p.fsp
 * @param {(p:string)=>void} [p.ensureDir]
 * @param {number} [p.maxImages=24]
 * @param {number} [p.concurrency=6]
 * @param {number} [p.timeoutMs=20000]
 * @param {number} [p.maxSide=4096]  超过则跳过（大图对建模参考没意义，还占内存）
 * @param {AbortSignal} [p.signal]
 */
export async function collectRefs(p) {
  const { fsp, outDir, candidates = [] } = p
  const maxImages = Math.max(1, Math.min(80, p.maxImages ?? 24))
  const concurrency = Math.max(1, Math.min(12, p.concurrency ?? 6))
  const timeoutMs = p.timeoutMs ?? 20000
  const maxSide = p.maxSide ?? 4096

  await fsp.mkdir(outDir, { recursive: true })

  const picked = candidates.slice(0, Math.max(maxImages * 3, maxImages))
  const results = []
  const seenHash = new Set()
  let idx = 0
  let stop = false

  async function worker() {
    while (!stop) {
      const my = idx++
      if (my >= picked.length) return
      const item = picked[my]
      try {
        const { buf, kind } = await fetchOne(item, { timeoutMs, referer: item.pageUrl, signal: p.signal })
        const size = readSize(buf, kind.ext)
        if (size && maxSide && Math.max(size.width, size.height) > maxSide) {
          throw new Error(`resolution too large (${size.width}x${size.height})`)
        }
        const sha = createHash('sha256').update(buf).digest('hex')
        if (seenHash.has(sha)) continue
        seenHash.add(sha)
        const seq = results.length
        const name = `ref_${String(seq).padStart(3, '0')}.${kind.ext}`
        const file = `${outDir}/${name}`
        await fsp.writeFile(file, buf)
        results.push({
          file,
          name,
          bytes: buf.length,
          sha256: sha,
          mime: kind.mime,
          width: size?.width ?? item.width ?? null,
          height: size?.height ?? item.height ?? null,
          url: item.url,
          pageUrl: item.pageUrl ?? null,
          source: item.source ?? null,
          query: item.query ?? null,
          kind: item.kind ?? null,
          title: item.title ?? null,
        })
        if (results.length >= maxImages) { stop = true; return }
      } catch (error) {
        if (p.signal?.aborted) return
        p.onLog?.(`[ref] 跳过 ${String(item.url).slice(0, 90)} — ${error?.message ?? error}`)
      }
    }
  }

  await Promise.all(Array.from({ length: concurrency }, worker))
  // 并发下 results 可能比上限多出 (concurrency-1) 个，这里截断保证确定性
  if (results.length > maxImages) results.length = maxImages
  // 保持下载顺序稳定
  results.sort((a, b) => a.name.localeCompare(b.name))
  return { images: results, attempted: picked.length }
}
