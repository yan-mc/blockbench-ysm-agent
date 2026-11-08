# -*- coding: utf-8 -*-
"""v7d pass 5: two side locks per side (let the original TwinTails read as the
outer long locks), layered bang hem instead of a straight fringe."""
import io, sys
p = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\tools\v7d_gen.py"
s = io.open(p, encoding="utf-8").read()

pairs = [
("""    bangs = [(0.40, 36.10, 0.86, 3), (1.10, 36.26, 0.98, 3), (1.78, 36.50, 0.96, 2),
             (2.40, 36.78, 0.84, 3), (2.94, 37.02, 0.72, 2), (3.36, 37.26, 0.58, 3)]""",
 """    bangs = [(0.40, 36.12, 0.86, 3), (1.10, 36.58, 0.98, 1), (1.78, 36.20, 0.96, 3),
             (2.40, 36.72, 0.84, 2), (2.94, 36.34, 0.74, 3), (3.36, 36.92, 0.60, 2)]"""),
("""        side = [
            (3.28, -1.55, 3.66, -1.98, 10.4, 1.18, 0.88, 2),
            (3.92, 0.12, 4.26, 0.44, 12.2, 1.36, 0.98, 1),
            (4.42, 2.30, 4.72, 2.70, 13.6, 1.30, 0.92, 3),
        ]""",
 """        side = [
            (3.30, -1.60, 3.72, -2.05, 10.6, 1.24, 0.92, 2),
            (3.98, 0.05, 4.34, 0.35, 12.6, 1.40, 1.00, 3),
        ]"""),
("""        (4.40, 3.15, 5.10, 4.20, 22.8, 1.85, 1.35, 1),
        (-4.40, 3.15, -5.10, 4.20, 22.8, 1.85, 1.35, 1),""",
 """        (4.15, 3.15, 4.65, 4.10, 22.6, 1.85, 1.35, 1),
        (-4.15, 3.15, -4.65, 4.10, 22.6, 1.85, 1.35, 1),"""),
]
for a, b in pairs:
    if a not in s:
        print("MISSING:", a.splitlines()[0]); sys.exit(1)
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8").write(s)
print("patched ok")
