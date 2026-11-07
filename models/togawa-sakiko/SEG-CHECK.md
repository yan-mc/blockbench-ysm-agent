# 丰川祥子「旋律的主人」— 立绘拆分(T1) + 逐部件对照检查

- 项目：`models/togawa-sakiko/pack`（project_id `togawa_sakiko-505fe1e6`，revision **21**）
- 模型现状：**70 bones / 217 cubes / 2×512 贴图 / 304 动画**，包围盒 16.27 × 43.16 × 10.04
- 本轮性质：**只读检查**。未改任何骨骼/方块/贴图，未 save，未 git，未装 T2。
- 检查日期：2026-11-07

---

## 0. 摘要（TL;DR）

| 项 | 结果 |
|---|---|
| T1（SAM2.1 轻量分割） | ✅ 可用，首次自动下载 **59.1 MB** 模型并即用（CPU，~12–39 s/张） |
| T2（See-through 24 层） | ⛔ 未安装（合规）；探测显示可装但需 ~7 GB + 首次 ~3 GB 权重 |
| 拆分部件数 | 4 张图共 **72 个部件 / 983 个候选掩膜** |
| 拆分可用度 | ⚠️ **低**。掩膜被大件道具（钢琴、沙发、基座、留声机）与背景占据，人物的毛发/裙层/手套/靴**未被切出** |
| 逐部件对照覆盖 | **8 / 8 组** 全部完成 isolate 渲染对照 |
| 判定 | **major 5 项**、**minor 4 项** |
| 渲染消耗 | 本任务 **8 次**（会话 29 → 37 / 40，余 **3**） |

---

## 1. T1 / T2 能力状态

`bb_seg_probe` 输出摘要：

| 层级 | 状态 | 说明 |
|---|---|---|
| **T0** 零依赖 | ✅ ok | 直接看立绘判断部件（无分层） |
| **T1** 轻量分割 | ✅ ok（本次已就绪） | SAM2 ONNX ~59 MB，只给可见部件掩膜，遮挡处靠对称推断 |
| **T2** See-through | ✅ ok / 可装 | 24 层（body 13 + head 11）+ 深度序 + 遮挡补全 + PSD；估算 **7 GB**，推荐分辨率 1024 |

环境事实：

- GPU：NVIDIA GeForce RTX 4080 Laptop，**12282 MiB**，驱动 621.14（非旧架构）
- Python：`C:\Users\28988\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`
- onnxruntime：**1.31.1**（已就绪）
- SAM2 模型目录：`C:\Users\28988\.dsh-blockbench-agent\sam2`（`vision_encoder_int8.onnx` 等，首次 seg 时自动下载，**downloaded: true, 59.1 MB**）
- ComfyUI：`http://127.0.0.1:8188` **不可达**（`fetch failed`）→ 与「T2 未安装」一致
- 安装盘剩余：`C:\Users\28988\.dsh-seethrough` 可用 230.4 GB

> ⚠️ T2 只做探测记录，**未安装、未下载任何 T2 权重**（遵守硬约束）。

---

## 2. 官方立绘拆分结果

### 2.1 四张拆分任务

| 图 | 尺寸 | 部件数 | 候选数 | 耗时 | 输出目录 |
|---|---|---|---|---|---|
| `refs/skin/sakiko_skin1.png`（唯一官方立绘，坐姿 3/4） | 2176×2176 | 24 | 346 | 38.9 s | `seg/sakiko_skin1/` |
| `refs/skin/crop_head.png` | 780×640 | 16 | 245 | 26.5 s | `seg/crop_head/` |
| `refs/skin/crop_body.png` | 900×620 | 16 | 214 | 12.0 s | `seg/crop_body/` |
| `refs/skin/crop_legs.png` | 880×440 | 16 | 178 | 11.3 s | `seg/crop_legs/` |
| **合计** | — | **72** | **983** | 88.7 s | — |

覆盖图（每张最后一格是分块图）：

- `artifacts/seg-check/seg_sakiko_skin1_montage.png`
- `artifacts/seg-check/seg_crop_head_montage.png`
- `artifacts/seg-check/seg_crop_body_montage.png`
- `artifacts/seg-check/seg_crop_legs_montage.png`

### 2.2 部件清单与语义归类（依据 bbox / 质心 / 主色 / 覆盖图人工核对）

坐标均为归一化 `[x1,y1,x2,y2]`。**`color` 是掩膜内平均色，对被背景淹没的部件意义有限。**

#### A. 人物本体（可用的极少）

| # | 图 | bbox_norm | 面积% | 主色 | 语义 | 可信度 |
|---|---|---|---|---|---|---|
| 08 | crop_head | 0.301–0.538, 0.000–0.523 | 5.29 | `#b3bbe2` | **前发 / 刘海主体**（亮蓝发束） | 中 |
| 11 | crop_head | 0.258–0.527, 0.003–0.531 | 4.42 | `#bfcbf7` | **前发亮面** | 中 |
| 10 | crop_head | 0.809–1.000, 0.000–0.297 | 2.09 | `#ccddfc` | **右侧发梢**（iou 0.954，最干净） | 高 |
| 07 | crop_head | 0.137–0.340, 0.003–0.516 | 3.41 | `#7795b8` | **左侧发束（暗部）** | 中 |
| 12 | crop_head | 0.485–0.750, 0.161–0.706 | 3.68 | `#a5acd7` | **右侧双马尾上段** | 中 |
| 13 | crop_head | 0.332–0.597, 0.375–0.652 | 2.05 | `#8892d1` | **面部 / 侧发交界** | 低 |
| 04 | sakiko_skin1 | 0.114–0.887, 0.043–0.941 | 13.37 | `#3b4051` | 人物上半身+道具（**过度合并**） | 低 |
| 05 | sakiko_skin1 | 0.308–0.805, 0.543–0.965 | 6.38 | `#31364d` | 下半身（裙+腿+琴，**合并**） | 低 |
| 18 | crop_body | 0.219–0.626, 0.418–0.910 | 7.56 | `#2e303a` | 裙体（深色，**与背景混**） | 低 |

#### B. 道具（分割最成功的一类）

| # | 图 | bbox_norm | 面积% | 主色 | 语义 | 可信度 |
|---|---|---|---|---|---|---|
| 13 | sakiko_skin1 | 0.625–0.734, 0.234–0.394 | 1.04 | `#b4a19e`（铜） | **留声机铜喇叭**（iou 0.941） | 高 |
| 23 | sakiko_skin1 | 0.574–0.707, 0.043–0.336 | 0.79 | `#b0c9ef` | **右上五线谱/高音谱号蓝色缎带** | 高 |
| 22 | sakiko_skin1 | 0.324–0.418, 0.082–0.367 | 0.83 | `#6d8aae` | 左上**立式麦克风 / 灯架** | 中 |
| 11 | sakiko_skin1 | 0.094–0.258, 0.516–0.801 | 2.15 | `#5273ad` | 左下**蓝色鸢尾花丛** | 高 |
| 10/16/21 | sakiko_skin1 | 0.14–0.36, 0.40–0.58 | 2.01+1.24+0.88 | `#373a48` | **黑色沙发靠背**（3 块重复） | 高 |
| 12/15 | sakiko_skin1 | 0.48–0.83, 0.09–0.43 | 2.82+1.17 | `#303443` | 右上**钢琴形黑色背景板** | 高 |
| 14/17 | sakiko_skin1 | 0.41–0.81, 0.58–0.94 | 1.70+0.71 | `#70749a` | 右下**琴键 / 反光气泡** | 中 |
| 06/09/19 | sakiko_skin1 | 0.34–0.69, 0.58–0.99 | 4.35+2.15+0.90 | `#41404b`/`#1b1312` | **底座 / 舞台台沿** | 高 |
| 10 | crop_body | 0.699–0.977, 0.398–0.794 | 4.00 | `#696587` | 右侧**留声机小桌沿** | 高 |
| 00 | crop_legs | 全图 | **68.31** | `#2a2d3c` | **钢琴弧形底座**（吃掉整张图） | 高 |

#### C. 背景 / 底色

| # | 图 | 面积% | 判定 |
|---|---|---|---|
| 00/01 | sakiko_skin1 | 57.29 / 50.56 | 整图与地板基底（全幅 + iou 0.977） |
| 02/03 | sakiko_skin1 | 26.26 / 18.57 | 中央主体群 / 下半场背景 |
| 01–05 | crop_head | 22.69 / 14.98 / 8.42 / 13.22 / 8.00 | 右上、左上角背景 |
| 01/02/03/09/11/12 | crop_body | 42.61 / 17.29 / 36.66 / 9.39 / 9.28 / 6.97 | 背景与暗部合并块 |

#### D. 精致小件（参考价值高的「知识点」）

- **角**：`crop_head` **#15**（bbox 0.781–0.949, 0.234–0.406，1.49%，`#3c404b`，**iou 0.936**）→ 只切到**右侧角的一段**，说明角与头发、背景明度太近，整只角未被完整切出。
- **耳饰 / 发饰 / 胸饰**：**没有任何部件**被单独切出（面积 <1.5%，全部并入大块）。

### 2.3 拆分质量评估（本轮最重要的发现）

**❌ T1 在这张图上不可用于「逐部件」参考。**

1. **全图 24 个部件里，0 个对应「裙」「手套」「腿」「靴」「胸饰」。** 人物本体被合进 `#04`(13.4%) / `#05`(6.4%) / `#02`(26.3%) 三个巨块。
2. **最干净的分割全是道具**：铜喇叭（iou 0.941）、五线谱缎带、鸢尾花丛、沙发、底座。即 SAM2 把「面积大、边界清晰」的东西切对了，把「贴身、面积小、与邻接部位同色」的东西全漏了。
3. **crop_body / crop_legs 基本失效**：深色服装 + 暗背景，SAM 把**背景当主体**（crop_legs 里 68% 是钢琴底座，腿部仅约 3–5%）。
4. **crop_head 是唯一半可用的**：前发、两侧发梢、一段角可辨，但**脸 / 眼 / 嘴 / 胸饰完全没切出**。
5. 根因：官方立绘是「暗色人物 + 暗色大件道具（钢琴/沙发/基座）+ 大面积亮背景」的稠密插画，人物与道具明度接近；SAM2 自动网格采样在面积占比 <2% 的贴身部件上召回率不足。

**结论**：逐部件对照的「参考依据」**改为以人工阅读 `crop_face / crop_horn_hair / crop_body` + 全图为准，拆分 bbox 仅作位置/占位辅助**。要拿到可靠的分层参考只能上 T2（24 层）或人工描边。

---

## 3. 逐部件对照表

模型 isolate 图全部在 `artifacts/seg-check/` 下（每张 2 格：正面 + 侧/斜）。

| # | 部件 | 模型 isolate 检查图 | isolate 参数 | 参考依据 | 差异 | 判定 |
|---|---|---|---|---|---|---|
| 1 | **头 + 脸 + 眼** | `01_head_eyes.png` | `Head`，zoom 1.6 | `crop_face.png`（眼/脸）、全图 | 眼**琥珀金** ✅ 与参考一致（不是蓝色，勿误改）；睫毛/下眼睑层次 ✅。**脸偏窄偏小**，可见脸仅约 4×2.5 单位，参考为柔和鹅蛋脸；额头被发带压成一条亮灰横条 | **minor** |
| 2 | **前发 / 侧发** | `03_front_hair.png` | `front_h1,corner_h1`，zoom 1.9 | `crop_head` #08/#11/#07/#10（前发亮面/侧发束/发梢） | 刘海在**正中有一处明显缺口**（发缝过宽），参考为连续发帘仅有浅分缝；发片是**薄的直板**，尖端不够锐；侧发（corner_h1，8 块）是两根直柱，缺贴颊曲线；金色发饰（GoldOrnament）过小、不够突出 | **minor** |
| 3 | **后发 / 双马尾 / 蝴蝶结** | `04_backhair_tails_bow.png` | `hl_side,hl_m,Ribbon`，zoom 1.2 | 全图 + `crop_horn_hair`（双马尾到臀下）+ `crop_head` #12/#10 | **最严重之一**：双马尾每条仅 **4 个方块**（`hl_side` 共 8 块），呈**细直柱 / 单层薄板**，无体积、无波浪、末端不收尖；后发（`hl_m` 17 块）是 4 条 × 4 段的**阶梯状大块**，侧看像"装甲片"而非头发；发侧黑蝴蝶结（`Ribbon` 9 块）几乎看不见。参考中双马尾+后发是**画面第一体量**（>30%） | **major** |
| 4 | **双角** | `02_horns.png` | `Horn_R_01..03,Horn_L_01..03`，zoom 2.2 | 全图 + `crop_horn_hair` + `crop_head` #15（iou 0.936） | **最严重**：模型角约 2 单位，参考角约 **1×头宽 × 1×头高**（≈1/3 差距）；模型只有**轻微弯钩**，参考是**强烈外展下勾的公羊角（≈180–270° 回卷）**；模型通体一档深灰，参考有**棱纹分段 + 浅灰高光 + 角尖金色环扣**，且角根有一圈环状结构 | **major** |
| 5 | **躯干 + 胸饰** | `05_torso_chest.png` | `UpperBody`，zoom 1.25 | `crop_horn_hair`（胸衣/黑蝴蝶结/青色宝石/蓝缎带）+ `crop_face`（颈饰） | 领口**白色内衬** ✅、喉间**青色小宝石** ✅ 方向正确；但**腹前一块大而平的浅灰方框**（`FrillPanel` + `CorsetStay2/3`）在参考中**无对应物**，是全模型最突兀的"错误物件"；胸口黑蝴蝶结 + 青色宝石**过小**，参考是明显的一整朵；腰间**蓝色缎带**（参考明显下垂）几乎不可见；胸/腰起伏被压平 | **major** |
| 6 | **手臂 + 手套** | `06_arms_gloves.png` | 6 根臂骨，zoom 1.5 | `crop_face` / `crop_horn_hair`（腕部黑褶边、短手套） | 手臂是**直而细的方柱**（约 2 单位），无肘部收放、无手套轮廓；腕部是**一整块亮白粗块**（应为**黑色蕾丝褶边**，参考几乎无白）；手是单个小方块，无掌心/手指区分 | **minor** |
| 7 | **裙 + 衬裙 + 拖尾** | `07_skirt_petti_train.png` | `Skirt`，zoom 1.15 | `crop_horn_hair`（多层重蕾丝裙）+ 全图（落地长拖尾） | 裙体偏小偏薄（像短盒），**正面裙摆几乎没有蕾丝层次**；**白色衬裙边只在侧后露出碎片**，参考是沿裙摆整圈露白；**拖尾仅 3 个方块**（`TrainL/C/R`），isolate 中几乎看不到长度，参考是**落地长拖尾 + 五线谱纹**；腰部蝴蝶结（`SashKnot`）被吞掉 | **major** |
| 8 | **腿 + 靴** | `08_legs_boots.png` | 6 根腿骨，zoom 1.5 | 全图（chunky 短靴 + 扣带 + 靴跟）、`crop_body` | 腿**过细过直**（每腿 1+1 块大腿/小腿），无大腿-膝-小腿肚的起伏；**靴子与黑丝完全糊在一起**（同为近黑），只剩**两颗小灰扣**和一个白鞋底；参考靴子有**靴筒、鞋跟、2 条扣带、靴口皮边**，与半透黑丝有明确明度差 | **major** |

### 判定统计

- **major 5**：双角、后发/双马尾、裙/衬裙/拖尾、腿/靴、躯干腹前灰框
- **minor 4**：头/脸（脸偏窄、额前灰条）、前发（中央缺口、薄板）、手臂/手套（白腕块、臂过细）、（+）发色与头身比
- **pass 0**（没有一组达到"无需修改"）

### 补充观察（跨组）

| 项 | 观察 | 判定 |
|---|---|---|
| 贴图色板 | `default` 512²：`#d6dcf2 / #b8c5e8 / #93a4cf / #7384b0` = 标准 **4 级 periwinkle 蓝**，加 `#e2b04a / #8f6a1e` 金、`#17151c / #262230 / #332f3a` 黑 —— **色板本身正确** | pass |
| 渲染发色偏灰 | 4 视图与 isolate 里头发显灰，是**平光渲染 + 最亮档 `#d6dcf2` 面积过大**导致，不是调色错误 | minor（渲染/明度层次） |
| 头身比 | 总高 43.16 / 头高 ≈ 7 → **≈6.2 头身**；参考约 7 头身，模型偏 Q | minor |
| 贴图预算 | 2×512 = 524k texel / 217 方块 ≈ **2400 texel/块**，远超 p90(358) | pass（富余） |
| 参考覆盖缺口 | **只有 1 张官方立绘且为坐姿 3/4，无背面/正侧面**；后发、拖尾、背部结构只能按常识推断 | 验收固有盲区 |

---

## 4. 结论

### 4.1 模型相对参考的 top 问题（按严重度）

1. **双角严重偏小且缺少回卷与棱纹** — 这是"旋律的主人"最强的剪影识别点，现在读起来像两个小突起。
2. **双马尾/后发是薄板 + 阶梯块，体量不足** — 参考里头发是第一体量，模型里它比躯干还"轻"。
3. **靴子没有形体、与黑丝糊成一片** — 下半身丢失全部结构，脚部只剩两颗扣子。
4. **裙层与白色衬裙边缺失、拖尾只有 3 块** — 参考的"重蕾丝 + 落地拖尾"是整个造型的重心。
5. **腹前浅灰方框** — 一个参考中不存在的高亮平构件，正面视线正中，最容易被看出"不像"。

### 4.2 如果继续修，优先级 top 5

| 优先级 | 动作 | 目标 | 预期收益 |
|---|---|---|---|
| **P1** | 双角：整体放大到 ~1.8–2×；每侧 3 段改为强回勾（外展→下卷→前勾）；每段加 1–2 片棱纹薄片（浅灰高光）；角尖加 1 片金色环 | 剪影辨识度 | ⭐⭐⭐⭐⭐ |
| **P2** | 双马尾/后发：每束改 2–3 层错位薄片（厚度 1.0→0.5 分层），末端加波浪与收尖；长度延到臀下；侧发贴颊内收 1–1.5 单位 | 头发体量回到 30%+ | ⭐⭐⭐⭐⭐ |
| **P3** | 靴：靴筒外扩 + 独立鞋跟 + 2 条扣带 + 靴口皮边；把靴与黑丝拉开 ≥3 级明度差（靴偏亮皮革、丝偏深） | 下半身可读性 | ⭐⭐⭐⭐ |
| **P4** | 裙/拖尾：正面加 2 层蕾丝裙摆；白衬裙边沿裙摆整圈露出；`TrainL/C/R` 从 3 块扩到 9–12 块薄片并真正落地 | 造型重心 | ⭐⭐⭐⭐ |
| **P5** | 胸衣正面：`FrillPanel`/`CorsetStay2/3` 改深色或移除，换成蓝色缎带 + 银色小扣；胸口黑蝴蝶结放大 1.5× | 去掉最突兀的错误物件 | ⭐⭐⭐ |

> 修完 P1–P2 再验收，性价比最高：这两项占了剪影识别度的大头。

### 4.3 给下一轮的技术建议

- `bb_look({isolate:...})` **会连带显示子骨骼**（isolate `Head` 会带出头发和角），所以查"纯面部"要用叶骨列表，别用父骨。
- 本轮 isolate 全部用 **2 格**（正面 + 侧/斜）+ `zoom 1.15–2.2`，一图就能判形体，比 `bb_render_views` 三视图省一半预算。
- 立绘是暗色人物时，**T1 不可依赖**；下次若要分层参考，直接从 `crop_*` 手工描边比跑 SAM2 快。

---

## 5. 预算与产物清单

### 5.1 预算

| 资源 | 起始 | 本轮消耗 | 结束 |
|---|---|---|---|
| 渲染（`bb_look`） | 29 / 40 | **8** | **37 / 40**（余 3） |
| 写操作（模型 edits） | 20 / 60 | **0**（只读检查） | 20 / 60 |
| `bb_seg_lite` 调用 | 0 | 4 | — |
| T1 模型下载 | — | 1 次（59.1 MB） | 已缓存 |
| T2 下载/安装 | — | **0**（禁止） | 未装 |

> 本任务**没有**产生任何模型/贴图/动画写入，`bb_save_project` 未调用，pack 内容与 revision 21 一致。

### 5.2 产物

隔离检查渲染（8 张，均 2 格拼图）：

```
F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\seg-check\01_head_eyes.png
F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\seg-check\02_horns.png
F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\seg-check\03_front_hair.png
F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\seg-check\04_backhair_tails_bow.png
F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\seg-check\05_torso_chest.png
F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\seg-check\06_arms_gloves.png
F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\seg-check\07_skirt_petti_train.png
F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\seg-check\08_legs_boots.png
```

T1 拆分覆盖图（4 张，最后一格为分块图）：

```
F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\seg-check\seg_sakiko_skin1_montage.png
F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\seg-check\seg_crop_head_montage.png
F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\seg-check\seg_crop_body_montage.png
F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\seg-check\seg_crop_legs_montage.png
```

原始拆分产物（引擎输出，含每个部件的单件掩膜 `*_partNN.png`）：

```
F:\Deepseek_harness\blockbench\models\togawa-sakiko\seg\sakiko_skin1\
F:\Deepseek_harness\blockbench\models\togawa-sakiko\seg\crop_head\
F:\Deepseek_harness\blockbench\models\togawa-sakiko\seg\crop_body\
F:\Deepseek_harness\blockbench\models\togawa-sakiko\seg\crop_legs\
```

既有整身基准图（复用，未消耗渲染）：`artifacts/renders/r0021/sheet_4views.png`（1024²，front/back/left/iso）

### 5.3 本次未做 / 失败项

| 项 | 状态 | 下一步 |
|---|---|---|
| T2 分层（24 层 + 遮挡补全） | **未做**（硬约束：ComfyUI 未装、~3 GB 权重禁止下载） | 若必须做分层验收：装 ComfyUI 便携版（1.8 GB）+ See-through 节点（2 GB）+ 首次权重（3 GB），并先启动 `http://127.0.0.1:8188` |
| 背面参考 | **缺失**（官方只有 1 张坐姿 3/4 立绘） | 后发/拖尾/背饰的差异判定只能标"合理推测"，建议补 1 张背视同人图或设定集 |
| 贴图级差异（蕾丝、刺绣、透明纱） | **未逐像素核对**（本轮只看渲染形体） | 需要时用 `bb_render_texture({scale:8})` 对 `default`/`blue` 局部放大 |
