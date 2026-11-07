# -*- coding: utf-8 -*-
import json, os
from collections import Counter
from PIL import Image

PACK = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack"
d = json.load(open(os.path.join(PACK, "models", "main.json"), encoding="utf-8"))
g = d["minecraft:geometry"][0]
B = {b["name"]: b for b in g["bones"]}
img = Image.open(os.path.join(PACK, "textures", "default.png")).convert("RGBA")
px = img.load()


def col(c):
    uv = c.get("uv")
    if isinstance(uv, dict):
        v = uv.get("north") or list(uv.values())[0]
        u, w = (v.get("uv", [0, 0]) if isinstance(v, dict) else v)
    else:
        u, w = (uv or [0, 0])[:2]
    r, gg, b, a = px[int(u), int(w)]
    return "#%02x%02x%02x" % (r, gg, b)


print("named cubes containing ear/ring/gem:")
for b in g["bones"]:
    for c in b.get("cubes", []):
        n = str(c.get("name", ""))
        if any(k in n.lower() for k in ("ear", "ring", "gem", "drop")):
            o, s = c["origin"], c["size"]
            print(" ", b["name"], n, [round(-(o[0] + s[0] / 2), 2), round(o[1] + s[1] / 2, 2), round(o[2] + s[2] / 2, 2)], [round(v, 2) for v in s], col(c))

for bn in ("HairBack", "Hair", "front_h1", "hl_side", "TwinTail_L"):
    h = Counter()
    ys = []
    for c in B[bn].get("cubes", []):
        h[col(c)] += 1
        ys.append(c["origin"][1] + c["size"][1] / 2)
    print("\n%s n=%d y=[%.2f..%.2f]" % (bn, len(B[bn].get("cubes", [])), min(ys), max(ys)))
    print("  colors:", h.most_common())

print("\nHead cubes:")
for c in B["Head"].get("cubes", []):
    o, s = c["origin"], c["size"]
    print("  ", [round(-(o[0] + s[0] / 2), 2), round(o[1] + s[1] / 2, 2), round(o[2] + s[2] / 2, 2)], [round(v, 2) for v in s], c.get("name"), col(c))

print("\nCape cubes:")
for bn in ("Cape", "CapeLow"):
    for c in B[bn].get("cubes", []):
        o, s = c["origin"], c["size"]
        print("  ", bn, [round(-(o[0] + s[0] / 2), 2), round(o[1] + s[1] / 2, 2), round(o[2] + s[2] / 2, 2)], [round(v, 2) for v in s], [round(v, 1) for v in c.get("rotation", [0, 0, 0])], c.get("name"), col(c))

print("\nFoot (LeftFoot) cubes:")
for c in B["LeftFoot"].get("cubes", []):
    o, s = c["origin"], c["size"]
    print("  ", [round(-(o[0] + s[0] / 2), 2), round(o[1] + s[1] / 2, 2), round(o[2] + s[2] / 2, 2)], [round(v, 2) for v in s], c.get("name"), col(c))
