from PIL import Image
import numpy as np
import os

root = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
os.makedirs(root + r"\artifacts\v5\r6", exist_ok=True)

im = Image.open(root + r"\artifacts\refstudy\t3-panel5-back.png")
im.crop((30, 420, 510, 800)).resize((960, 760)).save(root + r"\artifacts\v5\r6\t3back_lower.png")
im2 = Image.open(root + r"\artifacts\refstudy\t3-panel5-side.png")
im2.crop((30, 400, 395, 800)).resize((730, 800)).save(root + r"\artifacts\v5\r6\t3side_lower.png")


def load(path):
    im = Image.open(path)
    a = np.array(im.convert("RGBA")).astype(int)
    if a[:, :, 3].min() < 250:          # transparent render
        fg = a[:, :, 3] > 20
        rgb = a[:, :, :3]
    else:
        rgb = a[:, :, :3]
        fg = ~((rgb[:, :, 0] > 228) & (rgb[:, :, 1] > 228) & (rgb[:, :, 2] > 228))
    return rgb, fg


def prof(path, label, band=(0.30, 0.70)):
    rgb, fg = load(path)
    H, W, _ = rgb.shape
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    lum = 0.3 * r + 0.59 * g + 0.11 * b
    mx = rgb.max(axis=2); mn = rgb.min(axis=2)
    hair = fg & (b - r > 10) & (b > 60)
    black = fg & (lum < 95) & ((mx - mn) < 42)
    rows = np.where(fg.any(axis=1))[0]
    cols = np.where(fg.any(axis=0))[0]
    y0, y1 = rows.min(), rows.max()
    hgt = y1 - y0
    print(f"\n==== {label} {W}x{H} fg x[{cols.min()},{cols.max()}] y[{y0},{y1}] h={hgt}")
    print(" frac   y    hairW  hairX        blackW blackX")
    for frac in [0.42, 0.46, 0.50, 0.54, 0.58, 0.62, 0.66, 0.70, 0.74]:
        y = int(y0 + frac * hgt)
        hx = np.where(hair[y])[0]
        bx = np.where(black[y])[0]
        hs = f"{hx.min()}-{hx.max()}" if len(hx) else "-"
        bs = f"{bx.min()}-{bx.max()}" if len(bx) else "-"
        print(f" {frac:.2f} {y:5d}  {len(hx):5d}  {hs:12s} {len(bx):5d}  {bs}")
    # widths at specific model heights need scale; just print fractions too
    for name, mask in (("hair", hair), ("black", black)):
        ys = np.where(mask.any(axis=1))[0]
        print(f" {name} rows {ys.min()}..{ys.max()}")


prof(root + r"\artifacts\refstudy\t3-panel5-back.png", "T3 back")
prof(root + r"\artifacts\v5\r5\v5-r5-back-2400.png", "r5 back")
prof(root + r"\artifacts\refstudy\t3-panel5-side.png", "T3 side")
prof(root + r"\artifacts\v5\r5\v5-r5-left-2400.png", "r5 left")
