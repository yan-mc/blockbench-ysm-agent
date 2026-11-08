import json, math
P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
d = json.load(open(P, encoding="utf-8"))
g = d["minecraft:geometry"][0]
bones = g["bones"]
def Rmat(r):
    a,b,c = [math.radians(v) for v in r]
    ca,sa=math.cos(a),math.sin(a); cb,sb=math.cos(b),math.sin(b); cc,sc=math.cos(c),math.sin(c)
    return [[cb*cc,-cb*sc,sb],[ca*sc+sa*sb*cc,ca*cc-sa*sb*sc,-sa*cb],[sa*sc-ca*sb*cc,sa*cc+ca*sb*sc,ca*cb]]
def wpts(c):
    o=c["origin"]; s=c["size"]; r=c.get("rotation",[0,0,0])
    p=c.get("pivot",[o[0]+s[0]/2,o[1]+s[1]/2,o[2]+s[2]/2]); M=Rmat(r); out=[]
    for dx in (0,s[0]):
        for dy in (0,s[1]):
            for dz in (0,s[2]):
                v=[o[0]+dx-p[0],o[1]+dy-p[1],o[2]+dz-p[2]]
                out.append([sum(M[i][j]*v[j] for j in range(3))+p[i] for i in range(3)])
    return out
for bn in ("LeftArm","LeftForeArm","LeftHand","RightArm","RightForeArm","RightHand"):
    b=next(x for x in bones if x["name"]==bn)
    lo=[9,99,9]; hi=[-9,-99,-9]
    for c in b.get("cubes",[]):
        for p in wpts(c):
            for i in range(3):
                lo[i]=min(lo[i],p[i]); hi[i]=max(hi[i],p[i])
    print(bn,[round(v,2) for v in lo],[round(v,2) for v in hi])
