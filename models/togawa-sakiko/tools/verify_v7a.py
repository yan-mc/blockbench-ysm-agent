import json, math, os, shutil
from PIL import Image

ROOT = r'F:\Deepseek_harness\blockbench\models\togawa-sakiko'
OUT = os.path.join(ROOT, 'artifacts', 'v7a')
SRC = os.path.join(ROOT, 'artifacts', 'renders', 'r0048')
os.makedirs(OUT, exist_ok=True)

# ---------- 1. geometry verification (inverse-mirror to editor space) ----------
d = json.load(open(os.path.join(ROOT, 'pack', 'models', 'main.json'), encoding='utf-8'))
bones = d['minecraft:geometry'][0]['bones']
KEEP = ['Skirt', 'FrontSkirt', 'BackSkirt', 'LeftSkirt', 'RightSkirt']
CX, CZ = -0.15, 0.0

cubes = []
for b in bones:
    if b['name'] not in KEEP:
        continue
    for c in b['cubes']:
        o = c['origin']; s = c['size']
        # editor space: ex = -(json_x + sx)
        ex = -(o[0] + s[0]); ey = o[1]; ez = o[2]
        ctr = (ex + s[0] / 2, ey + s[1] / 2, ez + s[2] / 2)
        cubes.append({'bone': b['name'], 'ctr': ctr, 'size': s,
                      'rot': [-c['rotation'][0], -c['rotation'][1], c['rotation'][2]]})
print('skirt cubes', len(cubes), 'per bone', {b: sum(1 for c in cubes if c['bone'] == b) for b in KEEP})

def ring(layer_pred):
    sel = [c for c in cubes if layer_pred(c)]
    xs = [c['ctr'][0] for c in sel]; zs = [c['ctr'][2] for c in sel]
    ys = [c['ctr'][1] for c in sel]
    return sum(xs) / len(xs), sum(zs) / len(zs), min(ys), max(ys), len(sel)

top = ring(lambda c: c['ctr'][1] > 23.30)      # waistband ring
bot = ring(lambda c: c['ctr'][1] < 13.60)      # pale edge ring
print('top ring   cx=%.3f cz=%.3f y[%.2f,%.2f] n=%d' % top)
print('bottom ring cx=%.3f cz=%.3f y[%.2f,%.2f] n=%d' % bot)

def azim(c):
    return math.degrees(math.atan2(c['ctr'][0] - CX, -(c['ctr'][2] - CZ)))

def lowest_at(pred, target):
    sel = [c for c in cubes if pred(c)]
    best = min(sel, key=lambda c: abs((azim(c) - target + 180) % 360 - 180))
    return best['ctr'][1] - best['size'][1] / 2, best['bone']

# lowest hem per azimuth: lowest cube overall in that direction
def hem(target, tol=16):
    sel = [c for c in cubes if abs((azim(c) - target + 180) % 360 - 180) < tol]
    best = min(sel, key=lambda c: c['ctr'][1] - c['size'][1] / 2)
    return best['ctr'][1] - best['size'][1] / 2
for lab, t in [('front', 0), ('side', 90), ('back', 180)]:
    print('hem %-5s y=%.2f' % (lab, hem(t)))

# mirror error
pairs = 0; maxerr = 0.0
for c in cubes:
    tx = 2 * CX - c['ctr'][0]
    best = None
    for q in cubes:
        if q is c:
            continue
        e = abs(q['ctr'][0] - tx) + abs(q['ctr'][1] - c['ctr'][1]) + abs(q['ctr'][2] - c['ctr'][2])
        if best is None or e < best:
            best = e
    if best is not None and best < 0.2:
        pairs += 1
        maxerr = max(maxerr, best)
print('mirror: matched %d/%d  max_err=%.3f' % (pairs, len(cubes), maxerr))
tri = sum(1 for c in cubes if all(abs(v) > 0.05 for v in c['rot']))
print('3-axis %.1f%% (%d/%d)' % (100.0 * tri / len(cubes), tri, len(cubes)))
rs = [math.hypot(c['ctr'][0] - CX, c['ctr'][2] - CZ) for c in cubes]
print('radius range %.2f..%.2f' % (min(rs), max(rs)))

# ---------- 2. deliverables: copy renders ----------
names = {'front': 'final-front-2400.png', 'left': 'final-left-2400.png',
         'back': 'final-back-2400.png', 'iso_fr': 'final-iso_fr-2400.png'}
for k, v in names.items():
    shutil.copyfile(os.path.join(SRC, k + '_2400.png'), os.path.join(OUT, v))

# ---------- 3. closeups from the 2400 renders ----------
def crop(side, box, name, scale=2.0):
    im = Image.open(os.path.join(SRC, side + '_2400.png')).convert('RGBA')
    c = im.crop(box)
    c = c.resize((int(c.width * scale), int(c.height * scale)), Image.NEAREST)
    c.save(os.path.join(OUT, name))
    print('crop', name, c.size)

# waist closeup (front) + skirt front / side / back
crop('front', (1000, 980, 1400, 1330), 'closeup-waist-front-2x.png', 2.6)
crop('front', (930, 1120, 1470, 1720), 'closeup-skirt-front-2x.png', 2.0)
crop('left', (900, 1120, 1440, 1720), 'closeup-skirt-side-2x.png', 2.0)
crop('back', (930, 1120, 1470, 1720), 'closeup-skirt-back-2x.png', 2.0)

# ---------- 4. T3 comparison sheet ----------
REF = os.path.join(ROOT, 'artifacts', 'refstudy')
panels = ['t3-panel5-front.png', 't3-panel5-side.png', 't3-panel5-back.png']
ours = ['final-front-2400.png', 'final-left-2400.png', 'final-back-2400.png']
H = 900
cells = []
def flatten(im):
    bg = Image.new('RGB', im.size, (255, 255, 255))
    bg.paste(im, (0, 0), im)
    return bg

for p, o in zip(panels, ours):
    a = Image.open(os.path.join(REF, p)).convert('RGB')
    a = a.resize((int(a.width * H / a.height), H))
    b = flatten(Image.open(os.path.join(OUT, o)).convert('RGBA'))
    b = b.resize((int(b.width * H / b.height), H))
    cells.append((a, b))
pad = 16
W = sum(max(a.width, b.width) + pad for a, b in cells) + pad
sheet = Image.new('RGB', (W, H * 2 + pad * 3), (250, 250, 250))
x = pad
for a, b in cells:
    sheet.paste(a, (x + (max(a.width, b.width) - a.width) // 2, pad))
    sheet.paste(b, (x + (max(a.width, b.width) - b.width) // 2, H + pad * 2))
    x += max(a.width, b.width) + pad
sheet.save(os.path.join(OUT, 'compare-t3-vs-v7a.png'))
print('sheet', sheet.size)
