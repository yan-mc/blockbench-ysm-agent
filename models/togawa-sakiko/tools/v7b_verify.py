import json, math, sys
P = sys.argv[1] if len(sys.argv) > 1 else r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
d = json.load(open(P, encoding="utf-8"))
g = d["minecraft:geometry"][0]
bones = g["bones"]
SK = {"Skirt","RightSkirt","LeftSkirt","FrontSkirt","BackSkirt"}
LEG = {"LeftLeg","RightLeg","LeftLowerLeg","RightLowerLeg"}

def R_zyx(r):
    a,b,c = [math.radians(v) for v in r]
    ca,sa=math.cos(a),math.sin(a); cb,sb=math.cos(b),math.sin(b); cc,sc=math.cos(c),math.sin(c)
    Rx=[[1,0,0],[0,ca,-sa],[0,sa,ca]]; Ry=[[cb,0,sb],[0,1,0],[-sb,0,cb]]; Rz=[[cc,-sc,0],[sc,cc,0],[0,0,1]]
    def mul(A,B): return [[sum(A[i][k]*B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mul(mul(Rz,Ry),Rx)

def bb_cube(c):
    ox,oy,oz = c["origin"]; sx,sy,sz = c["size"]
    frm = [-(ox+sx), oy, oz]
    pivot = [-c["pivot"][0], c["pivot"][1], c["pivot"][2]] if "pivot" in c else [frm[0]+sx/2, frm[1]+sy/2, frm[2]+sz/2]
    rot = [-c["rotation"][0], -c["rotation"][1], c["rotation"][2]] if "rotation" in c else [0,0,0]
    return frm, [sx,sy,sz], pivot, rot

def boxes(names):
    out=[]
    for b in bones:
        if b["name"] not in names: continue
        for c in b.get("cubes",[]):
            frm, s, pivot, rot = bb_cube(c)
            M = R_zyx(rot)
            # corners in world
            pts=[]
            for dx in (0,s[0]):
                for dy in (0,s[1]):
                    for dz in (0,s[2]):
                        v=[frm[0]+dx-pivot[0], frm[1]+dy-pivot[1], frm[2]+dz-pivot[2]]
                        pts.append([sum(M[i][j]*v[j] for j in range(3))+pivot[i] for i in range(3)])
            ctr=[sum(p[i] for p in pts)/8 for i in range(3)]
            out.append((pts, M, [s[0]/2,s[1]/2,s[2]/2], b["name"], ctr))
    return out

sk = boxes(SK); lg = boxes(LEG)
print("skirt boxes", len(sk), "leg boxes", len(lg))

def hit(box, p, dv):
    pts, M, h, _, ctr = box
    # local coords of p and dv relative to center using M columns
    o=[p[i]-ctr[i] for i in range(3)]
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
    best=None
    for b in boxes:
        t=hit(b,p,dv)
        if t is not None and (best is None or t<best): best=t
    return best

x0=-0.15
def yhem(phi): return 14.10+1.50*math.cos(phi)

tot=0; cov=0
for k in range(72):
    phi=2*math.pi*k/72
    dirv=[math.sin(phi),0,-math.cos(phi)]
    y=yhem(phi)+0.15
    while y < 23.45:
        t=nearest(sk,[x0,y,0],dirv); tot+=1; cov += (t is not None)
        y+=0.4
print(f"A radial coverage: {cov}/{tot} = {100.0*cov/tot:.1f}%")

views={"front":((0,0,1),[0,-30]),"left":((-1,0,0),[30,0]),"back":((0,0,-1),[0,30])}
for name,(dv,fix) in views.items():
    tot_leg=0; vis=0; y=15.3
    while y < 21.4:
        u=-4.0
        while u <= 4.0:
            p=[u,y,fix[1]] if name in ("front","back") else [fix[0],y,u]
            tl=nearest(lg,p,dv)
            if tl is not None:
                tot_leg+=1
                ts=nearest(sk,p,dv)
                if ts is None or tl<ts: vis+=1
            u+=0.08
        y+=0.08
    print(f"B {name}: leg rays={tot_leg} visible={vis} blocked={100.0*(tot_leg-vis)/max(tot_leg,1):.2f}%")

lo=[9e9]*3; hi=[-9e9]*3
for b in sk:
    for p in b[0]:
        for i in range(3):
            lo[i]=min(lo[i],p[i]); hi[i]=max(hi[i],p[i])
print("skirt bbox(bb)", [round(v,2) for v in lo], [round(v,2) for v in hi])
print("total cubes", sum(len(b.get("cubes",[])) for b in bones), "skirt cubes", sum(len(b.get('cubes',[])) for b in bones if b['name'] in SK))
# sample hem heights by azimuth
for name,phi in (("front",0),("right",math.pi/2),("back",math.pi),("left",3*math.pi/2)):
    ys=[]
    for b in sk:
        for p in b[0]:
            # near this azimuth within 12 deg
            ang=math.atan2(p[0]-x0, -p[2])
            da=abs((ang-phi+math.pi)%(2*math.pi)-math.pi)
            if da<0.2: ys.append(p[1])
    print("hem", name, round(min(ys),2) if ys else None)

