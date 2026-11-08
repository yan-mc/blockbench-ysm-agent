import json
from PIL import Image
from collections import Counter, defaultdict

P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
T = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\textures\default.png"
d = json.load(open(P, encoding="utf-8"))
bones = d["minecraft:geometry"][0]["bones"]
im = Image.open(T).convert("RGBA")
W = H = 512


def face_color(f):
    uv = f.get("uv"); sz = f.get("uv_size") or [1, 1]
    x, y = int(uv[0]), int(uv[1])
    w, h = max(1, int(abs(sz[0]))), max(1, int(abs(sz[1])))
    reg = im.crop((x, y, min(W, x + w), min(H, y + h)))
    px = [p for p in reg.getdata() if p[3] > 40]
    return Counter(px).most_common(1)[0][0] if px else None


def cube_color(c):
    uvs = c.get("uv") or {}
    cols = [face_color(uvs[k]) for k in ("north", "south", "east", "west") if k in uvs]
    cols = [x for x in cols if x]
    return Counter(cols).most_common(1)[0][0] if cols else None


hb = [b for b in bones if b["name"] == "HairBack"][0]
print("HairBack pivot:", hb.get("pivot"), "parent", hb.get("parent"))
rows = defaultdict(list)
for i, c in enumerate(hb["cubes"]):
    o = c["origin"]; s = c["size"]
    rows[round(o[1] * 2) / 2].append((i, o, s, c.get("rotation"), cube_color(c)))
for y in sorted(rows, reverse=True):
    lst = rows[y]
    xmin = min(o[0] for _, o, _, _, _ in lst); xmax = max(o[0] + s[0] for _, o, s, _, _ in lst)
    zmin = min(o[2] for _, o, _, _, _ in lst); zmax = max(o[2] + s[2] for _, o, s, _, _ in lst)
    cols = Counter(str(col) for *_, col in lst)
    print(f"y={y:6.2f} n={len(lst):3d} x={xmin:6.2f}..{xmax:6.2f} z={zmin:5.2f}..{zmax:5.2f} cols={dict(cols)}")

print("\n== HairBack cubes detail ==")
for i, c in enumerate(hb["cubes"]):
    o = c["origin"]; s = c["size"]
    print(f"{i:3d} o=({o[0]:6.2f},{o[1]:6.2f},{o[2]:6.2f}) s=({s[0]:5.2f},{s[1]:5.2f},{s[2]:5.2f}) rot={c.get('rotation')}")

print("\n== Hair bone detail (y-z) ==")
h = [b for b in bones if b["name"] == "Hair"][0]
for i, c in enumerate(h["cubes"]):
    o = c["origin"]; s = c["size"]
    print(f"{i:3d} o=({o[0]:6.2f},{o[1]:6.2f},{o[2]:6.2f}) s=({s[0]:5.2f},{s[1]:5.2f},{s[2]:5.2f}) rot={c.get('rotation')}")
