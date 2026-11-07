# Blockbench YSM 建模/贴图工作流（bb_* 工具）

目标：用语义工具在后台 Blockbench 中安全地完成 YSM 皮肤/模型修改，并用无头渲染自检，而不是盲改 JSON。

## 0-A. 谁来调用（**强制**）

**主代理不要直接调用任何 `bb_*` 工具。** 一律走委派：

```
用户请求 → 主代理判定任务类型 → 用 assets/delegation-brief.md 模板拉起子智能体
        → 子智能体先「完善任务书（promote）」→ 再执行 → 回报产物与证据
主代理只做汇总与验收，不碰 bb_*
```

**必须委派的理由**（都是踩过的坑，不是洁癖）：

| 问题 | 不委派的后果 | 委派的收益 |
|---|---|---|
| 图像 token 污染 | 每张渲染 200–900 token，主会话很快被图塞满，后续推理质量下降 | 图只进子智能体上下文，主会话只收结论 |
| 跳过前置 | 主会话容易"直接改方块"，漏掉搜参考图 / 写 spec / 看对照表 | 子智能体按技能流程走，promote 阶段强制补齐 |
| 长任务被打断 | 建模动辄几十次写操作 + 多轮看图 | 子智能体独立上下文可长时间跑，失败可重启 |
| 事故难隔离 | 一次误删/误涂直接污染主线状态 | 子智能体工作副本独立，可 checkpoint 回滚 |

**例外**：只读的一次性查询（`bb_session_status` 看状态）可以由主代理做，但一旦涉及看图和改模型就必须委派。

委派协议与任务书模板见：
- `docs/17-子智能体委派规范.md`
- `assets/delegation-brief.md`

## 0. 铁律

- **不猜结构**：先 `bb_scene(scope="summary")` / `scope="bones"` / `scope="cube"` 看真实层级与尺寸；不要凭空编 bone 名。
- **小步修改**：一次 `bb_apply_model_patch` 只做一类事（加骨/加方块/改 UV）；大改前先 `bb_checkpoint`。
- **每次可见改动后必须看图**：写操作会自动附 `front + iso_fr` 拼图；不够就 `bb_look` / `bb_orbit` 补。不要连续改 3 次才看一次。
- **预算意识**：会话有 edit/render/restore 预算；查看用 `bb_session_status`。渲染次数少而准。
- **不要空转**：渲染返回 `review.verdict`；连续多次 `no_visible_change` 时停止叠加，检查或回滚。
- **导出前必校验**：`bb_validate` → `bb_save_project` → `bb_export_ysm`。
- 不要直接读写 `ysm.json`/模型 JSON 让用户粘贴；用工具。需要看细节用 `bb_get_element`。

## 1. 开局

**第 0 步：先拿「官方基准」，再大面积搜图。** 顺序不能反。

### 0-a 官方基准（必做第一步）

```
bb_ref_canon({character:"角色名"})
```

一次拿到三样东西：

1. **facts**：百科条目的外观描述（发色/瞳色/服装/身高/代号），已按外观相关段落裁剪；
2. **name_variants**：外文名/罗马音（例如「Eiga Sakiko」），**booru 类图站只认罗马音**；
3. **官方图**：条目自带的图里按角色名匹配出的官方立绘，并拼成一张编号对照表。

**这份基准是用来校验后面所有图的**。先看它，确认"这个角色到底长什么样"，
再去判断后面搜到的一堆同人图哪些对、哪些是别的角色、哪些是 AI 图。

> 实测教训：验收那次 15 张候选里混进了**另一个角色**（鹿島神：紫瞳短发水手服），
> 靠人肉识别才发现。有官方基准就能一眼排除。

### 0-b 大面积搜索（搜索本身很便宜，别省）

```
bb_ref_search({character:"角色名", depth:"deep", romaji:<name_variants>})
```

`depth:"deep"` 会展开 **全部查询词（24 条：中/日/英 × 设定集/三视图/立绘/背面/侧面/服装细节）
× Bing 三语区（zh-CN/ja-JP/en-US） × 分页（1-3）**，实测候选量比 fast 模式放大一个数量级。

源：Bing（多语区×分页）/ 360（分页）/ 萌娘百科图库 / yande.re（booru，需罗马音，高质量原图）。
单源失败自动跳过并在 `sources` 里报告状态——**不要把失败当成功**。

### 0-c 下载成对照表

- `bb_ref_collect()` —— 不传 urls 就用上一次搜索结果；下载 + 精确/感知去重 + 拼成**一张带编号对照表**。
- **必须真的看这张表**：确认哪些是同一角色、各是什么角度、有没有设定集页。
  编号 = `images[].index`，后续可直接说"#3 是背面"。
- 对照 `bb_ref_canon` 的基准：颜色/发型/服装对不上的直接剔除。
- 搜不到背面是常态：**继续做，背面合理推测，最后明确告诉用户"缺背面参考"**。
- 详见 `docs/11-参考图收集管线.md`、`docs/18-官方基准与深度搜索.md`。

**第 0.5 步：把结论写成 spec，再动手建。**
看过对照表后调用 `bb_spec_save({spec})`，把"角色长什么样、分几个部件、各给多少方块、
用什么色、哪张图对应哪个角度"固化成结构化的建模规格。

- 校验会挡住明显会做砸的方案：方块总数、头部占比（成品感主要来自头）、贴图尺寸、
  **缺背面参考却没在 `gaps` 里记录（直接 error）**。
- 通过后返回**构建计划**：`order`（按什么顺序建）+ `bones`（每个骨骼的父级与方块预算）+
  `texture.regions`（贴图分区面积）。
- 换会话或隔天继续：`bb_spec_load()` 直接恢复，不必重新搜图。
- 详见 `docs/12-建模规格与构建计划.md`。

然后：

1. `bb_session_status`：确认 `state=idle/editing`、`gpu_ok=true`。
2. 新模型：
   `bb_session_start({mode:"new_ysm", name:"...", pack_dir:"..."})`
   已有包：
   `bb_session_start({mode:"open_pack", pack_dir:"..."})`
3. `bb_scene({scope:"summary"})` 记录 bones/cubes/textures/animations 基线；列骨骼 `bb_scene({scope:"bones"})`。

## 2. 造型

> **开做前读这两份**（用 read 工具，绝对路径）：
> - `F:\Deepseek_harness\blockbench\packages\dsh-blockbench-agent\reference\blockbench-ysm-playbook.md`
>   —— 操作规范：骨架/命名/边角填缝/眼睛四层/贴图色彩/arm.json/动画槽位/MoLang
> - `F:\Deepseek_harness\blockbench\packages\dsh-blockbench-agent\reference\ysm-corpus-rules.md`
>   —— 181 个真实模型实测：方块预算、竖向分布、贴图尺寸、骨架出现率
>
> 三条最关键的：**方块总数中位 306、人物建议 50-300**；
> **头部区域要占 35–40%**（成品感主要来自头）；**贴图默认开 256，128 只是模板遗留**。

- 加方块：`{op:"add_cube", bone:"Head", name:"...", origin:[x,y,z], size:[w,h,d], texture:"default"}`
  - 坐标是 Blockbench 空间（Y 向上，像素=1/16 格）；先看父骨骼已有 cube 的 origin/size 对齐。
  - 加完立刻看 UV：`bb_scene({scope:"cube", id:"<name>", include_uv:true})`。
  - 自动 UV 可能是 `[0,0]` 重叠；需要可辨识颜色时用 `set_uv` 指定区域并预留贴图空间。
- 改尺寸/位置：`{op:"update_cube", id:"...", origin:[...], size:[...]}`；改骨骼 `{op:"update_bone", ...}`。
- `delete` 用 refs 数组；删骨骼会连带子级，慎重。
- 布尔/网格/自由造型当前不保证；优先方块+骨骼。
- **骨骼名要有语义**：语料里 `bone`/`bone2`… 出现率 54%，那是没改名的导入品，不是风格。
  官方规范：大写驼峰 + 形容词+名称（`LeftArm`/`AllHead`）；无意义分组用 `Mouth1`/`Mouth2`。
- 手/脚加 `RightHandLocator` / `LeftHandLocator`（社区 62% 都有，只是空骨骼，成本为零）。
  **Locator 必须放在对应 `Hand` 组里面**，否则持物定位失效。
- **边角接缝**：两面共面或近乎共面时调 `inflate`——`+0.01~+0.005` 外撑遮缝，
  `-0.01` 内收避穿模。不要用大幅 inflate 当圆角。
- **眼睛做四层**：`Eyelid → EyelidBase → EyesDot / Pupil (+高光)`，缺 EyesDot 会"糊"。

### 2.1 面部与头发的硬指标（拆解 4 个高完成度模型得出，见 docs/19）

**脸不要雕，要"框"。** 实测四个顶级模型（wine_fox 系列 + 官方 default_controllers）
的 `Head` 全是**一个 7×7×7 的平板方块、rotation=null**——没有一个是靠旋转方块削脸的。
脸型的观感来自三件事：刘海压过眉线吃掉额头直角、侧发贴着脸颊遮住侧棱、眼睛足够大。

| 指标 | 目标值 | 说明 |
|---|---|---|
| 头高 / 总身高 | **约 16%** | 7 单位头 / 约 44 单位身高 |
| 眼睛高度 / 脸高 | **28.6%**（= 2/7） | 7×7 脸上眼睛做成 **2×2** |
| 眼睛宽度 / 脸宽 | **28.6%** | 双眼中缝占脸宽 **40%**，两侧各只留 **0.1** |
| 眼中心高度（从脸底算） | **28.6%** | 眼睛偏下，额头大、被刘海盖住 |
| 虹膜层 z 厚度 | **2**（凸出脸面约 1.4） | 眼睛是凸出的方块堆，不是画上去的 |
| 眉毛凸出 | 比眼睛更前 0.5–1.0 | 2 个方块（内短外长） |

> 实测对照：v5 模型眼高只有 10.6%、位置 57.1%，是"娃娃眼/表情素"的根因。
> 眼高改成 2/7、下移到 28.6%，观感立刻不同。

**头发用薄片链，不要用厚块。**

- 每片厚度 **1.0–1.2 单位**（不是 2–3）
- 相邻片 **微转 3–7°**，位置递进、端点错落 → 一串平面小段拟合出弧线
- 刘海：8 片左右，长短差 1–2 单位，在脸面前方约 1.5 单位，统一下俯 5–8°
- 要做丝带/尾巴/发束这类连续曲线：**一串扁方块 + 递增角度**，不要旋转大块
- 真正的高级曲面（耳朵、面具）是**在 3D 视口里一块块自由摆**出来的，不是算公式：
  参考 `Left_ear` 的 11 个块用了 `(167°,73°,-175°)` 这种任意朝向

## 3. 贴图

**上色五条**（来自官方群课程，详见 playbook §7）：
1. **明度**：朝上的面更亮、朝下的面更暗；朝南北较亮、朝东西较暗
2. **饱和度**：亮部更低、暗部更高；阴影饱和度较低
3. **天光设定**：阳光亮黄+大气蓝 → **亮面偏暖、暗面偏冷、阴影偏冷**
4. **AO**：阳角亮、阴角暗
5. **闭塞阴影**：物体根部/缝隙最深，越远越浅

- 先 `bb_texture_read({format:"palette", region:[...]})` 看主色，避免覆盖重要区域。
- 涂色：`bb_texture_patch({texture:"default", ops:[{op:"rect"...},{op:"line"...},{op:"pixel"...}]})`，坐标是纹理像素（默认 128×128）。
- UV 与像素对应：`set_uv` 的 `uv` 是纹理左上角像素；默认 `uv_size` 由方块面尺寸决定，也可显式传 `uv_size:[w,h]`（或每面 `sizes`）把任意设计图压到指定面。add_cube 也可直接带 `uv:{mode:"faces",faces:{...},sizes:{...}}`。
- 新几何：add_cube/update_cube 支持 `inflate`、`rotation`、`pivot`；做圆角/倾斜的鳍、尾巴时优先用这三项，而不是堆大量小方块。
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

**默认用拼图工具，不要一上来就 `bb_render_views` 多图**（3 张 512² ≈552 token，
一张 2 格拼图只要 ≈211 token）。

- **编辑即看**：写操作（`bb_apply_model_patch` / `bb_texture_patch` / `bb_animation_*`）
  成功后会自动附一张 `front + iso_fr` 小拼图，**改完直接看图**，通常不需要再单独渲染。
- 想看更多角度：`bb_look({cells:[{view:"front"},{view:"iso_fr"},{view:"back"}]})`。
- 任意角度：`bb_look({camera:{azimuth:135, elevation:20, projection:"persp"}})`；
  先用 `bb_camera({get:true})` 看当前位姿，设置的相机会保持。
- **转台查穿模/对称**：`bb_orbit({steps:8, elevation:15})` —— 8 个角度一张图，每格带编号；
  背面对称性、裙摆穿腿、手臂穿身这类问题基本靠它发现。
- **动画检查**：`bb_anim_check({animation:"walk", samples:4})` —— 时间点采样成一张图，
  看幅度、起止姿势、有无穿模。
- **贴图精修**：`bb_render_texture({texture:"default", scale:12, region:[x1,y1,x2,y2]})`
  最近邻放大，核对 1-2 像素级的微小改动。
- 局部细节仍可用 `bb_render_views({views:["closeup"], focus:{element:"Head", padding:1.0}, antialias:"ssaa"})`
  （`padding` 越大视野越宽；closeup 触边时增大它）。
- 结果带 `changed_any` 与 `review`（watchdog-v2）：`verdict` 可能是 `visible_change` /
  `visible_change_clipped` / `no_visible_change` / `no_change_expected` / `empty_render`；
  `metrics` 有逐图 alpha/bbox/diff；`checks`/`suggestions` 给结构化建议。
  连续 3 次 no-visible-change 会触发 no-progress，先 `bb_restore` 或换策略。
- 画面触边（`edge_touch=true`）说明可能被裁切，用 `focus` 或缩小模型/调整机位。
- 判断：颜色/形状/位置是否与意图一致；如果 `changed_any=false` 或出现 `NO_VISIBLE_CHANGE`，
  先查 revision 是否增加、UV 是否真的指到涂色区域。
- 背景透明，不要用"背景色没变"判断失败；`EMPTY_RENDER` 表示整张图全透明，通常是相机/几何/GPU 问题。
  规则判定不是 VLM：造型/配色/意图仍要模型看图自己判断。

## 6. 保存/导出/回滚

- 检查点：`bb_checkpoint({label:"..."})` 会内嵌贴图当前像素，并在 arm tab 打开时快照 arm；列表 `bb_revisions`；回滚 `bb_restore({revision:n, confirm:true})`（会丢弃当前未保存改动，但贴图/arm 从快照恢复）。
- 保存时动画文件会“合并回写”：未修改的动画条目/顺序保留，只替换语义变化的动画，避免整文件重排/膨胀；hosttest 会验证。
- 全量回归：`npm run test`；快速回归（只 hosttest + 动画 diff）：`npm run test:quick`。
- 保存：`bb_save_project`（写回 pack：模型/动画/控制器/贴图/ysm.json）。
- 导出：`bb_export_ysm`（先 validate；产物含 export-manifest.json 与 zip；`zip:false` 可关闭 zip）。
- 批量只读/小操作可用 `bb_batch`；它不是事务，失败了不会自动回滚。

## 7. 用户接管

- 用户说“我来看看/手动改” → 提示输入 `/show`；窗口显示期间所有写操作会返回 `GUI_BUSY`。
- 用户改完输入 `/hide` 后会返回 `user_edits` 摘要；先 `bb_scene` 重新对账 revision，再继续。
- 不要自己调用 gui.show/hide 工具（默认未暴露）；用命令提示用户。

## 8. YSM 约束速查

> 硬约束与实测值必须分清。详见
> `F:\Deepseek_harness\blockbench\packages\dsh-blockbench-agent\reference\ysm-corpus-rules.md` §0。

- **骨骼数量：没有上限。** 默认模板是 64 bones / 172 cubes，但那是**模板自身的数量**，
  不是限制。语料实测 77% 的模型 >64 骨，中位 83，最高 451。
- **真正的限制是嵌套层数 ≤32**（YSM 2.6.3 起解除），以及网格子级 ≤64、纹理子级 ≤32。
- 贴图分辨率上限 **4096×4096**（2.2.2 起）；默认模板是 128，但社区 35% 用 512。
- 必需定位组：`Head`、`Body`、`RightArm`、`LeftArm`、`RightLeg`、`LeftLeg` 等；
  `bb_validate` 会报缺失。手/脚建议加 `RightHandLocator`/`LeftHandLocator`（社区 62% 有）。
- 动画文件路径由 ysm.json 决定（通常 `animations/main.animation.json`）；新建动画默认挂到 main。
- 改完模型/贴图记得保存，否则导出的是磁盘旧版本。
- 网格子级/纹理子级的上限由 `Cube.all.length`、`Texture.all.length` 决定，`bb_validate` 报错。
