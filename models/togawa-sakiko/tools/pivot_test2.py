import json, math, itertools, statistics

P = r'F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json'
d = json.load(open(P, encoding='utf-8'))
bones = d['minecraft:geometry'][0]['bones']


def Rax(ax, a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    if ax == 'x':
        return [[1, 0, 0], [0, c, -s], [0, s, c]]
    if ax == 'y':
        return [[c, 0, s], [0, 1, 0], [-s, 0, c]]
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]

def mm(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

def mv(A, v):
    return [sum(A[i][k] * v[k] for k in range(3)) for i in range(3)]

fs = next(b for b in bones if b['name'] == 'FrontSkirt')
rowA = [c for c in fs['cubes'] if abs(c['size'][0] - 1.2557) < 1e-4]

for order in ['xyz', 'zyx', 'xyz_star', 'zyx_star']:
    pts = []
    for c in rowA:
        o, s = c['origin'], c['size']
        ctr = [o[i] + s[i] / 2 for i in range(3)]
        p = c['pivot']
        r = dict(zip('xyz', c['rotation']))
        if order == 'xyz':
            R = mm(mm(Rax('x', r['x']), Rax('y', r['y'])), Rax('z', r['z']))
        elif order == 'zyx':
            R = mm(mm(Rax('z', r['z']), Rax('y', r['y'])), Rax('x', r['x']))
        elif order == 'xyz_star':  # negate z
            R = mm(mm(Rax('x', r['x']), Rax('y', r['y'])), Rax('z', -r['z']))
        else:
            R = mm(mm(Rax('z', -r['z']), Rax('y', r['y'])), Rax('x', r['x']))
        dv = [ctr[i] - p[i] for i in range(3)]
        moved = [p[i] + mv(R, dv)[i] for i in range(3)]
        pts.append((ctr, moved))
    ys = [q[1][1] for q in pts]
    # best-fit circle center in xz
    mx = sum(q[1][0] for q in pts) / len(pts)
    mz = sum(q[1][2] for q in pts) / len(pts)
    rs = [math.hypot(q[1][0] - mx, q[1][2] - mz) for q in pts]
    print(f'{order:9s} y[{min(ys):6.2f},{max(ys):6.2f}] spread={max(ys)-min(ys):5.2f} rmean={statistics.mean(rs):5.2f} rspread={max(rs)-min(rs):5.2f} center=({mx:.2f},{mz:.2f})')
