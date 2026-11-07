# -*- coding: utf-8 -*-
import json, os, sys
from PIL import Image

PACK = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack"
d = json.load(open(os.path.join(PACK, "models", "main.json"), encoding="utf-8"))
g = d["minecraft:geometry"][0]
B = {b["name"]: b for b in g["bones"]}
img = Image.open(os.path.join(PACK, "textures", "default.png")).convert("RGBA")
px = img.load()


def uv0(c):
    uv = c.get("uv")
    if isinstance(uv, dict):
        v = uv.get("north") or list(uv.values())[0]
        return (v.get("uv", [0, 0]) if isinstance(v, dict) else v)
    return (uv or [0, 0])[:2]


def bb(c):
    o, s = c["origin"], c["size"]
    return (-(o[0] + s[0] / 2.0), o[1] + s[1] / 2.0, o[2] + s[2] / 2.0, s)


def show(bn):
    print("\n== %s (%d)" % (bn, len(B[bn].get("cubes", []))))
    for i, c in enumerate(B[bn].get("cubes", [])):
        cx, cy, cz, s = bb(c)
        u, v = uv0(c)
        r, gg, b, a = px[int(u), int(v)]
        print(" %2d c=(%7.2f,%6.2f,%6.2f) s=(%5.2f,%5.2f,%5.2f) rot=%s uv=(%d,%d) %s a%d" % (
            i, cx, cy, cz, s[0], s[1], s[2],
            [round(x, 1) for x in c.get("rotation", [0, 0, 0])], u, v,
            "#%02x%02x%02x" % (r, gg, b), a))


for a in sys.argv[1:]:
    show(a)
