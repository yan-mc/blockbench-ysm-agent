"""Measure T3 panel5 back/side: hair width vs body, and hem colors."""
from PIL import Image
import numpy as np

root = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\refstudy"
for name in ("t3-panel5-back.png", "t3-panel5-side.png", "t3-panel5-front.png"):
    im = Image.open(root + "\\" + name).convert("RGB")
    a = np.array(im).astype(int)
    H, W, _ = a.shape
    print("\n====", name, W, "x", H)
    # background likely white-ish; find non-bg columns overall
    bg = (a[:, :, 0] > 230) & (a[:, :, 1] > 230) & (a[:, :, 2] > 230)
    fg = ~bg
    cols = np.where(fg.any(axis=0))[0]
    rows = np.where(fg.any(axis=1))[0]
    print("fg bbox x", cols.min(), cols.max(), " y", rows.min(), rows.max())
    # hair mask: bluish light
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    hair = fg & (b > 140) & (b - r > 12) & (g > 100)
    # black skirt mask
    black = fg & (r < 70) & (g < 70) & (b < 85) & (np.abs(r - b) < 40)
    print("hair px", hair.sum(), "black px", black.sum())
    for frac in (0.28, 0.33, 0.38, 0.43, 0.48, 0.53, 0.58, 0.63, 0.68, 0.73, 0.78):
        y = int(rows.min() + frac * (rows.max() - rows.min()))
        hx = np.where(hair[y])[0]
        bx = np.where(black[y])[0]
        s = f"y={y} ({frac:.0%}) "
        s += f"hair[{hx.min()},{hx.max()}] w={hx.max()-hx.min() if len(hx)>1 else 0} " if len(hx) else "hair[] "
        s += f"black[{bx.min()},{bx.max()}] w={bx.max()-bx.min() if len(bx)>1 else 0}" if len(bx) else "black[]"
        print(s)
