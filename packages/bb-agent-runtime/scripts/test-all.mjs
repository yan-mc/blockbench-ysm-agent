// 本地全量回归：assemble -> M0 -> e2e(WS) -> e2e(HTTP+SSE) -> hosttest -> 动画语义 diff
// 用法：node packages/bb-agent-runtime/scripts/test-all.mjs [--quick]
// --quick 跳过 M0 / 两条 e2e，只跑 hosttest + anim diff（改代码时快速回归）
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..')
const node = process.execPath
const quick = process.argv.includes('--quick')
const results = []

function run(name, args, opts = {}) {
  const started = Date.now()
  console.log(`\n[test-all] === ${name} ===`)
  const result = spawnSync(node, args, { cwd: REPO_ROOT, stdio: 'inherit', env: { ...process.env, ...(opts.env ?? {}) }, timeout: opts.timeout ?? 900000 })
  const ok = result.status === 0
  results.push({ name, ok, ms: Date.now() - started, status: result.status, signal: result.signal ?? null })
  if (!ok) console.error(`[test-all] ✗ ${name} (status=${result.status})`)
  return ok
}

// 1) 组装 BAE（插件运行时会占用 dist，测试脚本会自己 kill electron；运行前建议先禁用 dsh 插件）
if (!quick) {
  if (!run('assemble', ['packages/bb-agent-runtime/scripts/assemble.mjs'])) process.exit(1)
  if (!run('M0', ['packages/bb-agent-runtime/scripts/m0.mjs'])) process.exit(1)
  if (!run('e2e WS', ['packages/bb-agent-runtime/scripts/e2e.mjs'])) process.exit(1)
  if (!run('e2e HTTP+SSE', ['packages/bb-agent-runtime/scripts/e2e.mjs', '--transport=http'])) process.exit(1)
}

// 2) Host 插件全工具集成冒烟
if (!run('hosttest', ['packages/dsh-blockbench-agent/test/host-smoke.mjs'])) process.exit(1)

// 3) 动画语义 diff：hosttest 产物 pack vs 模板；缺失时退回 workspace/default
const template = path.join(REPO_ROOT, 'dist', 'bb-agent-app', 'templates', 'ysm_default')
const candidates = [
  path.join(REPO_ROOT, 'workspace', '_hosttest', 'workspaces', 'demo', 'pack'),
  path.join(REPO_ROOT, 'projects', 'deepseek-fish', 'pack'),
  path.join(REPO_ROOT, 'workspace', 'default', 'pack'),
]
const pack = candidates.find((p) => fs.existsSync(path.join(p, 'animations')))
if (!pack) {
  results.push({ name: 'animation semantic diff', ok: false, reason: 'no pack found' })
  console.error('[test-all] ✗ animation semantic diff: no pack found')
} else if (!run('animation semantic diff', ['packages/bb-agent-runtime/scripts/verify-animation-diff.mjs', '--a', template, '--b', pack, '--allow-added'])) {
  console.error('[test-all] ✗ animation semantic diff failed; see workspace/_logs/animation-diff.json')
}

const failed = results.filter((r) => !r.ok)
console.log('\n[test-all] summary:')
for (const r of results) console.log(`  ${r.ok ? 'PASS' : 'FAIL'}  ${r.name}  ${r.ms}ms`)
console.log(`[test-all] ${failed.length ? 'FAILED' : 'PASSED'} (${results.length - failed.length}/${results.length})`)
process.exit(failed.length ? 1 : 0)
