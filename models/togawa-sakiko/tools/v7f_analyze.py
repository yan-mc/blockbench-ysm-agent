import json, os, math
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
P = os.path.join(BASE, "pack", "models", "main.json")
BAK = os.path.join(BASE, "artifacts", "v7e", "_presave", "main.json")
cur = json.load(open(P, encoding="utf-8"))
bak = json.load(open(BAK, encoding="utf-8"))
Gc = cur["minecraft:geometry"][0]; Gb = bak["minecraft:geometry"][0]
bc = {b["name"]: b for b in Gc["bones"]}; bb = {b["name"]: b for b in Gb["bones"]}
print("bones", len(Gc["bones"]), "cubes", sum(len(b.get("cubes", [])) for b in Gc["bones"]))
print("bak bones", len(Gb["bones"]), "cubes", sum(len(b.get("cubes", [])) for b in Gb["bones"]))
print("parent map same:", [(b["name"], b.get("parent")) for b in Gc["bones"]] == [(b["name"], b.get("parent")) for b in Gb["bones"]])

def bbox(cs):
    lo = [1e9]*3; hi = [-1e9]*3
    for c in cs:
        o = c["origin"]; s = c["size"]
        for i in range(3):
            lo[i] = min(lo[i], o[i]); hi[i] = max(hi[i], o[i]+s[i])
    return [round(v,2) for v in lo], [round(v,2) for v in hi]

for nm in ("HairCap", "front_h1", "HairBack", "hl_side", "corner_h1", "TwinTail_L", "TwinTail_R", "Head", "AllHead"):
    if nm in bc:
        b = bc[nm]
        cs = b.get("cubes", [])
        print(f"\n== {nm} parent={b.get('parent')} pivot={b.get('pivot')} rot={b.get('rotation')} n={len(cs)}")
        if cs: print("   bbox", bbox(cs))

# HairCap: compare current prefix with bak kept
capc = bc["HairCap"]["cubes"]; capb = bb["HairCap"]["cubes"]
drop = {85, 88, 91, 92, 95, 96, 99}
kept_b = [c for i, c in enumerate(capb) if i not in drop]
print("\nbak HairCap", len(capb), "kept", len(kept_b), "cur", len(capc))
print("cur[:122]==kept_b:", capc[:len(kept_b)] == kept_b)

# distribution of top y among kept (the v7d shell) - grouped by rounded top
tops = sorted(((round(c["origin"][1]+c["size"][1], 2)), i) for i, c in enumerate(kept_b))
print("kept top-y: min", tops[0][0], "max", tops[-1][0])
import collections
hist = collections.Counter(round(t/0.5)*0.5 for t, _ in tops)
print("kept top-y hist(0.5):", dict(sorted(hist.items())))

# v7e added (cur[122:]) top-y
for i, c in enumerate(capc[len(kept_b):]):
    o = c["origin"]; s = c["size"]
    print(f"  add{i:02d} o={[round(v,2) for v in o]} s={[round(v,2) for v in s]} rot={c.get('rotation')} top={round(o[1]+s[1],2)}")
