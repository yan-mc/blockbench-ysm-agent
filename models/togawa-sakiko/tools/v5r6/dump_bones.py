import json, sys
from collections import OrderedDict

PACK = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack"
with open(PACK + r"\models\main.json", encoding="utf-8") as f:
    doc = json.load(f)

geo = doc["minecraft:geometry"][0]
bones = geo["bones"]
print("format", doc.get("format_version"), "bones", len(bones))

tot = 0
rows = []
for b in bones:
    n = len(b.get("cubes", []))
    tot += n
    rows.append((b["name"], n, b.get("parent"), b.get("pivot")))
print("total cubes", tot)

def bbox(cubes):
    if not cubes:
        return None
    lo = [1e9]*3; hi = [-1e9]*3
    for c in cubes:
        o = c["origin"]; s = c["size"]
        for i in range(3):
            lo[i] = min(lo[i], o[i]); hi[i] = max(hi[i], o[i]+s[i])
    return [round(lo[i],2) for i in range(3)], [round(hi[i],2) for i in range(3)]

print("\n== all bones (name, cubes, parent)")
for name, n, parent, piv in rows:
    print(f"{name:24s} {n:4d}  parent={parent}")

print("\n== focus bones")
for key in ["Cape", "CapeLow", "Skirt", "Skirt"]:
    for b in bones:
        if b["name"] == key:
            print(key, "cubes", len(b.get("cubes", [])), "pivot", b.get("pivot"), "bbox", bbox(b.get("cubes", [])))
            for c in b.get("cubes", [])[:40]:
                print("   ", c.get("origin"), c.get("size"), c.get("rotation"), c.get("uv"))
