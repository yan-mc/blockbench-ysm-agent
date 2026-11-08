import json, math
from collections import Counter
P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
d = json.load(open(P, encoding="utf-8"))
bones = {b["name"]: b for b in d["minecraft:geometry"][0]["bones"]}

def rotm(rx, ry, rz):
    rx, ry, rz = [math.radians(v) for v in (rx, ry, rz)]
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    Rx = [[1,0,0],[0,cx,-sx],[0,sx,cx]]; Ry=[[cy,0,sy],[0,1,0],[-sy,0,cy]]; Rz=[[cz,-sz,0],[sz,cz,0],[0,0,1]]
    def mm(a,b): return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mm(mm(Rx,Ry),Rz)
def aabb(c):
    o,s=c["origin"],c["size"]; p=c.get("pivot",o); R=rotm(*c.get("rotation",[0,0,0]))
    pts=[]
    for dx in (0,s[0]):
        for dy in (0,s[1]):
            for dz in (0,s[2]):
                v=[dx,dy,dz]
                pts.append([p[i]+sum(R[i][j]*v[j] for j in range(3)) for i in range(3)])
    return [min(q[i] for q in pts) for i in range(3)]+[max(q[i] for q in pts) for i in range(3)]

print("== UV swatches per hair bone")
for n in ("HairCap","front_h1","HairBack","hl_side","corner_h1","TwinTail_L"):
    c=Counter()
    for cu in bones[n]["cubes"]:
        uv=cu["uv"]
        key=tuple(tuple(uv[f]["uv"]) for f in ("north","east","south","west","up","down"))
        c[key]+=1
    print(n, len(c), "distinct")
    for k,v in c.most_common(12):
        print("   ", v, "uv=", k[0], "size=", uv["north"]["uv_size"] if False else "")
    break

print("\n== HairCap cubes sorted by top desc")
rows=[]
for i,cu in enumerate(bones["HairCap"]["cubes"]):
    b=aabb(cu)
    rows.append((b[4], b[0]+b[3])/2 if False else (b[4], i, (b[0]+b[3])/2, (b[2]+b[5])/2, b[1], b[4], cu["size"], cu.get("rotation")))
rows.sort(reverse=True)
for r in rows[:60]:
    yt,i,x,z,yb,yt2,s,rot=r
    print(f"#{i:3d} top{yt:6.2f} bot{yb:6.2f} x{x:6.2f} z{z:6.2f} s{round(s[0],2)},{round(s[1],2)},{round(s[2],2)} rot{[round(v,1) for v in rot]}")
print("... total", len(rows))
print("\n== anomalies |x|>6.2 or |z|>5.8")
for i,cu in enumerate(bones["HairCap"]["cubes"]):
    b=aabb(cu)
    if b[0]<-6.2 or b[3]>6.2 or b[2]<-5.9 or b[5]>5.9:
        print(f"#{i:3d} x[{b[0]:.2f},{b[3]:.2f}] y[{b[1]:.2f},{b[4]:.2f}] z[{b[2]:.2f},{b[5]:.2f}] s{[round(v,2) for v in cu['size']]} rot{[round(v,1) for v in cu.get('rotation',[0,0,0])]} o{[round(v,2) for v in cu['origin']]} p{[round(v,2) for v in cu.get('pivot',[])]}")
