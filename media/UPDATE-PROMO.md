# UPDATE-PROMO · DSH × Blockbench Agent v0.9.2 更新宣传片

- **成片**：`media/sakiko-0.9.2-promo.mp4`（1920×1080 / 30fps / H.264 High + AAC 192k）
- **时长**：110.16s（目标 95–115s）
- **封面**：`media/bilibili-cover-0.9.2.png`（1920×1080）
- **投稿文案**：`media/bilibili-upload-0.9.2.md`
- **生成脚本**：`media/build_update_promo.py`
- **配音**：Edge TTS `zh-CN-XiaoxiaoNeural`，语速 +6%
- **生成时间**：generated

> 未上传 B 站（无账号）；仓库源码 / `models/` 未做任何修改，本轮只写 `media/`。

---

## 1. 素材来源（全部为仓库内真实文件，无 AI 生成图）

| 用途 | 文件 | 说明 |
|---|---|---|
| 最终四视图 | `models/togawa-sakiko/artifacts/renders/r0023/{front,back,left,iso_fr}_768.png` | 401 块最终模型，768²，透明背景 |
| 首轮 217 块 | `models/togawa-sakiko/artifacts/renders/r0021/front_768.png` | 首轮验收基线 |
| 中间态 355 块 | `models/togawa-sakiko/artifacts/t2-repair/renders/front_768.png` | T2 逐细节修理后 |
| 官方立绘 | `models/togawa-sakiko/refs/skin/sakiko_skin1.png` | 2176²，画面标注“官方参考” |
| T1 掩膜 | `models/togawa-sakiko/seg/sakiko_skin1/masks/*_part00..23.png` | 24 张 2176² 二值掩膜，片中逐张叠加 |
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
的 Ken Burns 推近 + 轻微横移；场景之间 0.34s 交叉淡化；底部逐句烧录中文字幕；底部细进度条。

---

## 3. 旁白全文（540 字）

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
# 3) 正式渲染（约 6–10 分钟，逐帧 PIL + ffmpeg 管道）
python media/build_update_promo.py --full
# 4) 只重出封面
python media/build_update_promo.py --cover
```

TTS 缓存在 `media/_promo_tts/vNN_rRATE.wav`；改文案后删对应文件即可重配。
若 Edge TTS 不可达，脚本会回退到 Windows SAPI（见 `--tts sapi`），只出声不出网。

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
