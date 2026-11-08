import json
P = r'F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json'
m = json.load(open(P, encoding='utf-8'))
for b in m['minecraft:geometry'][0]['bones']:
    if b['name'] not in ('BackSkirt', 'LeftSkirt', 'RightSkirt'):
        continue
    for i, c in enumerate(b['cubes']):
        if abs(c['size'][2] - 0.24) < 1e-3:
            o = c['origin']; s = c['size']; p = c.get('pivot')
            ctr = [round(o[k] + s[k] / 2, 4) for k in range(3)]
            print(b['name'], i, 'pivot', p, 'center', ctr, 'rot', c.get('rotation'))
