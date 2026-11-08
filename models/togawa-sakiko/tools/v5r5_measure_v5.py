from PIL import Image
import numpy as np
from collections import Counter

p = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\renders\r0012\back_800.png"
im = Image.open(p).convert("RGB")
a = np.array(im).astype(int)
print("corner", a[2, 2], a[997, 2], a[2, 797])
bgc = a[2, 2]
dist = np.abs(a - bgc).sum(axis=2)
fg = dist > 24
rows = np.where(fg.any(axis=1))[0]
cols = np.where(fg.any(axis=0))[0]
print("fg bbox x", cols.min(), cols.max(), "y", rows.min(), rows.max())
H0, H1 = rows.min(), rows.max()
print("pct  y  width  xmin xmax")
for pct in range(15, 80, 5):
    y = int(H0 + pct / 100 * (H1 - H0))
    xs = np.where(fg[y])[0]
    if len(xs) < 2:
        print(f"{pct:3d}% {y:4d}  none")
        continue
    # main run only (largest)
    print(f"{pct:3d}% {y:4d}  {xs.max()-xs.min():4d}  {xs.min():4d} {xs.max():4d}")

# hair vs black at some rows
r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
hair = fg & (b > 120) & (b - r > 8) & (g > 90) & (b > g + 15)
blk = fg & (r < 80) & (g < 80) & (b < 90)
print("\nhair px", hair.sum(), "black px", blk.sum())
for pct in (30, 35, 40, 45, 50, 55, 60, 65, 70):
    y = int(H0 + pct / 100 * (H1 - H0))
    hx = np.where(hair[y])[0]
    bx = np.where(blk[y])[0]
    out = f"{pct:3d}% y={y} "
    out += f"hair[{hx.min()},{hx.max()}]w={hx.max()-hx.min()} " if len(hx) > 1 else "hair[] "
    out += f"black[{bx.min()},{bx.max()}]w={bx.max()-bx.min()}" if len(bx) > 1 else "black[]"
    print(out)
