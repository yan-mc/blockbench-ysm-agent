# UPDATE-PROMO · DSH × Blockbench Agent v0.9.2 更新宣传片

- **成片**：`media/sakiko-0.9.2-promo.mp4`（1920×1080 / 30fps / H.264 High + AAC 192k）
- **时长**：110.16s（目标 95–115s）
- **封面**：`media/bilibili-cover-0.9.2.png`（1920×1080）
- **投稿文案**：`media/bilibili-upload-0.9.2.md`
- **生成脚本**：`media/build_update_promo.py`
- **配音**：Edge TTS `zh-CN-XiaoxiaoNeural`，语速 +6%
- **生成时间**：2026-11-07 23:20 (Asia/Shanghai)

> 未上传 B 站（无账号）；仓库源码 / `models/` 未做任何修改，本轮只写 `media/`。

---

## 1. 素材来源（全部为仓库内真实文件，无 AI 生成图）

| 用途 | 文件 | 说明 |
|---|---|---|
| 最终四视图 | `models/togawa-sakiko/artifacts/renders/r0023/{front,back,left,iso_fr}_768.png` | 401 块最终模型，768²，透明背景 |
| 首轮 217 块 | `models/togawa-sakiko/artifacts/renders/r0021/front_768.png` | 首轮验收基线 |
| 中间态 355 块 | `models/togawa-sakiko/artifacts/t2-repair/renders/front_768.png` | T2 逐细节修理后 |
| 官方立绘 | `models/togawa-sakiko/refs/skin/sakiko_skin1.png` | 2176²，画面标注“官方参考” |
| T1 掩膜 | `models/togawa-sakiko/seg/sakiko_skin1/masks/*_part00..23.png` | 24 张 2176² 二值掩膜；片中只用于「24 个候选部件」计数与 §T1 面积统计，不叠色（掩膜本身多落在道具上，叠色会误导） |
| T2 分层 | `models/togawa-sakiko/seg/sakiko_skin1-layers/layers/*.png` + `layers.json` | 29 层 PNG + 深度中位数 |
| T2 统计 | `models/togawa-sakiko/artifacts/t2-preview/layer-metrics.json` | 每层 alpha 像素数 / 面积比 / depth_median |
| T2 预览 | `models/togawa-sakiko/seg/sakiko_skin1-layers/seethrough_*_preview_00001_.png` | 29 层合成预览 |
| 头部细节 | `docs/assets/showcase/sakiko-detail-head.png` | 角/发/菱形眼，左半幅裁切入镜 |
| 数据口径 | `T2-INSTALL-REPORT.md` / `T2-REPAIR.md` / `MODEL-V2-REFINE.md` / `README.md` | 29 层、22m43s、12.5GB、217→355→401、0 error |

**未使用**：`docs/assets/showcase/sakiko-before-after.png`、`t2-29-layers.png` 这两张拼图（内置英文标题栏，
不适合中文画面）；片中用同样的原始渲染与层图重新排版，信息一致。

---

## 2. 分镜表

| # | 起 | 时长 | 段落 | 卖点 | 画面函数 |
|---|---|---|---|---|---|
| 01 | 00:01 | 3.9s | 开场 | 开场：AI 真的能进 Blockbench？ | s_hook |
| 02 | 00:04 | 6.4s | 开场 | 不是给脚本，是自己建、自己看、自己改 | s_do |
| 03 | 00:11 | 6.4s | 案例 | 案例：丰川祥子「旋律的主人」 | s_case |
| 04 | 00:17 | 9.9s | 重点 1 · 立绘拆分 | 重点 1：T1 SAM2 轻量分割 | s_t1 |
| 05 | 00:27 | 6.8s | 重点 1 · 立绘拆分 | T1 的边界：可见轮廓 vs 遮挡 | s_t1_limit |
| 06 | 00:34 | 9.3s | 重点 1 · 立绘拆分 | 重点 1：T2 See-through 29 语义层 | s_t2 |
| 07 | 00:43 | 5.7s | 重点 1 · 立绘拆分 | 29 层清单与深度序 | s_ledger |
| 08 | 00:49 | 5.6s | 重点 1 · 立绘拆分 | 逐层特写：九张分件图 | s_layers |
| 09 | 00:54 | 8.5s | 重点 2 · 逐步调整 | 重点 2：首轮 217 块的三个问题 | s_217 |
| 10 | 01:03 | 10.2s | 重点 2 · 逐步调整 | T1 复检：5 个 major，217 → 355 | s_355 |
| 11 | 01:13 | 9.8s | 重点 2 · 逐步调整 | v2 美术优化：螺旋角 / 分组长发 / 菱形眼 | s_401 |
| 12 | 01:23 | 7.1s | 重点 2 · 逐步调整 | 217 → 355 → 401，validate 0 error | s_numbers |
| 13 | 01:30 | 9.9s | 工具链 | 工具链：41 工具 / 56 方法 | s_tools |
| 14 | 01:40 | 8.5s | 结尾 | 结尾：v0.9.2 在 GitHub | s_end |

**画面语汇**：深蓝底（#071222）+ 青 #59c2ff / 紫 #8b7cff 强调；每场 1.00→1.00+0.055
的 Ken Burns 推近 + 轻微横移；场景之间 0.34s 划像转场（左→右，带高光边缘）；底部逐句烧录中文字幕；底部细进度条。

---

## 3. 旁白全文（540 字，含标点；纯汉字 360 字）

01. AI 真的能进 Blockbench 做模型吗？
02. 不是给教程，也不是给脚本——是它自己建、自己看、自己改。
03. 这次的任务，是把这张官方立绘，做成能进游戏的 YSM 模型。
04. 第一步不是建模，是看懂图。T1 用 SAM2 轻量分割，五十九兆的模型，几秒钟切出二十四个部件。
05. 但 T1 只给可见轮廓，钢琴、沙发这些道具还会把掩膜抢走。
06. 要更细就上 T2：See-through 走 ComfyUI，十二点五 G 权重，首次二十二分钟，拆出二十九个语义层。
07. 每一层都有名字、有深度序，被挡住的部件还会补全。
08. 于是 AI 能一个部件一个部件地看，而不是凭整体印象。
09. 看图只是开始。第一轮二百一十七块，形有了，可角像两根小钩，裙子是一块黑盒子。
10. T1 复检挑出五个大问题：角、头发、裙摆、靴子、胸衣。照着层图逐条修，方块涨到三百五十五。
11. 第二轮是美术优化：角重做成连续螺旋带，背发分成四组窄束，眼睛改成菱形，最终四百零一块。
12. 二百一十七到四百零一，两次迭代，validate 零错误，导出就能进游戏。
13. 撑起这一切的，是四十一个工具、五十六个 bridge 方法：无头渲染、isolate 加 zoom、检查点、YSM 导出。
14. 0.9.2 已经在 GitHub 更新，二维码在这，欢迎 Star，也欢迎拿你自己的立绘来试。

---

## 4. 复现命令

```powershell
cd F:\Deepseek_harness\blockbench
pip install pillow numpy edge-tts imageio-ffmpeg qrcode
# 1) 先看每场静帧（media/_promo_stills/），不动视频
python media/build_update_promo.py --stills
# 2) 抽帧检查成片
python media/build_update_promo.py --check media/sakiko-0.9.2-promo.mp4
# 3) 正式渲染（约 12–15 分钟，逐帧 PIL + ffmpeg 管道，3305 帧）
python media/build_update_promo.py --full
# 4) 只重出封面
python media/build_update_promo.py --cover
```

TTS 缓存在 `media/_promo_tts/vNN_rRATE.wav`；改文案后删对应文件即可重配。
若 Edge TTS 不可达：脚本会抛错退出，可先 `--no-tts` 出纯字幕版（时长按字数估算），或修改 `VOICE` 常量换声线。

---

## 5. 自检结果

```text
| 时长 | **110.16 s** | 目标 95–115 s → ✅ |
| 分辨率 | **1920×1080** | 目标 1920×1080 → ✅ |
| 帧率 | **30.0 fps** | 目标 30 → ✅ |
| 视频编码 | **h264** | 目标 H.264 → ✅ |
| 音频编码 | **aac** | 需要 AAC 音轨 → ✅ |
| 文件体积 | **33.8 MB** | — |
| 黑帧检测 | 无 ≥0.3 s 黑段 | blackdetect d=0.3 / pix_th=0.12 |
| 响度 | 均值 -23.1 dB / 峰值 -5.4 dB | volumedetect（0 dBFS 天花板，未削波） |
```

抽帧目视：`media/_promo_check/`（脚本 `--check` 生成 8–11 张）——逐帧确认文字未溢出、图片未变形、无黑帧。

### 5.1 抽帧目视记录（成片 33.8 MB / 110.16 s）

`media/_promo_check/` 共 11 张（1.5s → 96.0s），逐张检查：

| 抽帧 | 场景 | 结论 |
|---|---|---|
| 1.5s | 开场 | 标题与模型淡入正常；本场不烧字幕（旁白即标题，避免重复） |
| 8.0s | 自己建 / 自己看 / 自己改 | 三卡 + 底部流程条，文字未溢出卡片 |
| 16.0s | 案例 | 立绘卡 1:1 内嵌不变形；70 / 401 / 2×512 三块对齐 |
| 25.0s | T1 | 参考图上的扫描光带 + `24 个候选部件`，无错位 |
| 34.0s | T1 → T2 转场 | 0.34s 划像，接缝带高光边，无重影（交叉淡化已弃用） |
| 44.0s | 29 层清单 | 两列 29 行逐行淡入；中文名 / 英文名 / 像素数三列不重叠 |
| 55.0s | 217 块 | 首轮渲染 + 三个问题，人物比例未拉伸 |
| 66.0s | 355 块 | ✓ 为矢量绘制（不依赖字体，避免方框）；计数动画正常 |
| 76.0s | 401 块 | 头部细节未裁切；计数器 355→401 中段 |
| 86.0s | 217→355→401 | 时间轴三节点 + validate 0 error |
| 96.0s | 工具链 | 六张卡，文字均在卡内 |

黑帧：blackdetect 无 ≥0.3 s 黑段；响度：均值 -23.1 dB / 峰值 -5.4 dB（未削波）。

---

## 6. 已知问题与剩余项

1. **旁白字数**：全文 540 字（含标点），纯汉字 360 字；略高于「420–520 字」推荐区间的上限，
   成品 110.2s 仍在 95–115s 内。若需严格压到 500 字以内，删 §3 第 05 或第 12 句即可（各约 30 字，
   删后需重跑 `--full`）。
2. **转场方式**：用 0.34s 划像替代交叉淡化——两页都是满屏文字时，交叉淡化会出现 0.3s 的重影。
3. **29 层的可读性**：原图是「暗色人物 + 大件道具 + 亮背景」的稠密插画，`front hair` 仅 2,606 px、
   `face` 1,772 px。片中如实按像素量展示（不放大、不虚构面积），逐层特写里小层会显得块状，属正常。
4. **T1 掩膜未上色**：24 张掩膜多数落在钢琴/沙发/基座上，直接叠色会误导成「切得很准」；
   片中用扫描光带 + 面积柱状图（57% / 50% / 26% …）说明「道具抢走掩膜」，符合 `SEG-CHECK.md` 的判定。
5. **未上传 B 站**：只产出可投稿文件（mp4 + 封面 + 文案），账号与上传由人工完成。

