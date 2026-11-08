import json
from PIL import Image
from collections import Counter

P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
T = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\textures\default.png"
d = json.load(open(P, encoding="utf-8"))
bones = d["minecraft:geometry"][0]["bones"]
im = Image.open(T).convert("RGBA")
W = H = 512


def face_color(f):
    uv = f.get("uv")
    sz = f.get("uv_size") or [1, 1]
    x, y = int(uv[0]), int(uv[1])
    w, h = max(1, int(abs(sz[0]))), max(1, int(abs(sz[1])))
    reg = im.crop((x, y, min(W, x + w), min(H, y + h)))
    px = [p for p in reg.getdata() if p[3] > 40]
    if not px:
        return None
    return Counter(px).most_common(1)[0][0]


def hexs(c):
    return "#%02x%02x%02x a%d" % c if c else "none"


def cube_color(c):
    uvs = c.get("uv") or {}
    if not isinstance(uvs, dict):
        return None
    cols = []
    for k in ("north", "south", "up", "down", "east", "west"):
        if k in uvs:
            cc = face_color(uvs[k])
            if cc:
                cols.append(cc)
    if not cols:
        return None
    return Counter(cols).most_common(1)[0][0]


order = ["Skirt", "BackSkirt", "RightSkirt", "LeftSkirt", "FrontSkirt", "Cape", "CapeLow"]
for b in bones:
    if b["name"] not in order:
        continue
    print("\n====", b["name"], "n=", len(b.get("cubes") or []), "pivot", b.get("pivot"))
    for i, c in enumerate(b["cubes"]):
        col = cube_color(c)
        o = c["origin"]; s = c["size"]
        print(f"{i:3d} o=({o[0]:6.2f},{o[1]:6.2f},{o[2]:6.2f}) s=({s[0]:5.2f},{s[1]:5.2f},{s[2]:5.2f}) rot={c.get('rotation')} col={hexs(col)}")
