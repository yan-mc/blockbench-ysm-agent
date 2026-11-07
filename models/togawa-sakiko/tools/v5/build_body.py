# -*- coding: utf-8 -*-
"""Stage 2: legs / stockings / garters / boots / puff sleeves / gloves / corset / cape."""
import math
import sys

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\tools\v5")
import common as C

NAMES = ["k0", "k1", "k2", "k3", "k1d", "k1l", "b1", "b2", "b3", "l1", "l2", "l3",
         "s1", "bt1", "bt2", "lace", "sk1", "sk2", "gem", "cp", "pw1", "pw2"]
CELLS = [(i * 16, 224) for i in range(len(NAMES))]
C.set_layout(CELLS, NAMES)
# hand-placed 32x32 starfield for the sheer cape (sparse, large enough to vary per plate)
SF = (320, 256, 32, 32)
C.SW_UV["cp"] = [SF[0], SF[1], 10, 10]

d, geo = C.load()
bn = C.bones(geo)
P = "v5b"

# ---- clear previous body cubes
n = 0
for b in geo["bones"]:
    if "cubes" in b:
        keep = [c for c in b["cubes"] if not str(c.get("name", "")).startswith(P)]
        n += len(b["cubes"]) - len(keep)
        b["cubes"] = keep
print("cleared body cubes:", n)

# ---- drop old parts
for b in ("LeftLeg", "LeftLowerLeg", "LeftFoot", "RightLeg", "RightLowerLeg", "RightFoot",
          "LeftForeArm", "RightForeArm", "LeftHand", "RightHand", "LeftArm", "RightArm"):
    print("drop", b, C.drop_all(geo, b))

# ---- remove the stray light-blue belt cube on UpperBody (old peplum strip)
ub = C.bones(geo)["UpperBody"]
before = len(ub["cubes"])
ub["cubes"] = [c for c in ub["cubes"]
               if not (abs(c["origin"][1] - 23.3) < 0.01 and abs(c["size"][0] - 5) < 0.01
                       and abs(c["size"][1] - 0.7) < 0.01)]
print("UpperBody belt cube removed:", before - len(ub["cubes"]))

# ---- cape bones
if "Cape" not in C.bones(geo):
    geo["bones"].append({"name": "Cape", "parent": "DownBody", "pivot": [0, 17.6, 4.0]})
    geo["bones"].append({"name": "CapeLow", "parent": "Cape", "pivot": [0, 12.8, 4.6]})


def put(bone, center, size, side, up=None, down=None, rot=(0, 0, 0), name=P):
    c = C.cube(bone, center, size, side, up, down, rot, name=name)
    bone_name = c["parent"]
    C.add(geo, bone_name, c)


def ring_at(bone, cx, R, n, phase, y0, y1, thick, cols, up=None, down=None,
            rot_extra=0.0, name=P):
    for i in range(n):
        a = 360.0 * (i + 0.5) / n + phase
        ar = math.radians(a)
        rc = R * math.cos(math.pi / n)
        w = 2 * R * math.sin(math.pi / n) * 1.10
        col = cols[i % len(cols)]
        put(bone, (cx + rc * math.sin(ar), (y0 + y1) / 2.0, -rc * math.cos(ar)),
            (w, y1 - y0, thick), col, up, down, rot=(0, -a + rot_extra, 0), name=name)


# ================================================================= 1. legs
for sgn, side in ((-1, "L"), (1, "R")):
    cx = 2.15 * sgn
    leg = "LeftLeg" if sgn < 0 else "RightLeg"
    low = "LeftLowerLeg" if sgn < 0 else "RightLowerLeg"
    # bare upper thigh (mostly under the skirt)
    ring_at(leg, cx, 1.24, 6, 0.0, 18.80, 21.35, 0.42, ["sk1"], "sk2", "sk2", rot_extra=30)
    # stocking top band (wide lace band, lighter so it reads as a step)
    ring_at(leg, cx, 1.28, 8, 0.0, 16.60, 18.15, 0.40, ["k2", "k1l"], "k3", "k1d")
    # stocking thigh (ribbed: alternate two darks)
    ring_at(leg, cx, 1.13, 8, 22.5, 14.60, 16.75, 0.40, ["k1", "k1l"], "k2", "k1d")
    # knee
    ring_at(low, cx, 1.01, 8, 0.0, 13.20, 14.75, 0.40, ["k1", "k1l"], "k2", "k1d")
    # calf
    ring_at(low, cx, 1.08, 8, 22.5, 10.60, 13.35, 0.40, ["k1", "k1l"], "k2", "k1d")
    # low calf -> ankle
    ring_at(low, cx, 0.98, 8, 0.0, 8.40, 10.75, 0.40, ["k1", "k1l"], "k2", "k1d")
    ring_at(low, cx, 0.90, 8, 22.5, 6.55, 8.55, 0.38, ["k1", "k1l"], "k2", "k1d")

# garters: two straps per leg + silver cross clasps
for sgn in (-1, 1):
    cx = 2.15 * sgn
    leg = "LeftLeg" if sgn < 0 else "RightLeg"
    for dx in (-0.52, 0.52):
        put(leg, (cx + dx, 18.95, -1.16), (0.30, 1.60, 0.16), "k1", "k2", "k1d")
        # silver cross clasp
        put(leg, (cx + dx, 17.85, -1.16), (0.17, 0.52, 0.17), "s1", "s1", "s1")
        put(leg, (cx + dx, 17.85, -1.17), (0.46, 0.15, 0.15), "s1", "s1", "s1")

# chain + gems on the character's LEFT thigh (T3 breakdown D3)
for i, dx in enumerate((-1.05, -0.55, 0.0, 0.55, 1.05)):
    dy = 17.55 - 0.26 * (1.0 - abs(dx) / 1.05)
    put("LeftLeg", (-2.15 + dx, dy, -1.20), (0.22, 0.20, 0.14), "s1", "s1", "s1")
for dx, dy, w in ((0.0, 16.95, 0.34), (-0.55, 17.12, 0.26), (0.55, 17.12, 0.26)):
    put("LeftLeg", (-2.15 + dx, dy, -1.22), (w, 0.55, 0.16), "gem", "s1", "b3")

# ================================================================= 2. boots
for sgn in (-1, 1):
    cx = 2.15 * sgn
    f = "LeftFoot" if sgn < 0 else "RightFoot"
    put(f, (cx, 0.55, -0.50), (2.55, 1.10, 4.35), "k0", "k1d", "k0")           # platform
    put(f, (cx, 1.55, -0.48), (2.50, 0.90, 4.25), "k1", "k2", "k0")            # platform mid
    put(f, (cx, 2.45, 1.05), (2.40, 0.90, 1.50), "k0", "k1d", "k0")            # heel block
    put(f, (cx, 3.15, -0.85), (2.45, 2.30, 3.55), "bt1", "bt2", "k0")         # shoe body
    put(f, (cx, 3.45, 1.08), (2.42, 1.85, 1.55), "k1", "k2", "k0")            # heel counter
    put(f, (cx, 2.85, -2.52), (2.50, 1.75, 0.85), "k0", "k0", "k0")            # toe cap
    put(f, (cx, 5.25, -0.30), (2.35, 2.30, 3.30), "bt1", "bt2", "k1")          # blue shaft
    put(f, (cx, 5.25, 1.06), (2.40, 2.30, 1.00), "k1", "k2", "k1")             # black back
    for dx in (-1.17, 1.17):
        put(f, (cx + dx, 5.15, -0.50), (0.20, 1.70, 2.50), "bt2", "bt1", "k1")  # side panels
    put(f, (cx, 6.45, -0.30), (2.50, 0.52, 3.45), "bt2", "bt1", "k1")          # cuff roll
    put(f, (cx, 6.76, -0.30), (2.42, 0.22, 3.35), "k1", "k2", "k1")            # cuff edge
    # criss-cross laces
    for k in range(3):
        yy = 4.45 + k * 0.60
        put(f, (cx - 0.28, yy, -1.99), (0.60, 0.15, 0.15), "lace", "lace", "lace",
            rot=(0, 0, 38))
        put(f, (cx + 0.28, yy + 0.30, -1.99), (0.60, 0.15, 0.15), "lace", "lace", "lace",
            rot=(0, 0, -38))
    for k in range(4):
        yy = 4.40 + k * 0.50
        put(f, (cx + (0.84 if k % 2 else -0.84), yy, -1.96), (0.16, 0.16, 0.14),
            "s1", "s1", "s1")

# ================================================================= 3. puff sleeves + arms
for sgn, side in ((-1, "L"), (1, "R")):
    cx = 3.30 * sgn
    arm = "LeftArm" if sgn < 0 else "RightArm"
    fore = "LeftForeArm" if sgn < 0 else "RightForeArm"
    hand = "LeftHand" if sgn < 0 else "RightHand"
    put(arm, (cx, 26.15, -0.05), (1.78, 2.60, 1.78), "sk1", "sk2", "sk2")      # upper arm skin
    put(arm, (cx, 29.15, -0.05), (3.70, 2.60, 3.70), "k1", "k2", "k1d")        # puff main
    put(arm, (cx, 29.15, -0.05), (3.40, 2.30, 3.40), "k1d", "k1", "k0", rot=(0, 45, 0))
    put(arm, (cx, 27.70, -0.05), (2.65, 0.95, 2.65), "k1", "k2", "k1d")        # gather
    put(arm, (cx, 30.55, -0.05), (2.60, 0.80, 2.60), "k2", "k3", "k1")         # shoulder roll
    ring_at(arm, cx, 1.50, 8, 0.0, 26.95, 27.95, 0.30, ["k1l", "k1"], "k2", "k1d")
    ring_at(arm, cx, 1.34, 6, 30.0, 30.80, 31.42, 0.26, ["k3", "k2"], "k3", "k1")
    # bare forearm (skin)
    put(fore, (cx, 24.30, -0.05), (2.02, 1.60, 2.02), "sk1", "sk2", "sk2")
    put(fore, (cx, 22.90, -0.05), (1.88, 2.20, 1.88), "sk1", "sk2", "sk2")
    put(fore, (cx, 21.00, -0.05), (1.78, 1.70, 1.78), "sk1", "sk2", "sk2")
    # glove cuff (lace edge = lightness step)
    ring_at(fore, cx, 1.10, 6, 0.0, 19.55, 20.30, 0.26, ["k2", "k2", "k3"], "k3", "k1")
    ring_at(fore, cx, 1.16, 6, 30.0, 20.30, 20.62, 0.24, ["k3", "k3"], "k3", "k2")
    # glove hand
    put(hand, (cx, 18.75, -0.05), (1.95, 1.70, 1.95), "k1", "k2", "k1d")
    put(hand, (cx, 17.45, -0.10), (1.82, 1.30, 1.55), "k1", "k2", "k1d")
    put(hand, (cx - 1.02 * sgn, 18.45, -0.30), (0.48, 0.95, 0.70), "k1", "k2", "k1d")

# ================================================================= 4. corset details
# blue criss-cross lacing on both sides of the corset waist
for sgn in (-1, 1):
    x = 2.36 * sgn
    for k in range(2):
        yy = 24.95 + k * 0.82
        put("UpperBody", (x, yy, -0.52), (0.14, 0.80, 0.14), "b2", "b2", "b1", rot=(40, 0, 0))
        put("UpperBody", (x, yy, 0.34), (0.14, 0.80, 0.14), "b2", "b2", "b1", rot=(-40, 0, 0))
    put("UpperBody", (x, 26.06, -0.10), (0.16, 0.55, 0.16), "b1", "b2", "b1")

# off-shoulder lace trim (elliptical ring round the neckline)
for i in range(12):
    a = math.radians(360.0 * (i + 0.5) / 12)
    rx, rz = 2.92, 1.98
    put("UpperBody", (rx * math.sin(a), 30.95, -rz * math.cos(a)),
        (1.42, 0.46, 0.26), "k1l" if i % 2 else "k3", "k2", "k1",
        rot=(0, -math.degrees(a), 0))

# chest bow: two blue loops + knot
put("UpperBody", (0.58, 28.30, -2.54), (0.98, 0.52, 0.28), "b2", "b3", "b1", rot=(0, 0, 26))
put("UpperBody", (-0.58, 28.30, -2.54), (0.98, 0.52, 0.28), "b2", "b3", "b1", rot=(0, 0, -26))
put("UpperBody", (0.0, 28.06, -2.62), (0.44, 0.50, 0.34), "b1", "b2", "b1")

# ================================================================= 5. sheer starry cape / train
def retint(c, rect):
    for f in c["uv"]:
        c["uv"][f] = {"uv": [rect[0], rect[1]], "uv_size": [rect[2], rect[3]]}


def cape_plate(bone, a_deg, R, yt, yb, w, zoff=0.0):
    ar = math.radians(a_deg)
    c = C.cube(bone, (R * math.sin(ar), (yt + yb) / 2, -R * math.cos(ar) + zoff),
               (w, yt - yb, 0.16), "cp", "cp", "cp", rot=(0, -a_deg, 0), name=P + "cape")
    C.add(geo, bone, c)
    return c


for i in range(6):
    a = 138.0 + i * (222.0 - 138.0) / 5.0
    yt = 15.60 - 0.12 * abs(i - 2)
    yb = 11.10 - 0.50 * ((i * 3) % 2)
    c = cape_plate("Cape", a, 4.50, yt, yb, 1.95, 0.25)
    retint(c, (SF[0] + (i % 3) * 11, SF[1] + (i // 3) * 11, 10, 10))
for i in range(6):
    a = 140.0 + i * (220.0 - 140.0) / 5.0
    yt = 11.45 - 0.30 * ((i * 3) % 2)
    yb = 7.55 - 0.65 * ((i * 5) % 2)
    c = cape_plate("CapeLow", a, 4.75, yt, yb, 2.05, 0.45)
    retint(c, (SF[0] + (i % 3) * 11, SF[1] + 12 + (i // 3) * 11, 10, 10))

tot = sum(len(b.get("cubes", [])) for b in geo["bones"])
print("total cubes:", tot)

# ---- paint the 32x32 starfield swatch (sparse stars, sheer navy)
from PIL import Image
import random
im = Image.open(C.TEX).convert("RGBA")
px = im.load()
x0, y0, w, h = SF
for yy in range(y0, y0 + h):
    for xx in range(x0, x0 + w):
        px[xx, yy] = (10, 15, 32, 210)
rnd = random.Random(11)
for i in range(4):
    sx = x0 + 5 + rnd.randrange(0, w - 10)
    sy = y0 + 3 + rnd.randrange(0, h - 6)
    for dx2, dy2 in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        px[sx + dx2, sy + dy2] = (214, 228, 250, 210)
im.save(C.TEX)

# ---- soften two bright boning strips on the corset front (they sampled a light region)
def solid(c, key):
    u, v, ww, hh = C.SW_UV[key]
    c["uv"] = {f: {"uv": [u, v], "uv_size": [ww, hh]}
               for f in ("north", "south", "east", "west", "up", "down")}


nfix = 0
for c in C.bones(geo)["UpperBody"]["cubes"]:
    if not isinstance(c.get("uv"), list):
        continue
    o, sz = c["origin"], c["size"]
    if abs(sz[0] - 2.8) < 0.05 or abs(sz[0] - 2.6) < 0.05:
        if abs(sz[1] - 0.5) < 0.06 or abs(sz[1] - 0.4) < 0.06:
            solid(c, "k2"); nfix += 1
            continue
    if abs(sz[0] - 0.5) < 0.05 and abs(sz[1] - 0.7) < 0.05:
        solid(c, "b3"); nfix += 1
        continue
    if o[2] <= -1.8 and sz[0] < 0.62 and sz[1] < 3.0:
        solid(c, "k3" if sz[0] > 0.2 else "k2"); nfix += 1
print("recolored corset strips:", nfix)
C.save(d)
