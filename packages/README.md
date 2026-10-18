# packages · 工程实现

> 本目录按 `docs/01-06` 的设计实现。设计文档保持原样；实现中的取舍与状态见 `../ENGINEERING.md`。

## 目录

| 包 | 作用 | 状态 |
|---|---|---|
| `bb-agent-runtime/` | BAE：隐藏 Blockbench Agent Runtime（Electron main/preload/bridge plugin/selftest/构建脚本） | M0 通过；YSM 项目创建/打开/保存/导出/动画/回滚可用 |
| `dsh-blockbench-agent/` | dsh Host 插件 bundle：28 个 `bb_*` 工具（默认暴露 26）+ 5 个命令 + Skill + 进程监管 + 图片缩略图 | host-smoke 通过；**已安装并激活** |
| `bb-protocol/` | 协议常量/错误码/共享类型（可选，当前 dsh 插件自包含 ws-server） | 骨架 |

## 常用命令（在仓库根目录执行）

```powershell
# 1) 组装 BAE（需要先完成 vendor/blockbench 的 pnpm install + build-electron）
node packages/bb-agent-runtime/scripts/assemble.mjs

# 2) M0：隐藏窗口 5 机位渲染 + 稳定性 + show/hide；产物在 workspace/_m0
node packages/bb-agent-runtime/scripts/m0.mjs
node packages/bb-agent-runtime/scripts/m0.mjs --safe-mode   # 无 GPU/SwiftShader

# 3) BAE <-> 协议端到端（创建 YSM 默认包→建模→贴图→渲染→保存→导出）
node packages/bb-agent-runtime/scripts/e2e.mjs

# 4) dsh Host 插件集成冒烟（mock ctx，真实 spawn BAE；不安装到 profile）
node packages/dsh-blockbench-agent/test/host-smoke.mjs

# 5) 发布包（BAE dist + 插件 + 文档 + SHA256 + zip）
node packages/bb-agent-runtime/scripts/package-release.mjs
```

本机没有全局 `node` 时，使用 dsh 自带运行时：

```powershell
$node = 'D:\dsh\resources\runtime\primary-runtime\dependencies\node\bin\node.exe'
& $node packages/bb-agent-runtime/scripts/m0.mjs
```

## 关键产物

- `dist/bb-agent-app/`：组装后的 BAE 应用目录（含 `agent/`、`templates/ysm_default`）。
- `workspace/_m0/artifacts/m0/`：M0 5 张机位 PNG + `m0-result.json` + `m0-verified.json`。
- `workspace/_e2e/`：e2e 的 pack、renders、exports、`e2e-result.json`。
- `workspace/_hosttest/`：Host 插件冒烟结果与真实 spawn 的 BAE 工作目录。
- `docs/M0-report.md`、`docs/M0-report-safe.md`：自动生成的 M0 报告。
- `release/bb-agent-<version>-<stamp>.zip`：可直接分发的发布包（0.2.0 为 207 文件 / 9.3MB；含 BAE、插件、文档、SHA256、GPL SOURCE）。
- `game-test/`：独立 Forge 1.20.1 + YSM 游戏内验证环境（首次 `setup.ps1`，之后 `ingame.ps1`；体积大，已 gitignore）。

## 实现边界（当前）

- WS（dsh 为 server）已实现；HTTP+SSE 回退未实现。
- YSM 默认包创建/打开/保存/导出已可用；main/arm 各自加载贴图；保存只从主项目写贴图，避免 arm 覆盖编辑。
- 工具面已补齐：动画 CRUD、贴图导入/导出、checkpoint/restore、batch、diagnostics、project_open/close；GUI 工具默认不暴露给模型（命令负责）。
- 写操作自动带 `expected_revision`；GUI 可见时返回 `GUI_BUSY`；编辑/渲染/restore 有预算。
- 进程崩溃自动重启（最多 5 次）；渲染附件默认 512px 缩略图。
- 渲染返回逐图 `changed`/`alpha_ratio`，并提供 `NO_VISIBLE_CHANGE`/`EMPTY_RENDER` 警告。
- 保存为增量写盘（未编辑动画/贴图不重写），二次保存幂等；导出同时生成目录与 zip。
- 仍未实现：PBR/图层、控制器绑定、HTTP+SSE、VLM critic 代码化、electron-builder 安装器。
- 已安装到当前 profile（`include:blockbench-agent`，autoStart=true）；卸载用 `plugin_manager remove_bundle`。
