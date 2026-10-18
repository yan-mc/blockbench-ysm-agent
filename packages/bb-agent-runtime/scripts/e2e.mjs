// BAE ↔ dsh BridgeServer 端到端测试（不依赖 dsh 安装）
// 覆盖：WS 握手鉴权 → 创建项目 → 场景读取 → 模型 patch → 贴图创建/绘制 → 多机位渲染 → GUI show/hide → 保存 → 关闭
// 用法：node packages/bb-agent-runtime/scripts/e2e.mjs [--safe-mode] [--keep]

import fs from 'node:fs'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { randomBytes, createHash } from 'node:crypto'
import { createWsServer } from '../../dsh-blockbench-agent/lib/ws-server.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PACKAGE_ROOT = path.resolve(__dirname, '..')
const REPO_ROOT = path.resolve(PACKAGE_ROOT, '..', '..')
const has = (flag) => process.argv.includes(`--${flag}`)
const safeMode = has('safe-mode')
const keep = has('keep')
const transport = process.argv.includes('--transport=http') ? 'http' : 'ws'

const appDir = path.join(REPO_ROOT, 'dist', 'bb-agent-app')
const workspace = path.join(REPO_ROOT, 'workspace', safeMode ? '_e2e-safe' : '_e2e')
const electronExe = path.join(REPO_ROOT, 'vendor', 'blockbench', 'node_modules', 'electron', 'dist', process.platform === 'win32' ? 'electron.exe' : 'electron')
const outDir = path.join(workspace, 'artifacts', 'e2e')
fs.rmSync(workspace, { recursive: true, force: true })
fs.mkdirSync(outDir, { recursive: true })
fs.mkdirSync(path.join(workspace, 'logs'), { recursive: true })

const results = { ok: false, steps: [], started_at: new Date().toISOString() }
const step = (name, data) => { results.steps.push({ name, at: new Date().toISOString(), ...data }); console.log(`[e2e] ✓ ${name}`, data ? JSON.stringify(data).slice(0, 300) : '') }
const fail = (name, error) => { results.ok = false; results.steps.push({ name, error: String(error?.stack ?? error) }); console.error(`[e2e] ✗ ${name}`, error); }

function pngSize(filePath) {
  const buf = fs.readFileSync(filePath)
  if (buf.length < 24 || buf.toString('ascii', 1, 4) !== 'PNG') throw new Error(`not png: ${filePath}`)
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20), bytes: buf.length }
}
function hashFile(filePath) {
  return createHash('sha256').update(fs.readFileSync(filePath)).digest('hex')
}

const token = randomBytes(32).toString('base64url')
let connectedResolve
const connectedPromise = new Promise((resolve) => { connectedResolve = resolve })
const server = createWsServer({
  token,
  logger: { info() {}, warn: (...a) => console.warn('[ws]', ...a) },
  defaultTimeoutMs: 120000,
  methods: {
    'system.hello': (params) => ({
      protocol: 'bb-agent/1',
      transport: 'ws',
      server: { name: 'e2e-dsh-bridge', version: '0.1.0', blockbench: '5.2.2' },
      capabilities: { render: { offscreen: true, transparent: true }, gui: { show: true } },
      session: { project_id: null, revision: 0, state: 'booting' },
    }),
  },
  onConnection: () => connectedResolve(true),
  onNotification: (method, params) => { if (method === 'event.heartbeat') results.lastHeartbeat = params },
})
const { port } = await server.listen(0)
const rpcUrl = `ws://127.0.0.1:${port}/bb-agent/v1`
console.log(`[e2e] rpc=${rpcUrl}`)

const childEnv = { ...process.env }
delete childEnv.ELECTRON_RUN_AS_NODE
const args = [
  appDir,
  `--workspace=${workspace}`,
  `--plugin=${path.join(appDir, 'agent', 'bb-agent-bridge.js')}`,
  `--user-data=${path.join(workspace, '.bb', 'userdata')}`,
  `--rpc-url=${rpcUrl}`,
  `--token=${token}`,
  `--transport=${transport}`,
]
if (safeMode) args.push('--safe-mode')
const child = spawn(electronExe, args, { cwd: appDir, windowsHide: true, env: childEnv })
const logPath = path.join(workspace, 'logs', 'e2e-electron.log')
const logStream = fs.createWriteStream(logPath, { flags: 'a' })
child.stdout.on('data', (d) => { process.stdout.write(d); logStream.write(d) })
child.stderr.on('data', (d) => { process.stderr.write(d); logStream.write(d) })
const timeout = setTimeout(() => { console.error('[e2e] TIMEOUT'); try { child.kill('SIGKILL') } catch { /* ignore */ } }, 180000)

const call = (method, params = {}, timeoutMs = 60000) => server.request(method, params, { timeoutMs })
let exitCode = 1
try {
  await Promise.race([
    connectedPromise,
    new Promise((_, reject) => setTimeout(() => reject(new Error('bridge connect timeout')), 30000)),
  ])
  step('bridge connected')

  const status = await call('session.status', {}, 5000)
  if (!status || typeof status !== 'object') throw new Error('bad session.status')
  step('session.status', { state: status.state, revision: status.revision })

  const project = await call('project.create_ysm', { name: 'e2e_model', resolution: [128, 128] })
  if (!project?.project_id) throw new Error('project.create_ysm failed')
  step('project.create_ysm', { project_id: project.project_id, revision: project.revision, summary: project.summary })

  const scene = await call('project.get_scene', { scope: 'summary' })
  if (!scene?.counts || scene.counts.bones < 1) throw new Error('empty scene')
  step('project.get_scene', { counts: scene.counts, bounds: scene.bounds })

  const patch = await call('model.apply_patch', {
    ops: [
      { op: 'add_bone', parent: 'UpperBody', name: 'E2E_Arm', pivot: [5, 22, 0] },
      { op: 'add_cube', bone: 'E2E_Arm', name: 'e2e_cube', origin: [4, 16, -2], size: [2, 6, 4] },
      { op: 'update_cube', cube_id: 'e2e_cube', size: [2, 7, 4] },
    ],
  })
  if (!patch?.changed?.length) throw new Error('model.apply_patch changed empty')
  step('model.apply_patch', { revision: patch.revision, changed: patch.changed })

  const tex = await call('texture.create', { name: 'default', width: 128, height: 128, fill: '#3355aa' })
  if (!tex?.id) throw new Error('texture.create failed')
  step('texture.create', { id: tex.id, size: tex.size })

  const paint = await call('texture.apply_patch', {
    texture: 'default',
    ops: [
      { op: 'rect', x1: 8, y1: 8, x2: 24, y2: 24, color: '#aa3344' },
      { op: 'pixel', x: 8, y: 8, color: '#ffffff' },
      { op: 'line', x1: 8, y1: 24, x2: 24, y2: 8, color: '#111111' },
    ],
  })
  if (!paint?.painted_pixels) throw new Error('texture.apply_patch painted_pixels=0')
  step('texture.apply_patch', { painted_pixels: paint.painted_pixels, revision: paint.revision })

  const read = await call('texture.read', { texture: 'default', format: 'palette' })
  if (!read?.palette?.length) throw new Error('texture.read palette empty')
  step('texture.read', { colors: read.palette.length })

  const render = await call('render.views', { views: ['front', 'right', 'iso_fr'], size: [384, 384] })
  if (render?.images?.length !== 3) throw new Error(`render.views returned ${render?.images?.length} images`)
  for (const img of render.images) {
    const abs = img.workspace_path ?? path.join(workspace, img.path)
    if (!fs.existsSync(abs)) throw new Error(`render missing: ${abs}`)
    const size = pngSize(abs)
    if (size.width !== 384 || size.height !== 384) throw new Error(`bad png size: ${JSON.stringify(size)}`)
    if (size.bytes < 1024) throw new Error(`suspicious small png: ${size.bytes}`)
    img.verified = size
  }
  step('render.views', { images: render.images.map((i) => ({ view: i.view, bytes: i.verified.bytes })) })

  // 同一状态重复渲染：应检测到无可见变化
  const renderSame = await call('render.views', { views: ['front', 'right', 'iso_fr'], size: [384, 384] }, 60000)
  if (renderSame.changed_any !== false) throw new Error(`expected changed_any=false, got ${renderSame.changed_any}`)
  if (!renderSame.warnings?.some((w) => w.code === 'NO_VISIBLE_CHANGE')) throw new Error('missing NO_VISIBLE_CHANGE warning')
  step('render change detection', { changed_any: renderSame.changed_any, warning: 'NO_VISIBLE_CHANGE' })

  // 编辑后渲染：应检测到变化
  await call('model.apply_patch', { ops: [{ op: 'add_cube', bone: 'Head', name: 'e2e_visible', origin: [-1, 44, -1], size: [2, 1, 2] }] }, 30000)
  const renderChanged = await call('render.views', { views: ['front', 'right', 'iso_fr'], size: [384, 384] }, 60000)
  if (renderChanged.changed_any !== true) throw new Error('expected changed_any=true after edit')
  if (!renderChanged.images.every((i) => typeof i.alpha_ratio === 'number')) throw new Error('missing alpha_ratio')
  step('render visible-change detection', { changed_any: renderChanged.changed_any, alpha: renderChanged.images.map((i) => i.alpha_ratio) })

  // checkpoint → 额外编辑 → restore：应恢复并重载 arm
  const checkpoint = await call('project.checkpoint', { label: 'e2e-restore' }, 30000)
  await call('model.apply_patch', { ops: [{ op: 'add_cube', bone: 'Head', name: 'e2e_after_checkpoint', origin: [-1, 44, -1], size: [2, 1, 2] }] }, 30000)
  const restored = await call('project.restore', { revision: checkpoint.revision, confirm: true }, 60000)
  if (!restored?.arm_loaded) throw new Error(`restore did not reload arm: ${JSON.stringify(restored)}`)
  step('checkpoint/restore + arm', { restored_from: restored.restored_from, revision: restored.revision, arm_loaded: restored.arm_loaded, debug: restored.debug })
  const savedAfterRestore = await call('project.save', {}, 60000)
  if (!savedAfterRestore?.saved) throw new Error('save after restore failed')
  step('save after restore', { files: savedAfterRestore.files?.length })

  const shown = await call('gui.show', {}, 10000)
  const hidden = await call('gui.hide', {}, 10000)
  if (!shown.gui_visible || hidden.gui_visible) throw new Error('gui show/hide state mismatch')
  step('gui.show/hide', { shown: shown.gui_visible, hidden: hidden.gui_visible })

  const saved = await call('project.save', {}, 60000)
  if (!saved?.saved) throw new Error('project.save failed')
  step('project.save', { files: saved.files?.length, pack_dir: saved.pack_dir })

  // 二次保存幂等性：已写文件内容不应再变化
  const savedPaths = saved.files.map((f) => f.path).filter((p) => fs.existsSync(p))
  const beforeHashes = Object.fromEntries(savedPaths.map((p) => [p, hashFile(p)]))
  const savedAgain = await call('project.save', {}, 60000)
  let changedFiles = 0
  for (const [p, hash] of Object.entries(beforeHashes)) {
    if (fs.existsSync(p) && hashFile(p) !== hash) changedFiles += 1
  }
  if (changedFiles > 0) throw new Error(`second save changed ${changedFiles} files (not idempotent)`)
  step('save idempotence', { files_checked: savedPaths.length, changed: changedFiles, second_save_files: savedAgain.files?.length })

  const validate = await call('project.validate', {}, 30000)
  step('project.validate', { ok: validate.ok, errors: validate.errors, warnings: validate.warnings })
  if (validate.errors?.length) throw new Error(`validate errors: ${JSON.stringify(validate.errors)}`)

  const exported = await call('project.export_ysm', {}, 120000)
  if (!exported?.export_dir || !fs.existsSync(exported.export_dir)) throw new Error(`export_ysm failed: ${JSON.stringify(exported)}`)
  if (!fs.existsSync(exported.manifest)) throw new Error(`export manifest missing: ${exported.manifest}`)
  const manifest = JSON.parse(fs.readFileSync(exported.manifest, 'utf8'))
  if (!manifest.files?.length) throw new Error('export manifest files empty')
  if (!exported.zip_path || !fs.existsSync(exported.zip_path)) throw new Error(`export zip missing: ${exported.zip_path}`)
  const zipHead = fs.readFileSync(exported.zip_path).subarray(0, 2).toString('ascii')
  if (zipHead !== 'PK') throw new Error(`bad zip header: ${zipHead}`)
  if (!(exported.zip_files > 0)) throw new Error('zip file count empty')
  step('project.export_ysm', { export_dir: exported.export_dir, files: exported.files, manifest_files: manifest.files.length, zip: { files: exported.zip_files, bytes: exported.zip_bytes } })

  await call('system.shutdown', {}, 5000).catch(() => {})
  results.ok = true
} catch (error) {
  fail('e2e', error)
} finally {
  clearTimeout(timeout)
  logStream.end()
  await Promise.race([
    new Promise((resolve) => child.on('exit', resolve)),
    new Promise((resolve) => setTimeout(resolve, 5000)),
  ])
  if (!keep) { try { child.kill('SIGKILL') } catch { /* ignore */ } }
  await server.close()
  results.finished_at = new Date().toISOString()
  fs.writeFileSync(path.join(outDir, 'e2e-result.json'), JSON.stringify(results, null, 2))
  console.log(`[e2e] ${results.ok ? 'PASSED' : 'FAILED'} → ${path.join(outDir, 'e2e-result.json')}`)
  process.exit(results.ok ? 0 : 1)
}
