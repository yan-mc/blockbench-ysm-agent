# T2（See-through 完整分层）安装与验证报告

- **项目**：`models/togawa-sakiko`（丰川祥子 / 旋律的主人立绘）
- **执行者**：t2-installer（task-7）
- **日期**：2026-11-07 20:55 → 21:47（Asia/Shanghai）
- **结论**：✅ **T2 环境安装成功、ComfyUI 运行中、首次 24/29 层完整分层成功、PSD + 分层 PNG 已交付**；全程 **0 次工具超时、0 次重试失败**。
- **硬约束遵守**：未改 `pack/`、未调用任何改模型/渲染工具、未 git、未删除任何已有文件、未用 T1 冒充 T2。ComfyUI 保持运行（PID 24708）。

---

## 0. TL;DR（关键结果一览）

| 项 | 结果 |
|---|---|
| T2 能力 | `bb_seg_probe`：`recommendedTier=t2`、`canInstall=true`、GPU RTX 4080 Laptop 12GB |
| ComfyUI | **0.44.0**（frontend 1.57.6），portable，PyTorch 2.14.1+cu130，Python 3.13.14 |
| See-through 节点 | `custom_nodes/ComfyUI-See-through`（324 文件 / 16.5MB），依赖已装齐 |
| ComfyUI 启动 | **PID 24708**，`/system_stats` **HTTP 200**（启动 29s），日志已落盘 |
| 权重 | HuggingFace cache **12.513GB / 43 文件**（约 15.5 分钟下载，一次性，已持久化） |
| 首次分层 | `sakiko_skin1.png` 832² / steps 28 → **29 个语义层**，**22 分 43 秒**（含权重下载） |
| 输出目录 | `seg/sakiko_skin1-layers/`（**61 文件 / 25.65MB**：29 层 PNG + 29 深度图 + layers.json + PSD + preview） |
| PSD | `seg/sakiko_skin1-layers/sakiko_skin1-layers.psd`（**17.28MiB，832²，29 层**）+ psd-tools 独立校验通过 |
| 可选头部特写 | `crop_head.png` 832² → **23 层**，**3 分 11 秒**（权重已缓存），`seg/crop_head-layers/`（49 文件 / 6.1MB + PSD 3.88MiB） |
| 磁盘 | C: 230.15GB → **203.08GB 剩余**（安装+权重+缓存共约 27GB） |

---

## 1. 环境与前置（20:55:49 记录）

| 项 | 值 |
|---|---|
| 平台 | win32 x64，Node v24.21.0（插件侧） |
| GPU | NVIDIA GeForce RTX 4080 Laptop GPU，12282 MiB VRAM，driver 621.14 |
| 安装目标盘 | `C:\Users\28988\.dsh-seethrough`，安装前剩余 **230.15GB** |
| ComfyUI（安装前） | 未安装：目录不存在、HF cache 不存在、端口 8188 空闲 |
| 工具链 | `git 2.55.0.windows.3`；`bsdtar 3.8.9 / libarchive 3.8.9`（**支持 7z 解压**） |
| 插件 | Blockbench Agent 0.9.1，`comfyUrl=http://127.0.0.1:8188`（默认，无需改配置） |
| 参考图 | `refs/skin/sakiko_skin1.png`（2176² 官方立绘）、`refs/skin/crop_head.png` |

T2 plan：`totalGB≈7`、`canInstall=true`、`blockers=[]`。

---

## 2. 安装过程时间线

| 时刻 | 步骤 | 结果 |
|---|---|---|
| 20:55:49 | `bb_seg_probe` | T0/T1/T2 均 ok，`recommendedTier=t2` |
| 20:56–21:01 | `bb_seg_install`（首次，被人工中断） | 7z 下载到 1,589,029,248 B 后被中断（`.part` 保留） |
| 21:05:10–21:08:52 | 系统 `curl` 单线程重下 7z（Lead 执行） | `ComfyUI_windows_portable_nvidia.7z` = **2,054,382,457 B**（1.913GiB，约 222s，≈9.3MB/s），7z 魔数 `37 7A BC AF 27 1C`(v0.4) 有效 |
| 21:10:00–21:11:31.7 | 后台 `tar -xf` 解压（保护性操作） | **62,623 文件 / 4.197GB / 91.7 秒**，EXIT=0 |
| 21:11:4x | 校验解压产物 | `python_embeded\python.exe`（3.13.14）、`ComfyUI\main.py` 存在；标准 portable 布局 |
| 21:12:0x | `bb_seg_install({confirm:true})` | ⚡ **一次成功（约 40s）**：download-comfy **skipped**「portable 已存在」、extract **skipped**、verify-comfy ok、install-node ok(git)、install-deps ok |
| 21:12:15 | 依赖实测 | torch 2.14.1+cu130（CUDA True）、diffusers 0.42.1、accelerate 1.15.0、transformers 5.21.0；site-packages 4.481GB/69,063 文件 |
| 21:12:56 | 后台启动 ComfyUI | PID 24708 |
| 21:13:23 | `/system_stats` | **HTTP 200**（启动 29s） |
| 21:13:34–21:36:17 | **首次 `bb_seg_run`** | 成功，`elapsed_ms=1,362,829`（22m43s） |
| 21:36:17 | 29 层落盘 | `seg/sakiko_skin1-layers/` |
| 21:37:36 | 补复制交付件 | `layers.json` + 29 张 `_depth.png` → workspace |
| 21:39:46 | 生成 PSD（Node + ag-psd） | 17.28MiB / 29 层 |
| 21:39:50–21:43 | PSD 独立校验（psd-tools） | 合成 mean diff **0.0812/255** → 层序正确 |
| 21:41:3x–21:43:23 | 可选 `crop_head` 分层 | 23 层，`elapsed_ms=190,819`（3m11s） |
| 21:44:49 | crop_head 交付件 + PSD | 6.1MB + 3.88MiB PSD |
| 21:47 | 本报告 | — |

**安装总体积**：`C:\Users\28988\.dsh-seethrough` = **6.54GB / 71,679 文件**
- `ComfyUI_windows_portable\` = **4.626GB / 71,678 文件**（portable 本体 62,623 + pip 新增 ≈9k）
- `ComfyUI_windows_portable_nvidia.7z` = 1.913GB（**保留未删**，遵守“不删已有文件”；可回收）

---

## 3. ComfyUI 运行状态（保持运行中）

**启动命令（= `bb_seg_install` 返回的 `paths.startCommand`）**：

```powershell
"C:\Users\28988\.dsh-seethrough\ComfyUI_windows_portable\python_embeded\python.exe" -s "C:\Users\28988\.dsh-seethrough\ComfyUI_windows_portable\ComfyUI\main.py" --listen 127.0.0.1 --port 8188
```

- **PID**：24708（2026-11-07 21:12:56 启动，工作目录 = `...\ComfyUI`）
- **健康检查**：`http://127.0.0.1:8188/system_stats` → HTTP 200
  - `comfyui_version=0.44.0`、`required_frontend_version=1.57.6`
  - `python_version=3.13.14`、`pytorch_version=2.14.1+cu130`、`embedded_python=true`
  - GPU：`cuda:0 NVIDIA GeForce RTX 4080 Laptop GPU : cudaMallocAsync`，`vram_total=12,878,086,144`，分层后 `vram_free≈10.74GB`
- **日志**：
  - stdout：`models/togawa-sakiko/artifacts/comfyui.log`
  - stderr：`models/togawa-sakiko/artifacts/comfyui.err.log`
- **启动/健康检查脚本（已落盘，可直接复用）**：
  - `models/togawa-sakiko/artifacts/start-comfyui.ps1`
  - `models/togawa-sakiko/artifacts/check-comfyui.ps1`

---

## 4. 首次权重下载（一次性，已持久化）

- 位置：`C:\Users\28988\.cache\huggingface`（`hub/` + `xet/`）
- 体积：**12.513GB / 43 文件**（无 `.incomplete` 残留）
- 耗时：21:17:30 首个权重 → 21:33:00 达到 12.513GB 并稳定（约 **15.5 分钟**，≈13.4MB/s）
- 体积曲线（后台监控 `artifacts/install-monitor.log`，每 30s 采样）：

| 时刻 | HF cache | 说明 |
|---|---|---|
| 21:14:04 | 0GB / 7f | 开始拉取 |
| 21:17:30 | 2.26GB / 13f | 第一批权重 |
| 21:18:39 | 3.05GB | |
| 21:27:15 | 7.12GB | |
| 21:30:06 | 10.83GB | |
| 21:32:26 | 11.06GB | |
| **21:33:00** | **12.513GB / 43f** | 下载完成，转入推理 |
| 21:36:25 | 12.513GB | 稳定（推理不增量） |

模型来源（日志）：LayerDiff(SDXL 系) + `frankjoshua/juggernautXL_version6Rundiffusion` + TransparentVAE + Marigold 深度（See-through 节点自动拉取）。**删除该 cache 会导致下次重新下载 12.5GB**。

---

## 5. 首次完整分层 `bb_seg_run`

**调用参数**

| 参数 | 值 |
|---|---|
| file | `refs/skin/sakiko_skin1.png`（插件 workspace 相对路径） |
| resolution | 832 |
| steps | 28 |
| timeout_sec | 3600 |
| attach | true |

**返回结果**

- `ok=true`，`prompt_id=5027692a-24c2-41fd-aadb-95c299449dd8`，`seed=793414787`
- `nodes_available=7`，`comfy.version=0.44.0`
- `layer_count=**29**`，`elapsed_ms=**1,362,829**`（22 分 42.8 秒；其中权重 ~15.5min + 推理 ~3.2min + 开销）
- `out_dir=seg/sakiko_skin1-layers`；`comfy_output_dir=...\ComfyUI\output`
- 节点内部流程（`comfyui.log`）：
  `GenerateLayers complete: 24 layers` → `GenerateDepth: Marigold`（GPU 峰值 allocated≈2.45GB，完成后 offload 到 CPU）→ `GenerateDepth complete: 23 depth maps` → `PostProcess: splitting & clustering` → **`PostProcess complete: 29 layers`**
- ⚠️ 注意：**返回 29 层而非固定 24 层**。24 是语义层数，PostProcess 会按深度/聚类把小部件（眼白、虹膜、睫毛、耳等）再拆分，实际落盘 29 个 PNG + 29 张深度图。以实际返回为准。

### 5.1 29 层清单（深度序：远 → 近，即 PSD 底 → 顶）

| # | 层名 | bbox | 尺寸 | depth_median | PNG 字节 |
|---|---|---|---|---|---|
| 1 | neck | 0,0,832,832 | 832×832 | 1.0000 | 329,286 |
| 2 | tail | 0,0,832,832 | 832×832 | 1.0000 | 321,264 |
| 3 | wings | 0,0,832,832 | 832×832 | 1.0000 | 304,475 |
| 4 | eyewear | 0,0,832,832 | 832×832 | 1.0000 | 302,649 |
| 5 | earwear | 0,0,832×832 | 832×832 | 1.0000 | 313,111 |
| 6 | irides-l | 819,818,827,830 | 8×12 | 1.0000 | 262 |
| 7 | eyebrow-l | 818,818,827,830 | 9×12 | 1.0000 | 249 |
| 8 | ears-l | 819,818,825,825 | 6×7 | 1.0000 | 169 |
| 9 | bottomwear | 0,0,832,832 | 832×832 | 0.9844 | 561,625 |
| 10 | objects | 0,0,832,832 | 832×832 | 0.9844 | 577,951 |
| 11 | neckwear | 0,0,832,832 | 832×832 | 0.9688 | 429,851 |
| 12 | handwear-l | 435,276,616,564 | 181×288 | 0.9648 | 78,446 |
| 13 | back hair | 0,0,832,832 | 832×832 | 0.9414 | 464,055 |
| 14 | legwear | 0,0,832,832 | 832×832 | 0.8203 | 287,392 |
| 15 | footwear | 0,0,832,832 | 832×832 | 0.8125 | 324,791 |
| 16 | eyebrow-r | 416,267,429,270 | 13×3 | 0.7266 | 156 |
| 17 | topwear | 0,0,832,832 | 832×832 | 0.6953 | 351,770 |
| 18 | headwear | 0,0,832,832 | 832×832 | 0.6836 | 355,959 |
| 19 | eyewhite-r | 418,271,433,281 | 15×10 | 0.6211 | 529 |
| 20 | eyewhite-l | 435,268,445,276 | 10×8 | 0.6211 | 338 |
| 21 | eyelash-l | 438,266,447,275 | 9×9 | 0.5117 | 299 |
| 22 | face | 0,0,832,832 | 832×832 | 0.5000 | 543,727 |
| 23 | handwear-r | 109,299,411,782 | 302×483 | 0.5000 | 166,753 |
| 24 | mouth | 0,0,832,832 | 832×832 | 0.4990 | 920,772 |
| 25 | irides-r | 419,270,430,279 | 11×9 | 0.4922 | 391 |
| 26 | nose | 0,0,832,832 | 832×832 | 0.4844 | 924,777 |
| 27 | eyelash-r | 412,271,428,281 | 16×10 | 0.4609 | 483 |
| 28 | ears-r | 401,271,411,284 | 10×13 | 0.4561 | 478 |
| 29 | front hair | 0,0,832,832 | 832×832 | 0.1738 | 380,065 |

> 语义分组：头/脸相关 17 层（front hair / back hair / face / eyes 系 10 层 / mouth / nose / ears 系 / headwear / earwear / eyewear），身体/服饰/其它 12 层（neck / tail / wings / objects / topwear / bottomwear / neckwear / handwear-l/r / legwear / footwear）。
> `_depth` 后缀为 Marigold 深度图（`depth/` 子目录），`depth_median` 越小越靠前，可直接作为建模遮挡层级依据。

### 5.2 产物清单（`models/togawa-sakiko/seg/sakiko_skin1-layers/`，61 文件 / 25.65MB）

```
seg/sakiko_skin1-layers/
├─ layers/                                   29 个语义层 PNG（832² 或 bbox 裁切），7.57MB
│   └─ seethrough_sakiko_skin1_mw6fcikd_20261107_213617_312f17c2_<层名>.png
├─ depth/                                    29 张深度图（同名 + _depth），0.52MB  ← 从 ComfyUI output 复制
├─ layers.json                               10,275B：29 层 name/filename/bbox/depth_median/depth_filename  ← 从 ComfyUI output 复制
├─ seethrough_sakiko_skin1_mw6fcikd_preview_00001_.png   284,834B（插件自动复制的预览）
└─ sakiko_skin1-layers.psd                   18,119,580B（17.28MiB，832²，29 层）
```

- 插件 `bb_seg_run` 默认只把 `layers/*.png` + preview 复制到 workspace；`layers.json`、`_depth.png` 留在 `...\ComfyUI\output`，已由本报告执行者复制补齐（原文件仍在 ComfyUI output）。
- `layer_sheet`（29 层缩略拼图）仅作为工具返回附件提供，**未落盘**（如需可用 `layers/` 自行拼）。

---

## 6. PSD：关键发现与生成/校验

### 6.1 发现：`bb_seg_run` 不会自动产 PSD（这不是失败）

- 服务端节点 `SeeThrough_SavePSD`（`nodes.py:898`）只保存层 PNG + `layers.json`，并打印：
  `[SeeThrough] 29 layers saved. Use 'Download PSD' button to generate PSD.`
- 即 **PSD 由 ComfyUI 前端 JS（节点内置 bundled `ag-psd`，`window.AgPsd.createPSDFromLayers`）在浏览器点「Download PSD」时生成**，服务端不落 PSD。
- 因此 `bb_seg_run` 返回结果中不存在 PSD / layers.json 路径，属实现行为，非安装或运行失败。

### 6.2 本报告的补齐方案（等价复刻 + 修正）

为交付可直接使用的 PSD，使用 Node + `ag-psd@34.1.0`（与前端同库）复刻 `createPSDFromLayers`：

- 脚本：`artifacts/psd-gen/make-psd.js`（依赖装在 `artifacts/psd-gen/node_modules`，用 DSH 捆绑 pnpm 安装，**未污染系统**）
- 输入：`layers.json` + `layers/*.png`；输出：`seg/sakiko_skin1-layers/sakiko_skin1-layers.psd`
- 与前端的两点差异（均为修正，已在脚本注释标明）：
  1. **按 bbox 正确放置**：前端 `drawImage(u,0,0,832,832)` 会把裁切层（如 `irides-l` 仅 8×12）拉伸到 832²；本脚本按 `layers.json` 的 `left/top/right/bottom` 放置图层（标准 PSD 图层偏移），避免小层变形。
  2. 合成图（PSD composite）由 29 层按深度序自下而上 alpha 合成（与前端 draw order 一致）。
- 生成结果：**8BPS、832×832、8bit RGB、29 层、17.28MiB**；层序 = `layers.json` 顺序（远→近 = PSD 底→顶，ag-psd writer 的 `children[0]` 即 background 层）。

### 6.3 独立校验（psd-tools 1.26.0，与 ag-psd 无关的第二实现）

- 结构：`size=(832,832)`、`num_layers=29`、29 层 bbox 与 layers.json **全部一致（0 mismatch）**、29 层 alpha 均非空
- 层序判定（`psd.composite(force=True)` 强制从图层重算，白底 RGB 对比）：

| 对比对象 | mean diff(/255) | max | 结论 |
|---|---|---|---|
| 预期合成（远→近 自下而上） | **0.0812** | 3 | ✅ 层序正确 |
| 反向合成（近→远） | 6.9867 | 241 | ❌ 明显不符 |
| PSD 内嵌 composite vs 预期 | 0.4575 | 3 | ✅ 内嵌合成也正确 |

- 目视核对产物：`artifacts/psd-verify/expected-composite.png`、`psd-tools-composite.png`（几乎一致）、`inverted-composite.png`（错误对照）。结论：**PSD 层叠方向与内容正确**（前发在脸之上、后发/椅背在后）。

### 6.4 若需要「官方前端 PSD」

在浏览器打开 `http://127.0.0.1:8188`，加载 See-through 工作流，点节点上的 **Download PSD**（会下载到浏览器下载目录）。本报告交付的 PSD 内容与之等价（且修掉了裁切层拉伸问题）。

---

## 7. 可选：`crop_head.png` 头部特写分层

| 项 | 值 |
|---|---|
| 输入 | `refs/skin/crop_head.png`，resolution 832 |
| 结果 | `ok=true`，`layer_count=**23**`，`elapsed_ms=**190,819**`（3 分 11 秒；权重已缓存，纯推理） |
| prompt_id | `260ec064-5bce-4abb-999e-e10910b46a0d`，seed 527038704 |
| 产物 | `seg/crop_head-layers/`（49 文件 / 6.1MB）：23 层 PNG + 23 depth + layers.json(8,162B) + preview(554,747B) + **crop_head-layers.psd（4,069,195B / 3.88MiB，23 层）** |
| 层名 | tail, bottomwear, handwear-r, back hair, objects, topwear, neck, eyebrow-l, headwear, ears-l, face, mouth, nose, eyebrow-r, eyewhite-r, eyewhite-l, irides-r, irides-l, eyelash-r, eyelash-l, ears-r, front hair, handwear-l |

---

## 8. 如何重启 / 检查 ComfyUI（给后续建模者）

**方式 A（推荐，一键脚本）**

```powershell
# 启动（已监听则直接返回 PID；日志写 artifacts/comfyui.log / comfyui.err.log）
pwsh -NoProfile -File "F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\start-comfyui.ps1"

# 健康检查（轮询 /system_stats 直到 200，默认最多 300s）
pwsh -NoProfile -File "F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\check-comfyui.ps1"
```

**方式 B（手工，等价于官方 startCommand）**

```powershell
$root = "C:\Users\28988\.dsh-seethrough\ComfyUI_windows_portable"
$py   = "$root\python_embeded\python.exe"
Start-Process -FilePath $py `
  -ArgumentList @('-s', "$root\ComfyUI\main.py", '--listen', '127.0.0.1', '--port', '8188') `
  -WorkingDirectory "$root\ComfyUI" `
  -RedirectStandardOutput "F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\comfyui.log" `
  -RedirectStandardError  "F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\comfyui.err.log" `
  -WindowStyle Hidden -PassThru
```

**速查**

| 用途 | 命令 / 位置 |
|---|---|
| 健康 | `curl http://127.0.0.1:8188/system_stats`（或 Invoke-WebRequest） |
| 端口占用 | `Get-NetTCPConnection -LocalPort 8188 -State Listen` |
| 进程 | `Get-Process python`（当前 PID 24708） |
| 正常启动标志 | 日志出现 `Starting server` / `To see the GUI go to: http://127.0.0.1:8188` |
| 插件连通 | `bb_seg_probe` → `comfy.reachable=true` |
| 停止 | `Stop-Process -Id 24708`（**注意：后续建模需要时保持运行**） |

---

## 9. 磁盘与体积汇总

| 项目 | 体积 / 文件数 |
|---|---|
| `C:\Users\28988\.dsh-seethrough`（安装） | **6.54GB / 71,679 文件** |
| ├ `ComfyUI_windows_portable\` | 4.626GB / 71,678 文件 |
| └ `ComfyUI_windows_portable_nvidia.7z` | 1.913GB（可回收，未删） |
| HuggingFace 权重 cache | **12.513GB / 43 文件** |
| C: 剩余 | **203.08GB**（安装前 230.15GB，净用约 27GB） |
| `seg/sakiko_skin1-layers/` | 25.65MB / 61 文件 |
| `seg/crop_head-layers/` | 6.10MB / 49 文件 |
| 其它 seg（T1 旧产物，未动） | crop_body 0.59MB、crop_head 0.64MB、crop_legs 0.34MB、sakiko_skin1 1.01MB |

> T1（`bb_seg_lite`）产物目录与 T2 产物目录互不覆盖：T1 在 `seg/<name>/masks/`，T2 在 `seg/<name>-layers/`。

---

## 10. 失败 / 异常与重试记录

| # | 事件 | 原因 | 处置 | 结果 |
|---|---|---|---|---|
| 1 | 首次 `bb_seg_install` 被中断（.part 1.589GB） | 人工 interrupt（怀疑下载卡住，实际只是显示滞后） | 检查发现下载进程被杀；`.part` 保留 | 后由 Lead 用系统 curl 重下完整 7z（2.054GB） |
| 2 | `.part` 曾被两个写入者同时写，长度异常 2.297GB | 并发下载冲突 | Lead 删除坏包、单线程重下；本执行者改为**不并发调用 install** | 解决 |
| 3 | 解压与工具调用超时风险 | Windows 解压 6 万文件可能数分钟 | 改为**后台 pwsh 作业**先解压（91.7s 完成），再让 `bb_seg_install` 跳过下载/解压 | 成功，规避了中断风险 |
| 4 | PSD 缺失 | 设计如此（PSD 由前端按钮生成） | 用 Node+ag-psd 复刻前端逻辑并修正 bbox | 已交付并通过 psd-tools 校验 |
| 5 | 层 PNG 非全画布（如 8×12） | 节点按 bbox 裁切保存 | 生成 PSD 时按 bbox 放置 | 已修正 |

**重试次数**：`bb_seg_install` 正式调用 1 次成功；`bb_seg_run` 各 1 次成功；**无工具超时**。

---

## 11. 未解决项 / 给建模者的注意事项

1. **PSD 非 run 自动产出**（见 §6）：需要「官方」PSD 时在 ComfyUI 前端点 Download PSD；本仓库已提供等价 PSD。
2. **`layer_sheet` 未落盘**：仅工具返回附件；如需拼图可自行从 `layers/` 生成。
3. **`layers.json` / `_depth.png` 原本不在 workspace**：已复制到 `seg/*-layers/`；ComfyUI output 中保留原文件（不要删 output，`layers.json` 是 PSD 生成/重建的关键索引）。
4. **HF 权重（12.5GB）不可随意清理**，否则下次分层会重新下载约 15 分钟。
5. **7z 安装包（1.913GB）保留**：含“未删除已有文件”约束；如需回收 C: 空间可手动删除（不影响已解压的 ComfyUI）。
6. **ComfyUI 当前保持运行**（PID 24708，HTTP 200）：后续 `bb_seg_run` / 建模请勿关闭；机器重启后按 §8 重启。
7. **层数不是固定 24**：本次 29 层（PostProcess 会拆分小部件）。下游按 `layers.json` / 返回列表为准，不要硬编码 24。
8. **深度图用途**：`depth_median` 越小越靠前（front hair 0.17 最前，neck/tail/wings/eyewear/earwear 1.0 最后），可用于建模时的遮挡/层级判断。
9. **磁盘**：C: 剩 203GB，后续建模请留意 ComfyUI output 与 HF cache 增长。

---

## 附录 A：日志与关键文件路径

| 文件 | 路径 |
|---|---|
| 安装/体积监控 | `artifacts/install-monitor.log`（30s 采样，含 HF/INST 体积曲线） |
| 解压日志 | `artifacts/extract.log` |
| ComfyUI stdout / stderr | `artifacts/comfyui.log` / `artifacts/comfyui.err.log` |
| 启动 / 健康检查脚本 | `artifacts/start-comfyui.ps1` / `artifacts/check-comfyui.ps1` |
| PSD 生成脚本 + Node 依赖 | `artifacts/psd-gen/{make-psd.js, verify_psd.py, verify_psd2.py, node_modules/}` |
| PSD 校验产物 | `artifacts/psd-verify/{expected-composite.png, psd-tools-composite.png, inverted-composite.png}` |
| 主交付 | `seg/sakiko_skin1-layers/`（29 层 + depth + layers.json + PSD + preview） |
| 头部特写交付 | `seg/crop_head-layers/`（23 层 + depth + layers.json + PSD + preview） |
| ComfyUI 安装 | `C:\Users\28988\.dsh-seethrough\ComfyUI_windows_portable` |
| See-through 节点 | `...\ComfyUI\custom_nodes\ComfyUI-See-through`（含 `.git`） |
| HF 权重 | `C:\Users\28988\.cache\huggingface` |

## 附录 B：关键日志摘录

```
[SeeThrough] GenerateLayers complete: 24 layers
[SeeThrough] GenerateDepth: running Marigold...
[SeeThrough] GenerateDepth complete: 23 depth maps, Marigold offloaded to CPU
[SeeThrough] PostProcess complete: 29 layers
  - front hair: depth_median=0.1738
  ...
[SeeThrough] 29 layers saved. Use 'Download PSD' button to generate PSD.
[INFO] Prompt executed in 00:22:39

[SeeThrough] PostProcess complete: 23 layers
[SeeThrough] 23 layers saved. Use 'Download PSD' button to generate PSD.
```

`/system_stats`（21:44）：

```json
{"system": {"comfyui_version": "0.44.0", "pytorch_version": "2.14.1+cu130",
 "python_version": "3.13.14 ...", "embedded_python": true,
 "argv": ["...ComfyUI\\main.py", "--listen", "127.0.0.1", "--port", "8188"]},
 "devices": [{"name": "cuda:0 NVIDIA GeForce RTX 4080 Laptop GPU : cudaMallocAsync",
 "vram_total": 12878086144, "vram_free": 11532... }]}
```
