import json, math
P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
d = json.load(open(P, encoding="utf-8"))
g = d["minecraft:geometry"][0]
bones = g["bones"]

def rotmat(r):
    a,b,c = [math.radians(v) for v in r]
    ca,sa = math.cos(a), math.sin(a); cb,sb = math.cos(b), math.sin(b); cc,sc = math.cos(c), math.sin(c)
    # R = Rx*Ry*Rz
    return [
      [cb*cc, -cb*sc, sb],
      [ca*sc+sa*sb*cc, ca*cc-sa*sb*sc, -sa*cb],
      [sa*sc-ca*sb*cc, sa*cc+ca*sb*sc, ca*cb]]

def corners(c):
    o=c["origin"]; s=c["size"]; r=c.get("rotation",[0,0,0]); p=c.get("pivot",[o[0]+s[0]/2,o[1]+s[1]/2,o[2]+s[2]/2])
    M=rotmat(r)
    pts=[]
    for dx in (0,s[0]):
        for dy in (0,s[1]):
            for dz in (0,s[2]):
                v=[o[0]+dx-p[0], o[1]+dy-p[1], o[2]+dz-p[2]]
                w=[sum(M[i][j]*v[j] for j in range(3)) for i in range(3)]
                pts.append([w[0]+p[0], w[1]+p[1], w[2]+p[2]])
    return pts

# torso near waist: UpperBody and DownBody cubes; find extents in y 22..25
for bn in ("UpperBody","DownBody","Breast"):
    b = next((x for x in bones if x["name"]==bn), None)
    if not b: continue
    lo=[9,9,9]; hi=[-9,-9,-9]
    cnt=0
    for c in b.get("cubes",[]):
        pts=corners(c)
        ys=[p[1] for p in pts]
        if max(ys) < 22 or min(ys) > 26: continue
        cnt+=1
        for p in pts:
            for i in range(3):
                lo[i]=min(lo[i],p[i]); hi[i]=max(hi[i],p[i])
    print(bn, "cubes in y22-26:", cnt, "bbox", [round(v,2) for v in lo], [round(v,2) for v in hi])

# skirt current world bbox per bone
for bn in ("Skirt","RightSkirt","LeftSkirt","FrontSkirt","BackSkirt"):
    b = next(x for x in bones if x["name"]==bn)
    lo=[9,99,9]; hi=[-9,-99,-9]
    for c in b.get("cubes",[]):
        for p in corners(c):
            for i in range(3):
                lo[i]=min(lo[i],p[i]); hi[i]=max(hi[i],p[i])
    print(bn, "bbox", [round(v,2) for v in lo], [round(v,2) for v in hi])

# torso full bbox and head
for bn in ("UpperBody","Head","LeftLeg","RightLeg"):
    b = next(x for x in bones if x["name"]==bn)
    lo=[9,99,9]; hi=[-9,-99,-9]
    for c in b.get("cubes",[]):
        for p in corners(c):
            for i in range(3):
                lo[i]=min(lo[i],p[i]); hi[i]=max(hi[i],p[i])
    print(bn, "FULL bbox", [round(v,2) for v in lo], [round(v,2) for v in hi])
