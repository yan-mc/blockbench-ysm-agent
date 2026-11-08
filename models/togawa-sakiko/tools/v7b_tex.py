import json
from PIL import Image
base = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack"
for name in ["default.png", "blue.png"]:
    im = Image.open(base + r"\textures\\" + name).convert("RGBA")
    print("==", name, im.size)
    pts = [(226,18),(258,18),(200,18),(230,40),(270,40),(100,230),(116,230),(132,230),(150,230),(164,230)]
    for p in pts:
        print("  ", p, im.getpixel(p))
    # find large opaque uniform-ish regions: sample grid and cluster colors of opaque pixels
    W,H = im.size
    px = im.load()
    from collections import Counter
    c = Counter()
    for y in range(0,H,2):
        for x in range(0,W,2):
            r,g,b,a = px[x,y]
            if a > 200:
                c[(r//16*16,g//16*16,b//16*16)] += 1
    print("  top colors:", c.most_common(12))
