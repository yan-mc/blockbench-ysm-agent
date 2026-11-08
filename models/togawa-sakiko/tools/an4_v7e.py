import json, math
P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
d = json.load(open(P, encoding="utf-8"))
bones = {b["name"]: b for b in d["minecraft:geometry"][0]["bones"]}

def rotm(rx, ry, rz):
    rx, ry, rz = [math.radians(v) for v in (rx, ry, rz)]
    cx, sx = math.cos(rx), math.sin(rx); cy, sy = math.cos(ry), math.sin(ry); cz, sz = math.cos(rz), math.sin(rz)
    Rx=[[1,0,0],[0,cx,-sx],[0,sx,cx]]; Ry=[[cy,0,sy],[0,1,0],[-sy,0,cy]]; Rz=[[cz,-sz,0],[sz,cz,0],[0,0,1]]
    def mm(a,b): return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mm(mm(Rx,Ry),Rz)
def aabb(c):
    o,s=c["origin"],c["size"]; p=c.get("pivot",o); R=rotm(*c.get("rotation",[0,0,0]))
    pts=[]
    for dx in (0,s[0]):
        for dy in (0,s[1]):
            for dz in (0,s[2]):
                v=[dx,dy,dz]; pts.append([p[i]+sum(R[i][j]*v[j] for j in range(3)) for i in range(3)])
    return [min(q[i] for q in pts) for i in range(3)]+[max(q[i] for q in pts) for i in range(3)]

print("bone symmetry check: mirror each AABB (x->-x), nearest other AABB dist")
for n in ("Head","HairCap","front_h1","HairBack","hl_side","corner_h1","Hair"):
    cs=bones[n]["cubes"]
    if not cs: continue
    bbs=[aabb(c) for c in cs]
    worst=[]
    for i,b in enumerate(bbs):
        m=[-b[3],b[1],b[2],-b[0],b[4],b[5]]
        best=1e9
        for j,c in enumerate(bbs):
            if j==i: continue
            dist=max(abs(m[k]-c[k]) for k in range(6))
            best=min(best,dist)
        worst.append((best,i))
    worst.sort(reverse=True)
    cen=[(min(b[0] for b in bbs)+max(b[3] for b in bbs))/2,(min(b[2] for b in bbs)+max(b[5] for b in bbs))/2]
    print(f"{n}: worst {[(round(w,2),i) for w,i in worst[:6]]} aabb_center x{cen[0]:.2f} z{cen[1]:.2f}")

print("\nHead cubes:")
for i,c in enumerate(bones["Head"]["cubes"]):
    b=aabb(c); print(i,[round(v,2) for v in c["origin"]],[round(v,2) for v in c["size"]],[round(v,1) for v in c.get("rotation",[0,0,0])],"->",[round(v,2) for v in b])
