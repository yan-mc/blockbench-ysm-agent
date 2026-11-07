# SETUP · 从仓库到可运行环境

> 目标：在一台干净的 Windows 机器上，从 clone 仓库开始，重建 `vendor/`、`dist/`，并把插件装进 DSH profile。
> 当前版本基线：**0.9.1** / Blockbench **5.2.2** / YSM-Utils-Plugins **2.6.0** / Node ≥ 20。

## 0. 前置

- Windows 10/11 x64
- **Node.js ≥ 20**：优先用 DSH 自带的 Node（无需全局安装）：
  `D:\deepseekharness\resources\runtime\primary-runtime\dependencies\node\bin\node.exe`
  如果系统有 `node`（≥20）也可以直接用；后文用 `node` 代指其一。
- **pnpm**（用于安装上游 Blockbench 依赖）
- **Python 3.10+**：仅用于生成 `spec/` 契约（`python spec/generate_spec.py`）
- 可选：Java 17 + Minecraft Java 1.20.1（仅游戏内加载验证需要；仓库不再自带 `game-test/`）

## 1. clone 仓库

```powershell
git clone https://github.com/yan-mc/blockbench-ysm-agent.git <仓库目录>
cd <仓库目录>
```

仓库**不包含** `vendor/`、`dist/`、`material/`、`release/`、`workspace/`（均在 `.gitignore` 中）。
本机实际布局可以已经有这些目录；没有时按下面步骤重建。

## 2. 重建 vendor（上游，只读）

### 2.1 Blockbench 5.2.2

```powershell
cd <repo>
git clone --depth 1 --branch v5.2.2 https://github.com/JannisX11/blockbench vendor/blockbench
cd vendor/blockbench
pnpm install --node-linker=hoisted
npm run build-electron
cd ../..
```

### 2.2 YSM-Utils-Plugins 2.6.0

```powershell
git clone --depth 1 --branch v2.6.0 https://github.com/YesSteveModel/YSM-Utils-Plugins vendor/YSM-Utils-Plugins
```

> BAE 只依赖其中的 `assets/default`（YSM 默认 CC0 模板），`assemble.mjs` 会把它复制进 `dist`。
> vendor 总体积约 1.54GB（重建后会有出入）。

## 3. 参考语料（可选，不影响运行）

`material/refmodels/` 是约 329.1MB 的本地参考语料（169 个解密 YSM 工程 / 9 包 / maid 446 条 / 62 对 bbmodel），
**因第三方版权不随仓库分发**。需要时从本机 MC 库用 `tools/ysmparser/YSMParser.exe` 解码：

```powershell
tools\ysmparser\YSMParser.exe -i <输入目录> -o material\refmodels\ysm_decoded
```

## 4. 组装 BAE（生成 dist）

```powershell
node packages/bb-agent-runtime/scripts/assemble.mjs
```

产物：`dist/bb-agent-app/`（含上游 Blockbench 构建产物、`agent/` 四件套、`@electron/remote`、`templates/ysm_default`、GPL `SOURCE.txt`）。
当前本机基线：**190 文件 / 36MB**，`templates/` 32 文件，`agent/` 4 文件 sha256 与源码一致。

> ⚠️ 若插件/BAE 正在运行，`dist/bb-agent-app` 被占用会 EPERM；先 `/bb-status` 确认/停 BAE 或禁插件再组装。

## 5. 快速验证（可选但推荐）

```powershell
node --test packages/dsh-blockbench-agent/test/*.test.mjs   # 62 项
node packages/dsh-blockbench-agent/test/host-smoke.mjs      # 35 步 / 41 工具 schema lint
python spec/generate_spec.py                                # 契约重生成，应 0 diff
```

`npm run test` 跑全量回归（会生成 M0/e2e/hosttest 产物到 `workspace/`）。

## 6. 安装 dsh Host 插件

### 6.1 确认配置

编辑 `packages/dsh-blockbench-agent/cordis.patch.yml` 的 `config`（本机默认已配好）：

```yaml
- insert:
    - id: blockbench-agent
      name: '@local/dsh-blockbench-agent'
      config:
        workspaceRoot: '<仓库目录>/models'                        # 模型根目录（按本机填）
        project: 'togawa-sakiko'                                  # 当前模型目录名
        autoStart: true
        executable: '<仓库目录>/vendor/blockbench/node_modules/electron/dist/electron.exe'
        appPath: '<仓库目录>/dist/bb-agent-app'
        pluginPath: '<仓库目录>/dist/bb-agent-app/agent/bb-agent-bridge.js'
        exposeGuiTools: false
        bridgeTransport: auto
```

> `workspaceRoot` + `project` 决定工作区 `<workspaceRoot>/<project>`；所有 `bb_project_open({pack_dir})` 都相对它。

### 6.2 安装 bundle（link 方式）

在 DSH 中执行：

```text
plugin_manager install_bundle target=<仓库目录>/packages/dsh-blockbench-agent
```

已安装过时先移除再装：

```text
plugin_manager remove_bundle target=@local/dsh-blockbench-agent
plugin_manager install_bundle target=<仓库目录>/packages/dsh-blockbench-agent
```

安装后插件行应显示 active。若改过 `dist` 需重启 BAE：`plugin_manager remove_bundle` → `install_bundle`，或先 `/bb-status` 停 BAE。

### 6.3 启动与验证

```text
/bb-status        # 或调用 bb_session_status；首次启动 BAE 可能需要数秒
/bb-start         # autoStart=false 时手动启动
/bb-help          # 列出工具
```

`gpu_ok: true` 表示离屏渲染可用。

## 7. 发布包（可选）

```powershell
node packages/bb-agent-runtime/scripts/package-release.mjs
```

产物在 `release/`（bundle 目录 + zip + SHA256SUMS + INSTALL.md）。
当前 **0.9.1 尚未重打**；GitHub Releases 上的 0.4.0 是历史发布。

## 8. 游戏内加载验证（可选，自备环境）

仓库已删除 `game-test/`。需要游戏内验证时，自备隔离的 Forge 1.20.1 + YSM 2.6.x 客户端：

1. 把 `bb_export_ysm` 产出的 `pack/` 复制到 `.minecraft/config/yes_steve_model/custom/<pack_name>/`
2. 启动客户端进入世界，执行 `/ysm model reload` 与 `/ysm model set @s <pack_name> default`
3. 日志出现 `[YSM] Set '<pack_name>' models for player` 即装载成功；再检查第三人称/第一人称渲染。
