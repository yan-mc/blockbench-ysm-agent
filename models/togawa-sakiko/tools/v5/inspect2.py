# -*- coding: utf-8 -*-
import json
import numpy as np
from PIL import Image

P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack"
d = json.load(open(P + r"\models\main.json", encoding="utf-8"))
g = d["minecraft:geometry"][0]
B = {b["name"]: b for b in g["bones"]}

for name in ["Ribbon", "Collar", "HairBack", "hl_side", "TwinTail_L", "corner_h1", "Hair", "Cape", "CapeLow"]:
    print("=== " + name, len(B[name].get("cubes", [])))
    for c in B[name].get("cubes", []):
        print("  ", [round(v, 2) for v in c["origin"]], [round(v, 2) for v in c["size"]],
              c.get("rotation"), (c.get("name") or "")[:14],
              ("box" if isinstance(c.get("uv"), list) else "face"))

# ---- texture usage
im = Image.open(P + r"\textures\default.png").convert("RGBA")
a = np.array(im)
print("\ntexture", im.size, "opaque px", int((a[:, :, 3] > 0).sum()))
occ = (a[:, :, 3] > 0)
# find fully free 16x16 cells
free = []
for cy in range(0, 512, 16):
    for cx in range(0, 512, 16):
        if not occ[cy:cy + 16, cx:cx + 16].any():
            free.append((cx, cy))
print("free 16x16 cells:", len(free))
rows = {}
for cx, cy in free:
    rows.setdefault(cy, []).append(cx)
for cy in sorted(rows):
    print("  row y=%d free x: %s" % (cy, sorted(rows[cy])))
