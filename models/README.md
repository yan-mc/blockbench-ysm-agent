# models · 测试模型仓库

| 模型 | 说明 | 工作区 | 状态 |
|---|---|---|---|
| `deepseek-fish/` | DeepSeek「鲸鱼娘 / 蓝色大肥鱼」YSM 模型：建模、贴图、渲染迭代、游戏内加载验证 | `models/deepseek-fish/` | v0.1 完成 |

约定：

- 插件配置 `workspaceRoot=models`、`project=<模型名>`，工作区即模型目录；每个模型一个目录。
- `pack/` 为 YSM 工作副本；`screenshots/` 放关键渲染与游戏内截图；`model-export/` 放可分发 zip；`BUGS.md` 记录问题。
- 旧 demo/证据在 `workspace/_archive/`；发布包在 `release/`（gitignored）。
