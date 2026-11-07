# 交接班档案 · YSM × Blockbench 无头建模 Agent

> 最后更新：2026-11-07
> 插件版本：**0.9.1**（43 个工具）
> 本文件是接手这个项目的第一份必读材料。设计细节见 `docs/`，使用方法见 `MANUAL.md`。

---

## 一、这是什么

一套让 AI 在**后台 Blockbench** 里建模、贴图、做动画、渲染自检、导出 YSM 皮肤的资源包的工具链。

- **DSH 插件**（`@local/dsh-blockbench-agent`）：把 43 个 `bb_*` 工具注册给 AI
- **BAE 运行时**（Blockbench Agent Engine）：隐藏的 Electron 窗口 + WebSocket JSON-RPC + 离屏渲染
- **技能文档**：教 AI 怎么建模（含 169 个现代模型实测出来的规范）
- **参考语料**：169 个解密后的现代 YSM 模型 + 325 个女仆模组模型 + 62 个舰娘模型

---

## 二、目录地图（所有东西都在 `F:\Deepseek_harness\blockbench` 下）

```
F:\Deepseek_harness\blockbench\
│
├── HANDOVER.md              ★ 本文件（交接班档案）
├── README.md                  项目介绍与功能列表
├── MANUAL.md                  使用手册
├── SETUP.md                   安装步骤
├── ENGINEERING.md             工程说明
├── FOLDER-MAP.md              目录地图（简版）
├── docs/                      ★ 设计文档 01–21c（27 份，见 §六）
├── spec/                      机器可读契约（tool-manifest.json / bridge-methods.json）
│
├── packages/                  ★ 源码
│   ├── dsh-blockbench-agent/     DSH 插件（host 侧）
│   │   ├── index.js              43 个工具定义
│   │   ├── lib/                  工具实现（refsearch/refcanon/segprobe/seglite/seginstall/segcomfy…）
│   │   ├── skills/               ★ 技能文档（AI 读这个）
│   │   │   └── blockbench-ysm-artist.md
│   │   ├── reference/            ★ 参考手册（AI 建模时查）
│   │   │   ├── blockbench-ysm-playbook.md
│   │   │   └── ysm-corpus-rules.md
│   │   ├── assets/               委派任务书模板、SAM2 推理脚本
│   │   └── test/                 62 个单元测试 + host-smoke
│   └── bb-agent-runtime/         BAE 运行时（Electron 主进程 + bridge）
│       └── agent/bb-agent-bridge.js   ★ 所有 bridge 方法都在这里
│
├── dist/                      构建产物（bb-agent-app，BAE 实际运行的是这份）
├── vendor/                    第三方（Blockbench 3.7.5、YSM-Utils-Plugins）3.6GB
├── tools/                     ★ 独立工具
│   ├── ysmparser/YSMParser.exe  ★ .ysm 解密器（OpenYSM/YSMParser v0.3.6）
│   └── bedrock_render.py        软渲染器（未完成，见 §八）
│
├── material/refmodels/        ★ 参考模型语料（371MB）
│   ├── ysm_decoded/            169 个解密后的现代 YSM 工程（1156 文件，233MB）
│   ├── maid/                   325 个女仆模组角色模型（JSON+PNG，874 文件）
│   ├── bbmodel/                62 个舰娘 bbmodel
│   ├── ysm/                    9 个未加密的 YSM 包
│   └── inventory_*.json        索引（方块数/骨骼数/尺寸分布）
│
├── research/                  研究证据（Blockbench 核心、YSM 格式、DSH 集成）
├── media/                     演示素材
├── release/                   发布物
└── workspace/                 hosttest 运行产物
```

**模型工程目录（BAE 的 workspace）**：`models/deepseek-fish/`
—— 所有 `bb_project_open({pack_dir})` 的路径都**相对这个目录**，不是仓库根。

---

## 三、怎么跑起来（从零到能建模）

### 3.1 装插件

```powershell
# 插件以 link 方式装进 DSH profile
# 在 DSH 里执行：
plugin_manager install_bundle target=F:/Deepseek_harness/blockbench/packages/dsh-blockbench-agent
```

验证：DSH 里应能看到 `bb_*` 工具（43 个）和 skill `blockbench-ysm-artist`。

### 3.2 让 BAE 启动

第一次调用任意 `bb_*` 工具（如 `bb_session_status`）时，host 会自动拉起隐藏的 Electron 窗口。
`gpu_ok: true` 表示离屏渲染可用。

### 3.3 改代码后怎么生效

| 改了什么 | 怎么生效 |
|---|---|
| `packages/dsh-blockbench-agent/index.js` 或 `lib/` | 重装插件：`plugin_manager remove_bundle` → `install_bundle` |
| `packages/bb-agent-runtime/agent/*.js`（bridge） | **必须重启 BAE**：杀光 `electron.exe` → `Copy-Item packages\bb-agent-runtime\agent\*.js dist\bb-agent-app\agent\ -Force` → 再调任意 `bb_*` |
| `skills/` 或 `reference/` 下的 md | 重装插件即可（skill 在插件激活时加载） |

> ⚠️ **dist 在 BAE 运行时是锁住的**，必须先杀 electron 才能覆盖。

### 3.4 改完必须验证

```powershell
cd F:\Deepseek_harness\blockbench
node --test packages\dsh-blockbench-agent\test\*.test.mjs     # 62 个单测
node packages\dsh-blockbench-agent\test\host-smoke.mjs        # 真实 schema 校验（41 工具）
python spec\generate_spec.py                                   # 重生成契约
```

> ⚠️ **工具 schema 一旦非法，所有工具和 skill 会从 DSH 里一起消失**
> （曾经因为 `type:'object'` 没写 `additionalProperties` 全挂过一次）。
> 改 schema 后必须跑 host-smoke。

---

## 四、43 个工具分组速查

| 组 | 工具 | 用途 |
|---|---|---|
| **会话** | `bb_session_status` `bb_session_start` `bb_project_open` `bb_project_close` | 开/关工程 |
| **读** | `bb_scene` `bb_get_element` `bb_revisions` `bb_diagnostics` | 看结构/骨骼/方块/UV |
| **写** | `bb_apply_model_patch` `bb_batch` `bb_checkpoint` `bb_restore` | 加骨/加块/改块 |
| **贴图** | `bb_texture_patch` `bb_texture_read` `bb_texture_render`→`bb_render_texture` `bb_texture_import_png` `bb_texture_export_png` `bb_texture_create` `bb_texture_layer` `bb_texture_pbr` | 画/读/导入导出/图层/PBR |
| **看** | `bb_look` `bb_render_views` `bb_orbit` `bb_camera` `bb_anim_check` | ★ 渲染自检，**支持 isolate+zoom 局部审查** |
| **参考图** | `bb_ref_canon` `bb_ref_search` `bb_ref_collect` | 官方基准 → 深度搜图 → 对照表 |
| **规格** | `bb_spec_save` `bb_spec_load` | 建模规格与构建计划 |
| **分层** | `bb_seg_probe` `bb_seg_install` `bb_seg_lite` `bb_seg_run` | T0/T1/T2 立绘分层 |
| **动画** | `bb_animation_create` `bb_animation_patch` `bb_animation_delete` `bb_animation_list` | 关键帧/控制器绑定 |
| **交付** | `bb_validate` `bb_save_project` `bb_export_ysm` | 校验/保存/导出 zip |
| **GUI** | `bb_show_gui` `bb_hide_gui`（默认不暴露） | 用户接管 |

### 两个最常用的

```
bb_look({isolate:"AllHead", zoom:2.5, cells:[{camera:{azimuth:0,elevation:4}},{camera:{azimuth:40,elevation:10}}]})
bb_apply_model_patch({ops:[{op:"add_cube", bone:"Head", name:"Bang1", origin:[...], size:[...]}]})
```

**`isolate` 是关键能力**：只渲染指定骨骼子树，其余隐藏并自动对焦，`zoom` 再放大。
检查单个手臂/头发/裙子时用它，不要每次都渲染全身。

---

## 五、参考语料怎么用

### 5.1 语料是什么

`material/refmodels/ysm_decoded/` 里有 **169 个解密后的现代 YSM 工程**，来自本机 MC 库的
520 个 `.ysm`（去重后 169 个唯一模型）。这些是**最重要的参考源**——现代 YSM 模型的真实基准。

**为什么能解密**：YSM 模型是加密容器，用 `tools/ysmparser/YSMParser.exe`（OpenYSM 开源项目）
可以解出 `main.json`（bedrock 几何）+ 贴图 + 动画。

### 5.2 从 .ysm 重新解码

```powershell
# 1. 把 .ysm 收集到输入目录
# 2. 解码
tools\ysmparser\YSMParser.exe -i <输入目录> -o <输出目录>
```

实测：169 个文件 **1.3 秒**解完，0 失败。

### 5.3 打开语料模型看

解码输出有两种布局，都要处理：
- 扁平：`{名字}/main.json` + `{名字}/*.png`
- 标准包：`{名字}/models/main.json` + `{名字}/textures/*.png`

要 `bb_project_open` 打开，需要先补 `ysm.json`（参考 `dist/bb-agent-app/templates/ysm_default/ysm.json`）。

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

---

## 六、文档索引（`docs/`）

| 组 | 文档 |
|---|---|
| **系统设计** | 01 总体架构 / 02 通信协议 / 03 Tool-API / 04 闭环状态机 / 05 工程难点 / 06 路线图 |
| **视口反馈** | 07 视口实时反馈方案（眼睛 A+B，已冻结） |
| **建模知识** | 08 语料挖掘 / 09 模型结构深挖 / 10 教程精要 / 11 参考图管线 / 12 建模规格 |
| **分层与委派** | 13 能力探测 / 14 T1 SAM2 / 15 T2 安装 / 16 T2 完整分层 / 17 委派规范 / 18 官方基准与深度搜索 |
| **★ 现代语料** | **19** 第一轮拆解（部分结论已作废）/ **20** 169 模型大规模拆解 / **21** 现代化建模总纲 / **21a** 衣服与裙子 / **21b** 身体曲线 / **21c** 头发与面部 |

---

## 七、技能文档（AI 建模时读这个）

`packages/dsh-blockbench-agent/skills/blockbench-ysm-artist.md`

**核心方法：从总到分四层**（§2.2）

```
第1层 风格档位   —— 定体素尺度，全模型贯彻
第2层 剪影比例   —— 轮廓/头身比/体积
第3层 部件形态   —— 长什么样、曲面往哪走
第4层 方块实现   —— 最后才决定用几块
```

**关键章节**：
- §2.3 实测参考值（比例表）
- §3.1 脸与五官（含 3.1.4 眼睛纯色叠层、3.1.5 isolate 局部检查）
- §3.2 头发（等粗条带链）
- §3.4 服装（5 种裙拓扑，圆环已淘汰）
- §5 验收清单（**整体优先**）
- §10 常见错误（含 Blockbench Z 轴旋向与右手定则相反）

---

## 八、已知限制与未完成项

| 项 | 状态 | 说明 |
|---|---|---|
| `tools/bedrock_render.py` | **未完成** | 自己写的软渲染器，骨骼 pivot 语义没调对，渲染会散架。**用 BAE 渲染即可，不要依赖它** |
| `closeup` 视图 | **有 bug** | `focus.padding` 只移动对焦点不改变缩放。**改用 `isolate` + `zoom` 代替** |
| `arm.json`（第一人称手臂） | 无法重建 | 没有切换 Blockbench 工程 tab 的 API |
| T1/T2 分层 | 需要额外安装 | T1 需 SAM2（首次自动下 59MB）；T2 需 ComfyUI + 权重（约 3GB） |
| `dist/` 与源码同步 | **手工** | 改 bridge 后必须手工复制到 dist，见 §3.3 |
| 文档 08/09 | 已过时 | 被 20/21 取代 |

---

## 九、开发约定（踩过的坑）

1. **工具 schema 里 `type:'object'` 必须写 `additionalProperties`**，否则所有工具消失。
2. **不要用联合类型** `type:['string','array']`，用单类型 + 逗号分隔更安全。
3. **Blockbench 里 cube 的 Z 轴滚转旋向与右手定则相反**——要 A 字外扩写 `rotation[2] = -pitch`。
   （这个 bug 导致前六版裙子一直是"漏斗"）
4. **写代码文件用 `write`/`edit` 工具**，不要用 PowerShell `Set-Content -NoNewline`（会写坏中文和换行）。
5. **调 bb_* 前确认 BAE 是 idle 状态**，否则可能撞上上一轮的项目。
6. **每次可见改动后看图**；连续 3 次 `no_visible_change` 会触发 no-progress，先 `bb_restore`。

---

## 十、推荐工作流（接手的第一个任务）

```
1. skill 加载 blockbench-ysm-artist，完整读一遍
2. bb_ref_canon({character})          拿官方基准
3. bb_ref_search({depth:"deep"})      大面积搜图（902 候选/2s）
4. bb_ref_collect()                   下载 → 去重 → 编号对照表，**真的看**
5. bb_spec_save({spec})               固化规格 → 拿到构建计划
6. bb_session_start({mode:"new_ysm", resolution:[512,512]})
7. 按四层方法建模
8. 每个部件 bb_look({isolate, zoom}) 局部检查
9. bb_validate → bb_save_project → bb_export_ysm
```

**参考语料随时可查**：`material/refmodels/ysm_decoded/` 里 169 个现代模型是最好的老师。

---

## 十一、Git

- 仓库：`https://github.com/yan-mc/blockbench-ysm-agent`
- 分支：`main`
- 当前提交：见 `git log -1`
- 大文件（`vendor/`、`material/`、`models/`、`dist/`）均在 `.gitignore` 里，**不入库**

---

## 十二、接手检查清单

- [ ] `bb_session_status` 返回 `gpu_ok: true`
- [ ] DSH 工具列表里有 43 个 `bb_*`
- [ ] skill `blockbench-ysm-artist` 可加载
- [ ] `node --test packages\dsh-blockbench-agent\test\*.test.mjs` 62 通过
- [ ] `node packages\dsh-blockbench-agent\test\host-smoke.mjs` PASSED
- [ ] `material/refmodels/ysm_decoded/` 有 169 个目录
- [ ] `tools/ysmparser/YSMParser.exe` 存在

全部通过即可开始建模。
