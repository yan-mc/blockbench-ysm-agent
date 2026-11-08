# -*- coding: utf-8 -*-
"""Extract hair colour swatches actually used by existing hair cubes."""
import json, os, sys
from collections import Counter
from PIL import Image

ROOT = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
BBM = os.path.join(ROOT, "checkpoints", "r0006.bbmodel")
TEX = os.path.join(ROOT, "pack", "textures", "default.png")

sys.path.insert(0, os.path.join(ROOT, "tools"))
from v7d_analyze import load, BONE_UUID

d, els, owner, tree = load()
img = Image.open(TEX).convert("RGBA")
W, H = img.size
px = img.load()
print("texture", W, H)

cnt = Counter()
pos = {}
for u, b in owner.items():
    if b not in ("Hair", "HairBack", "hl_side", "front_h1", "corner_h1", "TwinTail_L", "TwinTail_R", "Ribbon", "HairBow_R"):
        continue
    e = els[u]
    f = e["faces"]
    n = f.get("north", {}).get("uv")
    if not n:
        continue
    x = int((n[0] + n[2]) / 2)
    y = int((n[1] + n[3]) / 2)
    x = max(0, min(W - 1, x)); y = max(0, min(H - 1, y))
    c = px[x, y]
    key = "#%02x%02x%02x" % c[:3] if c[3] > 0 else "#transparent"
    cnt[key] += 1
    pos.setdefault(key, []).append((x, y, b))

for k, v in cnt.most_common(20):
    lum = 0
    if k != "#transparent":
        r = int(k[1:3], 16); g = int(k[3:5], 16); b2 = int(k[5:7], 16)
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b2
    ex = pos[k][:3]
    print("%-14s n=%3d lum=%5.1f  e.g. %s" % (k, v, lum, ex))
