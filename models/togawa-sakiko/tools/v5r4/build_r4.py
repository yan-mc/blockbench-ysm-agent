# -*- coding: utf-8 -*-
"""v5 round 4 (final polish) -- applied on top of the frozen r3 baseline.

Targets
  1 forehead : big grey 4-point star + wide black band  -> small gold fleur
               (3 thin pieces, total width <=1.2) + 1 sapphire; black band
               narrowed and kept on the crown only (no forehead bar)
  2 earrings : grey 0.52 diamond set -> sapphire diamond + silver setting (0.38)
  3 skirt    : +12 pointed black petals under the black hem (2 staggered rows),
               blue frill untouched
  4 hair     : +5 curved cover strips (2 segments each) on the upper back hair,
               +3 small micro-curls on top / side-back
  5 horns    : +3 ridge rings per side (light / dark alternating)
  6 cape     : stars brightened (light blue / white); side columns pulled inside
               the skirt silhouette so the front view shows skirt, not cape

Reads  artifacts/v5/r4/baseline/{main.json,default.png}   (frozen r3 state)
Writes pack/models/main.json + pack/textures/default.png
bbmodel space: +Y up, front = -Z, character LEFT = -X.
"""
import json, math, os, sys
from copy import deepcopy
from PIL import Image

ROOT = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
BASE = os.path.join(ROOT, "artifacts", "v5", "r4", "baseline")
PACK = os.path.join(ROOT, "pack")
MAIN = os.path.join(PACK, "models", "main.json")
TEX = os.path.join(PACK, "textures", "default.png")

d = json.load(open(os.path.join(BASE, "models", "main.json"), encoding="utf-8"))
geo = d["minecraft:geometry"][0]
B = {b["name"]: b for b in geo["bones"]}

img = Image.open(os.path.join(BASE, "textures", "default.png")).convert("RGBA")
px = img.load()
W, H = img.size
FACES = ("north", "south", "east", "west", "up", "down")


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


def cube(bone, cx, cy, cz, sx, sy, sz, uv, rot=(0, 0, 0), name="v5r4"):
    c = {"origin": [round(-(cx + sx / 2.0), 4), round(cy - sy / 2.0, 4), round(cz - sz / 2.0, 4)],
         "size": [round(sx, 4), round(sy, 4), round(sz, 4)],
         "uv": deepcopy(uv), "name": name}
    if any(abs(r) > 1e-9 for r in rot):
        c["rotation"] = [round(rot[0], 4), round(-rot[1], 4), round(-rot[2], 4)]
        c["pivot"] = [round(-cx, 4), round(cy, 4), round(cz, 4)]
    return c


def add(bone, c):
    B[bone].setdefault("cubes", []).append(c)


def set_size(c, sx, sy, sz):
    cx, cy, cz = center(c)
    c["size"] = [round(sx, 4), round(sy, 4), round(sz, 4)]
    c["origin"] = [round(-(cx + sx / 2.0), 4), round(cy - sy / 2.0, 4), round(cz - sz / 2.0, 4)]
    if "pivot" in c:
        c["pivot"] = [round(-cx, 4), round(cy, 4), round(cz, 4)]


def shift_x(c, dx):
    """move a cube along x, keeping any rotation pivot on the new centre"""
    c["origin"][0] = round(c["origin"][0] - dx, 4)
    if "pivot" in c:
        c["pivot"][0] = round(c["pivot"][0] - dx, 4)


# --------------------------------------------------------------- colour table
UV = {}
for bn, b in B.items():
    for c in b.get("cubes", []):
        UV.setdefault(col(c), c.get("uv"))


def norm_uv(src):
    if isinstance(src, dict):
        out = {}
        for f in FACES:
            v = src.get(f)
            if isinstance(v, dict):
                out[f] = {"uv": list(v.get("uv", [0, 0])), "uv_size": list(v.get("uv_size", [1, 1]))}
            else:
                out[f] = {"uv": list(v), "uv_size": [1, 1]}
        u, v = out["north"]["uv"]
        flat = {f: {"uv": [u, v], "uv_size": [3, 3]} for f in FACES}
        return flat
    u, v = uv0({"uv": src})
    return {f: {"uv": [int(u), int(v)], "uv_size": [3, 3]} for f in FACES}


# new swatch row (y = 256) -- verified empty in the r3 texture
SW = [("gold", (0xC9, 0xA3, 0x55)), ("gold_h", (0xE9, 0xD1, 0x8C)),
      ("gold_d", (0x93, 0x74, 0x36)), ("silver", (0xDF, 0xE4, 0xEE)),
      ("silver_d", (0x8E, 0x97, 0xAB)), ("sapphire", (0x2E, 0x6F, 0xD2)),
      ("sapphire_h", (0x83, 0xB6, 0xF2)), ("sapphire_d", (0x1B, 0x3C, 0x84))]
CELL_SW = {k: (i * 16, 256) for i, (k, _) in enumerate(SW)}
SWUV = {}
for k, _ in SW:
    u, v = CELL_SW[k]
    SWUV[k] = {f: {"uv": [u + 6, v + 6], "uv_size": [3, 3]} for f in FACES}


def paint_new_swatches():
    for k, rgb in SW:
        u, v = CELL_SW[k]
        for y in range(v, v + 16):
            for x in range(u, u + 16):
                if px[x, y][3] != 0:
                    raise SystemExit("swatch cell %s not empty at %d,%d" % (k, x, y))
                px[x, y] = (rgb[0], rgb[1], rgb[2], 255)


def U(key):
    if isinstance(key, tuple):
        if key not in UV:
            raise KeyError(key)
        return norm_uv(UV[key])
    return SWUV[key]


# name -> colour looked up from existing cubes
K = {}
for nm, hexs in (("k0", "0f0e14"), ("k1", "17151c"), ("k1l", "1d1a24"), ("k2", "262230"),
                 ("k3", "332f3a"), ("ridge_l", "41597a"), ("ridge_d", "1d1a24"),
                 ("b1", "2c4ea9"), ("b2", "3f6bb5"), ("b3", "6f9ad0")):
    K[nm] = (int(hexs[0:2], 16), int(hexs[2:4], 16), int(hexs[4:6], 16))

HAIR_CELLS = [(i * 16, 240) for i in range(7)]


def hair_uv(i):
    u, v = HAIR_CELLS[max(0, min(6, i))]
    return {f: {"uv": [u + 6, v + 6], "uv_size": [3, 3]} for f in FACES}


REPORT = []


# ================================================================ 1. FOREHEAD
def forehead():
    hair = B["Hair"]["cubes"]
    # --- black crown band: the 5 near-black bars on the centre line
    band = [c for c in hair if col(c) == (15, 14, 20) and abs(center(c)[0]) < 0.12
            and center(c)[1] > 39.0]
    band.sort(key=lambda c: center(c)[2])    # ascending z: most negative = lowest on the forehead
    removed = 0
    for c in band:                          # rebuild the whole band as a thin ribbon
        hair.remove(c)
        removed += 1
    # thin black alice-band laying on the crown, front-to-back, 0.55 wide x 0.16 tall
    for zz, yy in ((-2.60, 40.50), (-1.40, 40.97), (-0.20, 40.97), (1.00, 40.97), (2.20, 40.92)):
        add("Hair", cube("Hair", 0.00, yy, zz, 0.55, 0.16, 1.30,
                         U(K["k0"] if zz < -1.0 else K["k1"]), name="v5r4_band"))
    # --- old oversized silver four-point star + buckle + sapphire (12 cubes)
    old = [c for c in hair if center(c)[2] < -4.88 and abs(center(c)[0]) < 1.25
           and 37.2 < center(c)[1] < 39.6]
    for c in old:
        hair.remove(c)
    # --- buried gold / sapphire leftovers behind the fringe (Head bone)
    head = B["Head"]["cubes"]
    buried = [c for c in head if center(c)[2] < -3.4 and center(c)[1] > 38.4]
    for c in buried:
        head.remove(c)
    # --- new: small gold fleur (3 thin pieces, 1.00 wide) + 1 sapphire
    add("Hair", cube("Hair", 0.00, 38.26, -4.71, 0.18, 0.56, 0.16, U("gold"), name="v5r4_fleur"))
    add("Hair", cube("Hair", -0.25, 38.45, -4.71, 0.44, 0.13, 0.14, U("gold_h"),
                     (0, 0, -36), name="v5r4_fleur"))
    add("Hair", cube("Hair", 0.25, 38.45, -4.71, 0.44, 0.13, 0.14, U("gold_h"),
                     (0, 0, 36), name="v5r4_fleur"))
    add("Hair", cube("Hair", 0.00, 38.34, -4.82, 0.22, 0.22, 0.10, U("sapphire"),
                     (0, 0, 45), name="v5r4_gem"))
    REPORT.append("forehead: -%d band (2 on forehead) narrowed 3, -%d star pieces, -%d buried gold, +4"
                  % (removed, len(old), len(buried)))

    # --- side hairline sparkles: shrink 0.44 -> 0.32, drop the 0.62 cross bars
    sparks = [c for c in hair if 2.2 < abs(center(c)[0]) < 2.7 and center(c)[2] < -4.7
              and 37.9 < center(c)[1] < 38.8]
    drop = 0
    for c in sparks:
        if c["size"][0] < 0.3:              # the thin vertical cross bar
            hair.remove(c)
            drop += 1
        else:
            set_size(c, 0.32, 0.32, 0.18)
            c["uv"] = U("silver")
    REPORT.append("side sparkles: -%d bars, 2 diamonds 0.44->0.32 silver" % drop)


# ================================================================ 2. EARRINGS
def earrings():
    head = B["Head"]["cubes"]
    dead = [c for c in head if abs(center(c)[0]) > 4.2 and 0.05 < c["size"][0] < 0.95
            and center(c)[1] < 35.2]
    for c in dead:
        head.remove(c)
    # the side lock (hl_side #2: x<=4.60, z>=-2.98) hid the old drop -> hang the
    # earring just outside / in front of it so it is visible from the front
    for s in (-1, 1):
        add("Head", cube("Head", s * 4.56, 34.35, -3.06, 0.12, 0.34, 0.12, U("silver_d"),
                         name="v5r4_earlink"))
        add("Head", cube("Head", s * 4.56, 33.95, -3.08, 0.40, 0.40, 0.13, U("silver"),
                         (0, 0, 45), name="v5r4_earset"))
        add("Head", cube("Head", s * 4.56, 33.95, -3.17, 0.30, 0.30, 0.11, U("sapphire"),
                         (0, 0, 45), name="v5r4_eardrop"))
    REPORT.append("earrings: -%d old pieces, +6 (silver 0.40 setting + sapphire 0.30, z-3.08)" % len(dead))


# ================================================================== 3. SKIRT
def bone_for(a):
    a = a % 360.0
    if a <= 30 or a >= 330:
        return "FrontSkirt"
    if a <= 150:
        return "RightSkirt"
    if a <= 210:
        return "BackSkirt"
    return "LeftSkirt"


def skirt_petals():
    n = 0
    for k in range(12):
        a = 15.0 + 30.0 * k
        ar = math.radians(a)
        lower = (k % 2 == 0)
        # two tiers: lower/longer sits slightly inside, upper/shorter sits proud
        R = 5.56 if lower else 5.64
        yy = 17.16 if lower else 17.76
        sx, sy = (0.80, 1.10) if lower else (0.62, 0.82)
        pxx = R * math.sin(ar)
        pzz = -R * math.cos(ar)
        colr = "k1" if lower else "k2"
        add(bone_for(a), cube(bone_for(a), pxx, yy, pzz, sx, sy, 0.24,
                              U(K[colr]), (0, -a, 45), name="v5r4_petal"))
        n += 1
    REPORT.append("skirt: +12 pointed petals, 2 tiers (R5.34/5.54 y17.28/17.82)")


# =================================================================== 4. HAIR
def surface_z(bone, x, y):
    vals = []
    for c in B[bone]["cubes"]:
        cx, cy, cz = center(c)
        sx, sy, sz = c["size"]
        if abs(cx - x) <= sx / 2.0 + 0.45 and abs(cy - y) <= sy / 2.0 + 0.30:
            vals.append(cz + sz / 2.0)
    if not vals:
        return -99.0
    vals.sort()
    return vals[min(len(vals) - 1, int(len(vals) * 0.70))]   # upper quartile surface


def hair_strips():
    strips = [(-3.15, 10, 3), (-1.55, -12, 2), (0.15, 8, 4), (1.85, -9, 3), (3.30, 12, 2)]
    n = 0
    for x, yaw0, cell in strips:
        for i, (yy, hh, yawd) in enumerate(((35.90, 4.70, yaw0), (31.40, 4.60, -yaw0))):
            zs = surface_z("HairBack", x, yy)
            if zs < -50:
                continue
            z = zs + 0.12 - 0.26
            add("HairBack", cube("HairBack", x + (0.18 if i else 0.0), yy, z, 1.05, hh, 0.52,
                                 hair_uv(cell + (1 if i else 0)), (0, yawd, 0),
                                 name="v5r4_strip"))
            n += 1
    curls = [(0.00, 41.05, 3.55, 0.95, 0.60, 0.85, (0, 0, 0), 5),             (-3.55, 40.40, 2.95, 0.72, 0.52, 0.80, (0, -26, 0), 4),
             (3.55, 40.40, 2.95, 0.72, 0.52, 0.80, (0, 26, 0), 4)]
    for cx, cy, cz, sx, sy, sz, rot, cell in curls:
        add("Hair", cube("Hair", cx, cy, cz, sx, sy, sz, hair_uv(cell), rot, name="v5r4_curl"))
        n += 1
    REPORT.append("hair: +%d cover-strip segments (5 strips) +3 micro curls" % (n - 3))


# ================================================================== 5. HORNS
def horn_ridges():
    n = 0
    for bn in ("Horn_L", "Horn_R"):
        core = [c for c in B[bn]["cubes"]
                if abs(c["size"][0] - c["size"][1]) < 1e-6 and
                abs(c["size"][1] - c["size"][2]) < 1e-6 and 1.95 > c["size"][0] > 0.40]
        for idx, key, grow in ((4, "ridge_l", 0.22), (12, "ridge_d", 0.20),
                               (19, "ridge_l", 0.18)):
            if idx >= len(core):
                continue
            c = core[idx]
            cx, cy, cz = center(c)
            s = c["size"][0] + grow
            add(bn, cube(bn, cx, cy, cz, s, s, s, U(K[key]), name="v5r4_ridge"))
            n += 1
    REPORT.append("horns: +%d ridge rings (light 41597a / dark 1d1a24)" % n)


# =================================================================== 6. CAPE
def cape():
    moved = 0
    for bn in ("Cape", "CapeLow"):
        for c in B[bn]["cubes"]:
            cx, cy, cz = center(c)
            if abs(cx) > 4.55:
                nx = math.copysign(4.55, cx)
                shift_x(c, nx - cx)
                moved += 1
    # brighter starfield: repaint the three sheer-navy cells
    bases = [(0x1e, 0x27, 0x47), (0x23, 0x2e, 0x52), (0x1e, 0x27, 0x47)]
    stars = {
        0: [(3, 4, 2, (0xF4, 0xF8, 0xFF)), (10, 11, 2, (0xC9, 0xDF, 0xFF)),
            (13, 2, 2, (0xAF, 0xCC, 0xFA))],
        1: [(6, 7, 2, (0xF4, 0xF8, 0xFF)), (13, 13, 2, (0xC9, 0xDF, 0xFF))],
        2: [],
    }
    for i, (u, v) in enumerate(((112, 240), (128, 240), (144, 240))):
        base = bases[i]
        for y in range(v, v + 16):
            for x in range(u, u + 16):
                px[x, y] = (base[0], base[1], base[2], 191)
        for sx, sy, s, rgb in stars[i]:
            for dy in range(s):
                for dx in range(s):
                    px[u + sx + dx, v + sy + dy] = (rgb[0], rgb[1], rgb[2], 230)
    REPORT.append("cape: %d side cubes pulled inside |x|<=4.55, stars brightened" % moved)


def main():
    paint_new_swatches()
    forehead()
    earrings()
    skirt_petals()
    hair_strips()
    horn_ridges()
    cape()
    tot = sum(len(b.get("cubes", [])) for b in geo["bones"])
    names = set(B)
    for b in geo["bones"]:
        if b.get("parent") and b["parent"] not in names:
            print("BAD PARENT", b["name"])
    for r in REPORT:
        print(" -", r)
    print("TOTAL cubes:", tot, " bones:", len(geo["bones"]))
    if "--dry" in sys.argv:
        print("(dry run, nothing written)")
        return
    if tot > 1120:
        raise SystemExit("cube budget exceeded")
    os.makedirs(os.path.dirname(MAIN), exist_ok=True)
    json.dump(d, open(MAIN, "w", encoding="utf-8"), ensure_ascii=False, indent="\t")
    img.save(TEX)
    print("saved main.json + default.png")


main()
