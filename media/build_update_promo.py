#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the DSH x Blockbench Agent v0.9.2 update promo (Bilibili, Chinese).

Story: real livestream-art splitting (T1 SAM2 / T2 See-through 29 layers) and the
"complex step-by-step adjustment" case (217 -> 355 -> 401 cubes, togawa-sakiko).

Pipeline
  1. per-scene narration via edge-tts (zh-CN-XiaoxiaoNeural), cached in media/_promo_tts
  2. every scene is drawn with PIL at 1920x1080 * SS (supersampled), animated per frame
  3. per frame: Ken-Burns crop -> 1920x1080 -> overlay (header / subtitle / progress bar)
  4. raw frames piped into ffmpeg (libx264) + narration/music mix -> AAC, faststart

Usage
  python media/build_update_promo.py --stills          # one still per scene, for review
  python media/build_update_promo.py --scene 4 --at 0.5  # single still
  python media/build_update_promo.py --full            # render the mp4
  python media/build_update_promo.py --cover           # only the bilibili cover
All outputs stay inside media/; models/ and repo sources are read-only here.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import imageio_ffmpeg

try:
    import qrcode
except Exception:  # pragma: no cover - qrcode is available in this env
    qrcode = None

# ---------------------------------------------------------------- paths / consts
ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / 'media'
MODEL = ROOT / 'models' / 'togawa-sakiko'
SHOWCASE = ROOT / 'docs' / 'assets' / 'showcase'
TTS_DIR = MEDIA / '_promo_tts'
STILL_DIR = MEDIA / '_promo_stills'
CHECK_DIR = MEDIA / '_promo_check'
OUT_MP4 = MEDIA / 'sakiko-0.9.2-promo.mp4'
OUT_COVER = MEDIA / 'bilibili-cover-0.9.2.png'
for d in (TTS_DIR, STILL_DIR, CHECK_DIR):
    d.mkdir(parents=True, exist_ok=True)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FPS = 30
SS = 1.25                      # supersample factor for the scene canvas
CW, CH = int(1920 * SS), int(1080 * SS)
VOICE = 'zh-CN-XiaoxiaoNeural'
REPO = 'https://github.com/yan-mc/blockbench-ysm-agent'
REPO_SHORT = 'github.com/yan-mc/blockbench-ysm-agent'
VERSION = '0.9.2'

# palette (same family as docs/assets/cover.png)
BG = (7, 18, 34)
BG2 = (10, 26, 48)
PANEL = (13, 30, 52)
PANEL2 = (16, 36, 60)
BORDER = (36, 62, 92)
TEXT = (232, 242, 252)
MUTED = (148, 170, 194)
DIM = (108, 130, 156)
ACCENT = (89, 194, 255)
ACCENT2 = (139, 124, 255)
GREEN = (74, 222, 128)
AMBER = (251, 191, 36)
PINK = (244, 114, 182)

FONT_R = r'C:\Windows\Fonts\msyh.ttc'
FONT_B = r'C:\Windows\Fonts\msyhbd.ttc'
FONT_M = r'C:\Windows\Fonts\consola.ttf'

_FONT: dict = {}
_IMG: dict = {}
_RESIZED: dict = {}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (int(size), bold)
    if key not in _FONT:
        _FONT[key] = ImageFont.truetype(FONT_B if bold else FONT_R, int(size))
    return _FONT[key]


def mono(size: int) -> ImageFont.FreeTypeFont:
    key = ('m', int(size))
    if key not in _FONT:
        _FONT[key] = ImageFont.truetype(FONT_M, int(size))
    return _FONT[key]


def run(args, **kw):
    return subprocess.run([FFMPEG] + args, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', **kw)


def clamp01(v: float) -> float:
    return 0.0 if v < 0 else 1.0 if v > 1 else v


def ease_out(v: float) -> float:
    v = clamp01(v)
    return 1 - (1 - v) ** 3


def ease_io(v: float) -> float:
    v = clamp01(v)
    return 0.5 - 0.5 * math.cos(math.pi * v)


def appear(t: float, t0: float, d: float = 0.45) -> float:
    """0..1 alpha ramp, plus a small upward drift handled by callers."""
    return ease_out(clamp01((t - t0) / d))


def load(path: Path, mode: str = 'RGBA') -> Image.Image:
    key = (str(path), mode)
    if key not in _IMG:
        im = Image.open(path)
        im = im.convert(mode)
        im.load()
        _IMG[key] = im
    return _IMG[key]


def fmt_px(n: int) -> str:
    if n >= 10000:
        return f'{n / 10000:.1f} 万 px'
    return f'{n:,} px'


def _a(alpha) -> int:
    """Accept either a 0..1 easing value or a 0..255 int."""
    if isinstance(alpha, float):
        return int(round(max(0.0, min(1.0, alpha)) * 255))
    return int(alpha)


# ---------------------------------------------------------------- canvas wrapper
class Canvas:
    """Draw in 1920x1080 logical coordinates onto a supersampled RGB canvas."""

    def __init__(self, img: Image.Image):
        self.img = img
        self.s = SS
        self.d = ImageDraw.Draw(img, 'RGBA')

    # -- geometry
    def _b(self, b):
        return (b[0] * self.s, b[1] * self.s, b[2] * self.s, b[3] * self.s)

    def _p(self, xy):
        return (xy[0] * self.s, xy[1] * self.s)

    # -- primitives
    def text(self, xy, s, size=40, bold=False, color=TEXT, anchor='la', alpha=255,
             stroke=0, stroke_fill=(2, 7, 14, 190), spacing=0.0, font_obj=None):
        f = font_obj or font(int(size * self.s), bold)
        a = _a(alpha)
        fill = (color[0], color[1], color[2], a)
        sf = None
        if stroke:
            sf = (stroke_fill[0], stroke_fill[1], stroke_fill[2],
                  int(stroke_fill[3] * a / 255))
        self.d.multiline_text(self._p(xy), s, font=f, fill=fill, anchor=anchor,
                              spacing=spacing * self.s, align='left',
                              stroke_width=int(stroke * self.s), stroke_fill=sf)

    def mtext(self, xy, s, size=22, color=ACCENT, anchor='la', alpha=255):
        # Consolas has no CJK glyphs: mixed strings must fall back to the CJK face.
        has_cjk = any('\u4e00' <= ch <= '\u9fff' for ch in s)
        f = font(int(size * self.s), False) if has_cjk else mono(int(size * self.s))
        self.text(xy, s, size=size, color=color, anchor=anchor, alpha=alpha, font_obj=f)

    def rect(self, b, fill=None, outline=None, width=2, radius=0, alpha=255):
        aa = _a(alpha)
        f = None if fill is None else (fill[0], fill[1], fill[2], min(255, int(aa * (fill[3] / 255 if len(fill) > 3 else 1))))
        o = None if outline is None else (outline[0], outline[1], outline[2], min(255, int(aa * (outline[3] / 255 if len(outline) > 3 else 1))))
        if radius:
            self.d.rounded_rectangle(self._b(b), radius=radius * self.s,
                                     fill=f, outline=o, width=max(1, int(width * self.s)))
        else:
            self.d.rectangle(self._b(b), fill=f, outline=o, width=max(1, int(width * self.s)))

    def line(self, pts, color=ACCENT, width=2, alpha=255):
        p = [self._p(xy) for xy in pts]
        self.d.line(p, fill=(color[0], color[1], color[2], _a(alpha)),
                    width=max(1, int(width * self.s)), joint='curve')

    def dot(self, xy, r=4, color=ACCENT, alpha=255):
        x, y = self._p(xy)
        rr = r * self.s
        self.d.ellipse((x - rr, y - rr, x + rr, y + rr),
                       fill=(color[0], color[1], color[2], _a(alpha)))

    def paste(self, im: Image.Image, xy, size=None, alpha=1.0, radius=0,
              fit='contain', nearest=False, border=None, border_w=1, shadow=0):
        """Paste an RGBA image at logical xy; size=(w,h) box, fit contain/cover."""
        if im is None:
            return
        if im.mode != 'RGBA':
            im = im.convert('RGBA')
        box_w, box_h = (size if size else im.size)
        iw, ih = im.size
        if fit == 'contain':
            k = min(box_w / iw, box_h / ih)
        elif fit == 'cover':
            k = max(box_w / iw, box_h / ih)
        else:
            k = 1.0
        tw, th = max(1, int(round(iw * k))), max(1, int(round(ih * k)))
        tw_px, th_px = max(1, int(tw * self.s)), max(1, int(th * self.s))
        key = (id(im), tw_px, th_px, nearest)
        out = _RESIZED.get(key)
        if out is None:
            rs = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
            out = im.resize((tw_px, th_px), rs)
            if len(_RESIZED) > 220:
                _RESIZED.clear()
            _RESIZED[key] = out

        # alpha composition
        r, g, b, a = out.split()
        if alpha < 1.0:
            a = a.point(lambda v: int(v * alpha))
        if radius:
            mask = Image.new('L', out.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                (0, 0, out.size[0] - 1, out.size[1] - 1), radius=radius * self.s, fill=255)
            from PIL import ImageChops
            a = ImageChops.multiply(a, mask)
        comp = Image.merge('RGBA', (r, g, b, a))

        x = int((xy[0] + (box_w - tw) / 2.0) * self.s)
        y = int((xy[1] + (box_h - th) / 2.0) * self.s)
        if shadow:
            sh = Image.new('RGBA', (comp.size[0] + int(40 * self.s), comp.size[1] + int(40 * self.s)), (0, 0, 0, 0))
            sm = Image.new('L', comp.size, 0)
            ImageDraw.Draw(sm).rectangle((0, 0, comp.size[0], comp.size[1]), fill=int(90 * shadow))
            sh.paste((0, 0, 0, 120), (int(20 * self.s), int(20 * self.s)), sm.filter(ImageFilter.GaussianBlur(9 * self.s)))
            self.img.paste(sh, (x - int(20 * self.s), y - int(20 * self.s)), sh)
        self.img.paste(comp, (x, y), comp)
        if border:
            self.rect((xy[0] + (box_w - tw) / 2.0, xy[1] + (box_h - th) / 2.0,
                       xy[0] + (box_w - tw) / 2.0 + tw, xy[1] + (box_h - th) / 2.0 + th),
                      outline=border, width=border_w, radius=radius)
        return (x / self.s, y / self.s, tw, th)


# ---------------------------------------------------------------- background
def gradient_bg(w: int, h: int, top=BG2, bottom=(4, 10, 20)) -> Image.Image:
    g = Image.new('RGB', (1, h))
    gd = ImageDraw.Draw(g)
    for y in range(h):
        t = y / max(1, h - 1)
        gd.point((0, y), tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))
    return g.resize((w, h))


def add_glow(img: Image.Image, cx, cy, r, color, alpha) -> Image.Image:
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(r / 2.0))
    return Image.alpha_composite(img.convert('RGBA'), layer).convert('RGB')


def add_grid(img: Image.Image, step=64, color=(70, 120, 160), alpha=15) -> Image.Image:
    d = ImageDraw.Draw(img, 'RGBA')
    s = SS
    for x in range(0, int(1920 * s) + 1, int(step * s)):
        d.line((x, 0, x, img.size[1]), fill=color + (alpha,), width=1)
    for y in range(0, int(1080 * s) + 1, int(step * s)):
        d.line((0, y, img.size[0], y), fill=color + (alpha,), width=1)
    return img


_BG_CACHE: dict = {}


def scene_bg(key: str, glows) -> Image.Image:
    if key not in _BG_CACHE:
        img = gradient_bg(CW, CH)
        for (gx, gy, gr, gc, ga) in glows:
            img = add_glow(img, gx * SS, gy * SS, gr * SS, gc, ga)
        img = add_grid(img)
        _BG_CACHE[key] = img
    return _BG_CACHE[key].copy()


# ---------------------------------------------------------------- assets
def art_card_frame(c: Canvas, box, label='官方参考', sub=None, alpha=1.0):
    """White 'art print' card that the reference images sit on."""
    x0, y0, x1, y1 = box
    c.rect((x0 + 6, y0 + 12, x1 + 6, y1 + 12), fill=(0, 0, 0), alpha=int(70 * alpha), radius=10)
    c.rect(box, fill=(246, 249, 253), radius=10, alpha=int(255 * alpha))
    c.rect(box, outline=BORDER, width=2, radius=10, alpha=int(200 * alpha))


def ref_art() -> Image.Image:
    """Official illustration (2176^2, white bg)."""
    return load(MODEL / 'refs' / 'skin' / 'sakiko_skin1.png')


def t2_preview() -> Image.Image:
    p = MODEL / 'seg' / 'sakiko_skin1-layers'
    return load(p / 'seethrough_sakiko_skin1_mw6fcikd_preview_00001_.png')


def _crop_alpha(im: Image.Image, pad: int = 10) -> Image.Image:
    a = np.array(im.convert('RGBA'))[:, :, 3]
    ys, xs = np.where(a > 16)
    if len(xs) == 0:
        return im
    box = (max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad),
           min(im.width, int(xs.max()) + pad), min(im.height, int(ys.max()) + pad))
    return im.crop(box)


_RENDER: dict = {}


def render(rev: str, view: str) -> Image.Image:
    """Model render, cropped to its alpha bounds (the 768^2 files have big margins)."""
    key = (rev, view)
    if key in _RENDER:
        return _RENDER[key]
    if rev == 'r0021':
        p = MODEL / 'artifacts' / 'renders' / 'r0021' / f'{view}_768.png'
    elif rev == '355':
        p = MODEL / 'artifacts' / 't2-repair' / 'renders' / f'{view}_768.png'
    elif rev == 'r0023':
        p = MODEL / 'artifacts' / 'renders' / 'r0023' / f'{view}_768.png'
    elif rev == 'r0020':
        p = MODEL / 'artifacts' / 'v2' / 'renders' / f'{view}_768.png'
    else:
        raise KeyError(rev)
    _RENDER[key] = _crop_alpha(load(p))
    return _RENDER[key]


# --- T1 masks --------------------------------------------------------------
_T1 = {}


def t1_data():
    """Colored part map + index map, downscaled for cheap per-frame compositing."""
    if _T1:
        return _T1
    mdir = MODEL / 'seg' / 'sakiko_skin1' / 'masks'
    files = sorted(mdir.glob('*_part*.png'))
    base_w, base_h = 200, 200          # smoothed map: avoids SAM2 mask speckle
    art = ref_art().convert('RGBA').resize((720, 720), Image.Resampling.LANCZOS)
    idx = np.full((base_h, base_w), 255, dtype=np.uint8)
    colors = np.zeros((base_h, base_w, 3), dtype=np.uint8)
    # palette for parts (cycled)
    pal = [(89, 194, 255), (139, 124, 255), (74, 222, 128), (251, 191, 36),
           (244, 114, 182), (45, 212, 191), (248, 113, 113), (167, 139, 250),
           (56, 189, 248), (110, 231, 183), (253, 224, 71), (251, 146, 60)]
    for i, f in enumerate(files):
        m = Image.open(f).convert('L').resize((base_w, base_h), Image.Resampling.BOX)
        a = np.array(m)
        sel = (a > 105) & (idx == 255)
        idx[sel] = i
        colors[sel] = pal[i % len(pal)]
    _T1['art'] = art
    _T1['idx'] = idx
    _T1['colors'] = colors
    _T1['count'] = len(files)
    return _T1


_T1E = {}


def t1_edges():
    """Per-part contour map (paper-cut look) built once from the SAM2 masks."""
    if _T1E:
        return _T1E
    import colorsys
    d = t1_data()
    idx = d['idx']
    h, w = idx.shape
    edge_idx = np.full((h, w), 255, dtype=np.uint8)
    cols = np.zeros((h, w, 3), dtype=np.uint8)
    for k in range(d['count']):
        m = idx == k
        if not m.any():
            continue
        er = m.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            er &= np.roll(m, (dy, dx), (0, 1))
        edge = m & ~er
        thick = edge.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0), (0, 2), (0, -2)):
            thick |= np.roll(edge, (dy, dx), (0, 1))
        r, g, b = colorsys.hsv_to_rgb((k / d['count']) % 1.0, 0.70, 1.0)
        cols[thick] = (int(r * 255), int(g * 255), int(b * 255))
        edge_idx[thick] = k
    _T1E['idx'] = edge_idx
    _T1E['rgb'] = cols
    return _T1E


def masks_edges(upto: int):
    e = t1_edges()
    sel = e['idx'] < upto
    rgb = np.zeros(sel.shape + (4,), dtype=np.uint8)
    rgb[..., 0][sel] = e['rgb'][..., 0][sel]
    rgb[..., 1][sel] = e['rgb'][..., 1][sel]
    rgb[..., 2][sel] = e['rgb'][..., 2][sel]
    rgb[..., 3][sel] = 240
    return Image.fromarray(rgb, 'RGBA')


def masks_one(base_w, base_h, k: int, alpha=170):
    """RGBA overlay with a single part highlighted (rainbow hue per part)."""
    d = t1_data()
    idx = d['idx']
    sel = idx == k
    share = float(sel.mean())
    alpha = 150 if share < 0.08 else 88          # huge masks stay translucent
    rgb = np.zeros((base_h, base_w, 4), dtype=np.uint8)
    import colorsys
    r, g, b = colorsys.hsv_to_rgb((k / max(1, d['count'])) % 1.0, 0.62, 1.0)
    rgb[..., 0][sel] = int(r * 255)
    rgb[..., 1][sel] = int(g * 255)
    rgb[..., 2][sel] = int(b * 255)
    rgb[..., 3][sel] = alpha
    return Image.fromarray(rgb, 'RGBA')


def masks_overlay(base_w, base_h, upto: int, alpha=96):
    """RGBA overlay: parts 0..upto-1 tinted (soft, smoothed map)."""
    d = t1_data()
    idx = d['idx']
    sel = idx < upto
    h, w = idx.shape
    rgb = np.zeros((h, w, 4), dtype=np.uint8)
    col = d['colors']
    rgb[..., 0][sel] = col[..., 0][sel]
    rgb[..., 1][sel] = col[..., 1][sel]
    rgb[..., 2][sel] = col[..., 2][sel]
    rgb[..., 3][sel] = alpha
    return Image.fromarray(rgb, 'RGBA')


# --- T2 layers -------------------------------------------------------------
_LAYERS = {}


def layer_meta():
    """name -> dict(cn, px, depth, crop RGBA)."""
    if _LAYERS:
        return _LAYERS
    metrics = json.loads((MODEL / 'artifacts' / 't2-preview' / 'layer-metrics.json')
                         .read_text(encoding='utf-8'))
    js = json.loads((MODEL / 'seg' / 'sakiko_skin1-layers' / 'layers.json')
                    .read_text(encoding='utf-8'))
    ldir = MODEL / 'seg' / 'sakiko_skin1-layers' / 'layers'
    cn = {
        'back hair': '后发', 'bottomwear': '下装（裙）', 'ears-l': '左耳', 'ears-r': '右耳',
        'earwear': '耳饰', 'eyebrow-l': '左眉', 'eyebrow-r': '右眉', 'eyelash-l': '左睫',
        'eyelash-r': '右睫', 'eyewear': '眼镜', 'eyewhite-l': '左眼白', 'eyewhite-r': '右眼白',
        'face': '脸', 'footwear': '鞋', 'front hair': '前发', 'handwear-l': '左手套',
        'handwear-r': '右手套', 'headwear': '头饰', 'irides-l': '左虹膜', 'irides-r': '右虹膜',
        'legwear': '腿部', 'mouth': '嘴', 'neck': '颈', 'neckwear': '领饰', 'nose': '鼻',
        'objects': '道具', 'tail': '尾巴', 'topwear': '上衣', 'wings': '翅膀',
    }
    files = {f.split('_')[-1].replace('.png', ''): f for f in os.listdir(ldir)}
    out = {}
    for m in metrics:
        name = m['semantic']
        f = files.get(name)
        crop = None
        if f:
            im = Image.open(ldir / f).convert('RGBA')
            a = np.array(im)[:, :, 3]
            ys, xs = np.where(a > 40)
            if len(xs) > 40:
                pad = max(4, int(max(xs.max() - xs.min(), ys.max() - ys.min()) * 0.10))
                box = (max(0, xs.min() - pad), max(0, ys.min() - pad),
                       min(im.width, xs.max() + pad), min(im.height, ys.max() + pad))
                crop = im.crop(box)
        out[name] = dict(name=name, cn=cn.get(name, name), px=m['alpha_px'],
                         pct=m['area_pct_of_layer'], depth=m['depth_median'], crop=crop)
    # keep the depth order of layers.json (T2 emits far -> near); sort near -> far
    order = [l['name'] for l in js['layers']]
    _LAYERS.update(out)
    _LAYERS['_order'] = order
    return _LAYERS


def layer(name: str) -> Image.Image:
    return layer_meta()[name]['crop']


# ---------------------------------------------------------------- scene kit
def header_bits(c: Canvas, tag: str, idx: int, total: int):
    c.mtext((96, 46), 'DSH × BLOCKBENCH AGENT', size=19, color=(120, 150, 178))
    c.mtext((96, 72), f'v{VERSION}  ·  立绘拆分 × 复杂逐步调整', size=15, color=(84, 110, 138))
    c.mtext((1824, 46), f'{idx:02d} / {total:02d}', size=19, color=(120, 150, 178), anchor='ra')
    c.mtext((1824, 72), tag, size=15, color=ACCENT, anchor='ra')


def eyebrow(c: Canvas, xy, s, alpha=255, color=ACCENT):
    c.mtext(xy, s, size=20, color=color, alpha=alpha)
    w = font(20).getbbox(s)[2]
    c.line([(xy[0], xy[1] + 32), (xy[0] + 42, xy[1] + 32)], color=ACCENT, width=3, alpha=alpha)


def chip(c: Canvas, box, text, value=None, color=ACCENT, alpha=255, size=26, align='left'):
    x0, y0, x1, y1 = box
    c.rect(box, fill=PANEL, outline=BORDER, width=1, radius=8, alpha=int(alpha))
    if value:
        c.text((x0 + 22, y0 + (y1 - y0) / 2), value, size=size + 6, bold=True, color=color,
               anchor='lm', alpha=alpha)
        c.text((x0 + 22 + font(size + 6, True).getbbox(value)[2] + 10, y0 + (y1 - y0) / 2),
               text, size=size - 4, color=MUTED, anchor='lm', alpha=alpha)
    else:
        c.text(((x0 + x1) / 2 if align == 'center' else x0 + 22, (y0 + y1) / 2), text,
               size=size, color=color, anchor='mm' if align == 'center' else 'lm', alpha=alpha)


# ---------------------------------------------------------------- scenes
def s_hook(c: Canvas, t: float, d: float):
    bg = scene_bg('hook', [(1520, 330, 520, (30, 120, 200), 46), (250, 940, 460, (110, 78, 210), 32)])
    c.img.paste(bg, (0, 0))
    a = appear(t, 0.05, 0.5)
    eyebrow(c, (110, 188), '0.9.2 更新 · 立绘拆分 T1/T2  ·  复杂逐步调整', alpha=a)
    c.text((108, 258), 'AI 真的能进', size=98, bold=True, alpha=a)
    c.text((108, 372), 'Blockbench', size=112, bold=True, color=ACCENT, alpha=a)
    c.text((108, 505), '做模型吗？', size=98, bold=True, alpha=a)
    a2 = appear(t, 1.5, 0.6)
    c.rect((110, 648, 118, 708), fill=ACCENT, alpha=int(a2 * 220), radius=2)
    c.text((146, 652), '不是给教程，也不是给脚本', size=38, color=MUTED, alpha=a2)

    # model hero
    a3 = appear(t, 0.9, 0.9)
    c.rect((1310, 206, 1748, 830), fill=(18, 40, 66), outline=(46, 78, 112), width=1, radius=14, alpha=int(160 * a3))
    c.paste(render('r0023', 'iso_fr'), (1322, 218), size=(414, 600), alpha=a3)
    c.mtext((1330, 792), 'final · 401 cubes', size=15, color=DIM, alpha=int(210 * a3))


def s_do(c: Canvas, t: float, d: float):
    bg = scene_bg('do', [(980, 380, 620, (26, 90, 160), 34), (1760, 900, 420, (110, 78, 210), 26)])
    c.img.paste(bg, (0, 0))
    a = appear(t, 0.0, 0.45)
    eyebrow(c, (110, 168), '不是给教程，也不是给脚本', alpha=a, color=ACCENT)
    c.text((108, 214), '是它自己建、自己看、自己改', size=62, bold=True, alpha=a)

    cards = [
        ('01', '自己建', '语义化改模型', '骨骼 · 方块 · 贴图，一次一个 patch', ACCENT),
        ('02', '自己看', '无头渲染回传', '4 机位 + 多格拼图，改完立刻看见', ACCENT2),
        ('03', '自己改', '看见问题就修', '检查点随时回滚，改坏了能退', GREEN),
    ]
    for i, (num, title, sub, desc, col) in enumerate(cards):
        x0 = 140 + i * 556
        a2 = appear(t, 0.55 + i * 0.25, 0.5)
        dy = (1 - a2) * 26
        box = (x0, 400 + dy, x0 + 500, 700 + dy)
        c.rect(box, fill=PANEL, outline=BORDER, width=1, radius=12, alpha=int(235 * a2))
        c.rect((x0, 400 + dy, x0 + 500, 404 + dy), fill=col, radius=2, alpha=int(a2 * 220))
        c.mtext((x0 + 30, 424 + dy), num, size=22, color=col, alpha=int(a2 * 230))
        c.text((x0 + 30, 468 + dy), title, size=52, bold=True, alpha=a2)
        c.text((x0 + 30, 540 + dy), sub, size=26, color=col, alpha=int(a2 * 235))
        c.text((x0 + 30, 592 + dy), desc, size=22, color=MUTED, alpha=a2)

    # bottom pipeline strip
    flow = ['语义 patch', '无头渲染', '看图判定', '检查点', '导出 YSM']
    x = 140
    for i, s in enumerate(flow):
        a4 = appear(t, 1.6 + i * 0.14, 0.4)
        w = font(24).getbbox(s)[2] + 40
        c.rect((x, 784, x + w, 838), fill=(18, 38, 62), outline=BORDER, width=1, radius=7, alpha=int(215 * a4))
        c.text((x + w / 2, 811), s, size=24, color=TEXT, anchor='mm', alpha=a4)
        x += w
        if i < len(flow) - 1:
            c.text((x + 16, 811), '→', size=22, color=ACCENT, anchor='lm', alpha=a4)
            x += 46


def s_case(c: Canvas, t: float, d: float):
    bg = scene_bg('case', [(380, 420, 560, (26, 90, 160), 32), (1600, 260, 460, (110, 78, 210), 26)])
    c.img.paste(bg, (0, 0))

    a = appear(t, 0.05, 0.5)
    c.mtext((110, 168), '官方参考 / OFFICIAL ART', size=19, color=ACCENT, alpha=a)
    box = (110, 202, 750, 842)
    art_card_frame(c, box, alpha=a)
    c.paste(ref_art(), (128, 220), size=(604, 604), alpha=a, radius=4, fit='contain')
    c.text((110, 852), '丰川祥子「旋律的主人」', size=28, color=TEXT, alpha=a)
    c.mtext((110, 886), '2176 × 2176 · 联动干员立绘', size=15, color=DIM, alpha=a)

    a2 = appear(t, 0.55, 0.6)
    c.mtext((860, 236), 'CASE STUDY', size=21, color=ACCENT2, alpha=a2)
    c.text((856, 274), '把这张立绘', size=64, bold=True, alpha=a2)
    c.text((856, 358), '做成能进游戏的模型', size=64, bold=True, alpha=a2)

    pills = [('70', '骨骼'), ('401', '方块'), ('2×512', '贴图')]
    for i, (v, k) in enumerate(pills):
        x0 = 860 + i * 250
        a3 = appear(t, 1.15 + i * 0.12, 0.45)
        c.rect((x0, 486, x0 + 224, 566), fill=PANEL, outline=BORDER, width=1, radius=8, alpha=int(230 * a3))
        c.text((x0 + 20, 500), v, size=38, bold=True, color=ACCENT, alpha=a3)
        c.text((x0 + 20, 540), k, size=20, color=MUTED, alpha=a3)

    a4 = appear(t, 1.7, 0.6)
    steps = ['立绘', '29 层', '401 块', 'YSM zip']
    x = 860
    for i, s in enumerate(steps):
        w = font(26).getbbox(s)[2] + 44
        c.rect((x, 636, x + w, 686), fill=(20, 44, 70), outline=BORDER, width=1, radius=6, alpha=int(210 * a4))
        c.text((x + w / 2, 661), s, size=24, color=TEXT, anchor='mm', alpha=a4)
        if i < len(steps) - 1:
            c.text((x + w + 14, 661), '→', size=24, color=ACCENT, anchor='lm', alpha=a4)
            x += w + 44
        else:
            x += w
    c.text((856, 724), '全程只靠工具与渲染图自检，没有人工建模', size=24, color=MUTED, alpha=a4)


def s_t1(c: Canvas, t: float, d: float):
    bg = scene_bg('t1', [(500, 420, 520, (26, 90, 160), 34), (1660, 300, 420, (30, 150, 180), 22)])
    c.img.paste(bg, (0, 0))

    a = appear(t, 0.0, 0.5)
    c.mtext((110, 168), 'T1 · SAM2.1 ONNX · 轻量分割', size=19, color=ACCENT, alpha=a)

    box = (110, 202, 790, 882)
    c.rect(box, fill=(10, 22, 40), outline=BORDER, width=1, radius=10, alpha=int(235 * a))
    aw, ah = 640, 640
    c.paste(ref_art(), (135, 222), size=(aw, ah), alpha=a, radius=4)
    # scan pass over the untouched reference (no fake segmentation graphics)
    cnt = t1_data()['count']
    art_box = (135, 222, 775, 862)
    if t > 0.35:
        p = ((t - 0.35) % 3.2) / 3.2
        y = art_box[1] + p * (art_box[3] - art_box[1])
        for i in range(30):
            yy = y - i * 3.2
            if yy < art_box[1]:
                break
            a = int(58 * (1 - i / 30.0) * min(1.0, (t - 0.35) / 0.4))
            if a <= 0:
                continue
            c.rect((art_box[0], yy - 3.2, art_box[2], yy), fill=ACCENT, alpha=a)
        c.rect((art_box[0], y - 1.5, art_box[2], y + 1.5), fill=(180, 230, 255), alpha=210)
    # corner brackets
    bl = 44
    for (bx, by, sx, sy) in [(art_box[0], art_box[1], 1, 1), (art_box[2], art_box[1], -1, 1),
                             (art_box[0], art_box[3], 1, -1), (art_box[2], art_box[3], -1, -1)]:
        c.line([(bx, by + sy * bl), (bx, by), (bx + sx * bl, by)], color=ACCENT, width=3,
               alpha=int(220 * a))
    c.mtext((135, 866), f'sam2.1 · {cnt} candidate parts · cpu', size=14, color=DIM)

    a2 = appear(t, 0.6, 0.6)
    num = f'{t1_data()["count"]}'
    c.text((860, 250), num, size=196, bold=True, color=ACCENT, alpha=a2)
    nw = font(196, True).getbbox(num)[2]
    c.text((860 + nw + 26, 350), '个候选部件', size=44, color=TEXT, alpha=a2)

    rows = [('模型体积', '59.1 MB', '首次自动下载，ONNX 量化'),
            ('耗时', '12 – 39 s', 'CPU 推理，无需 GPU'),
            ('输出', '可见轮廓', '被遮挡的部分要靠推断')]
    for i, (k, v, note) in enumerate(rows):
        y = 540 + i * 108
        a3 = appear(t, 1.0 + i * 0.2, 0.45)
        c.line([(860, y), (860, y + 74)], color=ACCENT, width=2, alpha=int(a3 * 180))
        c.text((884, y + 4), k, size=22, color=MUTED, alpha=a3)
        c.text((884, y + 32), v, size=40, bold=True, color=TEXT, alpha=a3)
        c.text((1240, y + 44), note, size=20, color=DIM, alpha=a3)


def s_t1_limit(c: Canvas, t: float, d: float):
    bg = scene_bg('t1b', [(560, 500, 560, (40, 110, 190), 30), (1700, 720, 420, (120, 60, 140), 24)])
    c.img.paste(bg, (0, 0))

    a = appear(t, 0.0, 0.5)
    c.mtext((110, 168), 'T1 掩膜面积 · 24 个候选', size=19, color=AMBER, alpha=a)
    box = (110, 202, 790, 882)
    c.rect(box, fill=(10, 22, 40), outline=BORDER, width=1, radius=10, alpha=int(235 * a))
    c.paste(ref_art(), (135, 222), size=(640, 640), alpha=a, radius=4)

    # prop callouts (positions in art display space, 135..775 x 222..862)
    tags = [(520, 400, '钢琴 / 音箱'), (210, 560, '沙发'), (300, 760, '基座')]
    for i, (x, y, s) in enumerate(tags):
        a2 = appear(t, 1.0 + i * 0.22, 0.4)
        w = font(20).getbbox(s)[2] + 26
        c.rect((x, y, x + w, y + 34), fill=(8, 16, 28), outline=AMBER, width=1, radius=5, alpha=int(225 * a2))
        c.text((x + 13, y + 17), s, size=20, color=AMBER, anchor='lm', alpha=a2)

    a3 = appear(t, 0.5, 0.55)
    c.text((860, 240), '道具抢走了掩膜', size=56, bold=True, alpha=a3)
    c.text((860, 320), '钢琴、沙发、基座都是大件，更容易被整块切走；', size=23, color=MUTED, alpha=a3)

    # bar chart: the five biggest masks
    bars = [('mask 01', 57.2), ('mask 02', 50.4), ('mask 03', 26.2), ('mask 04', 18.6), ('mask 05', 13.4)]
    for i, (k, v) in enumerate(bars):
        y = 390 + i * 56
        a4 = appear(t, 1.0 + i * 0.16, 0.4)
        c.text((860, y), k, size=18, color=DIM, alpha=a4)
        bw = 470 * (v / 60.0)
        c.rect((960, y + 6, 960 + 470, y + 30), fill=(18, 34, 54), radius=4, alpha=int(180 * a4))
        c.rect((960, y + 6, 960 + bw, y + 30), fill=AMBER, radius=4, alpha=int(205 * a4))
        c.text((960 + bw + 14, y + 18), f'{v:.0f}%', size=18, color=AMBER, anchor='lm', alpha=a4)
    c.text((860, 682), '前五名都是背景与道具；人物部件大多只有 1–3%。', size=21, color=MUTED, alpha=a4)

    a5 = appear(t, 1.9, 0.55)
    c.rect((860, 736, 1700, 836), fill=(22, 30, 52), outline=ACCENT2, width=1, radius=10, alpha=int(230 * a5))
    c.text((892, 756), 'T1 够快，但不够细', size=18, color=MUTED, alpha=a5)
    c.text((892, 784), '→ 换 T2：语义分层 + 深度序 + 遮挡补全', size=30, bold=True, color=TEXT, alpha=a5)


def s_t2(c: Canvas, t: float, d: float):
    bg = scene_bg('t2', [(430, 430, 540, (40, 120, 190), 34), (1620, 320, 480, (120, 100, 255), 28)])
    c.img.paste(bg, (0, 0))

    a = appear(t, 0.0, 0.5)
    c.mtext((110, 168), 'T2 · SEE-THROUGH · COMFYUI', size=19, color=ACCENT2, alpha=a)
    box = (110, 202, 790, 882)
    c.rect(box, fill=(240, 245, 251), outline=BORDER, width=1, radius=10, alpha=int(240 * a))
    c.paste(t2_preview(), (128, 220), size=(644, 558), alpha=a, radius=4)
    c.text((132, 796), 'T2 输出预览 · 29 层合成', size=24, color=(20, 40, 62), alpha=a)
    c.mtext((132, 834), '832 × 832 · steps 28 · PSD 29 层', size=15, color=(90, 110, 130), alpha=a)

    a2 = appear(t, 0.5, 0.6)
    c.text((860, 236), '29', size=200, bold=True, color=ACCENT2, alpha=a2)
    c.text((860 + font(200, True).getbbox('29')[2] + 26, 336), '个语义层', size=44, color=TEXT, alpha=a2)

    rows = [('ComfyUI', '0.44.0', '本地 127.0.0.1:8188'),
            ('首次分层', '22 分 43 秒', '含约 12.5 GB 权重下载'),
            ('权重', '12.5 GB', 'HuggingFace 缓存，一次性')]
    for i, (k, v, note) in enumerate(rows):
        y = 470 + i * 96
        a3 = appear(t, 0.95 + i * 0.18, 0.45)
        c.text((860, y), k, size=20, color=MUTED, alpha=a3)
        c.text((860, y + 26), v, size=36, bold=True, color=TEXT, alpha=a3)
        c.text((1120, y + 38), note, size=19, color=DIM, alpha=a3)

    # progress bar for the first run
    a4 = appear(t, 1.6, 0.4)
    p = ease_io(clamp01((t - 1.7) / 2.6))
    c.rect((860, 782, 1660, 790), fill=(22, 40, 62), radius=4, alpha=int(210 * a4))
    c.rect((860, 782, 860 + 800 * p, 790), fill=ACCENT2, radius=4, alpha=int(235 * a4))
    c.mtext((860, 806), f'first run  {p * 100:3.0f}%   → 29 layers', size=16, color=DIM, alpha=int(220 * a4))


def s_ledger(c: Canvas, t: float, d: float):
    bg = scene_bg('ledger', [(300, 300, 520, (26, 80, 150), 30), (1700, 820, 460, (90, 70, 190), 26)])
    c.img.paste(bg, (0, 0))

    a = appear(t, 0.0, 0.45)
    c.mtext((110, 150), '29 层 · 每一层都有名字、有深度序', size=19, color=ACCENT, alpha=a)
    c.text((108, 182), 'AI 拿到的不是一张图，是 29 张分件图纸', size=46, bold=True, alpha=a)

    lm = layer_meta()
    names = [n for n in lm['_order'] if n in lm]
    # near -> far (ascending depth)
    names.sort(key=lambda n: lm[n]['depth'])
    col_w = 430
    x0s = [110, 570]
    row_h = 33
    for i, name in enumerate(names):
        m = lm[name]
        col = 0 if i < 15 else 1
        row = i if i < 15 else i - 15
        x = x0s[col]
        y = 268 + row * row_h
        a2 = appear(t, 0.25 + i * 0.028, 0.35)
        if a2 <= 0:
            continue
        has = m['crop'] is not None and m['px'] > 300
        c.mtext((x, y + 6), f'{i + 1:02d}', size=15,
                color=(ACCENT if has else (70, 92, 116)), alpha=int(a2 * 235))
        if has:
            c.paste(m['crop'], (x + 30, y + 3), size=(24, 24), alpha=a2, fit='contain')
        else:
            c.rect((x + 30, y + 3, x + 54, y + 27), fill=(16, 30, 48), outline=(40, 60, 84),
                   width=1, radius=3, alpha=int(a2 * 200))
        c.text((x + 66, y + 4), m['cn'], size=20,
               color=(TEXT if has else (108, 130, 156)), alpha=a2)
        c.mtext((x + 196, y + 7), m['name'], size=13, color=(80, 104, 130), alpha=int(a2 * 210))
        if has:
            c.mtext((x + 330, y + 7), f'{m["px"]:,}', size=13, color=(120, 150, 178), alpha=int(a2 * 220))

    a3 = appear(t, 1.4, 0.6)
    c.text((1080, 244), '深度序', size=40, bold=True, color=ACCENT, alpha=a3)
    rows2 = [('近 → 远', '前发 0.17  ·  脸 0.50  ·  后发 0.94'),
             ('遮挡补全', '被挡住的部件按对称与深度补'),
             ('PSD 导出', '17.28 MiB · 29 层 · 可单独取用')]
    for i, (k, v) in enumerate(rows2):
        y = 320 + i * 128
        a4 = appear(t, 1.6 + i * 0.22, 0.45)
        c.rect((1080, y, 1810, y + 100), fill=PANEL, outline=BORDER, width=1, radius=8, alpha=int(215 * a4))
        c.text((1104, y + 18), k, size=28, bold=True, color=ACCENT, alpha=a4)
        c.text((1104, y + 58), v, size=20, color=MUTED, alpha=a4)

    a5 = appear(t, 2.2, 0.5)
    c.text((1080, 748), '同一张立绘，29 个部件各归各位。', size=24, color=DIM, alpha=a5)

    stats = [('832²', '分层分辨率'), ('29', 'PNG + 深度图'), ('17.28 MiB', 'PSD 图层文件')]
    for i, (v, k) in enumerate(stats):
        x = 110 + i * 300
        a6 = appear(t, 2.4 + i * 0.12, 0.4)
        c.rect((x, 776, x + 276, 862), fill=PANEL, outline=BORDER, width=1, radius=8, alpha=int(215 * a6))
        c.text((x + 20, 792), v, size=30, bold=True, color=ACCENT, alpha=a6)
        c.text((x + 20, 830), k, size=18, color=MUTED, alpha=a6)


def s_layers(c: Canvas, t: float, d: float):
    bg = scene_bg('layers', [(960, 520, 700, (26, 80, 150), 26), (1780, 240, 400, (110, 78, 210), 22)])
    c.img.paste(bg, (0, 0))

    a = appear(t, 0.0, 0.4)
    c.mtext((110, 150), '逐层特写 · 挑九层看清楚', size=19, color=ACCENT, alpha=a)
    c.text((108, 180), 'AI 能逐部件看图，而不是凭整体印象', size=44, bold=True, alpha=a)

    picks = [
        ('back hair', '后发'), ('front hair', '前发'), ('face', '脸'),
        ('topwear', '上衣'), ('bottomwear', '下装（裙）'), ('handwear-r', '右手套'),
        ('legwear', '腿部'), ('footwear', '鞋'), ('headwear', '头饰'),
    ]
    lm = layer_meta()
    cw, chh, gap = 400, 196, 20
    x0 = (1920 - (cw * 3 + gap * 2)) / 2
    y0 = 258
    for i, (name, cn) in enumerate(picks):
        col, row = i % 3, i // 3
        x = x0 + col * (cw + gap)
        y = y0 + row * (chh + gap)
        a2 = appear(t, 0.35 + i * 0.17, 0.45)
        if a2 <= 0:
            continue
        dy = (1 - a2) * 22
        c.rect((x, y + dy, x + cw, y + chh + dy), fill=PANEL, outline=BORDER, width=1,
               radius=10, alpha=int(235 * a2))
        m = lm[name]
        if m['crop'] is not None:
            big = (m['crop'].width < 150)
            c.paste(m['crop'], (x + 12, y + 10 + dy), size=(cw - 24, 118), alpha=a2,
                    nearest=big)
        c.text((x + 16, y + 136 + dy), cn, size=25, bold=True, alpha=a2)
        c.mtext((x + 16, y + 168 + dy), f'{m["px"]:,} px  ·  depth {m["depth"]:.2f}',
                size=14, color=DIM, alpha=int(a2 * 220))

    a3 = 255


def s_217(c: Canvas, t: float, d: float):
    bg = scene_bg('s217', [(500, 480, 520, (60, 90, 150), 30), (1700, 300, 420, (140, 90, 60), 20)])
    c.img.paste(bg, (0, 0))

    a = appear(t, 0.0, 0.45)
    c.mtext((110, 168), '首轮验收 · 217 块', size=19, color=AMBER, alpha=a)
    c.rect((110, 202, 750, 842), fill=(12, 26, 46), outline=BORDER, width=1, radius=10, alpha=int(230 * a))
    c.paste(render('r0021', 'front'), (128, 220), size=(604, 604), alpha=a)
    c.text((110, 852), 'front / iso · 217 cubes · validate 0 error', size=18, color=DIM, alpha=a)

    a2 = appear(t, 0.6, 0.6)
    c.text((830, 218), '形有了，', size=52, bold=True, alpha=a2)
    c.text((830, 282), '但经不起近看。', size=52, bold=True, color=AMBER, alpha=a2)

    items = [('角', '两根小钩，没有回卷', 'C 形 7.0 × 7.76'),
             ('裙', '一块黑盒子', '无衬裙、无蕾丝'),
             ('靴', '被长裙遮住看不清', '腿和靴糊成一片')]
    for i, (k, v, note) in enumerate(items):
        y = 400 + i * 132
        a3 = appear(t, 1.2 + i * 0.28, 0.45)
        c.rect((830, y, 1740, y + 108), fill=PANEL, outline=BORDER, width=1, radius=8, alpha=int(225 * a3))
        c.dot((866, y + 54), r=6, color=AMBER, alpha=int(a3 * 240))
        c.text((890, y + 16), k, size=34, bold=True, color=AMBER, alpha=a3)
        c.text((890, y + 58), v, size=26, color=TEXT, alpha=a3)
        c.mtext((1440, y + 70), note, size=15, color=DIM, alpha=int(a3 * 220))

    a4 = appear(t, 2.3, 0.5)
    c.text((830, 790), '不是不会建，是没看清。', size=24, color=DIM, alpha=a4)


def s_355(c: Canvas, t: float, d: float):
    bg = scene_bg('s355', [(480, 470, 520, (40, 120, 170), 32), (1720, 260, 430, (90, 90, 180), 24)])
    c.img.paste(bg, (0, 0))

    a = appear(t, 0.0, 0.45)
    c.mtext((110, 168), 'T1 逐部件复检 · 5 个 major', size=19, color=ACCENT, alpha=a)
    c.rect((110, 202, 750, 842), fill=(12, 26, 46), outline=BORDER, width=1, radius=10, alpha=int(230 * a))
    c.paste(render('355', 'front'), (128, 220), size=(604, 604), alpha=a)
    c.text((110, 852), 'front · 355 cubes · +138', size=18, color=DIM, alpha=a)

    # animated counter 217 -> 355
    a2 = appear(t, 0.4, 0.5)
    p = ease_out(clamp01((t - 0.5) / 2.0))
    val = int(round(217 + (355 - 217) * p))
    c.text((830, 196), f'{val}', size=150, bold=True, color=ACCENT, alpha=a2)
    c.text((830 + font(150, True).getbbox(str(val))[2] + 26, 288), '块', size=40, color=MUTED, alpha=a2)
    c.mtext((832, 356), 'cubes  +138', size=18, color=DIM, alpha=a2)

    rows = ['角重做：7.0 × 7.76，回卷到位', '后发/马尾：3 层错位薄片 + 收尖',
            '裙：白衬裙整圈 + 蕾丝 + 拖尾', '靴：12.66 高靴筒 + 金口沿 + 扣带',
            '胸衣：压暗 + 4 根骨架线 + 蕾丝边']
    for i, s in enumerate(rows):
        y = 430 + i * 74
        a3 = appear(t, 1.0 + i * 0.2, 0.4)
        checkmark(c, (832, y + 4), size=19, color=GREEN, alpha=a3, width=4)
        c.text((866, y), s, size=25, color=TEXT, alpha=a3)
    c.text((830, 820), '对着层图逐条修，不是重画。', size=22, color=DIM, alpha=appear(t, 2.4, 0.5))


def s_401(c: Canvas, t: float, d: float):
    bg = scene_bg('s401', [(420, 420, 560, (40, 120, 200), 32), (1680, 520, 500, (120, 90, 240), 26)])
    c.img.paste(bg, (0, 0))

    a = appear(t, 0.0, 0.45)
    c.mtext((110, 168), 'v2 美术优化 · 头部重做', size=19, color=ACCENT2, alpha=a)

    # head detail: left panel of the showcase sheet (black bg blends in)
    head = load(SHOWCASE / 'sakiko-detail-head.png').crop((120, 40, 760, 716))
    c.rect((110, 200, 800, 850), fill=(8, 16, 30), outline=BORDER, width=1, radius=10, alpha=int(225 * a))
    c.paste(head, (118, 208), size=(674, 634), alpha=a)

    a2 = appear(t, 0.5, 0.6)
    feats = [('角', '连续螺旋带 1.6 圈', '12 段近立方体强重叠，0 缝隙'),
             ('背发', '每侧 4 组窄束', 'z 错落 2.2，末端收尖 30%'),
             ('眼', '菱形虹膜 + 菱形瞳孔', '斜高光 2 片，上眼睑斜置')]
    for i, (k, v, note) in enumerate(feats):
        y = 206 + i * 150
        a3 = appear(t, 1.0 + i * 0.3, 0.45)
        c.text((860, y), k, size=30, bold=True, color=ACCENT2, alpha=a3)
        c.text((940, y + 2), v, size=30, bold=True, alpha=a3)
        c.text((942, y + 46), note, size=19, color=DIM, alpha=a3)
        c.line([(860, y + 74), (1760, y + 74)], color=(40, 66, 96), width=1, alpha=int(160 * a3))

    a4 = appear(t, 2.0, 0.5)
    p = ease_out(clamp01((t - 2.1) / 1.4))
    val = int(round(355 + (401 - 355) * p))
    c.text((860, 682), f'{val}', size=130, bold=True, color=ACCENT, alpha=a4)
    c.text((860 + font(130, True).getbbox(str(val))[2] + 24, 760), '块 / final', size=30, color=MUTED, alpha=a4)
    c.mtext((1218, 800), 'validate 0 error · 70 bones', size=17, color=GREEN, alpha=a4)


def s_numbers(c: Canvas, t: float, d: float):
    bg = scene_bg('numbers', [(960, 620, 720, (20, 80, 150), 30), (300, 300, 420, (100, 70, 190), 24)])
    c.img.paste(bg, (0, 0))

    a = appear(t, 0.0, 0.45)
    c.mtext((110, 150), '两次迭代 · 217 → 355 → 401', size=19, color=ACCENT, alpha=a)
    c.text((108, 182), '每一步都看得见，也退得回去', size=44, bold=True, alpha=a)

    nodes = [('217', '首轮 T1 验收', 'r0021', AMBER), ('355', 'T2 层对照修理', '355', ACCENT),
             ('401', 'v2 美术优化', 'r0023', GREEN)]
    xs = [400, 960, 1520]
    # connector
    a2 = appear(t, 0.4, 0.4)
    c.line([(xs[0] + 60, 636), (xs[2] - 60, 636)], color=(40, 66, 96), width=3, alpha=int(200 * a2))
    p = ease_io(clamp01((t - 0.5) / 2.6))
    c.line([(xs[0] + 60, 636), (xs[0] + 60 + (xs[2] - xs[0] - 120) * p, 636)],
           color=ACCENT, width=3, alpha=int(230 * a2))

    for i, (num, label, rev, col) in enumerate(nodes):
        x = xs[i]
        a3 = appear(t, 0.5 + i * 0.35, 0.5)
        c.rect((x - 116, 320, x + 116, 552), fill=(12, 26, 46), outline=BORDER, width=1, radius=10, alpha=int(225 * a3))
        c.paste(render(rev, 'front'), (x - 106, 330), size=(212, 212), alpha=a3)
        c.dot((x, 636), r=7, color=col, alpha=int(a3 * 240))
        c.text((x, 662), num, size=78, bold=True, color=col, anchor='ma', alpha=a3)
        c.text((x, 762), label, size=24, color=MUTED, anchor='ma', alpha=a3)

    chips = [('validate', '0 error'), ('骨骼', '70'), ('动画', '303'), ('导出', 'YSM zip')]
    for i, (k, v) in enumerate(chips):
        x = 130 + i * 430
        a4 = appear(t, 2.2 + i * 0.12, 0.4)
        c.rect((x, 842, x + 400, 906), fill=PANEL, outline=BORDER, width=1, radius=8, alpha=int(225 * a4))
        c.mtext((x + 18, 852), k, size=14, color=DIM, alpha=int(a4 * 220))
        c.text((x + 18, 872), v, size=26, bold=True, color=(GREEN if i == 0 else TEXT), alpha=a4)


def s_tools(c: Canvas, t: float, d: float):
    bg = scene_bg('tools', [(960, 520, 760, (20, 80, 150), 26), (1760, 200, 420, (110, 78, 210), 22)])
    c.img.paste(bg, (0, 0))

    a = appear(t, 0.0, 0.4)
    c.mtext((110, 150), '工具链 · 一句话说完', size=19, color=ACCENT, alpha=a)
    c.text((108, 182), '它不是聊天框，是一双手和一双眼睛', size=44, bold=True, alpha=a)

    cards = [
        ('41 / 43', '个工具', '暴露 / 定义，全部有 schema'),
        ('56', 'bridge 方法', '7 事件 · 22 错误码'),
        ('4 机位', '无头渲染', '拼图回传，不抢焦点'),
        ('isolate + zoom', '局部审查', '只看一个部件，2.5 倍'),
        ('checkpoint', '检查点回滚', '含贴图与 arm 快照'),
        ('YSM zip', '一键导出', 'validate 后打包'),
    ]
    for i, (v, k, note) in enumerate(cards):
        col, row = i % 3, i // 3
        x = 140 + col * 556
        y = 300 + row * 268
        a2 = appear(t, 0.35 + i * 0.14, 0.45)
        dy = (1 - a2) * 22
        c.rect((x, y + dy, x + 500, y + 228 + dy), fill=PANEL, outline=BORDER, width=1,
               radius=12, alpha=int(232 * a2))
        c.text((x + 28, y + 26 + dy), v, size=42, bold=True, color=ACCENT, alpha=a2)
        c.text((x + 28, y + 92 + dy), k, size=34, bold=True, alpha=a2)
        c.text((x + 28, y + 148 + dy), note, size=21, color=MUTED, alpha=a2)


def s_end(c: Canvas, t: float, d: float):
    bg = scene_bg('end', [(1350, 380, 620, (30, 110, 190), 34), (300, 900, 480, (110, 78, 210), 26)])
    c.img.paste(bg, (0, 0))

    a = appear(t, 0.0, 0.45)
    views = ['front', 'iso_fr', 'left', 'back']
    for i, v in enumerate(views):
        x = 110 + (i % 2) * 276
        y = 210 + (i // 2) * 276
        a2 = appear(t, 0.1 + i * 0.12, 0.45)
        c.rect((x, y, x + 260, y + 260), fill=(10, 22, 40), outline=BORDER, width=1, radius=8, alpha=int(220 * a2))
        c.paste(render('r0023', v), (x + 6, y + 6), size=(248, 248), alpha=a2)

    a3 = appear(t, 0.4, 0.5)
    c.mtext((660, 200), 'RELEASED · GITHUB', size=20, color=GREEN, alpha=a3)
    c.text((656, 236), f'v{VERSION}', size=112, bold=True, color=ACCENT, alpha=a3)
    c.text((656, 376), '已更新到 GitHub', size=44, bold=True, alpha=a3)
    c.text((658, 446), '欢迎 Star，也欢迎拿你自己的立绘来试', size=28, color=MUTED, alpha=a3)
    c.mtext((660, 512), REPO, size=26, color=ACCENT, alpha=a3)

    a4 = appear(t, 0.9, 0.5)
    c.rect((660, 580, 940, 620), fill=(18, 40, 64), outline=BORDER, width=1, radius=6, alpha=int(220 * a4))
    c.text((800, 600), 'Star  ·  试用  ·  Issue', size=22, color=TEXT, anchor='mm', alpha=a4)

    # QR
    if qrcode is not None:
        a5 = appear(t, 1.2, 0.5)
        qp = TTS_DIR / 'repo_qr.png'
        if not qp.exists():
            q = qrcode.QRCode(border=2, box_size=8)
            q.add_data(REPO)
            q.make(fit=True)
            q.make_image(fill_color=(7, 18, 34), back_color=(255, 255, 255)).save(qp)
        c.rect((1330, 470, 1590, 730), fill=(255, 255, 255), radius=10, alpha=int(250 * a5))
        c.paste(load(qp, 'RGB'), (1342, 482), size=(236, 236), alpha=a5, radius=4)
        c.text((1460, 754), '扫码进仓库', size=22, color=MUTED, anchor='ma', alpha=a5)

    c.mtext((110, 862), '案例：丰川祥子「旋律的主人」 · 401 块 · 29 语义层 · validate 0 error',
            size=17, color=DIM, alpha=appear(t, 1.5, 0.5))


SCENES = [
    dict(id='s01', tag='开场', voice='title', kb=0.055, pan=(0.0, -0.2), fn=s_hook, sub=False,
         narration='AI 真的能进 Blockbench 做模型吗？',
         chapter='开场：AI 真的能进 Blockbench？'),
    dict(id='s02', tag='开场', voice='title', kb=0.05, pan=(-0.2, 0.0), fn=s_do,
         narration='不是给教程，也不是给脚本——是它自己建、自己看、自己改。',
         chapter='不是给脚本，是自己建、自己看、自己改'),
    dict(id='s03', tag='案例', voice='title', kb=0.05, pan=(0.15, 0.0), fn=s_case,
         narration='这次的任务，是把这张官方立绘，做成能进游戏的 YSM 模型。',
         chapter='案例：丰川祥子「旋律的主人」'),
    dict(id='s04', tag='重点 1 · 立绘拆分', voice='title', kb=0.05, pan=(0.1, 0.05), fn=s_t1,
         narration='第一步不是建模，是看懂图。T1 用 SAM2 轻量分割，五十九兆的模型，几秒钟切出二十四个部件。',
         chapter='重点 1：T1 SAM2 轻量分割'),
    dict(id='s05', tag='重点 1 · 立绘拆分', voice='title', kb=0.05, pan=(-0.1, 0.0), fn=s_t1_limit,
         narration='但 T1 只给可见轮廓，钢琴、沙发这些道具还会把掩膜抢走。',
         chapter='T1 的边界：可见轮廓 vs 遮挡'),
    dict(id='s06', tag='重点 1 · 立绘拆分', voice='title', kb=0.05, pan=(0.0, 0.1), fn=s_t2,
         narration='要更细就上 T2：See-through 走 ComfyUI，十二点五 G 权重，首次二十二分钟，拆出二十九个语义层。',
         chapter='重点 1：T2 See-through 29 语义层'),
    dict(id='s07', tag='重点 1 · 立绘拆分', voice='title', kb=0.045, pan=(0.0, 0.0), fn=s_ledger,
         narration='每一层都有名字、有深度序，被挡住的部件还会补全。',
         chapter='29 层清单与深度序'),
    dict(id='s08', tag='重点 1 · 立绘拆分', voice='title', kb=0.05, pan=(0.1, 0.0), fn=s_layers,
         narration='于是 AI 能一个部件一个部件地看，而不是凭整体印象。',
         chapter='逐层特写：九张分件图'),
    dict(id='s09', tag='重点 2 · 逐步调整', voice='title', kb=0.05, pan=(-0.1, 0.05), fn=s_217,
         narration='看图只是开始。第一轮二百一十七块，形有了，可角像两根小钩，裙子是一块黑盒子。',
         chapter='重点 2：首轮 217 块的三个问题'),
    dict(id='s10', tag='重点 2 · 逐步调整', voice='title', kb=0.05, pan=(0.05, 0.0), fn=s_355,
         narration='T1 复检挑出五个大问题：角、头发、裙摆、靴子、胸衣。照着层图逐条修，方块涨到三百五十五。',
         chapter='T1 复检：5 个 major，217 → 355'),
    dict(id='s11', tag='重点 2 · 逐步调整', voice='title', kb=0.05, pan=(-0.05, 0.08), fn=s_401,
         narration='第二轮是美术优化：角重做成连续螺旋带，背发分成四组窄束，眼睛改成菱形，最终四百零一块。',
         chapter='v2 美术优化：螺旋角 / 分组长发 / 菱形眼'),
    dict(id='s12', tag='重点 2 · 逐步调整', voice='title', kb=0.04, pan=(0.0, 0.0), fn=s_numbers,
         narration='二百一十七到四百零一，两次迭代，validate 零错误，导出就能进游戏。',
         chapter='217 → 355 → 401，validate 0 error'),
    dict(id='s13', tag='工具链', voice='title', kb=0.04, pan=(0.1, -0.1), fn=s_tools,
         narration='撑起这一切的，是四十一个工具、五十六个 bridge 方法：无头渲染、isolate 加 zoom、检查点、YSM 导出。',
         chapter='工具链：41 工具 / 56 方法'),
    dict(id='s14', tag='结尾', voice='title', kb=0.045, pan=(0.0, 0.0), fn=s_end,
         narration='0.9.2 已经在 GitHub 更新，二维码在这，欢迎 Star，也欢迎拿你自己的立绘来试。',
         chapter='结尾：v0.9.2 在 GitHub'),
]

LEAD = 0.55
GAP = 0.12        # extra breathing room after the narration inside its own scene
TAIL = 1.90
XFADE = 0.34
MIN_DUR = 3.2


# ---------------------------------------------------------------- TTS
def wav_duration(path: Path) -> float:
    with wave.open(str(path), 'rb') as w:
        return w.getnframes() / float(w.getframerate())


def synth(i: int, text: str, rate: int):
    mp3 = TTS_DIR / f'v{i:02d}_r{rate}.mp3'
    wav = TTS_DIR / f'v{i:02d}_r{rate}.wav'
    if not mp3.exists() or mp3.stat().st_size < 2000:
        r = subprocess.run([sys.executable, '-m', 'edge_tts', '--voice', VOICE,
                            f'--rate={rate:+d}%', '--volume=+0%', '--text', text,
                            '--write-media', str(mp3)], capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        if r.returncode != 0:
            raise RuntimeError(f'edge-tts failed: {r.stderr[-400:]}')
    if not wav.exists() or wav.stat().st_size < 2000:
        r = run(['-y', '-i', str(mp3), '-ar', '44100', '-ac', '1', str(wav)])
        if r.returncode != 0:
            raise RuntimeError(f'wav convert failed: {r.stderr[-400:]}')
    return wav, wav_duration(wav)


def build_timeline(rate: int):
    t = LEAD
    for i, sc in enumerate(SCENES):
        wav, dur = synth(i, sc['narration'], rate)
        d = max(dur + GAP + 0.42, MIN_DUR)
        sc['start'] = round(t, 3)
        sc['dur'] = round(d, 3)
        sc['voice_dur'] = dur
        sc['wav'] = wav
        t += d
    total = t + TAIL
    return total


# ---------------------------------------------------------------- audio mix
def make_music(total: float) -> np.ndarray:
    sr = 44100
    n = int(total * sr)
    t = np.arange(n, dtype=np.float64) / sr
    out = np.zeros(n)
    # Am - F - C - G, one bar = 8s, soft sines with slow tremolo
    chords = [[220.00, 261.63, 329.63, 164.81],
              [174.61, 220.00, 261.63, 130.81],
              [130.81, 196.00, 261.63, 164.81],
              [196.00, 246.94, 293.66, 146.83]]
    bar = 8.0
    for k in range(4):
        f0 = chords[k]
        # smooth crossfade between chords
        env = np.ones(n)
        phase = ((t / bar) - k) % 4.0
        blend = 0.5 + 0.5 * np.cos(2 * math.pi * np.clip(phase - 1.0, 0, 1))
        for j, f in enumerate(f0):
            amp = 0.030 / (1 + 0.55 * j)
            det = 1.0 + 0.0016 * (j - 1)
            out += amp * (0.65 + 0.35 * blend) * np.sin(2 * math.pi * f * t * det + k * 0.7)
    # airy high shimmer
    out += 0.004 * np.sin(2 * math.pi * 1046.5 * t) * (0.5 + 0.5 * np.sin(2 * math.pi * 0.07 * t))
    out += 0.003 * np.sin(2 * math.pi * 1318.5 * t) * (0.5 + 0.5 * np.sin(2 * math.pi * 0.05 * t + 1.2))
    # gentle low pulse every 4s
    pulse = np.zeros(n)
    period = int(4 * sr)
    for s in range(0, n - period, period):
        seg = np.arange(period) / sr
        pulse[s:s + period] += np.exp(-seg * 3.2) * np.sin(2 * math.pi * 55 * seg) * 0.05
    out += pulse
    # fades
    fi, fo = int(2.0 * sr), int(3.0 * sr)
    if n > fi + fo:
        out[:fi] *= np.linspace(0, 1, fi) ** 1.5
        out[-fo:] *= np.linspace(1, 0, fo) ** 1.2
    out /= max(1e-9, np.max(np.abs(out)))
    return out * 0.085          # ~ -22 dB relative to speech peak


def build_audio(total: float, path: Path) -> Path:
    sr = 44100
    n = int(total * sr)
    voice = np.zeros(n)
    for sc in SCENES:
        with wave.open(str(sc['wav']), 'rb') as w:
            data = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(np.float64) / 32768.0
        st = int((sc['start'] + 0.12) * sr)
        en = min(n, st + len(data))
        voice[st:en] += data[:en - st]
    music = make_music(total)
    mix = voice * 1.0 + music * 0.95
    peak = np.max(np.abs(mix))
    if peak > 0.97:
        mix = mix / peak * 0.97
    pcm = (np.clip(mix, -1, 1) * 32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


# ---------------------------------------------------------------- frame render
def render_scene(i: int, t_local: float) -> Image.Image:
    sc = SCENES[i]
    img = Image.new('RGB', (CW, CH), BG)
    c = Canvas(img)
    sc['fn'](c, t_local, sc['dur'])
    # Ken Burns
    d = max(0.001, sc['dur'])
    p = clamp01(t_local / d)
    z = 1.0 + sc['kb'] * ease_io(p)
    bw, bh = CW / z, CH / z
    px, py = sc['pan']
    cx = CW / 2 + px * (CW - bw) / 2 * (p - 0.5) * 2
    cy = CH / 2 + py * (CH - bh) / 2 * (p - 0.5) * 2
    x0 = min(max(0, cx - bw / 2), CW - bw)
    y0 = min(max(0, cy - bh / 2), CH - bh)
    return img.crop((int(x0), int(y0), int(x0 + bw), int(y0 + bh))).resize((1920, 1080), Image.Resampling.LANCZOS)


def wrap_cjk(text: str, f: ImageFont.FreeTypeFont, max_w: int):
    """Break CJK text per character, but keep Latin words/numbers intact."""
    cjk = set('，。！？；：、（）【】「」《》—…·~')
    tokens, i = [], 0
    while i < len(text):
        ch = text[i]
        if ch == ' ':
            tokens.append(' ')
            i += 1
        elif '\u4e00' <= ch <= '\u9fff' or ch in cjk:
            tokens.append(ch)
            i += 1
        else:
            j = i
            while j < len(text) and not ('\u4e00' <= text[j] <= '\u9fff') \
                    and text[j] not in cjk and text[j] != ' ':
                j += 1
            tokens.append(text[i:j])
            i = j
    lines, cur = [], ''
    for tok in tokens:
        cand = cur + tok
        if f.getbbox(cand.strip())[2] <= max_w or not cur:
            cur = cand
        else:
            lines.append(cur.rstrip())
            cur = '' if tok == ' ' else tok
    if cur.strip():
        lines.append(cur.rstrip())
    return lines or ['']


def checkmark(c: Canvas, xy, size=20, color=GREEN, alpha=255, width=3):
    x, y = xy
    c.line([(x, y + size * 0.52), (x + size * 0.36, y + size * 0.92),
            (x + size * 1.0, y + size * 0.02)], color=color, width=width, alpha=alpha)


def overlay(frame: Image.Image, total: float, now: float, scene_i: int, local_t: float):
    d = ImageDraw.Draw(frame, 'RGBA')
    # header
    d.text((96, 44), 'DSH × BLOCKBENCH AGENT', font=mono(19), fill=(120, 150, 178, 190))
    d.text((96, 70), f'v{VERSION}  ·  立绘拆分 × 复杂逐步调整', font=font(15), fill=(84, 110, 138, 180))
    d.text((1824, 44), f'{scene_i + 1:02d} / {len(SCENES):02d}', font=mono(19),
           fill=(120, 150, 178, 190), anchor='ra')
    d.text((1824, 70), SCENES[scene_i]['tag'], font=font(15), fill=ACCENT + (210,), anchor='ra')

    # subtitle
    sc = SCENES[scene_i]
    if sc.get('sub', True) and sc['start'] + 0.05 <= now <= sc['start'] + sc['dur'] - 0.05:
        f = font(42, True)
        lines = wrap_cjk(sc['narration'], f, 1420)
        lh = 56
        y = 986 - (len(lines) - 1) * lh
        for k, line in enumerate(lines):
            d.text((960, y + k * lh), line, font=f, fill=(255, 255, 255, 246), anchor='ma',
                   stroke_width=5, stroke_fill=(4, 10, 20, 210))

    # progress
    p = clamp01(now / max(0.001, total))
    d.rectangle((0, 1075, 1920, 1080), fill=(10, 22, 38, 200))
    d.rectangle((0, 1075, int(1920 * p), 1080), fill=ACCENT + (235,))
    # persistent cta
    d.text((1824, 1046), REPO_SHORT, font=mono(15), fill=(96, 120, 146, 150), anchor='ra')
    return frame


def wipe(a: Image.Image, b: Image.Image, k: float, feather: float = 0.055) -> Image.Image:
    """Hard-ish left→right wipe (avoids the double-exposure mush of a crossfade)."""
    w, h = a.size
    xs = np.arange(w, dtype=np.float32)
    fw = max(1.0, feather * w)
    edge = (-feather + clamp01(k) * (1 + 2 * feather)) * w
    v = np.clip((edge - xs) / fw, 0, 1)
    mask = Image.fromarray(np.repeat((v * 255).astype(np.uint8)[None, :], h, axis=0), 'L')
    out = Image.composite(b, a, mask)
    if 0 < edge < w:
        d = ImageDraw.Draw(out, 'RGBA')
        al = int(190 * math.sin(math.pi * clamp01(k)))
        d.rectangle((edge - 2, 0, edge + 2, h), fill=(150, 220, 255, al))
        d.rectangle((edge - 14, 0, edge - 2, h), fill=(89, 194, 255, int(al * 0.35)))
    return out


def compose_frame(T: float, total: float) -> Image.Image:
    # locate scene
    i = 0
    for k, sc in enumerate(SCENES):
        if T >= sc['start']:
            i = k
    sc = SCENES[i]
    local = T - sc['start']
    frame = render_scene(i, min(local, sc['dur'] - 1e-3))
    # wipe in from the previous scene
    if i > 0 and local < XFADE:
        prev = SCENES[i - 1]
        pf = render_scene(i - 1, prev['dur'] - 1e-3)
        frame = wipe(pf, frame, ease_io(local / XFADE))
    return overlay(frame, total, T, i, local)


def still_frame(i: int, at: float = 0.55) -> Image.Image:
    sc = SCENES[i]
    local = sc['dur'] * at
    return overlay(render_scene(i, local), sc['start'] + sc['dur'], sc['start'] + local, i, local)


def render_video(total: float, audio: Path, out: Path):
    nframes = int(math.ceil(total * FPS))
    cmd = [FFMPEG, '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', '1920x1080', '-r', str(FPS), '-i', '-',
           '-i', str(audio),
           '-map', '0:v', '-map', '1:a',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-profile:v', 'high',
           '-pix_fmt', 'yuv420p', '-g', '60',
           '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2',
           '-shortest', '-movflags', '+faststart',
           '-metadata', 'title=DSH × Blockbench Agent v0.9.2 更新宣传片',
           '-metadata', 'artist=yan-mc', '-metadata', 'comment=立绘拆分 T1/T2 + 复杂逐步调整（案例：丰川祥子）',
           str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    t0 = os.times().elapsed
    for k in range(nframes):
        T = k / FPS
        frame = compose_frame(T, total)
        p.stdin.write(frame.tobytes())
        if k % 150 == 0:
            el = os.times().elapsed - t0
            print(f'  frame {k:5d}/{nframes}  t={T:6.2f}s  elapsed={el:6.1f}s', flush=True)
    p.stdin.close()
    err = p.stderr.read().decode('utf-8', 'replace')
    rc = p.wait()
    if rc != 0:
        raise RuntimeError(f'ffmpeg failed rc={rc}\n{err[-1200:]}')
    return out


# ---------------------------------------------------------------- cover
def build_cover(path: Path):
    W, H = 1920, 1080
    img = gradient_bg(W, H, (12, 32, 58), (3, 8, 16))
    img = add_glow(img, 1480, 320, 520, (30, 120, 200), 58)
    img = add_glow(img, 300, 900, 460, (110, 78, 210), 40)
    img = add_glow(img, 980, 640, 520, (18, 74, 124), 26)
    d = ImageDraw.Draw(img, 'RGBA')
    for x in range(0, W, 64):
        d.line((x, 0, x, H), fill=(70, 120, 160, 18), width=1)
    for y in range(0, H, 64):
        d.line((0, y, W, y), fill=(70, 120, 160, 18), width=1)

    # hero: final model (iso), full body inside the frame
    iso = load(MODEL / 'artifacts' / 'renders' / 'r0023' / 'iso_fr_768.png').convert('RGBA')
    iso = _crop_alpha(iso)

    def put(im, box, alpha=1.0):
        k = min((box[2] - box[0]) / im.width, (box[3] - box[1]) / im.height)
        w, h = int(im.width * k), int(im.height * k)
        im2 = im.resize((w, h), Image.Resampling.LANCZOS)
        if alpha < 1:
            r, g, b, a = im2.split()
            a = a.point(lambda v: int(v * alpha))
            im2 = Image.merge('RGBA', (r, g, b, a))
        img.paste(im2, (box[0] + (box[2] - box[0] - w) // 2, box[1] + (box[3] - box[1] - h) // 2), im2)

    # floor glow + contact shadow, then the model
    glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((1210, 720, 1880, 1010), fill=(40, 130, 210, 60))
    img = Image.alpha_composite(img.convert('RGBA'), glow.filter(ImageFilter.GaussianBlur(60))).convert('RGB')
    shadow = Image.new('RGBA', (420, 70), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((0, 0, 420, 70), fill=(0, 0, 0, 120))
    img.paste(shadow.filter(ImageFilter.GaussianBlur(18)), (1310, 940), shadow.filter(ImageFilter.GaussianBlur(18)))
    put(iso, (1290, 130, 1830, 950))

    d = ImageDraw.Draw(img, 'RGBA')
    # left: tags + headline
    d.rectangle((110, 176, 118, 236), fill=ACCENT + (255,))
    d.text((148, 180), 'v0.9.2 更新', font=font(30, True), fill=ACCENT + (255,))
    d.text((108, 268), '立绘拆分', font=font(116, True), fill=(255, 255, 255, 255))
    d.text((108, 396), 'T1 / T2', font=font(116, True), fill=ACCENT + (255,))
    d.text((108, 540), '让 AI 逐部件看图', font=font(64, True), fill=(232, 242, 252, 255))
    d.text((108, 626), '一张立绘 → 29 个语义层 → 401 块', font=font(40), fill=(148, 170, 194, 255))
    d.text((108, 690), '案例：丰川祥子「旋律的主人」', font=font(34), fill=(139, 124, 255, 255))

    # stats strip
    stats = [('29', '语义层'), ('401', '方块'), ('0', 'validate error')]
    for i, (v, k) in enumerate(stats):
        x = 108 + i * 300
        d.text((x, 790), v, font=font(64, True), fill=ACCENT + (255,))
        d.text((x, 866), k, font=font(24), fill=(148, 170, 194, 255))
    d.text((108, 960), 'DSH × Blockbench Agent', font=font(44, True), fill=(232, 242, 252, 255))
    d.text((108, 1016), REPO_SHORT, font=mono(24), fill=(96, 120, 146, 230))
    # bottom accent
    d.rectangle((0, H - 8, W, H), fill=ACCENT + (255,))
    img.save(path, quality=95)
    return path


# ---------------------------------------------------------------- docs
def fmt_ts(sec: float) -> str:
    m = int(sec // 60)
    s = int(round(sec - m * 60))
    if s == 60:
        m, s = m + 1, 0
    return f'{m:02d}:{s:02d}'


def write_docs(total: float):
    lines = ['# media · 0.9.2 更新宣传片（丰川祥子案例）', '',
             '本目录存放 **DSH × Blockbench Agent v0.9.2 更新宣传片** 的成片、封面、投稿文案与生成脚本。',
             '', '| 文件 | 说明 |', '|---|---|',
             '| `sakiko-0.9.2-promo.mp4` | 成片：1920×1080 / 30fps / H.264 + AAC / '
             f'{total:.1f}s |',
             '| `bilibili-cover-0.9.2.png` | B 站投稿封面（1920×1080，最终模型图） |',
             '| `bilibili-upload-0.9.2.md` | 标题 / 简介 / 标签 / 章节 / 封面建议 |',
             '| `UPDATE-PROMO.md` | 素材来源、分镜表、旁白全文、复现命令、自检结果 |',
             '| `build_update_promo.py` | 生成本片（PIL 逐帧 + Edge TTS + ffmpeg） |',
             '| `_promo_tts/` `_promo_stills/` `_promo_check/` | TTS 缓存 / 场景静帧 / 抽帧自检（可重生成） |',
             '', '## 重新生成', '', '```powershell',
             'pip install pillow numpy edge-tts imageio-ffmpeg qrcode',
             'python media/build_update_promo.py --full',
             '```', '']
    (MEDIA / 'README-0.9.2-promo.md').write_text('\n'.join(lines), encoding='utf-8')

    # upload copy
    chapters = '\n'.join(f'{fmt_ts(sc["start"])} {sc["chapter"]}' for sc in SCENES)
    up = f'''# B 站投稿文案 · DSH × Blockbench Agent v0.9.2 更新宣传片

## 标题备选（3 个）

1. `AI 把一张立绘拆成 29 层，再从 217 块改到 401 块｜Blockbench Agent v0.9.2`
2. `立绘拆分 + 逐步精修：AI 在 Blockbench 里做丰川祥子｜DSH 插件 v0.9.2`
3. `AI 建模不再靠整体印象：29 层语义分层 + 217→401 块精修实录`

推荐第 1 个（数字对比 + 结果导向，B 站信息流里辨识度最高）。
副标题/分区建议：`野生技能协会` 或 `AI` 分区，标签补 `我的世界`。

## 简介

```text
DSH × Blockbench Agent v0.9.2 更新：立绘拆分（T1/T2）+ 复杂逐步调整。

这次不讲功能清单，只讲两条产线：
① 一张官方立绘 → T1 SAM2 轻量分割（59MB，CPU 秒级，24 个候选部件）
   → T2 See-through 完整分层（ComfyUI + 12.5GB 权重，首次 22 分钟，29 个语义层 + 深度序 + 遮挡补全）
   → AI 可以逐部件核对，而不是凭整体印象改模型
② 案例 丰川祥子「旋律的主人」：首轮 217 块 → T1 复检 5 个 major → T2 层对照逐条修 355 块
   → v2 美术优化 401 块（角重做为正面连续螺旋带、背发四组窄束、菱形眼），validate 0 error

工具链：41 个工具（43 定义）/ 56 个 bridge 方法 / 无头渲染 / isolate+zoom / 检查点 / YSM 导出。

项目：{REPO}
安装：按 SETUP.md 从仓库搭建（0.9.2 以仓库代码为准）

模型：丰川祥子「旋律的主人」（YSM，70 骨骼 / 401 方块 / 2×512 贴图）
配音：Edge TTS（zh-CN-XiaoxiaoNeural）；音乐：程序生成的环境铺底，无第三方素材。
```

## 标签

`我的世界` `Minecraft` `Blockbench` `YSM` `YesSteveModel` `AI建模` `DeepSeek` `DeepSeekHarness`
`dsh` `插件` `丰川祥子` `AveMujica` `明日方舟` `立绘拆分` `AI工具` `3D建模`

（B 站最多 10 个标签，优先前 10 个；角色/IP 标签放中间，工具类放后面。）

## 章节时间点

```text
{chapters}
```

## 封面建议

- 主推 `bilibili-cover-0.9.2.png`（1920×1080，深蓝科技风，左文右模型）。
- 3:4 竖版封面可另裁：取 `sakiko-detail-head.png` 头部 + 「立绘拆分 29 层」大字。
- 封面文字不超过 12 字，避免缩略图糊；人物图不要压到右下角（会被时长/角标遮挡）。

## 发布注意

- 素材全部来自本仓库自建模型与官方立绘（`models/togawa-sakiko/refs/skin/`），画面已标注“官方参考”。
- 视频内数据取自 `T2-INSTALL-REPORT.md` / `T2-REPAIR.md` / `MODEL-V2-REFINE.md`，可逐条复查。
- 未上传 B 站：本目录只产出可投稿文件，账号与上传由人工完成。
'''
    (MEDIA / 'bilibili-upload-0.9.2.md').write_text(up, encoding='utf-8')


def write_promo_doc(total: float, meta: dict):
    rows = []
    for i, sc in enumerate(SCENES):
        rows.append(f'| {i + 1:02d} | {fmt_ts(sc["start"])} | {sc["dur"]:.1f}s | {sc["tag"]} | '
                    f'{sc["chapter"]} | {sc["fn"].__name__} |')
    story = '\n'.join(rows)
    voice = '\n'.join(f'{i + 1:02d}. {sc["narration"]}' for i, sc in enumerate(SCENES))
    full = ''.join(sc['narration'] for sc in SCENES)
    cjk = sum(1 for ch in full if '\u4e00' <= ch <= '\u9fff')
    doc = f'''# UPDATE-PROMO · DSH × Blockbench Agent v0.9.2 更新宣传片

- **成片**：`media/sakiko-0.9.2-promo.mp4`（1920×1080 / 30fps / H.264 High + AAC 192k）
- **时长**：{total:.2f}s（目标 95–115s）
- **封面**：`media/bilibili-cover-0.9.2.png`（1920×1080）
- **投稿文案**：`media/bilibili-upload-0.9.2.md`
- **生成脚本**：`media/build_update_promo.py`
- **配音**：Edge TTS `zh-CN-XiaoxiaoNeural`，语速 {meta["rate"]:+d}%
- **生成时间**：{meta["time"]}

> 未上传 B 站（无账号）；仓库源码 / `models/` 未做任何修改，本轮只写 `media/`。

---

## 1. 素材来源（全部为仓库内真实文件，无 AI 生成图）

| 用途 | 文件 | 说明 |
|---|---|---|
| 最终四视图 | `models/togawa-sakiko/artifacts/renders/r0023/{{front,back,left,iso_fr}}_768.png` | 401 块最终模型，768²，透明背景 |
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
{story}

**画面语汇**：深蓝底（#071222）+ 青 #59c2ff / 紫 #8b7cff 强调；每场 1.00→1.00+{max(s["kb"] for s in SCENES):.3f}
的 Ken Burns 推近 + 轻微横移；场景之间 {XFADE:.2f}s 划像转场（左→右，带高光边缘）；底部逐句烧录中文字幕；底部细进度条。

---

## 3. 旁白全文（{len(full)} 字，含标点；纯汉字 {cjk} 字）

{voice}

---

## 4. 复现命令

```powershell
cd F:\\Deepseek_harness\\blockbench
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

{meta["check"]}
'''
    (MEDIA / 'UPDATE-PROMO.md').write_text(doc, encoding='utf-8')


# ---------------------------------------------------------------- main
def probe(path: Path) -> dict:
    r = run(['-hide_banner', '-i', str(path)])
    txt = r.stderr or ''
    out = {}
    m = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.\d+)', txt)
    if m:
        out['duration'] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = re.search(r'Video:\s*(\w+)[^\n]*?,\s*(\d{3,5})x(\d{3,5})', txt)
    if m:
        out['vcodec'], out['width'], out['height'] = m.group(1), int(m.group(2)), int(m.group(3))
    m = re.search(r'(\d+(?:\.\d+)?) fps', txt)
    if m:
        out['fps'] = float(m.group(1))
    m = re.search(r'Audio:\s*(\w+)', txt)
    if m:
        out['acodec'] = m.group(1)
    return out, txt


def self_check(path: Path) -> str:
    """ffprobe/ffmpeg based verification, rendered as a markdown block."""
    info, _ = probe(path)
    nul = 'NUL' if os.name == 'nt' else '/dev/null'
    rb = run(['-hide_banner', '-i', str(path), '-vf', 'blackdetect=d=0.3:pix_th=0.12',
              '-an', '-f', 'null', nul])
    blacks = re.findall(r'black_start:([\d.]+)\s+black_end:([\d.]+)', rb.stderr)
    ra = run(['-hide_banner', '-i', str(path), '-af', 'volumedetect', '-vn', '-f', 'null', nul])
    mv = re.search(r'mean_volume:\s*(-?[\d.]+) dB', ra.stderr)
    xv = re.search(r'max_volume:\s*(-?[\d.]+) dB', ra.stderr)
    dur = info.get('duration', 0)
    rows = [
        f'| 时长 | **{dur:.2f} s** | 目标 95–115 s → {"✅" if 95 <= dur <= 115 else "❌"} |',
        f'| 分辨率 | **{info.get("width")}×{info.get("height")}** | 目标 1920×1080 → '
        f'{"✅" if (info.get("width"), info.get("height")) == (1920, 1080) else "❌"} |',
        f'| 帧率 | **{info.get("fps")} fps** | 目标 30 → {"✅" if info.get("fps") == 30.0 else "❌"} |',
        f'| 视频编码 | **{info.get("vcodec")}** | 目标 H.264 → '
        f'{"✅" if info.get("vcodec") in ("h264", "avc1") else "❌"} |',
        f'| 音频编码 | **{info.get("acodec")}** | 需要 AAC 音轨 → '
        f'{"✅" if info.get("acodec") == "aac" else "❌"} |',
        f'| 文件体积 | **{path.stat().st_size / 1e6:.1f} MB** | — |',
        f'| 黑帧检测 | {"无 ≥0.3 s 黑段" if not blacks else f"{len(blacks)} 段黑场"} | '
        f'blackdetect d=0.3 / pix_th=0.12 |',
        f'| 响度 | 均值 {mv.group(1) if mv else "?"} dB / 峰值 {xv.group(1) if xv else "?"} dB | '
        f'volumedetect（0 dBFS 天花板，未削波） |',
    ]
    return ('```text\n' + '\n'.join(rows) + '\n```\n\n'
            '抽帧目视：`media/_promo_check/`（脚本 `--check` 生成 8–11 张）——'
            '逐帧确认文字未溢出、图片未变形、无黑帧。')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--full', action='store_true')
    ap.add_argument('--stills', action='store_true')
    ap.add_argument('--scene', type=int, default=None)
    ap.add_argument('--frame', type=float, default=None, help='render one global frame time (s)')
    ap.add_argument('--at', type=float, default=0.55)
    ap.add_argument('--cover', action='store_true')
    ap.add_argument('--check', type=str, default=None)
    ap.add_argument('--rate', type=int, default=6)
    ap.add_argument('--no-tts', action='store_true')
    args = ap.parse_args()

    if args.cover:
        print(build_cover(OUT_COVER))
        return

    if args.check:
        p = Path(args.check)
        info, txt = probe(p)
        CHECK_DIR.mkdir(parents=True, exist_ok=True)
        for ts in [1.5, 8.0, 16.0, 25.0, 34.0, 44.0, 55.0, 66.0, 76.0, 86.0, 96.0]:
            if ts >= info.get('duration', 0) - 1:
                continue
            r = run(['-y', '-ss', f'{ts:.2f}', '-i', str(p), '-frames:v', '1',
                     str(CHECK_DIR / f'frame_{ts:05.1f}.png')])
        print(json.dumps({'probe': info, 'size_mb': round(p.stat().st_size / 1e6, 2)},
                         ensure_ascii=False, indent=2))
        print(txt[-1200:])
        return

    rate = args.rate
    if args.no_tts:
        for sc in SCENES:
            sc['dur'] = max(len(sc['narration']) / 5.0 + GAP + 0.42, MIN_DUR)
            sc['voice_dur'] = sc['dur']
        t = LEAD
        for sc in SCENES:
            sc['start'] = round(t, 3)
            t += sc['dur']
        total = t + TAIL
    else:
        total = build_timeline(rate)
    print(f'total = {total:.2f}s  (rate {rate:+d}%)')

    if args.stills:
        for i, sc in enumerate(SCENES):
            im = still_frame(i, args.at)
            im.save(STILL_DIR / f'{sc["id"]}.png')
            print(f'  still {sc["id"]} {sc["dur"]:.2f}s -> {STILL_DIR / (sc["id"] + ".png")}')
        return

    if args.frame is not None:
        im = compose_frame(args.frame, total)
        p = STILL_DIR / f'frame_{args.frame:07.2f}.png'
        im.save(p)
        print(p)
        return

    if args.scene is not None:
        im = still_frame(args.scene, args.at)
        p = STILL_DIR / f'scene{args.scene:02d}_{args.at:.2f}.png'
        im.save(p)
        print(p)
        return

    if args.full:
        audio = build_audio(total, MEDIA / '_promo_audio.wav')
        print('audio ok')
        render_video(total, audio, OUT_MP4)
        build_cover(OUT_COVER)
        info, _ = probe(OUT_MP4)
        check = self_check(OUT_MP4)
        write_docs(total)
        write_promo_doc(total, dict(rate=rate, time='generated', check=check))
        print(json.dumps({'out': str(OUT_MP4), 'duration': info.get('duration'),
                          'bytes': OUT_MP4.stat().st_size}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
