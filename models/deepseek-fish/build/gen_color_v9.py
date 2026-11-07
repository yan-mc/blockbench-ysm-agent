"""v9 colour pass: lift the near-black dress to a 4+ level ramp, brighten the
blue-violet petticoat, keep the silver trim bright.

Operates on the saved default.png and writes default_v9.png.
"""
from PIL import Image
import numpy as np

SRC = r"F:\Deepseek_harness\blockbench\models\deepseek-fish\sakiko-melodia\textures\default.png"
DST = r"F:\Deepseek_harness\blockbench\models\deepseek-fish\build\out\default_v9.png"

im = Image.open(SRC).convert("RGBA")
a = np.array(im).astype(np.float32)
rgb = a[:, :, :3]
al = a[:, :, 3]

mx = rgb.max(axis=2)
mn = rgb.min(axis=2)
L = mx                      # crude luminance

# masks
dark = (al > 8) & (L < 0x50)
mid = (al > 8) & (L >= 0x50) & (L < 0xA0)

# --- 1. dark ramp: compress 0..0x4f into 0x18..0x4e (keeps relative order)
target = 0x18 + (L / 0x50) * (0x4e - 0x18)
k = np.where(L > 1, target / np.maximum(L, 1), 2.2)
new = rgb * k[:, :, None]
# blue bias so the blacks read as cold cloth, not neutral grey
new[:, :, 2] *= 1.10
new[:, :, 0] *= 0.96
rgb = np.where(dark[:, :, None], new, rgb)

# --- 2. mid tones: gentle +10% so the fold shading survives
rgb = np.where(mid[:, :, None], rgb * 1.10, rgb)

# --- 3. blue-violet petticoat: brighten and push saturation a little
mx2 = rgb.max(axis=2)
mn2 = rgb.min(axis=2)
blueish = (al > 8) & (rgb[:, :, 2] > rgb[:, :, 0] + 8) & (mx2 < 0xB0) & (mx2 > 0x30)
mean = rgb.mean(axis=2, keepdims=True)
sat = np.where(mean > 1, (rgb - mean) / np.maximum(mean, 1), 0)
boost = rgb * 1.16 + sat * rgb * 0.16
rgb = np.where(blueish[:, :, None], boost, rgb)

# --- 4. keep silver trim crisp: brighten pixels already bright
bright = (al > 8) & (mx2 > 0xB8)
rgb = np.where(bright[:, :, None], np.clip(rgb * 1.04, 0, 255), rgb)

out = np.dstack([np.clip(rgb, 0, 255), al]).astype(np.uint8)
Image.fromarray(out, "RGBA").save(DST)
print("saved", DST)

# quick stats
o = np.array(Image.open(DST).convert("RGBA"))
op = o[o[:, :, 3] > 8][:, :3]
Lv = op.max(axis=1)
for lo, hi in [(0, 0x1a), (0x1a, 0x2a), (0x1a, 0x30), (0x30, 0x45), (0x45, 0x60), (0x60, 0x90), (0x90, 0xB0), (0xB0, 0xD0), (0xD0, 0x100)]:
    n = int(((Lv >= lo) & (Lv < hi)).sum())
    print(f"  L {lo:02x}-{hi:02x}: {n:7d}  {n/len(Lv)*100:5.1f}%")
