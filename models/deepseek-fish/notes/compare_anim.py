import json, glob, os

a = r'dist\bb-agent-app\templates\ysm_default'
b = r'workspace\_hosttest\workspaces\demo\pack'

def load(root):
    out = {}
    for p in glob.glob(os.path.join(root, '**', '*.animation.json'), recursive=True):
        d = json.load(open(p, encoding='utf-8'))
        for n, v in (d.get('animations') or {}).items():
            out[n] = v
    return out

A = load(a)
B = load(b)
for name in ['parcool:jump_charging', 'parcool:charge_jump', 'slashblade:idle', 'garage_kit']:
    x, y = A[name], B[name]
    print('===', name)
    def walk(x, y, path=''):
        if type(x) != type(y):
            print('type', path, type(x), type(y)); return
        if isinstance(x, dict):
            for k in set(x) | set(y):
                if k not in x or k not in y:
                    print('key', path, k, 'missing', k in x, k in y); continue
                walk(x[k], y[k], path + '/' + str(k))
        elif isinstance(x, list):
            if len(x) != len(y):
                print('len', path, len(x), len(y)); return
            for i, (p, q) in enumerate(zip(x, y)):
                walk(p, q, path + f'[{i}]')
        else:
            if x != y:
                print('val', path, repr(x), repr(y))
    walk(x, y)
