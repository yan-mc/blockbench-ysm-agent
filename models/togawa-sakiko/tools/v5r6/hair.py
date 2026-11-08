import json, math
P = r'F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json'
d = json.load(open(P, encoding='utf-8'))
bones = {b['name']: b for b in d['minecraft:geometry'][0]['bones']}

def dump(name, ylim=22.0):
    cs = bones[name].get('cubes', [])
    if not cs:
        print(name, 'empty'); return
    lo = [9e9]*3; hi = [-9e9]*3
    for c in cs:
        o = c['origin']; s = c['size']
        for i in range(3):
            lo[i] = min(lo[i], o[i]); hi[i] = max(hi[i], o[i]+s[i])
    print(f"\n== {name} n={len(cs)} bbox {[round(v,2) for v in lo]} .. {[round(v,2) for v in hi]}")
    low = [c for c in cs if c['origin'][1] + c['size'][1] < ylim]
    print(f"  cubes with top<{ylim}: {len(low)}")
    for c in sorted(low, key=lambda c: c['origin'][1]):
        o = c['origin']; s = c['size']
        print(f"   x[{o[0]:6.2f},{o[0]+s[0]:6.2f}] y[{o[1]:6.2f},{o[1]+s[1]:6.2f}] z[{o[2]:5.2f},{o[2]+s[2]:5.2f}] rot={c.get('rotation')}")

for n in ('HairBack', 'hl_side', 'TwinTail_L', 'TwinTail_R'):
    dump(n)
