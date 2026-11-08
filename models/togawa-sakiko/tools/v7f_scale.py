import json, os, math
import numpy as np
from PIL import Image
from collections import deque
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
P = os.path.join(BASE, "pack", "models", "main.json")
d = json.load(open(P, encoding="utf-8")); bones = {b["name"]: b for b in d["minecraft:geometry"][0]["bones"]}
R = math.radians
def rotM(rot):
    a, b, c = (rot or [0, 0, 0]); a, b, c = R(a), R(b), R(c)
    ca, sa = math.cos(a), math.sin(a); cb, sb = math.cos(b), math.sin(b); cc, sc = math.cos(c), math.sin(c)
    return [[cb*cc, -cb*sc, sb], [ca*sc+sa*sb*cc, ca*cc-sa*sb*sc, -sa*cb], [sa*sc-ca*sb*cc, sa*cc+ca*sb*sc, ca*cb]]
def verts(c):
    o = c["origin"]; s = c["size"]; M = rotM(c.get("rotation"))
    cen = [o[i]+s[i]/2 for i in range(3)]; out = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                p = [sx*s[0]/2, sy*s[1]/2, sz*s[2]/2]
                out.append([sum(M[i][j]*p[j] for j in range(3))+cen[i] for i in range(3)])
    return out
# Hair subtree
parent = {b["name"]: b.get("parent") for b in d["minecraft:geometry"][0]["bones"]}
def under(n, root):
    while n:
        if n == root: return True
        n = parent.get(n)
    return False
hair = [n for n in bones if under(n, "Hair")]
print("hair subtree:", hair)
pts = []
for n in hair:
    for c in bones[n].get("cubes", []):
        pts += verts(c)
xmin = min(p[0] for p in pts); xmax = max(p[0] for p in pts)
zmin = min(p[2] for p in pts); zmax = max(p[2] for p in pts)
ymax = max(p[1] for p in pts)
print("hair world x[%.2f,%.2f] z[%.2f,%.2f] ymax %.2f" % (xmin, xmax, zmin, zmax, ymax))
im = Image.open(os.path.join(BASE, "artifacts", "renders", "r0022", "top_2400.png")).convert("RGBA")
a = np.array(im)[:, :, 3]; m = a > 8
ys, xs = np.nonzero(m)
print("mask bbox x[%d,%d] y[%d,%d]" % (xs.min(), xs.max(), ys.min(), ys.max()))
sx = (xs.max()-xs.min())/(xmax-xmin); sz = (ys.max()-ys.min())/(zmax-zmin)
print("scale from x: %.2f px/u | from z: %.2f px/u" % (sx, sz))
