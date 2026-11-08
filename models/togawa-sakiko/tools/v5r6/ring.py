import json, math
from collections import defaultdict

d = json.load(open(r'F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json', encoding='utf-8'))
bones = {b['name']: b for b in d['minecraft:geometry'][0]['bones']}
names = ['Skirt', 'BackSkirt', 'LeftSkirt', 'RightSkirt', 'FrontSkirt']

print(f"{'name':10s} {'i':>3s} {'theta':>7s} {'R':>6s} {'y0':>6s} {'y1':>6s} {'W':>5s} {'T':>5s} {'rotY':>7s} {'uv':>10s}")
rows = []
for n in names:
    for i, c in enumerate(bones[n].get('cubes', [])):
        o = c['origin']; s = c['size']
        cx = o[0] + s[0] / 2; cz = o[2] + s[2] / 2
        R = math.hypot(cx, cz); th = math.degrees(math.atan2(cz, cx))
        rot = c.get('rotation') or [0, 0, 0]
        uv = c.get('uv')
        uv0 = None
        if isinstance(uv, dict):
            v = list(uv.values())[0]
            uv0 = tuple(v.get('uv')) if isinstance(v, dict) else None
        rows.append((n, i, th, R, o[1], o[1] + s[1], s[0], s[2], rot[1], uv0))
        print(f"{n:10s} {i:3d} {th:7.1f} {R:6.2f} {o[1]:6.2f} {o[1]+s[1]:6.2f} {s[0]:5.2f} {s[2]:5.2f} {rot[1]:7.1f} {str(uv0):>10s}")

print("\n=== coverage: theta bins (deg) -> max radius per y-band")
bands = [(23.0, 25.0), (20.0, 23.0), (18.0, 20.0), (16.5, 18.0), (15.0, 16.5)]
for (y0, y1) in bands:
    print(f"\n y[{y0},{y1})")
    for tb in range(-180, 180, 15):
        sel = [r for r in rows if r[3] > 0 and y0 <= (r[4] + r[5]) / 2 < y1 and tb <= r[2] < tb + 15]
        if sel:
            Rs = [f"{r[3]:.1f}" for r in sel]
            print(f"   {tb:4d}..{tb+15:4d}: R={','.join(Rs)}")
