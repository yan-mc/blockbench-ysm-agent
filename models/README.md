# 模型工程目录

> 这里是 BAE（Blockbench Agent Engine）的工作区根目录（`workspaceRoot`），
> 当前 `project=togawa-sakiko`（见 `packages/dsh-blockbench-agent/cordis.patch.yml`），
> 即工作区为 `models/togawa-sakiko/`。所有 `bb_project_open({pack_dir})` 的路径都**相对这个工作区**。

## 当前状态

**首轮验收模型 `togawa-sakiko` 已完成（2026-11-07，带已知降级项）。**

| 项 | 说明 |
|---|---|
| `togawa-sakiko/` | 明日方舟 × BanG Dream! Ave Mujica 联动干员 **丰川祥子（Togawa Sakiko）**，皮肤「旋律的主人 / Master of Melodia」，卡普里尼双大角 |
| 实测 | 70 bones / **217 cubes** / 2×512² 贴图 / 304 animations（模板 303 + 自定义 `sakiko_showcase`）；`bb_validate` ok=true、**0 error**（3 warning：512 贴图 ×2、可选 ViewLocator 缺省） |
| 产物 | `pack/`（YSM 工作副本）、`exports/<ts>/pack.zip`（32 文件 / 486KB）、`artifacts/renders/r0021/*_768.png`（front/back/left/iso）、`specs/丰川祥子_*.json/.md`、`checkpoints/r0019.bbmodel`、`SEG-CHECK.md`（立绘拆分+逐部件复检） |
| **复检结论** | 2026-11-07 T1 立绘拆分 + 8 组 isolate 复检：**major 5 / minor 4 / pass 0**。top 问题：角仅约参考 1/3、双马尾仅 4 块薄板、靴无形体、裙层/衬裙边/拖尾缺失、腹前灰框无对应物。详见 [`togawa-sakiko/SEG-CHECK.md`](togawa-sakiko/SEG-CHECK.md)；下一步 P1 角→P2 头发→P3 靴→P4 裙/拖尾→P5 胸衣 |
| 已知降级 | 角为 10 段折线（无罗纹）、裙/蕾丝/褶皱简化、头发卷曲不足、眼睛偏圆、背面为对称推断（无背面参考）、arm.json 与 blue.png 仍是模板 |
| 历史 `deepseek-fish/` | 已按要求删除；BUGS 记录保留到 [`../docs/archive/BUGS-deepseek-fish-testmodel.md`](../docs/archive/BUGS-deepseek-fish-testmodel.md) |
| 历史 `sakiko-melodia/` | 已在更早提交 `8f3a09f` 删除 |
| 参考语料 | 不在本目录，在 [`../material/refmodels/`](../material/refmodels/)（gitignored，仅本地） |

> 最新验收记录/证据见 [`../docs/test-evidence/`](../docs/test-evidence/README.md)；模型渲染见 `togawa-sakiko/artifacts/renders/r0021/`。

## 约定

1. **每个模型一个目录**：`models/<name>/`。
2. 用 `bb_session_start({mode:"new_ysm", name:"<name>", resolution:[512,512]})` 创建；
   `resolution` **必须显式指定**（默认 128 是模板遗留，做人物模型太小）。
3. 运行时产物（`.bb/`、`logs/`、`artifacts/`、`checkpoints/`、`exports/`）由 BAE 自愈生成、在 `.gitignore` 里；
   **可以清空内容，但不要删除目录本身**（`logs/` 被删曾导致宿主未捕获异常退出，v0.5.0 起会自愈重建）。
4. 参考语料不放本目录；需要参考时从 `../material/refmodels/` 读取/复制。
5. 模型目录可参考结构：`pack/`（YSM 工作副本）、`model-export/`（导出 zip）、`screenshots/`、`notes/`、`reference/`（参考图不提交）。

## 一个 YSM 工程的结构

```
my-character/
├── ysm.json
├── models/main.json         主模型
├── models/arm.json          第一人称手臂
├── textures/default.png     主贴图
├── animations/main.animation.json
└── controller/
```

## 参考

- 交接说明：[`../HANDOVER.md`](../HANDOVER.md)
- 建模方法（AI 技能）：[`../packages/dsh-blockbench-agent/skills/blockbench-ysm-artist.md`](../packages/dsh-blockbench-agent/skills/blockbench-ysm-artist.md)
- 语料实测规则：[`../packages/dsh-blockbench-agent/reference/ysm-corpus-rules.md`](../packages/dsh-blockbench-agent/reference/ysm-corpus-rules.md)
