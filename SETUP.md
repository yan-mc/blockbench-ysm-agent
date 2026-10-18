# SETUP · 从仓库到可运行环境

本仓库不含 `vendor/`、`dist/`、`workspace/`、`game-test/`、`release/`（均已 gitignore）。按下面步骤在本地重建。

## 0. 前置

- Windows 10/11 x64
- Node.js 20+（推荐 dsh 自带的 Node 或系统 Node 24）
- pnpm（用于安装上游 Blockbench 依赖）
- Python 3.10+（仅生成 `spec/` 契约与游戏内测试辅助）
- Java 17（仅游戏内加载验证需要）

## 1. 获取上游 Blockbench 5.2.2

```powershell
cd <repo>
git clone --depth 1 --branch v5.2.2 https://github.com/JannisX11/blockbench vendor/blockbench
cd vendor/blockbench
pnpm install --node-linker=hoisted
npm run build-electron
cd ../..
```

## 2. 组装 BAE

```powershell
node packages/bb-agent-runtime/scripts/assemble.mjs
```

产物：`dist/bb-agent-app/`（含上游构建产物、agent 三件套、`@electron/remote`、YSM 默认模板、GPL `SOURCE.txt`）。

## 3. 跑 M0 / e2e / 插件测试

```powershell
node packages/bb-agent-runtime/scripts/m0.mjs
node packages/bb-agent-runtime/scripts/m0.mjs --safe-mode
node packages/bb-agent-runtime/scripts/e2e.mjs
node packages/dsh-blockbench-agent/test/host-smoke.mjs
```

报告与结果在 `workspace/_m0*`、`workspace/_e2e`、`workspace/_hosttest`。

## 4. 安装 dsh Host 插件

1. 把 `packages/dsh-blockbench-agent` 放到固定目录（或直接使用仓库路径）；
2. 修改 `packages/dsh-blockbench-agent/cordis.patch.yml`：
   - `workspaceRoot`：工作区根目录
   - `executable`：`vendor/blockbench/node_modules/electron/dist/electron.exe`
   - `appPath`：本仓库 `dist/bb-agent-app` 绝对路径
   - `pluginPath`：`dist/bb-agent-app/agent/bb-agent-bridge.js`
3. 在 dsh 中安装 bundle：

```text
plugin_manager install_bundle target="<绝对路径>/packages/dsh-blockbench-agent"
```

4. 启用插件行后 `/bb-start`，再调用 `bb_session_start`。

## 5. 发布包

```powershell
node packages/bb-agent-runtime/scripts/package-release.mjs
```

产物在 `release/`（bundle 目录 + zip + SHA256SUMS + INSTALL.md）。

## 6. 游戏内加载验证（可选，独立环境）

首次下载 Forge 1.20.1 + YSM + Mojang assets 到 `game-test/`：

```powershell
powershell -File game-test/setup.ps1
powershell -File game-test/ingame.ps1
```

脚本把导出包安装到 `game-test/config/yes_steve_model/custom/live_gold3`，启动客户端进世界后执行 `/ysm model reload` 和 `/ysm model set`，截图在 `game-test/logs/`。
