import sys
from PIL import Image
import numpy as np

p = sys.argv[1]
im = Image.open(p).convert("RGBA")
a = np.array(im)
h, w = a.shape[:2]
alpha = a[:, :, 3]
if alpha.min() < 250:
    mask = alpha > 16
else:
    rgb = a[:, :, :3].astype(int)
    bg = np.array([rgb[0, 0], rgb[0, 0], rgb[0, 0]])
    mask = (np.abs(rgb - rgb[0, 0]).max(axis=2) > 12)
# bbox
rows = np.where(mask.any(axis=1))[0]
cols = np.where(mask.any(axis=0))[0]
print("image", w, h, "bbox rows", rows.min(), rows.max(), "cols", cols.min(), cols.max())
print("model bbox center x", (cols.min() + cols.max()) / 2)
# per-row extents
for y in range(rows.min(), rows.max() + 1, max(1, (rows.max() - rows.min()) // 40)):
    xs = np.where(mask[y])[0]
    if len(xs):
        print(f"row {y:5d} x {xs.min():5d}..{xs.max():5d} c {(xs.min()+xs.max())/2:7.1f} n {len(xs):5d}")
# white trim detection (bright, low saturation) in lower half
rgb = a[:, :, :3].astype(int)
mx = rgb.max(axis=2); mn = rgb.min(axis=2)
bright = mask & (mx > 200) & ((mx - mn) < 25)
ys, xs = np.where(bright)
print("bright/white pixels:", len(xs))
if len(xs):
    for lo, hi in [(0, h // 2), (h // 2, h)]:
        sel = (ys >= lo) & (ys < hi)
        if sel.sum() > 50:
            print(f" white band rows {ys[sel].min()}..{ys[sel].max()} x {xs[sel].min()}..{xs[sel].max()} center {(xs[sel].min()+xs[sel].max())/2:.1f}")
