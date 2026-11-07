# 交接班档案 · YSM × Blockbench 无头建模 Agent

> 最后更新：2026-11-07
> 插件版本：**0.9.2**（43 个工具定义 / 实际暴露 41 个、5 个命令、1 个 Skill、56 个 bridge 方法）
> 本文件是接手这个项目的**第一份必读材料**。设计细节见 `docs/`，使用方法见 `MANUAL.md`，工程实测见 `ENGINEERING.md`。

---

## 一、这是什么

一套让 AI 在**后台 Blockbench** 里建模、贴图、做动画、渲染自检、导出 YSM 皮肤的工具链。

- **DSH 插件**（`@local/dsh-blockbench-agent`）：向 AI 注册 43 个 `bb_*` 定义（默认暴露 41 个；`bb_show_gui`/`bb_hide_gui` 由 `/show` `/hide` 命令替代），5 个命令、1 个 Skill
- **BAE 运行时**（Blockbench Agent Engine）：隐藏的 Electron 窗口 + WebSocket JSON-RPC（56 方法 / 7 事件 / 22 错误码）+ 离屏渲染
- **技能文档**：教 AI 怎么建模（含 169 个现代模型实测出来的规范）
- **参考语料**：169 个解密后的现代 YSM 模型 + 325 个女仆模组角色 + 62 对舰娘模型

---

## 二、目录地图（所有东西都在 `F:\Deepseek_harness\blockbench` 下）

```
F:\Deepseek_harness\blockbench\
│
├── HANDOVER.md              ★ 本文件（交接班档案）
├── README.md                  项目介绍与功能列表（含历史设计基线）
├── MANUAL.md                  使用手册（v0.9.2）
├── SETUP.md                   从零搭建
├── ENGINEERING.md             工程状态/实测数据/已知限制
├── FOLDER-MAP.md              目录地图与维护约定
├── NOTICE.md                  第三方许可
├── 系统开发与设计方案.md       历史设计合订本（2026-10-18，看设计意图用）
├── docs/                      ★ 设计文档 01–07/10–18/20/21* + archive + test-evidence + assets
├── spec/                      机器可读契约（tool-manifest.json / bridge-methods.json / generate_spec.py）
│
├── packages/                  ★ 源码
│   ├── dsh-blockbench-agent/     DSH 插件（host 侧）
│   │   ├── index.js              43 个工具定义（41 暴露）
│   │   ├── lib/                  工具实现（refcanon/refsearch/refcollect/spec/seg*/viewsheet/imageprune/ws-server）
│   │   ├── skills/               ★ 技能文档（AI 读这个）
│   │   │   └── blockbench-ysm-artist.md
│   │   ├── reference/            ★ 参考手册（AI 建模时查）
│   │   │   ├── blockbench-ysm-playbook.md
│   │   │   └── ysm-corpus-rules.md
│   │   ├── assets/               委派任务书模板、SAM2 推理脚本
│   │   └── test/                 6 个单测文件（62 项）+ host-smoke（35 步）
│   ├── bb-agent-runtime/         BAE 运行时（Electron 主进程 + preload + bridge + scripts）
│   │   └── agent/bb-agent-bridge.js   ★ 所有 bridge 方法都在这里
│
├── dist/                      构建产物（bb-agent-app；2026-11-07 重新 assemble，190 文件/36MB）
├── vendor/                    第三方（Blockbench 5.2.2、YSM-Utils-Plugins 2.6.0，约 1.54GB）
├── tools/                     ★ 独立工具
│   ├── ysmparser/YSMParser.exe  ★ .ysm 解密器（OpenYSM/YSMParser v0.3.6）
│   ├── extract_corpus.py        语料抽取脚本（由 refmodels 的 _extract.py 转正）
│   ├── mine_*.py / merge_ocr.py / slice_longimg.py / tidy_materials.py   分析脚本
│   └── bedrock_render.py        软渲染器（未完成，见 §八）
│
├── material/refmodels/        ★ 参考模型语料（约 329.1MB，gitignored，仅本地）
│   ├── ysm_decoded/            169 个解密后的现代 YSM 工程（1156 文件，233MB）
│   │   （168 个扁平解密件 + 1 个完整标准包「爱莉希雅__1769436c7a73」；8 个 JSONC 带 // 注释）
│   ├── maid/                   874 文件 / 446 条（325 个角色，其余家具/载具/PvZ）
│   ├── bbmodel/                62 对舰娘 bbmodel（含建筑/载具，人物参考价值偏低）
│   ├── ysm/                    9 个未加密 YSM 包（6 官方 CC0 模板 + 3 wine_fox 角色包）
│   └── inventory_*.json        索引（ysm 已修正为 169 条；parts 仍为 161 条历史派生统计）
│
├── models/                    BAE 工作区根（workspaceRoot），当前验收模型 togawa-sakiko（见 §十）
├── research/                  研究证据（Blockbench 核心、YSM 格式、DSH 集成）
├── media/                     演示素材
├── release/                   发布物落点（当前为空；0.9.2 发布包待重打）
└── 根文件                     .gitignore / .gitattributes / LICENSE / package.json / README 等
```

> 已不存在：`prototype/`、`game-test/`、`_archive/`、`workspace/`、`models/deepseek-fish/`。归档统一在 `docs/archive/`。

**模型工程目录（BAE 的 workspace）**：`models/<project>/`，由 `packages/dsh-blockbench-agent/cordis.patch.yml` 的 `workspaceRoot` + `project` 决定：
当前 `workspaceRoot=F:\Deepseek_harness\blockbench\models`、`project=togawa-sakiko`。
所有 `bb_project_open({pack_dir})` 的路径都**相对 `<workspaceRoot>/<project>`**，不是仓库根。

---

## 三、怎么跑起来（从零到能建模）

### 3.1 装插件

```powershell
# 插件以 link 方式装进 DSH profile（profile 指向仓库内 packages/dsh-blockbench-agent）
# 在 DSH 里执行：
plugin_manager install_bundle target=F:/Deepseek_harness/blockbench/packages/dsh-blockbench-agent
```

重装/更新时代码路径：

```text
plugin_manager remove_bundle target=@local/dsh-blockbench-agent
plugin_manager install_bundle target=F:/Deepseek_harness/blockbench/packages/dsh-blockbench-agent
```

验证：DSH 里应能看到 **41 个暴露的 `bb_*`**（43 定义）和 skill `blockbench-ysm-artist`。

### 3.2 让 BAE 启动

第一次调用任意 `bb_*` 工具（如 `bb_session_status`）时，host 会自动拉起隐藏的 Electron 窗口。
`gpu_ok: true` 表示离屏渲染可用。也可用 `/bb-start` 手动启动、`/bb-status` 查看状态。

### 3.3 改代码后怎么生效

| 改了什么 | 怎么生效 |
|---|---|
| `packages/dsh-blockbench-agent/index.js` 或 `lib/` | 重装插件：`plugin_manager remove_bundle` → `install_bundle` |
| `packages/bb-agent-runtime/agent/*.js`（bridge/main/preload/selftest） | **必须同步到 dist 并重启 BAE**：停 BAE → `node packages/bb-agent-runtime/scripts/assemble.mjs`（或 `Copy-Item packages\bb-agent-runtime\agent\*.js dist\bb-agent-app\agent\ -Force`）→ 再调任意 `bb_*` |
| `skills/` 或 `reference/` 下的 md | 重装插件即可（skill 在插件激活时加载） |
| 依赖/上游/vendor 变化 | 用 `assemble.mjs` 全量重建 `dist/bb-agent-app`（只依赖 vendor + packages + YSM-Utils assets/default） |

> ⚠️ **dist 在 BAE 运行时是锁住的**，必须先停 BAE/杀 electron 才能覆盖。
> 当前 `dist/bb-agent-app` 是 **2026-11-07 从 vendor Blockbench 5.2.2 + 当前源码重新 assemble** 的产物（**190 文件 / 36MB**，`templates/` 32 文件），`agent/` 4 个文件 sha256 与源码一致。

### 3.4 改完必须验证

```powershell
cd F:\Deepseek_harness\blockbench
# node 不在 PATH 时用 DSH 自带：
# $node = 'D:\deepseekharness\resources\runtime\primary-runtime\dependencies\node\bin\node.exe'
node --test packages\dsh-blockbench-agent\test\*.test.mjs     # 6 文件 / 62 项
node packages\dsh-blockbench-agent\test\host-smoke.mjs        # 35 步，真实 schema 校验 41 工具
python spec\generate_spec.py                                   # 重生成契约（应 0 diff）
```

> ⚠️ **工具 schema 一旦非法，所有工具和 skill 会从 DSH 里一起消失**
> （曾经因为 `type:'object'` 没写 `additionalProperties` 全挂过一次）。
> 改 schema 后必须跑 host-smoke。

---

## 四、工具分组速查（43 定义 / 41 暴露）

> 完整参数以 `index.js` 实际 schema 为准；`spec/tool-manifest.json` 是手工维护契约源，存在已知参数漂移。

| 组 | 工具 | 用途 |
|---|---|---|
| **会话** | `bb_session_status` `bb_session_start` `bb_project_open` `bb_project_close` | 开/关工程 |
| **读** | `bb_scene` `bb_get_element` `bb_revisions` `bb_diagnostics` | 看结构/骨骼/方块/UV |
| **写** | `bb_apply_model_patch` `bb_batch` `bb_checkpoint` `bb_restore` | 加骨/加块/改块 |
| **贴图** | `bb_texture_patch` `bb_texture_read` `bb_render_texture` `bb_texture_import_png` `bb_texture_export_png` `bb_texture_create` `bb_texture_layer` `bb_texture_pbr` | 画/读/导入导出/图层/PBR |
| **看** | `bb_look` `bb_render_views` `bb_orbit` `bb_camera` `bb_anim_check` | ★ 渲染自检，**支持 isolate+zoom 局部审查** |
| **参考图** | `bb_ref_canon` `bb_ref_search` `bb_ref_collect` | 官方基准 → 深度搜图 → 对照表 |
| **规格** | `bb_spec_save` `bb_spec_load` | 建模规格与构建计划 |
| **分层** | `bb_seg_probe` `bb_seg_install` `bb_seg_lite` `bb_seg_run` | T0/T1/T2 立绘分层 |
| **动画** | `bb_animation_create` `bb_animation_patch` `bb_animation_delete` `bb_animation_list` | 关键帧/控制器绑定 |
| **交付** | `bb_validate` `bb_save_project` `bb_export_ysm` | 校验/保存/导出 zip |
| **GUI** | `bb_show_gui` `bb_hide_gui`（默认不暴露，43 定义中的 2 个） | 用户接管（由 `/show` `/hide` 命令代替） |

### 两个最常用的

```
bb_look({isolate:"AllHead", zoom:2.5, cells:[{camera:{azimuth:0,elevation:4}},{camera:{azimuth:40,elevation:10}}]})
bb_apply_model_patch({ops:[{op:"add_cube", bone:"Head", name:"Bang1", origin:[...], size:[...]}]})
```

**`isolate` 是关键能力**：只渲染指定骨骼子树，其余隐藏并自动对焦，`zoom` 再放大。
检查单个手臂/头发/裙子时用它，不要每次都渲染全身。（`focus.padding` 已修，但局部审查仍推荐 isolate+zoom。）

---

## 五、参考语料怎么用

### 5.1 语料是什么

`material/refmodels/ysm_decoded/` 里有 **169 个解密后的现代 YSM 工程**，来自本机 MC 库的
520 个 `.ysm`（去重后 169 个唯一模型）。这些是**最重要的参考源**——现代 YSM 模型的真实基准。

布局两种都要处理：

- 扁平：`{名字}/main.json` + `{名字}/*.png`（168 个）
- 标准包：`{名字}/models/main.json` + `{名字}/textures/*.png`（1 个：`爱莉希雅__1769436c7a73`）

**坑**：其中 **8 个是 JSONC**（带 `//` 注释），解析时要宽松处理，不能直接 `JSON.parse`。

**为什么能解密**：YSM 模型是加密容器，用 `tools/ysmparser/YSMParser.exe`（OpenYSM 开源项目）可以解出 `main.json`（bedrock 几何）+ 贴图 + 动画。

### 5.2 从 .ysm 重新解码

```powershell
# 1. 把 .ysm 收集到输入目录
# 2. 解码
tools\ysmparser\YSMParser.exe -i <输入目录> -o <输出目录>
```

实测：169 个文件 **1.3 秒**解完，0 失败。

### 5.3 打开语料模型看

解码输出见 5.1 的两种布局。要 `bb_project_open` 打开，需要先补 `ysm.json`（参考 `dist/bb-agent-app/templates/ysm_default/ysm.json`）。

### 5.4 语料的关键实测结论

**全部写在两个地方**：
- `packages/dsh-blockbench-agent/reference/ysm-corpus-rules.md`（规则速查）
- `docs/20`、`docs/21`、`docs/21a/b/c`（详细拆解）

最重要几条：

| 指标 | 现代 YSM 中位 |
|---|---|
| 方块总数 | 744（p25 434 / p75 1074） |
| 旋转方块占比 | 85% |
| 薄片（<0.5 厚）占比 | 26% |
| 方块特征尺度 | 1.38 单位 |
| 总高/头高 | **7.31** |
| 肩宽/头宽 | **1.01** |
| 胯宽/头宽 | **0.69** |
| 头发厚度 | **恒 1.00**（49.2% 落在 ±0.05） |
| 眼睛 | 纯色方块叠层（82% 贴图是纯色），眼睑板 2.0×1.5（横向扁） |

### 5.5 语料分析的三个坑（务必知道）

1. **`rotation` 不能无条件重放**——重放 yujin 的方块旋转会把块甩到半径 30。按尺寸+骨骼名分析。
2. **`ysmGlow*` 是复制出来的自发光层**（82/169 模型有），会虚高方块数。
3. **3 个模型有整骨架副本**（`X` 与 `X2`），计数要除重。

### 5.6 官方包与其它模型

- `material/refmodels/ysm/`：**9 个包** = 6 个官方 CC0 模板 + 3 个 wine_fox 角色包（旧派参考）。
- `material/refmodels/maid/`：874 文件 / 446 条，其中 **325 个角色**（其余家具/载具/PvZ）。
- `material/refmodels/bbmodel/`：**62 对**舰娘实体模型（含建筑/载具，人物参考价值偏低）。
- 索引：`inventory_ysm.json` 已修正为 **169 条**；`inventory_parts.json` 仍是 **161 条**历史派生统计；`inventory_maid.json` 446 条。

---

## 六、文档索引（`docs/`）

### 现行

| 组 | 文档 |
|---|---|
| **系统设计** | 01 总体架构 / 02 通信协议 / 03 Tool-API / 04 闭环状态机 / 05 工程难点 / 06 路线图 |
| **视口反馈** | 07 视口实时反馈方案（眼睛 A+B，已冻结） |
| **建模知识** | 10 教程精要 / 11 参考图管线 / 12 建模规格 |
| **分层与委派** | 13 能力探测 / 14 T1 SAM2 / 15 T2 安装 / 16 T2 完整分层 / 17 委派规范 / 18 官方基准与深度搜索 |
| **★ 现代语料** | **20** 169 模型大规模拆解 / **21** 现代化建模总纲 / **21a** 衣服与裙子 / **21b** 身体曲线 / **21c** 头发与面部 |
| **测试证据** | `docs/test-evidence/`（0.9.1/0.9.2 复核证据，`README.md` 说明） |

### 归档（`docs/archive/`，不随现状维护）

- `08-语料挖掘与技能归纳.md`、`09-模型结构深挖.md`、`19-参考模型拆解-脸型眼睛与曲线.md`（旧拆解，已被 20/21 取代）
- `M0-report.md` / `M0-report-safe.md` / `M0-report-template.md`（2026-10 M0 报告）
- `test-evidence-0.4.0/`（0.4.0 时期证据）
- `BUGS-deepseek-fish-testmodel.md`（历史测试模型 BUG 记录）
- `cleanup-2026-11-07.md`（本次清理记录）
- 首页说明：`docs/archive/README.md`

---

## 七、技能文档（AI 建模时读这个）

`packages/dsh-blockbench-agent/skills/blockbench-ysm-artist.md`（**v2，2026-11-07 重构，约 400 行**）

> v2 把此前 31 次补丁式修改合并成一份自洽手册，消除了旧 skill / playbook / corpus-rules 之间的
> 头身比（7.31 vs 4.87）、发片厚度、贴图尺寸、工具行为等矛盾。配套三份文档：
> `reference/blockbench-ysm-playbook.md`（操作/格式）、`reference/ysm-corpus-rules.md`（数字出处）、
> `assets/delegation-brief.md`（任务书/回报格式）。

**章节结构**：

| 节 | 内容 |
|---|---|
| §0 | 强制委派 + 十条流水线（canon → 深搜 → **立绘拆分** → spec → 开项目 → 档位/剪影/比例 → 建模 → 贴图 → **逐部件检查** → 出厂） |
| §1 | 14 条铁律（含"禁止模板换色""先算后做""美术亲自看图"） |
| §2 | 参考阶段：官方基准 → deep 搜索 → 对照表逐格判读 → **T1/T2 立绘拆分（分档强制）** → spec → 开项目（清示例模型/rest rotation） |
| §3 | 从总到分四层法 + **头身比双口径**（7.31 方块 / 4.87 视觉）与肩宽/胯宽/头宽 |
| §4 | 部件配方：脸/眼（纯色方块叠层）/发（等粗条带+发色分档）/角（需超出头发）/身体/服装/配饰 |
| §5 | 贴图与配色（尺寸/texel/纯色分档/UV 三写法） |
| §6 | **逐部件检查（强制）**：8 组 isolate 清单 + 整体验收 + 反模板检查 |
| §7 | 动画 |
| §8 | 保存/导出/回滚 |
| §9 | YSM 约束、骨架树/命名、arm、动画槽位、MoLang |
| §10 | 工具坑（致命静默类 + 效率类） |
| 附录 | 41 暴露工具速查、常见美术错误 |

---

## 八、已知限制与未完成项

| 项 | 状态 | 说明 |
|---|---|---|
| `tools/bedrock_render.py` | **未完成** | 自己写的软渲染器，骨骼 pivot 语义没调对，渲染会散架。**用 BAE 渲染即可，不要依赖它** |
| `closeup` 视图 | **已修** | `focus.padding` 已修；局部审查仍推荐 `isolate` + `zoom` |
| `arm.json`（第一人称手臂） | 无法重建 | 没有切换 Blockbench 工程 tab 的 API |
| T1/T2 分层 | **T1 已内置；T2 已装并跑通（2026-11-07）** | T1 首次自动下 SAM2 ~59MB 到 `~/.dsh-blockbench-agent/sam2`；T2 已安装到 `~/.dsh-seethrough`（ComfyUI 0.44.0 + See-through，权重 12.5GB），首次分层约 22m43s（含下载），之后约 1–3 分钟，**实测输出 29 个语义层**；`bb_seg_run` 不产 PSD（需前端/ag-psd） |
| `dist/` 与源码同步 | **手工** | 改 bridge 后必须同步到 dist / 用 assemble 重建，见 §3.3 |
| `locale/*.json` | 加载未验证 | 插件 package.json 已导出 locale 文件，但 dsh 侧实际加载路径/时机未做端到端验证 |
| `spec/` 契约漂移 | 已知 | 手工维护契约源，与 `index.js` 存在 17 个工具参数漂移；以 `index.js` 实际 schema 为准 |
| 发布包 | 待重打 | 0.4.0 为历史发布；0.9.2 发布包待 `package-release.mjs` 重新生成 |

---

## 九、开发约定（踩过的坑）

1. **工具 schema 里 `type:'object'` 必须写 `additionalProperties`**，否则所有工具消失。
2. **不要用联合类型** `type:['string','array']`，用单类型 + 逗号分隔更安全。
3. **Blockbench 里 cube 的 Z 轴滚转旋向与右手定则相反**——要 A 字外扩写 `rotation[2] = -pitch`。
   （这个 bug 导致前六版裙子一直是"漏斗"）
4. **写代码文件用 `write`/`edit` 工具**，不要用 PowerShell `Set-Content -NoNewline`（会写坏中文和换行）。
5. **调 bb_* 前确认 BAE 是 idle 状态**，否则可能撞上上一轮的项目。
6. **每次可见改动后看图**；连续 3 次 `no_visible_change` 会触发 no-progress，先 `bb_restore`。
7. **改 `packages/**` 后记得同步/重装**：插件 lib 重装插件、bridge 同步 dist、md 重装插件（见 §3.3）。

---

## 十、推荐工作流（接手的第一个任务）

```
1. skill 加载 blockbench-ysm-artist，完整读一遍（并读 playbook / corpus-rules）
2. bb_ref_canon({character})          拿官方基准
3. bb_ref_search({depth:"deep"})      大面积搜图（902 候选/2s）
4. bb_ref_collect()                   下载 → 去重 → 编号对照表，**真的看**
5. bb_seg_probe → bb_seg_lite         立绘拆分（标准档必做；精修档再加 T2）
6. bb_spec_save({spec})               固化规格 → 拿到构建计划
7. bb_session_start({mode:"new_ysm", resolution:[512,512]}); 清空示例模型/处理 rest rotation
8. 按四层方法建模
9. 每个部件 bb_look({isolate, zoom}) 局部检查（8 组清单）
10. bb_validate → bb_save_project → bb_export_ysm → 成品 4 视角图
```

**当前测试模型：`togawa-sakiko`（首轮验收已完成，2026-11-07，带已知降级项）。**

明日方舟 × BanG Dream! Ave Mujica 联动干员 **丰川祥子**（官方罗马音 **Togawa Sakiko**），指定皮肤 **「旋律的主人 / Master of Melodia」**（卡普里尼双大角、黑银冷色演出服）。

| 项 | 实测（T2 + v2 优化后） |
|---|---|
| 骨架 / 方块 | 70 bones / **401 cubes**（首轮 217 → T2 修理 355 → v2 优化 401） |
| 贴图 | 2 × 512²（default / blue，未改） |
| 动画 | 303（未触碰） |
| 校验 | `bb_validate` ok=true、**0 error**；3 warning（512 贴图 ×2、可选 ViewLocator 缺省） |
| 导出 | 32 文件 + `export-manifest.json`；zip 489,046 B |
| 渲染 | `models/togawa-sakiko/artifacts/renders/r0016/{front,back,left,iso_fr}_768.png`；前后对比 `artifacts/t2-repair/before-after-sheet.png` |
| 工程 / 规格 | `models/togawa-sakiko/pack/`、`specs/丰川祥子_Togawa_Sakiko（Oblivionis）.json/.md` |
| 预算（T2 修理轮） | edits 15、renders 13、restore 0 |

**T2（See-through 29 层）逐细节修理（2026-11-07）**：T2 已完整安装（ComfyUI 0.44.0 + 权重 12.5GB，`~/.dsh-seethrough`，保持运行）；官方立绘 → 29 语义层 + crop_head 23 层。按层对照后 P1–P5 全部落地：双角重建为 **7.00×7.76 单位/只**（6 棱环+金尖/金根环，42 块）、双马尾 3 层错位垂到 y=17.2、白衬裙整圈 + 21 片落地拖尾、靴筒/鞋跟/2 扣带、胸衣面板改形。详见 [`models/togawa-sakiko/T2-REPAIR.md`](models/togawa-sakiko/T2-REPAIR.md) 与 [`T2-INSTALL-REPORT.md`](models/togawa-sakiko/T2-INSTALL-REPORT.md)。

已知降级（T2 + v2 优化后仍存在）：头发仍"薄板/栅栏"感、背面发束偏直（最大剩余项）；角已连续但尖端偏钝、金环偏小；背面拖尾片间有缝、裙蕾丝仅 2 层；腿无小腿肚/手臂无肘收放；头身比约 6.5 偏 Q；无官方背面参考；`arm.json` 与 `blue.png` 仍是模板。

**v2 美术优化（2026-11-07 晚）**：双角改为**正面连续扁平螺旋带**（每侧 25 块：20 段带片 + 3 肋 + 金尖/根环，只绕 Z 旋转，椭圆螺旋 C=(4.30,40.35)、rx 2.20→0.90 / ry 4.20→1.55、扫角 −330°、带面 1.90→0.75、z 厚 1.40→0.70）；背面长发每侧 4 组窄束垂到 y=15.3；眼睛改菱形（每眼 10 块：斜置菱形虹膜/瞳孔/高光/眼睑）；角根左右分离 ±2.1。详见 [`MODEL-V2-REFINE.md`](models/togawa-sakiko/MODEL-V2-REFINE.md)。

历史测试模型（deepseek-fish、sakiko-melodia）已按要求清理（sakiko-melodia 在提交 `8f3a09f` 删除；deepseek-fish 目录于 2026-11-07 删除，BUGS 记录存 `docs/archive/BUGS-deepseek-fish-testmodel.md`）。

---

## 十一、Git

- 仓库：`https://github.com/yan-mc/blockbench-ysm-agent`
- 分支：`main`
- 当前提交：见 `git log -1`
- 大文件（`vendor/`、`material/`、`dist/`、`release/`、`workspace/`）在 `.gitignore`，**不入库**；
  `models/` 只提交 `pack/` 与 `specs/`（`refs/`、`exports/`、`artifacts/`、`checkpoints/`、`logs/`、`.bb/` 均忽略）

---

## 十二、接手检查清单

- [ ] `bb_session_status` 返回 `gpu_ok: true`（或 `/bb-status` 正常）
- [ ] DSH 工具列表里有 **41 个暴露的 `bb_*`**（43 定义）
- [ ] skill `blockbench-ysm-artist` 可加载
- [ ] `node --test packages\dsh-blockbench-agent\test\*.test.mjs` **62 通过**
- [ ] `node packages/dsh-blockbench-agent/test/host-smoke.mjs` **35 步 PASSED**（schema lint 41 工具）
- [ ] `material/refmodels/ysm_decoded/` 有 **169 个目录**（其中 8 个 JSONC）
- [ ] `tools/ysmparser/YSMParser.exe` 存在
- [ ] `dist/bb-agent-app/agent/` 4 文件 sha256 与 `packages/bb-agent-runtime/agent/` 一致
- [ ] `spec/generate_spec.py` 重跑 0 diff

全部通过即可开始建模。
