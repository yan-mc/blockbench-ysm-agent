"""
v9 face + eye + crown texture generator for sakiko-melodia  (v3)

World-space face painting + shaped eye islands + crown hair patch.

Head geometry (v9):
  skull  x -3.10..3.10   y 37.55..43.50   front plane z = -3.05
  jaw    x -2.55..2.55   y 36.49..37.57   front plane z = -2.99
  face island (north of skull):  uv [0,0]    size 136 x 166
  jaw  island (north of jaw):    uv [12,166] size 112 x 34
  eye islands: eyelid 96x84 @ (640,912)/(736,912); iris 64x64 @ (832,912)/(928,912)
  crown patch: 64x64 @ (128,960)  [5 side bands 32x12 + up 32x32 + down 32x32]

Eye plates (world):
  eyelid 1.80 x 1.72 x 0.14 @ z -3.13, spans y 38.29..40.01, centre x +-1.10
  iris   1.34 x 1.26 x 0.06 @ z -3.19, spans y 38.44..39.70
"""
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
import math, os, sys

BASE = r"F:\Deepseek_harness\blockbench\models\deepseek-fish\sakiko-melodia\textures\default.png"
OUT = r"F:\Deepseek_harness\blockbench\models\deepseek-fish\build\out"
os.makedirs(OUT, exist_ok=True)

X0, X1 = -3.10, 3.10
SKY0, SKY1 = 37.55, 43.50
JY0, JY1 = 36.49, 37.57
JX0, JX1 = -2.55, 2.55
FACE_UV = (0, 0, 136, 166)
JAW_UV = (12, 166, 112, 34)
EYE_CY, EYE_CX = 38.85, 1.05
EYE_W, EYE_H = 1.66, 1.80
CROWN_UV = (128, 960)

def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v

def mix(c1, c2, t):
    t = clamp(t)
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(c1, c2))

def smoothstep(e0, e1, x):
    if e1 == e0:
        return 0.0 if x < e0 else 1.0
    t = clamp((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)

def blob(wx, wy, cx, cy, rx, ry, power=2.0):
    d = ((wx - cx) / rx) ** 2 + ((wy - cy) / ry) ** 2
    return clamp(1.0 - d) ** (power * 0.5)

SKIN_TOP  = (250, 234, 226)
SKIN_MID  = (245, 219, 210)
SKIN_LOW  = (240, 206, 197)
SKIN_DEEP = (206, 160, 148)
BLUSH     = (231, 140, 126)
BROW      = (84, 76, 94)
LIP       = (186, 112, 106)
LIP_DARK  = (152, 84, 80)

# ============================================================== FACE ART
def face_rgba(wx, wy):
    t = clamp((SKY1 - wy) / (SKY1 - JY0))
    c = mix(SKIN_TOP, SKIN_MID, smoothstep(0.05, 0.45, t))
    c = mix(c, SKIN_LOW, smoothstep(0.62, 0.98, t))
    c = mix(c, SKIN_DEEP, 0.15 * blob(wx, wy, 3.1, 39.3, 1.0, 2.2))
    c = mix(c, SKIN_DEEP, 0.15 * blob(wx, wy, -3.1, 39.3, 1.0, 2.2))
    bang = 1.0 - smoothstep(42.25, 43.5, wy)
    c = mix(c, (217, 186, 177), 0.45 * bang)
    c = mix(c, (212, 176, 166), 0.36 * smoothstep(1.45, 0.45, abs(wx) - 1.9))
    # blush
    b = blob(wx, wy, EYE_CX + 0.05, 38.32, 1.00, 0.56, 2.2)
    b = max(b, blob(wx, wy, -EYE_CX - 0.05, 38.32, 1.00, 0.56, 2.2))
    c = mix(c, BLUSH, 0.52 * b)
    c = mix(c, (252, 210, 200), 0.34 * blob(wx, wy, EYE_CX + 0.05, 38.26, 0.66, 0.34, 2.0))
    c = mix(c, (252, 210, 200), 0.34 * blob(wx, wy, -EYE_CX - 0.05, 38.26, 0.66, 0.34, 2.0))
    # eye socket seating
    for sx in (1, -1):
        cx = sx * EYE_CX
        c = mix(c, (219, 170, 160), 0.50 * blob(wx, wy, cx, EYE_CY + 0.10, EYE_W * 0.70, EYE_H * 0.60, 3.0))
        c = mix(c, (198, 149, 141), 0.44 * blob(wx, wy, cx, EYE_CY + 0.66, EYE_W * 0.58, 0.26, 2.5))
        c = mix(c, (214, 166, 156), 0.24 * blob(wx, wy, cx, EYE_CY - 0.74, EYE_W * 0.55, 0.24, 2.5))
    # nose
    c = mix(c, (218, 172, 161), 0.85 * blob(wx, wy, 0.06, 37.62, 0.14, 0.30, 2.0))
    c = mix(c, (205, 155, 145), 0.62 * blob(wx, wy, 0.10, 37.46, 0.10, 0.08, 2.0))
    c = mix(c, (253, 235, 228), 0.50 * blob(wx, wy, -0.09, 37.50, 0.085, 0.07, 2.0))
    # mouth: small but readable
    mw, my = 0.33, 37.22
    d = ((wx - 0.02) / mw) ** 2 + ((wy - my) / 0.125) ** 2
    if d < 1.0:
        k = (1.0 - d) ** 0.5
        c = mix(c, (196, 116, 108), k)
        if wy > my + 0.015:
            c = mix(c, (146, 78, 76), 0.72 * k)
    # upper lip shadow / lower lip light
    c = mix(c, (206, 155, 147), 0.32 * blob(wx, wy, 0.0, my + 0.155, 0.34, 0.075, 2.0))
    c = mix(c, (250, 214, 205), 0.30 * blob(wx, wy, 0.0, my - 0.105, 0.24, 0.055, 2.0))
    # jaw / chin contour shading
    c = mix(c, (214, 172, 162), 0.36 * (1.0 - smoothstep(36.62, 37.35, wy)))
    c = mix(c, (219, 180, 170), 0.30 * smoothstep(1.55, 2.45, abs(wx)) * (1 - smoothstep(38.6, 40.0, wy)))
    return (c[0], c[1], c[2], 255)


def draw_brows(img, flip_u):
    draw = ImageDraw.Draw(img)
    sx = FACE_UV[2] / (X1 - X0)
    sy = FACE_UV[3] / (SKY1 - SKY0)
    def tx(wx):
        u = (wx - X0) * sx
        return (FACE_UV[2] - 1 - u) if flip_u else u
    def ty(wy):
        return (SKY1 - wy) * sy
    for s in (1, -1):
        inner, outer = s * 0.42, s * 1.76
        y_in, y_out = 40.40, 40.56
        steps = 30
        top, bot = [], []
        for i in range(steps + 1):
            t = i / steps
            wx = inner + (outer - inner) * t
            wy = y_in + (y_out - y_in) * t + 0.04 * math.sin(math.pi * t)
            thick = 0.042 + 0.026 * (1.0 - t) + 0.012 * math.sin(math.pi * t)
            top.append((tx(wx), ty(wy + thick)))
            bot.append((tx(wx), ty(wy - thick)))
        draw.polygon(top + bot[::-1], fill=BROW + (255,))


def make_face(flip_u=False):
    w, h = FACE_UV[2], FACE_UV[3]
    img = Image.new("RGBA", (w, h))
    px = img.load()
    sx, sy = w / (X1 - X0), h / (SKY1 - SKY0)
    for j in range(h):
        wy = SKY1 - (j + 0.5) / sy
        for i in range(w):
            wx = X0 + ((w - 1 - i) + 0.5) / sx if flip_u else X0 + (i + 0.5) / sx
            px[i, j] = face_rgba(wx, wy)
    draw_brows(img, flip_u)
    return img


def make_jaw(flip_u=False):
    w, h = JAW_UV[2], JAW_UV[3]
    img = Image.new("RGBA", (w, h))
    px = img.load()
    sx, sy = w / (JX1 - JX0), h / (JY1 - JY0)
    for j in range(h):
        wy = JY1 - (j + 0.5) / sy
        for i in range(w):
            wx = JX0 + ((w - 1 - i) + 0.5) / sx if flip_u else JX0 + (i + 0.5) / sx
            c = face_rgba(wx, wy)
            k = smoothstep(37.25, 36.55, wy)
            c = mix(c[:3], (202, 160, 150), 0.35 * k)
            px[i, j] = (c[0], c[1], c[2], 255)
    return img

# ============================================================== EYE ART
SS = 4

TOP_KNOTS = [(0.00, 58), (0.06, 41), (0.16, 22), (0.30, 13), (0.50, 10),
             (0.70, 11), (0.85, 15), (0.94, 22), (1.00, 30)]
BOT_KNOTS = [(0.00, 58), (0.06, 69), (0.16, 76), (0.30, 79), (0.50, 81),
             (0.70, 79), (0.85, 70), (0.94, 52), (1.00, 30)]

def _interp(knots, t):
    t = clamp(t)
    for i in range(len(knots) - 1):
        t0, y0 = knots[i]
        t1, y1 = knots[i + 1]
        if t <= t1 or i == len(knots) - 2:
            k = 0.0 if t1 == t0 else clamp((t - t0) / (t1 - t0))
            k = k * k * (3 - 2 * k)
            return y0 + (y1 - y0) * k
    return knots[-1][1]


def make_eyelid(outer_right=True, side=1, W=96, H=104):
    """side=+1 for the character's +x eye, -1 for the -x eye.
    The plate's skin area is painted with the same face function so the plate
    blends into the cheek instead of reading as a raised rectangle."""
    cx_w = side * EYE_CX
    y_top, y_bot = EYE_CY + EYE_H / 2, EYE_CY - EYE_H / 2
    img = Image.new("RGBA", (W, H))
    px = img.load()
    for j in range(H):
        wy = y_top - (j + 0.5) / H * EYE_H
        for i in range(W):
            wx = cx_w + ((i + 0.5) / W - 0.5) * EYE_W
            px[i, j] = face_rgba(wx, wy)
    img = img.resize((W * SS, H * SS), Image.LANCZOS)
    w, h = W * SS, H * SS
    d = ImageDraw.Draw(img, "RGBA")

    def X(t):
        return (t * w) if outer_right else ((1 - t) * w)

    def top(t):
        return _interp(TOP_KNOTS, t) / 84 * h

    def bot(t):
        return _interp(BOT_KNOTS, t) / 84 * h

    n = 260
    poly = [(X(i / n), top(i / n)) for i in range(n + 1)]
    poly += [(X(i / n), bot(i / n)) for i in range(n, -1, -1)]
    d.polygon(poly, fill=(220, 217, 227, 255))

    band = [(X(i / n), top(i / n)) for i in range(n + 1)]
    band += [(X(i / n), min(bot(i / n), top(i / n) + 0.32 * h)) for i in range(n, -1, -1)]
    d.polygon(band, fill=(190, 188, 204, 205))
    b2 = [(X(i / n), max(top(i / n), bot(i / n) - 0.16 * h)) for i in range(n + 1)]
    b2 += [(X(i / n), bot(i / n)) for i in range(n, -1, -1)]
    d.polygon(b2, fill=(232, 210, 204, 155))

    # upper lash: follows the lid, heavier at the outer corner
    lt, lb = [], []
    for i in range(n + 1):
        t = i / n
        x = X(t)
        y = top(t)
        thick = (0.070 + 0.062 * (t ** 1.8)) * h
        lt.append((x, y - thick))
        lb.append((x, y + 0.012 * h))
    d.polygon(lt + lb[::-1], fill=(46, 39, 60, 255))
    wx = X(1.0)
    d.polygon([(wx - (0.10 * w if outer_right else -0.10 * w), top(1.0) - 0.025 * h),
               (wx + (0.040 * w if outer_right else -0.040 * w), top(1.0) - 0.115 * h),
               (wx + (0.01 * w if outer_right else -0.01 * w), top(1.0) + 0.05 * h)],
              fill=(46, 39, 60, 255))
    ix = X(0.0)
    d.polygon([(ix, top(0.0) - 0.03 * h),
               (ix + (0.09 * w if outer_right else -0.09 * w), top(0.09) - 0.012 * h),
               (ix + (0.09 * w if outer_right else -0.09 * w), top(0.09) + 0.02 * h),
               (ix, top(0.0) + 0.03 * h)], fill=(46, 39, 60, 255))

    lid = [(X(i / n), bot(i / n)) for i in range(n + 1)]
    lid += [(X(i / n), bot(i / n) - 0.05 * h) for i in range(n, -1, -1)]
    d.polygon(lid, fill=(197, 141, 128, 205))
    hi = [(X(i / n), bot(i / n) - 0.05 * h) for i in range(n + 1)]
    hi += [(X(i / n), bot(i / n) - 0.10 * h) for i in range(n, -1, -1)]
    d.polygon(hi, fill=(250, 236, 230, 150))

    return img.resize((W, H), Image.LANCZOS)


def make_iris(flip=False, W=80, H=82):
    img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    w, h = W * SS, H * SS
    cx, cy = w * 0.50, h * 0.50
    rx, ry = w * 0.495, h * 0.495

    # vertical iris gradient (light from above), drawn per pixel
    a = np.zeros((h, w, 4), dtype=np.uint8)
    ys, xs = np.mgrid[0:h, 0:w]
    nx = (xs - cx) / rx
    ny = (ys - cy) / ry
    inside = (nx ** 2 + ny ** 2) <= 1.0
    t = np.clip((ys / h), 0, 1)          # 0 top .. 1 bottom
    top_c = np.array([96, 54, 16])
    mid_c = np.array([196, 128, 40])
    bot_c = np.array([252, 206, 112])
    col = np.where(t[:, :, None] < 0.55,
                   top_c + (mid_c - top_c) * (t[:, :, None] / 0.55),
                   mid_c + (bot_c - mid_c) * ((t[:, :, None] - 0.55) / 0.45))
    # rim darkening
    r = np.sqrt(nx ** 2 + ny ** 2)
    rim = np.clip((r - 0.86) / 0.14, 0, 1)
    col = col * (1 - 0.75 * rim[:, :, None])
    a[:, :, :3] = col.astype(np.uint8)
    a[:, :, 3] = np.where(inside, 255, 0).astype(np.uint8)
    img = Image.fromarray(a, "RGBA")
    d = ImageDraw.Draw(img, "RGBA")

    # pupil above centre
    prx, pry = rx * 0.315, ry * 0.335
    pcx, pcy = cx, cy - h * 0.045
    d.ellipse([pcx - prx, pcy - pry, pcx + prx, pcy + pry], fill=(30, 20, 15, 255))
    d.ellipse([pcx - prx * 0.55, pcy - pry * 0.55, pcx + prx * 0.55, pcy + pry * 0.55],
              fill=(14, 10, 9, 255))
    d.arc([pcx - prx * 1.12, pcy - pry * 1.12, pcx + prx * 1.12, pcy + pry * 1.12],
          start=15, end=165, fill=(255, 214, 140, 190), width=int(1.8 * SS))

    # lid occlusion: darken only the part of the iris that is inside the ellipse
    occl_t = np.clip((0.17 - t) / 0.17, 0, 1) ** 0.8
    occl_col = np.array([40, 28, 28])
    col = col * (1 - 0.88 * occl_t[:, :, None]) + occl_col * (0.88 * occl_t[:, :, None])
    a[:, :, :3] = np.clip(col, 0, 255).astype(np.uint8)
    img = Image.fromarray(a, "RGBA")
    d = ImageDraw.Draw(img, "RGBA")

    # pupil above centre
    prx, pry = rx * 0.315, ry * 0.335
    pcx, pcy = cx, cy - h * 0.045
    d.ellipse([pcx - prx, pcy - pry, pcx + prx, pcy + pry], fill=(30, 20, 15, 255))
    d.ellipse([pcx - prx * 0.55, pcy - pry * 0.55, pcx + prx * 0.55, pcy + pry * 0.55],
              fill=(14, 10, 9, 255))
    d.arc([pcx - prx * 1.12, pcy - pry * 1.12, pcx + prx * 1.12, pcy + pry * 1.12],
          start=15, end=165, fill=(255, 214, 140, 190), width=int(1.8 * SS))

    # highlights
    s = -1 if flip else 1
    hx, hy = cx - s * rx * 0.40, cy - ry * 0.36
    d.ellipse([hx - 0.072 * w, hy - 0.072 * w, hx + 0.072 * w, hy + 0.072 * w],
              fill=(255, 255, 255, 255))
    hx2, hy2 = cx + s * rx * 0.18, cy + ry * 0.26
    d.ellipse([hx2 - 0.028 * w, hy2 - 0.028 * w, hx2 + 0.028 * w, hy2 + 0.028 * w],
              fill=(255, 255, 255, 170))
    return img.resize((W, H), Image.LANCZOS)


def compose_eyes(flip_u=False):
    """352x104 strip at (640,912): [R eyelid 96][L eyelid 96][R iris 80][L iris 80]"""
    strip = Image.new("RGBA", (352, 104), (0, 0, 0, 0))
    strip.paste(make_eyelid(outer_right=not flip_u, side=1), (0, 0))
    strip.paste(make_eyelid(outer_right=flip_u, side=-1), (96, 0))
    hl_flip = flip_u
    strip.paste(make_iris(flip=hl_flip), (192, 0))
    strip.paste(make_iris(flip=hl_flip), (272, 0))
    return strip

# ============================================================== CROWN HAIR
def make_crown():
    """64x64 @ (128,960): side bands L1..L5 (x 0..31, 12px each),
       up face (x 32..63, y 0..31), down face (x 32..63, y 32..63)."""
    img = Image.new("RGBA", (64, 64), (220, 230, 245, 255))
    px = img.load()
    bands = [(184, 198, 220), (200, 212, 232), (214, 226, 243), (228, 237, 250), (239, 245, 253)]
    for bi, base in enumerate(bands):
        for j in range(12):
            k = j / 11.0
            col = mix(base, (base[0] - 16, base[1] - 16, base[2] - 14), 0.55 * k)
            for i in range(32):
                # faint vertical strand variation
                v = 0.5 + 0.5 * math.sin(i * 0.55 + bi)
                cc = mix(col, (col[0] + 8, col[1] + 9, col[2] + 9), 0.10 * v)
                px[i, bi * 12 + j] = (cc[0], cc[1], cc[2], 255)
    # up face: light with soft radial
    for j in range(32):
        for i in range(32):
            dx, dy = (i - 15.5) / 16, (j - 15.5) / 16
            r = math.sqrt(dx * dx + dy * dy)
            c = mix((242, 248, 255), (206, 220, 240), smoothstep(0.15, 1.0, r))
            px[32 + i, j] = (c[0], c[1], c[2], 255)
    for j in range(32):
        for i in range(32):
            c = mix((186, 200, 220), (160, 176, 200), j / 31.0)
            px[32 + i, 32 + j] = (c[0], c[1], c[2], 255)
    return img


if __name__ == "__main__":
    flip = len(sys.argv) > 1 and sys.argv[1] == "flip"
    face = make_face(flip_u=flip)
    jaw = make_jaw(flip_u=flip)
    eyes = compose_eyes(flip_u=flip)
    crown = make_crown()
    face.save(os.path.join(OUT, "face.png"))
    jaw.save(os.path.join(OUT, "jaw.png"))
    eyes.save(os.path.join(OUT, "eyes.png"))
    crown.save(os.path.join(OUT, "crown.png"))
    prev = Image.open(BASE).convert("RGBA")
    prev.paste(face, (0, 0))
    prev.paste(jaw, (12, 166))
    prev.paste(eyes, (640, 912))
    prev.paste(crown, (128, 960))
    prev.save(os.path.join(OUT, "default_merged.png"))
    prev.crop((0, 0, 136, 205)).resize((136 * 4, 205 * 4), Image.NEAREST).save(os.path.join(OUT, "face_preview_x4.png"))
    prev.crop((640, 912, 992, 1016)).resize((352 * 2, 104 * 2), Image.NEAREST).save(os.path.join(OUT, "eyes_preview_x2.png"))
    print("saved flip=", flip)





