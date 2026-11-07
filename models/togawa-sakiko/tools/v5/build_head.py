# -*- coding: utf-8 -*-
"""v5 Round2 - head/hair/horn/ornament rebuild + Phase-1 fixes.

Authoring space = main.json space (front = -Z, up = +Y, char left = -X here).
Cubes are written directly with per-face UV pointing at solid swatch cells.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C
from PIL import Image

# ------------------------------------------------------------------ swatches
ROW = 288
NEW = ["h1", "h2", "h3", "h4", "h5", "h6", "h7",
       "sv", "sv2", "gd", "gd2", "sp", "sp2", "sp3"]
C.SWATCH_DEF.update({
    "h1": (0x44, 0x4c, 0x73),
    "h2": (0x57, 0x62, 0x92),
    "h3": (0x6e, 0x7d, 0xb6),
    "h4": (0x87, 0x98, 0xce),
    "h5": (0xa0, 0xb0, 0xdf),
    "h6": (0xba, 0xc7, 0xe9),
    "h7": (0xd4, 0xdd, 0xf4),
    "sv":  (0xdf, 0xe4, 0xee),
    "sv2": (0x9a, 0xa4, 0xb8),
    "gd":  (0xd8, 0xb0, 0x61),
    "gd2": (0x9b, 0x77, 0x35),
    "sp":  (0x4a, 0x8f, 0xd8),
    "sp2": (0x2b, 0x5d, 0xa6),
    "sp3": (0x93, 0xc6, 0xf0),
})
C.set_layout([(i * 16, ROW) for i in range(len(NEW))], NEW)
for i, n in enumerate(NEW):
    C.SW_UV[n] = [i * 16 + 6, ROW + 6, 4, 4]

# the Phase-1 ramp lives on row 224; re-register it for per-face sampling
OLD = ["k0", "k1", "k2", "k3", "k1d", "k1l", "b1", "b2", "b3", "l1", "l2", "l3",
       "s1", "bt1", "bt2", "lace", "sk1", "sk2", "gem", "cp", "pw1", "pw2"]
for i, n in enumerate(OLD):
    C.SW_UV[n] = [i * 16 + 5, 229, 3, 3]
C.SW_UV["cp"] = [320, 256, 10, 10]
C.SW_UV["cp2"] = [331, 256, 10, 10]
C.SW_CELLS["pw1"] = (320, 224)
C.SW_CELLS["pw2"] = (336, 224)

# saturated blue for the mid skirt layer (was pale pw1/pw2)
C.SWATCH_DEF["pw1"] = (0x39, 0x61, 0xb5)
C.SWATCH_DEF["pw2"] = (0x54, 0x7e, 0xc9)

d, geo = C.load()
B = C.bones(geo)

# ------------------------------------------------------------------ helpers
def tier(y):
    if y >= 38.6:
        return 6
    if y >= 35.6:
        return 5
    if y >= 32.4:
        return 4
    if y >= 29.0:
        return 3
    if y >= 25.5:
        return 2
    return 1


def hcol(y, adj=0):
    t = max(1, min(7, tier(y) + adj))
    return "h%d" % t


def faces(key, up=None, dn=None):
    up = up or key
    dn = dn or key
    out = {}
    for f in C.FACES:
        k = up if f == "up" else (dn if f == "down" else key)
        u, v, w, h = C.SW_UV[k]
        out[f] = {"uv": [u, v], "uv_size": [w, h]}
    return out


def put(bone, x, y, z, sx, sy, sz, col, up=None, dn=None, rot=None, name="v5h"):
    c = {
        "origin": [round(x - sx / 2.0, 4), round(y - sy / 2.0, 4), round(z - sz / 2.0, 4)],
        "size": [round(sx, 4), round(sy, 4), round(sz, 4)],
        "uv": faces(col, up, dn),
        "name": name,
    }
    if rot and any(abs(r) > 1e-6 for r in rot):
        c["rotation"] = [round(rot[0], 4), round(rot[1], 4), round(rot[2], 4)]
        c["pivot"] = [round(x, 4), round(y, 4), round(z, 4)]
    C.add(geo, bone, c)
    return c


def drop(bone):
    b = B[bone]
    n = len(b.get("cubes", []))
    b["cubes"] = []
    return n


def clear_prefix(pfx):
    n = 0
    for b in geo["bones"]:
        if "cubes" in b:
            keep = [c for c in b["cubes"] if not str(c.get("name", "")).startswith(pfx)]
            n += len(b["cubes"]) - len(keep)
            b["cubes"] = keep
    return n


# reverse map: swatch sample u -> colour name (from the v5 body layout)
OLD_NAMES = ["k0", "k1", "k2", "k3", "k1d", "k1l", "b1", "b2", "b3", "l1", "l2", "l3",
             "s1", "bt1", "bt2", "lace", "sk1", "sk2", "gem", "cp", "pw1", "pw2"]
REV = {i * 16 + 5: n for i, n in enumerate(OLD_NAMES)}


def key_of(c):
    uv = c.get("uv")
    if isinstance(uv, dict):
        f = uv.get("north")
        if isinstance(f, dict):
            return REV.get(f["uv"][0])
    return None


def reswatch(c, key, up=None, dn=None):
    c["uv"] = faces(key, up, dn)


print("clear v5h:", clear_prefix("v5h"))
for bn in ("HairBack", "hl_side", "corner_h1", "TwinTail_L", "TwinTail_R",
           "Ribbon", "Horn_L", "Horn_R"):
    print("drop", bn, drop(bn))

# =================================================================== A. HAIR
# ---- A0. re-colour the surviving cap + bangs to the new hair ramp
for i, c in enumerate(B["Hair"]["cubes"]):
    y = c["origin"][1] + c["size"][1] / 2.0
    z = c["origin"][2] + c["size"][2] / 2.0
    if z >= 2.0:
        adj = -2 + (1 if i % 2 else 0)   # back cap plates: shaded bands, not one flat panel
    elif y >= 39.8:
        adj = 0
    else:
        adj = -1
    reswatch(c, hcol(y, adj))
for c in B["front_h1"]["cubes"]:
    y = c["origin"][1] + c["size"][1] / 2.0
    reswatch(c, hcol(y, 0))

# ---- A0b. close the bare scalp band at the top of the back of the head
for i, x in enumerate((-2.9, -1.45, 0.0, 1.45, 2.9)):
    put("Hair", x, 39.55, 3.62, 1.60, 1.45, 1.15, hcol(39.4, -1), name="v5hcap")
    put("Hair", x, 40.35, 3.30, 1.55, 0.85, 1.60, hcol(40.3, -1), name="v5hcap")

# ---- A0c. layered fringe tips in front of the bang panel (never over the eyes)
FRINGE = [
    (2.30, -4.96, 37.00, 1.10, 0.52, -12),
    (-2.30, -4.96, 37.00, 1.10, 0.52, 12),
    (3.62, -4.92, 36.60, 1.85, 0.50, -16),
    (-3.62, -4.92, 36.60, 1.85, 0.50, 16),
    (4.02, -4.88, 35.90, 1.40, 0.44, -22),
    (-4.02, -4.88, 35.90, 1.40, 0.44, 22),
]
for x, z, yt, hgt, w, rz in FRINGE:
    put("front_h1", x, yt, z, w, hgt, 0.38, hcol(yt, 0), rot=(0, 0, rz), name="v5hbang")

# ---- A1. back mass: 5 depth layers of wavy strands
LAYERS = [
    # z,     ytop, ybot, n, halfw, adj
    (3.68, 38.80, 24.6, 6, 3.90, -1),
    (4.28, 38.10, 22.2, 7, 4.30, 0),
    (4.90, 37.50, 20.4, 7, 4.50, 0),
    (5.52, 36.90, 23.4, 6, 4.20, 1),
    (6.10, 36.20, 26.2, 4, 3.10, 1),
]
nback = 0
for k, (z0, ytop, ybot, n, W, adj) in enumerate(LAYERS):
    for j in range(n):
        x = -W + 2.0 * W * j / (n - 1.0)
        # deterministic per-column jitter
        j1 = math.sin(1.7 * j + 0.9 * k)
        j2 = math.sin(2.9 * j + 1.7 * k + 0.4)
        yb = ybot + 3.1 * j1 + 1.2 * j2 + 2.4 * (x / W) ** 2
        ytop_c = ytop + 0.9 * math.sin(2.3 * j + 1.5 * k)
        L = ytop_c - yb
        seg = [0.40 * L, 0.34 * L, 0.26 * L]
        w = 2.0 * W / (n - 1.0) * 1.14
        dz = -0.24 * (x / W) ** 2 + 0.26 * math.sin(1.4 * j + 2.1 * k)
        cx, cz = x, z0 + dz
        y = ytop_c
        # per-column shading so the strands read as separate locks
        cadj = adj + (1 if (j % 2 == 0) else -1) if k >= 2 else adj + (
            1 if (j % 3 == 0) else (-1 if j % 3 == 1 else 0))
        for i in range(3):
            h = seg[i]
            yc = y - h / 2.0
            wz = 0.34 * math.sin(1.9 * i + 0.8 * j + 0.6 * k) + 0.12 * i
            wx = 0.20 * math.sin(1.3 * i + 1.1 * j)
            put("HairBack", cx + wx, yc, cz + wz, w, h + 0.04, 0.62,
                hcol(yc, cadj), name="v5hback")
            nback += 1
            y -= h
            cx += wx * 0.7
            cz += wz * 0.6
        # tip flick + curl tile
        sgn = 1.0 if x >= 0 else -1.0
        put("HairBack", cx, y - 0.62, cz + 0.34, w * 0.60, 1.35, 0.52,
            hcol(y - 0.6, cadj), rot=(0, 0, sgn * 16), name="v5hback")
        put("HairBack", cx + 0.26 * sgn, y - 1.64, cz + 0.58, w * 0.40, 0.95, 0.42,
            hcol(y - 1.6, cadj - 1), rot=(0, 0, -sgn * 12), name="v5hback")
        nback += 2
print("hairback cubes:", nback)

# ---- A2. side locks (in front of the ear, down to the chest / waist)
SIDE = [
    # x,    z,     ytop, ybot, w,   d,   adj
    (3.86, -4.05, 36.90, 29.4, 0.78, 0.85, 1),
    (4.24, -2.45, 36.60, 25.6, 0.92, 1.05, 0),
    (4.58, 0.55, 36.00, 23.4, 0.90, 1.10, -1),
]
ns = 0
for x0, z0, ytop, ybot, w, dd, adj in SIDE:
    for sgn in (-1.0, 1.0):
        L = ytop - ybot
        y = ytop
        seg = [0.42 * L, 0.34 * L, 0.24 * L]
        for i in range(3):
            h = seg[i]
            yc = y - h / 2.0
            wx = 0.12 * math.sin(1.4 * i + 1.0)
            put("corner_h1" if abs(x0) < 4.0 else "hl_side",
                sgn * (x0 + wx * sgn + 0.06 * i), yc, z0 - 0.22 * i,
                w, h + 0.04, dd, hcol(yc, adj), name="v5hside")
            ns += 1
            y -= h
        put("hl_side", sgn * (x0 + 0.28), y - 0.45, z0 - 0.60, w * 0.62, 1.05, dd * 0.6,
            hcol(y, adj - 1), rot=(0, 0, -sgn * 18), name="v5hside")
        ns += 1
print("side lock cubes:", ns)

# ---- A3. low twin tails with wave + black ribbon tie
nt = 0
for sgn in (-1.0, 1.0):
    bone = "TwinTail_L" if sgn < 0 else "TwinTail_R"
    for j, (dx, dz) in enumerate(((-0.44, 0.35), (0.10, 0.95), (0.60, 1.55))):
        x = sgn * (4.30 + dx)
        z0 = dz
        y = 36.4
        ybot = 21.8 + 0.9 * j
        L = y - ybot
        seg = [0.38 * L, 0.34 * L, 0.28 * L]
        for i in range(3):
            h = seg[i]
            yc = y - h / 2.0
            wz = 0.34 * math.sin(1.8 * i + 1.2 * j)
            put(bone, x + sgn * 0.10 * i, yc, z0 + wz, 1.02, h + 0.04, 0.90,
                hcol(yc, 0), rot=(0, 0, -sgn * 5 * i), name="v5htail")
            nt += 1
            y -= h
        put(bone, x + sgn * 0.34, y - 0.55, z0 + 0.55, 0.62, 1.30, 0.55,
            hcol(y, -1), rot=(0, 0, -sgn * 20), name="v5htail")
        nt += 1
    # ribbon tie at the root
    put(bone, sgn * 4.26, 36.35, 0.95, 1.20, 0.46, 1.15, "k1", "k2", "k1d",
        rot=(0, 0, 0), name="v5htail")
    nt += 1
print("twin tail cubes:", nt)

# ---- A4. big black bows (left on Ribbon, right on new HairBow_R)
if "HairBow_R" not in B:
    geo["bones"].append({"name": "HairBow_R", "parent": "Hair", "pivot": [4.72, 36.2, 0.9]})
    B["HairBow_R"] = geo["bones"][-1]

def bow(bone, sx, x, y, z, rot):
    sgn = -1.0 if x < 0 else 1.0
    put(bone, x + sgn * 0.58, y + 0.68, z, 1.45, 0.86, 0.66, "k1", "k2", "k1d",
        rot=(0, 0, sgn * 26), name="v5hbow")
    put(bone, x + sgn * 0.58, y - 0.68, z, 1.45, 0.86, 0.66, "k1", "k2", "k1d",
        rot=(0, 0, -sgn * 26), name="v5hbow")
    put(bone, x, y, z + 0.06, 0.66, 0.92, 0.78, "k0", "k1", "k0", name="v5hbow")
    put(bone, x - sgn * 0.16, y - 1.30, z + 0.16, 0.56, 1.75, 0.46, "k1", "k2", "k1d",
        rot=(0, 0, sgn * 8), name="v5hbow")
    put(bone, x - sgn * 0.02, y - 2.55, z + 0.36, 0.50, 1.45, 0.40, "k1", "k2", "k1d",
        rot=(0, 0, -sgn * 6), name="v5hbow")

bow("Ribbon", -1, -5.12, 36.05, -0.20, 0)
bow("HairBow_R", 1, 5.12, 36.05, -0.20, 0)
print("bow cubes: 10")

# =================================================================== B. HORNS
BASE = [
    (-1.63, 38.84, 0.52), (-1.81, 38.73, -0.09), (-1.99, 38.86, -0.68),
    (-2.17, 39.20, -1.20), (-2.35, 39.70, -1.59), (-2.52, 40.33, -1.83),
    (-2.70, 40.98, -1.88), (-2.88, 41.62, -1.77), (-3.05, 42.17, -1.49),
    (-3.23, 42.59, -1.10), (-3.41, 42.82, -0.65), (-3.58, 42.88, -0.14),
    (-3.76, 42.77, 0.34), (-3.93, 42.48, 0.74), (-4.12, 42.08, 1.05),
    (-4.29, 41.60, 1.22), (-4.46, 41.09, 1.26), (-4.64, 40.62, 1.19),
    (-4.82, 40.21, 0.98), (-5.01, 39.93, 0.69), (-5.17, 39.76, 0.39),
    (-5.34, 39.75, 0.05), (-5.53, 39.84, -0.26), (-5.70, 40.04, -0.50),
    (-5.88, 40.34, -0.68),
]
# remap the spiral so the ring sits BESIDE the head (jaw -> above crown), not on top
Y0, YS = 36.60, 1.35
Z0, ZS = -3.00, 1.25


def thick(t):
    # hold girth for the first 30 %, then taper hard to a fine tip
    if t < 0.30:
        return 1.98
    u = (t - 0.30) / 0.70
    return 1.98 - (1.98 - 0.50) * (u ** 1.20)


nh = 0
for sgn in (-1.0, 1.0):
    bone = "Horn_L" if sgn < 0 else "Horn_R"
    pts = []
    for (px, py, pz) in BASE:
        y = Y0 + (py - 38.73) * YS
        z = Z0 + (pz + 2.50) * ZS
        b = (abs(px) + 0.62) * 0.94 + 0.72
        pts.append((sgn * b, y, z))
    # resample to 34 points for a smoother tube
    N = 34
    dense = []
    for i in range(N):
        f = i / (N - 1.0) * (len(pts) - 1)
        i0 = int(math.floor(f))
        i1 = min(i0 + 1, len(pts) - 1)
        u = f - i0
        dense.append(tuple(pts[i0][c] * (1 - u) + pts[i1][c] * u for c in range(3)))
    n = len(dense)
    for i, (x, y, z) in enumerate(dense):
        t = i / (n - 1.0)
        s = thick(t)
        col = "k2" if (i // 4) % 2 == 0 else "k1"
        if t > 0.90:
            col = "k1"
        put(bone, x, y, z, s, s, s, col, "k3", "k1d", name="v5hhorn")
        nh += 1
    # ribbed rings
    for f in (0.10, 0.24, 0.38, 0.52, 0.66, 0.79):
        i = int(round(f * (n - 1)))
        x, y, z = dense[i]
        s = thick(f) * 1.20
        put(bone, x, y, z, s, s * 0.44, s, "bt1", "sv2", "k2", name="v5hhorn")
        nh += 1
    # root collar + gold rings near the tip
    x, y, z = dense[1]
    s = thick(0.03) * 1.12
    put(bone, x, y, z, s, s * 0.54, s, "k0", "k1", "k0", name="v5hhorn")
    nh += 1
    for f in (0.82, 0.88):
        i = int(round(f * (n - 1)))
        x, y, z = dense[i]
        s = thick(f) * 1.15
        put(bone, x, y, z, s, s * 0.38, s, "gd", "gd2", "gd2", name="v5hhorn")
        nh += 1
print("horn cubes:", nh)

# =================================================================== C. ORNAMENTS
# ---- black band over the crown + fleur-de-lis + sapphire (front bangs)
BAND = [
    (0.0, 40.96, -1.05, 1.55, 0.30, 0.42, 0),
    (0.0, 40.78, -2.55, 1.52, 0.30, 0.52, 0),
    (0.0, 40.38, -3.55, 1.46, 0.30, 0.46, 0),
    (0.0, 39.82, -4.24, 1.38, 0.32, 0.40, 0),
    (0.0, 39.18, -4.64, 1.24, 0.34, 0.32, 0),
]
for x, y, z, sx, sy, sz, _ in BAND:
    put("Hair", x, y, z, sx, sy, sz, "k0", "k1", "k0", name="v5hband")
# fleur-de-lis (silver) at the forehead
put("Hair", 0.0, 38.52, -5.06, 0.46, 1.30, 0.28, "sv", "sv", "sv2", name="v5horn")
put("Hair", 0.0, 38.18, -5.10, 1.52, 0.22, 0.26, "sv2", "sv", "sv2", name="v5horn")
put("Hair", 0.74, 38.66, -5.04, 0.66, 0.62, 0.26, "sv", "sv", "sv2",
    rot=(0, 0, 32), name="v5horn")
put("Hair", -0.74, 38.66, -5.04, 0.66, 0.62, 0.26, "sv", "sv", "sv2",
    rot=(0, 0, -32), name="v5horn")
put("Hair", 0.0, 37.54, -4.98, 0.46, 0.70, 0.26, "sv", "sv", "sv2", name="v5horn")
put("Hair", 0.0, 38.42, -5.18, 0.40, 0.50, 0.22, "sp", "sp3", "sp2", name="v5horn")
# silver star pins on both temples
for sgn in (-1.0, 1.0):
    put("Hair", sgn * 2.42, 38.36, -4.86, 0.44, 0.44, 0.22, "sv", "sv", "sv2",
        rot=(0, 0, 45), name="v5horn")
    put("Hair", sgn * 2.42, 38.36, -4.88, 0.18, 0.62, 0.18, "sv2", "sv", "sv2",
        name="v5horn")
print("head ornament cubes: 14")

# ---- earrings
for sgn in (-1.0, 1.0):
    put("Head", sgn * 3.74, 34.42, -0.85, 0.18, 0.55, 0.18, "sv2", "sv", "sv2",
        name="v5horn")
    put("Head", sgn * 3.76, 33.86, -0.90, 0.52, 0.52, 0.26, "sp3", "sp", "sp2",
        rot=(0, 0, 45), name="v5horn")
    put("Head", sgn * 3.76, 33.32, -0.90, 0.30, 0.34, 0.22, "sp2", "sp", "sp2",
        rot=(0, 0, 45), name="v5horn")
print("earring cubes: 6")

# ---- choker jewel + gold chain dangles (on Collar, in front of the chest)
put("Collar", 0.0, 32.62, -1.98, 0.62, 0.62, 0.24, "sp3", "sp", "sp2",
    rot=(0, 0, 45), name="v5horn")
put("Collar", 0.0, 33.14, -1.94, 0.30, 0.22, 0.20, "sv", "sv", "sv2", name="v5horn")
for sgn in (-1.0, 1.0):
    put("Collar", sgn * 0.52, 31.62, -2.05, 0.16, 0.80, 0.16, "gd", "gd", "gd2",
        name="v5horn")
    put("Collar", sgn * 0.52, 30.96, -2.05, 0.28, 0.42, 0.18, "sp3", "sp", "sp2",
        rot=(0, 0, 45), name="v5horn")
put("Collar", 0.0, 31.30, -2.08, 0.16, 0.95, 0.16, "gd", "gd", "gd2", name="v5horn")
put("Collar", 0.0, 30.62, -2.08, 0.30, 0.46, 0.18, "sp3", "sp", "sp2",
    rot=(0, 0, 45), name="v5horn")
print("choker cubes: 7")

# =================================================================== D. PHASE-1
# ---- D1. close the front skirt gap (was open y 15.4..19.3)
put("FrontSkirt", 0.0, 17.85, -5.00, 2.62, 4.30, 0.42, "k1", "k2", "k1d", name="v5hs")
put("FrontSkirt", 2.18, 17.55, -4.60, 2.42, 4.00, 0.42, "k2", "k3", "k1", rot=(0, 22, 0),
    name="v5hs")
put("FrontSkirt", -2.18, 17.55, -4.60, 2.42, 4.00, 0.42, "k2", "k3", "k1", rot=(0, -22, 0),
    name="v5hs")
put("FrontSkirt", 0.0, 15.72, -5.06, 2.30, 0.46, 0.40, "k1", "k2", "k1d", name="v5hs")
# ---- D1b. side layers above the blue band become black (narrow blue hem)
nrec = 0
for bn in ("LeftSkirt", "RightSkirt", "FrontSkirt", "BackSkirt"):
    for c in B[bn]["cubes"]:
        if str(c.get("name", "")).startswith("v5h"):
            continue
        k = key_of(c)
        if k not in ("pw1", "pw2", "l1", "l2", "b1", "b2", "b3", "l3"):
            continue
        y = c["origin"][1] + c["size"][1] / 2.0
        if y > 15.40:
            idx = int(round((y - 14.0) * 2)) % 2
            reswatch(c, "k1" if idx == 0 else "k2", "k2", "k1d")
            nrec += 1
        elif y > 14.40:
            col = "b2" if int(round(abs(c["origin"][0]) * 2)) % 2 == 0 else "b3"
            reswatch(c, col, "b3", "b1")
            nrec += 1
print("skirt blue->black:", nrec)

# ---- D2. corset bow (bigger) + long ribbon tails
put("UpperBody", 0.72, 28.42, -2.70, 1.24, 0.66, 0.30, "b2", "b3", "b1", rot=(0, 0, 26),
    name="v5hs")
put("UpperBody", -0.72, 28.42, -2.70, 1.24, 0.66, 0.30, "b2", "b3", "b1", rot=(0, 0, -26),
    name="v5hs")
put("UpperBody", 0.0, 28.12, -2.78, 0.50, 0.56, 0.36, "b1", "b2", "b1", name="v5hs")
put("UpperBody", 0.0, 28.12, -2.86, 0.26, 0.30, 0.22, "sp3", "sp3", "sp", name="v5hs")
put("UpperBody", 0.26, 26.55, -2.72, 0.36, 2.90, 0.22, "b2", "b3", "b1", rot=(0, 0, 3),
    name="v5hs")
put("UpperBody", -0.30, 26.30, -2.72, 0.34, 3.30, 0.22, "b1", "b2", "b1", rot=(0, 0, -4),
    name="v5hs")
put("UpperBody", 0.44, 24.80, -2.62, 0.40, 0.44, 0.22, "b3", "b3", "b2", rot=(0, 0, 20),
    name="v5hs")
put("UpperBody", -0.50, 24.55, -2.62, 0.40, 0.44, 0.22, "b3", "b3", "b2", rot=(0, 0, -20),
    name="v5hs")
# ---- D2b. stronger blue cross lacing on the waist sides
for sgn in (-1.0, 1.0):
    for k in range(3):
        yy = 24.55 + k * 0.78
        put("UpperBody", sgn * 2.40, yy, -1.72, 0.18, 0.95, 0.18, "b2", "b3", "b1",
            rot=(38, 0, 0), name="v5hs")
        put("UpperBody", sgn * 2.40, yy + 0.34, -1.72, 0.18, 0.95, 0.18, "b3", "b2", "b1",
            rot=(-38, 0, 0), name="v5hs")

# ---- D3. boots: bigger visible laces, sole detail, blue panel edge
for sgn in (-1.0, 1.0):
    f = "LeftFoot" if sgn < 0 else "RightFoot"
    cx = 2.15 * sgn
    put(f, cx, 1.02, -0.48, 2.62, 0.18, 4.42, "k3", "k3", "k1", name="v5hs")   # midsole line
    put(f, cx, 0.14, -0.50, 2.48, 0.28, 4.30, "k0", "k0", "k0", name="v5hs")   # sole bottom
    put(f, cx, 2.30, -2.42, 2.44, 0.30, 0.95, "sv2", "sv2", "k1", name="v5hs")  # toe welt
    for k in range(4):
        yy = 4.55 + k * 0.62
        off = 0.30 if k % 2 == 0 else -0.30
        put(f, cx + off, yy, -2.12, 1.15, 0.20, 0.20, "sp3", "sp", "sp2",
            rot=(0, 0, 30 if k % 2 == 0 else -30), name="v5hs")
        put(f, cx - off, yy + 0.30, -2.12, 1.15, 0.20, 0.20, "sp3", "sp", "sp2",
            rot=(0, 0, -30 if k % 2 == 0 else 30), name="v5hs")
    for k in range(5):
        yy = 4.52 + k * 0.50
        put(f, cx + (0.92 if k % 2 else -0.92), yy, -2.14, 0.18, 0.18, 0.14,
            "sv", "sv", "sv2", name="v5hs")

# ---- D4. cape: raise to the waist, widen, keep it sheer
SF = (320, 256, 32, 32)
print("drop old cape:", clear_prefix("v5bcape"))


def cape_plate(bone, a_deg, R, yt, yb, w, zoff=0.0, uvoff=(0, 0)):
    ar = math.radians(a_deg)
    c = put(bone, R * math.sin(ar), (yt + yb) / 2.0, -R * math.cos(ar) + zoff,
            w, yt - yb, 0.16, "cp", rot=(0, a_deg, 0), name="v5hcape")
    rect = (SF[0] + uvoff[0], SF[1] + uvoff[1], 10, 10)
    for fc in C.FACES:
        c["uv"][fc] = {"uv": [rect[0], rect[1]], "uv_size": [rect[2], rect[3]]}
    return c


for i in range(6):
    a = 143.0 + i * (217.0 - 143.0) / 5.0
    cape_plate("Cape", a, 4.95, 22.60 - 0.20 * abs(i - 2.5), 15.40 - 0.55 * (i % 2),
               2.05, 0.15, ((i % 3) * 11, (i // 3) * 11))
for i in range(6):
    a = 138.0 + i * (222.0 - 138.0) / 5.0
    cape_plate("CapeLow", a, 5.45, 15.80 - 0.40 * (i % 2), 8.80 - 0.85 * ((i * 3) % 2),
               2.25, 0.30, ((i % 3) * 11, (i // 3) * 11))
print("cape plates: 12")

# ---- D5. narrow light-blue petticoat edge ring at the very hem
for i in range(10):
    a = math.radians(360.0 * (i + 0.5) / 10)
    R = 4.62
    put("FrontSkirt" if math.cos(a) < -0.55 else ("BackSkirt" if math.cos(a) > 0.55
        else ("LeftSkirt" if math.sin(a) > 0 else "RightSkirt")),
        R * math.sin(a), 13.86, -R * math.cos(a), 2.60, 0.40, 0.34, "l2", "l1", "l3",
        rot=(0, -math.degrees(a), 0), name="v5hs")

# =================================================================== save
C.paint_swatches()
tot = sum(len(b.get("cubes", [])) for b in geo["bones"])
print("total cubes:", tot)
C.save(d)
