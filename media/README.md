# media · 介绍视频与封面

本目录放 **B 站介绍视频**的生成脚本、封面和上传文案。

| 文件 | 说明 |
|---|---|
| `deepseek-blockbench-agent-intro.mp4` | 成片（1920×1080 / 30fps / H.264 + AAC / 约 2:46；不提交，随 Release 资产分发） |
| `build_slides.py` | 生成 12 页 1920×1080 幻灯片 + GitHub 封面 |
| `build_video.py` | Edge TTS 配音 + 生成音乐 + ffmpeg 合成视频 |
| `bilibili-cover.png` | B 站投稿封面（16:9） |
| `bilibili-upload.md` | 标题/简介/标签/章节/封面建议 |
| `frames/` | 幻灯片帧（可重新生成，不提交） |
| `_tts/` | TTS 音频/视频分段（可重新生成，不提交） |

## 重新生成

```powershell
pip install edge-tts imageio-ffmpeg qrcode
python media/build_slides.py
python media/build_video.py
```

依赖：Windows 中文字体（微软雅黑/Consolas）、ffmpeg（由 imageio-ffmpeg 提供）、Edge TTS 网络。

## 视频内容

- 开场：让 AI 真正走进 Blockbench
- 痛点：传统 AI 建模断在“最后一公里”
- 方案：dsh Host + 隐藏 Blockbench 闭环
- 能力总览：30 个语义工具
- 建模 / 贴图 / 渲染自检 / 动画与保存
- 游戏内验证（DeepSeek 鲸鱼娘测试模型）
- 安全/接管、优势对比、3 分钟上手
- 结尾：GitHub / Release / 使用手册二维码

无制作过程旁白，全部围绕功能、使用与优势。
