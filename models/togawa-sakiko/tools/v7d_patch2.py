# -*- coding: utf-8 -*-
import io, sys

p = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\tools\v7d_gen.py"
s = io.open(p, encoding="utf-8").read()

pairs = [
("""        L = max(0.45, math.dist(res[i], res[i + 1]) + overlap)""",
 """        L = max(0.58, math.dist(res[i], res[i + 1]) + overlap)"""),
("""            L = max(0.42, L * 0.95)""",
 """            L = max(0.52, L * 0.95)"""),
("""            cubes += make_strand("front_h1", ctrl, 6, w0, w0 * 0.62, 0.55, (0, 0, 1), 0.22, base_tier=3)""",
 """            cubes += make_strand("front_h1", ctrl, 7, w0, w0 * 0.62, 0.55, (0, 0, 1), 0.26, base_tier=3)"""),
("""        cubes += make_strand("front_h1", ctrl, 5, 0.80, 0.55, 0.50, (0, 0, 1), 0.22, base_tier=3)""",
 """        cubes += make_strand("front_h1", ctrl, 6, 0.80, 0.55, 0.50, (0, 0, 1), 0.26, base_tier=3)"""),
("""                    (sx * x * 1.05, 37.25, -4.12),
                    (sx * (x + 0.12), ytip, -4.16)]""",
 """                    (sx * x * 1.03, 37.25, -4.11),
                    (sx * (x + 0.10), ytip, -4.13)]"""),
]
for a, b in pairs:
    if a not in s:
        print("MISSING:", a.splitlines()[0]); sys.exit(1)
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8").write(s)
print("patched ok")
