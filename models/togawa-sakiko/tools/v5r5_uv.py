import json
from PIL import Image
from collections import Counter

P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
T = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\textures\default.png"
d = json.load(open(P, encoding="utf-8"))
bones = d["minecraft:geometry"][0]["bones"]
im = Image.open(T).convert("RGBA")
W = H = 512

# 1) dump uv dicts of sample cubes
def dump(bone, idxs):
    b = [x for x in bones if x["name"] == bone][0]
    for i in idxs:
        c = b["cubes"][i]
        o = c["origin"]
        print(f"{bone}[{i}] y={o[1]:.2f} uv={json.dumps(c['uv'], separators=(',',':'))}")

print("== HairBack samples ==")
dump("HairBack", [0, 1, 5, 15, 16, 30, 65, 75, 77, 100, 110, 130, 150])
print("\n== BackSkirt black/dark ==")
dump("BackSkirt", [3, 4, 8, 11, 12, 15, 21])
print("\n== RightSkirt samples ==")
dump("RightSkirt", [7, 31, 41])

# 2) free texture space: gather used uv rects
used = bytearray(W * H)
for b in bones:
    for c in b.get("cubes") or []:
        uvs = c.get("uv") or {}
        if not isinstance(uvs, dict):
            continue
        for f in uvs.values():
            uv = f.get("uv"); sz = f.get("uv_size") or [0, 0]
            x, y = int(uv[0]), int(uv[1])
            w, h = int(abs(sz[0])), int(abs(sz[1]))
            for yy in range(max(0, y), min(H, y + h)):
                base = yy * W
                for xx in range(max(0, x), min(W, x + w)):
                    used[base + xx] = 1
print("\nused area:", sum(used), "free:", W * H - sum(used))
# find largest free rectangles in 32x32 blocks
best = []
for by in range(0, H, 32):
    for bx in range(0, W, 32):
        if sum(used[by * W + bx: by * W + bx + 32]) == 0 and all(sum(used[(by + i) * W + bx:(by + i) * W + bx + 32]) == 0 for i in range(32)):
            best.append((bx, by))
print("free 32x32 blocks:", best[:20], "count", len(best))
