"""Build the Bilibili intro video from generated slides + Edge TTS narration + generated ambient bed.

Output: media/deepseek-blockbench-agent-intro.mp4 (1920x1080, 30fps, H.264/AAC)
"""
import os
import re
import sys
import json
import math
import wave
import subprocess
import struct
from pathlib import Path

import numpy as np
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / 'media'
FRAMES = MEDIA / 'frames'
TTS = MEDIA / '_tts'
OUT = MEDIA / 'deepseek-blockbench-agent-intro.mp4'
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FFPROBE = None
NUL = 'NUL' if os.name == 'nt' else '/dev/null'
FPS = 30
VOICE = 'zh-CN-XiaoxiaoNeural'
os.makedirs(TTS, exist_ok=True)

segments = [
    dict(slide=0, text='如果 AI 不只是给你一段建模建议，而是能直接打开 Blockbench，建模、画贴图、渲染、自检，最后把模型送进 Minecraft 呢？这就是 DSH Blockbench Agent。'),
    dict(slide=1, text='大多数 AI 建模工具，只能生成步骤或代码。它看不见渲染结果，改坏了没有回滚，也不会帮你把 YSM 包、贴图、动画完整保存出来。'),
    dict(slide=2, text='这个插件把 DeepSeek Harness 和隐藏的 Blockbench 接成闭环：AI 通过工具操作模型，Blockbench 在后台无头渲染，图片再回到 AI 眼里，让它看见结果再继续改。'),
    dict(slide=3, text='它提供 30 个语义工具，覆盖从 YSM 工程创建、骨骼和方块编辑、像素贴图、动画与控制器，到无头渲染、检查点、校验和 zip 导出。'),
    dict(slide=4, text='建模不是点鼠标，而是语义化 patch：加骨骼、加方块、改尺寸、圆角、旋转，都可以一次提交，一次撤销、一个 revision。改了什么都可追溯。'),
    dict(slide=5, text='贴图可以精确到像素：矩形、线条、渐变、替换、镜像；还支持图层和 PBR 的 normal、specular 贴图。AI 不再只会描述颜色，它能直接改纹理。'),
    dict(slide=6, text='每次编辑后，它会渲染正面、侧面、特写，甚至两倍超采样。渲染结果会做变化检测和 watchdog 判定：连续改不出效果，就提示回滚或者换策略，避免空转。'),
    dict(slide=7, text='动画、控制器、检查点也都能用工具完成。检查点会连贴图和第一人称手臂一起保存；保存时只写改动，动画文件合并回写，不会把没改的动画全部重排。'),
    dict(slide=8, text='最后导出 YSM zip，放进游戏的 custom 目录，重载模型，就能在游戏里看到它。这个测试模型就是 DeepSeek 鲸鱼娘，蓝色大肥鱼本鱼。'),
    dict(slide=9, text='整个过程在隐藏窗口里进行，不抢你的焦点；写操作有 revision 校验和预算限制；需要人工时输入 /show，窗口出现，AI 自动暂停，改完再 /hide 交还。'),
    dict(slide=10, text='和普通脚本相比，它最大的优势不是工具多，而是闭环：看得到结果、能回滚、能保存、能在游戏里验证，还能随时让人接管。'),
    dict(slide=11, text='安装发布包到 dsh，打开任意会话，加载 blockbench-ysm-artist 技能就可以开始。仓库里有完整使用手册和这只大肥鱼模型，链接在简介和二维码里。'),
]

def run(args, **kwargs):
    return subprocess.run([FFMPEG] + args, capture_output=True, text=True, **kwargs)

def media_duration(path):
    r = subprocess.run([FFMPEG, '-hide_banner', '-i', str(path), '-f', 'null', NUL], capture_output=True, text=True)
    m = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.\d+)', r.stderr)
    if not m:
        raise RuntimeError(f'no duration for {path}: {r.stderr[-300:]}')
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

def tts_segment(i, text):
    mp3 = TTS / f'voice-{i:02d}.mp3'
    if not mp3.exists() or mp3.stat().st_size < 1000:
        r = subprocess.run([sys.executable, '-m', 'edge_tts', '--voice', VOICE, '--rate=+8%', '--volume=+0%', '--text', text, '--write-media', str(mp3)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f'edge-tts failed: {r.stderr[-400:]}')
    raw_dur = media_duration(mp3)
    wav = TTS / f'voice-{i:02d}.wav'
    # pad to leave a natural beat between slides
    pad = 0.62
    r = run(['-y', '-i', str(mp3), '-af', f'apad=pad_dur={pad}', '-ar', '44100', '-ac', '1', str(wav)])
    if r.returncode != 0:
        raise RuntimeError(f'audio pad failed: {r.stderr[-400:]}')
    return wav, raw_dur + pad

def make_video_segment(i, slide_path, dur):
    seg = TTS / f'seg-{i:02d}.mp4'
    frames = int(math.ceil(dur * FPS))
    # 2112x1188 source allows a subtle 1.0 -> 1.06 zoom without black edges
    vf = (
        'scale=2112:1188,'
        'zoompan=z=\'min(1.0+0.00055*on,1.06)\':x=\'iw/2-(iw/zoom/2)\':y=\'ih/2-(ih/zoom/2)\':'
        f'd=1:s=1920x1080:fps={FPS},'
        'format=yuv420p,'
        f'fade=t=in:st=0:d=0.32,fade=t=out:st={max(0.1, dur - 0.32):.3f}:d=0.32'
    )
    r = run(['-y', '-loop', '1', '-i', str(slide_path), '-t', f'{dur:.3f}', '-vf', vf,
             '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-an', str(seg)])
    if r.returncode != 0:
        raise RuntimeError(f'segment {i} failed: {r.stderr[-600:]}')
    return seg

def write_ambient(total):
    sr = 44100
    n = int(total * sr)
    t = np.arange(n, dtype=np.float64) / sr
    # slow, soft chord progression (A minor ambient) with gentle pulse
    chords = [
        [220.0, 261.63, 329.63],  # Am
        [174.61, 220.0, 261.63],  # F
        [196.0, 246.94, 293.66],  # G
        [164.81, 196.0, 246.94],  # Em
    ]
    out = np.zeros(n)
    for k in range(4):
        f = chords[k]
        env = 0.5 + 0.5 * np.cos(2 * math.pi * (t / 16.0 - k / 4.0))
        for j, freq in enumerate(f):
            out += (0.028 / (j + 1)) * env * np.sin(2 * math.pi * freq * t + k * 0.4)
    # subtle sparkle
    out += 0.006 * np.sin(2 * math.pi * 880 * t) * (0.5 + 0.5 * np.sin(2 * math.pi * 0.11 * t))
    # fade in/out
    fade = int(2.0 * sr)
    if n > 2 * fade:
        out[:fade] *= np.linspace(0, 1, fade)
        out[-fade:] *= np.linspace(1, 0, fade)
    out = out / max(1e-9, np.max(np.abs(out))) * 0.7
    path = MEDIA / 'music.wav'
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((out * 32767).astype('<i2').tobytes())
    return path

def main():
    # 1) narration
    total = 0.0
    for i, seg in enumerate(segments):
        wav, dur = tts_segment(i, seg['text'])
        seg['wav'] = wav
        seg['dur'] = dur
        total += dur
        print(f'[{i:02d}] voice {dur:.2f}s  {seg["text"][:24]}...')
    print('total', total)

    # 2) video segments
    seg_files = []
    for i, seg in enumerate(segments):
        slide = FRAMES / f'slide-{seg["slide"]:02d}.png'
        seg_files.append(make_video_segment(i, slide, seg['dur']))

    # 3) concat video
    list_file = TTS / 'segments.txt'
    list_file.write_text(''.join(f"file '{p.as_posix()}'\n" for p in seg_files), encoding='utf-8')
    silent = MEDIA / 'video-silent.mp4'
    r = run(['-y', '-f', 'concat', '-safe', '0', '-i', str(list_file), '-c', 'copy', str(silent)])
    if r.returncode != 0:
        raise RuntimeError(f'concat video failed: {r.stderr[-500:]}')

    # 4) concat voice
    vlist = TTS / 'voices.txt'
    vlist.write_text(''.join(f"file '{seg['wav'].as_posix()}'\n" for seg in segments), encoding='utf-8')
    voice = MEDIA / 'voice.wav'
    r = run(['-y', '-f', 'concat', '-safe', '0', '-i', str(vlist), '-ar', '44100', '-ac', '1', str(voice)])
    if r.returncode != 0:
        raise RuntimeError(f'concat voice failed: {r.stderr[-500:]}')

    # 5) music and mix
    music = write_ambient(total)
    mixed = MEDIA / 'video-mixed.mp4'
    r = run(['-y', '-i', str(silent), '-i', str(voice), '-i', str(music),
             '-filter_complex', '[1:a]volume=1.0[v];[2:a]volume=0.20[m];[v][m]amix=inputs=2:duration=first:dropout_transition=0,alimiter=limit=0.95[a]',
             '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', str(mixed)])
    if r.returncode != 0:
        raise RuntimeError(f'mix failed: {r.stderr[-600:]}')
    # finalize faststart + metadata
    r = run(['-y', '-i', str(mixed), '-c', 'copy', '-movflags', '+faststart',
             '-metadata', 'title=DSH Blockbench Agent 功能介绍',
             '-metadata', 'artist=yan-mc', str(OUT)])
    if r.returncode != 0:
        raise RuntimeError(f'finalize failed: {r.stderr[-600:]}')
    print(json.dumps({'out': str(OUT), 'duration': round(total, 2), 'bytes': OUT.stat().st_size}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
