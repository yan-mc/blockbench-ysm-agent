# -*- coding: utf-8 -*-
"""Inspect v5 model in bbmodel space, with swatch colors sampled from default.png."""
import json, os, sys
from collections import Counter

PACK = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack"
MAIN = os.path.join(PACK, "models", "main.json")
TEX = os.path.join(PACK, "textures", "default.png")

d = json.load(open(MAIN, encoding="utf-8"))
g = d["minecraft:geometry"][0]
B = {b["name"]: b for b in g["bones"]}

from PIL import Image
img = Image.open(TEX).convert("RGBA")
px = img.load()
W, H = img.size


def sample(c):
    uv = c.get("uv")
    try:
        if isinstance(uv, dict):
            v = uv.get("north") or list(uv.values())[0]
            if isinstance(v, dict):
                u, w = v.get("uv", [0, 0])
            else:
                u, w = v
        else:
            u, w = (uv or [0, 0])[:2]
        u, v = int(u), int(w)
        u = max(0, min(W - 1, u)); v = max(0, min(H - 1, v))
        r, gg, b, a = px[u, v]
        return "#%02x%02x%02x" % (r, gg, b) + ("" if a == 255 else " a%d" % a)
    except Exception as e:
        return "?"


def info(c):
    o, s = c["origin"], c["size"]
    cx = -(o[0] + s[0] / 2.0)
    cy = o[1] + s[1] / 2.0
    cz = o[2] + s[2] / 2.0
    return cx, cy, cz, s


def bone_report(names):
    for n in names:
        b = B.get(n)
        if not b:
            print("MISSING", n); continue
        cs = b.get("cubes", [])
        ys = [info(c)[1] for c in cs]
        print("\n== %s parent=%s cubes=%d y=[%.2f..%.2f]" % (
            n, b.get("parent"), len(cs), min(ys) if ys else 0, max(ys) if ys else 0))
        for c in cs:
            cx, cy, cz, s = info(c)
            print("  c=(%7.2f,%6.2f,%6.2f) s=(%5.2f,%5.2f,%5.2f) rot=%s %s" % (
                cx, cy, cz, s[0], s[1], s[2],
                [round(v, 1) for v in c.get("rotation", [0, 0, 0])], sample(c)))


if __name__ == "__main__":
    targets = sys.argv[1:] or ["Skirt", "FrontSkirt", "BackSkirt", "LeftSkirt", "RightSkirt", "Cape", "CapeLow"]
    bone_report(targets)
    print("\n--- totals")
    tot = 0
    for b in g["bones"]:
        tot += len(b.get("cubes", []))
    print("bones", len(g["bones"]), "cubes", tot)
