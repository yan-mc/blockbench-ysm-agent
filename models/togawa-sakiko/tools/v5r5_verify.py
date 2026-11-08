import json
from PIL import Image
from collections import Counter

P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
T = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\textures\default.png"
d = json.load(open(P, encoding="utf-8"))
g = d["minecraft:geometry"][0]
bones = g["bones"]
cubes = sum(len(b.get("cubes") or []) for b in bones)
print("bones:", len(bones), "cubes:", cubes, "tex:", g["description"]["texture_width"], g["description"]["texture_height"])

# any UV rect overlapping the new swatch area
over = []
for b in bones:
    for c in b.get("cubes") or []:
        uvd = c.get("uv") or {}
        if not isinstance(uvd, dict):
            continue
        for face, f in uvd.items():
            uv = f.get("uv"); sz = f.get("uv_size") or [0, 0]
            x, y = uv[0], uv[1]; w, h = abs(sz[0]), abs(sz[1])
            if x < 316 and x + w > 300 and y < 486 and y + h > 470:
                over.append((b["name"], face, x, y, w, h))
print("uv rects overlapping new swatch:", len(over), over[:6])

# trail cubes
for b in bones:
    if b["name"] in ("Cape", "CapeLow"):
        print(b["name"], "cubes:", len(b.get("cubes") or []))
        for c in b.get("cubes") or []:
            o = c["origin"]; s = c["size"]
            print("   origin", o, "size", s, "uv_n", c["uv"]["north"])

# sanity: no NaN / zero size
bad = 0
for b in bones:
    for c in b.get("cubes") or []:
        for v in c["origin"] + c["size"]:
            if v != v:
                bad += 1
        if min(c["size"]) <= 0:
            bad += 1
print("bad cubes:", bad)

im = Image.open(T).convert("RGBA")
print("swatch pixel (300,470):", im.getpixel((300, 470)), "(302,473):", im.getpixel((302, 473)))
print("max alpha in swatch:", max(im.getpixel((x, y))[3] for x in range(300, 316) for y in range(470, 486)))
