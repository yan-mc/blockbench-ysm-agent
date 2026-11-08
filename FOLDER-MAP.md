# 目录地图与维护约定

> 目标：源码、模型、测试、发布物、媒体素材各自独立；大目录不误提交。
> 现状基线：v0.9.4 / 2026-11-08（`docs/archive/` 为历史归档，不再使用 `_archive/`）。

## 顶层（当前真实布局）

| 路径 | 内容 | 是否提交 | 说明 |
|---|---|---|---|
| `README.md` | 仓库门面/快速链接 | ✅ | 封面 + 功能/架构/案例/快速开始（历史设计基线移到 `docs/archive/`） |
| `MANUAL.md` | 完整使用手册 | ✅ | 安装/命令/44 定义 / 42 暴露/工作流/排障（v0.9.4） |
| `HANDOVER.md` | 交接班档案（第一手） | ✅ | 接手先读这个 |
| `ENGINEERING.md` | 工程状态/实测数据/已知限制 | ✅ | 实现状态以此为准 |
| `FOLDER-MAP.md` | 目录地图与维护约定 | ✅ | 本文件 |
| `SETUP.md` | 从零搭建 | ✅ | vendor/dist 重建与插件安装 |
| `NOTICE.md` | 第三方许可 | ✅ | Blockbench GPL / YSM-Utils MIT / YSM 模板 CC0 |
| `系统开发与设计方案.md` | 历史设计合订本（2026-10-18） | ✅ | 只读设计意图，不随实现维护 |
| `docs/` | 设计文档 01–07/10–18/20/21* + `archive/` + `test-evidence/` + `assets/` | ✅ | 封面在 `docs/assets/`；归档在 `docs/archive/` |
| `spec/` | tool/bridge 契约 JSON + 生成器 | ✅ | 手工维护契约源；改后跑 `python spec/generate_spec.py`（应 0 diff） |
| `packages/` | BAE 运行时 + dsh Host 插件 + Skill + 协议骨架 | ✅ | 核心源码（改代码见 HANDOVER §3.3） |
| `models/` | BAE 工作区根（`workspaceRoot`） | ✅（运行时产物除外） | 当前案例：`togawa-sakiko`（72 骨 / 1182 块） |
| `material/` | 本地参考语料（约 329.1MB） | ❌（gitignored） | 第三方模型/贴图版权，仅本地研究，不随仓库分发 |
| `tools/` | 分析脚本 + `ysmparser` 解密器 + `extract_corpus.py` | ✅（二进制除外） | `tools/ysmparser/YSMParser.exe` 为本地二进制 |
| `research/` | Blockbench/YSM/dsh 研究 | ✅ | 事实依据（677/826/439 非空行） |
| `media/` | 介绍视频、幻灯片、构建脚本 | ✅（输出视频除外） | 视频输出在 `.gitignore` |
| `vendor/` | 上游 Blockbench 5.2.2 + YSM-Utils 2.6.0（只读） | ❌ | 体积约 1.54GB，按 SETUP 重建 |
| `dist/` | 组装后的 BAE（`bb-agent-app`） | ❌ | 由 `assemble.mjs` 生成（190 文件/36MB；agent 文件已同步 0.9.4） |
| `release/` | 发布 zip/目录 | ❌ | 由 `package-release.mjs` 生成；0.9.4 已生成（`bb-agent-0.9.4/` + zip） |
| `workspace/` | 测试脚本临时输出 | ❌ | 已清理；`npm run test` 会重新生成 |

> 已不存在：`prototype/`（早期骨架，已删除）、`game-test/`（隔离游戏验证环境，已删除）、`_archive/`（旧归档方案，已废弃）、`models/deepseek-fish/`（测试模型已清理）。

## 模型目录约定（`models/<name>/`）

> `workspaceRoot=models`，当前 `project=togawa-sakiko`（见 `packages/dsh-blockbench-agent/cordis.patch.yml`），
> 即工作区为 `models/togawa-sakiko/`。

```text
models/<name>/
├─ README.md          # 模型说明/设定/状态（可选）
├─ pack/              # YSM 工作副本（可重新打开）
├─ model-export/      # 可分发 zip
├─ screenshots/       # 渲染 + 游戏内截图
├─ notes/             # 迭代记录/辅助脚本
└─ reference/         # 参考图（版权原因不提交）
```

运行时目录（由 BAE 自愈生成，**可以清空内容，但不要删除目录本身**）：

```text
models/<name>/
├─ .bb/               # BAE userdata
├─ logs/              # runtime.log / agent.log
├─ artifacts/         # 渲染产物
└─ checkpoints/       # .bbmodel 检查点
```

> 历史教训：`logs/` 目录被删导致宿主未捕获异常退出；v0.5.0 起 spawn 前确保目录存在 + 监听 stream error + apply 时重建。

## 测试证据

- `docs/test-evidence/README.md`：0.9.4 证据说明（`test-all-0.9.4.log` / `hosttest-result-0.9.4.json` 由 Lead 写入）
- `docs/archive/test-evidence-0.4.0/`：0.4.0 时期旧证据（历史，不代表现状）
- `docs/archive/M0-report*.md`：2026-10 M0 报告

## 发布

- 本地 `release/` 只留最新 zip；解包目录不提交。
- 发布包内含 `INSTALL.md`、`SHA256SUMS.txt`、GPL `SOURCE.txt`。
- 当前 **0.9.4 发布包待重打**（`node packages/bb-agent-runtime/scripts/package-release.mjs`）；GitHub Releases 上的 0.4.0 为历史发布。

## 清理规则

- 不提交：`.bb/`、`checkpoints/`、`artifacts/`、`logs/`、`node_modules/`、`dist/`、`release/`、`vendor/`、`material/`、`workspace/`。
- 不提交：`__pycache__/`、`*.pyc`、参考图、临时截图、`*.log`（`docs/test-evidence/*.log` 例外）、本机绝对路径。
- 模型参考图、临时截图不进入提交。
- 每次大改后跑 `npm run test`，把最新证据放到 `docs/test-evidence/`。
- **归档一律放 `docs/archive/`（不再用 `_archive/`）**；归档文件不随现状维护，见 `docs/archive/README.md`。
