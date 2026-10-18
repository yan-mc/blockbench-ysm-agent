"""Recolor the YSM default texture into DeepSeek whale-girl palette.

Reads the exported default.png, keeps alpha and bottom debug swatches, recolors
red/magenta pixels (hair + coat + eyes) into blue/navy using lightness bands.
"""
from PIL import Image
import colorsys
import sys, os

src = sys.argv[1] if len(sys.argv) > 1 else r'F:\Deepseek_harness\blockbench\projects\deepseek-fish\artifacts\textures\default.png'
out = sys.argv[2] if len(sys.argv) > 2 else r'F:\Deepseek_harness\blockbench\projects\deepseek-fish\reference\recolor-v1.png'

img = Image.open(src).convert('RGBA')
px = img.load()
w, h = img.size

def lerp(a, b, t):
    return int(round(a + (b - a) * t))

# HSL helpers: hue in 0..360, s/l in 0..1
def to_hsl(r, g, b):
    hh, ll, ss = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return hh * 360, ss, ll

def from_hsl(hue, s, l):
    r, g, b = colorsys.hls_to_rgb((hue % 360) / 360, max(0, min(1, l)), max(0, min(1, s)))
    return int(r * 255), int(g * 255), int(b * 255)

for y in range(min(100, h)):
    for x in range(w):
        r, g, b, a = px[x, y]
        if a == 0:
            continue
        hue, sat, light = to_hsl(r, g, b)
        # 只处理红色/品红（发色、红外套、粉眼）；保留橙色皮肤与白色
        red_or_magenta = hue > 300 or hue < 12
        if not red_or_magenta:
            continue
        if sat < 0.06:
            continue
        if light > 0.58:
            # hair / frills / bright pink -> 蓝色渐变：越靠上越深，越靠下发越浅
            t = max(0.0, min(1.0, y / 60.0))
            nr, ng, nb = from_hsl(205, 0.50 + 0.12 * t, 0.30 + 0.58 * t)
        elif light > 0.30:
            # mid pink (hair shading / bow) -> mid blue
            nr, ng, nb = from_hsl(213, 0.55, 0.30 + (light - 0.30) * 0.75)
        else:
            # coat / dark red / eyes -> navy
            nr, ng, nb = from_hsl(217, 0.58, 0.12 + light * 0.55)
        px[x, y] = (nr, ng, nb, a)

img.save(out)
print('saved', out)
