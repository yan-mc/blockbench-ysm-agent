# media · 0.9.2 更新宣传片（丰川祥子案例）

本目录存放 **DSH × Blockbench Agent v0.9.2 更新宣传片** 的成片、封面、投稿文案与生成脚本。

| 文件 | 说明 |
|---|---|
| `sakiko-0.9.2-promo.mp4` | 成片：1920×1080 / 30fps / H.264 + AAC / 110.2s |
| `bilibili-cover-0.9.2.png` | B 站投稿封面（1920×1080，最终模型图） |
| `bilibili-upload-0.9.2.md` | 标题 / 简介 / 标签 / 章节 / 封面建议 |
| `UPDATE-PROMO.md` | 素材来源、分镜表、旁白全文、复现命令、自检结果 |
| `build_update_promo.py` | 生成本片（PIL 逐帧 + Edge TTS + ffmpeg） |
| `_promo_tts/` `_promo_stills/` `_promo_check/` | TTS 缓存 / 场景静帧 / 抽帧自检（可重生成） |

## 重新生成

```powershell
pip install pillow numpy edge-tts imageio-ffmpeg qrcode
python media/build_update_promo.py --full
```
