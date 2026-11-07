# -*- coding: utf-8 -*-
"""v5 Round 3 (成品化精修) geometry rebuild, authored directly on main.json.

Sections
  A skirt  : drop 5 skirt bones, rebuild layered skirt (black bell + 2 ruffle rows
             + saturated blue pleat layer + narrow pale petticoat + bustle)
  B cape   : rebuild wide starry sheer cape to the calf
  C hair   : repoint all hair cubes to a brighter 7-step palette with diagonal
             streaks, ripple the back hair in z, add crown/side curls
  D horns  : +3 ridge rings, tapered tip
  E earrings / forehead ornament moved outwards + star pin
  F boots  : outer star, sole side stripe, heel block, seam stitches

bbmodel space: +Y up, front = -Z, character LEFT = -X.
"""
import json, math, os, sys
from copy import deepcopy
from PIL import Image

PACK = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack"
MAIN = os.path.join(PACK, "models", "main.json")
TEX = os.path.join(PACK, "textures", "default.png")

FACES = ("north", "south", "east", "west", "up", "down")

d = json.load(open(MAIN, encoding="utf-8"))
geo = d["minecraft:geometry"][0]
B = {b["name"]: b for b in geo["bones"]}

# ------------------------------------------------------------------ colour utils
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
    r, g, b, a = px[int(u), int(v)]
    return (r, g, b)


def cube(bone, cx, cy, cz, sx, sy, sz, uv, rot=(0, 0, 0), name="v5r3", up=None, down=None):
    c = {
        "origin": [round(-(cx + sx / 2.0), 4), round(cy - sy / 2.0, 4), round(cz - sz / 2.0, 4)],
        "size": [round(sx, 4), round(sy, 4), round(sz, 4)],
        "uv": deepcopy(uv),
        "name": name,
    }
    if up is not None:
        c["uv"]["up"] = deepcopy(up["north"])
    if down is not None:
        c["uv"]["down"] = deepcopy(down["north"])
    if any(abs(r) > 1e-9 for r in rot):
        c["rotation"] = [round(rot[0], 4), round(-rot[1], 4), round(-rot[2], 4)]
        c["pivot"] = [round(-cx, 4), round(cy, 4), round(cz, 4)]
    return c


def add(bone, c):
    B[bone].setdefault("cubes", []).append(c)


def center(c):
    o, s = c["origin"], c["size"]
    return (-(o[0] + s[0] / 2.0), o[1] + s[1] / 2.0, o[2] + s[2] / 2.0)


def move(c, cx, cy, cz, rot=None):
    """Re-centre an existing cube (keeps size + uv)."""
    s = c["size"]
    c["origin"] = [round(-(cx + s[0] / 2.0), 4), round(cy - s[1] / 2.0, 4), round(cz - s[2] / 2.0), ]
    c.pop("pivot", None)
    c.pop("rotation", None)
    if rot and any(abs(r) > 1e-9 for r in rot):
        c["rotation"] = [round(rot[0], 4), round(-rot[1], 4), round(-rot[2], 4)]
        c["pivot"] = [round(-cx, 4), round(cy, 4), round(cz, 4)]
    return c


# ------------------------------------------------------------- existing uv per colour
def norm_uv(src):
    """Return a full 6-face uv dict sampling a solid 3x3 patch."""
    if isinstance(src, dict):
        out = {}
        ok = True
        for f in FACES:
            v = src.get(f)
            if isinstance(v, dict):
                out[f] = {"uv": list(v.get("uv", [0, 0])), "uv_size": list(v.get("uv_size", [1, 1]))}
            elif isinstance(v, (list, tuple)):
                out[f] = {"uv": list(v), "uv_size": [1, 1]}
            else:
                ok = False
                break
        if ok:
            u, v = out["north"]["uv"]
            flat = {f: {"uv": [u, v], "uv_size": [3, 3]} for f in FACES}
            flat["up"] = out["up"]
            flat["down"] = out["down"]
            return flat
    u, v = uv0({"uv": src})
    return {f: {"uv": [int(u), int(v)], "uv_size": [3, 3]} for f in FACES}


UV = {}
for bn, b in B.items():
    for c in b.get("cubes", []):
        k = col(c)
        if k not in UV:
            UV[k] = norm_uv(c.get("uv"))
print("known colours:", len(UV))


NAME2HEX = {
    "k0": "0f0e14", "k1": "17151c", "k1d": "121018", "k1l": "1d1a24",
    "k2": "262230", "k3": "332f3a",
    "b1": "2c4ea9", "b2": "3f6bb5", "b3": "6f9ad0",
    "l1": "e4eefb", "l3": "cfd6e6",
    "pw1": "e4eefb", "pw2": "dfe4ee",
    "s1": "cfd6e6",
}


def U(k):
    if isinstance(k, str):
        k = RGB(NAME2HEX.get(k, k))
    if k not in UV:
        raise KeyError("no swatch for %s" % (k,))
    return UV[k]
    return UV[k]


def RGB(hexs):
    return (int(hexs[0:2], 16), int(hexs[2:4], 16), int(hexs[4:6], 16))


# ------------------------------------------------------------------ new swatches
HAIR_NEW = [(0x44, 0x4d, 0x78), (0x56, 0x61, 0x94), (0x6a, 0x77, 0xac),
            (0x80, 0x8e, 0xc2), (0x98, 0xa6, 0xd4), (0xaf, 0xbc, 0xe4), (0xc4, 0xcf, 0xec)]
CELL_HAIR = [(i * 16, 240) for i in range(7)]
CELL_CP = [(112, 240), (128, 240), (144, 240)]
OLD_HAIR = {RGB("444c73"), RGB("576292"), RGB("6e7db6"), RGB("8798ce"),
            RGB("a0b0df"), RGB("bac7e9")}


def hair_uv(i):
    u, v = CELL_HAIR[i]
    return {f: {"uv": [u + 6, v + 6], "uv_size": [3, 3]} for f in FACES}


def cp_uv(i):
    u, v = CELL_CP[i]
    return {f: {"uv": [u, v], "uv_size": [16, 16]} for f in FACES}


def paint_new_swatches():
    for i, rgb in enumerate(HAIR_NEW):
        u, v = CELL_HAIR[i]
        for y in range(v, v + 16):
            for x in range(u, u + 16):
                px[x, y] = (rgb[0], rgb[1], rgb[2], 255)
    # starry sheer navy cells (sparse: 3 / 2 stars so the cloth reads as navy, not glitter)
    bases = [(0x1e, 0x27, 0x47, 191), (0x23, 0x2e, 0x52, 191), (0x1e, 0x27, 0x47, 191)]
    for i, (u, v) in enumerate(CELL_CP):
        base = bases[i]
        for y in range(v, v + 16):
            for x in range(u, u + 16):
                px[x, y] = base
        stars = {
            0: [(3, 4, 2, (0xcf, 0xe0, 0xff)), (10, 11, 2, (0xa8, 0xc2, 0xec)),
                (13, 2, 1, (0x9d, 0xb6, 0xe2))],
            1: [(6, 7, 2, (0xcf, 0xe0, 0xff)), (13, 13, 1, (0xa8, 0xc2, 0xec))],
            2: [],                     # plain navy for the thin side faces
        }[i]
        for sx, sy, sz, rgb in stars:
            for dy in range(sz):
                for dx in range(sz):
                    if u + sx + dx < u + 16 and v + sy + dy < v + 16:
                        px[u + sx + dx, v + sy + dy] = (rgb[0], rgb[1], rgb[2], 255)


# =========================================================================== A. SKIRT
SKIRT_BONES = ("Skirt", "FrontSkirt", "BackSkirt", "LeftSkirt", "RightSkirt")


def bone_for(a):
    a = a % 360.0
    if a <= 30 or a >= 330:
        return "FrontSkirt"
    if a <= 150:
        return "RightSkirt"
    if a <= 210:
        return "BackSkirt"
    return "LeftSkirt"


def ring(R, n, phase, ytop, ybot, thick, colfn, up=None, down=None,
         yaw_jit=0.0, skip=None, name="v5r3_skirt", radial=0.0):
    made = 0
    for i in range(n):
        a = 360.0 * (i + 0.5) / n + phase
        aa = a
        while aa > 180:
            aa -= 360
        while aa <= -180:
            aa += 360
        if skip and skip(aa):
            continue
        ar = math.radians(a)
        rc = (R + radial) * math.cos(math.pi / n)
        w = 2 * R * math.sin(math.pi / n) * 1.14
        pxx = rc * math.sin(ar)
        pzz = -rc * math.cos(ar)
        yt = ytop(i, aa) if callable(ytop) else ytop
        yb = ybot(i, aa) if callable(ybot) else ybot
        c = cube(bone_for(aa), pxx, (yt + yb) / 2.0, pzz, w, yt - yb, thick,
                 U(colfn(i, aa)),
                 (0, -a + yaw_jit * (((i * 7) % 3) - 1), 0), name=name,
                 up=U(up) if up else None, down=U(down) if down else None)
        add(bone_for(aa), c)
        made += 1
    return made


def rebuild_skirt():
    old = 0
    for bn in SKIRT_BONES:
        old += len(B[bn].get("cubes", []))
        B[bn]["cubes"] = []
    n = 0
    # 1 waistband
    n += ring(3.20, 10, 0.0, 24.62, 23.50, 0.50, lambda i, a: "k2", up="k3")
    # 2 peplum flaps
    n += ring(3.52, 10, 18.0, 23.66, lambda i, a: 22.58 - (0.38 if i % 2 else 0.0),
              0.42, lambda i, a: "k2" if i % 2 else "k1l", up="k2", yaw_jit=3.5,
              name="v5r3_peplum")
    # 3 black bell upper
    n += ring(4.06, 14, 0.0, 23.88, 20.10, 0.56,
              lambda i, a: "k1" if i % 2 else "k1d", up="k3", down="k0",
              name="v5r3_bell1")
    # 4 black bell lower (slightly wider)
    n += ring(4.44, 14, 12.86, 20.60, lambda i, a: 19.55 - (0.10 if i % 2 else 0.0),
              0.56, lambda i, a: "k1" if i % 3 else "k2", up="k3", down="k0",
              name="v5r3_bell2")
    # 5 black ruffle row 1 (upper, lighter -> reads as its own tier)
    n += ring(4.90, 20, 9.0, lambda i, a: 20.30 - (0.10 if i % 2 else 0.0),
              lambda i, a: 18.95 + (0.35 if i % 2 else -0.24), 0.40,
              lambda i, a: "k2" if i % 2 else "k3", up="k3", down="k0",
              yaw_jit=6.0, name="v5r3_rf1")
    # 6 black ruffle row 2 (widest, lowest black).  phase 352.5 puts one plate dead
    #   centre-front; skipping it leaves the small front notch (the only slit).
    n += ring(5.30, 24, 352.5, lambda i, a: 19.30 - (0.12 if i % 2 else 0.0),
              lambda i, a: 17.85 + (0.42 if i % 3 == 0 else -0.30), 0.42,
              lambda i, a: "k1l" if i % 2 else "k2", up="k3", down="k0",
              yaw_jit=8.0, skip=lambda a: abs(a) < 7, name="v5r3_rf2")
    # 7 blue pleated layer (saturated, striped) - exposed 2 units below black
    n += ring(4.30, 14, 12.86, 18.98, 16.30, 0.40,
              lambda i, a: "b2" if i % 2 else "b3", up="b3", down="b1",
              name="v5r3_blue")
    # 8 blue ruffle hem
    n += ring(4.72, 18, 10.0, lambda i, a: 16.60,
              lambda i, a: 15.45 + (0.22 if i % 2 else -0.16), 0.34,
              lambda i, a: "b3" if i % 3 else "b2", up="b3", down="b2",
              yaw_jit=5.0, name="v5r3_bluerf")
    # 9 pale petticoat - narrow edge only, tucked INSIDE the blue ruffle (continuous:
    #    it is what you see through the small front slit)
    n += ring(4.50, 18, 10.0, lambda i, a: 15.85,
              lambda i, a: 15.20 + (0.12 if i % 2 else -0.08), 0.30,
              lambda i, a: "pw1" if i % 2 else "pw2", up="l1", down="l3",
              yaw_jit=4.0, name="v5r3_petti")
    # 10 bustle volume: carried by the sheer cape bulge (see B) so it cannot clip;
    #    only two side plates here to fatten the hip line under the cape edge
    for a, yt, yb, cb in ((152, 20.20, 18.10, "k1"), (208, 20.20, 18.10, "k1")):
        ar = math.radians(a)
        R = 5.02
        pxx = R * math.sin(ar)
        pzz = -R * math.cos(ar)
        add("BackSkirt", cube("BackSkirt", pxx, (yt + yb) / 2.0, pzz, 2.10, yt - yb, 0.46,
                              U(cb), (0, -a, 0), name="v5r3_bustle", up=U("k3")))
        n += 1
    # 11 dark inner lining (back) + recessed panel behind the small front slit
    add("Skirt", cube("Skirt", 0.0, 17.10, 1.10, 2.30, 4.20, 0.40, U("k1"), (0, 0, 0),
                      name="v5r3_lining", up=U("k2")))
    n += 1
    return old, n


# ============================================================================ B. CAPE
def rebuild_cape():
    old = len(B["Cape"].get("cubes", [])) + len(B["CapeLow"].get("cubes", []))
    B["Cape"]["cubes"] = []
    B["CapeLow"]["cubes"] = []
    n = 0
    rows = [
        # (bone, ytop, ybot, R, arc_lo, arc_hi, cols, cell)
        ("Cape", 21.70, 19.40, 3.95, 116, 244, 6, 0),
        ("Cape", 19.40, 17.10, 5.60, 110, 250, 6, 1),
        ("CapeLow", 17.10, 14.80, 5.75, 108, 252, 6, 0),
        ("CapeLow", 14.80, 12.50, 5.55, 110, 250, 6, 1),
        ("CapeLow", 12.50, 10.40, 5.30, 114, 246, 6, 0),
        ("CapeLow", 10.40, 9.05, 5.10, 118, 242, 6, 0),
    ]
    for ri, (bone, yt, yb, R, lo, hi, cols, cell) in enumerate(rows):
        for j in range(cols):
            a = lo + (hi - lo) * (j + 0.5) / cols
            ar = math.radians(a)
            RR = R + 0.13 * math.sin(j * 2.1 + ri * 1.7)
            w = 2 * R * math.sin(math.radians((hi - lo) / cols / 2.0)) * 1.32
            pxx = RR * math.sin(ar)
            pzz = -RR * math.cos(ar)
            yy = (yt + yb) / 2.0
            hh = yt - yb
            if yb < 10.0:            # wavy hem on the last row
                yy += 0.24 * math.sin(j * 1.9 + 0.4)
                hh += 0.30 * math.sin(j * 1.3 + 1.1)
            uv = cp_uv(cell)
            plain = cp_uv(2)
            for f in ("east", "west", "up", "down"):
                uv[f] = plain[f]
            add(bone, cube(bone, pxx, yy, pzz, w, hh, 0.14, uv,
                           (0, -a, 0), name="v5r3_cape"))
            n += 1
    return old, n


# ============================================================================ C. HAIR
def shade_idx(cx, cy):
    t = max(0.0, min(1.0, (cy - 15.5) / 23.0))
    base = 1.15 + t * 2.40
    d = (0.45 * math.sin(cx * 0.90 + cy * 0.60 + 0.6)
         + 0.20 * math.sin(cx * 2.1 - cy * 0.40)
         + 0.45 * math.sin(cx * 3.30 + 0.9))       # high-freq vertical streaks
    return max(0, min(6, int(round(base + d))))


def rebuild_hair():
    stats = {}
    touched = 0
    for bn in ("Hair", "HairBack", "front_h1", "corner_h1", "hl_side",
               "TwinTail_L", "TwinTail_R"):
        for c in B[bn].get("cubes", []):
            k = col(c)
            if k not in OLD_HAIR:
                continue
            cx, cy, cz = center(c)
            idx = shade_idx(cx, cy)
            if bn == "front_h1" and cy > 36.0:
                idx = min(6, idx + 1)
            if bn in ("TwinTail_L", "TwinTail_R", "hl_side"):
                idx = min(6, idx + 1)
            c["uv"] = hair_uv(idx)
            touched += 1
            stats[bn] = stats.get(bn, 0) + 1
    # back-hair ripple (breaks the flat horizontal bands / adds wave offset)
    moved = 0
    for c in B["HairBack"].get("cubes", []):
        cx, cy, cz = center(c)
        if cy > 25.5:
            amp = 0.70 if 29.0 < cy < 38.2 else 0.40
            dz = amp * math.sin(cx * 0.55 + cy * 0.35)
            dy = 0.16 * math.sin(cx * 0.95 + 1.2)
            yaw = 11.0 * math.sin(cx * 0.85 + cy * 0.42)
            move(c, cx, cy + dy, cz + dz, rot=(0, yaw, 0))
            moved += 1
    # crown + side curl clusters
    curls = [
        (-3.30, 41.00, 1.60, 0.95, 0.55, 1.20, (0, 22, 0), 4),
        (-3.95, 40.55, 1.10, 0.70, 0.45, 0.90, (0, 46, 0), 5),
        (3.30, 41.00, 1.60, 0.95, 0.55, 1.20, (0, -22, 0), 4),
        (3.95, 40.55, 1.10, 0.70, 0.45, 0.90, (0, -46, 0), 5),
        (0.00, 39.90, 4.15, 1.25, 0.62, 0.95, (0, 0, 0), 3),
        (0.45, 39.30, 4.55, 0.95, 0.52, 0.75, (12, 0, 0), 4),
        (-3.85, 35.60, 2.60, 0.80, 1.50, 0.80, (0, -18, 0), 3),
        (-4.05, 34.60, 2.15, 0.60, 1.10, 0.60, (0, -30, 0), 2),
        (3.85, 35.60, 2.60, 0.80, 1.50, 0.80, (0, 18, 0), 3),
        (4.05, 34.60, 2.15, 0.60, 1.10, 0.60, (0, 30, 0), 2),
    ]
    for cx, cy, cz, sx, sy, sz, rot, idx in curls:
        add("Hair", cube("Hair", cx, cy, cz, sx, sy, sz, hair_uv(idx), rot, name="v5r3_curl"))
    # small side ringlets (waves in the side locks)
    for sx in (-1, 1):
        for i, (yy, zz, s) in enumerate([(33.15, -0.35, 0.58), (32.35, 0.55, 0.50),
                                         (32.95, 1.55, 0.46)]):
            add("hl_side", cube("hl_side", sx * 3.98, yy, zz, s, 1.05, s,
                                hair_uv(2 + (i % 3)), (0, sx * (8 + 6 * i), 0),
                                name="v5r3_ringlet"))
    return touched, moved, len(curls) + 6


# ============================================================================ D. HORNS
def horn_ridges():
    n = 0
    for bn, sign in (("Horn_L", 1), ("Horn_R", -1)):
        cs = B[bn]["cubes"]
        core = [c for c in cs if abs(c["size"][0] - c["size"][1]) < 1e-6 and
                abs(c["size"][1] - c["size"][2]) < 1e-6 and
                c["size"][0] < 1.95 and c["size"][0] > 0.40]
        # add ridge rings on 3 core segments
        for t in (8, 15, 22):
            if t >= len(core):
                continue
            c = core[t]
            cx, cy, cz = center(c)
            s = c["size"][0] + 0.24
            add(bn, cube(bn, cx, cy, cz, s, s, s, U("332f3a") if RGB("332f3a") in UV
                         else U("3f3f4a"), (0, 0, 0), name="v5r3_ridge"))
            n += 1
        # taper the last three segments and add a fine tip
        tail = core[-3:]
        for i, c in enumerate(tail):
            cx, cy, cz = center(c)
            f = (0.86, 0.74, 0.58)[i]
            s = c["size"][0] * f
            c["origin"] = [round(-(cx + s / 2.0), 4), round(cy - s / 2.0, 4), round(cz - s / 2.0, 4)]
            c["size"] = [round(s, 4)] * 3
        cx, cy, cz = center(core[-1])
        add(bn, cube(bn, cx + sign * 0.30, cy - 0.10, cz - 0.05, 0.26, 0.26, 0.26,
                     U("17151c"), (0, 0, 0), name="v5r3_tip"))
        n += 1
    return n


# ================================================== E. EARRINGS + FOREHEAD ORNAMENT
def jewellery():
    n = 0
    head = B["Head"]["cubes"]
    ear = [c for c in head if abs(center(c)[0]) > 3.6 and 32.5 < center(c)[1] < 35.0]
    for c in ear:
        cx, cy, cz = center(c)
        s = 1 if cx > 0 else -1
        move(c, s * (abs(cx) + 0.70), cy, cz - 0.55)
    for s in (-1, 1):
        add("Head", cube("Head", s * 4.05, 34.62, -1.32, 0.80, 0.16, 0.16, U("9aa4b8"),
                         (0, 0, 0), name="v5r3_earpin"))
        n += 1
    # silver four-point star + buckle on the forehead
    star_c = U("cfd6e6")
    add("Hair", cube("Hair", 0.00, 38.42, -5.26, 0.62, 0.62, 0.14, star_c, (0, 0, 45),
                     name="v5r3_star"))
    add("Hair", cube("Hair", 0.00, 39.20, -5.22, 0.22, 0.42, 0.12, star_c, (0, 0, 0),
                     name="v5r3_star"))
    add("Hair", cube("Hair", 0.00, 37.64, -5.22, 0.22, 0.42, 0.12, star_c, (0, 0, 0),
                     name="v5r3_star"))
    add("Hair", cube("Hair", -0.66, 38.42, -5.22, 0.34, 0.16, 0.12, star_c, (0, 0, 0),
                     name="v5r3_star"))
    add("Hair", cube("Hair", 0.66, 38.42, -5.22, 0.34, 0.16, 0.12, star_c, (0, 0, 0),
                     name="v5r3_star"))
    add("Hair", cube("Hair", 0.00, 38.95, -5.02, 0.55, 0.22, 0.16, U("9aa4b8"),
                     (0, 0, 0), name="v5r3_buckle"))
    n += 6
    return n


# ============================================================================ F. BOOTS
def boots():
    n = 0
    for bn, s in (("LeftFoot", -1), ("RightFoot", 1)):
        # outer-side silver star (diamond) on the blue-grey panel
        add(bn, cube(bn, s * 3.46, 5.05, -0.50, 0.14, 0.46, 0.46, U("dfe4ee"),
                     (0, 0, 0), name="v5r3_bstar"))
        add(bn, cube(bn, s * 3.46, 5.05, -0.50, 0.14, 0.22, 0.22, U("ffffff") if RGB("ffffff") in UV
                     else U("dfe4ee"), (45, 0, 0), name="v5r3_bstar"))
        # sole side stripe (sits just proud of the sole wall)
        add(bn, cube(bn, s * 3.47, 0.92, -0.45, 0.12, 0.20, 3.90, U("3f3f4a"),
                     (0, 0, 0), name="v5r3_bsole"))
        # block heel
        add(bn, cube(bn, s * 2.15, 0.72, 1.35, 1.95, 1.05, 1.35, U("17151c"),
                     (0, 0, 0), name="v5r3_bheel"))
        # seam stitch across the toe cap
        add(bn, cube(bn, s * 2.15, 2.42, -3.02, 0.60, 0.15, 0.14, U("527399"),
                     (0, 0, 0), name="v5r3_bstitch"))
        n += 5
    return n


# ============================================================================== RUN
def main():
    paint_new_swatches()
    old_s, new_s = rebuild_skirt()
    old_c, new_c = rebuild_cape()
    h = rebuild_hair()
    nh = horn_ridges()
    nj = jewellery()
    nb = boots()
    tot = sum(len(b.get("cubes", [])) for b in geo["bones"])
    print("skirt %d -> %d | cape %d -> %d | hair touched/rippled/add %s | horns +%d ear+face +%d boots +%d"
          % (old_s, new_s, old_c, new_c, h, nh, nj, nb))
    print("TOTAL cubes:", tot, " bones:", len(geo["bones"]))
    # assert nothing references an unknown bone parent
    names = set(B)
    for b in geo["bones"]:
        if b.get("parent") and b["parent"] not in names:
            print("BAD PARENT", b["name"], b["parent"])
    if "--dry" in sys.argv:
        return
    img.save(TEX)
    json.dump(d, open(MAIN, "w", encoding="utf-8"), ensure_ascii=False, indent="\t")
    print("saved main.json + texture")


main()
