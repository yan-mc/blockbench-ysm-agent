import json, math, shutil, os
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
P = os.path.join(BASE, "pack", "models", "main.json")
BAK = os.path.join(BASE, "artifacts", "v7e", "_presave", "main.json")
if os.path.exists(BAK): shutil.copy2(BAK, P)          # always rebuild from v7d base
d = json.load(open(P, encoding="utf-8"))
G = d["minecraft:geometry"][0]
bones = {b["name"]: b for b in G["bones"]}

def add(a,b): return [a[0]+b[0],a[1]+b[1],a[2]+b[2]]
def sub(a,b): return [a[0]-b[0],a[1]-b[1],a[2]-b[2]]
def dot(a,b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def cross(a,b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def norm(a):
    l=math.sqrt(dot(a,a)) or 1.0
    return [a[0]/l,a[1]/l,a[2]/l]

def euler(X,Y,Z):
    M=[[X[i],Y[i],Z[i]] for i in range(3)]
    sb=max(-1.0,min(1.0,M[0][2])); b=math.asin(sb); cb=math.cos(b)
    if abs(cb)<1e-6:
        a=0.0; c=math.atan2(M[1][0],M[1][1])
    else:
        a=math.atan2(-M[1][2],M[2][2]); c=math.atan2(-M[0][1],M[0][0])
    return [round(math.degrees(a),3),round(math.degrees(b),3),round(math.degrees(c),3)]

def uvsw(x): return {f:{"uv":[x,246],"uv_size":[3,3]} for f in ("north","east","south","west","up","down")}

def cube(center,size,X,Y,Z,xuv):
    c=[round(v,4) for v in center]; s=[round(v,4) for v in size]
    return {"origin":[round(c[i]-s[i]/2,4) for i in range(3)],"size":s,"pivot":c,
            "rotation":euler(norm(X),norm(Y),norm(Z)),"uv":uvsw(xuv)}

def flat(center,sx,sz,th,xuv):   # horizontal plate: sx along X, sz along Z, th vertical
    return cube(center,[sx,sz,th],[1,0,0],[0,0,1],[0,-1,0],xuv)
def vplate(center,w,h,th,xuv):   # vertical plate: w along X, h along Y, th along Z
    return cube(center,[w,h,th],[1,0,0],[0,-1,0],[0,0,-1],xuv)

REF=[0,0,1]
def basis_from_dir(down):
    Y=norm(down); X=norm(cross(Y,REF)); Z=norm(cross(X,Y)); return X,Y,Z
def ang_between(a,b):
    return math.degrees(math.acos(max(-1,min(1,dot(norm(a),norm(b))))))

report={}

# ================= HairCap crown =================
cap=bones["HairCap"]["cubes"]
drop_idx={85,88,91,92,95,96,99}
kept=[c for i,c in enumerate(cap) if i not in drop_idx]
new=[]
# ---- stacked shingle dome: horizontal concentric rings, small fixed tilt (no crossing) ----
def ring(y,r0,r1,n,tilt,xuv):
    rm=(r0+r1)/2.0
    w=2*math.pi*rm/n+0.28
    h=(r1-r0)+0.35
    for k in range(n):
        ph=math.radians(360.0*k/n)
        c=[rm*math.sin(ph),y,-rm*math.cos(ph)]
        u=[math.cos(ph),0,math.sin(ph)]
        a=math.radians(tilt)
        v=norm([math.sin(ph)*math.cos(a),-math.sin(a),-math.cos(ph)*math.cos(a)])   # radial, sloping down-outward
        new.append(cube([c[i]+0.04*cross(u,v)[i] for i in range(3)],[w,h,0.30],u,v,cross(u,v),xuv))
new.append(flat([0,42.50,0],2.05,2.05,0.30,86))     # crown centre plate
ring(42.30,0.85,1.95,8,8.0,86)
ring(42.04,1.80,2.75,10,10.0,86)
ring(41.78,2.60,3.42,12,12.0,70)
ring(41.53,3.30,3.98,14,14.0,54)
# front hairline band: closes slot between front wall top (40.36) and ring4 (41.52)
for k in range(6):
    x=-2.5+k*1.0
    new.append(cube([x,41.02,-3.46],[1.25,1.35,0.45],[1,0,0],[0,-1,0.38],cross([1,0,0],norm([0,-1,0.38])),54))
# solid core: hidden filler layers over crown centre
for (cx,cz,sx,sz,y,uv) in [(-1.15,-1.15,2.3,2.3,40.95,70),(1.15,-1.15,2.3,2.3,40.95,70),
                           (-1.15,1.15,2.3,2.3,40.95,70),(1.15,1.15,2.3,2.3,40.95,70),
                           (0,0,3.1,3.1,41.28,86),(0,0,2.4,2.4,41.60,86)]:
    new.append(flat([cx,y,cz],sx,sz,0.36,uv))
bones["HairCap"]["cubes"]=kept+new
report["HairCap"]={"kept":len(kept),"deleted":len(drop_idx),"added":len(new),"total":len(kept)+len(new)}

# ================= front_h1 bangs =================
fh=[]
for x in (0.55,1.85,3.05):
    for s in (1,-1):
        fh.append(vplate([s*x,38.55,-3.55],1.75,3.45,0.36,54))
TOP=40.60
# x0, width, tipY, outward drift, z0
locks=[(0.30,0.95,36.40,0.04,-3.86),(0.90,1.02,36.95,0.08,-3.98),(1.50,1.04,36.55,0.12,-3.88),
       (2.10,1.00,37.25,0.16,-3.80),(2.70,0.95,36.75,0.18,-3.94),(3.25,0.92,37.55,0.20,-3.82)]
deltas=[]
for (x0,w0,tip,dxt,z0) in locks:
    for s in (1,-1):
        L=TOP-tip; n=4; h=L/n+0.30; dirs=[]
        for i in range(n):
            t=(i+0.5)/n
            y=TOP-t*L; z=z0-0.30*t; x=s*(x0+dxt*(t**1.4))
            w=w0*(1-0.22*t)*(0.92 if i==n-1 else 1.0)
            t0=max(0.0,t-0.15); t1=min(1.0,t+0.15)
            dvec=sub([s*(x0+dxt*(t1**1.4)),TOP-t1*L,z0-0.30*t1],[s*(x0+dxt*(t0**1.4)),TOP-t0*L,z0-0.30*t0])
            dirs.append(norm(dvec)); Xb,Yb,Zb=basis_from_dir(dvec)
            fh.append(cube([x,y,z],[w,h,0.50],Xb,Yb,Zb,86 if i<=1 else 70))
        for i in range(len(dirs)-1): deltas.append(ang_between(dirs[i],dirs[i+1]))
bones["front_h1"]["cubes"]=fh
report["front_h1"]={"locks":10,"segs_per_lock":4,"cubes":len(fh),"max_delta_deg":round(max(deltas),2)}

# ================= HairBack =================
hb=[]
bd=[]
def zc_of(x): return 5.28-0.058*x*x
locks_b=[(0.0,1.15,1.05,23.2,0.0),(1.02,1.12,1.18,21.4,0.16),(2.05,1.06,0.92,24.6,-0.14),
         (3.05,1.00,1.12,22.0,0.10),(4.02,0.90,0.88,25.2,-0.18)]
TOP=39.40
for (x0,w0,dep,tip,zoff) in locks_b:
    for s in ((1,) if x0==0 else (1,-1)):
        L=TOP-tip; n=8; h=L/n+0.30; dirs=[]
        for i in range(n):
            t=(i+0.5)/n; y=TOP-t*L
            grow=0.86+0.20*t
            x=s*(x0*grow)
            zc=zc_of(x0)+zoff
            z=zc-0.55*max(0.0,min(1.0,(39.4-y)/7.4))
            w=w0*(1.0-0.08*t)*(0.72 if i>=n-2 else 1.0)
            dz=0.35 if i==n-1 else 0.0
            t0=max(0.0,t-0.13); t1=min(1.0,t+0.13)
            y0=TOP-t0*L; y1=TOP-t1*L
            z0=zc-0.55*max(0.0,min(1.0,(39.4-y0)/7.4)); z1=zc-0.55*max(0.0,min(1.0,(39.4-y1)/7.4))
            dvec=sub([0,y1,z1],[0,y0,z0]); dirs.append(norm(dvec))
            Xb,Yb,Zb=basis_from_dir(dvec)
            uv=54 if t<0.28 else (38 if t<0.70 else 22)
            hb.append(cube([x,y,z],[w,h,dep],Xb,Yb,Zb,uv))
        for i in range(len(dirs)-1): bd.append(ang_between(dirs[i],dirs[i+1]))
# inner fill (vertical plates, slightly inside)
for (x0,y0,hgt,w) in [(-3.4,31.5,10.0,1.2),(-1.7,32.5,11.0,1.3),(0.0,32.0,11.5,1.3),(1.7,32.5,11.0,1.3),(3.4,31.5,10.0,1.2),
                      (-2.6,24.0,9.0,1.1),(-0.9,23.0,9.5,1.2),(0.9,23.0,9.5,1.2),(2.6,24.0,9.0,1.1)]:
    hb.append(vplate([x0,y0,zc_of(abs(x0))-0.62],w,hgt,0.42,22))
bones["HairBack"]["cubes"]=hb
report["HairBack"]={"locks":9,"segs_per_lock":8,"cubes":len(hb),"max_delta_deg":round(max(bd),2)}

# ================= hl_side =================
hs=[]; sd=[]
side_locks=[(4.05,-1.10,25.8,0.88,0.66),(4.55,0.12,26.6,0.80,0.62)]
TOP=37.35
for (x0,z0,tip,w0,dep) in side_locks:
    for s in (1,-1):
        L=TOP-tip; n=5; h=L/n+0.32; dirs=[]
        for i in range(n):
            t=(i+0.5)/n; y=TOP-t*L
            x=s*(x0-0.18*t); z=z0+0.20*t
            w=w0*(1-0.16*t)*(1.0 if i<3 else 0.82)
            t0=max(0.0,t-0.12); t1=min(1.0,t+0.12)
            dvec=sub([s*(x0-0.18*t1),TOP-t1*L,z0+0.20*t1],[s*(x0-0.18*t0),TOP-t0*L,z0+0.20*t0])
            dirs.append(norm(dvec)); Xb,Yb,Zb=basis_from_dir(dvec)
            uv=70 if t<0.35 else (54 if t<0.75 else 38)
            hs.append(cube([x,y,z],[w,h,dep],Xb,Yb,Zb,uv))
        for i in range(len(dirs)-1): sd.append(ang_between(dirs[i],dirs[i+1]))
bones["hl_side"]["cubes"]=hs
report["hl_side"]={"locks":6,"segs_per_lock":5,"cubes":len(hs),"max_delta_deg":round(max(sd),2)}

total=sum(len(b.get("cubes",[])) for b in G["bones"])
report["total_cubes"]=total; report["bones"]=len(G["bones"])
json.dump(d,open(P,"w",encoding="utf-8"),ensure_ascii=False,separators=(",",":"))
print(json.dumps(report,ensure_ascii=False,indent=1))
