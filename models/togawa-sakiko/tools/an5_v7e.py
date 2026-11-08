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

def corners(c):
    o,s=c["origin"],c["size"]; p=c.get("pivot",o); R=rotm(*c.get("rotation",[0,0,0]))
    pts=[]
    for dx in (0,s[0]):
        for dy in (0,s[1]):
            for dz in (0,s[2]):
                v=[o[k]+[dx,dy,dz][k]-p[k] for k in range(3)]
                pts.append([p[i]+sum(R[i][j]*v[j] for j in range(3)) for i in range(3)])
    return pts
def aabb(c):
    pts=corners(c)
    return [min(q[i] for q in pts) for i in range(3)]+[max(q[i] for q in pts) for i in range(3)]

for n in ("Head","HairCap","front_h1","HairBack","hl_side","corner_h1"):
    cs=bones[n]["cubes"]; bbs=[aabb(c) for c in cs]
    lo=[min(b[i] for b in bbs) for i in range(3)]; hi=[max(b[i+3] for b in bbs) for i in range(3)]
    print(f"{n}: n={len(cs)} AABB {[round(v,2) for v in lo]} .. {[round(v,2) for v in hi]}  center x{(lo[0]+hi[0])/2:.2f} z{(lo[2]+hi[2])/2:.2f}")

print("\nHairCap top-down max-top map (0.5 grid, char = int(ytop-35))")
cs=bones["HairCap"]["cubes"]; bbs=[aabb(c) for c in cs]
for zt in [i*0.5 for i in range(-13,14)]:
    row=""
    for xt in [i*0.5 for i in range(-13,14)]:
        hs=[b[4] for b in bbs if b[0]-0.001<=xt<b[3]+0.001 and b[2]-0.001<=zt<b[5]+0.001]
        row += "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[min(35,int(max(hs)-35))] if hs else "."
    print(f"{zt:6.1f} {row}")

print("\nHairCap plates sorted by top")
rows=[]
for i,c in enumerate(bones["HairCap"]["cubes"]):
    b=aabb(c); rows.append((b[4],i,(b[0]+b[3])/2,(b[2]+b[5])/2,b[1],b[4],[round(v,2) for v in c["size"]],c.get("rotation",[0,0,0])))
rows.sort(reverse=True)
for r in rows[:24]:
    print(f"#{r[1]:3d} top{r[0]:6.2f} bot{r[4]:6.2f} x{r[2]:6.2f} z{r[3]:6.2f} s{r[6]} rot{[round(v,1) for v in r[7]]}")
print("...")
for r in rows[24:]:
    print(f"#{r[1]:3d} top{r[0]:6.2f} bot{r[4]:6.2f} x{r[2]:6.2f} z{r[3]:6.2f} s{r[6]} rot{[round(v,1) for v in r[7]]}")
