<p align="center">
  <img src="docs/assets/cover.png" alt="DSH × Blockbench Agent" width="100%">
</p>

<h1 align="center">DSH × Blockbench Agent</h1>

<p align="center">
  <b>让 AI 真正走进 Blockbench：隐藏建模 · 无头渲染 · 像素贴图 · 动画 · YSM 游戏验证</b>
</p>

<p align="center">
  <img alt="version" src="https://img.shields.io/badge/version-0.9.2-59c2ff">
  <img alt="platform" src="https://img.shields.io/badge/platform-Windows%20%7C%20dsh-1b2a52">
  <img alt="tools" src="https://img.shields.io/badge/tools-43%20defined%20%2F%2041%20exposed-3d7fd6">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-4ade80">
</p>

<p align="center">
  <a href="MANUAL.md"><b>📖 完整使用手册</b></a> ·
  <a href="https://github.com/yan-mc/blockbench-ysm-agent/releases">⬇️ Releases</a> ·
  <a href="HANDOVER.md">交接班档案</a> ·
  <a href="ENGINEERING.md">工程状态</a> ·
  <a href="SETUP.md">从零搭建</a>
</p>

> **用一句话说**：给 dsh 里的模型装上“Blockbench 的手和眼睛”——它能语义化建模、精确改贴图、无头渲染看结果、检查点回滚、保存/导出 YSM，并最终在 Minecraft 里加载验证；需要人工时 `/show` 随时接管。

> **发布状态**：当前版本 **0.9.2**。GitHub Releases 上的 **0.4.0 为历史发布**；0.9.2 发布包尚未重打（`release/` 已清空，待 `package-release.mjs` 重新生成）。想直接试用当前代码，按 [SETUP.md](SETUP.md) 从仓库搭建。

## 🎬 视频介绍

[![插件介绍视频](docs/assets/cover.png)](#)

- **B 站向介绍视频（2:46）**：[deepseek-blockbench-agent-intro.mp4](https://github.com/yan-mc/blockbench-ysm-agent/releases/download/v0.4.0/deepseek-blockbench-agent-intro.mp4)（该视频为 0.4.0 时期录制，功能与本仓库不同步，仅作演示）
- 讲功能、使用与优势，不含制作过程；素材使用早期测试模型「DeepSeek 鲸鱼娘 / 蓝色大肥鱼」（该测试模型已清理）
- 封面与投稿文案：[media/bilibili-upload.md](media/bilibili-upload.md)、[media/bilibili-cover.png](media/bilibili-cover.png)
- **0.9.2 更新宣传片**：见 `media/`（立绘拆分 T1/T2 + 复杂逐步调整案例，本地生成，不进仓库）

## ✨ 0.9.2 更新亮点：立绘拆分 + 复杂逐步调整（案例：丰川祥子）

> 案例模型：明日方舟 × BanG Dream! Ave Mujica 联动干员 **丰川祥子「旋律的主人」**（YSM，2×512 贴图）。
> 完整过程与数据：[models/togawa-sakiko/](models/togawa-sakiko/README.md) · [T2 安装/分层报告](models/togawa-sakiko/T2-INSTALL-REPORT.md) · [逐细节修理报告](models/togawa-sakiko/T2-REPAIR.md)

![最终模型四视图](docs/assets/showcase/sakiko-final-4views.png)

**① 立绘拆分（T1/T2）让 AI 能"逐部件看图"**：一张官方立绘 → T1 SAM2 轻量分割（59MB，CPU 秒级）→ T2 See-through 完整分层（ComfyUI + 权重，首次约 23 分钟；实测输出 **29 个语义层**：前发/后发/脸/眼/上衣/裙/手套/靴… + 深度顺序 + 遮挡补全）。AI 不再是"凭整体印象改模型"，而是对着 29 张部件图逐层核对。

![T2 29 层语义分层](docs/assets/showcase/t2-29-layers.png)

**② 复杂逐步调整：从 217 块到 401 块**：首轮验收 → T1 逐部件复检发现 5 个 major → T2 层对照 + P1–P5 逐项修理 → v2 美术优化（角重做为正面连续螺旋带、背部长发分组、眼睛改菱形、侧发/角穿插修正）。最终 `bb_validate` 0 error。

![修理前后对比](docs/assets/showcase/sakiko-before-after.png)

**③ 头部细节**（角/发/菱形眼）：

![头部细节](docs/assets/showcase/sakiko-detail-head.png)

## 工程状态（v0.9.2，2026-11-07 复核）

**已实现并验证**：隐藏窗口 BAE、JSON-RPC bridge（WS + HTTP/SSE 双传输）、**43 个 `bb_*` 工具定义 / 实际暴露 41 个**（`bb_show_gui`、`bb_hide_gui` 由 `/show` `/hide` 命令替代）、**5 个命令**（show/hide/bb-status/bb-start/bb-help）、**1 个 Skill**（`blockbench-ysm-artist`）、**56 个 bridge 方法 / 7 个事件 / 22 个错误码**、YSM 创建/打开/保存/zip 导出、动画/贴图/图层/PBR/控制器绑定、检查点/回滚（内嵌贴图 + arm 快照）、增量保存与幂等、动画合并回写、渲染变化/空图检测、watchdog-v2、512px 附件、GPU 降级、Client UI 状态 pill。

**0.9.2 实测**：

| 项 | 结果 |
|---|---|
| 单元测试 | **62/62 通过**（6 个 `*.test.mjs`：imageprune 13 / refcanon 9 / segprobe 10 / spec 17 / tool-schema 5 / viewsheet 8） |
| host-smoke | **35 步全过**，schema lint 检查 **41 个工具**（本地实跑，2026-11-07 18:40） |
| 契约 | `spec/tool-manifest.json` 43 工具、`spec/bridge-methods.json` 56 方法 / 7 事件 / 22 错误码；`spec/generate_spec.py` 重跑与提交内容 **0 diff**，且 0.9.2 已对齐 `spec` ↔ `index.js` 的 43/43 参数（以 `index.js` 实际 schema 为准） |
| 上游 | `vendor/blockbench` = **Blockbench 5.2.2**；`vendor/YSM-Utils-Plugins` = 2.6.0（MIT）；vendor 总体积约 **1.54GB** |
| 参考语料 | `material/` 约 **329.1MB**；`ysm_decoded` 169 目录 / 1156 文件 / 233MB；`ysm` 9 包；`maid` 874 文件 / 446 条（含 325 个角色）；`bbmodel` 62 对 |
| 模型工程 | `models/togawa-sakiko/`：**丰川祥子（旋律的主人）**案例模型，70 骨 / **401 方块** / 2×512 贴图 / 303 动画，`bb_validate` 0 error；见 [models/README.md](models/README.md) |

### 0.5–0.9 新增能力

| 能力 | 说明 |
|---|---|
| **编辑即看** | 写操作完成后自动附一张小拼图（同 step 合并成一张），改完立刻看见 |
| **参数化相机** | `bb_camera` 任意方位/俯仰/距离/正交透视；`render.preview` 不落盘单帧 |
| **多格拼图** | `bb_look` 一次返回一张 N 格拼图（2-8 帧 token 相近，比多次渲染省 2-3 倍） |
| **局部审查** | `bb_look({isolate:"AllHead", zoom:2.5})` 只渲染指定骨骼子树并自动对焦；`closeup` 的 `focus.padding` 已修，但推荐 isolate+zoom |
| **环绕转台** | `bb_orbit` 8 角度合一张图，替代"靠三视图脑补"，查穿模与对称性 |
| **贴图像素放大** | `bb_render_texture` 走 inline 拼图路径，精修核对微小改动 |
| **动画采样** | `bb_anim_check` 按时间轴采样 4-16 帧，检查动作幅度与起止姿势 |
| **图史压缩** | 旧渲染图从上下文剥离为占位文本（surface replace，零模型调用）+ 附件预算护栏 |
| **参考图管线** | `bb_ref_canon` / `bb_ref_search` / `bb_ref_collect`：官方基准 → 多源搜图 → 下载去重 → 带编号对照表（零安装，详见 [docs/11](docs/11-参考图收集管线.md) 与 [docs/18](docs/18-官方基准与深度搜索.md)） |
| **建模规格** | `bb_spec_save` / `bb_spec_load` 固化规格并生成构建计划 |
| **分层能力** | T1 SAM2 ONNX（约 59MB，CPU 秒级；**标准档必做**）/ T2 See-through（安装约 6.5GB + 权重约 12.5GB；**精修档推荐**；实测输出 29 语义层 + 深度序 + 遮挡补全） |
| **渲染自检** | `bb_render_views` + watchdog-v2 变化/空图/触边检测；isolate+zoom 局部审查 |

### 实战验证

在视口反馈闭环下做过完整实战验证：从搜参考图、写规格、建模、贴图、渲染自检到导出，全程只靠工具与渲染图自我校验，没有人工建模。

**0.9.2 新案例**：丰川祥子「旋律的主人」— 首轮 T1 验收（217 块）→ T1 逐部件复检（5 major）→ T2 完整分层（29 层）逐细节修理（355 块）→ v2 美术优化（401 块，角/发/眼重做）。产线、对比图与剩余差距见 [models/togawa-sakiko/README.md](models/togawa-sakiko/README.md) 与 [docs/22](docs/22-建模实战复盘与经验（2026-11-07）.md)。

- 工程状态/实测数据：[ENGINEERING.md](ENGINEERING.md)
- 完整使用手册：[MANUAL.md](MANUAL.md)
- 交接班档案（第一手）：[HANDOVER.md](HANDOVER.md)
- 目录地图：[FOLDER-MAP.md](FOLDER-MAP.md)
- 从零搭建：[SETUP.md](SETUP.md)
- 实现包说明：[packages/README.md](packages/README.md)
- 机器可读契约：[spec/tool-manifest.json](spec/tool-manifest.json)、[spec/bridge-methods.json](spec/bridge-methods.json)
- 测试证据：[docs/test-evidence/](docs/test-evidence/README.md)

---

# 设计文档（历史设计基线）

> **本节及以下为 2026-10-18 版设计稿（合并版），保留设计意图与事实依据；实现状态以 [ENGINEERING.md](ENGINEERING.md) 与 [HANDOVER.md](HANDOVER.md) 为准。**
> 其中的工具数量、里程碑状态、目录结构均可能过时，不要当作现况引用。

## 0. 先读结论（TL;DR）

| 问题 | 结论 |
|---|---|
| 怎么隐藏 Blockbench？ | 上游 `electron/main.js` **硬编码 `win.show()`**，必须 fork 主进程（3 处小改：不 show、`backgroundThrottling:false`、注入 bridge 插件）；渲染层零改动。 |
| 怎么无头出图？ | 复用 Blockbench 内置**离屏 Preview**（`MediaPreview`/`NoAAPreview`）+ `Screencam.advancedScreenshot(cb)` + `Blockbench.writeFile`；renderer 已 `preserveDrawingBuffer:true`，全程无对话框。 |
| 怎么让 AI 不写原始 JSON？ | dsh 侧注册 `bb_*` 语义工具（建模 patch / 像素绘制 / 渲染 / 校验），底层 JSON-RPC 转给 Blockbench 插件；回执只给 changed ids + diff + 摘要，列表全部分页。 |
| 怎么让 AI "看见"？ | `ctx.attachments.saveImage()` + `output.render()` 返回 `image` block；v0.5 起支持**编辑即看**（写操作自动附图）、`bb_look`/`bb_orbit` 多格拼图、参数化相机、动画采样；旧图可被剥离为占位文本以控上下文。 |
| 怎么保证 YSM 能进游戏？ | YSM-Utils 是 **UI 插件、无导出 API、只写 ysm.json**；必须自研 YRL（规范化/骨架/导出编排），并强制 `export_empty_groups=true`（否则 30 根空定位骨骼被剪，进游戏缺手持物/鞘翅）。 |
| 怎么人机协同？ | dsh 原生 `/show` `/hide` 命令（`ctx.commands.register`），不消耗模型 token；GUI 期间冻结写操作，`/hide` 后 resync revision 并注入用户改动摘要。 |
| 通信走什么？ | 本地 WebSocket JSON-RPC 2.0（dsh 为 server，BBAR 为 client）；首包 token 鉴权；协议与传输解耦，可回退 HTTP+SSE / Python client。 |
| 最大的技术风险？ | 隐藏窗口下 WebGL 的稳定性（不同 GPU/驱动/远程桌面）。**必须先用 M0 Spike 验证**，再投入开发。 |

---

## 1. 交付物导航

| 文件 | 内容 | 对应需求模块 |
|---|---|---|
| **[系统开发与设计方案.md](<系统开发与设计方案.md>)** | 合并版主文档（历史合订本，推荐通读设计意图） | 全部 |
| [docs/01-总体架构与数据流.md](docs/01-总体架构与数据流.md) | 架构图、进程/生命周期、数据流、ADR、目录规范 | ① 系统架构与数据流 |
| [docs/02-通信协议规范.md](docs/02-通信协议规范.md) | WebSocket JSON-RPC 2.0 规范、方法目录、错误码、超时/幂等、示例 | ② 通信协议 |
| [docs/03-Tool-API-清单.md](docs/03-Tool-API-清单.md) | 43 定义 / 41 暴露的 `bb_*` 工具参数/返回/错误/预算、Tool 设计原则 | ③ Tool API 声明 |
| [docs/04-闭环状态机.md](docs/04-闭环状态机.md) | 状态机、预算/收敛/回滚、VLM 评审协议、失败恢复、伪代码 | ④ 闭环工作流 |
| [docs/05-工程难点与避坑指南.md](docs/05-工程难点与避坑指南.md) | Electron/WebGL、启动/注入、Undo/保存、贴图/UV、YSM、Token、Windows、许可 | ⑤ 工程难点 |
| [docs/06-实施路线图与验收.md](docs/06-实施路线图与验收.md) | M0–M6 里程碑、测试策略、验收标准、发布 | 落地计划 |
| [spec/tool-manifest.json](spec/tool-manifest.json) | 机器可读工具清单（JSON Schema，43 工具） | ③ 契约 |
| [spec/bridge-methods.json](spec/bridge-methods.json) | 机器可读 JSON-RPC 方法/事件/错误码（56/7/22） | ② 契约 |
| [spec/generate_spec.py](spec/generate_spec.py) | 契约生成器（手工维护的契约源，重跑应 0 diff） | 工具链 |
| **[ENGINEERING.md](ENGINEERING.md)** | **工程实现状态/实测数据/DSH 端完成度/已知限制**（设计不变，实现以此为准） | 落地状态 |
| [HANDOVER.md](HANDOVER.md) | 交接班档案（第一手现状） | 落地状态 |
| [packages/README.md](packages/README.md) | 两个实现包的构建、测试与运行命令 | 工程说明 |
| [models/](models/README.md) | 模型工程工作区（当前无测试模型，新验收项目进行中） | 落地工程 |
| [research/blockbench-core.md](research/blockbench-core.md) | Blockbench 5.2.2 源码级研究（677 行非空，文件:行号） | 事实依据 |
| [research/ysm-format.md](research/ysm-format.md) | YSM 格式/插件导入导出研究（826 行非空，文件:行号） | 事实依据 |
| [research/dsh-integration.md](research/dsh-integration.md) | dsh 插件/Tool/多模态/命令研究（439 行非空，取证） | 事实依据 |

---

## 2. 系统一览

```mermaid
flowchart LR
  M["主模型 / VLM"] --> D["DBA · dsh Host 插件<br/>bb_* 工具 + /show 命令"]
  D -- "JSON-RPC 2.0 over WebSocket" --> B["BABP · Blockbench 插件<br/>renderer 侧"]
  B --> C["Blockbench Core<br/>Project/Cube/Texture/Undo/Preview"]
  B --> Y["YRL · YSM 资源层<br/>骨架/规范化/导出"]
  C --> R["离屏 Preview<br/>MediaPreview.render()"]
  R --> P["PNG 落盘 + 附件回灌"]
  P --> D
  D --> M
  E["BBAR · 隐藏 Electron 进程"] --- B
```

三条关键链路：

1. **语义编辑**：`bb_apply_model_patch` / `bb_texture_patch` → 一个 Undo 事务 → revision+1 → 有界回执。
2. **无头反馈**：`bb_look` / `bb_render_views` → 离屏 Preview 渲染 → PNG 落盘/拼图 → `ImageBlock` → 模型视觉自检。
3. **人机协同**：`/show` 显示同一进程窗口 → 冻结 AI 写操作 → 用户手改 → `/hide` → 重新同步 revision。

---

## 3. 已核实的事实基线（节选）

- Blockbench v5.2.2：Electron 43 + Vue2 + three.js r129；`electron/main.js` 在 `loadURL().finally()` 中 `win.show()`；窗口无 `backgroundThrottling`。
- Preview renderer：`alpha:true`、`preserveDrawingBuffer:true`；存在离屏 `MediaPreview`/`Screencam.NoAAPreview`；`Screencam.advancedScreenshot(..., cb)` 在传入 cb 时不弹 UI。
- 贴图：`Texture.getActiveCanvas()` + `updateChangesAfterEdit()` 才能刷新 3D；Undo aspects `{textures:[t],bitmap:true}`。
- 保存：`Codecs.*.compile()/write()`、`Blockbench.writeFile` 无对话框；`export()/exportFile()/Action.trigger()` 会弹 native 模态（`window.confirm/alert` 在桌面端被替换为同步 MessageBox，会卡死 renderer）。
- 插件：`source:'file'` 条目按绝对路径加载；可在主进程 `did-finish-load` 后用 `executeJavaScript` 执行 `new Plugin().loadFromFile({path}, false)` 注入并持久化。
- YSM：`ysm.json` spec 2；默认主模型 64 bones / 172 cubes / 30 空骨骼（26 个 Locator）；贴图 128×128 per-face UV；动画 Bedrock 1.8、控制器 1.19；YSM-Utils 为纯 UI 插件、只写 ysm.json。
- dsh：`ctx.tools.register(defineTool(...))`、`ctx.commands.register(...)`、`ctx.attachments.saveImage()`、`ctx.effect()` 清理；图片会从产生起在每次请求中重复计费。

> 完整证据（文件:行号、官方文档链接）见三份 research 报告与各章末尾的引用。

---

## 4. 如何阅读

| 你的角色 | 建议顺序 |
|---|---|
| 接手/负责人 | [HANDOVER.md](HANDOVER.md) → [docs/21](docs/21-现代化建模总纲.md) → Skill → [docs/07](docs/07-视口实时反馈方案-冻结.md) |
| 架构/设计 | 本 README 设计段 → `01` → `04` → `06` |
| dsh / Agent 工程师 | `01` → `02` → `03` → `packages/` |
| Electron / 渲染工程师 | `01` §4 → `05` §1/§2 → `ENGINEERING.md` |
| YSM / 建模工程师 | `docs/20`/`21*` → `research/ysm-format.md` → Skill |
| QA | `06` §3–§5、`docs/test-evidence/` |

---

## 5. 历史里程碑状态（2026-10，仅供追溯）

| 项 | 当时状态 |
|---|---|
| 传输层（WS 握手/鉴权/双向请求/事件/并发/超时） | ✅ 已跑通 WS 冒烟 |
| M0 隐藏窗口 + WebGL 真实出图 | ✅ 通过（GPU 与 SwiftShader 两条路径） |
| YSM 默认包创建/导入/导出 | ✅ 已实现 |
| dsh 插件安装/启用 | ✅ 已安装并激活 |
| 视觉闭环端到端（VLM） | 🟡 规则 watchdog + 外部模型看图，无内置 critic |

> 完整进展见 [ENGINEERING.md](ENGINEERING.md)，2026-10 的 M0 报告已归档到 `docs/archive/`。

---

## 6. 下一步方向

1. 重打 **0.9.2 发布包**（`node packages/bb-agent-runtime/scripts/package-release.mjs`）。
2. 完成新验收项目 `togawa-sakiko`（明日方舟×BanG Dream 丰川祥子，联动皮肤「旋律」，双大角）。
3. 完善 T1/T2 分层与 `bedrock_render`（当前未完成，勿依赖）。
4. 补 `arm.json` 重建与 locale 加载验证（见 HANDOVER「已知限制」）。

---

## 7. 目录（当前真实布局）

```
F:\Deepseek_harness\blockbench\
├─ README.md                      # 门面：封面 / 工程状态 / 历史设计基线
├─ MANUAL.md                      # 完整使用手册（v0.9.2）
├─ HANDOVER.md                    # 交接班档案（第一手）
├─ ENGINEERING.md                 # 工程状态/实测数据/已知限制
├─ FOLDER-MAP.md                  # 目录地图与维护约定
├─ SETUP.md                       # 从零搭建
├─ NOTICE.md                      # 第三方许可
├─ 系统开发与设计方案.md          # 历史设计合订本（2026-10-18）
├─ docs\                          # 设计文档 01–07/10–18/20/21* + archive + test-evidence + assets
├─ spec\                          # 机器可读契约 + 生成器
├─ packages\
│  ├─ bb-agent-runtime\           # BAE 运行时（main/preload/bridge/selftest/scripts）
│  ├─ dsh-blockbench-agent\       # dsh Host 插件 + Client pill + Skill + reference
├─ models\                        # BAE 工作区根（当前无测试模型，README 说明约定）
├─ material\                      # 本地参考语料（gitignored，约 329.1MB）
├─ tools\                         # 分析脚本 + ysmparser 解密器 + extract_corpus.py
├─ research\                      # Blockbench / YSM / dsh 研究证据
├─ media\                         # 介绍视频、幻灯片、构建脚本
├─ vendor\                        # 上游 Blockbench 5.2.2 + YSM-Utils 2.6.0（只读，约 1.54GB）
├─ dist\bb-agent-app\             # assemble.mjs 组装产物（本地运行）
├─ release\                       # 发布物落点（当前为空，0.9.2 待重打）
└─ .gitignore / .gitattributes / LICENSE / package.json
```

> 没有 `prototype/`、`game-test/`、`_archive/`；`workspace/` 已在 2026-11-07 清理。归档统一放 `docs/archive/`。

---

## 8. 许可与声明

- 本方案与原创代码/文档：按项目需要授权；引用第三方内容遵循其原许可。
- **Blockbench**：GPL-3.0-or-later。BAE 是衍生发行版，发布时必须随包提供对应源码/修改说明与许可证；不得暗示官方背书。
- **YSM-Utils-Plugins**：MIT；复用其规范化规则/代码需保留版权与许可声明。
- **YSM 默认模型**：官方文档注明以 CC 0 发布（可修改分发）；用户提供的参考图/皮肤版权由用户负责。
- **Minecraft**：遵守 Mojang EULA，不分发原始游戏资产。
- **参考语料**（`material/`）：第三方模型/贴图，仅本地研究使用，不随仓库分发（已 gitignore）。
