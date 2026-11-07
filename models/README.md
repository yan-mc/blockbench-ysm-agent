# 模型工程目录

> 这里是 BAE（Blockbench Agent Engine）的工作区根目录，
> 所有 `bb_project_open({pack_dir})` 的路径都**相对本目录**。

## 当前状态

**没有模型工程。** 之前的测试模型已按要求清理。

目录内容：

| 路径 | 说明 |
|---|---|
| `deepseek-fish/` | BAE 工作区（`bb_session_start` 默认建在这里），目前只有说明文档 |
| `README.md` | 本文件 |

## 约定

1. **每个模型一个目录**，例如 `deepseek-fish/my-character/`
2. 用 `bb_session_start({mode:"new_ysm", name:"my-character", resolution:[512,512]})` 创建
3. `resolution` **必须显式指定**，默认 128 是模板遗留，做人物模型太小
4. 运行时产物（`.bb/`、`artifacts/`、`checkpoints/`、`exports/`）都在 `.gitignore` 里，不进仓库
5. 参考语料不在本目录，在 `../material/refmodels/`

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

- 完整交接说明：`../HANDOVER.md`
- 建模方法（AI 技能）：`../packages/dsh-blockbench-agent/skills/blockbench-ysm-artist.md`
- 语料实测规则：`../packages/dsh-blockbench-agent/reference/ysm-corpus-rules.md`
