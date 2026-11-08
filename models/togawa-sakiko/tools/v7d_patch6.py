# -*- coding: utf-8 -*-
import io, sys
p = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\tools\v7d_gen.py"
s = io.open(p, encoding="utf-8").read()
pairs = [
("""              (36.65, 0.995, 0.992), (35.50, 0.972, 0.968), (34.00, 0.940, 0.935)]""",
 """              (36.65, 0.995, 0.992), (35.50, 0.972, 0.968), (33.92, 0.940, 0.935)]"""),
("""                yy = y - (0.28 if ti % 3 else 0.0)
                hh = 1.72""",
 """                yy = y - (0.28 if ti % 3 else 0.0)
                hh = 1.86"""),
("""                (4.05, 34.70, -3.28, 0.90, 1.75, 0.50)]):""",
 """                (4.02, 34.35, -3.40, 0.95, 2.30, 0.50)]):"""),
]
for a, b in pairs:
    if a not in s:
        print("MISSING:", a.splitlines()[0]); sys.exit(1)
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8").write(s)
print("patched ok")
