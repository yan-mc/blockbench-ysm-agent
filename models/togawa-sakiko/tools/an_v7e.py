import json, math
P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
d = json.load(open(P, encoding="utf-8"))
bones = {b["name"]: b for b in d["minecraft:geometry"][0]["bones"]}

def rotm(rx, ry, rz):
    rx, ry, rz = [math.radians(v) for v in (rx, ry, rz)]
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    Rx = [[1,0,0],[0,cx,-sx],[0,sx,cx]]
    Ry = [[cy,0,sy],[0,1,0],[-sy,0,cy]]
    Rz = [[cz,-sz,0],[sz,cz,0],[0,0,1]]
    def mm(a,b): return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mm(mm(Rx,Ry),Rz)

def corners(c):
    o, s = c["origin"], c["size"]
    p = c.get("pivot", o)
    R = rotm(*c.get("rotation",[0,0,0]))
    pts=[]
    for dx in (0,s[0]):
        for dy in (0,s[1]):
            for dz in (0,s[2]):
                v=[dx, dy, dz]
                w=[p[i]+sum(R[i][j]*v[j] for j in range(3)) for i in range(3)]
                pts.append(w)
    return pts

def aabb(c):
    pts=corners(c)
    return [min(p[i] for p in pts) for i in range(3)]+[max(p[i] for p in pts) for i in range(3)]

def stats(name):
    cs=bones[name]["cubes"]
    bb=[aabb(c) for c in cs]
    lo=[min(b[i] for b in bb) for i in range(3)]
    hi=[max(b[i+3] for b in bb) for i in range(3)]
    sizes=[[round(c["size"][i],2) for i in range(3)] for c in cs]
    print(f"== {name}: {len(cs)} cubes  AABB {[round(v,2) for v in lo]} .. {[round(v,2) for v in hi]}")
    from collections import Counter
    print("  sizes:", Counter(tuple(s) for s in sizes).most_common(8))
    rots=Counter(tuple(round(v,1) for v in c.get("rotation",[0,0,0])) for c in cs)
    print("  rots:", rots.most_common(10))
    return cs, bb

for n in ("Head","HairCap","front_h1","corner_h1","HairBack","hl_side","TwinTail_L","Ribbon","HairBow_R"):
    if n in bones: stats(n)

# top-down map of HairCap: which cells have coverage by cubes whose top y >= 40
print("\n== HairCap top-down occupancy (x right, z down), y range per cell")
cs = bones["HairCap"]["cubes"]
bb=[aabb(c) for c in cs]
for zt in [round(v,1) for v in [i*0.5 for i in range(-16,17)]]:
    row=""
    for xt in [i*0.5 for i in range(-16,17)]:
        hs=[b[4] for b in bb if b[0]-0.001<=xt<b[3]+0.001 and b[2]-0.001<=zt<b[5]+0.001]
        if hs:
            row += "0123456789ABCDEFGHIJ"[min(19,int(max(hs)-35))]
        else:
            row += "."
    print(f"z={zt:6.1f} {row}")
