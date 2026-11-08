import json
d = json.load(open(r'F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json', encoding='utf-8'))
bones = d['minecraft:geometry'][0]['bones']
print("== non-zero rest rotations")
for b in bones:
    r = b.get('rotation')
    if r and any(abs(x) > 1e-6 for x in r):
        print(f"{b['name']:20s} rot={r} pivot={b.get('pivot')} cubes={len(b.get('cubes', []))}")
print("\n== key bones")
for b in bones:
    if b['name'] in ('Cape', 'CapeLow', 'Skirt', 'BackSkirt', 'LeftSkirt', 'RightSkirt', 'FrontSkirt',
                     'HairBack', 'LongHair', 'TwinTail_L', 'TwinTail_R', 'hl_side', 'Hair', 'Head'):
        print(f"{b['name']:12s} rot={b.get('rotation')} pivot={b.get('pivot')} parent={b.get('parent')}")

print("\n== HairBack bottom distribution (y=origin bottom)")
import collections
cs = [c for b in bones if b['name'] == 'HairBack' for c in b['cubes']]
print("n", len(cs))
by = sorted(cs, key=lambda c: c['origin'][1])
for c in by[:18]:
    o = c['origin']; s = c['size']
    print(f"  o=({o[0]:6.2f},{o[1]:6.2f},{o[2]:5.2f}) s=({s[0]:4.2f},{s[1]:4.2f},{s[2]:4.2f}) rot={c.get('rotation')}")
print("...")
print("y<=18 count", sum(1 for c in cs if c['origin'][1] <= 18))
print("y<=19.5 count", sum(1 for c in cs if c['origin'][1] <= 19.5))
