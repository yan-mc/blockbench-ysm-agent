import json, math
P = r'F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json'
d = json.load(open(P, encoding='utf-8'))
bones = d['minecraft:geometry'][0]['bones']

def bbox(c):
    o = c['origin']; s = c['size']
    return (o[0], o[1], o[2], o[0]+s[0], o[1]+s[1], o[2]+s[2])

def ctr(c):
    o = c['origin']; s = c['size']
    return (o[0]+s[0]/2, o[1]+s[1]/2, o[2]+s[2]/2)

for name in ['Skirt','FrontSkirt','BackSkirt','LeftSkirt','RightSkirt']:
    b = next(x for x in bones if x.get('name') == name)
    cbs = b['cubes']
    print('===', name, len(cbs))
    rows = sorted(cbs, key=lambda c: -ctr(c)[1])
    for i, c in enumerate(rows):
        cx, cy, cz = ctr(c)
        ang = math.degrees(math.atan2(cx, -cz))  # 0=front(-z), 90=+x(left)
        r = math.hypot(cx, cz)
        print(f'{i:2d} c=({cx:6.2f},{cy:6.2f},{cz:6.2f}) ang={ang:7.1f} r={r:5.2f} size={c["size"]} rot={c.get("rotation")}')
