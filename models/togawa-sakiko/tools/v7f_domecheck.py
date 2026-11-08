import json, os, math
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
d = json.load(open(os.path.join(BASE, "pack", "models", "main.json"), encoding="utf-8"))
cap = {b["name"]: b for b in d["minecraft:geometry"][0]["bones"]}["HairCap"]["cubes"]
dome = cap[118:]
R = math.radians
AX, BZ_B, BZ_F, H0, KK = 4.78, 4.80, 4.02, 42.36, 1.70
def rotM(rot):
    a, b, c = (rot or [0, 0, 0]); a, b, c = R(a), R(b), R(c)
    ca, sa = math.cos(a), math.sin(a); cb, sb = math.cos(b), math.sin(b); cc, sc = math.cos(c), math.sin(c)
    return [[cb*cc, -cb*sc, sb], [ca*sc+sa*sb*cc, ca*cc-sa*sb*sc, -sa*cb], [sa*sc-ca*sb*cc, sa*cc+ca*sb*sc, ca*cb]]
def det3(M):
    return (M[0][0]*(M[1][1]*M[2][2]-M[1][2]*M[2][1])
            - M[0][1]*(M[1][0]*M[2][2]-M[1][2]*M[2][0])
            + M[0][2]*(M[1][0]*M[2][1]-M[1][1]*M[2][0]))
bad = []
print("idx  cen(x,y,z)        s     ideal  d(y-ideal)  rot                 det   size")
for i, c in enumerate(dome):
    o = c["origin"]; s = c["size"]; M = rotM(c.get("rotation"))
    cen = [o[j]+s[j]/2 for j in range(3)]
    # top face height at centroid: + local Y * s[1]/2
    top = [cen[j] + M[j][1]*s[1]/2 for j in range(3)]
    rr = math.sqrt((top[0]/AX)**2 + (top[2]/(BZ_B if top[2] >= 0 else BZ_F))**2)
    ideal = H0-KK*rr*rr if rr <= 1.0 else None
    if i < 30 or (ideal is not None and abs(top[1]-ideal) > 0.25):
        print("%3d %s s=%.2f ideal=%s dy=%-6s rot=%s det=%.2f size=%s" % (
            i, [round(v, 2) for v in cen], rr,
            ("%.2f" % ideal) if ideal else "out",
            ("%.2f" % (top[1]-ideal)) if ideal else "-",
            [(round(v, 1)) for v in (c.get("rotation") or [0,0,0])], det3(M), [round(v, 2) for v in s]))
    if ideal is not None and abs(top[1]-ideal) > 0.25: bad.append((i, round(top[1]-ideal, 2)))
print("\ncubes deviating >0.25 from ideal:", len(bad), bad[:12])
