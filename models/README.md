# models · 测试模型仓库

| 模型 | 说明 | 工作区 | 状态 |
|---|---|---|---|
| `deepseek-fish/` | DeepSeek「鲸鱼娘 / 蓝色大肥鱼」YSM 模型：建模、贴图、渲染迭代、游戏内加载验证 | `models/deepseek-fish/` | v0.1 完成 |
| `deepseek-fish/sakiko-final/` | 「丰川祥子 · 月之森制服」：v0.5.0 视口反馈闭环下生成的成品模型（56 骨 / 196 方块，0 error） | 同上 | v1.0 完成 |

`sakiko-final/` 同时作为**视口实时反馈**（`bb_look` / `bb_orbit` / 编辑即看）的验收样例，
构建过程见其 [README](deepseek-fish/sakiko-final/README.md)。

约定：

- 插件配置 `workspaceRoot=models`、`project=<模型名>`，工作区即模型目录；每个模型一个目录。
- `pack/` 为 YSM 工作副本；`screenshots/` 放关键渲染与游戏内截图；`model-export/` 放可分发 zip；`BUGS.md` 记录问题。
- **运行时目录**（`logs/`、`artifacts/`、`checkpoints/`、`.bb/`）会被插件持续写入，
  可清空但不要删除目录本身。
- 旧 demo/证据在 `_archive/`；发布包在 `release/`（gitignored）。
