# -*- coding: utf-8 -*-
"""Shared helpers for the v5 Phase-1 rebuild (skirt / legs / boots / sleeves / corset / cape).

Coordinate conventions:
  * All geometry in this module is authored in *Blockbench/bbmodel* space:
    +Y up, front = -Z, and the character's LEFT is -X (matches LeftLeg pivot x=-2.4).
  * main.json is a MIRROR of bbmodel space:  json_x = -(bb_x_max), pinning
        origin_x_json = -(cx + sx/2)
        rot_json     = (rx, -ry, -rz)
        pivot_x_json = -pivot_x_bb
    verified against LeftFoot cube json o=[-3.2,...] -> bb_scene o=[0.9,...].
"""
import json
import math
import os

PACK = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack"
MAIN = os.path.join(PACK, "models", "main.json")
TEX = os.path.join(PACK, "textures", "default.png")


def load():
    with open(MAIN, encoding="utf-8") as f:
        d = json.load(f)
    return d, d["minecraft:geometry"][0]


def save(d):
    with open(MAIN, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def bones(geo):
    return {b["name"]: b for b in geo["bones"]}


# ---------------------------------------------------------------- texture swatches
# name -> (rgb or rgba, block size in px)
SWATCH_DEF = {
    "k0":  (0x0f, 0x0e, 0x14),
    "k1":  (0x17, 0x15, 0x1c),
    "k2":  (0x26, 0x22, 0x30),
    "k3":  (0x33, 0x2f, 0x3a),
    "k1d": (0x12, 0x10, 0x18),
    "k1l": (0x1d, 0x1a, 0x24),
    "b1":  (0x2c, 0x4e, 0xa9),
    "b2":  (0x3f, 0x6b, 0xb5),
    "b3":  (0x6f, 0x9a, 0xd0),
    "l1":  (0xcf, 0xe0, 0xf5),
    "l2":  (0xe4, 0xee, 0xfb),
    "l3":  (0xa9, 0xc6, 0xe8),
    "pw1": (0x9a, 0xbb, 0xdd),
    "pw2": (0xb4, 0xcd, 0xe9),
    "s1":  (0xcf, 0xd6, 0xe6),
    "bt1": (0x41, 0x59, 0x7a),
    "bt2": (0x52, 0x73, 0x99),
    "lace": (0x4d, 0x7f, 0xc4),
    "sk1": (0xf2, 0xd7, 0xcc),
    "sk2": (0xe4, 0xc0, 0xb6),
    "gem": (0x8f, 0xb8, 0xea),
    "cp":  (0x0e, 0x14, 0x28, 150),   # starry sheer navy (drawn with stars by paint_swatches)
    "cp2": (0x16, 0x1e, 0x38, 170),
}

# 16x16 cell grid; every swatch owns one whole cell.  Filled in by find_free_cells / set_layout.
SW_CELLS = {}   # name -> (cx, cy) top-left of the 16x16 cell
SW_UV = {}      # name -> [u, v, w, h] sample rect


def used_mask(geo, size=512):
    import numpy as np
    m = np.zeros((size, size), dtype=bool)
    for b in geo["bones"]:
        for c in b.get("cubes", []):
            s = c["size"]
            uv = c.get("uv")
            rects = []
            if isinstance(uv, dict):
                for f, val in uv.items():
                    if isinstance(val, dict):
                        u, v = val.get("uv", [0, 0])
                        w, h = val.get("uv_size", [1, 1])
                    else:
                        u, v = val
                        w, h = 1, 1
                    rects.append((u, v, u + w, v + h))
            else:
                u, v = (uv or [0, 0])[:2]
                w = 2 * (s[0] + s[2])
                h = s[1] + s[2]
                rects.append((u, v, u + w, v + h))
            for (x0, y0, x1, y1) in rects:
                x0 = max(0, int(math.floor(x0))); y0 = max(0, int(math.floor(y0)))
                x1 = min(size, int(math.ceil(x1))); y1 = min(size, int(math.ceil(y1)))
                if x1 > x0 and y1 > y0:
                    m[y0:y1, x0:x1] = True
    return m


def find_free_cells(geo, ymin=224, size=512, cell=16):
    """Return list of (cx,cy) cell origins that are completely free, scanning rows."""
    m = used_mask(geo, size)
    out = []
    for cy in range(ymin, size - cell + 1, cell):
        for cx in range(0, size - cell + 1, cell):
            if not m[cy:cy + cell, cx:cx + cell].any():
                out.append((cx, cy))
    return out


def set_layout(cells, names, cell=16, block=6, pad=5):
    """Assign each name a 16x16 cell; sample rect is a solid block inside it."""
    if len(cells) < len(names):
        raise RuntimeError("not enough free cells: %d < %d" % (len(cells), len(names)))
    SW_CELLS.clear(); SW_UV.clear()
    for i, n in enumerate(names):
        cx, cy = cells[i]
        SW_CELLS[n] = (cx, cy)
        if n in ("cp", "cp2"):
            SW_UV[n] = [cx + 1, cy + 1, cell - 2, cell - 2]   # pattern swatch: whole cell
        else:
            # sample a 3x3 solid area well inside the cell
            SW_UV[n] = [cx + pad, cy + pad, 3, 3]


def paint_swatches(path=None, cell=16):
    """Paint every swatch into the texture PNG (keeps existing pixels)."""
    from PIL import Image, ImageDraw
    path = path or TEX
    img = Image.open(path).convert("RGBA")
    px = img.load()
    for n, (cx, cy) in SW_CELLS.items():
        col = SWATCH_DEF[n]
        rgba = (col[0], col[1], col[2], col[3] if len(col) > 3 else 255)
        for y in range(cy, cy + cell):
            for x in range(cx, cx + cell):
                px[x, y] = rgba
    # star dots + ruffles for the cape swatches
    for n in ("cp", "cp2"):
        if n not in SW_CELLS:
            continue
        cx, cy = SW_CELLS[n]
        base = SWATCH_DEF[n]
        rnd = 12345
        for i in range(9):
            rnd = (rnd * 1103515245 + 12345) & 0x7fffffff
            sx = cx + 2 + (rnd // 7) % (cell - 4)
            rnd = (rnd * 1103515245 + 12345) & 0x7fffffff
            sy = cy + 2 + (rnd // 7) % (cell - 4)
            px[sx, sy] = (0xe6, 0xf0, 0xff, 235)
            if i % 3 == 0:
                px[sx + 1, sy] = (0xd8, 0xe6, 0xfa, 200)
                px[sx, sy + 1] = (0xd8, 0xe6, 0xfa, 200)
    img.save(path)
    return path


# ---------------------------------------------------------------- cube builder
FACES = ("north", "south", "east", "west", "up", "down")


def _face_uv(name):
    u, v, w, h = SW_UV[name]
    return {"uv": [u, v], "uv_size": [w, h]}


def cube(bone, center, size, side, up=None, down=None, rot=(0, 0, 0), name="v5"):
    """Build one bedrock cube dict from bbmodel-space center/size."""
    cx, cy, cz = [round(float(v), 4) for v in center]
    sx, sy, sz = [round(float(v), 4) for v in size]
    up = up or side
    down = down or side
    uv = {}
    for f in FACES:
        key = up if f == "up" else (down if f == "down" else side)
        uv[f] = _face_uv(key)
    out = {
        "origin": [round(-(cx + sx / 2.0), 4), round(cy - sy / 2.0, 4), round(cz - sz / 2.0, 4)],
        "size": [sx, sy, sz],
        "uv": uv,
        "name": name,
        "parent": bone,
    }
    if any(abs(r) > 1e-6 for r in rot):
        out["rotation"] = [round(rot[0], 4), round(-rot[1], 4), round(-rot[2], 4)]
        out["pivot"] = [round(-cx, 4), cy, cz]
    return out


def add(geo, bone, c):
    b = bones(geo)[bone]
    if "cubes" not in b:
        b["cubes"] = []
    c.pop("parent", None)
    b["cubes"].append(c)


def clear_v5(geo):
    """Remove every cube this script (or a previous run) added."""
    n = 0
    for b in geo["bones"]:
        if "cubes" in b:
            keep = [c for c in b["cubes"] if not str(c.get("name", "")).startswith("v5")]
            n += len(b["cubes"]) - len(keep)
            b["cubes"] = keep
    return n


def drop_all(geo, bone):
    b = bones(geo)[bone]
    n = len(b.get("cubes", []))
    b["cubes"] = []
    return n


def ring(geo, bone, R, n, phase, y0, y1, thick, side, up=None, down=None,
         cx=0.0, cz=0.0, skip=None, hem=None, yaw_jit=0.0, name="v5ring"):
    """A ring of vertical plates around (cx,cz).  skip(a_deg) -> True to omit."""
    made = []
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
        rc = R * math.cos(math.pi / n)
        w = 2 * R * math.sin(math.pi / n) * 1.10
        px = cx + rc * math.sin(ar)
        pz = cz - rc * math.cos(ar)
        ya, yb = y0, y1
        if hem:
            dy0, dy1 = hem(i, aa)
            ya += dy0; yb += dy1
        made.append(cube(bone, (px, (ya + yb) / 2.0, pz), (w, yb - ya, thick),
                         side, up, down, rot=(0, -a + yaw_jit * ((i % 3) - 1), 0), name=name))
    for c in made:
        add(geo, bone, c)
    return len(made)


def ring_center(bone, R, n, a_deg, cx=0.0, cz=0.0):
    ar = math.radians(a_deg)
    rc = R * math.cos(math.pi / n)
    return cx + rc * math.sin(ar), cz - rc * math.cos(ar)


def yaw_for(a_deg):
    return -a_deg
