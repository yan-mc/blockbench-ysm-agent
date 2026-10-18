# prototype · 设计参考骨架

> 状态：**协议/传输层已在本机 Node 24 上通过冒烟测试；Electron/Blockbench 侧代码仅做语法检查，未在目标环境端到端运行。**
> 这些文件用于把 `docs/01-06` 的接口/机制落成可读代码，**不是可直接发布的成品**；接入真实项目时按 `research/*.md` 的"未验证清单"逐项确认。

## 文件

```
prototype/
├─ dsh-plugin/                      # dsh Host 插件（bundle）
│  ├─ index.js                      # apply(ctx, config)：启动 BAE、注册工具/命令
│  ├─ ws-server.js                  # 零依赖 WebSocket JSON-RPC server（含 server→client request）
│  ├─ ws-smoke-test.mjs             # 冒烟测试（已通过）
│  ├─ package.json                  # dsh.bundle.patch / exports / files / peerDeps
│  ├─ cordis.patch.yml              # insert 插件行（autoStart 默认 false）
│  ├─ locale/{en,zh}.json           # Plugin Manager 展示元数据
│  └─ icon.svg
└─ blockbench-agent/                # BAE（Blockbench Agent Runtime）
   ├─ agent/main.js                 # 隐藏窗口、userData、插件注入、网络拦截、close→hide
   ├─ agent/preload.cjs             # 注入 window.__BB_AGENT__ 配置
   ├─ agent/bb-agent-bridge.js      # Blockbench 插件：WS client + JSON-RPC dispatch + 最小编辑/渲染
   ├─ build.mjs                     # 上游构建 + 目录组装 + GPL 合规文件
   └─ package.json
```

## 已实现（骨架级）

- **传输**：WebSocket 握手、首包 token 鉴权、server→client 请求/响应、client→server 请求、事件通知、超时、错误码。`ws-smoke-test.mjs` 覆盖坏 token、hello、双向请求、事件、并发、未知方法。
- **DBA**：`defineTool` 注册 6 个工具（status/scene/model patch/texture patch/render/validate）、`/show` `/hide` `/bb-status` 命令、进程 spawn/cleanup、渲染 PNG → `ctx.attachments.saveImage` → `ImageBlock`。
- **BABP**：WS 连接/重连/心跳；创建项目、读场景、模型 patch（add/update/delete）、像素绘制（pixel/rect/line/shade/replace/clear/copy_mirror）、多机位离屏渲染、贴图放大、最小校验、最小保存。
- **BAE main**：`show:false` + `backgroundThrottling:false`、独立 userData、外部网络拦截、等待 `Blockbench.setup_successful` 后注入 bridge、close→hide、renderer 崩溃退出码。

## 未实现 / 需要真实环境验证

- 完整 YSM 骨架（64 bones/172 cubes）与 `ysm.json` 规范化/导出（`TODO(YRL)`）。
- 动画/控制器编辑与导出、PBR 贴图、lang/avatar/sounds 复制。
- 渲染的 zoom-to-fit、SSAA、closeup、空图检测、GPU 降级。
- GUI `/show` 后用户编辑检测与 revision resync。
- BAE 打包（electron-builder）与真实 GPU/驱动验证。
- 本骨架未安装到当前 profile、未修改任何 profile 配置。

## 快速验证

```powershell
# 0) 本机可用 Node（dsh 自带，无需安装）：
#    $node = 'D:\dsh\resources\runtime\primary-runtime\dependencies\node\bin\node.exe'
#    或者：$env:ELECTRON_RUN_AS_NODE='1'; & 'D:\dsh\DeepSeek Harness.exe' <script>

# 1) 传输层冒烟
cd F:\Deepseek_harness\blockbench\prototype\dsh-plugin
& $node ws-smoke-test.mjs
# 期望：ALL SMOKE TESTS PASSED

# 2) 语法检查
& $node --check ws-server.js
& $node --check index.js
& $node --check ..\blockbench-agent\agent\bb-agent-bridge.js
& $node --check ..\blockbench-agent\agent\main.js

# 3) 真实运行（需先完成 docs/06 的 M0/M1）
#    - 构建 BAE：& $node ..\blockbench-agent\build.mjs
#    - 在 dsh 中安装本 bundle（plugin_manager install_bundle），config 指向 executable/appPath
#    - 调用 bb_session_status 验证连接
```

## 如何扩展

1. 按 `spec/tool-manifest.json` 为每个工具补齐 `parameters`/`output`，在 `dsh-plugin/index.js` 注册。
2. 在 `bb-agent-bridge.js` 增加对应 handler（命名与 `spec/bridge-methods.json` 一致）。
3. 渲染/保存路径统一走 `workspacePath()`，不要硬编码根目录。
4. 任何写操作必须包在 `Undo.initEdit/finishEdit` 内，并在成功后 `bump()` revision。
5. YRL 逻辑按 `research/ysm-format.md §8.4` 的 12 条最小清单实现。
