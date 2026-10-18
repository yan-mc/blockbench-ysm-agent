// dsh Host 插件集成冒烟测试（不安装到 profile）
// 做法：把插件复制到 workspace/_hosttest 并用 stub 的 @deepseek-ai/dsh-tools 加载，
//       用 mock ctx 调用 apply()，然后通过工具定义直接驱动真实 BAE（spawn Electron）。
// 覆盖：spawn/连接、session_start、scene、model patch、texture create/patch、render+图片附件、checkpoint、save、命令。

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PACKAGE_ROOT = path.resolve(__dirname, '..')
const REPO_ROOT = path.resolve(PACKAGE_ROOT, '..', '..')
const appDir = path.join(REPO_ROOT, 'dist', 'bb-agent-app')
const electronExe = path.join(REPO_ROOT, 'vendor', 'blockbench', 'node_modules', 'electron', 'dist', process.platform === 'win32' ? 'electron.exe' : 'electron')
const testRoot = path.join(REPO_ROOT, 'workspace', '_hosttest')
fs.rmSync(testRoot, { recursive: true, force: true })
fs.mkdirSync(path.join(testRoot, 'plugin', 'lib'), { recursive: true })
fs.mkdirSync(path.join(testRoot, 'plugin', 'node_modules', '@deepseek-ai', 'dsh-tools'), { recursive: true })
fs.mkdirSync(path.join(testRoot, 'logs'), { recursive: true })
fs.cpSync(path.join(PACKAGE_ROOT, 'index.js'), path.join(testRoot, 'plugin', 'index.js'))
fs.cpSync(path.join(PACKAGE_ROOT, 'lib', 'ws-server.js'), path.join(testRoot, 'plugin', 'lib', 'ws-server.js'))
fs.writeFileSync(path.join(testRoot, 'plugin', 'package.json'), JSON.stringify({ name: 'hosttest-plugin', type: 'module' }, null, 2))
fs.writeFileSync(path.join(testRoot, 'plugin', 'node_modules', '@deepseek-ai', 'dsh-tools', 'package.json'), JSON.stringify({
  name: '@deepseek-ai/dsh-tools', version: '0.0.0-test', type: 'module', exports: { '.': './index.js' },
}, null, 2))
fs.writeFileSync(path.join(testRoot, 'plugin', 'node_modules', '@deepseek-ai', 'dsh-tools', 'index.js'), 'export const defineTool = (definition) => definition\n')

const results = { ok: false, steps: [] }
const step = (name, data) => { results.steps.push({ name, data }); console.log(`[hosttest] ✓ ${name}`, data ? JSON.stringify(data).slice(0, 240) : '') }
const fail = (name, error) => { results.steps.push({ name, error: String(error?.stack ?? error) }); console.error(`[hosttest] ✗ ${name}`, error) }

const tools = new Map()
const commands = new Map()
const savedImages = []
const mockAttachments = {
  async saveImage({ data, mediaType, name }) {
    savedImages.push({ bytes: data?.length ?? 0, mediaType, name })
    return { attachmentId: `att-${savedImages.length}`, mediaType, bytes: data?.length ?? 0, width: 384, height: 384, name }
  },
}
let cleanup = null
const ctx = {
  tools: { register(definition) { tools.set(definition.name, definition); return () => tools.delete(definition.name) } },
  commands: { register(definition) { commands.set(definition.name, definition); return () => commands.delete(definition.name) } },
  get(name) { return name === 'attachments' ? mockAttachments : undefined },
  effect(fn) { cleanup = fn(); return () => {} },
  logger: { info() {}, warn() {} },
}

const plugin = await import(pathToFileURL(path.join(testRoot, 'plugin', 'index.js')).href)
await plugin.apply(ctx, {
  workspaceRoot: path.join(testRoot, 'workspaces'),
  project: 'demo',
  executable: electronExe,
  appPath: appDir,
  autoStart: true,
  connectTimeoutMs: 30000,
  defaultTimeoutMs: 120000,
})
step('plugin applied', { tools: [...tools.keys()], commands: [...commands.keys()] })

const exec = async (name, args = {}) => {
  const def = tools.get(name)
  if (!def) throw new Error(`tool missing: ${name}`)
  return def.execute(args, { signal: new AbortController().signal })
}
const command = async (name) => {
  const def = commands.get(name)
  if (!def) throw new Error(`command missing: ${name}`)
  return def.handler({ name, args: [], raw: `/${name}` })
}

try {
  // 等运行时连接
  let status = null
  for (let i = 0; i < 120; i++) {
    status = await exec('bb_session_status')
    if (status && status.state) break
    await new Promise((r) => setTimeout(r, 250))
  }
  if (!status?.state) throw new Error(`runtime not connected: ${JSON.stringify(status)}`)
  step('bb_session_status', { state: status.state, revision: status.revision })

  const created = await exec('bb_session_start', { mode: 'new_ysm', name: 'hosttest_model', resolution: [128, 128] })
  if (!created?.project_id) throw new Error(`bb_session_start failed: ${JSON.stringify(created)}`)
  step('bb_session_start', { project_id: created.project_id, revision: created.revision, summary: created.summary })

  const scene = await exec('bb_scene', { scope: 'summary' })
  if (!scene?.counts) throw new Error('bb_scene failed')
  step('bb_scene', { counts: scene.counts })

  const patch = await exec('bb_apply_model_patch', {
    note: 'hosttest',
    ops: [
      { op: 'add_bone', parent: 'UpperBody', name: 'HostTest_Arm', pivot: [5, 22, 0] },
      { op: 'add_cube', bone: 'HostTest_Arm', name: 'hosttest_cube', origin: [4, 16, -2], size: [2, 6, 4] },
    ],
  })
  if (!patch?.changed?.length) throw new Error(`bb_apply_model_patch failed: ${JSON.stringify(patch)}`)
  step('bb_apply_model_patch', { revision: patch.revision, changed: patch.changed.length })

  const texture = await exec('bb_texture_create', { name: 'default', width: 128, height: 128, fill: '#224488' })
  if (!texture?.id) throw new Error('bb_texture_create failed')
  step('bb_texture_create', { size: texture.size })

  const painted = await exec('bb_texture_patch', {
    texture: 'default',
    ops: [{ op: 'rect', x1: 4, y1: 4, x2: 20, y2: 20, color: '#cc3344' }, { op: 'pixel', x: 4, y: 4, color: '#ffffff' }],
  })
  if (!painted?.painted_pixels) throw new Error('bb_texture_patch failed')
  step('bb_texture_patch', { painted_pixels: painted.painted_pixels })

  const render = await exec('bb_render_views', { views: ['front', 'right'], size: [384, 384] })
  if (!render?.images?.length) throw new Error('bb_render_views failed')
  const blocks = tools.get('bb_render_views').output.render({}, render)
  const imageBlocks = blocks.filter((b) => b.type === 'image').length
  if (imageBlocks !== render.images.filter((i) => i.attachment).length) throw new Error(`image block mismatch ${imageBlocks}`)
  if (imageBlocks < 2) throw new Error(`expected >=2 image attachments, got ${imageBlocks}`)
  step('bb_render_views', { images: render.images.length, imageBlocks, savedImages: savedImages.length })

  const checkpoint = await exec('bb_checkpoint', { label: 'hosttest' })
  if (!checkpoint?.checkpoint) throw new Error('bb_checkpoint failed')
  step('bb_checkpoint', { checkpoint: checkpoint.checkpoint, bytes: checkpoint.bytes })

  const revisions = await exec('bb_revisions', {})
  step('bb_revisions', { count: revisions.checkpoints?.length })

  const saved = await exec('bb_save_project', {})
  if (!saved?.saved) throw new Error('bb_save_project failed')
  step('bb_save_project', { files: saved.files?.length, pack_dir: saved.pack_dir })

  const validated = await exec('bb_validate', {})
  step('bb_validate', { ok: validated.ok, errors: validated.errors?.length, warnings: validated.warnings?.length })

  // ---- 新增：revision 冲突 / 动画 / 贴图导入导出 / restore / batch / diagnostics / GUI 门控
  const conflict = await exec('bb_apply_model_patch', { expected_revision: 0, ops: [{ op: 'add_bone', name: 'ConflictBone' }] })
  if (conflict?.code !== 'REVISION_CONFLICT') throw new Error(`expected REVISION_CONFLICT, got ${JSON.stringify(conflict)}`)
  step('revision conflict', { code: conflict.code })

  const mainAnimAbs = path.join(testRoot, 'workspaces', 'demo', 'pack', 'animations', 'main.animation.json')
  const baselineAnimCount = fs.existsSync(mainAnimAbs) ? Object.keys(JSON.parse(fs.readFileSync(mainAnimAbs, 'utf8')).animations ?? {}).length : 0

  const animation = await exec('bb_animation_create', { name: 'hosttest_wave', length: 1, loop: 'once' })
  if (!animation?.animation) throw new Error(`bb_animation_create failed: ${JSON.stringify(animation)}`)
  const animPatch = await exec('bb_animation_patch', {
    ops: [{
      op: 'set_keyframes', animation: 'hosttest_wave', bone: 'Head', channel: 'rotation',
      keys: [{ time: 0, value: [0, 0, 0] }, { time: 0.5, value: [0, 45, 0] }],
    }],
  })
  if (!animPatch?.changed?.length) throw new Error(`bb_animation_patch failed: ${JSON.stringify(animPatch)}`)
  const animList = await exec('bb_animation_list', {})
  if (!animList.animations?.some((a) => a.animation === 'hosttest_wave')) throw new Error('animation missing from list')
  step('animation create/patch/list', { created: animation.animation, list: animList.animations.length })

  const exportedTexture = await exec('bb_texture_export_png', { texture: 'default' })
  if (!fs.existsSync(exportedTexture.workspace_path)) throw new Error(`texture export missing: ${exportedTexture.workspace_path}`)
  const importedTexture = await exec('bb_texture_import_png', { texture: 'default', path: exportedTexture.path, at: [0, 0] })
  if (!importedTexture?.ok) throw new Error(`bb_texture_import_png failed: ${JSON.stringify(importedTexture)}`)
  step('texture export/import', { path: exportedTexture.path, size: exportedTexture.bytes })

  // B1 回归：checkpoint 必须保存贴图快照；restore 后画布应回到 checkpoint 状态
  // 用独立名字避免模板里已有 default 造成同名歧义
  await exec('bb_texture_create', { name: 'restore_tex', width: 64, height: 64, fill: '#112233' })
  await exec('bb_texture_patch', { texture: 'restore_tex', ops: [{ op: 'pixel', x: 1, y: 1, color: '#00ff00' }] })
  const paletteBefore = await exec('bb_texture_read', { texture: 'restore_tex', format: 'palette', region: [0, 0, 2, 2], max_colors: 8 })
  if (!JSON.stringify(paletteBefore).includes('#00ff00')) throw new Error(`checkpoint baseline pixel missing: ${JSON.stringify(paletteBefore)}`)
  const checkpoint2 = await exec('bb_checkpoint', { label: 'before-restore' })
  const checkpointAbs = path.join(testRoot, 'workspaces', 'demo', checkpoint2.checkpoint)
  const metaAbs = checkpointAbs.replace(/\.bbmodel$/, '.meta.json')
  if (!fs.existsSync(metaAbs)) throw new Error(`checkpoint meta missing: ${metaAbs}`)
  const checkpointMeta = JSON.parse(fs.readFileSync(metaAbs, 'utf8'))
  if (!checkpointMeta.texture_snapshots?.length) throw new Error('checkpoint did not save texture snapshots')
  const extraPatch = await exec('bb_apply_model_patch', {
    ops: [{ op: 'add_cube', bone: 'Head', name: 'after_checkpoint', origin: [-1, 42, -1], size: [2, 1, 2] }],
  })
  if (!extraPatch?.changed?.length) throw new Error('extra edit failed')
  await exec('bb_texture_patch', { texture: 'restore_tex', ops: [{ op: 'pixel', x: 1, y: 1, color: '#ff0000' }] })
  const beforeRestore = await exec('bb_scene', { scope: 'summary' })
  const restored = await exec('bb_restore', { revision: checkpoint2.revision, confirm: true })
  if (!restored?.revision) throw new Error(`bb_restore failed: ${JSON.stringify(restored)}`)
  const paletteAfter = await exec('bb_texture_read', { texture: 'restore_tex', format: 'palette', region: [0, 0, 2, 2], max_colors: 8 })
  if (!JSON.stringify(paletteAfter).includes('#00ff00')) throw new Error(`checkpoint texture restore mismatch: ${JSON.stringify(paletteAfter)}`)
  const afterRestore = await exec('bb_scene', { scope: 'summary' })
  if (afterRestore.counts.cubes >= beforeRestore.counts.cubes) throw new Error('restore did not roll back cube count')
  if (checkpointMeta.arm_checkpoint && !restored.arm_from_checkpoint) throw new Error(`arm snapshot not restored: ${JSON.stringify(restored)}`)
  step('checkpoint/restore', {
    from: beforeRestore.counts.cubes, to: afterRestore.counts.cubes, revision: restored.revision,
    textures: checkpointMeta.texture_snapshots.length, restored_textures: restored.textures_restored,
    arm_from_checkpoint: restored.arm_from_checkpoint,
  })

  // B5/B7 回归：add_cube 支持 inflate/rotation/uv.sizes；update_bone 接受 bone_id 别名
  const advanced = await exec('bb_apply_model_patch', {
    ops: [
      {
        op: 'add_cube', bone: 'Head', name: 'inflated_cube', origin: [0, 42, 0], size: [2, 2, 2],
        inflate: 1.5, rotation: [10, 20, 30],
        uv: { mode: 'faces', faces: { north: [0, 0] }, sizes: { north: [6, 6] } },
      },
      { op: 'update_bone', bone_id: 'Head', rotation: [0, 1, 0] },
    ],
  })
  if (!advanced?.changed?.length) throw new Error(`advanced model patch failed: ${JSON.stringify(advanced)}`)
  const cubeInfo = await exec('bb_scene', { scope: 'cube', id: 'inflated_cube', include_uv: true })
  if (Number(cubeInfo?.inflate) !== 1.5) throw new Error(`inflate not applied: ${JSON.stringify(cubeInfo)}`)
  if (!cubeInfo?.rotation?.some((v) => v !== 0)) throw new Error(`rotation not applied: ${JSON.stringify(cubeInfo)}`)
  if (JSON.stringify(cubeInfo?.uv?.faces?.north?.uv_size) !== JSON.stringify([6, 6])) throw new Error(`uv_size override failed: ${JSON.stringify(cubeInfo?.uv)}`)
  await exec('bb_apply_model_patch', { ops: [{ op: 'update_bone', bone_id: 'Head', rotation: [0, 0, 0] }] })
  step('model patch inflate/rotation/uv_size/alias', { inflate: cubeInfo.inflate, uv_size: cubeInfo.uv.faces.north.uv_size })

  const controllerInfo = (animList.controllers ?? []).find((c) => c.states?.length)
  if (!controllerInfo) throw new Error('no controller states to bind')
  const bound = await exec('bb_animation_patch', {
    ops: [{ op: 'bind_controller', animation: 'hosttest_wave', controller: controllerInfo.controller, state: controllerInfo.states[0].name }],
  })
  if (!bound?.changed?.some((c) => c.op === 'bind_controller')) throw new Error(`bind_controller failed: ${JSON.stringify(bound)}`)
  step('controller bind', { controller: controllerInfo.controller, state: controllerInfo.states[0].name })

  const layer = await exec('bb_texture_layer', { op: 'create', texture: 'default', name: 'agent_layer', fill: '#ff0000' })
  if (!layer?.ok) throw new Error(`layer create failed: ${JSON.stringify(layer)}`)
  const layers = await exec('bb_texture_layer', { op: 'list', texture: 'default' })
  if (!layers.layers?.some((l) => l.layer === 'agent_layer')) throw new Error(`layer list missing: ${JSON.stringify(layers)}`)
  const flattened = await exec('bb_texture_layer', { op: 'flatten', texture: 'default' })
  if (flattened.layers_enabled !== false) throw new Error('layer flatten failed')
  step('texture layers', { layers: layers.layers.length, flattened: flattened.layers_enabled })

  const pbr = await exec('bb_texture_pbr', { op: 'create', texture: 'default', channel: 'normal' })
  if (!pbr?.texture?.endsWith('_n')) throw new Error(`pbr create failed: ${JSON.stringify(pbr)}`)
  const pbrList = await exec('bb_texture_pbr', { op: 'list' })
  if (!pbrList.pbr_textures?.some((t) => t.texture === pbr.texture)) throw new Error('pbr list missing')
  const savedAfterPbr = await exec('bb_save_project', {})
  const pbrAbs = path.join(testRoot, 'workspaces', 'demo', 'pack', 'textures', `${pbr.texture}.png`)
  if (!fs.existsSync(pbrAbs)) throw new Error(`PBR file not saved: ${pbrAbs}; save=${JSON.stringify(savedAfterPbr)}`)
  if (fs.existsSync(mainAnimAbs)) {
    const mergedJson = JSON.parse(fs.readFileSync(mainAnimAbs, 'utf8'))
    const anims = mergedJson.animations ?? {}
    if (!anims.hosttest_wave) throw new Error('animation merge-back lost hosttest_wave')
    if (Object.keys(anims).length < baselineAnimCount + 1) throw new Error(`animation merge-back lost original animations: ${Object.keys(anims).length} < ${baselineAnimCount + 1}`)
  }
  step('texture PBR', { texture: pbr.texture, saved_files: savedAfterPbr.files?.length })
  step('animation merge-back', { baseline: baselineAnimCount, after: fs.existsSync(mainAnimAbs) ? Object.keys(JSON.parse(fs.readFileSync(mainAnimAbs, 'utf8')).animations ?? {}).length : 0 })

  // 隐藏方块：先以相同尺寸建基线，再编辑并渲染，应判定 no_visible_change
  await exec('bb_render_views', { views: ['front'], size: [256, 256] })
  await exec('bb_apply_model_patch', { ops: [{ op: 'add_cube', bone: 'Head', name: 'hidden_edit', origin: [-1, 34, -1], size: [1, 1, 1] }] })
  const noVisible = await exec('bb_render_views', { views: ['front'], size: [256, 256] })
  if (noVisible?.review?.verdict !== 'no_visible_change') throw new Error(`watchdog verdict: ${JSON.stringify(noVisible?.review)}`)
  step('render watchdog', { verdict: noVisible.review.verdict, streak: noVisible.review.unchanged_streak })

  const closeup = await exec('bb_render_views', { views: ['closeup'], size: [256, 256], antialias: 'ssaa' })
  const closeImage = closeup.images?.[0]
  if (!closeImage || closeImage.width !== 256 || closeImage.antialias !== 'ssaa') throw new Error(`closeup/ssaa failed: ${JSON.stringify(closeImage)}`)
  step('closeup + SSAA', { width: closeImage.width, antialias: closeImage.antialias, focus: closeImage.focus })

  const batch = await exec('bb_batch', { calls: [{ tool: 'bb_scene', args: { scope: 'summary' } }, { tool: 'bb_validate', args: {} }] })
  if (!batch?.results?.length || batch.results.length !== 2) throw new Error(`bb_batch failed: ${JSON.stringify(batch)}`)
  step('bb_batch', { results: batch.results.length, ok: batch.ok })

  const diagnostics = await exec('bb_diagnostics', {})
  if (!diagnostics?.ok || !diagnostics.runtime?.connected) throw new Error(`bb_diagnostics failed: ${JSON.stringify(diagnostics)}`)
  step('bb_diagnostics', { childPid: diagnostics.runtime.childPid, logs: Object.keys(diagnostics.logs) })

  const show = await command('show')
  const blocked = await exec('bb_apply_model_patch', { ops: [{ op: 'add_bone', name: 'GuiBlocked' }] })
  if (blocked?.code !== 'GUI_BUSY') throw new Error(`expected GUI_BUSY while visible, got ${JSON.stringify(blocked)}`)
  const hide = await command('hide')
  if (show.kind !== 'success' || hide.kind !== 'success') throw new Error(`show/hide failed: ${show.text} / ${hide.text}`)
  step('/show + GUI_BUSY + /hide', { show: show.text, hide: hide.text, blocked: blocked.code })

  const closed = await exec('bb_project_close', { force: true })
  if (!closed?.closed) throw new Error(`bb_project_close failed: ${JSON.stringify(closed)}`)
  step('bb_project_close', { closed: closed.closed })

  results.ok = true
} catch (error) {
  fail('hosttest', error)
} finally {
  try { cleanup?.() } catch (error) { console.warn('[hosttest] cleanup error', error?.message) }
  // 等待 electron 退出，避免残留
  await new Promise((r) => setTimeout(r, 1500))
  fs.writeFileSync(path.join(testRoot, 'hosttest-result.json'), JSON.stringify(results, null, 2))
  console.log(`[hosttest] ${results.ok ? 'PASSED' : 'FAILED'} → ${path.join(testRoot, 'hosttest-result.json')}`)
  process.exit(results.ok ? 0 : 1)
}

