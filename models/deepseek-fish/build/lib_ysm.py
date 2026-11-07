# -*- coding: utf-8 -*-
"""Tiny helper library: atlas, materials, cube/bone emitter for BB/YSM bedrock geometry."""
import json, math, os
import numpy as np

# ---------------------------------------------------------------- palette
def hx(s):
    s = s.lstrip('#')
    return np.array([int(s[i:i+2], 16) for i in (0, 2, 4)], dtype=np.float64)

def mix(a, b, t):
    return np.array(a, dtype=np.float64) * (1 - t) + np.array(b, dtype=np.float64) * t

def dk(c, k):
    return np.array(c, dtype=np.float64) * k

def lt(c, k):
    return np.clip(np.array(c, dtype=np.float64) * k + (k - 1) * 26, 0, 255)

P = dict(
    # ---- hair: icy silver-blue
    hair_hi   = hx('#F2F7FD'),
    hair_lt   = hx('#DCE9F7'),
    hair_mid  = hx('#C0D3E9'),
    hair_dk   = hx('#9DB2D0'),
    hair_deep = hx('#7789AA'),
    hair_sh   = hx('#5C6C8C'),
    # ---- skin
    skin      = hx('#F8DFD4'),
    skin_lt   = hx('#FDF0E9'),
    skin_sh   = hx('#E4BCAE'),
    skin_deep = hx('#CB9C8E'),
    # ---- black cloth
    bk0 = hx('#0A090F'),
    bk1 = hx('#1A1924'),
    bk2 = hx('#2A2838'),
    bk3 = hx('#3D3A50'),
    bk4 = hx('#544F6C'),
    # ---- periwinkle blue
    bl0 = hx('#383A62'),
    bl1 = hx('#4C4F7E'),
    bl2 = hx('#686C9E'),
    bl3 = hx('#8B8FBE'),
    bl4 = hx('#B4B8DE'),
    # ---- silver / white
    sv0 = hx('#8A93A6'),
    sv1 = hx('#B7BFCE'),
    sv2 = hx('#DCE2EC'),
    wh  = hx('#F6F7FB'),
    # ---- eyes
    eye_a = hx('#5A3410'),
    eye_b = hx('#A8701F'),
    eye_c = hx('#DFAF52'),
    eye_d = hx('#F6D98C'),
    lash  = hx('#2A2130'),
    # ---- accents
    gem   = hx('#A9E4FA'),
    gem_d = hx('#4E9CCB'),
    gold  = hx('#C9A254'),
    rose  = hx('#E8A8A0'),
    bt0 = hx('#09080D'), bt1 = hx('#191824'), bt2 = hx('#2B2938'), bt3 = hx('#3E3B50'),
    st0 = hx('#0E0D14'), st1 = hx('#1E1D28'), st2 = hx('#302E3E'),
    lip = hx('#C4827C'),
)

# ---------------------------------------------------------------- atlas
class Atlas:
    """Shelf packer with best-height-fit (dense enough for our item mix)."""

    def __init__(self, size=512, margin=1):
        self.size, self.margin = size, margin
        self.shelves = []          # [y, height, cursor_x]
        self.next_y = 0
        self.used = 0

    def alloc(self, w, h):
        wi = max(1, int(math.ceil(w)))
        hi = max(1, int(math.ceil(h)))
        m = self.margin
        W, H = wi + m, hi + m
        S = self.size
        best = None
        for i, (y, sh, cx) in enumerate(self.shelves):
            if sh >= H and cx + W <= S:
                waste = sh - H
                if best is None or waste < best[0]:
                    best = (waste, i)
        if best is not None:
            i = best[1]
            y, sh, cx = self.shelves[i]
            self.shelves[i][2] = cx + W
            self.used += wi * hi
            return (cx, y, wi, hi)
        y = self.next_y
        if y + H > S:
            raise RuntimeError('atlas overflow %dx%d' % (wi, hi))
        self.shelves.append([y, H, W])
        self.next_y = y + H
        self.used += wi * hi
        return (0, y, wi, hi)


# ---------------------------------------------------------------- materials
class Mat:
    """A paint recipe producing per-face pixel blocks."""

    def __init__(self, top, bot=None, up=None, dn=None, deco=None, side_k=1.0):
        self.top = np.array(top, float)
        self.bot = np.array(bot if bot is not None else dk(top, 0.74), float)
        self.up = np.array(up if up is not None else lt(top, 1.10), float)
        self.dn = np.array(dn if dn is not None else dk(top, 0.60), float)
        self.deco = deco
        self.side_k = side_k

    def paint(self, w, h, kind):
        if kind == 'up':
            a = np.tile(self.up, (h, w, 1))
        elif kind == 'down':
            a = np.tile(self.dn, (h, w, 1))
        else:
            t = (np.arange(h) / max(h - 1, 1))[:, None, None]
            row = self.top[None, None, :] * (1 - t) + self.bot[None, None, :] * t
            a = np.tile(row, (1, w, 1))
            if kind in ('east', 'west'):
                a = a * self.side_k
                a[:, :, 2] = np.minimum(255, a[:, :, 2] * 1.03)
        if self.deco is not None:
            a = self.deco(a, kind, w, h)
        return np.clip(a, 0, 255)


def _rng(seed):
    r = np.random.RandomState(seed)
    return r


def deco_hair(seed=1, strands=5, hi_band=True):
    """vertical strand lines + soft highlight band; makes hair read as hair."""
    def f(a, kind, w, h):
        r = _rng(seed)
        if kind in ('up', 'down'):
            return a
        for i in range(strands):
            x = int(r.randint(0, max(1, w)))
            k = r.uniform(0.86, 0.95)
            a[:, x, :] *= k
            if x + 1 < w:
                a[:, x + 1, :] *= (k + 1) / 2
        if hi_band and h > 5:
            y0 = int(h * 0.18); y1 = int(h * 0.42)
            a[y0:y1, :, :] = np.clip(a[y0:y1, :, :] * 1.10 + 8, 0, 255)
            a[y0:y0 + 1, :, :] = np.clip(a[y0:y0 + 1, :, :] * 1.16 + 12, 0, 255)
        return a
    return f


def deco_cloth(seed=3, amp=0.05):
    def f(a, kind, w, h):
        r = _rng(seed)
        if kind in ('up', 'down'):
            return a
        n = r.uniform(-amp, amp, size=(h, w, 1))
        a = a * (1 + n)
        return a
    return f


def deco_metal(seed=5):
    def f(a, kind, w, h):
        if kind in ('up', 'down'):
            return np.clip(a * 1.05, 0, 255)
        if h > 2 and w > 1:
            y = min(h - 1, max(1, int(h * 0.26)))
            a[y, :, :] = np.clip(a[y, :, :] * 1.33 + 16, 0, 255)
        return a
    return f


def deco_lace(seed=7, notch=3, dark=0.45):
    """hem lace: dark band with periodic notches."""
    def f(a, kind, w, h):
        if kind in ('up', 'down'):
            return a * dark
        if h < 3:
            return a
        y0 = max(0, h - max(2, int(h * 0.22)))
        a[y0:, :, :] *= dark
        for x in range(0, w, notch):
            a[y0:, x, :] = np.clip(a[y0:, x, :] * 1.9 + 10, 0, 255)
        return a
    return f


def deco_stripe(seed=11, period=4, k=0.5):
    def f(a, kind, w, h):
        if kind in ('up', 'down'):
            return a
        for x in range(0, w, period):
            a[:, x, :] *= k
        return a
    return f


def deco_fold(seed=13, light=1.22, dark=0.78):
    """Per-panel fold: one lit edge + one shadowed edge -> reads as draped cloth."""
    def f(a, kind, w, h):
        if kind in ('up', 'down') or w < 4:
            return a
        x1 = max(1, int(w * 0.30)); x2 = max(x1 + 1, int(w * 0.62))
        a[:, :max(1, int(w * 0.14)), :] = np.clip(a[:, :max(1, int(w * 0.14)), :] * light + 6, 0, 255)
        if x1 > 1:
            a[:, 1:x1, :] = np.clip(a[:, 1:x1, :] * 1.07, 0, 255)
        a[:, x2:w, :] = a[:, x2:w, :] * dark
        return a
    return f


# ---------------------------------------------------------------- model build
class Builder:
    def __init__(self, skeleton, tex_size=512, D=4.0):
        self.bones = []          # ordered dicts
        self.bmap = {}
        self.atlas = Atlas(tex_size)
        self.D = D
        self.paint_ops = []      # (x,y,w,h, Mat, kind)
        self.tex_size = tex_size
        for name, parent, pivot in skeleton:
            self.bone(name, parent, pivot)

    def bone(self, name, parent=None, pivot=(0, 0, 0)):
        if name in self.bmap:
            return self.bmap[name]
        b = {'name': name, 'pivot': [round(v, 4) for v in pivot]}
        if parent:
            b['parent'] = parent
        b['cubes'] = []
        self.bones.append(b)
        self.bmap[name] = b
        return b

    def set_pivot(self, name, pivot):
        self.bmap[name]['pivot'] = [round(v, 4) for v in pivot]

    def cube(self, bone, org, size, mat, rot=None, piv=None, faces=None,
             facename=None, paint_faces=None):
        """faces: dict face_kind -> (x,y,w,h) override rect in texture pixels."""
        b = self.bmap[bone]
        dx, dy, dz = [abs(float(v)) for v in size]
        D = self.D
        W = max(1, int(round(dx * D)))
        H = max(1, int(round(dy * D)))
        Pp = max(1, int(round(dz * D)))
        ru, rv, _rw, _rh = self.atlas.alloc(W * 2 + Pp * 2, H + Pp)
        u, v = ru, rv
        rects = {
            'west':  (u,       v + Pp, Pp, H),
            'north': (u + Pp,  v + Pp, W,  H),
            'east':  (u + Pp + W, v + Pp, Pp, H),
            'south': (u + Pp + W + Pp, v + Pp, W, H),
            'up':    (u + Pp,  v,      W,  Pp),
            'down':  (u + Pp + W, v,   W,  Pp),
        }
        if faces:
            for k, r in faces.items():
                rects[k] = r
        uvobj = {}
        for k, (rx, ry, rw, rh) in rects.items():
            uvobj[k] = {'uv': [int(rx), int(ry)], 'uv_size': [int(rw), int(rh)]}
            if not (faces and k in faces):
                self.paint_ops.append((int(rx), int(ry), int(rw), int(rh), mat, k))
        c = {'origin': [round(float(o), 4) for o in org],
             'size': [round(dx, 4), round(dy, 4), round(dz, 4)],
             'uv': uvobj}
        if rot is not None and any(abs(r) > 1e-6 for r in rot):
            c['rotation'] = [round(float(r), 4) for r in rot]
            c['pivot'] = [round(float(p), 4) for p in (piv if piv is not None
                                                        else (org[0] + dx / 2, org[1] + dy / 2, org[2] + dz / 2))]
        if facename:
            c['name'] = facename
        b['cubes'].append(c)
        return c

    # convenience: plate rotated about Y at azimuth a, positioned already (pivot at model axis)
    def radial(self, bone, y0, h, r, w, t, ang_deg, mat, tiltsign=0, cy=None):
        """plate tangent to circle radius r at azimuth ang; width along tangent."""
        a = ang_deg
        box = self.cube(bone,
                        (r - t / 2, y0, -w / 2),
                        (t, h, w), mat,
                        rot=(0, a, 0),
                        piv=(0, cy if cy is not None else (y0 + h / 2), 0))
        return box

    def to_json(self, ident='geometry.unknown'):
        bones = []
        for b in self.bones:
            nb = {'name': b['name'], 'pivot': b['pivot']}
            if b.get('parent'):
                nb['parent'] = b['parent']
            rot = b.get('rotation')
            if rot and any(abs(v) > 1e-6 for v in rot):
                nb['rotation'] = [round(float(v), 4) for v in rot]
            if b.get('cubes'):
                nb['cubes'] = b['cubes']
            bones.append(nb)
        return {
            'format_version': '1.12.0',
            'minecraft:geometry': [{
                'description': {
                    'identifier': ident,
                    'texture_width': self.tex_size,
                    'texture_height': self.tex_size,
                    'visible_bounds_width': 7,
                    'visible_bounds_height': 7,
                    'visible_bounds_offset': [0, 0.5, 0],
                },
                'bones': bones,
            }]
        }

    def render_texture(self, bg=(0, 0, 0, 0)):
        img = np.zeros((self.tex_size, self.tex_size, 4), float)
        img[:, :, :] = bg
        for (x, y, w, h, mat, kind) in self.paint_ops:
            if w <= 0 or h <= 0:
                continue
            block = mat.paint(w, h, kind)
            img[y:y + h, x:x + w, :3] = block
            img[y:y + h, x:x + w, 3] = 255
        return img
