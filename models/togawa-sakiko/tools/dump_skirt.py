import json, sys, statistics
P = r'F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json'
d = json.load(open(P, encoding='utf-8'))
geo = d['minecraft:geometry'][0]
bones = geo['bones']
print('bones', len(bones), 'desc', geo.get('description'))

names = ['Skirt', 'FrontSkirt', 'BackSkirt', 'LeftSkirt', 'RightSkirt']
tot = 0
for b in bones:
    n = b.get('name', '')
    cbs = b.get('cubes', [])
    if any(k in n for k in ['Skirt', 'Body', 'Waist', 'Hip']):
        print('==', n, 'pivot', b.get('pivot'), 'rot', b.get('rotation'), 'parent', b.get('parent'), 'cubes', len(cbs))
    tot += len(cbs)
print('total cubes', tot)

for n in names:
    b = next((x for x in bones if x.get('name') == n), None)
    if not b:
        print('MISSING', n); continue
    cbs = b.get('cubes', [])
    xs = []; ys = []; zs = []
    print('\n###', n, 'cubes', len(cbs), 'pivot', b.get('pivot'), 'rot', b.get('rotation'))
    for c in cbs[:200]:
        o = c['origin']; s = c['size']; r = c.get('rotation')
        xs += [o[0], o[0] + s[0]]; ys += [o[1], o[1] + s[1]]; zs += [o[2], o[2] + s[2]]
    if xs:
        print(' x', round(min(xs), 2), round(max(xs), 2), 'cx', round((min(xs) + max(xs)) / 2, 2))
        print(' y', round(min(ys), 2), round(max(ys), 2))
        print(' z', round(min(zs), 2), round(max(zs), 2), 'cz', round((min(zs) + max(zs)) / 2, 2))
    for c in cbs[:6]:
        print('  cube', c['origin'], c['size'], c.get('rotation'), c.get('uv'))
