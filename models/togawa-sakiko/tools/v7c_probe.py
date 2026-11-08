import json, math, sys, statistics

P = sys.argv[1] if len(sys.argv) > 1 else r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
d = json.load(open(P, encoding="utf-8"))
g = d["minecraft:geometry"][0]
bones = g["bones"]
by = {b["name"]: b for b in bones}
SK = ["Skirt", "RightSkirt", "LeftSkirt", "FrontSkirt", "BackSkirt"]

print("desc", json.dumps(g["description"], ensure_ascii=False))
print("bones", len(bones), "cubes", sum(len(b.get("cubes", [])) for b in bones))
for n in SK:
    b = by.get(n)
    if not b:
        print(n, "MISSING"); continue
    cs = b.get("cubes", [])
    print(f"\n== {n} parent={b.get('parent')} pivot={b.get('pivot')} rot={b.get('rotation')} cubes={len(cs)}")
    if not cs:
        continue
    xs = [c["origin"][0] + c["size"][0] / 2 for c in cs]
    ys = [c["origin"][1] + c["size"][1] / 2 for c in cs]
    zs = [c["origin"][2] + c["size"][2] / 2 for c in cs]
    print("  ctr x %.2f..%.2f mean %.2f | y %.2f..%.2f | z %.2f..%.2f mean %.2f" % (
        min(xs), max(xs), statistics.mean(xs), min(ys), max(ys), min(zs), max(zs), statistics.mean(zs)))
    rx = sorted({round(c.get("rotation", [0, 0, 0])[0], 1) for c in cs})
    ry = sorted({round(c.get("rotation", [0, 0, 0])[1], 1) for c in cs})
    rz = sorted({round(c.get("rotation", [0, 0, 0])[2], 1) for c in cs})
    print("  rotX", rx[:8], "rotY", ry[:8], "rotZ", rz[:8])
    sx = [c["size"][0] for c in cs]; sy = [c["size"][1] for c in cs]; sz = [c["size"][2] for c in cs]
    print("  size x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f" % (min(sx), max(sx), min(sy), max(sy), min(sz), max(sz)))
    piv = {tuple(round(v, 2) for v in c["pivot"]) for c in cs if "pivot" in c}
    print("  distinct pivots", len(piv), list(piv)[:4])
    print("  sample", json.dumps(cs[0], ensure_ascii=False))
    print("  sample2", json.dumps(cs[-1], ensure_ascii=False))

# body reference: torso/hip cubes
for n in ["Body", "UpperBody", "UpBody", "DownBody", "Hip", "LeftLeg", "RightLeg"]:
    b = by.get(n)
    if not b:
        continue
    cs = b.get("cubes", [])
    if not cs:
        print(f"bodyref {n}: no cubes"); continue
    xs = [c["origin"][0] + c["size"][0] / 2 for c in cs]
    zs = [c["origin"][2] + c["size"][2] / 2 for c in cs]
    print(f"bodyref {n}: cubes={len(cs)} x {min(xs):.2f}..{max(xs):.2f} mean {statistics.mean(xs):.2f} | z {min(zs):.2f}..{max(zs):.2f}")

# texture swatch usage of skirt cubes (uv)
uvs = {}
for n in SK:
    b = by.get(n)
    if not b: continue
    for c in b.get("cubes", []):
        u = c.get("uv")
        if isinstance(u, dict):
            key = (u.get("mode"), tuple(u.get("offset", [])) if u.get("offset") else None, u.get("size"))
        else:
            key = str(u)
        uvs[key] = uvs.get(key, 0) + 1
print("\nskirt uv styles:", len(uvs))
for k, v in list(uvs.items())[:8]:
    print("  ", k, v)
