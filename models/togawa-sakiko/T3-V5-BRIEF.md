# v5 修整任务书：按 T3 拆解图重做服装/下肢（Phase 1）

> 参考图（**唯一造型依据**）：
> - T3 turnaround：`artifacts/t3-sheets/run2-turnaround/丰川祥子（旋律的主人）_2026-11-07T19-16-29_v1.jpg`
> - T3 breakdown：`artifacts/t3-sheets/run2-breakdown/丰川祥子（旋律的主人）_2026-11-07T19-17-12_v1.jpg`
> - 官方原图：`refs/丰川祥子/arknights-pick/ref_000.png`
> - 对照图：`artifacts/refstudy/t3-vs-current.png`（左 T3 / 右当前模型）
> - 头部细节裁切：`artifacts/refstudy/t3-head-detail.png`（角/刘海/额头饰品/黑丝带/耳环/颈饰）
> - 服装细节裁切：`artifacts/refstudy/t3-clothing-detail.png`（corset/泡泡袖/手套/裙层/吊袜带/靴子三视图+鞋底）
>
> 当前工程：`bb_project_open({pack_dir:"pack"})`，68 骨 / 534 块，已 v4.4 保存。
> 目标：Phase 1 后服装与腿/靴到位，整体从"简版长裙"变为 T3 的**短款层叠哥特裙 + 泡泡袖 + 长手套 + 厚底靴 + 星空披风**。

## Phase 1 范围（只做这些；头发/角/脸留 Phase 2）

### 1. 裙装（最高优先）
- 短款：**黑层主裙至大腿中部**（不是拖到脚踝的长裙）；侧面/后面略长（bustle/train），前面略短。
- 三层：黑外裙（荷叶边/分片，波浪下摆）→ 蓝灰中层 → **浅蓝/白衬裙**（露 1–2 单位，带蕾丝边）。
- 裙摆要有体积：前后左右都外扩，侧视不能是薄片；用 20–40 片斜置/交错的裙片 + 波浪下摆。
- 保留骨骼 `Skirt / FrontSkirt / BackSkirt / LeftSkirt / RightSkirt`（动画引用），只换方块；可新增 `SkirtLayer2/3` 等骨（≤4 个），但要挂 `Skirt` 下。
- 腰部：黑 corset 收腰 + **蓝色交叉绑带** + 腰侧蓝缎带/蝴蝶结；胸口蓝缎带蝴蝶结 + 蕾丝领口。

### 2. 腿/袜/靴
- 大腿/小腿：黑丝袜（大腿有暗纹/接缝线），**左大腿 garter + 蓝色宝石 + 细链**（T3 breakdown D3）；右腿简洁。
- 靴：**厚底平台短靴**（蓝灰星空面板 + 黑鞋面 + 交叉鞋带 + 厚黑底 + 鞋底纹），从脚踝到小腿中下；左右分开、可看清鞋底/鞋跟。
- 当前腿只有 1 块/段、脚 15 块；需要重建为有体积的大腿/膝/小腿/靴筒/鞋底。

### 3. 上装与手臂
- 收腰 corset 胸衣：黑色、蓝交叉绑带、胸下/腰线清晰；领口 off-shoulder 蕾丝边。
- **泡泡短袖**（肩部独立，off-shoulder，带蕾丝边）+ **黑长手套**（前臂/手，带蕾丝袖口）。
- 手套/袖口要与手部有明度台阶，不要黑成一片。

### 4. 披风（可做简版，Phase 2 精修）
- 背部/肩后挂**半透明星空披风**（T3 breakdown B4）：深蓝黑、稀疏星点、下摆到膝/小腿；先做薄片/斜片，纹理可用 alpha 或深色+星点；如果 alpha 渲染异常，改用很暗的深蓝+星点，不要放弃。
- 新增 1–2 根骨（如 `Cape`/`CapeSide_L/R`）挂 `UpperBody`/`AllBody`，不要改现有动画。

## 硬约束
- **不得删除/改名现有骨骼**（动画引用 303 条）；可新增 ≤8 根骨。
- 脸/眼/眉/角/头发 Phase 1 不动（可微调位置给领口让位）。
- 方块总数控制在 **≤ 1050**；体素尺度 1.0–1.5，不要碎成小片（眼睛/蕾丝边除外 0.3–0.6）。
- 颜色：黑 `#17151c/#262230/#332f3a`，蓝 `#2c4ea9/#3f6bb5/#6f9ad0`，浅蓝 `#cfe0f5/#e4eefb`，银 `#cfd6e6`；沿用现有 swatch 行，新增行不要和发色行混用。
- 每步 `bb_apply_model_patch` 小步，改完立刻 `bb_render_views({views:["front","left","back","iso_fr"],size:[1200,1200]})` 或 `bb_look` 检查；**每轮至少 3 次 front/back/side 对照 T3**。
- 先 `bb_checkpoint({label:"before-v5-phase1"})` 再开始；结束 `bb_validate` 0 error、`bb_save_project`。
- 只在 Phase 1 完成后报告；中间不要导出。

## 验收（Lead 会看）
1. front/side/back 轮廓：短层叠裙、泡泡袖、长手套、厚底靴、星空披风可辨认；侧视有裙摆体积。
2. 裙摆三层颜色/层次可辨；蓝缎带、胸口蝴蝶结、corset 绑带在正面可见。
3. 腿部：丝袜/garter/链/靴分开，不再是一根黑柱。
4. 0 error；方块数/骨骼数报告；渲染 2400² 四视图 + 头部/裙/靴特写。
