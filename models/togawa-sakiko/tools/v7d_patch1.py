# -*- coding: utf-8 -*-
import io, sys

p = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\tools\v7d_gen.py"
s = io.open(p, encoding="utf-8").read()

pairs = [
("""    sd = [dirs[0]]
    for i in range(1, len(dirs)):
        sd.append(norm(lerp(dirs[i - 1], dirs[i], 0.5)))
    sd = [norm(lerp(sd[i], sd[i + 1], 0.35)) if i + 1 < len(sd) else sd[i] for i in range(len(sd))]""",
"""    sd = [dirs[0]]
    for i in range(1, len(dirs)):
        sd.append(norm(lerp(dirs[i - 1], dirs[i], 0.5)))
    for _ in range(3):
        sd = [norm(lerp(sd[i], sd[i + 1], 0.35)) if i + 1 < len(sd) else sd[i] for i in range(len(sd))]"""),

("""        L = math.dist(res[i], res[i + 1]) + overlap""",
"""        L = max(0.45, math.dist(res[i], res[i + 1]) + overlap)"""),

("""            w *= 0.78
            L *= 0.92""",
"""            w *= 0.78
            L = max(0.42, L * 0.95)"""),

("""                    (sx * x * 1.06, 37.25, -4.10),
                    (sx * (x + 0.10), ytip, -4.02)]""",
"""                    (sx * x * 1.05, 37.25, -4.12),
                    (sx * (x + 0.12), ytip, -4.16)]"""),

("""        ctrl = [(sx * 0.10, 40.10, -3.80), (sx * 0.55, 39.10, -4.10),
                (sx * 0.85, 37.60, -4.20), (sx * 0.95, 36.55, -4.12)]""",
"""        ctrl = [(sx * 0.10, 40.10, -3.80), (sx * 0.55, 39.10, -4.10),
                (sx * 0.85, 37.60, -4.20), (sx * 0.95, 36.55, -4.24)]"""),
]
for a, b in pairs:
    if a not in s:
        print("MISSING:", a.splitlines()[0])
        sys.exit(1)
    s = s.replace(a, b)
io.open(p, "w", encoding="utf-8").write(s)
print("patched ok")
