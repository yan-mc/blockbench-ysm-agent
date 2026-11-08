import json, sys, math

P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
d = json.load(open(P, encoding="utf-8"))
print("top keys:", list(d.keys()))
geo = d.get("minecraft:geometry")
print("geo count:", len(geo))
g = geo[0]
print("desc:", g.get("description"))
bones = g["bones"]
print("bones:", len(bones), "cubes:", sum(len(b.get("cubes", [])) for b in bones))

skirt_names = {"Skirt", "RightSkirt", "LeftSkirt", "FrontSkirt", "BackSkirt"}
for b in bones:
    if b["name"] in skirt_names:
        print("\n===", b["name"], "pivot", b.get("pivot"), "rot", b.get("rotation"), "cubes", len(b.get("cubes", [])))
        for c in b.get("cubes", []):
            o = c.get("origin"); s = c.get("size"); r = c.get("rotation"); p = c.get("pivot"); inf = c.get("inflate")
            uv = c.get("uv")
            print(f"  o={o} s={s} rot={r} piv={p} inf={inf} uv={uv}")
