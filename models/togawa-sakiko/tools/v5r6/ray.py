"""Find which cube is visible at a given (x,y) in the back view (max z)."""
import json, math
P = r'F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json'
m = json.load(open(P, encoding='utf-8'))
bones = m['minecraft:geometry'][0]['bones']


def rot(p, r):
    x, y, z = p
    rx, ry, rz = [math.radians(a) for a in r]
    y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
    x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
    x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
    return [x, y, z]


def cubes_containing(px, py):
    hits = []
    for b in bones:
        for i, c in enumerate(b.get('cubes', [])):
            o = c['origin']; s = c['size']; r = c.get('rotation') or [0, 0, 0]
            pv = c.get('pivot') or [o[0] + s[0] / 2, o[1] + s[1] / 2, o[2] + s[2] / 2]
            # transform point into cube-local (inverse rotation about pivot)
            lp = [px - pv[0], py - pv[1], 0 - pv[2]]
            lp = rot(lp, [-r[0], -r[1], -r[2]])
            lx, ly, lz = lp[0] + pv[0], lp[1] + pv[1], lp[2] + pv[2]
            if o[0] - 1e-4 <= lx <= o[0] + s[0] + 1e-4 and o[1] - 1e-4 <= ly <= o[1] + s[1] + 1e-4 and o[2] - 1e-4 <= lz <= o[2] + s[2] + 1e-4:
                hits.append((o[2] + s[2], b['name'], i, c))
    hits.sort(key=lambda t: -t[0])
    return hits[:6]


for pt in [(0.6, 15.3), (0.0, 15.0), (1.2, 15.6)]:
    print("== point", pt)
    for z, bn, i, c in cubes_containing(*pt):
        uv0 = None
        u = c.get('uv')
        if isinstance(u, dict):
            v = list(u.values())[0]
            uv0 = v.get('uv') if isinstance(v, dict) else v
        print("  z_max %.2f %s[%d] origin %s size %s uv %s" % (z, bn, i, c['origin'], c['size'], uv0))
