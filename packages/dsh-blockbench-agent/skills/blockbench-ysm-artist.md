# Blockbench YSM 建模/贴图工作流（bb_* 工具）

目标：用语义工具在后台 Blockbench 中安全地完成 YSM 皮肤/模型修改，并用无头渲染自检，而不是盲改 JSON。

## 0. 铁律

- **不猜结构**：先 `bb_scene(scope="summary")` / `scope="bones"` / `scope="cube"` 看真实层级与尺寸；不要凭空编 bone 名。
- **小步修改**：一次 `bb_apply_model_patch` 只做一类事（加骨/加方块/改 UV）；大改前先 `bb_checkpoint`。
- **每次可见改动后必须渲染**：`bb_render_views(["front","iso_fr"])`，看图确认；不要连续改 3 次才看一次。
- **预算意识**：会话有 edit/render/restore 预算；查看用 `bb_session_status`。渲染次数少而准。
- **不要空转**：渲染返回 `review.verdict`；连续多次 `no_visible_change` 时停止叠加，检查或回滚。
- **导出前必校验**：`bb_validate` → `bb_save_project` → `bb_export_ysm`。
- 不要直接读写 `ysm.json`/模型 JSON 让用户粘贴；用工具。需要看细节用 `bb_get_element`。

## 1. 开局

1. `bb_session_status`：确认 `state=idle/editing`、`gpu_ok=true`。
2. 新模型：
   `bb_session_start({mode:"new_ysm", name:"...", pack_dir:"..."})`
   已有包：
   `bb_session_start({mode:"open_pack", pack_dir:"..."})`
3. `bb_scene({scope:"summary"})` 记录 bones/cubes/textures/animations 基线；列骨骼 `bb_scene({scope:"bones"})`。

## 2. 造型

- 加方块：`{op:"add_cube", bone:"Head", name:"...", origin:[x,y,z], size:[w,h,d], texture:"default"}`
  - 坐标是 Blockbench 空间（Y 向上，像素=1/16 格）；先看父骨骼已有 cube 的 origin/size 对齐。
  - 加完立刻看 UV：`bb_scene({scope:"cube", id:"<name>", include_uv:true})`。
  - 自动 UV 可能是 `[0,0]` 重叠；需要可辨识颜色时用 `set_uv` 指定区域并预留贴图空间。
- 改尺寸/位置：`{op:"update_cube", id:"...", origin:[...], size:[...]}`；改骨骼 `{op:"update_bone", ...}`。
- `delete` 用 refs 数组；删骨骼会连带子级，慎重。
- 布尔/网格/自由造型当前不保证；优先方块+骨骼。

## 3. 贴图

- 先 `bb_texture_read({format:"palette", region:[...]})` 看主色，避免覆盖重要区域。
- 涂色：`bb_texture_patch({texture:"default", ops:[{op:"rect"...},{op:"line"...},{op:"pixel"...}]})`，坐标是纹理像素（默认 128×128）。
- UV 与像素对应：`set_uv` 的 `uv` 是纹理左上角像素；方块面尺寸决定 `uv_size`（工具会自动设）。要改哪块面，就改对应 UV 区域并渲染确认。
- 新贴图：`bb_texture_create({name, width, height, fill})`；绑定/选择默认用 `texture` 参数或 `texture.select`。
- 图层（编辑期便利）：`bb_texture_layer({op:"create"|"list"|"select"|"delete"|"flatten", texture, name/layer, fill})`；保存时合成回单张 PNG。
- PBR（现代光影）：`bb_texture_pbr({op:"create", texture:"default", channel:"normal"|"specular"})` 生成 `_n`/`_s` 贴图并随包保存；`op:"list"` 查看。只有支持 PBR 的光影/环境才会显示效果。
- 需要外部图：先放进 workspace，再 `bb_texture_import_png({texture, path, at})`；导出检查用 `bb_texture_export_png` + `bb_render_texture`。

## 4. 动画

- 列表：`bb_animation_list`。
- 新建：`bb_animation_create({name:"animation.main.wave", length:1, loop:"loop"})`。
- 关键帧：
  `bb_animation_patch({ops:[{op:"set_keyframes", animation:"animation.main.wave", bone:"Head", channel:"rotation", keys:[{time:0,value:[0,0,0]},{time:0.5,value:[0,45,0]}]}]})`
  - channel: rotation/position/scale；value 单位分别度/像素/倍率。
  - 一个 patch 内多个 op 共享一个 Undo；失败整体回滚。
- 删除：`bb_animation_delete` 或 `delete_animation` op。
- 绑定控制器：`bb_animation_patch({ops:[{op:"bind_controller", animation:"animation.main.wave", controller:"player.pre_main", state:"default"}]})`；`bb_animation_list` 返回控制器/状态与已绑定动画。

## 5. 渲染自检

- 标准两视图：`bb_render_views({views:["front","iso_fr"], size:[768,768]})`。
- 局部细节：`bb_render_views({views:["closeup"], focus:{element:"Head"}, antialias:"ssaa", size:[512,512]})`；`iso_fl`、`iso_br`、`top` 也可用。
- 贴图细节：`bb_render_texture({texture:"default", scale:8, region:[x1,y1,x2,y2]})`。
- 结果带 `changed_any` 与 `review`（verdict / unchanged_streak / suggestion）：连续多次编辑后仍 `NO_VISIBLE_CHANGE`，先查 UV/绑定/层级，必要时 `bb_restore` 回滚，不要继续叠加同类修改。
- 判断：颜色/形状/位置是否与意图一致；如果 `changed_any=false` 或出现 `NO_VISIBLE_CHANGE`，先查 revision 是否增加、UV 是否真的指到涂色区域。
- 背景透明，不要用“背景色没变”判断失败；`EMPTY_RENDER` 表示整张图全透明，通常是相机/几何/GPU 问题。

## 6. 保存/导出/回滚

- 检查点：`bb_checkpoint({label:"..."})`；列表 `bb_revisions`；回滚 `bb_restore({revision:n, confirm:true})`（会丢弃当前未保存改动）。
- 保存：`bb_save_project`（写回 pack：模型/动画/控制器/贴图/ysm.json）。
- 导出：`bb_export_ysm`（先 validate；产物含 export-manifest.json 与 zip；`zip:false` 可关闭 zip）。
- 批量只读/小操作可用 `bb_batch`；它不是事务，失败了不会自动回滚。

## 7. 用户接管

- 用户说“我来看看/手动改” → 提示输入 `/show`；窗口显示期间所有写操作会返回 `GUI_BUSY`。
- 用户改完输入 `/hide` 后会返回 `user_edits` 摘要；先 `bb_scene` 重新对账 revision，再继续。
- 不要自己调用 gui.show/hide 工具（默认未暴露）；用命令提示用户。

## 8. YSM 约束速查

- 默认 main：64 bones / 172 cubes 上限；arm：6 bones。超出会导致游戏端丢弃。
- 贴图默认 128×128；单纹理多 UV 图集。
- 必需定位组：Head、Body、RightArm、LeftArm、RightLeg、LeftLeg 等；`bb_validate` 会报缺失。
- 动画文件路径由 ysm.json 决定（通常 `animations/main.animation.json`）；新建动画默认挂到 main。
- 改完模型/贴图记得保存，否则导出的是磁盘旧版本。
