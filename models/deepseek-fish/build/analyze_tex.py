"""Analyze default.png: palette, alpha occupancy, free rectangles, and a face-region dump."""
from PIL import Image
import numpy as np
from collections import Counter

p = r"F:\Deepseek_harness\blockbench\models\deepseek-fish\sakiko-melodia\textures\default.png"
im = Image.open(p).convert("RGBA")
a = np.array(im)
print("size", im.size, "mode", im.mode)
alpha = a[:, :, 3]
print("opaque px", int((alpha > 8).sum()), "ratio", round(float((alpha > 8).mean()), 4))

# opaque bbox
ys, xs = np.nonzero(alpha > 8)
print("opaque bbox x", xs.min(), xs.max(), "y", ys.min(), ys.max())

# palette of opaque pixels
op = a[alpha > 8]
cols = Counter(map(tuple, op[:, :4].tolist()))
print("distinct rgba colors:", len(cols))
print("top 28 colors:")
for c, n in cols.most_common(28):
    print("  #%02x%02x%02x a=%3d  n=%6d" % (c[0], c[1], c[2], c[3], n))

# free rect search: transparent 16x16 grid
free = (alpha <= 8)
cell = 16
gh, gw = 1024 // cell, 1024 // cell
occ = free[: gh * cell, : gw * cell].reshape(gh, cell, gw, cell).all(axis=(1, 3))
print("\nfree 16px grid (rows=y, cols=x), '.'=free:")
for r in range(gh):
    print("%4d " % (r * cell) + "".join("." if occ[r, c] else "#" for c in range(gw)))
