# -*- coding: utf-8 -*-
"""v7d pass 6: bangs as a parted, layered fringe with tapered tips (no comb of
equal tabs), plus stronger tip taper for every strand."""
import io, sys
p = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\tools\v7d_gen.py"
s = io.open(p, encoding="utf-8").read()

pairs = [
# stronger taper at the very tip
("""        if taper_end and i >= len(sd) - 2:
            w *= 0.78""",
 """        if taper_end and i >= len(sd) - 2:
            w *= 0.74
            if i == len(sd) - 1:
                w *= 0.72"""),

# parted layered bangs
("""    bangs = [(0.40, 36.12, 0.86, 3), (1.10, 36.58, 0.98, 1), (1.78, 36.20, 0.96, 3),
             (2.40, 36.72, 0.84, 2), (2.94, 36.34, 0.74, 3), (3.36, 36.92, 0.60, 2)]
    for bi, (x, ytip, w0, btier) in enumerate(bangs):
        for sx in (-1, 1):
            zj = -3.70 - 0.05 * (bi % 3)
            ctrl = [(sx * x * 0.88, 40.02, zj),
                    (sx * x * 0.95, 39.30, zj - 0.18),
                    (sx * x * 1.00, 38.45, zj - 0.30),
                    (sx * x * 1.03, 37.50, zj - 0.37),
                    (sx * x * 1.04, ytip, zj - 0.41)]
            cubes += make_strand("front_h1", ctrl, 7, w0, w0 * 0.60, 0.52, (0, 0, 1), 0.26, base_tier=btier)""",
 """    bangs = [(0.42, 36.20, 0.90, 3), (1.12, 36.42, 0.98, 2), (1.80, 36.62, 0.94, 3),
             (2.42, 36.82, 0.86, 2), (2.96, 37.02, 0.74, 3), (3.38, 37.22, 0.62, 2)]
    for bi, (x, ytip, w0, btier) in enumerate(bangs):
        for sx in (-1, 1):
            zj = -4.02 + 0.045 * bi          # centre locks in front, outer locks behind
            ctrl = [(sx * x * 0.88, 40.02, zj),
                    (sx * x * 0.95, 39.30, zj - 0.16),
                    (sx * x * 1.00, 38.45, zj - 0.26),
                    (sx * x * 1.03, 37.50, zj - 0.32),
                    (sx * x * 1.04, ytip, zj - 0.36)]
            cubes += make_strand("front_h1", ctrl, 7, w0, w0 * 0.55, 0.50, (0, 0, 1), 0.26, base_tier=btier)"""),

# centre wisps: shorter, in front, tapered
("""        ctrl = [(sx * 0.12, 40.08, -3.76), (sx * 0.45, 39.20, -4.02),
                (sx * 0.70, 37.90, -4.16), (sx * 0.80, 36.55, -4.22)]
        cubes += make_strand("front_h1", ctrl, 6, 0.72, 0.50, 0.48, (0, 0, 1), 0.26, base_tier=3)""",
 """        ctrl = [(sx * 0.10, 40.08, -4.06), (sx * 0.42, 39.20, -4.14),
                (sx * 0.66, 37.90, -4.20), (sx * 0.76, 36.28, -4.24)]
        cubes += make_strand("front_h1", ctrl, 6, 0.76, 0.44, 0.46, (0, 0, 1), 0.26, base_tier=3)"""),
]
for a, b in pairs:
    if a not in s:
        print("MISSING:", a.splitlines()[0]); sys.exit(1)
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8").write(s)
print("patched ok")
