from PIL import Image
import numpy as np
import os

root = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
os.makedirs(root + r"\artifacts\v5\r6", exist_ok=True)

# crops
im = Image.open(root + r"\artifacts\refstudy\t3-panel5-back.png")
im.crop((30, 400, 510, 800)).resize((960, 800)).save(root + r"\artifacts\v5\r6\t3back_lower.png")
im2 = Image.open(root + r"\artifacts\refstudy\t3-panel5-side.png")
im2.crop((0, 380, 395, 820)).resize((790, 880)).save(root + r"\artifacts\v5\r6\t3side_lower.png")


def profile(path, label, x0f=0.28, x1f=0.72, scales=1.0):
    a = np.array(Image.open(path).convert("RGB")).astype(int)
    H, W, _ = a.shape
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    bg = (r > 228) & (g > 228) & (b > 228)
    fg = ~bg
    rows = np.where(fg.any(axis=1))[0]
    cols = np.where(fg.any(axis=0))[0]
    print(f"\n==== {label} {W}x{H} fg x[{cols.min()},{cols.max()}] y[{rows.min()},{rows.max()}]")
    # hair: bluish
    hair = fg & (b > 60) & (b - r > 10) & (b - g > -5)
    # black cloth: dark, low chroma
    black = fg & (r < 80) & (g < 80) & (b < 95)
    x0, x1 = int(W * x0f), int(W * x1f)
    print(" y | hairC | blackC | hairX | blackX")
    y0, y1 = rows.min(), rows.max()
    for frac in [0.30, 0.35, 0.40, 0.45, 0.50, 0.53, 0.56, 0.59, 0.62, 0.65, 0.68, 0.71, 0.74]:
        y = int(y0 + frac * (y1 - y0))
        hrow = np.where(hair[y, x0:x1])[0]
        brow = np.where(black[y, x0:x1])[0]
        hs = f"{hrow.min()+x0}-{hrow.max()+x0}" if len(hrow) else "-"
        bs = f"{brow.min()+x0}-{brow.max()+x0}" if len(brow) else "-"
        print(f" {frac:.2f} y={y:4d} hair={len(hrow):4d} black={len(brow):4d}  hX={hs:12s} bX={bs}")
    # hair bottom in center band
    center = hair[:, int(W*0.35):int(W*0.65)]
    cy = np.where(center.any(axis=1))[0]
    print(" hair rows center band:", cy.min(), cy.max())
    # black skirt rows center band
    cb = black[:, int(W*0.35):int(W*0.65)]
    by = np.where(cb.sum(axis=1) > 12)[0]
    print(" black(>12px) rows center band:", by.min(), by.max())


profile(root + r"\artifacts\refstudy\t3-panel5-back.png", "T3 back")
profile(root + r"\artifacts\refstudy\t3-panel5-side.png", "T3 side", 0.2, 0.9)
profile(root + r"\artifacts\v5\r5\v5-r5-back-2400.png", "r5 back")
profile(root + r"\artifacts\v5\r5\v5-r5-left-2400.png", "r5 left", 0.2, 0.9)
