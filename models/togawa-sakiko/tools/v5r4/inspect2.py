# -*- coding: utf-8 -*-
"""Read-only structural probes for r4 targets."""
import json, os
from PIL import Image

PACK = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack"
MAIN = os.path.join(PACK, "models", "main.json")
d = json.load(open(MAIN, encoding="utf-8"))
geo = d["minecraft:geometry"][0]
B = {b["name"]: b for b in geo["bones"]}
img = Image.open(os.path.join(PACK, "textures", "default.png")).convert("RGBA")
px = img.load()


def uv0(c):
    uv = c.get("uv")
    if isinstance(uv, dict):
        v = uv.get("north") or list(uv.values())[0]
        return (v.get("uv", [0, 0]) if isinstance(v, dict) else v)
    return (uv or [0, 0])[:2]


def col(c):
    u, v = uv0(c)
    return px[int(u), int(v)][:3]


def center(c):
    o, s = c["origin"], c["size"]
    return (-(o[0] + s[0] / 2.0), o[1] + s[1] / 2.0, o[2] + s[2] / 2.0)


print("== Head cubes ==")
for i, c in enumerate(B["Head"]["cubes"]):
    cx, cy, cz = center(c)
    print("#%-2d %-14s c=(%6.2f,%6.2f,%6.2f) sz=(%5.2f,%5.2f,%5.2f) rot=%s rgb=%s"
          % (i, c.get("name"), cx, cy, cz, *c["size"],
             [round(x, 1) for x in (c.get("rotation") or [0, 0, 0])], col(c)))

print("\n== HairBack z-profile by y band ==")
bands = {}
for c in B["HairBack"]["cubes"]:
    cx, cy, cz = center(c)
    k = round(cy * 2) / 2.0
    bands.setdefault(k, []).append((cz, c["size"][2], cx, c["size"][0], c["size"][1]))
for k in sorted(bands):
    v = bands[k]
    zmax = max(x[0] + x[1] / 2 for x in v)
    print("y=%5.1f n=%-3d z_center_max=%5.2f  x=[%5.2f,%5.2f]" %
          (k, len(v), zmax, min(x[2] for x in v), max(x[2] for x in v)))

print("\n== HairBack cubes y>29 sorted by y desc (first 40) ==")
rows = sorted(B["HairBack"]["cubes"], key=lambda c: -center(c)[1])
for c in rows[:40]:
    cx, cy, cz = center(c)
    print(" c=(%6.2f,%6.2f,%6.2f) sz=(%5.2f,%5.2f,%5.2f) yaw=%s rgb=%s"
          % (cx, cy, cz, *c["size"], round((c.get("rotation") or [0, 0, 0])[1], 1), col(c)))

print("\n== skirt names ==")
for bn in ("RightSkirt", "LeftSkirt", "FrontSkirt", "BackSkirt"):
    st = {}
    for c in B[bn]["cubes"]:
        cx, cy, cz = center(c)
        st.setdefault(c.get("name"), []).append((cy, c["size"][1]))
    for nm, v in st.items():
        print("%-11s %-14s n=%-2d y=[%5.2f,%5.2f] h=[%4.2f,%4.2f]"
              % (bn, nm, len(v), min(a for a, b in v), max(a for a, b in v),
                 min(b for a, b in v), max(b for a, b in v)))

print("\n== cape rows ==")
for bn in ("Cape", "CapeLow"):
    st = {}
    for c in B[bn]["cubes"]:
        cx, cy, cz = center(c)
        import math
        ang = math.degrees(math.atan2(cx, -cz)) % 360
        st.setdefault(round(cy * 2) / 2, []).append(ang)
    for y in sorted(st):
        print("%-8s y=%5.1f n=%-2d ang=[%5.1f,%5.1f]" % (bn, y, len(st[y]), min(st[y]), max(st[y])))

print("\n== horn core count ==")
for bn in ("Horn_L", "Horn_R"):
    cs = B[bn]["cubes"]
    core = [c for c in cs if abs(c["size"][0] - c["size"][1]) < 1e-6 and
            abs(c["size"][1] - c["size"][2]) < 1e-6 and 0.40 < c["size"][0] < 1.95]
    print(bn, "total", len(cs), "core", len(core))
    for i, c in enumerate(core):
        cx, cy, cz = center(c)
        print("  core#%-2d c=(%6.2f,%6.2f,%6.2f) s=%4.2f" % (i, cx, cy, cz, c["size"][0]))
