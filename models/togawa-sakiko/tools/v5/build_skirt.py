# -*- coding: utf-8 -*-
"""Stage 1: rebuild the skirt (3 tiers + bustle) and paint the v5 swatch row."""
import math
import sys

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\tools\v5")
import common as C

NAMES = ["k0", "k1", "k2", "k3", "k1d", "k1l", "b1", "b2", "b3", "l1", "l2", "l3",
         "s1", "bt1", "bt2", "lace", "sk1", "sk2", "gem", "cp", "pw1", "pw2"]
CELLS = [(i * 16, 224) for i in range(len(NAMES))]

C.set_layout(CELLS, NAMES)
C.paint_swatches()

d, geo = C.load()
n = C.clear_v5(geo)
print("cleared v5 cubes:", n)

for b in ("Skirt", "FrontSkirt", "BackSkirt", "LeftSkirt", "RightSkirt"):
    print("drop", b, C.drop_all(geo, b))


def bone_for(a):
    a = a % 360.0
    if a <= 34 or a >= 326:
        return "FrontSkirt"
    if a <= 146:
        return "RightSkirt"
    if a <= 214:
        return "BackSkirt"
    return "LeftSkirt"


def az(i, n, phase=0.0):
    a = 360.0 * (i + 0.5) / n + phase
    while a > 180:
        a -= 360
    while a <= -180:
        a += 360
    return a


def tier(R, n, phase, ytop, ybot_fn, thick, color_fn, up=None, down=None,
         skip=None, yaw_jit=0.0, name="v5skirt"):
    total = 0
    for i in range(n):
        a = az(i, n, phase)
        if skip and skip(a):
            continue
        ar = math.radians(a)
        rc = R * math.cos(math.pi / n)
        w = 2 * R * math.sin(math.pi / n) * 1.12
        px = rc * math.sin(ar)
        pz = -rc * math.cos(ar)
        yb = ybot_fn(i, a)
        yt = ytop(i, a) if callable(ytop) else ytop
        tot = C.cube(bone_for(a), (px, (yt + yb) / 2.0, pz), (w, yt - yb, thick),
                     color_fn(i, a), up, down,
                     rot=(0, -a + yaw_jit * (((i * 7) % 3) - 1), 0), name=name)
        C.add(geo, tot["parent"], dict(tot))
        total += 1
    return total


# ---------------------------------------------------------------- 1. waistband
c = 0
c += tier(3.20, 10, 0.0, 24.62, lambda i, a: 23.50, 0.50, lambda i, a: "k2", up="k3")
# ---------------------------------------------------------------- 2. peplum flaps
c += tier(3.48, 10, 18.0, 23.62,
          lambda i, a: 22.60 - (0.35 if i % 2 else 0.0), 0.42,
          lambda i, a: "k1" if i % 2 else "k1l", up="k2", yaw_jit=3.0)

# ---------------------------------------------------------------- 3. black main (two tiers, bell)
c += tier(4.02, 12, 0.0, 23.85,
          lambda i, a: 21.55 - (0.15 if i % 2 else 0.0), 0.58,
          lambda i, a: "k1" if i % 2 else "k1d", up="k3", down="k0")


def main_bot(i, a):
    aa = abs(a)
    if aa <= 42:
        return 21.00
    if aa >= 138:
        return 19.00
    return 19.60


c += tier(4.58, 14, 12.857, 21.80, main_bot, 0.58,
          lambda i, a: "k1" if i % 3 else "k2", up="k3", down="k0", name="v5skirt2")

# ---------------------------------------------------------------- 4. black ruffle hem
def ruf_bot(i, a):
    base = main_bot(i, a) - 1.15
    return base - (0.60 if i % 2 else 0.0)


c += tier(4.86, 18, 10.0, lambda i, a: main_bot(i, a) + 0.50, ruf_bot, 0.38,
          lambda i, a: "k1l" if i % 2 else "k1d", up="k3", down="k0",
          yaw_jit=7.0, name="v5ruffle")


# ---------------------------------------------------------------- 5. light blue petticoat
def gap22(a):
    return abs(a) < 45


c += tier(4.74, 16, 11.25, lambda i, a: ruf_bot(i, a) + 0.55,
          lambda i, a: ruf_bot(i, a) - 1.55 - (0.15 if i % 2 else 0.0), 0.30,
          lambda i, a: "pw1" if i % 2 else "pw2", up="l1", down="l3",
          skip=gap22, yaw_jit=4.0, name="v5petticoat")

# ---------------------------------------------------------------- 6. mid blue body
c += tier(4.98, 16, 11.25, lambda i, a: ruf_bot(i, a) - 1.35,
          lambda i, a: 15.10, 0.38,
          lambda i, a: "l3" if i % 2 else "pw1", up="pw2", down="b3",
          skip=gap22, name="v5midblue")

# ---------------------------------------------------------------- 7. mid blue ruffle
c += tier(5.12, 18, 10.0, 15.40,
          lambda i, a: 14.35 - (0.30 if i % 2 else 0.0), 0.34,
          lambda i, a: "l3" if i % 3 else "b3", up="pw2", down="b3",
          skip=lambda a: abs(a) < 20, yaw_jit=5.0, name="v5midruffle")

# ---------------------------------------------------------------- 7b. dark inner lining
for cx, cz, w in ((0.0, 1.35, 2.3),):
    cc = C.cube("Skirt", (cx, 14.9, cz), (w, 8.4, 0.50), "k1", "k2", "k0", name="v5lining")
    C.add(geo, "Skirt", cc)

# ---------------------------------------------------------------- 8. bustle (back volume)
for i, (R, a, yt, yb, col) in enumerate([
        (4.98, 158, 20.3, 16.4, "k1"),
        (4.98, 202, 20.3, 16.4, "k1"),
        (5.12, 180, 19.8, 15.6, "k1d"),
        (5.02, 132, 19.9, 17.0, "k1l"),
        (5.02, 228, 19.9, 17.0, "k1l")]):
    ar = math.radians(a)
    px = R * math.sin(ar)
    pz = -R * math.cos(ar)
    cc = C.cube("BackSkirt", (px, (yt + yb) / 2, pz), (2.1, yt - yb, 0.45), col,
                "k3", "k0", rot=(0, -a, 0), name="v5skirtb")
    C.add(geo, "BackSkirt", cc)

tot = sum(len(b.get("cubes", [])) for b in geo["bones"])
print("cubes total now:", tot, " skirt tiers + waist:", c)
C.save(d)

