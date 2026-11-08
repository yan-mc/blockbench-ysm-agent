"""Apply planned hair taper to preview json (match by old origin) then dump preview2."""
import json, copy

ROOT = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
OUT = ROOT + r"\artifacts\v5\r6"
doc = json.load(open(OUT + r"\preview_main.json", encoding="utf-8"))
bones = {b["name"]: b for b in doc["minecraft:geometry"][0]["bones"]}

spec = [
    (-2.18, 15.60, 5.56, 2.6, 0.0, 5.56),
    (3.02, 16.35, 5.18, 2.3, 0.0, 5.18),
    (-2.09, 16.42, 5.27, 2.1, 0.0, 5.27),
    (2.59, 17.17, 4.89, 1.7, 0.0, 4.89),
    (-0.28, 18.04, 4.80, 1.3, 0.0, 4.80),
    (-2.10, 18.71, 4.52, 1.1, 0.0, 4.52),
    (-3.46, 18.75, 5.17, 1.3, 0.0, 5.17),
    (-0.70, 18.86, 4.51, 1.1, 0.0, 4.51),
    (-2.00, 19.53, 4.23, 0.9, 0.0, 4.23),
    (-3.37, 19.57, 4.88, 1.0, 0.0, 4.88),
    (4.63, 19.88, 5.33, 0.9, -0.9, 5.33),
    (2.91, 20.29, 4.86, 0.7, 0.0, 4.86),
    (-3.02, 20.22, 6.21, 0.8, 0.0, 6.21),
    (2.28, 20.74, 5.90, 0.6, 0.0, 5.90),
    (-4.95, 18.90, 5.60, 1.0, 1.2, 5.60),
    (4.10, 18.90, 5.60, 1.0, -1.2, 5.60),
    (-5.20, 19.60, 4.55, 0.8, 1.0, 4.55),
    (4.30, 19.60, 4.55, 0.8, -1.0, 4.55),
    (4.45, 20.13, 4.46, 0.6, -0.9, 4.46),
    (-4.95, 20.60, 5.90, 0.5, 0.8, 5.90),
    (4.10, 20.60, 5.90, 0.5, -0.8, 5.90),
]

cubes = bones["HairBack"]["cubes"]
used = set()
for (x, y, z, dy, dx, zz) in spec:
    hits = [i for i, c in enumerate(cubes)
            if i not in used and abs(c["origin"][0] - x) < 0.05 and abs(c["origin"][1] - y) < 0.05 and abs(c["origin"][2] - z) < 0.05]
    assert len(hits) == 1, (x, y, z, len(hits))
    i = hits[0]
    used.add(i)
    c = cubes[i]
    c["origin"] = [round(c["origin"][0] + dx, 4), round(c["origin"][1] + dy, 4), c["origin"][2]]
    if "pivot" in c:
        c["pivot"] = [round(c["pivot"][0] + dx, 4), round(c["pivot"][1] + dy, 4), c["pivot"][2]]

json.dump(doc, open(OUT + r"\preview2_main.json", "w", encoding="utf-8"), ensure_ascii=False)
print("edited", len(used))
