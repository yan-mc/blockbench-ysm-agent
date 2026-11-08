import json, math
from collections import Counter, defaultdict
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

def clusters(name, key="x", tol=0.7):
    cubes=bones[name]["cubes"]
    items=[]
    for cu in cubes:
        b=aabb(cu); items.append(((b[0]+b[3])/2,(b[2]+b[5])/2,b,cu))
    items.sort()
    groups=[]; cur=[]
    for it in items:
        if cur and abs(it[0]-cur[-1][0])>tol:
            groups.append(cur); cur=[]
        cur.append(it)
    if cur: groups.append(cur)
    return groups

print("=== front_h1 columns ===")
g=clusters("front_h1")
for i,grp in enumerate(g):
    xs=[it[0] for it in grp]; ys=[it[2][1] for it in grp]; yt=[it[2][4] for it in grp]; zs=[it[1] for it in grp]
    w=[round(it[3]["size"][0],2) for it in grp]
    print(f"col{i:2d} n={len(grp):2d} x[{min(xs):.2f},{max(xs):.2f}] y[{min(ys):.2f},{max(yt):.2f}] z[{min(zs):.2f},{max(zs):.2f}] widths={w}")
print("total cols", len(g))

print("\n=== HairBack columns ===")
g=clusters("HairBack", tol=0.8)
for i,grp in enumerate(g):
    xs=[it[0] for it in grp]; ys=[it[2][1] for it in grp]; yt=[it[2][4] for it in grp]; zs=[it[1] for it in grp]
    w=[round(it[3]["size"][0],2) for it in grp]
    print(f"col{i:2d} n={len(grp):2d} x[{min(xs):.2f},{max(xs):.2f}] y[{min(ys):.2f},{max(yt):.2f}] z[{min(zs):.2f},{max(zs):.2f}] widths={w}")
print("total cols", len(g))

print("\n=== hl_side columns ===")
g=clusters("hl_side", tol=1.0)
for i,grp in enumerate(g):
    xs=[it[0] for it in grp]; ys=[it[2][1] for it in grp]; yt=[it[2][4] for it in grp]; zs=[it[1] for it in grp]
    print(f"col{i:2d} n={len(grp):2d} x[{min(xs):.2f},{max(xs):.2f}] y[{min(ys):.2f},{max(yt):.2f}] z[{min(zs):.2f},{max(zs):.2f}]")

print("\n=== HairCap dome plates (rotation X not 0/180) ===")
n=0
for i,cu in enumerate(bones["HairCap"]["cubes"]):
    r=cu.get("rotation",[0,0,0])
    rx=((r[0]%360)+360)%360
    if abs(rx-0)>0.5 and abs(rx-180)>0.5:
        b=aabb(cu); n+=1
        print(f"#{i:3d} x{(b[0]+b[3])/2:6.2f} z{(b[2]+b[5])/2:6.2f} y[{b[1]:.2f},{b[4]:.2f}] s{[round(v,2) for v in cu['size']]} rot{[round(v,1) for v in r]} uv{cu['uv']['north']['uv']}")
print("dome plates:",n)
