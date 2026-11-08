# togawa-sakiko · 丰川祥子（明日方舟 × BanG Dream! Ave Mujica「旋律的主人」）

> 2026-11-07 全新建模验收模型。工作区即本目录（`workspaceRoot=models` + `project=togawa-sakiko`）。
> 已完成八轮：**首轮 217 块 → T2 修理 355 → v2 401 → v3 510（角/眼/发）→ v4 534（眼睛）→ v5 1100（按 T3 重建服装/头发/角）→ v6 1117（三轴斜板裙）→ v7 1182（裙对齐斜面锥 + 头发全覆盖平滑化）**。

## 规格（v7 成品，2026-11-08）

| 项 | 值 |
|---|---|
| 角色 | 明日方舟联动干员 **丰川祥子**（官方罗马音 Togawa Sakiko，Ave Mujica / Oblivionis） |
| 皮肤 | **「旋律的主人」/ Master of Melodia**（Ave Mujica 合作服装；卡普里尼双大角、黑银演出服） |
| 骨架 | **72 bones**（v3 68 + v5 新增 Cape / CapeLow / HairBow_R + v7 新增 HairCap；原骨名全保留，303 动画引用不变） |
| 方块 | **1182 cubes**（217 → 355 → 401 → 510 → 534 → 1100 → 1117 → **1182**） |
| 贴图 | 2 × 512²（`textures/default.png`、`blue.png`；swatch 调色板式） |
| 动画 | 303（未触碰） |
| 校验 | `bb_validate` ok=true，**0 error**；3 warning（512 贴图 ×2、可选 ViewLocator 缺省） |
| 导出 | `exports/v7-final-clean/pack/`（32 条目 + manifest）、`pack.zip`（**516,768 B / 32 条目**） |

## 产物

- 工作副本：`pack/`（`ysm.json`、`models/main.json`、`models/arm.json`、`textures/`、`animations/`、`controller/`）
- 规格：`specs/丰川祥子_Togawa_Sakiko（Oblivionis）.json` / `.md`
- **T2 安装/分层报告**：[`T2-INSTALL-REPORT.md`](T2-INSTALL-REPORT.md)（29 层 + crop_head 23 层 + PSD + 权重 12.5GB）
- **T2 逐细节修理报告**：[`T2-REPAIR.md`](T2-REPAIR.md)（层对照表、P1–P5 明细、剩余差距）
- **v2 美术优化报告**：[`MODEL-V2-REFINE.md`](MODEL-V2-REFINE.md)（角参数表/2D 预检、头发分组、菱形眼、§10 最终状态）
- **v3 结构重建报告**：[`MODEL-V3-REFINE.md`](MODEL-V3-REFINE.md)（角绕 X 轴螺旋、眼睛 6 层配方、头发底发帽+附属束；§9 v3.1 / §10 v3.2 / §11 v3.3）
- **参考模型实证分析**：[`../../docs/23-眼睛头发与角实证分析.md`](../../docs/23-眼睛头发与角实证分析.md)（逐个打开 8 个参考模型后的眼睛/头发/角配方）
- **v5 T3 参考与重建（历史）**：[`V5-FINAL-REPORT.md`](V5-FINAL-REPORT.md)、[`T3-V5-BRIEF.md`](T3-V5-BRIEF.md)、[`T3-V5-BRIEF-PHASE2.md`](T3-V5-BRIEF-PHASE2.md)、[`V5-PHASE1-REPORT.md`](V5-PHASE1-REPORT.md)、[`V5-R3-REPORT.md`](V5-R3-REPORT.md)、[`V5-R4-REPORT.md`](V5-R4-REPORT.md)；重建/校对脚本 `tools/v5*/`
- **v6 曲面裙层（历史）**：[`V6-CURVED-SKIRT-REPORT.md`](V6-CURVED-SKIRT-REPORT.md)；重建脚本 `tools/v6*/`；对照图 `docs/assets/showcase/sakiko-v5-vs-v6-skirt.png`、`sakiko-t3-vs-v6.png`
- **v7 裙对齐/斜面锥 + 头发全覆盖**：[`V7-FINAL-REPORT.md`](V7-FINAL-REPORT.md)；对照图 `docs/assets/showcase/sakiko-t3-vs-v7.png`、`sakiko-hair-coverage-v7.png`、`sakiko-skirt-detail-v7.png`、`sakiko-v6-vs-v7-skirt.png`
- **T3 参考图**（gitignored）：`artifacts/t3-sheets/run2-turnaround/`、`run2-breakdown/`（APIYI / Nano Banana Pro）
- 首轮拆分/逐部件复检：[`SEG-CHECK.md`](SEG-CHECK.md)
- 最终渲染（2400²）：`artifacts/v7/final/final-{front,iso_fr,back,left}-2400.png` + 特写；**对照** `docs/assets/showcase/sakiko-t3-vs-v7.png`、`sakiko-hair-coverage-v7.png`、`sakiko-skirt-detail-v7.png`、`sakiko-v6-vs-v7-skirt.png`、`sakiko-final-4views.png`、`sakiko-t3-crop-proof.png`
- 参考研究裁切（gitignored）：`artifacts/refstudy/`（doggo/kaltsis/ganyu/jingliu 等参考渲染 + 官方角 5× 裁切）
- T2 分层产物（gitignored）：`seg/sakiko_skin1-layers/`（29 层 + depth + layers.json + PSD）、`seg/crop_head-layers/`（23 层 + PSD）
- 参考图（不提交）：`refs/skin/sakiko_skin1.png`（官方立绘 2176²）、`refs/skin/crop_*.png`、`refs/sakiko/ref_00*.png`
- 检查点：`checkpoints/r0016.bbmodel`（T2 修理终稿）、`r0001/r0009/r0012`

## 立绘拆分：T1 → T2（2026-11-07）

- **T1（SAM2）**：72 部件 / 983 候选，但对这张"暗色人物 + 暗色大件道具 + 亮背景"的稠密插画失效（裙/手套/腿/靴/胸饰 0 个切出）→ 改人工裁切判读。
- **T2（See-through，已完整安装）**：官方立绘 832²/28 步 → **29 个语义层**（back hair / front hair / headwear / face / eyes 系 / topwear / bottomwear / handwear / legwear / footwear / neckwear / objects 等）+ 深度序 + 遮挡补全；`objects`(19.98%) 是钢琴/背景，不建模。
- T2 有效提供「语义归属 + 形状 + 遮挡序」，但**面积比例不可用**（人物在原图占比小）→ 比例改用官方裁切图人工判读。

## T2 修理结果（SEG-CHECK 5 个 major 全部落地）

| 项 | 首轮（217 块） | T2 修理后 |
|---|---|---|
| 双角 | 约参考 1/3，无回卷 | **7.00×7.76 单位/只**（1.00 头宽×1.11 头高），6 棱环 + 金尖/金根环，42 块 |
| 头发/马尾 | 每条 4 块薄板、后发阶梯块 | 双马尾每侧 3 层错位薄片垂到 y=17.2（40 块）；刘海 27 块；后发分组 |
| 裙/衬裙/拖尾 | 裙层缺失、拖尾 3 块 | 裙组 79 块：白衬裙整圈 11 块 + 蕾丝 16 片 + **21 片落地拖尾**（y=2.6） |
| 腿/靴 | 靴与黑丝糊死 | 靴筒 y12.66 + 金口沿 + 2 扣带 + 鞋底/鞋尖/鞋跟（15 块/只），黑丝-皮革差 4 档 |
| 胸衣 | 腹前浅灰平板无对应物 | 对照 T2 确认参考确有浅色胸衣面板 → **改形**（压暗 + 4 骨架线 + 黑边）；胸结放大 1.5×、加蓝缎带 |

## v2 美术优化（2026-11-07，401 块 · 历史）

- **双角**：从"散块/齿轮"改为正面连续扁平螺旋带（每侧 25 块、只绕 Z 旋转、椭圆螺旋 rx 2.20→0.90 / ry 4.20→1.55、扫角 −330°）；**事后判定旋转轴画错**（见 v3）。
- **背面长发**：每侧 4 组窄束（双马尾 TW1/TW2 + 背发 B1/B2）、末段收尖、垂到 y=15.3。
- **眼睛**：每眼 10 块菱形叠层（"金菱形宝石"，凸出脸 0.34–0.62）——**v3 已推翻重做**。
- 详细数据见 [`MODEL-V2-REFINE.md`](MODEL-V2-REFINE.md)。

## v3 结构重建（2026-11-08，510 块）

依据 [`docs/23`](../../docs/23-眼睛头发与角实证分析.md) 的参考模型配方（逐个打开 doggo / zhe_2 / ak_kaltsis / yujin / 甘雨 / 镜流 等参考工程判读）：

- **角（旋转轴改为左右轴 X）**：删 6 个旧角骨 → `Horn_L/Horn_R` 各 26 段近立方参数化螺旋（轴 ±X、L=4.60、θ=150°+470°t ≈1.3 圈、ry 2.45→1.05、rz 2.05→0.85、**rotation 全 0**、每 3 段棱纹、金尖环/根环）。z 跨度 0.85 → **3.14**，90° 侧视是完整椭圆圈（"弹簧"），不再是竖片。
- **眼睛（按参考 6 层配方重做，每眼 16 块）**：平眼白板 2.05×1.55×0.30 齐脸（凸 0.03）→ 外金环 1.65×1.55 → 内深金环 1.05×1.02 → 深棕竖瞳 0.48×0.62（居中）→ 2 白高光 → 上眼线 1.85×0.24（凸 0.11）＋外/内眼角＋下睑＋3 片肤色角遮片＋3 段深灰紫眉。**不再凸出 0.34–0.62，也不再是纯方板**。
- **头发（底发帽 + 附属束分层）**：底发帽 28 小板替换 2 块 8.2×8.7 大平板；刘海两层 48（中分斜扫、2 段折角、8 根三角收尖）；侧发 HairSide_L/R；后发 HairBack 43（5 束×7 段 + 内层填充，垂到 y≈13）；双马尾 TwinTail_L/R 24（前移到耳后）；发饰 23。头发 **198 块 / 占 39%**；任意角度无露皮。
- 发色 swatch 重画为浅紫灰（#cbc7e2/#b3aed3/#918cb8/#6c6893）。

## v4 眼睛精修（2026-11-08，534 块）

依据 [`docs/23 §6`](../../docs/23-眼睛头发与角实证分析.md)（追加：眼睛间距 + 眼角小方块实测）：

- **眼距修正**：眼中心 **±2.315 → ±1.76**（脸宽 7；双眼内缘间距 2.58→**1.52 ≈22% 脸宽**，与现代模板 zhe_2/kaltsis/yujin/shazhi 的 ±1.76/20–24% 一致；旧派 doggo 是 ±2.12/41%）。RightEyelid/RightEyesBase/RightPupil 等 8 根眼/眉骨 pivot x 同步移，动画未动。
- **平板眼白 + 小方块叠层 + 四角勾勒**：眼白 1.95×1.42 齐脸（front −3.53）；金环 1.55×1.35（−3.55）→ 深金内环 1.00×0.95（−3.57）→ 竖瞳 0.48×0.62（−3.59）→ 2 白高光（−3.61）；上眼线弧 + 外眼角改 **2 片深色 lash 翼（0.30 rot−24° / 0.25 rot−42°）**；内眼角、下睑；**四角 6 片小块（0.24–0.30，相邻 rot 差 18°，沿眼弧排列，z=−3.56）** 把方形四角切成弧形；眼角片 uv 用 **脸皮同色格心 (144,16)#f8eaea**（原 (128,0) 被发色 swatch 重画污染成淡紫）；眼白 2.0×1.5→1.95×1.42。
- **迭代**：v4（移眼距 + 22 块/眼）→ v4.1（虹膜缩小 + 四角片移到虹膜前）→ v4.2（修淡紫 swatch、上外角改深色翼、四角缩小）→ v4.3（四角拆 6 片沿弧 + lash 翼拆 2 片 + 脸皮同色）→ v4.4（删 8 块冗余压边，净 534 块）。
- **已知未解**：isolate `RightEyesBase` 时眼心仍有一块约 0.4×0.4 的淡色块（挡住了竖瞳下半）。实测用"把 default 贴图对应区域涂洋红"验证该处**确实采样 default 纹理**（涂后变洋红），但改方块 `uv` 两次均无变化 → 怀疑是**极小面 box-UV 采样/混合**问题，当前 `bb_*` 未暴露 per-cube texture/UV 逐面控制，暂记为已知问题（正常 768 全身视距下约 1–2px，不影响整体观感）。

## v5 按 T3 拆解图重建（2026-11-08，1100 块 · 历史）

T3（Nano Banana Pro / Gemini 3 Pro Image，经 APIYI 中转）用官方立绘 + 局部裁切 + Q 版小人共 5 张参考图，生成两版 2K 参考（$0.1415/张，约 40s）：
- `turnaround`：严格正/侧/背三视图 + 头部/上半身/下半身/手/脚单独图 + 服装/配饰单品拆解；
- `breakdown`：全展开部件设定板（角/冠/发饰/眼/颈饰/上衣/裙/披风/手/腿/靴/鞋底逐项编号）。

据此做四轮重建：
1. **服装/下肢**：三层短裙（黑外裙 + 饱和蓝条纹荷叶边 + 浅蓝衬裙窄边）、corset 蓝交叉绑带 + 胸口蓝蝴蝶结、off-shoulder 泡泡袖 + 腕部手套、黑丝袜 + 左腿 garter/银十字扣/细链、蓝灰厚底平台短靴（X 鞋带/气眼/鞋底）、腰后星点半透明披风。
2. **头发/角/头部**：HairBack 55→150 块 5 层波浪、双马尾/黑蝴蝶结发带、43 段/只粗卷角 + 棱环、额头金饰+蓝宝石、蓝宝石耳环、蕾丝 choker + 蓝钻金链。
3. **成品化精修**：裙层花瓣/蓝荷叶、后发覆盖条、额头饰品缩小、耳环外移、角棱环高光、靴子细节。
4. **裁切错误修正（R5/R6）**：发现 T3 对照图面板裁切错误后，用正确独立面板重查——移除三视图中不存在的星空披风、后发加宽 33 块、背面蓝层改黑、后裙补 9 片钟形裙片；最终 **1100 块**。
5. **交付**：`bb_validate` 0 error、303 动画未动、`exports/v5-final2/` + zip **511,459 B**。

## v6 曲面裙层：三轴斜置薄板（2026-11-08，1117 块 · 历史）

v5-r6 的裙 165 块全部只绕 Y（竖片环/圆筒）。按 skill §3.6 对 160 个参考工程统计（85.4% 方块带旋转、裙类 93.3%、5,275 块三轴裙板），重做三轮：
1. **v6**：裙 165 → 233 块三轴斜板，可见斜面；特写仍漏光/碎片多。
2. **v6.1**：去前中蓝插片、peplum 收窄、后摆加长；特写仍散刺。
3. **v6.2**：**182 块三轴斜板** + 32 片内层黑壳 + 30 片蓝壳堵缝（切向重叠 1.24–1.38）；裙 182/182 三轴（100%）、板厚中位 0.30；总 71 骨 / 1117 块 / 303 动画未动；validate 0 error。
- 五裙骨保留：`Skirt 12 / FrontSkirt 56 / BackSkirt 56 / LeftSkirt 29 / RightSkirt 29`。
- 导出 `exports/v6-final/pack.zip`（513,051 B）。

## v7 裙体对齐 + 斜面截断锥 + 头发全覆盖（2026-11-08，1182 块）

针对用户反馈的三类问题：
1. **裙歪/连接错位**：查出 v6.2 生成器 `origin=pivot−R·loc` 把旋转乘了两次（设计中心偏 1.87u），且左/右裙扇区骨分配反；v7a/v7c 改为世界坐标重建、按方位重分五骨，裙中心 x=-0.15、顶环 y≈23.6 贴胯，透明背景无偏。
2. **斜面截断圆锥**：前下摆 y≈15.4、后 y≈12.4（差 3.0u），侧≈14.0；连续黑内壳 36 片挡腿，蓝衬裙 + 白细边连续；腰封/内衬衔接上身。
3. **头发全覆盖/平滑**：新增 `HairCap` 骨（实心叠层穹顶 + 内填充），顶视无孔/无白块；后发 9 缕×8 段、侧发 3 缕/侧、刘海 12 缕（去针刺），相邻段重叠 0.2–0.3、旋转差 5–12°；顶/侧/背覆盖射线 0 孔。
- 最终 72 骨 / 1182 块 / 303 动画 / validate 0 error；导出 `exports/v7-final-clean/pack.zip`（516,768 B）。

## 剩余差距（诚实）

1. **角**：43 段近立方块仍有"块状/正面钩形"感（T3 是粗圆卷角）；已加棱环，但近看仍能看出分段。
2. **后发/侧发**：v7 已全覆盖、无露头皮；但远看仍偏片状/叠瓦，不如 T3 的连续大波浪；发帽顶为实心叠层（稳定性优先），不是蓬松细发。
3. **披风**：星空披风已可见，但纯侧视只剩薄边、背面会遮裙后幅；alpha 0.72 在浅色背景下略暗。
4. **裙**：v6.2 已改为三轴斜置薄板 + 内壳，漏光消除；但黑摆比 T3 少两层明显荷叶/peplum、蓝白条纹偏宽块、裙摆前后等长（T3 前短后长），侧/背裙宽仍略大。
5. **耳环**受侧发厚度限制，只能挂发外略浮；**额头金饰**已缩小但仍比 T3 略大。
6. 头身比 A 口径约 6.9–7.0 偏 Q；无官方背面参考，T3 背面/内侧属推断（已写 spec.gaps）。
7. `arm.json` 与 `blue.png` 仍是模板。

## 复现

```powershell
bb_session_status
bb_project_open({ pack_dir: "pack" })
bb_scene({ scope: "summary" })
bb_validate
bb_export_ysm({ zip: true })
```

**T2 环境**：ComfyUI 0.44.0 已装（`~/.dsh-seethrough`，权重 12.5GB 已缓存）；重启用
`models/togawa-sakiko/artifacts/start-comfyui.ps1`，健康检查用 `check-comfyui.ps1`。

> 方法论见 `packages/dsh-blockbench-agent/skills/blockbench-ysm-artist.md`；T2 用法见 `docs/16`。
