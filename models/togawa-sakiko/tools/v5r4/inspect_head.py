# -*- coding: utf-8 -*-
"""Read-only inspection of the head region + texture cell occupancy."""
import json, os
from PIL import Image

PACK = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack"
MAIN = os.path.join(PACK, "models", "main.json")
TEX = os.path.join(PACK, "textures", "default.png")

d = json.load(open(MAIN, encoding="utf-8"))
geo = d["minecraft:geometry"][0]
B = {b["name"]: b for b in geo["bones"]}
img = Image.open(TEX).convert("RGBA")
px = img.load()
W, H = img.size


def uv0(c):
    uv = c.get("uv")
    if isinstance(uv, dict):
        v = uv.get("north") or list(uv.values())[0]
        return (v.get("uv", [0, 0]) if isinstance(v, dict) else v)
    return (uv or [0, 0])[:2]


def col(c):
    u, v = uv0(c)
    return px[int(u), int(v)]


def center(c):
    o, s = c["origin"], c["size"]
    return (-(o[0] + s[0] / 2.0), o[1] + s[1] / 2.0, o[2] + s[2] / 2.0)


print("== head-region cubes (cy 35.5..44, |cx|<4.2) ==")
rows = []
for bn in ("Head", "Hair", "front_h1", "corner_h1", "hl_side", "Ribbon",
           "HairBow_R", "Horn_L", "Horn_R", "FLongHair"):
    for i, c in enumerate(B[bn].get("cubes", [])):
        cx, cy, cz = center(c)
        if 35.0 < cy < 44.5 and abs(cx) < 4.6:
            u, v = uv0(c)
            rows.append((cy, bn, i, c.get("name"), cx, cy, cz, c["size"],
                         c.get("rotation"), (u, v), col(c)[:3]))
rows.sort(key=lambda r: (-r[0], r[4]))
for r in rows:
    cy, bn, i, name, cx, y, cz, s, rot, uv, rgb = r
    print("%-10s #%-3d %-14s c=(%6.2f,%6.2f,%6.2f) sz=(%5.2f,%5.2f,%5.2f) rot=%s uv=%s rgb=%s"
          % (bn, i, name, cx, y, cz, s[0], s[1], s[2],
             [round(x, 1) for x in (rot or [0, 0, 0])], uv, rgb))

print("\n== Head bone cubes all ==")
for i, c in enumerate(B["Head"]["cubes"]):
    cx, cy, cz = center(c)
    print("#%-3d %-14s c=(%6.2f,%6.2f,%6.2f) sz=(%5.2f,%5.2f,%5.2f) rot=%s rgb=%s uv=%s"
          % (i, c.get("name"), cx, cy, cz, *c["size"],
             [round(x, 1) for x in (c.get("rotation") or [0, 0, 0])], col(c)[:3], uv0(c)))

print("\n== 16px cell occupancy (default.png %dx%d) ==" % (W, H))
occ = {}
for bn, b in B.items():
    for c in b.get("cubes", []):
        uv = c.get("uv")
        faces = uv.values() if isinstance(uv, dict) else [{"uv": uv}]
        for f in faces:
            if isinstance(f, dict) and f.get("uv"):
                u, v = f["uv"][:2]
                occ[(int(u) // 16 * 16, int(v) // 16 * 16)] = 1
cells = []
for cy_ in range(0, H, 16):
    line = ""
    for cx_ in range(0, W, 16):
        line += "#" if (cx_, cy_) in occ else "."
    cells.append("%3d %s" % (cy_, line))
print("     " + "".join(str((x // 16) % 10) for x in range(0, W, 16)))
for l in cells:
    if l.split(" ", 1)[1].strip(".") or True:
        print(l)
