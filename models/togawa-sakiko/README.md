# togawa-sakiko · 丰川祥子（明日方舟 × BanG Dream! Ave Mujica「旋律的主人」）

> 2026-11-07 全新建模验收模型。工作区即本目录（`workspaceRoot=models` + `project=togawa-sakiko`）。
> 已完成两轮验收：**首轮（217 块，T1 复检）→ T2 级逐细节修理（355 块）**。

## 规格（T2 修理后，2026-11-07 22:12）

| 项 | 值 |
|---|---|
| 角色 | 明日方舟联动干员 **丰川祥子**（官方罗马音 Togawa Sakiko，Ave Mujica / Oblivionis） |
| 皮肤 | **「旋律的主人」/ Master of Melodia**（Ave Mujica 合作服装；卡普里尼双大角、黑银演出服） |
| 骨架 | 70 bones（角/马尾骨重建后仍 70；双角链 `Horn_R/L_01..06`） |
| 方块 | **355 cubes**（首轮 217 → +138，+63.6%） |
| 贴图 | 2 × 512²（`textures/default.png`、`blue.png`；swatch 调色板式） |
| 动画 | 303（未触碰） |
| 校验 | `bb_validate` ok=true，**0 error**；3 warning（512 贴图 ×2、可选 ViewLocator 缺省） |
| 导出 | `exports/t2-repair/pack/`（32 文件 + manifest）、`pack.zip`（**489,046 B / 32 文件**） |

## 产物

- 工作副本：`pack/`（`ysm.json`、`models/main.json`、`models/arm.json`、`textures/`、`animations/`、`controller/`）
- 规格：`specs/丰川祥子_Togawa_Sakiko（Oblivionis）.json` / `.md`
- **T2 安装/分层报告**：[`T2-INSTALL-REPORT.md`](T2-INSTALL-REPORT.md)（29 层 + crop_head 23 层 + PSD + 权重 12.5GB）
- **T2 逐细节修理报告**：[`T2-REPAIR.md`](T2-REPAIR.md)（层对照表、P1–P5 明细、剩余差距）
- 首轮拆分/逐部件复检：[`SEG-CHECK.md`](SEG-CHECK.md)
- 最终渲染（768²）：`artifacts/renders/r0016/{front,back,left,iso_fr}_768.png`；**前后对比** `artifacts/t2-repair/before-after-sheet.png`（r0021 → r0016）
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

## 剩余差距（诚实）

1. 头发仍是"薄板 + 栅栏"感，未做到参考的连续波浪发流（最大剩余项）。
2. 背面拖尾 21 片之间有缝，读作"排骨"而非连续布面。
3. 裙蕾丝密度不足（2 层 vs 参考 4+ 层）。
4. 可见脸约 38% 头宽（目标下缘）；腿无小腿肚、手臂无肘收放/掌指。
5. 头身比 A 口径 6.21（语料中位 7.31）偏 Q；背面无官方参考，后发/拖尾形状属推断。
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
