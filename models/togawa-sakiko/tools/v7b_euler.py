import json, math
P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
d = json.load(open(P, encoding="utf-8"))
g = d["minecraft:geometry"][0]
bones = g["bones"]
sk = next(b for b in bones if b["name"]=="Skirt")

def R_xyz(a,b,c):
    a,b,c=[math.radians(v) for v in (a,b,c)]
    ca,sa=math.cos(a),math.sin(a); cb,sb=math.cos(b),math.sin(b); cc,sc=math.cos(c),math.sin(c)
    return [[cb*cc,-cb*sc,sb],[ca*sc+sa*sb*cc,ca*cc-sa*sb*sc,-sa*cb],[sa*sc-ca*sb*cc,sa*cc+ca*sb*sc,ca*cb]]
def R_zyx(a,b,c):
    # R = Rz*Ry*Rx
    a,b,c=[math.radians(v) for v in (a,b,c)]
    ca,sa=math.cos(a),math.sin(a); cb,sb=math.cos(b),math.sin(b); cc,sc=math.cos(c),math.sin(c)
    Rx=[[1,0,0],[0,ca,-sa],[0,sa,ca]]
    Ry=[[cb,0,sb],[0,1,0],[-sb,0,cb]]
    Rz=[[cc,-sc,0],[sc,cc,0],[0,0,1]]
    def mul(A,B): return [[sum(A[i][k]*B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mul(mul(Rz,Ry),Rx)

for idx,c in enumerate(sk["cubes"]):
    r=c.get("rotation")
    if not r: continue
    for name,f in (("XYZ",R_xyz),("ZYX",R_zyx)):
        M=f(*r)
        cols=[[M[i][j] for i in range(3)] for j in range(3)]
        print(idx, name, "x:", [round(v,2) for v in cols[0]], "y:", [round(v,2) for v in cols[1]], "z:", [round(v,2) for v in cols[2]])
    print()
    if idx>6: break
