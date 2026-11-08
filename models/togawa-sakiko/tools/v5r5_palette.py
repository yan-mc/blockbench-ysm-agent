import json
from PIL import Image
from collections import Counter

P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
T = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\textures\default.png"
d = json.load(open(P, encoding="utf-8"))
bones = d["minecraft:geometry"][0]["bones"]
im = Image.open(T).convert("RGBA")
W = H = 512

sw = {}
for b in bones:
    for c in b.get("cubes") or []:
        uvd = c.get("uv") or {}
        if isinstance(uvd, list):
            print("LIST-UV cube in", b["name"], uvd)
            continue
        for f in uvd.values():
            uv = f.get("uv")
            if not uv:
                continue
            k = (int(uv[0]), int(uv[1]))
            sw.setdefault(k, Counter())[im.getpixel(k)] += 1

print("swatch count:", len(sw))
for k in sorted(sw):
    col = sw[k].most_common(1)[0][0]
    print(f"uv=({k[0]:3d},{k[1]:3d}) rgba={col} uses={sum(sw[k].values())}")

# candidate free spots
for (x, y) in [(500, 300), (300, 470), (470, 470), (430, 300)]:
    print("free?", (x, y), im.getpixel((x, y)))
