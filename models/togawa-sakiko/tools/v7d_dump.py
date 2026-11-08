import json, sys, math
P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
m = json.load(open(P, encoding="utf-8"))

bones = m["minecraft:geometry"][0]["bones"] if "minecraft:geometry" in m else m["bones"]
if isinstance(bones, list):
    bmap = {b["name"]: b for b in bones}
else:
    bmap = bones

def dump(name, limit=None):
    b = bmap[name]
    out = []
    for i, c in enumerate(b.get("cubes", [])):
        out.append(dict(idx=i, id=c.get("uuid",""), o=c.get("origin"), s=c.get("size"),
                        r=c.get("rotation"), p=c.get("pivot"), inf=c.get("inflate"),
                        uv=c.get("uv")))
    return out

if __name__ == "__main__":
    names = sys.argv[1:] or ["Head", "Hair", "HairBack", "hl_side", "front_h1", "corner_h1", "TwinTail_L", "Ribbon", "HairBow_R"]
    for n in names:
        print("==", n, "pivot", bmap[n].get("pivot"), "rot", bmap[n].get("rotation"), "parent", bmap[n].get("parent"))
        for row in dump(n):
            print(json.dumps(row, ensure_ascii=False))
