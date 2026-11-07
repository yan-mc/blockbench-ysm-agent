"""Crop the head region out of a full-body render for close inspection."""
from PIL import Image
import numpy as np, sys, os

src = sys.argv[1]
dst = sys.argv[2]
top_frac = float(sys.argv[3]) if len(sys.argv) > 3 else 0.16
pad = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0

im = Image.open(src).convert("RGBA")
a = np.array(im)[:, :, 3]
ys, xs = np.nonzero(a > 8)
y0, y1 = ys.min(), ys.max()
x0, x1 = xs.min(), xs.max()
# head = top slice of the opaque bbox
hy1 = y0 + int((y1 - y0) * top_frac)
w = x1 - x0
cx = (x0 + x1) // 2
half = int(w * 0.33 * pad)
cx0, cx1 = max(0, cx - half), min(im.width, cx + half)
crop = im.crop((cx0, max(0, y0 - 10), cx1, hy1))
scale = max(1, int(900 / crop.width))
crop = crop.resize((crop.width * scale, crop.height * scale), Image.NEAREST)
crop.save(dst)
print("saved", dst, crop.size)
