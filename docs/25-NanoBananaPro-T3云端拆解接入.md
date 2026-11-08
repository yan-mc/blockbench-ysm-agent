# 25 · T3 云端拆解：Nano Banana Pro 接入与降级策略（2026-11-08）

> 用户确认的优先级：**T3 > T2 > T1**。T3 = Google **Nano Banana Pro（Gemini 3 Pro Image）**，多参考图生成"三视图 / 全景式深度拆解板"；需要外接付费 API，**不能替代本地流水线**，没有 API 时自动降级现有 T2（See-through）。
> 本文记录：能力与 API 事实、成本、隐私/版权、工具设计（`bb_seg_t3`）、提示词模板、与 T2/T1 的组合流程、失败与降级矩阵、验收清单。

---

## 0. 一句话结论

- **能接**：`gemini-3-pro-image` 是标准 REST `generateContent` 调用，支持**多张参考图 + 文本提示**、输出 1K/2K/4K、宽高比可选；含 **SynthID** 水印。
- **值得接**：它正好解决"官方立绘带动作/背景/打光、T1/T2 拆不干净"和"缺背面/缺内侧结构"两个痛点；生成的拆解板/三视图是**假设清单**，不是还原。
- **必须降级**：Pro Image 无免费层，按张计费；无 key/超时/限流/内容拦截时，工具返回可识别错误并明确指向 `bb_seg_run`（T2）。
- **定位**：T3 生成 → 人工复核 →（可选）T2 对生成图继续分层 → spec/建模。不是替代 T2，而是 T2 的"上游补全器"。

---

## 1. Nano Banana Pro 是什么

Google Gemini 的原生图像生成系列叫 **Nano Banana**（2025 起）。截至 2026-11，Gemini API 中可用的图像模型：

| 模型 | Model ID | 定位 | 备注 |
|---|---|---|---|
| **Nano Banana Pro** | `gemini-3-pro-image` | 复杂指令、品牌/角色一致性、高保真文字 | **T3 默认**；支持多参考图、1K/2K/4K |
| Nano Banana 2.1 | `gemini-nano-banana-2.1` | 高性价比主力（Flash 级速度/成本） | 多参考图一致性略逊于 Pro |
| Nano Banana 2 | `gemini-3.1-flash-image` | 上一代高性价比 | 4K、多参考图一致性 |
| Nano Banana 2 Lite | `gemini-3.1-flash-lite-image` | 最快最便宜 | 不擅长多参考图/多轮编辑 |
| Nano Banana（旧） | `gemini-2.5-flash-image` | 旧版兜底 | 迁移到 2 Lite |

官方文档：<https://ai.google.dev/gemini-api/docs/image-generation>（2026-11 抓取）。
统一说明：**所有生成图都带 SynthID 水印**；上传参考图前需确认版权/使用权限。

### 1.1 为什么它适合"复杂立绘"

普通 T2（See-through）只能看到图里**可见**的部分；官方立绘里的动作遮挡、背景、打光会让分层质量下降。Nano Banana Pro 的强项是：

- **多参考图**：同一角色的正面/侧面/动作图一起给，模型能锁定身份（脸、发色、角、服装结构）；
- **复杂指令遵循**（Pro 有 thinking）：能按要求输出"严格三视图"、"把服装拆成单品"、"用箭头标注对应部位"；
- **文字/排版**：拆解板里的手写注释、标签、箭头能画对（Pro 的强项）；
- **4K 输出**：拆解板细节足够放大看。

---

## 2. API 事实（用于实现）

### 2.1 端点与请求体

```
POST {baseUrl}/models/{model}:generateContent?key={API_KEY}
baseUrl 默认 https://generativelanguage.googleapis.com/v1beta
```

```json
{
  "contents": [{
    "role": "user",
    "parts": [
      { "text": "<提示词>" },
      { "inlineData": { "mimeType": "image/png", "data": "<base64>" } }
    ]
  }],
  "generationConfig": {
    "responseModalities": ["TEXT", "IMAGE"],
    "imageConfig": { "aspectRatio": "16:9", "imageSize": "2K" }
  }
}
```

- `imageSize`：`1K` / `2K` / `4K`（Pro 支持）。
- `aspectRatio`：`1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9`。
- 参考图：`inlineData` 多张（建议 4–6 张；第三方服务说明 Pro 系列最多约 14 张，实际以 API 报错为准；本工具默认上限 6、参数上限 14）。
- 响应：`candidates[].content.parts[]` 中 `inlineData`（或 `inline_data`）为 base64 图片，`text` 为说明；无图时看 `promptFeedback.blockReason` / `finishReason`。
- 请求体风格：默认 **camelCase**（`inlineData`/`mimeType`，与 Google 官方与 APIYI 文档一致）；兼容 `bodyStyle:"snake"`（`inline_data`/`mime_type`）。
- 输出模态：默认 `responseModalities:["IMAGE"]`（APIYI 文档示例）；需要文字说明时可配 `nanoBananaResponseModalities:["TEXT","IMAGE"]`。

### 2.1.1 APIYI 中转站兼容性（2026-11 核对）

APIYI 的 Nano Banana 图片编辑文档（<https://docs.apiyi.com/api-capabilities/nano-banana-image/image-edit>）给的是**与官方 Gemini 一致的 generateContent 接口**，只是换成中转站域名 + Bearer 鉴权：

```
POST https://api.apiyi.com/v1beta/models/gemini-3-pro-image:generateContent
Authorization: Bearer <APIYI token>
Content-Type: application/json

{
  "contents": [{ "parts": [
    { "text": "<提示词>" },
    { "inlineData": { "mimeType": "image/png", "data": "<base64>" } },
    { "inlineData": { "mimeType": "image/png", "data": "<base64>" } }
  ]}],
  "generationConfig": {
    "responseModalities": ["IMAGE"],
    "imageConfig": { "aspectRatio": "16:9", "imageSize": "2K" }
  }
}
```

结论：**格式兼容**，不需要改请求体结构；只需要：
- `nanoBananaProvider: 'apiyi'`（自动 baseUrl=`https://api.apiyi.com/v1beta`、`auth: bearer`、`bodyStyle: camel`）；
- `nanoBananaApiKey` 填 APIYI 的 token（或环境变量 `GEMINI_API_KEY`）；
- 模型名用 `gemini-3-pro-image`（APIYI 文档就是这个 id；如中转站另有别名，按报错调整）。
- 多参考图：文档示例就是多个 `inlineData`，支持；图片大小/限额以中转站为准。
- **价格/额度以 APIYI 账单为准**（本插件的 `cost_estimate_usd` 是按 Google 官方价估算，不是中转站账单）。
- 迁移到其他中转站：用 `nanoBananaProvider:'custom'` + `nanoBananaBaseUrl` + `nanoBananaAuth`（query/bearer）+ `nanoBananaBodyStyle` 覆盖即可。

> **2026-11-08 实测（无有效 token）**：对本机网络 `POST https://api.apiyi.com/v1beta/models/gemini-3-pro-image:generateContent` + 假 Bearer token，返回 `HTTP 401 {"error":{"message":"Invalid token..."}}` → **端点路径与 Bearer 鉴权格式都正确**，缺的只是有效 token；拿到 token 后即可用上面的配置。

- **APIYI 实际返回格式（2026-11-08 实测）**：生成图不在 `inlineData`，而是放在 text part 里的**签名 URL**（`https://mycdn-gg.oss-us-west-1.aliyuncs.com/response_images/...png?X-Amz-...`，24h 有效）。插件会自动 GET 下载并转 base64；同时按**文件头 magic** 识别真实格式（APIYI CDN 可能把 JPEG 标成 PNG）。修复前的报错是 `T3_NO_IMAGE: STOP`（有 URL 但没图）。

### 2.2 价格（官方 pricing 页，2026-11 抓取）

| 项 | 价格 |
|---|---|
| 输入 | $2.00 / 1M tokens（文本/图片；图片约 $0.0011/张） |
| 输出（图片） | $120 / 1M image tokens → **约 $0.134 / 张（1K 或 2K）**；**$0.24 / 张（4K）** |
| 输出（文本/thinking） | $12 / 1M tokens |
| 免费层 | **不可用**（Pro Image 无免费层） |
| Batch / Flex / Priority | 有折扣/加价档，T3 暂不用 |

> 结论：一张 2K 拆解板 ≈ **$0.14**；一张 4K ≈ **$0.24**；`variants=2` 翻倍。实现会在调用前给出 `cost_estimate_usd`，`dry_run:true` 不花钱。

### 2.3 限制与坑

1. **内容安全**：参考图含版权角色/敏感内容可能被拦截；返回 `T3_NO_IMAGE`。
1b. **生成会补细节**：实测 `breakdown` 会给角色补出参考图未确认的"银冠/眼罩/腿链"等部件（官方图里没有或不明确）——这些是生成假设，必须逐项对照官方图剔除或写进 gaps，不能直接当设定。
2. **一致性不是保证**：多张图之间仍会漂移，尤其左右手/左右眼、纹样、文字徽记。
3. **背面/内侧是推断**：模型会"合理编"，必须逐张对照官方图复核，并写进 `spec.gaps`。
4. **水印**：所有图带 SynthID；不能当官方素材直接分发。
5. **请求大小**：内联 base64 有上限（实现里限制单图 8MB、总 base64 ≤18MB；超过提示压缩）。
6. **网络/区域**：需要能访问 `generativelanguage.googleapis.com`；企业代理可改 `nanoBananaBaseUrl`。
7. **费用不可逆**：生成即计费；重试/多变体要自己控。

---

## 3. 工具设计：`bb_seg_t3`

### 3.1 能力分级（写进 `bb_seg_probe`）

```
T3  Nano Banana Pro 云端拆解   （需 key；优先）
T2  See-through 本地完整分层   （23–29 语义层 + 遮挡补全）
T1  SAM2 本地轻量分割          （只给可见部件）
T0  零依赖：模型直接看立绘
```

- `bb_seg_probe` 只**检查配置**（`nanoBanana.apiKey` / env `GEMINI_API_KEY`），不发请求、不耗额度；
- 有 key → `recommendedTier:"t3"`；没有 → 回落到 `t2`（环境支持时），再不行 `t1/t0`；
- `tiers.t3` 返回 model、api_key_source、price、reasons、fallback。

### 3.2 `bb_seg_t3` 参数

| 参数 | 说明 |
|---|---|
| `references` / `reference_dir` | 1–14 张同角色多角度参考图（二选一；目录自动取前 N 张） |
| `max_references` | 默认 6（配置 `nanoBananaMaxReferences`） |
| `mode` | `turnaround`（严格三视图，默认）/ `breakdown`（全景拆解板）/ `custom` |
| `prompt` | 追加说明；custom 必填 |
| `character` | 身份锚定（可选） |
| `aspect_ratio` | 默认 16:9 |
| `image_size` | `1K/2K/4K`，默认 2K |
| `variants` | 1–4，默认 1（成本×N） |
| `out_dir` | 默认 `artifacts/t3-sheets/<时间戳>` |
| `attach` | 是否附第一张预览（默认 true） |
| `dry_run` | 只返回提示词/成本，不调用 API |

返回：`tier:"T3"`、model、mode、references、`images[]`（workspace 相对路径）、`meta_path`（t3-meta.json）、`cost_estimate_usd`、`warnings[]`、`next_steps[]`、附件预览。

### 3.3 配置

**官方 Gemini**（`cordis.patch.yml` 或用户 profile）：

```yaml
config:
  nanoBananaProvider: 'official'   # Google 官方（默认）
  # 也可用环境变量 GEMINI_API_KEY / GOOGLE_API_KEY
  nanoBananaApiKey: 'AIza...'
  nanoBananaModel: 'gemini-3-pro-image'
  nanoBananaImageSize: '2K'
  nanoBananaAspectRatio: '16:9'
  nanoBananaMaxReferences: 6
  nanoBananaTimeoutMs: 180000
```

**APIYI 中转站**（中国大陆/香港不直连官方时用）：

```yaml
config:
  nanoBananaProvider: 'apiyi'
  nanoBananaApiKey: 'APIYI 的 token'
  # provider=apiyi 自动：baseUrl=https://api.apiyi.com/v1beta, auth=bearer, bodyStyle=camel
  nanoBananaModel: 'gemini-3-pro-image'
  nanoBananaImageSize: '2K'
  nanoBananaAspectRatio: '16:9'
  nanoBananaMaxReferences: 6
```

**其他中转站**：

```yaml
config:
  nanoBananaProvider: 'custom'
  nanoBananaApiKey: '...'
  nanoBananaBaseUrl: 'https://relay.example.com/v1beta'
  nanoBananaAuth: 'bearer'        # 或 'query'
  nanoBananaBodyStyle: 'camel'    # 或 'snake'
  nanoBananaModel: 'gemini-3-pro-image'
```

不提交 key；文档只写占位符。

---

## 4. 提示词模板

### 4.1 `turnaround`（默认，建模主用）

要求模型输出"**正交三视图 + 逐部位单独图 + 服装单品拆解**"，而不是只画三张全身：

```
你是资深游戏角色概念设计师，正在为 3D 建模制作角色设定图。
以用户提供的参考图（同一角色的官方立绘/设定图，可能有多张多角度）作为唯一身份依据，
生成一张排版清晰、等比例、可量尺寸的**正交三视图 + 部件分解图**。

一、三视图（必须清晰、完整）
- 横向并排：严格正面、严格 90° 正侧面、严格背面，三个完整全身视图；
- 三视图等高等比例，头顶与脚底分别对齐同一条水平基线；
- 中性站立姿势（A-pose 或双臂自然下垂），不保留参考图的坐姿/动作/舞蹈姿势；
- 纯白或极浅灰背景；无场景、无道具、无特效、无水印、无多余装饰文字；
- 严格保持脸型、五官、瞳色、发型、角/兽耳、服装结构、层次、配色、纹样与配饰；

二、单独部位图（必须逐项画出，不要只画全身）
- 头部：正面、侧面、背面特写，清晰画出五官、发型、角/耳、发饰；
- 上半身：正面、侧面（躯干 + 手臂 + 上衣结构）；
- 下半身：正面、侧面（腰胯 + 腿 + 鞋/靴）；
- 手部：正/背/侧面（被袖子遮挡时画出袖口连接结构）；
- 脚部/鞋：正面、侧面、鞋底；
- 服装拆解：把每件衣服和配饰拆成独立单品平铺展示（外套、上衣、裙/裤、腰带/绑带、袖套、手套、鞋、发饰、胸针、角环等），一件一张，保持原配色与纹样；
- 对应关系：可用细线/编号把拆解单品连到三视图上的对应位置（编号少而清晰）。

三、约束
- 只出现参考图里的这一个角色；不添加参考图没有的配饰、花纹、道具、内着或其他物品；
- 不画参考图原有的背景、家具、乐器、特效；
- 参考图缺少背面/侧面信息时，按可见结构做合理推断，三视图与拆解件之间必须自洽；
- 只输出一张图，不要输出大段文字说明。
```

### 4.2 `breakdown`（全展开部件拆解板）

用户找到的原始爆款（Nano Banana Pro "像素级拆解"）见：<https://github.com/mqyqingfeng/Blog/issues/385>。
原始提示词里的"生活切片/私密物品/脑补二级元素"属于过度编造，**已从我们的模板删掉**。现在的 `breakdown` 只做**设计拆解**：

```
你是资深游戏角色概念设计师，正在制作角色部件拆解设定图（用于 3D 建模）。
以用户提供的同一角色参考图（可多张多角度）作为唯一设计依据，生成一张"全展开部件设定板"。

1. 中心位：角色全身中性站姿（正面），可加正/侧/背三视图小图；
2. 拆解部件：把角色拆成独立部件，按区域整齐排开，互不遮挡、平铺摆放：
- 头部：正/侧/背特写（五官、发型、角/兽耳、发饰分别画出）；
- 躯干：正面/背面（上衣、胸饰、腰带逐件分开）；
- 双臂与手：左右分开，画清袖口与手套连接；
- 双腿与脚：左右分开，画清裤/袜/鞋的结构与鞋底；
- 每件服装单品：外套、上衣、裙/裤、袖套、腰带/绑带、鞋/靴逐件平铺；
- 每件配饰/道具：发饰、胸针、角环、挂件等逐个放大展示；
3. 标注：用细编号或短标签说明部件名称/连接关系；保持原设计、配色、纹样、材质；
4. 约束：只拆参考图中确实存在的部件；不添加参考图没有的服装、道具、内着、花纹或生活物品；
被遮挡的结构可按可见设计语言补全，但必须与原设计一致；
纯白或浅灰背景，只输出一张排版清晰的设计图，不要大段文字。
```

> 注意：拆解板是**生成式设定稿**，不是严格三视图；适合做部件清单/连接结构/遮挡参考，不适合量尺寸。

### 4.3 `custom`

直接传 `prompt`，用于"只拆上半身""只补背面""把动作改成站姿"等定向修改。

---

## 5. 组合流程（怎么用才不出错）

```
官方立绘/同人多角度
   │
   ├─ bb_ref_search / bb_ref_collect → 带编号对照表
   │     └─ **先把对照表给用户看，让用户按编号挑选"角度正确"的几张**（正面/侧面/背面/细节）
   │        再把选中的文件路径传入 bb_seg_t3.references（或 reference_dir）
   │
   ├─ T3 bb_seg_t3(mode:"turnaround")  → 干净三视图 + 部位/服装拆解（人工复核）
   ├─ T3 bb_seg_t3(mode:"breakdown")   → 部件/服装分层/遮挡假设（人工标注可信度）
   │
   ├─ 可选：把 T3 生成的三视图交给 T2 bb_seg_run → 23–29 层语义分层
   ├─ 可选：T1 bb_seg_lite 对生成图做部件分割/比例校准
   │
   └─ 写 spec：所有背面/内侧/被挡部件标为"推定"，进 spec.gaps
```

**规则**：
1. T3 先给"假设"，T2/T1 给"可见证据"；两者不一致时以官方图为准。
2. 每张 T3 图必须人工逐项检查：身份、左右镜像、配色、纹样、文字、比例、背面自洽。
3. T3 结果不得直接当最终贴图/尺寸依据；可以作为建模参考、部件 checklist、T2 的输入。
4. 失败/无 key 一律降级 T2，并在报告写"降级原因"。

---

## 6. 失败与降级矩阵

| 情况 | 工具返回 | 处理 |
|---|---|---|
| 没配 key | `T3_NOT_CONFIGURED` + `fallback:"t2"` | `bb_seg_run`（T2），或配置 key |
| key 无效/无权限 | `T3_AUTH` | 检查 key/计费/权限；降级 T2 |
| 限流/配额 | `T3_QUOTA` | 降 variants、换模型（2.1）、稍后重试；降级 T2 |
| 参数/参考图问题 | `T3_BAD_REQUEST` | 检查图片格式/大小/宽高比；减少参考图 |
| 模型 id/端点错 | `T3_MODEL_NOT_FOUND` | 检查 model/baseUrl |
| 内容被拦 | `T3_NO_IMAGE` + `blockReason/finishReason` | 换参考图、去掉敏感描述；降级 T2 |
| 超时 | `T3_TIMEOUT` / 取消 | 重试一次；仍失败降级 T2 |
| 网络/代理失败 | `T3_NETWORK` | 检查网络/代理/baseUrl；重试或降级 T2 |
| 返回无图 | `T3_NO_IMAGE` | 重试；降级 T2 |

---

## 7. 隐私 / 版权 / 合规

- **会上传参考图到所选服务商**（Google 官方，或 APIYI 等中转站）：不要把未授权/敏感素材传上去；项目里的第三方参考图仅本地研究（我们已 gitignore `artifacts/refstudy/`）。
- **生成图通常带 SynthID 水印**（Google 模型侧；中转站是否保留以实际返回为准）：不能当官方素材；如果要对外发布，注明"AI 生成参考"。
- **不要把 API key 写进仓库**：只用 `cordis.patch.yml` 注释占位/环境变量。
- **内容政策**：角色/服装描述避免低俗；拆解板只做设计用途。

---

## 8. 验收清单

- [ ] 未配置 key：`bb_seg_probe` 显示 `tiers.t3.ok=false`、`recommendedTier` 落 `t2`；`bb_seg_t3` 返回 `T3_NOT_CONFIGURED`（不崩溃、不扣费）。
- [ ] APIYI：`nanoBananaProvider:"apiyi"` + token 后 `bb_seg_probe` 显示 provider=apiyi、auth=bearer；真实调用 URL 为 `https://api.apiyi.com/v1beta/models/gemini-3-pro-image:generateContent`。
- [ ] `dry_run:true` **在没 key 时也能**返回提示词/成本（不发请求、不花钱）；配 key 后仍可用。
- [ ] 配 key：`turnaround` 生成 2K 三视图，落盘 + meta.json + 附件预览。
- [ ] `breakdown` 生成拆解板（中心角色 + 服装分层 + 表情 + 道具 + 箭头）。
- [ ] 多参考图（4–6 张）身份一致；单图也能跑。
- [ ] 错误路径：401/429/400/404 分别映射 T3_AUTH/T3_QUOTA/T3_BAD_REQUEST/T3_MODEL_NOT_FOUND。
- [ ] 成本估算与实际张数一致；variants 成倍。
- [ ] 人工复核后把推定项写入 spec.gaps。

**2026-11-08 实测（APIYI + 5 张参考图）**：
- `turnaround` 与 `breakdown` 各 1 张成功；分辨率 **2752×1536**；耗时 **40.1s / 42.1s**；成本估算 **$0.1415/张**（共 $0.283）。
- 产物：`models/togawa-sakiko/artifacts/t3-sheets/run2-turnaround/`、`run2-breakdown/`（含 `t3-meta.json`）。
- 结论：turnaround 的三视图标定、头/上身/下身/手/脚/服装单品拆分质量高；breakdown 部件标注清晰，但会补出官方图未确认的银冠/眼罩/腿链，需人工剔除。

---

## 9. 与现有文档/工具的关系

- 分层能力总纲：[docs/13](13-分层能力探测与安装.md)；T1：[docs/14](14-T1轻量分割SAM2.md)；T2：[docs/15](15-T2安装执行器.md)、[docs/16](16-T2完整分层调用.md)。
- 方案调研（为什么需要 T3、其他方案对比）：[docs/24](24-立绘转三视图与拆解方案调研.md)。
- 工具契约：`spec/tool-manifest.json`（`bb_seg_probe` / `bb_seg_t3`）；实现：`packages/dsh-blockbench-agent/lib/nanobanana.js`、`index.js`。
- Skill：`packages/dsh-blockbench-agent/skills/blockbench-ysm-artist.md` §2.4 分层能力与 §0-B 流水线步骤 3。

---

> **2026-11-08 实际应用**：T3 turnaround/breakdown 已用于丰川祥子「旋律的主人」v5 重建（534→1100 块）；流程与结果见 [`models/togawa-sakiko/V5-FINAL-REPORT.md`](../models/togawa-sakiko/V5-FINAL-REPORT.md)。

> **裁切教训（2026-11-08）**：T3 拆解板常把多视图/部件细节排在同一张图里。使用前必须按**原图像素坐标**把 front / side / back / 头部 / 服装细节裁成独立面板并逐张目检，不能按比例估算。本轮就曾把 front 裁进 side、side 裁进 back，导致对照图错位；正确裁切示例见 `models/togawa-sakiko/artifacts/refstudy/t3-panel5-*.png` 与 `docs/assets/showcase/sakiko-t3-crop-proof.png`。

## 10. 参考

- Gemini 图像生成文档（模型列表/参数/SynthID）：<https://ai.google.dev/gemini-api/docs/image-generation>
- Gemini 图像理解（多图上传/内联/文件 API）：<https://ai.google.dev/gemini-api/docs/image-understanding>
- Gemini API 价格：<https://ai.google.dev/gemini-api/docs/pricing>
- APIYI Nano Banana 图片编辑（Gemini 兼容格式 + Bearer）：<https://docs.apiyi.com/api-capabilities/nano-banana-image/image-edit>
- 社区爆款"像素级拆解"提示词：<https://github.com/mqyqingfeng/Blog/issues/385>
- See-through（T2）：<https://arxiv.org/abs/2602.03749>
- ai-chan-sheets（单立绘 → 多素材设定板流程）：<https://github.com/lmy414/ai-chan-sheets>
