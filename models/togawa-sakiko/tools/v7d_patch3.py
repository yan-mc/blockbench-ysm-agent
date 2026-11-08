# -*- coding: utf-8 -*-
"""v7d pass 2: slimmer cap, rounder crown, separated bangs / side / back strands."""
import io, sys

p = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\tools\v7d_gen.py"
s = io.open(p, encoding="utf-8").read()

pairs = [
# ---------- cap perimeter base size
("""def cap_perimeter(t, sx=1.0, sz=1.0, hx=4.30, hz=4.20, n=5.0):""",
 """def cap_perimeter(t, sx=1.0, sz=1.0, hx=3.96, hz=3.90, n=5.0):"""),

# ---------- cap levels: hug the skull, narrower crown, uneven bottom edge
("""    levels = [(39.30, 1.00, 0.999), (38.10, 1.052, 1.046), (36.90, 1.072, 1.062),
              (35.70, 1.056, 1.048), (34.50, 1.022, 1.010), (33.20, 0.968, 0.955)]
    for li, (y, sx, sz) in enumerate(levels):
        for ti, t in enumerate(ts):
            (x, z), nrm = cap_perimeter(t, sx, sz)
            # face window: no cap plate on the front plane below the hairline
            if y < 37.85 and z < -2.80 and abs(x) < 2.75:
                continue
            R = frame((0.0, 1.0, 0.0), nrm)
            cubes.append(Cube(bone, (x, y, z), (perim / K * 1.42, 1.72, 0.50),
                              R, SWATCH[4 if y > 38.9 else (3 if y > 36.6 else 2)]))""",
 """    levels = [(39.55, 0.90, 0.90), (38.70, 0.975, 0.975), (37.75, 1.000, 1.000),
              (36.65, 0.995, 0.992), (35.50, 0.972, 0.968), (34.25, 0.940, 0.935)]
    for li, (y, sx, sz) in enumerate(levels):
        for ti, t in enumerate(ts):
            (x, z), nrm = cap_perimeter(t, sx, sz)
            # face window: no cap plate on the front plane below the hairline
            if y < 37.85 and z < -2.80 and abs(x) < 2.75:
                continue
            yy = y
            if li == len(levels) - 1:      # ragged bottom edge instead of a bob-cut line
                yy = y - (0.34 if ti % 3 else 0.0) + (0.18 if ti % 4 == 1 else 0.0)
            R = frame((0.0, 1.0, 0.0), nrm)
            cubes.append(Cube(bone, (x, yy, z), (perim / K * 1.42, 1.48, 0.46),
                              R, SWATCH[3 if y > 38.9 else (3 if y > 36.6 else 2)]))"""),

# ---------- dome: smaller apex, tighter rings
("""    rings = [
        # (scale, y, count, depth, tilt_deg)
        (0.00, 41.08, 1, 3.40, 0),
        (0.42, 40.86, 6, 1.95, 10),
        (0.68, 40.52, 10, 1.90, 24),
        (0.85, 40.12, 12, 1.85, 40),
        (0.96, 39.66, 14, 1.75, 58),
        (1.02, 39.22, 16, 1.60, 72),
    ]""",
 """    rings = [
        # (scale, y, count, depth, tilt_deg)
        (0.00, 41.02, 1, 2.30, 0),
        (0.38, 40.84, 6, 1.60, 10),
        (0.63, 40.54, 10, 1.60, 26),
        (0.83, 40.16, 12, 1.55, 44),
        (0.95, 39.70, 14, 1.50, 62),
        (1.02, 39.24, 16, 1.42, 74),
    ]"""),
("""            w = max(1.30, perim_r * s / count * 1.5)
            cubes.append(Cube(bone, (x, y, z), (w, depth, 0.52), R,
                              SWATCH[4 if ri < 4 else 3]))""",
 """            w = max(1.20, perim_r * s / count * 1.5)
            cubes.append(Cube(bone, (x, y, z), (w, depth, 0.50), R,
                              SWATCH[3 if ri < 3 else 3]))"""),
("""            cubes.append(Cube(bone, (0.0, y, 0.0), (3.40, depth, 0.52), R, SWATCH[4]))""",
 """            cubes.append(Cube(bone, (0.0, y, 0.0), (2.30, depth, 0.50), R, SWATCH[3]))"""),
("""    cubes.append(Cube(bone, (0.0, 32.92, 3.05), (7.20, 1.90, 0.55), R, SWATCH[1]))""",
 """    cubes.append(Cube(bone, (0.0, 32.92, 3.00), (6.60, 1.80, 0.55), R, SWATCH[1]))"""),

# ---------- back strands: stagger depth + length + tone so they read as locks
("""    back_main = [
        # (x0, z0, x1, z1, len_y, width0, width1)
        (0.00, 3.35, 0.30, 4.55, 18.4, 2.45, 1.95),
        (1.55, 3.45, 2.05, 4.75, 19.6, 2.35, 1.85),
        (-1.55, 3.45, -2.05, 4.75, 19.6, 2.35, 1.85),
        (3.05, 3.30, 3.95, 4.55, 21.0, 2.25, 1.75),
        (-3.05, 3.30, -3.95, 4.55, 21.0, 2.25, 1.75),
        (4.45, 3.05, 5.25, 4.20, 22.4, 1.95, 1.45),
        (-4.45, 3.05, -5.25, 4.20, 22.4, 1.95, 1.45),
        (0.75, 4.55, 1.20, 5.35, 17.2, 2.05, 1.55),
        (-0.75, 4.55, -1.20, 5.35, 17.2, 2.05, 1.55),
    ]""",
 """    back_main = [
        # (x0, z0, x1, z1, len_y, width0, width1, base_tier)
        (0.00, 3.55, 0.30, 4.45, 18.2, 2.30, 1.80, 2),
        (1.55, 3.20, 2.10, 4.95, 20.4, 2.30, 1.80, 1),
        (-1.55, 3.20, -2.10, 4.95, 20.4, 2.30, 1.80, 1),
        (3.05, 3.45, 3.90, 4.60, 21.6, 2.10, 1.60, 2),
        (-3.05, 3.45, -3.90, 4.60, 21.6, 2.10, 1.60, 2),
        (4.40, 3.15, 5.10, 4.20, 22.8, 1.85, 1.35, 1),
        (-4.40, 3.15, -5.10, 4.20, 22.8, 1.85, 1.35, 1),
        (0.78, 4.60, 1.25, 5.20, 16.6, 1.95, 1.45, 2),
        (-0.78, 4.60, -1.25, 5.20, 16.6, 1.95, 1.45, 2),
    ]"""),
("""    for i, (x0, z0, x1, z1, drop, w0, w1) in enumerate(back_main):""",
 """    for i, (x0, z0, x1, z1, drop, w0, w1, btier) in enumerate(back_main):"""),
("""        cubes += make_strand("HairBack", ctrl, 9, w0, w1, 1.05, (0, 0, 1), 0.26, base_tier=2)""",
 """        cubes += make_strand("HairBack", ctrl, 9, w0, w1, 1.05, (0, 0, 1), 0.26, base_tier=btier)"""),
("""            cubes += make_strand("HairBack", ctrl2, 7, w0 * 0.82, w1 * 0.7, 0.85, (0, 0, 1), 0.24, base_tier=1)""",
 """            cubes += make_strand("HairBack", ctrl2, 7, w0 * 0.80, w1 * 0.68, 0.85, (0, 0, 1), 0.24, base_tier=0)"""),

# ---------- side locks: narrower, spread in depth
("""        side = [
            (3.35, -1.35, 3.75, -1.95, 10.6, 1.45, 1.05, 2),
            (4.05, 0.15, 4.55, 0.55, 12.4, 1.70, 1.20, 2),
            (4.45, 1.55, 5.05, 2.10, 13.6, 1.60, 1.15, 3),
        ]""",
 """        side = [
            (3.30, -1.50, 3.70, -1.95, 10.4, 1.30, 0.95, 2),
            (3.95, 0.10, 4.30, 0.40, 12.2, 1.50, 1.05, 2),
            (4.45, 2.20, 4.75, 2.60, 13.4, 1.40, 1.00, 3),
        ]"""),

# ---------- bangs: 6 pairs, uneven hem, staggered depth
("""    bangs = [(0.42, 36.15, 1.05), (1.20, 36.30, 1.30), (1.95, 36.45, 1.25),
             (2.62, 36.65, 1.10), (3.18, 36.90, 0.95)]
    for (x, ytip, w0) in bangs:
        for sx in (-1, 1):
            ctrl = [(sx * x * 0.86, 40.02, -3.70),
                    (sx * x * 0.94, 39.30, -3.90),
                    (sx * x * 0.99, 38.40, -4.00),
                    (sx * x * 1.02, 37.45, -4.07),
                    (sx * x * 1.03, ytip, -4.11)]
            cubes += make_strand("front_h1", ctrl, 7, w0, w0 * 0.62, 0.55, (0, 0, 1), 0.26, base_tier=3)""",
 """    bangs = [(0.40, 36.10, 0.88, 3), (1.12, 36.28, 1.00, 3), (1.82, 36.52, 1.00, 2),
             (2.46, 36.80, 0.92, 3), (3.02, 37.05, 0.82, 2), (3.44, 37.30, 0.70, 3)]
    for bi, (x, ytip, w0, btier) in enumerate(bangs):
        for sx in (-1, 1):
            zj = -3.70 - 0.05 * (bi % 3)
            ctrl = [(sx * x * 0.88, 40.02, zj),
                    (sx * x * 0.95, 39.30, zj - 0.18),
                    (sx * x * 1.00, 38.45, zj - 0.30),
                    (sx * x * 1.03, 37.50, zj - 0.37),
                    (sx * x * 1.04, ytip, zj - 0.41)]
            cubes += make_strand("front_h1", ctrl, 7, w0, w0 * 0.60, 0.52, (0, 0, 1), 0.26, base_tier=btier)"""),
("""        cubes += make_strand("front_h1", ctrl, 6, 0.80, 0.55, 0.50, (0, 0, 1), 0.26, base_tier=3)""",
 """        cubes += make_strand("front_h1", ctrl, 6, 0.72, 0.50, 0.48, (0, 0, 1), 0.26, base_tier=3)"""),

# ---------- corner plates: pull in a touch
("""                (3.62, 37.30, -3.95, 1.30, 2.20, 0.55),
                (3.98, 35.95, -3.70, 1.15, 2.00, 0.55),
                (4.22, 34.55, -3.35, 1.00, 1.80, 0.55)]):""",
 """                (3.55, 37.35, -3.86, 1.15, 2.10, 0.50),
                (3.86, 36.05, -3.60, 1.00, 1.95, 0.50),
                (4.05, 34.70, -3.28, 0.90, 1.75, 0.50)]):"""),
]
for a, b in pairs:
    if a not in s:
        print("MISSING:", a.splitlines()[0]); sys.exit(1)
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8").write(s)
print("patched ok")
