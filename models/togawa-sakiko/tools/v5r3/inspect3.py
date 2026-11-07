# -*- coding: utf-8 -*-
"""Find free 16x16 cells and global color usage (to know what is safe to repaint)."""
import json, os
import numpy as np
from collections import Counter
from PIL import Image

PACK = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack"
d = json.load(open(os.path.join(PACK, "models", "main.json"), encoding="utf-8"))
g = d["minecraft:geometry"][0]
TEX = os.path.join(PACK, "textures", "default.png")
img = Image.open(TEX).convert("RGBA")
A = np.array(img)
alpha = A[:, :, 3]
print("size", img.size, "opaque%", round((alpha > 8).mean() * 100, 2))

# UV usage mask
S = 512
mask = np.zeros((S, S), dtype=bool)
for b in g["bones"]:
    for c in b.get("cubes", []):
        uv = c.get("uv")
        rects = []
        if isinstance(uv, dict):
            for k, v in uv.items():
                if isinstance(v, dict) and "uv" in v:
                    u, w = v["uv"]
                    su, sw = v.get("uv_size", [1, 1])
                elif isinstance(v, (list, tuple)):
                    u, w = v
                    su, sw = 1, 1
                else:
                    continue
                rects.append((u, w, u + su, w + sw))
        else:
            u, w = (uv or [0, 0])[:2]
            s = c["size"]
            rects.append((u, w, u + 2 * (s[0] + s[2]), w + s[1] + s[2]))
        for x0, y0, x1, y1 in rects:
            x0, y0 = max(0, int(np.floor(x0))), max(0, int(np.floor(y0)))
            x1, y1 = min(S, int(np.ceil(x1))), min(S, int(np.ceil(y1)))
            if x1 > x0 and y1 > y0:
                mask[y0:y1, x0:x1] = True

free = []
for cy in range(224, S - 15, 16):
    for cx in range(0, S - 15, 16):
        if not mask[cy:cy + 16, cx:cx + 16].any() and not (alpha[cy:cy + 16, cx:cx + 16] > 8).any():
            free.append((cx, cy))
print("free cells:", len(free))
print([f for f in free])

# color usage per bone
def col(c):
    uv = c.get("uv")
    if isinstance(uv, dict):
        v = uv.get("north") or list(uv.values())[0]
        u, w = (v.get("uv", [0, 0]) if isinstance(v, dict) else v)
    else:
        u, w = (uv or [0, 0])[:2]
    r, gg, b, a = A[int(w), int(u)]
    return "#%02x%02x%02x" % (r, gg, b), int(a)

allc = Counter()
by_color = {}
B = {b["name"]: b for b in g["bones"]}
for bn, b in B.items():
    for c in b.get("cubes", []):
        k, a = col(c)
        allc[k] += 1
        by_color.setdefault(k, Counter())[bn] += 1
print("\ncolors used:", len(allc))
for k, n in allc.most_common():
    print(" %s %4d  %s" % (k, n, dict(by_color[k].most_common(6))))
