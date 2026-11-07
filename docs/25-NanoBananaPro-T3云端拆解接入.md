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
      { "inline_data": { "mime_type": "image/png", "data": "<base64>" } }
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
- 参考图：`inline_data` 多张（建议 4–6 张；第三方服务说明 Pro 系列最多约 14 张，实际以 API 报错为准；本工具默认上限 6、参数上限 14）。
- 响应：`candidates[].content.parts[]` 中 `inlineData/inline_data` 为 base64 图片，`text` 为说明；无图时看 `promptFeedback.blockReason` / `finishReason`。
- 兼容性：REST 用 snake_case（`inline_data`/`mime_type`），`generationConfig` 内部为 camelCase；实现里两种都解析。

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

`cordis.patch.yml` 里可选（或用户 profile）：

```yaml
config:
  # 也可用环境变量 GEMINI_API_KEY / GOOGLE_API_KEY
  nanoBananaApiKey: 'AIza...'
  nanoBananaModel: 'gemini-3-pro-image'
  nanoBananaBaseUrl: 'https://generativelanguage.googleapis.com/v1beta'
  nanoBananaImageSize: '2K'
  nanoBananaAspectRatio: '16:9'
  nanoBananaMaxReferences: 6
  nanoBananaTimeoutMs: 180000
```

不提交 key；文档只写占位符。

---

## 4. 提示词模板

### 4.1 `turnaround`（默认，建模主用）

```
你是资深游戏角色概念设计师，正在为 3D 建模制作严格三视图。
以用户提供的参考图（同一角色的官方立绘/设定图，可能有多张多角度）作为唯一身份依据，生成一张横向三视图：
- 从左到右：严格正面、严格 90° 正侧面、严格背面，三个完整全身视图；
- 三视图等高等比例，头顶与脚底分别对齐同一条水平基线；
- 中性站立姿势（A-pose 或双臂自然下垂），不要保留参考图里的坐姿/动作/舞蹈姿势；
- 纯白或极浅灰背景；无场景、无道具、无特效、无水印、无多余装饰文字；
- 严格保持脸型、五官、瞳色、发型、角/兽耳、服装结构、层次、配色、纹样与配饰；不得新增参考图里没有的元素；
- 参考图缺少背面/侧面信息时，按可见结构与设计语言做合理推断，三个视图之间必须自洽；
- 只输出一张图。
```

### 4.2 `breakdown`（全景拆解板，来自社区爆款提示词的工程化版本）

用户找到的原始爆款（Nano Banana Pro "像素级拆解"）见：<https://github.com/mqyqingfeng/Blog/issues/385>。核心是"**全景式角色深度概念分解图**"：

- 中心：角色全身立绘（身份锚点）；
- 环绕：**服装分层（单品/内层）**、3–4 个表情、材质特写、核心道具、随身物品/生活切片；
- 用手绘箭头/引导线连到对应部位；
- 米黄/羊皮纸/浅灰设计稿背景 + 手写注释。

我们的改造（写进 `lib/nanobanana.js`）：

- 保留"中心立绘 + 服装分层 + 表情 + 材质 + 道具 + 箭头"；
- 增加**三视图**区（正面/90°侧面/背面）；
- 去掉低俗/隐私类内容要求，强调"只出现参考图角色、不要背景场景、不要改设计"；
- 加一致性要求 + "只输出一张图"。

> 注意：拆解板是**生成式设定稿**，不是严格三视图；适合做部件清单/穿法假设/遮挡参考，不适合量尺寸。

### 4.3 `custom`

直接传 `prompt`，用于"只拆上半身""只补背面""把动作改成站姿"等定向修改。

---

## 5. 组合流程（怎么用才不出错）

```
官方立绘/同人多角度
   │
   ├─ T3 bb_seg_t3(mode:"turnaround")  → 干净三视图候选（人工复核）
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

- **会上传参考图到 Google**：不要把未授权/敏感素材传上去；项目里的第三方参考图仅本地研究（我们已 gitignore `artifacts/refstudy/`）。
- **生成图带 SynthID**：不能当官方素材；如果要对外发布，注明"AI 生成参考"。
- **不要把 API key 写进仓库**：只用 `cordis.patch.yml` 注释占位/环境变量。
- **内容政策**：角色/服装描述避免低俗；拆解板只做设计用途。

---

## 8. 验收清单

- [ ] 未配置 key：`bb_seg_probe` 显示 `tiers.t3.ok=false`、`recommendedTier` 落 `t2`；`bb_seg_t3` 返回 `T3_NOT_CONFIGURED`（不崩溃、不扣费）。
- [ ] `dry_run:true` **在没 key 时也能**返回提示词/成本（不发请求、不花钱）；配 key 后仍可用。
- [ ] 配 key：`turnaround` 生成 2K 三视图，落盘 + meta.json + 附件预览。
- [ ] `breakdown` 生成拆解板（中心角色 + 服装分层 + 表情 + 道具 + 箭头）。
- [ ] 多参考图（4–6 张）身份一致；单图也能跑。
- [ ] 错误路径：401/429/400/404 分别映射 T3_AUTH/T3_QUOTA/T3_BAD_REQUEST/T3_MODEL_NOT_FOUND。
- [ ] 成本估算与实际张数一致；variants 成倍。
- [ ] 人工复核后把推定项写入 spec.gaps。

---

## 9. 与现有文档/工具的关系

- 分层能力总纲：[docs/13](13-分层能力探测与安装.md)；T1：[docs/14](14-T1轻量分割SAM2.md)；T2：[docs/15](15-T2安装执行器.md)、[docs/16](16-T2完整分层调用.md)。
- 方案调研（为什么需要 T3、其他方案对比）：[docs/24](24-立绘转三视图与拆解方案调研.md)。
- 工具契约：`spec/tool-manifest.json`（`bb_seg_probe` / `bb_seg_t3`）；实现：`packages/dsh-blockbench-agent/lib/nanobanana.js`、`index.js`。
- Skill：`packages/dsh-blockbench-agent/skills/blockbench-ysm-artist.md` §2.4 分层能力与 §0-B 流水线步骤 3。

---

## 10. 参考

- Gemini 图像生成文档（模型列表/参数/SynthID）：<https://ai.google.dev/gemini-api/docs/image-generation>
- Gemini 图像理解（多图上传/内联/文件 API）：<https://ai.google.dev/gemini-api/docs/image-understanding>
- Gemini API 价格：<https://ai.google.dev/gemini-api/docs/pricing>
- 社区爆款"像素级拆解"提示词：<https://github.com/mqyqingfeng/Blog/issues/385>
- See-through（T2）：<https://arxiv.org/abs/2602.03749>
- ai-chan-sheets（单立绘 → 多素材设定板流程）：<https://github.com/lmy414/ai-chan-sheets>
