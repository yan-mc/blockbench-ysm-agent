import json, math
P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
d = json.load(open(P, encoding="utf-8"))
g = d["minecraft:geometry"][0]
bones = g["bones"]
def rotmat(r):
    a,b,c = [math.radians(v) for v in r]
    ca,sa = math.cos(a), math.sin(a); cb,sb = math.cos(b), math.sin(b); cc,sc = math.cos(c), math.sin(c)
    return [[cb*cc, -cb*sc, sb],[ca*sc+sa*sb*cc, ca*cc-sa*sb*sc, -sa*cb],[sa*sc-ca*sb*cc, sa*cc+ca*sb*sc, ca*cb]]
def corners(c):
    o=c["origin"]; s=c["size"]; r=c.get("rotation",[0,0,0]); p=c.get("pivot",[o[0]+s[0]/2,o[1]+s[1]/2,o[2]+s[2]/2])
    M=rotmat(r); pts=[]
    for dx in (0,s[0]):
        for dy in (0,s[1]):
            for dz in (0,s[2]):
                v=[o[0]+dx-p[0],o[1]+dy-p[1],o[2]+dz-p[2]]
                w=[sum(M[i][j]*v[j] for j in range(3)) for i in range(3)]
                pts.append([w[0]+p[0],w[1]+p[1],w[2]+p[2]])
    return pts
def slice_bone(bn, y):
    b=next(x for x in bones if x["name"]==bn)
    lo=[9,9]; hi=[-9,-9]; cnt=0
    for c in b.get("cubes",[]):
        pts=corners(c); ys=[p[1] for p in pts]
        if not (min(ys) <= y <= max(ys)): continue
        # approximate: include all corners at that y range -> use bbox of cube
        xs=[p[0] for p in pts]; zs=[p[2] for p in pts]
        lo[0]=min(lo[0],min(xs)); lo[1]=min(lo[1],min(zs)); hi[0]=max(hi[0],max(xs)); hi[1]=max(hi[1],max(zs)); cnt+=1
    return cnt, [round(v,2) for v in lo], [round(v,2) for v in hi]
for y in (21.6, 22.2, 22.8, 23.2, 23.6, 23.85, 24.1):
    print("y=",y, "UpperBody", slice_bone("UpperBody",y))
print()
# list UpperBody cubes near corset bottom (y 20.5-22.5), sorted by y
b=next(x for x in bones if x["name"]=="UpperBody")
rows=[]
for c in b.get("cubes",[]):
    pts=corners(c); ys=[p[1] for p in pts]
    if max(ys) < 20.5 or min(ys) > 24.5: continue
    rows.append((round(min(ys),2), round(max(ys),2), [round(v,2) for v in c["origin"]], [round(v,2) for v in c["size"]], c.get("rotation"), c.get("uv")))
rows.sort()
for r in rows: print(r)
