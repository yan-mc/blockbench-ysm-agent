import json
P = r'F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json'
m = json.load(open(P, encoding='utf-8'))
hb = [b for b in m['minecraft:geometry'][0]['bones'] if b['name'] == 'HairBack'][0]['cubes']
for c in hb:
    s = c['size']
    if abs(s[1] - 3.9096) < 0.01 or abs(s[1] - 4.1491) < 0.01 or abs(s[1] - 5.41) < 0.01 or abs(s[1] - 5.21) < 0.01:
        print("origin", c['origin'], "size", s, "rot", c.get('rotation'), "pivot", c.get('pivot'))
print("total", len(hb))
