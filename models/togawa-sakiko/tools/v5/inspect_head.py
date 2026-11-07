# -*- coding: utf-8 -*-
import json, sys

d = json.load(open(r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json", encoding="utf-8"))
g = d["minecraft:geometry"][0]
B = {b["name"]: b for b in g["bones"]}
kids = {}
for b in g["bones"]:
    kids.setdefault(b.get("parent"), []).append(b["name"])


def bbox(name):
    acc = []
    def walk(n):
        b = B[n]
        for c in b.get("cubes", []):
            o, s = c["origin"], c["size"]
            acc.append((o[0], o[1], o[2], o[0] + s[0], o[1] + s[1], o[2] + s[2]))
        for k in kids.get(n, []):
            walk(k)
    walk(name)
    if not acc:
        return None
    return (min(a[0] for a in acc), min(a[1] for a in acc), min(a[2] for a in acc),
            max(a[3] for a in acc), max(a[4] for a in acc), max(a[5] for a in acc))


for n in ["Head", "Hair", "HairBack", "front_h1", "corner_h1", "hl_side", "TwinTail_L",
          "TwinTail_R", "Ribbon", "Horn_L", "Horn_R"]:
    bb = bbox(n)
    print(n, [round(v, 2) for v in bb] if bb else None, len(B[n].get("cubes", [])))

print("\n--- Head cubes")
for c in B["Head"]["cubes"]:
    print([round(v, 2) for v in c["origin"]], [round(v, 2) for v in c["size"]], c.get("name"))

print("\n--- Hair cubes")
for c in B["Hair"]["cubes"]:
    print([round(v, 2) for v in c["origin"]], [round(v, 2) for v in c["size"]], c.get("name"), c.get("rotation"))

print("\n--- front_h1 cubes")
for c in B["front_h1"]["cubes"]:
    print([round(v, 2) for v in c["origin"]], [round(v, 2) for v in c["size"]], c.get("name"), c.get("rotation"))

print("\n--- Horn_L cubes")
for c in B["Horn_L"]["cubes"]:
    print([round(v, 2) for v in c["origin"]], [round(v, 2) for v in c["size"]], c.get("name"), c.get("rotation"), c.get("pivot"))
