# media · 介绍视频与封面

本目录放 **B 站介绍/更新视频**的生成脚本、封面和上传文案。

## 0.9.2 更新宣传片（当前，2026-11-07）

案例：丰川祥子「旋律的主人」；重点：**T1/T2 立绘拆分** + **217→355→401 块复杂逐步调整**。

| 文件 | 说明 |
|---|---|
| `sakiko-0.9.2-promo.mp4` | 成片（1920×1080 / 30fps / H.264 + AAC / **110s**；不提交仓库） |
| `build_update_promo.py` | 生成本片（PIL 逐帧 + Edge TTS + 程序化环境音乐 + ffmpeg） |
| `bilibili-cover-0.9.2.png` | B 站投稿封面（1920×1080，最终模型） |
| `bilibili-upload-0.9.2.md` | 标题 3 选 / 简介 / 标签 / 章节时间点 / 封面建议 |
| `README-0.9.2-promo.md` | 制件说明与重新生成命令 |
| `UPDATE-PROMO.md` | 素材来源、分镜表、旁白全文、自检结果 |
| `_promo_tts/` `_promo_stills/` `_promo_check/` | TTS/静帧/抽帧（可重生成，不提交） |

```powershell
pip install pillow numpy edge-tts imageio-ffmpeg qrcode
python media/build_update_promo.py --full
```

## 0.4.0 历史介绍片

| 文件 | 说明 |
|---|---|
| `deepseek-blockbench-agent-intro.mp4` | 成片（1920×1080 / 30fps / H.264 + AAC / 约 2:46；不提交，随 Release 资产分发） |
| `build_slides.py` | 生成 12 页 1920×1080 幻灯片 + GitHub 封面 |
| `build_video.py` | Edge TTS 配音 + 生成音乐 + ffmpeg 合成视频 |
| `bilibili-cover.png` | B 站投稿封面（16:9） |
| `bilibili-upload.md` | 标题/简介/标签/章节/封面建议 |
| `frames/` `_tts/` | 幻灯片帧与 TTS 分段（可重新生成，不提交） |

## 重新生成（旧片）

```powershell
pip install edge-tts imageio-ffmpeg qrcode
python media/build_slides.py
python media/build_video.py
```

依赖：Windows 中文字体（微软雅黑/Consolas）、ffmpeg（由 imageio-ffmpeg 提供）、Edge TTS 网络。

## 视频内容（旧片）

- 开场：让 AI 真正走进 Blockbench
- 痛点：传统 AI 建模断在“最后一公里”
- 方案：dsh Host + 隐藏 Blockbench 闭环
- 能力总览：41 个工具（43 定义）
- 建模 / 贴图 / 渲染自检 / 动画与保存
- 游戏内验证（DeepSeek 鲸鱼娘测试模型）
- 安全/接管、优势对比、3 分钟上手
- 结尾：GitHub / Release / 使用手册二维码

无制作过程旁白，全部围绕功能、使用与优势。
