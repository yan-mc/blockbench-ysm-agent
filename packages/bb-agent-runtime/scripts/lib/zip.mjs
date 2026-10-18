// 零依赖 ZIP 打包（deflate），用于发布包；仅支持常规文件（无目录项、无 zip64）
import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'

const CRC_TABLE = (() => {
  const table = new Uint32Array(256)
  for (let n = 0; n < 256; n++) {
    let c = n
    for (let k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1)
    table[n] = c >>> 0
  }
  return table
})()

function crc32(buf) {
  let c = 0xffffffff
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

function dosTime(date = new Date()) {
  const time = ((date.getHours() & 0x1f) << 11) | ((date.getMinutes() & 0x3f) << 5) | (Math.floor(date.getSeconds() / 2) & 0x1f)
  const day = (((date.getFullYear() - 1980) & 0x7f) << 9) | (((date.getMonth() + 1) & 0x0f) << 5) | (date.getDate() & 0x1f)
  return { time, day }
}

function walk(root, rel = '') {
  const out = []
  for (const entry of fs.readdirSync(path.join(root, rel))) {
    const relPath = rel ? `${rel}/${entry}` : entry
    const stat = fs.statSync(path.join(root, relPath))
    if (stat.isDirectory()) out.push(...walk(root, relPath))
    else out.push(relPath)
  }
  return out
}

/** 把目录打包成 zip；返回 { path, files, bytes } */
export function createZipFromDir(rootDir, zipPath) {
  const files = walk(rootDir).sort()
  const local = []
  const central = []
  let offset = 0
  for (const rel of files) {
    const abs = path.join(rootDir, ...rel.split('/'))
    const data = fs.readFileSync(abs)
    const name = Buffer.from(rel, 'utf8')
    const compressed = zlib.deflateRawSync(data, { level: 6 })
    const crc = crc32(data)
    const dt = dosTime(fs.statSync(abs).mtime)
    const lh = Buffer.alloc(30)
    lh.writeUInt32LE(0x04034b50, 0)
    lh.writeUInt16LE(20, 4)
    lh.writeUInt16LE(0x0800, 6)
    lh.writeUInt16LE(8, 8)
    lh.writeUInt16LE(dt.time, 10)
    lh.writeUInt16LE(dt.day, 12)
    lh.writeUInt32LE(crc, 14)
    lh.writeUInt32LE(compressed.length, 18)
    lh.writeUInt32LE(data.length, 22)
    lh.writeUInt16LE(name.length, 26)
    local.push(lh, name, compressed)
    const ch = Buffer.alloc(46)
    ch.writeUInt32LE(0x02014b50, 0)
    ch.writeUInt16LE(20, 4)
    ch.writeUInt16LE(20, 6)
    ch.writeUInt16LE(0x0800, 8)
    ch.writeUInt16LE(8, 10)
    ch.writeUInt16LE(dt.time, 12)
    ch.writeUInt16LE(dt.day, 14)
    ch.writeUInt32LE(crc, 16)
    ch.writeUInt32LE(compressed.length, 20)
    ch.writeUInt32LE(data.length, 24)
    ch.writeUInt16LE(name.length, 28)
    ch.writeUInt32LE(offset, 42)
    central.push(ch, name)
    offset += lh.length + name.length + compressed.length
  }
  const centralSize = central.reduce((sum, b) => sum + b.length, 0)
  const end = Buffer.alloc(22)
  end.writeUInt32LE(0x06054b50, 0)
  end.writeUInt16LE(files.length, 8)
  end.writeUInt16LE(files.length, 10)
  end.writeUInt32LE(centralSize, 12)
  end.writeUInt32LE(offset, 16)
  const buf = Buffer.concat([...local, ...central, end])
  fs.mkdirSync(path.dirname(zipPath), { recursive: true })
  fs.writeFileSync(zipPath, buf)
  return { path: zipPath, files: files.length, bytes: buf.length }
}
