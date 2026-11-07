# togawa-sakiko · 丰川祥子（明日方舟 × BanG Dream! Ave Mujica「旋律的主人」）

> 2026-11-07 全新建模验收模型。工作区即本目录（`workspaceRoot=models` + `project=togawa-sakiko`）。
> 已完成两轮验收：**首轮（217 块，T1 复检）→ T2 级逐细节修理（355 块）**。

## 规格（T2 修理后，2026-11-07 22:12）

| 项 | 值 |
|---|---|
| 角色 | 明日方舟联动干员 **丰川祥子**（官方罗马音 Togawa Sakiko，Ave Mujica / Oblivionis） |
| 皮肤 | **「旋律的主人」/ Master of Melodia**（Ave Mujica 合作服装；卡普里尼双大角、黑银演出服） |
| 骨架 | 70 bones（角重建为 25 块/侧扁平螺旋带；双马尾/后发分组；眼睛菱形化） |
| 方块 | **401 cubes**（首轮 217 → T2 修理 355 → v2 优化 401） |
| 贴图 | 2 × 512²（`textures/default.png`、`blue.png`；swatch 调色板式） |
| 动画 | 303（未触碰） |
| 校验 | `bb_validate` ok=true，**0 error**；3 warning（512 贴图 ×2、可选 ViewLocator 缺省） |
| 导出 | `exports/v2-refine3/pack/`（32 文件 + manifest）、`pack.zip`（**489,547 B / 32 文件**） |

## 产物

- 工作副本：`pack/`（`ysm.json`、`models/main.json`、`models/arm.json`、`textures/`、`animations/`、`controller/`）
- 规格：`specs/丰川祥子_Togawa_Sakiko（Oblivionis）.json` / `.md`
- **T2 安装/分层报告**：[`T2-INSTALL-REPORT.md`](T2-INSTALL-REPORT.md)（29 层 + crop_head 23 层 + PSD + 权重 12.5GB）
- **T2 逐细节修理报告**：[`T2-REPAIR.md`](T2-REPAIR.md)（层对照表、P1–P5 明细、剩余差距）
- **v2 美术优化报告**：[`MODEL-V2-REFINE.md`](MODEL-V2-REFINE.md)（角参数表/2D 预检、头发分组、菱形眼、§10 最终状态）
- 首轮拆分/逐部件复检：[`SEG-CHECK.md`](SEG-CHECK.md)
- 最终渲染（768²）：`artifacts/renders/r0023/{front,back,left,iso_fr}_768.png`；**前后对比** `artifacts/t2-repair/before-after-sheet.png`（217 → 355）与 `docs/assets/showcase/sakiko-before-after.png`（217 → 401）
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

## v2 美术优化（2026-11-07，401 块）

- **双角**：从"散块/齿轮"改为**正面连续扁平螺旋带**——每侧 25 块（20 段带片 + 3 肋 + 金尖环 + 根环），只绕 Z 旋转（无欧拉序风险）；椭圆螺旋 C=(4.30,40.35)、rx 2.20→0.90 / ry 4.20→1.55、扫角 −330°、带面宽 1.90→0.75、z 厚 1.40→0.70（正面扁平、侧面有厚度）；根在 ±2.10（左右分离），外点 x=6.45 / 顶 y=45.16，均超头发包围盒。**先做 2D 预检叠图再上模型**（`artifacts/v2/horn_v22_precheck2.png`）。
- **背面长发**：每侧 4 组窄束（双马尾 TW1/TW2 + 背发 B1/B2），束宽 0.94–1.12、z 错落 2.2、末段收尖 30%、垂到 y=15.3；中央补缝组封背面竖缝；发色 7 档高度色带。
- **眼睛**：每眼 10 块——琥珀底板 + 2 层 45° 斜置菱形虹膜 + 菱形瞳孔 + 2 片斜高光 + 2 片斜眼睑/睫毛；虹膜挂 `EyesBase`（可随视线）、眼睑挂 `Eyelid`（可眨眼）。
- **穿插**：角根落在头顶 (±1.30, 40.60, 1.50)，高于侧发/刘海；缩矮头顶两撮呆毛让角根/金饰露出。

## 剩余差距（诚实）

1. 头发仍是"薄板/栅栏"感、背面发束偏直条（波浪/发流弱）——最大剩余项；刘海 27 块未大改。
2. 角已连续、但尖端偏钝、金环偏小（下一轮：末段缩到 0.25 宽 + 金环外扩 1.15× + 双段金）；角根为左右分离放在 ±2.1，比原画（≈±0.8，贴近额心金饰）偏外。
3. 背面拖尾 21 片之间有缝，读作"排骨"而非连续布面；裙蕾丝密度 2 层（参考 4+）。
4. 可见脸约 38% 头宽；腿无小腿肚、手臂无肘收放/掌指。
5. 头身比 A 口径约 6.5（语料中位 7.31）偏 Q；背面无官方参考，后发/拖尾形状属推断。
6. `arm.json` 与 `blue.png` 仍是模板。

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
