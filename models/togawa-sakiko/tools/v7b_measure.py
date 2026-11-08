import json, math, sys

P = sys.argv[1] if len(sys.argv) > 1 else r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
d = json.load(open(P, encoding="utf-8"))
g = d["minecraft:geometry"][0]
bones = g["bones"]
SK = {"Skirt","RightSkirt","LeftSkirt","FrontSkirt","BackSkirt"}
LEG = {"LeftLeg","RightLeg","LeftLowerLeg","RightLowerLeg"}

def Rmat(r):
    a,b,c = [math.radians(v) for v in r]
    ca,sa=math.cos(a),math.sin(a); cb,sb=math.cos(b),math.sin(b); cc,sc=math.cos(c),math.sin(c)
    Rx=[[1,0,0],[0,ca,-sa],[0,sa,ca]]
    Ry=[[cb,0,sb],[0,1,0],[-sb,0,cb]]
    Rz=[[cc,-sc,0],[sc,cc,0],[0,0,1]]
    def mul(A,B): return [[sum(A[i][k]*B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mul(mul(Rz,Ry),Rx)

def boxes(names):
    out=[]
    for b in bones:
        if b["name"] not in names: continue
        for c in b.get("cubes",[]):
            o=c["origin"]; s=c["size"]; r=c.get("rotation",[0,0,0])
            p=c.get("pivot",[o[0]+s[0]/2,o[1]+s[1]/2,o[2]+s[2]/2])
            M=Rmat(r)
            ctr=[sum(M[i][j]*(o[j]+s[j]/2-p[j]) for j in range(3))+p[i] for i in range(3)]
            out.append((ctr, [M[0],M[1],M[2]], [s[0]/2,s[1]/2,s[2]/2], b["name"]))
    return out

sk = boxes(SK); lg = boxes(LEG)
print("skirt boxes", len(sk), "leg boxes", len(lg))

def hit(box, p, dv):
    ctr, M, h, _ = box
    o=[p[i]-ctr[i] for i in range(3)]
    # local coords: dot with columns (M[i][j] is row i col j) -> local = M^T * vec
    lo=[sum(M[i][j]*o[i] for i in range(3)) for j in range(3)]
    ld=[sum(M[i][j]*dv[i] for i in range(3)) for j in range(3)]
    tmin, tmax = 1e18, -1e18
    for i in range(3):
        if abs(ld[i]) < 1e-9:
            if abs(lo[i]) > h[i]: return None
        else:
            t1=(-h[i]-lo[i])/ld[i]; t2=(h[i]-lo[i])/ld[i]
            if t1>t2: t1,t2=t2,t1
            tmin=min(tmin,t1); tmax=max(tmax,t2)
    if tmax < max(tmin,0): return None
    return max(tmin,0.0)

def nearest(boxes, p, dv):
    best=None; who=None
    for b in boxes:
        t=hit(b,p,dv)
        if t is not None and (best is None or t<best):
            best=t; who=b[3]
    return best, who

x0=-0.15
def yhem(phi): return 14.10+1.50*math.cos(phi)

# A: radial continuous coverage
tot=0; cov=0
for k in range(72):
    phi=2*math.pi*k/72
    dirv=[math.sin(phi),0,-math.cos(phi)]
    y=yhem(phi)+0.15
    while y < 23.45:
        p=[x0,y,0]
        t,who=nearest(sk,p,dirv)
        tot+=1
        if t is not None: cov+=1
        y+=0.4
print(f"A radial coverage: {cov}/{tot} = {100.0*cov/tot:.1f}%")

# A2: at blue hem just above black coverage? check blue shell alone at its own hem+0.1
blue=[b for b in sk if b[3]=="Skirt"]
# B: thigh visibility from three axes
def yhem_b(phi): return 13.35+0.80*math.cos(phi)
views = {
 "front": ((0,0,1),   [0,-30]),
 "left":  ((-1,0,0),  [30,0]),
 "back":  ((0,0,-1),  [0,30]),
}
for name,(dv,fix) in views.items():
    dv=list(dv); tot_leg=0; vis=0
    y=15.3
    while y < 21.4:
        u=-4.0
        while u <= 4.0:
            if name in ("front","back"):
                p=[u, y, fix[1]]
            else:
                p=[fix[0], y, u]
            tl,wl=nearest(lg,p,dv)
            if tl is not None:
                tot_leg+=1
                ts,ws=nearest(sk,p,dv)
                if ts is None or tl < ts: vis+=1
            u+=0.08
        y+=0.08
    print(f"B {name}: leg rays={tot_leg} visible={vis} blocked={100.0*(tot_leg-vis)/max(tot_leg,1):.2f}%")

# C: bbox / hem stats
def bbox(names):
    lo=[9e9]*3; hi=[-9e9]*3
    for b in bones:
        if b["name"] not in names: continue
        for c in b.get("cubes",[]):
            o=c["origin"]; s=c["size"]; r=c.get("rotation",[0,0,0])
            p=c.get("pivot",[o[0]+s[0]/2,o[1]+s[1]/2,o[2]+s[2]/2]); M=Rmat(r)
            for dx in (0,s[0]):
                for dy in (0,s[1]):
                    for dz in (0,s[2]):
                        v=[o[0]+dx-p[0],o[1]+dy-p[1],o[2]+dz-p[2]]
                        w=[sum(M[i][j]*v[j] for j in range(3))+p[i] for i in range(3)]
                        for i in range(3):
                            lo[i]=min(lo[i],w[i]); hi[i]=max(hi[i],w[i])
    return lo,hi
lo,hi=bbox(SK)
print("skirt bbox", [round(v,2) for v in lo], [round(v,2) for v in hi])
tot_cubes=sum(len(b.get("cubes",[])) for b in bones)
print("total cubes", tot_cubes, "skirt cubes", sum(len(b.get('cubes',[])) for b in bones if b['name'] in SK))
for b in bones:
    if b["name"] in SK:
        print(" ", b["name"], len(b["cubes"]), "pivot", b.get("pivot"))

