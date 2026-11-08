"""Silhouette width vs y for HairBack / skirt / whole model, plus T3 hair profile."""
import json
from PIL import Image
import numpy as np

P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
d = json.load(open(P, encoding="utf-8"))
bones = d["minecraft:geometry"][0]["bones"]

def sil(bone_names, y0=0, y1=44, step=0.5):
    cubes = []
    for b in bones:
        if b["name"] in bone_names:
            cubes += b.get("cubes") or []
    out = {}
    y = y0
    while y <= y1:
        xs = []
        for c in cubes:
            o = c["origin"]; s = c["size"]
            if o[1] - 0.001 <= y <= o[1] + s[1] + 0.001:
                xs.append((o[0], o[0] + s[0]))
        out[y] = (min(a for a, _ in xs), max(b for _, b in xs)) if xs else None
        y += step
    return out

for label, names in (("HairBack", ("HairBack",)), ("Skirt", ("Skirt", "RightSkirt", "LeftSkirt", "FrontSkirt", "BackSkirt"))):
    s = sil(names)
    print("\n==", label)
    for y in sorted(s, reverse=True):
        v = s[y]
        if v:
            print(f"y={y:5.1f} x=[{v[0]:6.2f},{v[1]:6.2f}] w={v[1]-v[0]:5.2f}")

# T3 back profile at more heights
root = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\refstudy"
im = Image.open(root + r"\t3-panel5-back.png").convert("RGB")
a = np.array(im).astype(int)
H, W, _ = a.shape
bg = (a[:, :, 0] > 230) & (a[:, :, 1] > 230) & (a[:, :, 2] > 230)
fg = ~bg
rows = np.where(fg.any(axis=1))[0]
r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
hair = fg & (b > 140) & (b - r > 12) & (g > 100)
print("\n== T3 back hair width by pct of figure height ==")
print("figure rows", rows.min(), rows.max(), "height", rows.max() - rows.min())
for pct in range(15, 56, 2):
    y = int(rows.min() + pct / 100 * (rows.max() - rows.min()))
    hx = np.where(hair[y])[0]
    if len(hx) > 1:
        print(f"pct={pct:3d}% y={y} hair x=[{hx.min()},{hx.max()}] w={hx.max()-hx.min()}")
    else:
        print(f"pct={pct:3d}% y={y} none")
