# packages · 工程实现

> 本目录按 `docs/01-06` 的设计实现。设计文档保持原样（历史设计基线）；实现状态见 `../ENGINEERING.md`，交接信息见 `../HANDOVER.md`。
> 当前版本：**0.9.4**（根/插件/runtime 三个 package.json 均为 0.9.4）。

## 目录

| 包 | 作用 | 状态 |
|---|---|---|
| `bb-agent-runtime/` | BAE：隐藏 Blockbench Agent Runtime（Electron main/preload/bridge plugin/selftest/构建脚本） | 可用；bridge 实现 **56 个 JSON-RPC 方法 / 7 事件 / 22 错误码** |
| `dsh-blockbench-agent/` | dsh Host 插件 bundle：**44 个 `bb_*` 定义（42 个默认暴露）** + 5 个命令 + Skill + 双传输（WS/HTTP+SSE）+ 进程监管 + 图片缩略图 | host-smoke 35 步通过；**以 link 方式安装并激活** |

## 常用命令（在仓库根目录执行）

> `node` 不在 PATH 时用 DSH 自带：
> `$node = '<DSH 自带 node>'`

```powershell
# 1) 组装 BAE（需要先完成 vendor/blockbench 的 pnpm install + build-electron）
node packages/bb-agent-runtime/scripts/assemble.mjs

# 2) 单元测试：7 个 *.test.mjs，共 84 项
node --test packages/dsh-blockbench-agent/test/*.test.mjs

# 3) dsh Host 插件集成冒烟（mock ctx，真实 spawn BAE；35 步 / 42 工具 schema lint）
node packages/dsh-blockbench-agent/test/host-smoke.mjs

# 4) BAE <-> 协议端到端（创建 YSM 默认包→建模→贴图→渲染→保存→导出）
node packages/bb-agent-runtime/scripts/e2e.mjs

# 5) 视口反馈 e2e（bb_look / 拼图 / 转台 / 动画采样）
node packages/bb-agent-runtime/scripts/e2e-look.mjs

# 6) 契约重生成（手工维护契约源，重跑应 0 diff）
python spec/generate_spec.py

# 7) 全量回归（assemble → M0 → e2e WS → e2e HTTP+SSE → hosttest → 动画语义 diff）
npm run test
npm run test:quick        # 快速：hosttest + 动画语义 diff

# 8) 发布包（BAE dist + 插件 + 文档 + SHA256 + zip）
node packages/bb-agent-runtime/scripts/package-release.mjs
```

可用 npm scripts 共 **10 个**：`assemble`、`m0`、`m0:safe`、`e2e`、`hosttest`、`test`、`test:quick`、`release`、`verify:anim`、`spec`。

## 关键产物

- `dist/bb-agent-app/`：组装后的 BAE 应用目录（含 `agent/`、`templates/ysm_default`）。2026-11-07 基线：**190 文件 / 36MB**，`templates/` 32 文件，`agent/` 4 文件 sha256 与源码一致。
- `workspace/`：测试脚本临时输出（`npm run test` 时生成；当前已清理）。
- `docs/test-evidence/`：回归证据；0.4.0 旧证据在 `docs/archive/test-evidence-0.4.0/`。
- `release/`：发布包落点；**0.9.4 已生成**（`release/bb-agent-0.9.4-*.zip`）（0.4.0 为历史发布）。
- `models/<project>/`：BAE 工作区（当前 `project=togawa-sakiko`，无已完成测试模型）。

## 实现边界（当前）

- WS（dsh 为 server）与 HTTP+SSE 双传输已实现，共用 `/rpc`、`/events`；`--transport=auto|ws|http`。
- YSM 默认包创建/打开/保存/导出已可用；main/arm 各自加载贴图；保存只从主项目写贴图，避免 arm 覆盖编辑。
- 工具面：动画 CRUD/控制器绑定、贴图导入导出/图层/PBR、checkpoint/restore、batch、diagnostics、project_open/close、渲染自检（`bb_look`/`bb_camera`/`bb_orbit`/`bb_anim_check`）、参考图管线（`bb_ref_*`）、建模规格（`bb_spec_*`）、分层（`bb_seg_*`）。GUI 工具默认不暴露（命令负责）。
- 写操作自动带 `expected_revision`；GUI 可见时返回 `GUI_BUSY`；编辑/渲染/restore 有预算；渲染返回 watchdog `review`。
- 写操作自动附图（step 级合并）+ 图史压缩/附件预算护栏。
- 进程崩溃自动重启（最多 5 次）；渲染失败可自动切 safe-mode（SwiftShader）重试；渲染附件默认 512px 缩略图。
- 增量保存（未编辑动画/贴图不重写），二次保存幂等；导出目录 + zip。
- 测试：84 项单测（7 文件）+ host-smoke 35 步 + e2e + 动画语义 diff。
- 剩余：0.9.4 发布包已生成、electron-builder 安装器/签名（无证书，zip 为正式分发）、完整内置 VLM critic、PBR 预览、locale 加载验证、`arm.json` 重建。
- 已安装到当前 profile（`include:blockbench-agent`，autoStart=true，`workspaceRoot=models`、`project=togawa-sakiko`）；卸载用 `plugin_manager remove_bundle target=@local/dsh-blockbench-agent`。
