# -*- coding: utf-8 -*-
"""v7d pass 4: round the crown silhouette (dome no longer widest), squarer cap
corners so the box skull corners are covered, softer bang / side-lock edges."""
import io, sys
p = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\tools\v7d_gen.py"
s = io.open(p, encoding="utf-8").read()

pairs = [
# squarer shell cross-section (covers the box skull corners)
("""def cap_perimeter(t, sx=1.0, sz=1.0, hx=3.96, hz=3.90, n=5.0):""",
 """def cap_perimeter(t, sx=1.0, sz=1.0, hx=3.92, hz=3.86, n=8.0):"""),

# profile: widest around the ears, tapering both up and down
("""    levels = [(39.55, 0.90, 0.90), (38.70, 0.975, 0.975), (37.75, 1.000, 1.000),
              (36.65, 0.995, 0.992), (35.50, 0.972, 0.968), (33.92, 0.940, 0.935)]""",
 """    levels = [(39.62, 0.905, 0.905), (38.75, 0.975, 0.975), (37.80, 1.000, 1.000),
              (36.70, 0.995, 0.992), (35.55, 0.972, 0.968), (33.92, 0.940, 0.935)]"""),

# dome: sits on top of the shell and narrows all the way up
("""    rings = [
        # (scale, y, count, depth, tilt_deg)
        (0.00, 41.02, 1, 2.30, 0),
        (0.38, 40.84, 6, 1.60, 10),
        (0.63, 40.54, 10, 1.60, 26),
        (0.83, 40.16, 12, 1.55, 44),
        (0.95, 39.70, 14, 1.50, 62),
        (1.02, 39.24, 16, 1.42, 74),
    ]""",
 """    rings = [
        # (scale, y, count, depth, tilt_deg)
        (0.00, 40.98, 1, 1.95, 0),
        (0.33, 40.78, 6, 1.40, 12),
        (0.57, 40.46, 9, 1.35, 32),
        (0.77, 40.06, 11, 1.30, 52),
        (0.905, 39.62, 13, 1.30, 70),
    ]"""),

# corner tiles become part of the dome shoulder instead of a slab on top
("""            cubes.append(Cube(bone, (sx * 3.28, 40.30, sz * 3.28),
                              (2.50, 2.50, 0.52), Rc, SWATCH[3]))""",
 """            cubes.append(Cube(bone, (sx * 3.18, 40.06, sz * 3.18),
                              (2.45, 2.45, 0.50), Rc, SWATCH[3]))"""),

# softer outer bangs
("""    bangs = [(0.40, 36.10, 0.88, 3), (1.12, 36.28, 1.00, 3), (1.82, 36.52, 1.00, 2),
             (2.46, 36.80, 0.92, 3), (3.02, 37.05, 0.82, 2), (3.44, 37.30, 0.70, 3)]""",
 """    bangs = [(0.40, 36.10, 0.86, 3), (1.10, 36.26, 0.98, 3), (1.78, 36.50, 0.96, 2),
             (2.40, 36.78, 0.84, 3), (2.94, 37.02, 0.72, 2), (3.36, 37.26, 0.58, 3)]"""),

# slimmer, better separated side locks
("""        side = [
            (3.30, -1.50, 3.70, -1.95, 10.4, 1.30, 0.95, 2),
            (3.95, 0.10, 4.30, 0.40, 12.2, 1.50, 1.05, 2),
            (4.45, 2.20, 4.75, 2.60, 13.4, 1.40, 1.00, 3),
        ]""",
 """        side = [
            (3.28, -1.55, 3.66, -1.98, 10.4, 1.18, 0.88, 2),
            (3.92, 0.12, 4.26, 0.44, 12.2, 1.36, 0.98, 1),
            (4.42, 2.30, 4.72, 2.70, 13.6, 1.30, 0.92, 3),
        ]"""),
]
for a, b in pairs:
    if a not in s:
        print("MISSING:", a.splitlines()[0]); sys.exit(1)
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8").write(s)
print("patched ok")
