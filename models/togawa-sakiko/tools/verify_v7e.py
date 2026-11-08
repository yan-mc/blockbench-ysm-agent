import json, math, os
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
P = os.path.join(BASE,"pack","models","main.json")
POLD = os.path.join(BASE,"artifacts","v7e","_presave","main.json")

def rotm(rx,ry,rz):
    rx,ry,rz=[math.radians(v) for v in (rx,ry,rz)]
    cx,sx=math.cos(rx),math.sin(rx); cy,sy=math.cos(ry),math.sin(ry); cz,sz=math.cos(rz),math.sin(rz)
    Rx=[[1,0,0],[0,cx,-sx],[0,sx,cx]]; Ry=[[cy,0,sy],[0,1,0],[-sy,0,cy]]; Rz=[[cz,-sz,0],[sz,cz,0],[0,0,1]]
    def mm(a,b): return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mm(mm(Rx,Ry),Rz)
def ab(c):
    o,s=c["origin"],c["size"]; p=c.get("pivot",o); R=rotm(*c.get("rotation",[0,0,0]))
    pts=[]
    for dx in (0,s[0]):
        for dy in (0,s[1]):
            for dz in (0,s[2]):
                v=[o[k]+[dx,dy,dz][k]-p[k] for k in range(3)]
                pts.append([p[i]+sum(R[i][j]*v[j] for j in range(3)) for i in range(3)])
    return [min(q[i] for q in pts) for i in range(3)]+[max(q[i] for q in pts) for i in range(3)]

def load(p):
    d=json.load(open(p,encoding="utf-8")); g=d["minecraft:geometry"][0]
    return d,g,{b["name"]:b for b in g["bones"]}

def crown_gaps(bones, step=0.1, r=3.4, ythr=40.3):
    boxes=[]
    for n in ("HairCap","front_h1","corner_h1","HairBack","hl_side"):
        for c in bones[n].get("cubes",[]): boxes.append(ab(c))
    nx=int(2*r/step)+1; holes=0; tot=0; minTop=99
    for i in range(nx):
        x=-r+i*step
        for j in range(nx):
            z=-r+j*step
            if x*x+z*z>r*r: continue
            tot+=1
            tops=[b[4] for b in boxes if b[0]-1e-6<=x<b[3]+1e-6 and b[2]-1e-6<=z<b[5]+1e-6]
            t=max(tops) if tops else -1
            if t<ythr: holes+=1
            if tops: minTop=min(minTop,t)
    return tot,holes,minTop

def face_cover(bones, step=0.1):
    # frontal projection: hair in front of face plane z<-3.45 covering face rect x[-3.2,3.2] y[33,40]
    boxes=[]
    for n in ("HairCap","front_h1","corner_h1","hl_side"):
        for c in bones[n].get("cubes",[]):
            b=ab(c)
            if b[2]<-3.45: boxes.append(b)
    cov=0; tot=0
    xs=[-3.2+i*step for i in range(int(6.4/step)+1)]
    ys=[33.0+i*step for i in range(int(7.0/step)+1)]
    for x in xs:
        for y in ys:
            tot+=1
            if any(b[0]<=x<b[3] and b[1]<=y<b[4] for b in boxes): cov+=1
    eye=0; eyet=0
    for x in [(-2.6+i*0.05) for i in range(int(5.2/0.05)+1)]:
        for y in [34.0+i*0.05 for i in range(int(2.4/0.05)+1)]:
            eyet+=1
            if any(b[0]<=x<b[3] and b[1]<=y<b[4] for b in boxes): eye+=1
    return cov/tot, eye/eyet

for tag,p in (("v7d",POLD),("v7e",P)):
    d,g,b=load(p)
    tot=sum(len(x.get("cubes",[])) for x in g["bones"])
    t,h,mn=crown_gaps(b)
    fc,ec=face_cover(b)
    counts={n:len(b[n].get("cubes",[])) for n in ("HairCap","front_h1","HairBack","hl_side","corner_h1","TwinTail_L","TwinTail_R")}
    print(tag,"cubes",tot,"bones",len(g["bones"]),"| crown cells",t,"holes(top<40.3)",h,"min top %.2f"%mn,"| face blocked %.1f%%"%(fc*100),"eye-region blocked %.2f%%"%(ec*100))
    print("   ",counts)

# v7e specifics
d,g,b=load(P)
for n in ("HairCap","front_h1","HairBack","hl_side"):
    bs=[ab(c) for c in b[n]["cubes"]]
    lo=[min(x[i] for x in bs) for i in range(3)]; hi=[max(x[i+3] for x in bs) for i in range(3)]
    print(n,"AABB",[round(v,2) for v in lo],[round(v,2) for v in hi])
