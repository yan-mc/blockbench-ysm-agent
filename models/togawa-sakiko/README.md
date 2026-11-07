# togawa-sakiko · 丰川祥子（明日方舟 × BanG Dream! Ave Mujica「旋律的主人」）

> 2026-11-07 全新建模验收模型。工作区即本目录（`workspaceRoot=models` + `project=togawa-sakiko`）。

## 规格

| 项 | 值 |
|---|---|
| 角色 | 明日方舟联动干员 **丰川祥子**（官方罗马音 Togawa Sakiko，Ave Mujica / Oblivionis） |
| 皮肤 | **「旋律的主人」/ Master of Melodia**（Ave Mujica 合作服装；卡普里尼双大角、黑银演出服） |
| 骨架 | 70 bones（YSM 模板 70，新增双角链 `Horn_R_01..03` / `Horn_L_01..03`） |
| 方块 | **217 cubes** |
| 贴图 | 2 × 512²（`textures/default.png`、`blue.png`；swatch 调色板式） |
| 动画 | 304（模板 303 + 自定义 `sakiko_showcase` 2.4s loop：呼吸/发丝/裙摆/手臂微摆） |
| 校验 | `bb_validate` ok=true，**0 error**；3 warning（512 贴图 ×2、可选 ViewLocator 缺省） |
| 导出 | `exports/20261107113554/pack/`（32 文件 + manifest）、`pack.zip`（486,591 B） |

## 产物

- 工作副本：`pack/`（`ysm.json`、`models/main.json`、`models/arm.json`、`textures/`、`animations/`、`controller/`）
- 规格：`specs/丰川祥子_Togawa_Sakiko（Oblivionis）.json` / `.md`
- 渲染（768²）：`artifacts/renders/r0021/{front,back,left,iso_fr}_768.png`，四视图拼图 `sheet_4views.png`
- 参考图（不提交）：`refs/skin/sakiko_skin1.png`（官方立绘 2176²，Moegirl 原图）、`refs/skin/crop_*.png`、`refs/sakiko/ref_00*.png`
- 检查点：`checkpoints/r0019.bbmodel`（导出前终稿）、`r0001.bbmodel`（模板原样）

## 立绘拆分与逐部件复检（2026-11-07）

- `bb_seg_probe`：T1 可用（自动下载 SAM2.1 59.1MB）；T2 未装（ComfyUI 不可达，约 7GB，按规定未装）。
- `bb_seg_lite`：对官方立绘 + 3 张裁切图共拆出 **72 个部件 / 983 候选**；但对这张"暗色人物+暗色道具+亮背景"的稠密插画，
  人物本体的裙/手套/腿/靴/胸饰 **0 个被切出**（掩膜被钢琴/沙发/基座/留声机占据）→ 人工读 `crop_*` + bbox 辅助。
- 逐部件 8 组 isolate 检查全部完成，判定 **major 5 / minor 4 / pass 0**。
- 完整报告：[`SEG-CHECK.md`](SEG-CHECK.md)；隔离渲染与拆分覆盖图在 `artifacts/seg-check/`。

**top 问题与修复优先级**：

| 优先级 | 问题 | 目标 |
|---|---|---|
| P1 | 双角仅约参考 1/3，缺回卷/棱纹/金环 | 放大到 1.8–2×，强回勾 + 棱纹薄片 + 角尖金环 |
| P2 | 双马尾每条仅 4 块薄板、后发阶梯块 | 每束 2–3 层错位薄片、末端收尖、长度到臀下 |
| P3 | 靴与黑丝糊成一片，无靴筒/鞋跟/扣带 | 靴筒外扩 + 独立鞋跟 + 2 条扣带；与丝袜明度差 ≥3 级 |
| P4 | 裙层/白衬裙边缺失、拖尾仅 3 块 | 正面加 2 层蕾丝裙摆；白衬裙整圈；拖尾 9–12 块落地 |
| P5 | 腹前浅灰方框（参考无对应物） | 改深色或移除，换蓝缎带 + 银扣 |

## 已知降级（按严重程度）

1. 双角为每侧 10 段折线，脊棱仅明暗两色近似，无真实罗纹；前倾角按 3/4 立绘推断。
2. 裙装/蕾丝/荷叶层次大幅简化，裙摆略短、蓬松度不足。
3. 头发为等粗长条发束，卷曲与发流不足；刘海直板分撮。
4. 服装细节（蕾丝/星光丝袜/靴面装饰）未做或降级；胸饰为单块纯色板。
5. 眼睛比原画更圆更大；无背面参考，后发/裙后/拖尾为对称推断（见 `spec.gaps`）。
6. `arm.json` 第一人称手臂仍是模板几何；`blue.png` 第二套贴图未重绘；`ysm.json` authors 仍模板默认。

## 复现

```powershell
bb_session_status
bb_project_open({ pack_dir: "pack" })
bb_scene({ scope: "summary" })
bb_validate
bb_export_ysm({ zip: true })
```

> 方法论见 `packages/dsh-blockbench-agent/skills/blockbench-ysm-artist.md`；语料规则见 `reference/ysm-corpus-rules.md`。
