// 动画语义 diff：比较两个 YSM 包的 *.animation.json（按动画名/循环/时长/骨骼/关键帧），
// 用于验证"保存后动画语义不变"而不是只看字节。
// 用法：node packages/bb-agent-runtime/scripts/verify-animation-diff.mjs --a <packA> --b <packB>
import fs from 'node:fs'
import path from 'node:path'

const arg = (name, fallback) => {
  const idx = process.argv.indexOf(`--${name}`)
  return idx >= 0 ? process.argv[idx + 1] : fallback
}
const aDir = path.resolve(arg('a', 'dist/bb-agent-app/templates/ysm_default'))
const bDir = path.resolve(arg('b', 'workspace/default/live_gold3'))

function collectAnimations(root) {
  const out = new Map()
  const walk = (dir) => {
    if (!fs.existsSync(dir)) return
    for (const name of fs.readdirSync(dir)) {
      const abs = path.join(dir, name)
      if (fs.statSync(abs).isDirectory()) { walk(abs); continue }
      if (!name.endsWith('.animation.json')) continue
      let json
      try { json = JSON.parse(fs.readFileSync(abs, 'utf8')) } catch (error) { out.set(`${name}#parse-error`, { file: name, error: String(error) }); continue }
      for (const [animName, anim] of Object.entries(json.animations ?? {})) {
        const bones = {}
        for (const [boneName, bone] of Object.entries(anim.bones ?? {})) {
          const channels = {}
          for (const [channel, value] of Object.entries(bone)) {
            if (Array.isArray(value)) {
              channels[channel] = value.map((kf) => JSON.stringify({
                t: kf.time ?? 0,
                pre: kf.pre ?? null,
                post: kf.post ?? null,
                lerp: kf.lerp_mode ?? null,
              }))
            }
          }
          bones[boneName] = channels
        }
        out.set(animName, {
          file: name, name: animName, loop: anim.loop ?? false,
          length: anim.animation_length ?? null, bones,
        })
      }
    }
  }
  walk(root)
  return out
}

const a = collectAnimations(aDir)
const b = collectAnimations(bDir)
const added = [...b.keys()].filter((k) => !a.has(k))
const removed = [...a.keys()].filter((k) => !b.has(k))
const changed = []
for (const [name, av] of a) {
  const bv = b.get(name)
  if (!bv) continue
  const same = av.loop === bv.loop && av.length === bv.length &&
    JSON.stringify(av.bones) === JSON.stringify(bv.bones)
  if (!same) changed.push({ name, loop: [av.loop, bv.loop], length: [av.length, bv.length] })
}

const report = {
  a: aDir, b: bDir,
  animations: { a: a.size, b: b.size },
  added, removed, changed,
  equal: added.length === 0 && removed.length === 0 && changed.length === 0,
}
const outPath = path.join('workspace', '_logs', 'animation-diff.json')
fs.mkdirSync(path.dirname(outPath), { recursive: true })
fs.writeFileSync(outPath, JSON.stringify(report, null, 2) + '\n')
console.log(JSON.stringify(report, null, 2))
console.log(`[anim-diff] ${report.equal ? 'EQUAL' : 'DIFFERENT'} → ${outPath}`)
process.exit(report.equal ? 0 : 1)
