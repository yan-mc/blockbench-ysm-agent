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
