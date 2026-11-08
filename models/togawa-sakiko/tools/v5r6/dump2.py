import json
from collections import Counter

PACK = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack"
doc = json.load(open(PACK + r"\models\main.json", encoding="utf-8"))
geo = doc["minecraft:geometry"][0]
bones = {b["name"]: b for b in geo["bones"]}

def bbox(name):
    cs = bones[name].get("cubes", [])
    if not cs: return None
    lo=[1e9]*3; hi=[-1e9]*3
    for c in cs:
        o=c["origin"]; s=c["size"]
        for i in range(3):
            lo[i]=min(lo[i],o[i]); hi[i]=max(hi[i],o[i]+s[i])
    return [round(v,2) for v in lo],[round(v,2) for v in hi]

for n in ["Head","Hair","HairBack","UpperBody","Collar","Breast","BackSkirt","FrontSkirt","LeftSkirt","RightSkirt",
          "LeftLeg","RightLeg","LeftLowerLeg","RightLowerLeg","LeftFoot","RightFoot","Horn_L","LeftArm","LeftForeArm"]:
    print(f"{n:14s} pivot={bones[n].get('pivot')} bbox={bbox(n)}")

print("\n=== BackSkirt cubes (all)")
for c in bones["BackSkirt"]["cubes"]:
    print("  o=",c["origin"],"s=",c["size"],"rot=",c.get("rotation"),"uv=",list(c["uv"].values())[0] if isinstance(c.get("uv"),dict) else c.get("uv"), "inflate=",c.get("inflate"))

print("\n=== LeftSkirt first 12")
for c in bones["LeftSkirt"]["cubes"][:12]:
    print("  o=",c["origin"],"s=",c["size"],"rot=",c.get("rotation"),"uv=",c.get("uv"))
print("\n=== RightSkirt first 6")
for c in bones["RightSkirt"]["cubes"][:6]:
    print("  o=",c["origin"],"s=",c["size"],"rot=",c.get("rotation"),"uv=",c.get("uv"))
print("\n=== FrontSkirt first 6")
for c in bones["FrontSkirt"]["cubes"][:6]:
    print("  o=",c["origin"],"s=",c["size"],"rot=",c.get("rotation"),"uv=",c.get("uv"))

# uv palette counts
cnt = Counter()
for b in geo["bones"]:
    for c in b.get("cubes", []):
        uv = c.get("uv")
        if isinstance(uv, dict):
            faces = uv.get("faces") if "faces" in uv else None
            if faces:
                pass
            else:
                for f, v in uv.items():
                    if isinstance(v, dict) and "uv" in v:
                        cnt[(tuple(v["uv"]), tuple(v.get("uv_size") or []))] += 1
print("\n=== top uv swatches")
for k, v in cnt.most_common(30):
    print(v, k)
