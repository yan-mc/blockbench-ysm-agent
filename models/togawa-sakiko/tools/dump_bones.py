import json
P = r'F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json'
d = json.load(open(P, encoding='utf-8'))
bones = d['minecraft:geometry'][0]['bones']
for b in bones:
    cbs = b.get('cubes', [])
    if not cbs: continue
    xs=[];ys=[];zs=[]
    for c in cbs:
        o=c['origin'];s=c['size']
        xs+=[o[0],o[0]+s[0]];ys+=[o[1],o[1]+s[1]];zs+=[o[2],o[2]+s[2]]
    print(f"{b['name']:22s} n={len(cbs):3d} pivot={b.get('pivot')} rot={b.get('rotation')} x[{min(xs):6.2f},{max(xs):6.2f}] y[{min(ys):6.2f},{max(ys):6.2f}] z[{min(zs):6.2f},{max(zs):6.2f}]")
