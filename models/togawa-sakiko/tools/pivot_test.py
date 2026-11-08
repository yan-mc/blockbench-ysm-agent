import json, math

P = r'F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json'
d = json.load(open(P, encoding='utf-8'))
bones = d['minecraft:geometry'][0]['bones']


def Rx(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return [[1, 0, 0], [0, c, -s], [0, s, c]]

def Ry(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]

def Rz(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]

def mm(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

def mv(A, v):
    return [sum(A[i][k] * v[k] for k in range(3)) for i in range(3)]

def Rxyz(r):
    return mm(mm(Rx(r[0]), Ry(r[1])), Rz(r[2]))

# row-A cubes of FrontSkirt
fs = next(b for b in bones if b['name'] == 'FrontSkirt')
rowA = [c for c in fs['cubes'] if abs(c['size'][0] - 1.2557) < 1e-4]
print('rowA count', len(rowA))
for c in rowA:
    o, s, r, p = c['origin'], c['size'], c['rotation'], c['pivot']
    ctr = [o[i] + s[i] / 2 for i in range(3)]
    R = Rxyz(r)
    d_ = [ctr[i] - p[i] for i in range(3)]
    moved = [p[i] + mv(R, d_)[i] for i in range(3)]
    print('center2', [round(v, 2) for v in ctr], 'pivot-based', [round(v, 2) for v in moved])
