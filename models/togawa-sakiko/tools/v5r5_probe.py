import json

P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
d = json.load(open(P, encoding="utf-8"))
g = d["minecraft:geometry"][0]
print("geom keys:", list(g.keys()))
print("description:", json.dumps(g.get("description"), ensure_ascii=False)[:600])
bones = g["bones"]
print("bones:", len(bones))
b0 = [b for b in bones if b.get("name") == "Cape"][0]
print("bone keys:", list(b0.keys()))
c0 = b0["cubes"][0]
print("cube keys:", list(c0.keys()))
print("cube sample:", json.dumps(c0, ensure_ascii=False)[:600])

def bbox(cubes):
    xs, ys, zs = [], [], []
    for c in cubes:
        o = c.get("origin", [0, 0, 0]); s = c.get("size", [0, 0, 0])
        for i, arr in enumerate((xs, ys, zs)):
            arr.append(o[i]); arr.append(o[i] + s[i])
    return ([min(xs), max(xs)], [min(ys), max(ys)], [min(zs), max(zs)])

print("\n== per-bone ==")
for b in bones:
    cs = b.get("cubes") or []
    if not cs:
        continue
    bb = bbox(cs)
    print(f"{b.get('name'):20s} n={len(cs):4d} x={bb[0][0]:7.2f}..{bb[0][1]:7.2f} y={bb[1][0]:7.2f}..{bb[1][1]:7.2f} z={bb[2][0]:7.2f}..{bb[2][1]:7.2f}")

print("\n== cape cubes ==")
for b in bones:
    if b.get("name") in ("Cape", "CapeLow"):
        print("--", b["name"], "pivot", b.get("pivot"), "parent", b.get("parent"), "rot", b.get("rotation"))
        for c in b["cubes"]:
            print("   ", json.dumps({k: c.get(k) for k in ("origin", "size", "pivot", "rotation", "uv", "inflate") if k in c}, ensure_ascii=False))
