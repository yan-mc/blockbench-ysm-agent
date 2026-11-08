# -*- coding: utf-8 -*-
"""v7d pass 3: close the crown corners and the jaw-side band."""
import io, sys

p = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\tools\v7d_gen.py"
s = io.open(p, encoding="utf-8").read()

pairs = [
("""              (36.65, 0.995, 0.992), (35.50, 0.972, 0.968), (34.25, 0.940, 0.935)]""",
 """              (36.65, 0.995, 0.992), (35.50, 0.972, 0.968), (34.05, 0.940, 0.935)]"""),
("""    cubes.append(Cube(bone, (0.0, 32.92, 3.00), (6.60, 1.80, 0.55), R, SWATCH[1]))""",
 """    cubes.append(Cube(bone, (0.0, 32.92, 3.00), (7.00, 1.80, 0.55), R, SWATCH[1]))
    # crown corner caps: the box skull has sharp top corners the dome cannot reach
    Rc = frame((0, 0, 1), (0, 1, 0))
    for sx in (-1, 1):
        for sz in (-1, 1):
            cubes.append(Cube(bone, (sx * 3.28, 40.30, sz * 3.28),
                              (2.50, 2.50, 0.52), Rc, SWATCH[3]))"""),
]
for a, b in pairs:
    if a not in s:
        print("MISSING:", a.splitlines()[0]); sys.exit(1)
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8").write(s)
print("patched ok")
