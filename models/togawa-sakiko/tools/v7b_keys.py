import json
P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
d = json.load(open(P, encoding="utf-8"))
g = d["minecraft:geometry"][0]
bones = g["bones"]
names = {"Skirt","RightSkirt","LeftSkirt","FrontSkirt","BackSkirt"}
allkeys=set()
for b in bones:
    if b["name"] in names:
        print(b["name"], "bone keys:", list(b.keys()))
        for c in b["cubes"][:3]:
            allkeys.update(c.keys())
            print("  cube keys:", list(c.keys()), c)
        break
print("all cube keys:", allkeys)
from collections import Counter
tex = Counter()
for b in bones:
    for c in b.get("cubes", []):
        tex[c.get("texture")] += 1
print("texture field counts:", tex)
# print uv->texture mapping for skirt
for b in bones:
    if b["name"] in names:
        cnt = Counter()
        for c in b.get("cubes", []):
            cnt[(c.get("texture"), tuple(c.get("uv",[])))] += 1
        print(b["name"], "texture/uv:", sorted(cnt.items())[:40])
