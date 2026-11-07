# Release 0.9.2 · 发布说明（草稿）

> 发布日期：2026-11-07（草稿，待 Lead 定稿）
> 上一版本：0.9.1
> 本仓库版本：根 `package.json` / `packages/dsh-blockbench-agent` / `packages/bb-agent-runtime` = **0.9.2**；BAE 应用版本沿用上游 Blockbench：`blockbench-agent-runtime@5.2.2-agent.0`。

---

## 1. 版本亮点

### 1.1 T2 完整分层（See-through）实装并跑通

- ComfyUI 0.44.0 + See-through 节点安装执行器（`bb_seg_install`）与完整分层调用（`bb_seg_run`）全部落地。
- **实测 23–29 个语义层**：GenerateLayers 输出 24 层后，PostProcess 按 depth 拆分/聚类，官方立绘得 **29 层**（back hair / bottomwear / ears / eyebrow / eyelash / eyewhite / face / footwear / front hair / handwear / headwear / irides / legwear / mouth / neck / neckwear / nose / objects / tail / topwear / wings 等），`crop_head` 头部特写得 **23 层**；**层名以返回的 `layers.json` 为准**，不要假设固定层数。
- 首次运行约 22 分 43 秒（含 12.5GB 权重下载），之后约 1–3 分钟；安装体积约 6.5GB（ComfyUI 便携版 + 依赖），权重落在 HuggingFace cache。
- **不自动产 PSD**：服务端节点只写层 PNG + `layers.json`（前端按钮才生成 PSD）；仓库内已用 ag-psd 复刻并校验层序，工具描述已据实修正。

### 1.2 立绘拆分（T1）与参考图管线成为标准步骤

- T1 SAM2.1 ONNX 分割（`bb_seg_lite`）：约 59MB，CPU 可跑，首次自动下载到 `~/.dsh-blockbench-agent/sam2`。
- 参考图三步管线：`bb_ref_canon`（官方基准：百科文字 + 官方图）→ `bb_ref_search`（多源深度搜索）→ `bb_ref_collect`（下载 + 精确/感知去重 + 编号对照表），把"看图判断"变成可逐格指认的证据链。
- 分档执行：标准档 T1 必做，精细档再加 T2；环境不满足时允许降级但必须在报告写明原因。

### 1.3 渲染自检：isolate / zoom 局部核对

- `bb_look` / `bb_render_views` 支持 `isolate`（只渲染指定部件）与 `zoom`（额外放大），用于逐部件核对头/发/角/袖口等遮挡细节。
- 配套：多格拼图、转台、动画采样、closeup+SSAA、watchdog-v2（空图/触边/无变化检测）、512px 附件缩略图与 token 预算。

### 1.4 Skill v2 与建模方法沉淀

- `blockbench-ysm-artist` skill 更新：isolate 局部核对流程、眼睛"实心方块按深度堆叠"而非画贴图的 doctrine、T2 逐层修理工作流。
- 语料规律沉淀进 `reference/`（骨架层级、部位方块配额、头发/裙子结构、身体曲线、边角处理）。

### 1.5 模型案例

- `models/togawa-sakiko`（丰川祥子，明日方舟×BanG Dream 联动皮肤「旋律」）：按 T2 29 层逐层修理，双角重建为 7.00×7.76 单位/只（6 棱环 + 金尖/金根环，42 块）、双马尾 3 层错位垂到 y=17.2、白衬裙整圈 + 21 片落地拖尾、靴筒/鞋跟/2 扣带、胸衣面板改形。
- **v2 美术优化（最终 401 块）**：双角改为**正面连续扁平螺旋带**（每侧 25 块、只绕 Z 旋转、椭圆螺旋 rx 2.20→0.90 / ry 4.20→1.55、扫角 −330°、带面 1.90→0.75、z 厚 1.40→0.70，2D 预检后再上模）；背面长发每侧 4 组窄束垂到 y=15.3；眼睛改菱形叠层（斜置虹膜/瞳孔/高光/眼睑）。
- 展示图：[`docs/assets/showcase/`](../docs/assets/showcase/)（最终四视图 / 217→401 前后对比 / T2 29 层 / 头部细节）；过程报告见 `models/togawa-sakiko/`。
- 早期测试模型「DeepSeek 鲸鱼娘 / 蓝色大肥鱼」已完成展示用途并清理。

---

## 2. 变更 / 修复清单（0.9.2）

### 契约与工具定义

- **修复 spec ↔ index.js 参数漂移（17 处）**：以 `index.js` 实际 schema 为准对齐 `spec/generate_spec.py`，重新生成 `spec/tool-manifest.json`。
  - 移除未进入实现的模型参数（`gender` / `template` / `cursor` / `include_siblings` / `atomic` / `make_active`(保留并入实现) / `include_preview` / `checkpoint` / `profile` / `include` / `grid` / `resync` / `message` / `shading` / `show_gizmos` / `pose` / `inline` 等）。
  - 补齐已实现但 spec 缺失的参数：`bb_look.isolate/zoom`、`bb_render_views.isolate/zoom/attach_size`、`bb_render_texture.attach_image`。
  - `expected_revision` 明确为 **DBA 自动注入**的内部参数，不再列入模型可见 schema。
- **补齐三个模型可传参数**（bridge 已支持，此前 schema 未暴露）：`bb_project_open.save_current`、`bb_texture_create.make_active`、`bb_texture_patch.return_palette`。
- **描述与实测对齐**：`bb_seg_run` 不再声称固定 24 层/自动产 PSD，改为"实测 23–29 层、以 layers.json 为准、不自动产 PSD"；`bb_seg_install` 体积估算由"约 1.8GB + 2GB"改为"约 6.5GB 安装 + 12.5GB 首次权重"。

### 代码清理

- 删除死代码：`packages/dsh-blockbench-agent/ws-smoke-test.mjs`（import 路径已破损、指向旧 prototype 目录）、`packages/bb-protocol/`（仅有 package.json、`exports` 指向不存在的 index.js，无任何引用）。
- `.gitignore` 补充 `__pycache__/`、`*.pyc`；移除误入库的 Python 缓存。
- 版本号统一：根/插件/runtime 三个 `package.json`、`bridge` 两处握手、Host `/bb-agent/status` 全部为 **0.9.2**。

### 文档

- 修正 T2 相关数字：29 层实测、安装/权重体积、PSD 说明（docs/13、docs/16、README、MANUAL、docs/03）。
- 统一工具面数字：**43 个 `bb_*` 定义 / 实际暴露 41 个**（`bb_show_gui`、`bb_hide_gui` 默认由 `/show` `/hide` 命令替代）、**56 个 bridge 方法 / 7 个事件**、**62 个单测**、**host-smoke 35 步**。
- 清理 `bb-protocol` 残留目录树/架构描述。
- 新增本文件与 `docs/test-evidence/hosttest-result-0.9.2.json`（发布前基线证据）。

---

## 3. 升级说明

### 从 0.9.1 升级

1. 用 0.9.2 发布包替换 `dsh-blockbench-agent/` 与 `bb-agent-app/`（或从仓库执行 `node packages/bb-agent-runtime/scripts/assemble.mjs` 重建 BAE）。
2. 更新 profile 里 `cordis.patch.yml` 的 `workspaceRoot` / `executable` / `appPath` / `pluginPath` 为你的本机路径（仓库默认值是本机绝对路径，仅作示例）。
3. 重启 dsh（或重载插件）。工具面为 41 个（另 2 个 GUI 工具由 `/show` `/hide` 命令接管，`exposeGuiTools:false` 为默认值）。
4. T2 已安装用户**无需重装**：保持 ComfyUI 运行并把 `comfyUrl` 写进插件配置即可；本次只改了工具描述与参数契约，未改 ComfyUI 工作流。

### 从 0.4.0 升级

- 建议按全新安装走一遍（工具面、协议、模板、保存/导出逻辑变化较大）；旧的 `release/bb-agent-0.4.0-*` 仅作历史参考。

### 配置项速查

- `workspaceRoot`：模型工作区（每个项目一目录）。
- `executable` / `appPath` / `pluginPath`：Electron 与 BAE 应用路径。
- `comfyUrl` / `segInstallDir`：T2 分层（可选增强）。
- `exposeGuiTools`：默认 `false`；需要模型直接开 GUI 时再打开。
- `autoLook` / `sessionImageBudget` / `maxLiveImages`：自动附图与图史压缩预算。

---

## 4. 验证（0.9.2 发布前基线）

| 项 | 结果 |
|---|---|
| 单元测试 `node --test packages/dsh-blockbench-agent/test/*.test.mjs` | **62/62 通过**（6 个文件：imageprune 13 / refcanon 9 / segprobe 10 / spec 17 / tool-schema 5 / viewsheet 8） |
| Host 集成冒烟 `node packages/dsh-blockbench-agent/test/host-smoke.mjs` | **35 步全过**，schema lint 检查 **41** 个暴露工具，5 个命令 |
| `python spec/generate_spec.py` + `git diff -- spec/` | 生成结果与提交一致（无漂移） |
| dist 与源码 | `agent/` 四件套 sha256 一致（bridge 握手版本已同步） |
| 全量回归 `npm run test` | 0.9.1 已由 Lead 复跑 6/6（`docs/test-evidence/test-all-0.9.1.log`）；0.9.2 未改动渲染/导出主链路 |

复现：

```powershell
# node 不在 PATH 时用 DSH 自带 node
$node = "C:\Users\28988\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe"
& $node --test packages\dsh-blockbench-agent\test\*.test.mjs
& $node packages\dsh-blockbench-agent\test\host-smoke.mjs
python spec/generate_spec.py
```

---

## 5. 已知限制

1. **美术验收未完成**：`togawa-sakiko` v12 仍是"工程成功、美术未达标"——头发薄板/栅栏感（最大剩余项）、背面拖尾片间有缝、裙蕾丝密度仅 2 层、腿无小腿肚/手臂无肘收放、头身比 6.21 偏 Q、无官方背面参考（背面为推断）、`arm.json` 与 `blue.png` 仍是模板。
2. **PSD 不在工具链内**：`bb_seg_run` 只出层 PNG + layers.json；PSD 需前端/ag-psd 复刻。
3. **T2 环境门槛**：需 NVIDIA 显卡（Pascal 及更早不支持 NF4）、显存 ≥6GB、磁盘充足；首次 12.5GB 权重下载耗时较长。
4. **分发形式**：无 electron-builder 安装器与代码签名，正式分发为 zip 便携包；本次 0.9.2 发布包需用 `package-release.mjs` 重新生成。
5. **locale 加载未验证**：`locale/*.json` 随包分发，但 DSH 是否自动加载尚未实测（见 HANDOVER 已知限制）。
6. **契约校验未入 CI**：`spec/generate_spec.py` 目前只支持"生成"，未提供 `--check`；建议后续在 CI 加"生成后 git diff 必须为空"。
7. **测试证据时效**：全量回归证据为 0.9.1 时期（`docs/test-evidence/`），0.9.2 仅复跑单测 + host-smoke 基线。
