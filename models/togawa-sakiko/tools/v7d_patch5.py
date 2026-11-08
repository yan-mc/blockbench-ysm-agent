# -*- coding: utf-8 -*-
import io, sys
p = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\tools\v7d_gen.py"
s = io.open(p, encoding="utf-8").read()
pairs = [
("""              (36.65, 0.995, 0.992), (35.50, 0.972, 0.968), (34.05, 0.940, 0.935)]""",
 """              (36.65, 0.995, 0.992), (35.50, 0.972, 0.968), (34.00, 0.940, 0.935)]"""),
("""            yy = y
            if li == len(levels) - 1:      # ragged bottom edge instead of a bob-cut line
                yy = y - (0.34 if ti % 3 else 0.0) + (0.18 if ti % 4 == 1 else 0.0)
            R = frame((0.0, 1.0, 0.0), nrm)
            cubes.append(Cube(bone, (x, yy, z), (perim / K * 1.42, 1.48, 0.46),
                              R, SWATCH[3 if y > 38.9 else (3 if y > 36.6 else 2)]))""",
 """            yy = y
            hh = 1.48
            if li == len(levels) - 1:      # ragged bottom edge instead of a bob-cut line
                yy = y - (0.28 if ti % 3 else 0.0)
                hh = 1.72
            R = frame((0.0, 1.0, 0.0), nrm)
            cubes.append(Cube(bone, (x, yy, z), (perim / K * 1.42, hh, 0.46),
                              R, SWATCH[3 if y > 38.9 else (3 if y > 36.6 else 2)]))"""),
]
for a, b in pairs:
    if a not in s:
        print("MISSING:", a.splitlines()[0]); sys.exit(1)
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8").write(s)
print("patched ok")
