# ENGINEERING · 工程进展与验收

> 设计基线（历史设计意图）：见 [系统开发与设计方案.md](系统开发与设计方案.md) 与 `docs/01-06`。
> 本文件只记录**实现状态、实测数据、已知边界与下一步**；交接第一手信息见 [HANDOVER.md](HANDOVER.md)。
>
> 当前版本：**0.9.3**（2026-11-08 复核，新增 T3 云端拆解）。

## 0. 2026-11-08 复核（0.9.3）

| 项 | 结果 |
|---|---|
| 单元测试 | **62/62 通过**（6 个 `*.test.mjs`：imageprune 13 / refcanon 9 / segprobe 10 / spec 17 / tool-schema 5 / viewsheet 8） |
| host-smoke | **35 步全过**；schema lint 检查 **42 个暴露工具**（本地实跑 2026-11-08；产物 `workspace/_hosttest/` 已清理，复跑命令见 §4） |
| 契约重生成 | `python spec/generate_spec.py` 重跑后与提交内容 **0 diff**（契约是**手工维护**的源，不是从 `index.js` 生成；与 `index.js` 存在 17 个工具参数漂移，以 `index.js` 实际 schema 为准） |
| dist 组装 | `dist/bb-agent-app` 于 2026-11-07 由 `assemble.mjs` 从 vendor Blockbench 5.2.2 + 当前源码重新组装：**190 文件 / 36MB**，`templates/` 32 文件；`agent/` 4 个文件（main.js、preload.cjs、bb-agent-bridge.js、selftest.js）sha256 与源码一致 |
| 版本 | 根 `package.json`、`packages/dsh-blockbench-agent/package.json`、`packages/bb-agent-runtime/package.json` 均为 **0.9.3**；bridge 握手与 `/bb-agent/status` 版本号均为 0.9.3 |
| 工具规模 | `index.js` 定义 **44 个 `bb_*`**，因 `exposeGuiTools:false` 实际暴露 **42 个**（`bb_show_gui`/`bb_hide_gui` 由 `/show` `/hide` 命令替代）；5 个命令、1 个 Skill |
| 协议 | `spec/bridge-methods.json` = **56 方法 / 7 事件 / 22 错误码** |
| 参考语料 | `material/` 约 **329.1MB**；`ysm_decoded` **169 目录 / 1156 文件 / 233MB**；`ysm` 9 包；`maid` 874 文件 / 446 条（325 角色）；`bbmodel` 62 对 |
| 上游 | `vendor/blockbench` = **Blockbench 5.2.2**（不是 3.7.5）；`vendor/YSM-Utils-Plugins` = 2.6.0 MIT；vendor 总体积约 **1.54GB** |

## 1. 当前结论

**DSH 端已完整可用（v0.9.3）：插件以 link 方式安装并激活；44 个工具定义 / 42 个实际暴露、5 个命令、1 个 Skill；56 个 bridge 方法；T3 云端拆解（Nano Banana Pro）+ T2/T1 分层；渲染自检（isolate+zoom、多格拼图、转台、动画采样）、参考图管线、建模规格、T0/T1/T2 分层、YSM 创建/保存/导出、检查点/回滚、Client UI 状态 pill 全部就位；76/76 单测与 35 步 host-smoke 通过。**

- **M0 通过（Go，历史闸门）**：隐藏窗口离屏 WebGL 渲染稳定；GPU（RTX 4080 / ANGLE D3D11）与 SwiftShader 两条路径都通过；show/hide 往返后仍可渲染。报告已归档：[docs/archive/M0-report.md](docs/archive/M0-report.md)、[docs/archive/M0-report-safe.md](docs/archive/M0-report-safe.md)。
- **BAE 可用**：`dist/bb-agent-app` 由上游 Blockbench 5.2.2 构建产物 + agent 四件套 + YSM 默认模板组装而成（2026-11-07 重新 assemble；见 §0）。
- **协议可用**：WebSocket JSON-RPC 2.0 与 HTTP+SSE 双传输（dsh 为 server、BBAR 为 client），首包 token 鉴权、双向请求、事件、超时、断线重连均实现；变更加 `expected_revision` 前置校验。
- **YSM 可用**：默认包创建/打开（main+arm、2 贴图、303 动画、8 控制器）、显式保存（16 个文件）、导出（32 个文件 + manifest）、YSM 校验、贴图/动画/检查点/回滚。
- **dsh 插件已安装并激活**：entry `include:blockbench-agent`（`@local/dsh-blockbench-agent`），`autoStart:true`；**42 个暴露工具**（44 定义，GUI 2 个由命令接管）、**5 个命令**、**1 个 Skill**（`blockbench-ysm-artist`）、进程崩溃自动重启、GUI 抢占冻结、512px 附件缩略图。
- **真实闭环已验证（历史）**：AI 通过工具创建 YSM 项目 → 加方块 → 精确 UV → 像素涂色 → 无头渲染 → 看图确认金色王冠 → 保存 → 导出。
- **渲染自检（0.5–0.9）**：`bb_look`（多格拼图 + `isolate` 局部审查 + `zoom`）、`bb_camera`、`bb_orbit`、`bb_anim_check`、图史压缩与附件预算；`focus.padding` 缺陷已修，局部审查推荐 `isolate`+`zoom`。
- **参考语料**：`material/refmodels/ysm_decoded` 已由 Lead 修正为 **169 条**（`inventory_ysm.json`）；`inventory_parts.json` 仍为 161 条历史派生统计。

## 2. 实测证据

### 2.1 M0 渲染（历史，2026-10）

| 指标 | GPU（RTX 4080 Laptop / ANGLE D3D11） | safe-mode（SwiftShader） |
|---|---|---|
| 默认 YSM 模型加载 | ~400ms（64 bones / 172 cubes） | ~360ms |
| 5 机位渲染 | 62–72ms | 83ms |
| 单帧 50 次 | p50 4ms / p95 5ms | p50 9ms / p95 11ms |
| show→hide→再渲染 | ✅（513ms） | ✅（630ms） |
| 输出 | 768×768 PNG，透明背景，非空 | 同左 |

报告：[docs/archive/M0-report.md](docs/archive/M0-report.md)、[docs/archive/M0-report-safe.md](docs/archive/M0-report-safe.md)。
原图片目录 `workspace/_m0/`、`workspace/_m0-safe/` 已在 2026-11-07 清理（见 [docs/archive/cleanup-2026-11-07.md](docs/archive/cleanup-2026-11-07.md)）。

### 2.2 自动化测试（0.9.1 复核）

| 测试 | 命令 | 结果 |
|---|---|---|
| 单元测试 6 个文件 | `node --test packages/dsh-blockbench-agent/test/*.test.mjs` | ✅ **62/62** |
| dsh Host 插件全工具（mock ctx + 真实 spawn BAE + 图片附件 + 命令） | `node packages/dsh-blockbench-agent/test/host-smoke.mjs` | ✅ **35 步全过**，schema lint 42 工具 |
| 契约重生成 | `python spec/generate_spec.py` | ✅ 0 diff（与提交内容一致） |
| 全量回归（assemble → M0 → e2e WS → e2e HTTP+SSE → hosttest → 动画语义 diff） | `npm run test` | 0.4.0 时期 6/6 PASSED（历史）；0.9.1 全量回归由 Lead 复跑，证据落 `docs/test-evidence/` |

0.4.0 时期的历史证据（e2e-result / hosttest-result / test-all-final.log 等）已归档到 [docs/archive/test-evidence-0.4.0/](docs/archive/test-evidence-0.4.0/)。

### 2.3 0.5–0.9 渲染反馈实测（RTX 4080 / 默认 YSM 模型，历史数据）

| 指标 | 实测 |
|---|---|
| `render.preview` 640² 单帧 | 渲染 p50 **4.5–6.4 ms**；端到端 40–60 ms（含 PNG 编码 + base64） |
| `render.sheet` 2 格 320² | 9–24 ms，**211 token** |
| `render.sheet` 8 格转台 1280×640 | 12–25 ms，**514 token** |
| 自动附图（front+iso，320²） | **11–13 ms**，211 token |
| `render.texture_sheet` 2 块放大 | 1.7–3.6 ms |
| 动画采样 4 帧 | 17–25 ms |

> 这些数字来自 0.5.0 时期实机，作为量级参考仍有效；工具已随 0.9.1 演进。

### 2.4 游戏内加载验证（历史，独立环境）

0.4.0 时期曾在仓库内独立安装 Forge 1.20.1 + YSM 2.6.5，把导出包放入 `config/yes_steve_model/custom/deepseek_fish`，进入世界后 `/ysm model reload` + `/ysm model set`，YSM 返回 `Set 'live_gold3' models for player`，第三人称截图可见金色王冠。

> **该验证环境（`game-test/`）与测试模型（`models/deepseek-fish/`）均已删除**，相关截图随模型清理；结论仍作为"YSM 能解析、装载并渲染导出包"的历史证据保留。原记录见本文旧版与 [docs/archive/](docs/archive/README.md)。

### 2.5 真实会话内的闭环（历史）

1. `bb_session_start(mode="new_ysm", name="live_gold3", pack_dir="live_gold3")` → 创建完整 YSM 默认包。
2. `bb_apply_model_patch`：`add_cube`（Head 上加 `GoldCrown` 7×1×7）+ `set_uv`。
3. `bb_texture_patch`：在 `default.png` 精确涂金色。
4. `bb_render_views(["front","iso_fr"])` → 返回多模态图片；AI 看图确认金色王冠。
5. `bb_validate` → `bb_save_project`（16 files）→ `bb_export_ysm`（32 files + manifest）。
6. 后续 live 复核：`animation.create`/`apply_patch`、`texture.export_png`/`import_png`、`checkpoint`/`restore`（174→173 cubes）、`batch`、`diagnostics` 均通过；渲染附件降为 512×512 缩略图。

> 测试模型已清理，`models/` 当前无模型；新验收项目 `togawa-sakiko` 进行中。

## 3. 已实现的组成

| 模块 | 文件 | 说明 |
|---|---|---|
| BAE 主进程 | `packages/bb-agent-runtime/agent/main.js` | 隐藏窗口、独立 userData、网络拦截、插件注入、close→hide、window IPC、selftest |
| preload | `packages/bb-agent-runtime/agent/preload.cjs` | 注入 `__BB_AGENT__`、受控窗口 API、fs 权限预授权配合 |
| Bridge plugin | `packages/bb-agent-runtime/agent/bb-agent-bridge.js` | WS client/dispatch、revision/预算/GUI 门控、项目/模型/贴图/动画/渲染/校验/检查点/保存/导出/GUI、YRL、附件缩略图；**56 方法**实现 |
| 自检脚本 | `packages/bb-agent-runtime/agent/selftest.js` | 加载真实 YSM 默认模型，5 机位 + show/hide + WebGL 信息 |
| 组装/测试脚本 | `packages/bb-agent-runtime/scripts/{assemble,m0,e2e,e2e-look,test-all,verify-animation-diff,package-release}.mjs` | 组装 BAE、M0 报告、协议 e2e、视口 e2e、全量回归、动画 diff、发布包 |
| dsh Host 插件 | `packages/dsh-blockbench-agent/index.js` | **44 个 `bb_*` 定义（42 暴露）**、5 个命令、Skill 注册、进程监管/自动重启、revision 自动注入、超时/取消、图片附件缩略图、GPU safe-mode 降级 |
| 工具实现库 | `packages/dsh-blockbench-agent/lib/*.js` | `ws-server`、`refcanon`/`refsearch`/`refcollect`、`spec`、`segprobe`/`seglite`/`seginstall`/`segcomfy`、`viewsheet`、`imageprune`、`toolschema` |
| Skill / reference | `packages/dsh-blockbench-agent/skills/`、`reference/` | 建模工作流与语料规则（AI 读） |
| 测试 | `packages/dsh-blockbench-agent/test/` | 6 个 `*.test.mjs`（62 项）+ `host-smoke.mjs` + e2e 辅助脚本 |
| 协议传输 | `packages/dsh-blockbench-agent/lib/ws-server.js` | 零依赖 RFC6455 + JSON-RPC + HTTP/SSE（`/rpc`、`/events`）、token、超时、双向请求 |
| 契约 | `spec/tool-manifest.json`、`spec/bridge-methods.json`、`spec/generate_spec.py` | **44 工具 / 56 bridge 方法**的机器可读契约（手工维护源，重跑应 0 diff） |
| 参考语料 | `material/refmodels/`、`tools/ysmparser/`、`tools/extract_corpus.py` | 本地语料（gitignored）与解密/抽取工具 |

### DSH 端完成度清单

| 能力 | 状态 |
|---|---|
| 工具面：会话/场景/模型/贴图/动画/渲染/校验/检查点/回滚/保存/导出/批量/诊断/参考图/规格/分层 | ✅ |
| `/show` `/hide` `/bb-status` `/bb-start` `/bb-help` | ✅ |
| 工具 → bridge 方法映射、超时、exec AbortSignal 透传 | ✅ |
| `expected_revision` 自动注入 + bridge 侧冲突校验 | ✅ |
| GUI 可见期间写操作冻结（`GUI_BUSY`），用户编辑 revision 检测 | ✅ |
| 编辑/渲染/restore 预算与 `session.status` 展示 | ✅ |
| 进程崩溃自动重启（指数退避，最多 5 次）、端口/唯一 userData 隔离 | ✅ |
| 多模态结果：最多 4 图、512px 缩略图、原图落盘路径 | ✅ |
| 渲染自检：多格拼图 / 转台 / 动画采样 / isolate+zoom 局部审查 | ✅ |
| 图史压缩（旧图 surface replace 剥离）+ 附件预算护栏 | ✅ |
| 参考图管线：`bb_ref_canon` / `bb_ref_search` / `bb_ref_collect` | ✅ |
| 建模规格：`bb_spec_save` / `bb_spec_load` | ✅ |
| 分层：T0 探测（`bb_seg_probe`）/ T1 SAM2 轻量分割（`bb_seg_lite`）/ T2 安装与完整分层（`bb_seg_install`、`bb_seg_run`） | ✅（T1/T2 需首次下载） |
| 渲染变化/空图检测（`NO_VISIBLE_CHANGE`/`EMPTY_RENDER`） | ✅ |
| closeup / focus / SSAA | ✅（局部审查推荐 isolate+zoom） |
| 纹理图层 / PBR `_n`,`_s` / 控制器绑定 | ✅ |
| HTTP+SSE 传输（与 WS 同一端口，auto/ws/http） | ✅ |
| GPU 降级（渲染失败自动 safe-mode 重启重试） | ✅ |
| 增量保存（未编辑动画/贴图不重写）+ 二次保存幂等 | ✅ |
| zip 导出（目录 + manifest + zip） | ✅ |
| restore 后 arm 重载 | ✅ |
| Client UI 状态 pill（composer dock，Host `/bb-agent/status`） | ✅（需刷新页面加载 client） |
| Skill 注册（模型可发现、可加载） | ✅ |
| 回归测试：单测 62 + host-smoke 35 步 + e2e + 动画语义 diff | ✅ |
| 发布包 | ❌ 0.4.0 为历史发布；0.9.3 发布包待重打 |

## 4. 快速验证

```powershell
# node 不在 PATH 时用 DSH 自带的：
$node = 'D:\deepseekharness\resources\runtime\primary-runtime\dependencies\node\bin\node.exe'
cd F:\Deepseek_harness\blockbench
& $node --test packages/dsh-blockbench-agent/test/*.test.mjs   # 62/62
& $node packages/dsh-blockbench-agent/test/host-smoke.mjs      # 35 步，42 工具 schema lint
& $node packages/bb-agent-runtime/scripts/assemble.mjs         # 重新组装 dist/bb-agent-app
& $node packages/bb-agent-runtime/scripts/e2e.mjs              # 协议 + YSM 全链路
& $node packages/bb-agent-runtime/scripts/e2e-look.mjs         # 视口反馈 e2e
python spec/generate_spec.py                                   # 契约重生成（应 0 diff）
```

> 注意：如果 dsh 插件正在运行，`assemble.mjs` 会因 BAE 占用 `dist/bb-agent-app` 而 EPERM。先停 BAE/禁用插件，组装完再启用。

## 5. 安装与使用

- 已安装到当前 profile：entry `include:blockbench-agent`，配置见 `packages/dsh-blockbench-agent/cordis.patch.yml`：
  `workspaceRoot=F:\Deepseek_harness\blockbench\models`、`project=togawa-sakiko`、`autoStart=true`、
  `appPath=dist\bb-agent-app`、`executable=vendor\blockbench\node_modules\electron\dist\electron.exe`、`exposeGuiTools=false`。
- 插件以 **link** 方式指向 `F:/Deepseek_harness/blockbench/packages/dsh-blockbench-agent`；重装流程见 [MANUAL.md](MANUAL.md) §4。
- 当前会话可直接调用 `bb_*` 工具；`/show` 显示隐藏的 Blockbench 窗口，`/hide` 回后台并同步用户改动，`/bb-status` 查看状态，`/bb-start` 启动运行时，`/bb-help` 列出工具。
- 工作区：`<workspaceRoot>/<project>` = `models/togawa-sakiko/`；每次插件激活使用独立 `userdata-<pid>-<rand>`，避免实例锁冲突。
- 关闭/重启 dsh 后插件会自动启动 BAE（autoStart=true）。如不想常驻，把 config 的 `autoStart` 改为 false。
- 新会话可直接让模型加载 `blockbench-ysm-artist` Skill，获得完整工作流。

## 6. 已知限制（下一步）

1. **`tools/bedrock_render.py` 未完成**：自写软渲染器的骨骼 pivot 语义没调对，渲染会散架；**用 BAE 渲染，不要依赖它**。
2. **`arm.json`（第一人称手臂）无法重建**：没有切换 Blockbench 工程 tab 的 API。
3. **T1/T2 需要额外下载**：T1 首次自动下载 SAM2 约 59MB 到 `~/.dsh-blockbench-agent/sam2`；T2 需要 ComfyUI + See-through 权重（安装约 7GB，首次跑权重约 12.5GB）到 `~/.dsh-seethrough`。
4. **`dist/` 与源码同步是手工的**：改 bridge 后必须复制到 `dist/bb-agent-app/agent/`（或用 `assemble.mjs` 重建）。当前 2026-11-07 已复核 4 文件 sha256 一致。
5. **YSM 规范化是 v1**：动画文件已合并回写（保留未修改条目/顺序），但仍不是 YSM-Utils `saveNormalization` 的逐条移植；`ysm.json`/控制器文件的字节级规范化未做。
6. **动画语义 diff**：已接入回归（hosttest 产物 vs 模板，允许新增动画）；"修改已有动画"的逐动画回归仍靠人工/模型评审。
7. **VLM critic 是规则 watchdog-v2 + 外部 VLM**：结构化 bbox/edge/alpha/no-progress 判定已实现，但没有内置视觉评审模型。
8. **PBR 只在支持 Iris/光影时可见**：工具会生成/保存 `_n`/`_s` 贴图，但 Blockbench 离屏渲染不展示 PBR 效果。
9. **Client UI 验证**：状态 pill 已随 bundle 提供，Host `/bb-agent/status` 已用 HTTP 验证；当前页面需刷新后由 boot graph 加载 client half，未做浏览器自动化截图确认视觉细节。
10. **`locale/*.json` 加载未验证**：插件 package.json 已导出 locale 文件，但 dsh 侧实际加载路径/时机未做端到端验证。
11. **发布/分发**：0.9.3 发布包待重打；未做 electron-builder 安装器与代码签名（zip 便携分发为当前正式方式）。
12. **游戏内验证范围有限**：历史验证只覆盖单模型装载/渲染；未做多人同步、服务端校验、动画全量、长时间游玩。`game-test/` 环境已删除。
13. **契约漂移**：`spec/` 为手工维护契约源，与 `index.js` 实际 schema 存在 17 个工具参数漂移；以 `index.js` 为准（host-smoke 校验的是真实 schema）。

## 7. 与设计文档的工程偏差（不修改方案）

- BAE 采用**独立 dist 组装**（复制上游构建产物 + agent 四件套 + @electron/remote + YSM 模板），等价于方案中的"最小主进程 patch"。
- 为绕过 BB5 首次 `requireNativeModule('fs')` 权限弹窗，主进程在独立 userData 中预写 `plugin_permissions.json`（只授权 bridge 插件 fs），仅 agent profile 生效。
- 渲染使用自算 zoom-to-fit + 一次 warm-up 渲染（首帧空帧）；`focus.padding` 已修，局部审查推荐 `isolate` + `zoom`。
- 传输层 WS 与 HTTP+SSE 在同一个本地端口共存；`--transport=auto|ws|http` 控制优先/强制，auto 在 WS 连续失败后切换 HTTP。
- 附件缩略图在 renderer 里生成（512px），因为 dsh Host 侧 `nativeImage` 不可用（见 `bb_diagnostics.image.nativeImage=false`）；原图仍按 768 落盘。
- YSM 模板以 `templates/ysm_default` 随 BAE 分发（来自 YSM-Utils-Plugins assets/default，CC0 默认模型）。
- 模型工作区根由 `workspace` 改为 **`models/`**（`workspaceRoot=models`），`project=togawa-sakiko`；旧 `workspace/` 已清理。

---

## 8. v0.5.0 · 视口实时反馈（历史章节，眼睛 A+B）

> 方案与决策：[docs/07-视口实时反馈方案-冻结.md](docs/07-视口实时反馈方案-冻结.md)
> 本轮结论：**已实现并实机验收**；不做"常驻观看"（眼睛 C）。

### 8.1 交付内容

| 层 | 变更 |
|---|---|
| bridge | 新增 `camera.get/set`、`render.preview`、`render.sheet`、`render.turntable`、`render.animation_frame`、`render.texture_sheet`；`render.texture` 增加 inline；**渲染串行化** |
| host | 新增 `bb_look` / `bb_camera` / `bb_orbit` / `bb_anim_check`；**写操作自动附图**（step 级合并）；图史压缩器；`/bb-status` 展示图片预算 |
| 新模块 | `lib/viewsheet.js`（token 估算 + 网格规划）、`lib/imageprune.js`（旧图 surface replace 剥离） |
| 测试 | `e2e-look.mjs`（10 项）、`viewsheet.test.mjs` + `imageprune.test.mjs`（21 项） |

### 8.2 实测数据（RTX 4080 / 默认 YSM 模型，2026-10 数据）

| 指标 | 实测 |
|---|---|
| `render.preview` 640² 单帧 | 渲染 p50 **4.5–6.4 ms**；端到端 40–60 ms（含 PNG 编码 + base64） |
| `render.sheet` 2 格 320² | 9–24 ms，**211 token** |
| `render.sheet` 8 格转台 1280×640 | 12–25 ms，**514 token** |
| 自动附图（front+iso，320²） | **11–13 ms**，211 token |
| `render.texture_sheet` 2 块放大 | 1.7–3.6 ms |
| 动画采样 4 帧 | 17–25 ms |

### 8.3 实机验收中发现并修复的缺陷

| # | 缺陷 | 根因 | 修复 |
|---|---|---|---|
| 1 | WebSocket 分片不支持 | `ws-server.js` 遇非 FIN 帧直接 `closeWith(1003)`；浏览器对 >64KB 消息**强制分片**，故 8MB 上限从未真正生效 | 按 RFC 6455 §5.4 重组分片；累计超限才 1009 |
| 2 | 拼图首格恒空 | 用整张 sheet 判空（被其它格撑着永不空）；且 `resize` 与 `applyCamera` 之间插入调用会拿到空 buffer | 新增按**格子矩形**判空；`resize→applyCamera→draw` 封装为 `prepare` 在每次重试前重跑 |
| 3 | `set_uv` box 模式静默丢 `uv_size` | 只写 `uv_offset`，`uv_size` 未读 | box 模式支持显式尺寸 |
| 4 | `bb_batch` 内图片块丢失 | 子结果整包 JSON 化，image block 结构丢失 | 收集子调用 image block 统一附加；剥离 base64（JSON 从数 MB → 1.4KB） |
| 5 | `focus.padding` 参数无效 | 声明未实现，closeup 总触边 | 按 padding 外扩聚焦包围盒（**后续已修，局部审查推荐 isolate+zoom**） |
| 6 | **清理 `logs/` 目录导致宿主崩溃** | `createWriteStream(logs/runtime.log)` 无目录、无 `error` 监听 → 未捕获异常 → dsh host 退出 | spawn 前确保目录存在 + 监听 stream error + apply 时重建全部运行时目录 |

### 8.4 复验（v0.5.0 时期）

| 套件 | 结果 |
|---|---|
| 单元测试（viewsheet + imageprune） | 21/21 |
| 视口 E2E（e2e-look） | 10/10 |
| 协议回归（e2e.mjs） | 通过 |
| host 插件回归（host-smoke） | 33 项全通过（0.9.1 已扩到 35 步 / 41 工具） |
| 实机建模 | 通过（56 骨 / 196 方块 / 0 error / 导出 38 文件；该模型已清理） |

### 8.5 已知边界

- **L2 长跨度摘要未接入**：`compaction-basic` 被 `dsh-web-app` 默认 `disabled:true`，强行启用影响整个 profile，超出插件职责。当前用 L1（图史剥离）+ L3（`image-offload` 兜底）控制成本。
- **不做常驻连续观看**（眼睛 C）：每帧送模型不划算，改为"编辑即看 + 按需拉取"。
- 用户 Ctrl+Z/Ctrl+Y 仍未计入 revision（既有问题，与本轮无关）。
