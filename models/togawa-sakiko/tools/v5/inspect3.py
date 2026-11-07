# -*- coding: utf-8 -*-
import json

P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack"
d = json.load(open(P + r"\models\main.json", encoding="utf-8"))
g = d["minecraft:geometry"][0]
B = {b["name"]: b for b in g["bones"]}


def uvkey(c):
    uv = c.get("uv")
    if isinstance(uv, list):
        return "box"
    if isinstance(uv, dict):
        k = uv.get("north")
        if isinstance(k, dict):
            return str(k.get("uv"))
        return str(k)
    return "?"


for name in ["FrontSkirt", "LeftSkirt", "BackSkirt", "Cape", "CapeLow"]:
    print("=== " + name, len(B[name].get("cubes", [])))
    for c in B[name].get("cubes", []):
        o, s = c["origin"], c["size"]
        print("  o=%s s=%s ctr=%s rot=%s uv=%s" % (
            [round(v, 2) for v in o], [round(v, 2) for v in s],
            [round(o[i] + s[i] / 2, 2) for i in range(3)], c.get("rotation"), uvkey(c)))
