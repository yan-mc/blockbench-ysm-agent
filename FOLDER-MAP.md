# 目录地图与维护约定

> 目标：源码、模型、测试、发布物、媒体素材各自独立；大目录不误提交。

## 顶层

| 路径 | 内容 | 是否提交 | 说明 |
|---|---|---|---|
| `README.md` | 仓库门面/快速链接 | ✅ | 封面 + 工程状态 + 设计文档 |
| `MANUAL.md` | 完整使用手册 | ✅ | 安装/命令/30 工具/工作流/排障 |
| `ENGINEERING.md` | 工程状态/实测数据/已知限制 | ✅ | 设计不变，实现以此为准 |
| `系统开发与设计方案.md` | 合并版设计主文档 | ✅ | 不随实现频繁改 |
| `docs/` | 01–06 设计分章、test-evidence、assets | ✅ | 封面在 `docs/assets/` |
| `spec/` | tool/bridge 契约 JSON + 生成器 | ✅ | 改代码后跑 `python spec/generate_spec.py` |
| `packages/` | BAE + dsh Host 插件 + Skill | ✅ | 核心源码 |
| `models/` | 测试模型仓库 | ✅（reference 除外） | 每个模型一个目录 |
| `media/` | 介绍视频、幻灯片、构建脚本 | ✅（输出视频除外） | 视频输出在 `.gitignore` |
| `prototype/` | 早期骨架代码 | ✅ | 仅历史参考 |
| `research/` | Blockbench/YSM/dsh 研究 | ✅ | 事实依据 |
| `vendor/` | 上游 Blockbench/YSM（只读） | ❌ | 体积大，按 SETUP 重建 |
| `dist/` | 组装后的 BAE | ❌ | 由 `assemble.mjs` 生成 |
| `release/` | 发布 zip | ❌ | 由 `package-release.mjs` 生成 |
| `game-test/` | 隔离 Forge/YSM 测试环境 | ❌ | 需要时按 `game-test/` 脚本重建 |
| `workspace/` | 测试脚本的临时输出 | ❌ | `npm test` 会重建 |

## 模型目录约定（`models/<name>/`）

```text
models/deepseek-fish/
├─ README.md          # 模型说明/设定/状态
├─ BUGS.md            # 建模过程问题记录
├─ pack/              # YSM 工作副本（可重新打开）
├─ model-export/      # 可分发 zip
├─ screenshots/       # 渲染 + 游戏内截图
├─ notes/             # 迭代记录/辅助脚本
└─ reference/         # 参考图（版权原因不提交）
```

插件配置：`workspaceRoot=models`、`project=deepseek-fish` → 工作区 `models/deepseek-fish`。

## 测试证据

- `docs/test-evidence/test-all-final.log`：全量回归 6/6 PASSED
- `docs/test-evidence/hosttest-result.json`：Host 插件工具回归
- `docs/test-evidence/e2e-result.json`：WS/HTTP+SSE 协议回归
- `workspace/_logs/`：测试脚本临时输出（不提交）

## 发布

- GitHub Release 资产：`bb-agent-0.4.0-*.zip`
- 本地 `release/` 只留最新 zip；解包目录不提交
- 发布包内含 `INSTALL.md`、`SHA256SUMS.txt`、GPL `SOURCE.txt`

## 清理规则

- 不提交 `.bb/`、`checkpoints/`、`artifacts/`、`logs/`、`node_modules/`、`dist/`、`release/`、`game-test/`、`vendor/`。
- 模型参考图、临时截图、`*.log`、本机绝对路径不进入提交。
- 每次大改后跑 `npm run test`，把最新证据拷到 `docs/test-evidence/`。
