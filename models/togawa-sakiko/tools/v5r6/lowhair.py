import json
P = r'F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json'
m = json.load(open(P, encoding='utf-8'))
hb = [b for b in m['minecraft:geometry'][0]['bones'] if b['name'] == 'HairBack'][0]['cubes']
low = sorted([c for c in hb if c['origin'][1] + c['size'][1] < 20.0], key=lambda c: c['origin'][1])
print('low cubes', len(low))
for c in low:
    o = c['origin']; s = c['size']
    print("x[%6.2f,%6.2f] y[%6.2f,%6.2f] rot=%s" % (o[0], o[0] + s[0], o[1], o[1] + s[1], c.get('rotation')))
