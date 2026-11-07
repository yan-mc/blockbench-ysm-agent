# -*- coding: utf-8 -*-
"""
Sakiko / Master of Melodia  --  YSM model builder  (v7, single source of truth)

LAYER 1  标准档：体素特征尺度 ~1.35（方块平均边 1.3-1.6），贴图 1024
LAYER 2  剪影：头宽 6.2（非 7）、头身比 ~4.9、梨形、A 字长裙 + 侧发外扩
LAYER 3  形态：冷淡锐利的脸、直刘海 + 鬓发贴颊、羊角卷、黑裙/蓝衬裙/银白边
LAYER 4  方块
"""
import json, math, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_ysm import (Atlas, Mat, Builder, P as C, hx, mix, dk, lt,
                     deco_hair, deco_cloth, deco_metal, deco_lace, deco_stripe, deco_fold)

TS  = 1024
WS  = r"F:\Deepseek_harness\blockbench\models\deepseek-fish"
OUT = os.path.join(WS, "build", "out")
os.makedirs(OUT, exist_ok=True)

# ------------------------------------------------------------------ LAYOUT
Y_ANKLE  = 3.80
Y_KNEE   = 14.20
Y_CROTCH = 23.00
Y_WAIST  = 26.60
Y_SHLDR  = 34.60
Y_CHIN   = 35.90
Y_JAW    = 37.45
Y_SKULL  = 45.00
X_LEG    = 1.90
X_ARM    = 4.70

DF       = 22.0
FX0, FY0 = 1, 1
FW       = int(round(6.20 * DF))
FH       = int(round((Y_SKULL - Y_CHIN) * DF))


def fx(wx): return (wx + 3.10) * DF
def fy(wy): return (Y_SKULL - wy) * DF


def face_rect(wx0, wx1, wy0, wy1):
    x = int(round(fx(wx0))); y = int(round(fy(wy1)))
    w = int(round((wx1 - wx0) * DF)); h = int(round((wy1 - wy0) * DF))
    return (FX0 + x, FY0 + y, max(1, w), max(1, h))


# ------------------------------------------------------------------ SKELETON
SKEL = [
    ('Root', None, (0, 0, 0)),
    ('MAllBody', 'Root', (0, Y_CROTCH, 0)),
    ('AllBody', 'MAllBody', (0, Y_CROTCH, 0)),
    ('UpBody', 'AllBody', (0, Y_CROTCH, 0)),
    ('UpperBody', 'UpBody', (0, Y_CROTCH, 0)),
    ('AllHead', 'UpperBody', (0, Y_CHIN + 0.1, 0)),
    ('MHead', 'AllHead', (0, Y_CHIN + 0.6, 0)),
    ('Head', 'MHead', (0, Y_CHIN + 0.6, 0)),
    ('Hair', 'Head', (0, 43.40, 0)),
    ('Bangs', 'Head', (0, 43.30, -3.10)),
    ('SideLockL', 'Head', (2.60, 42.20, -2.90)),
    ('SideLockR', 'Head', (-2.60, 42.20, -2.90)),
    ('BackHair1', 'Hair', (0, 42.60, 2.60)),
    ('BackHair2', 'BackHair1', (0, 34.20, 2.90)),
    ('BackHair3', 'BackHair2', (0, 27.60, 2.70)),
    ('TailL1', 'Hair', (3.20, 42.20, 0.50)),
    ('TailL2', 'TailL1', (4.05, 33.60, 0.70)),
    ('TailL3', 'TailL2', (4.45, 25.60, 0.90)),
    ('TailR1', 'Hair', (-3.20, 42.20, 0.50)),
    ('TailR2', 'TailR1', (-3.95, 34.60, 0.70)),
    ('RibbonL', 'Hair', (3.10, 42.40, 0.40)),
    ('RibbonR', 'Hair', (-3.10, 42.40, 0.40)),
    ('HornL', 'Head', (2.30, 43.60, 0.60)),
    ('HornR', 'Head', (-2.30, 43.60, 0.60)),
    ('front_h1', 'Hair', (0, 42.90, -3.00)),
    ('corner_h1', 'Hair', (-3.00, 42.00, -1.80)),
    ('FLongHair', 'Hair', (0, 40.00, 2.60)),
    ('MLongHair', 'FLongHair', (0, 34.00, 2.80)),
    ('LongHair', 'MLongHair', (0, 28.00, 2.70)),
    ('hl_side', 'LongHair', (0, 32.70, 2.60)),
    ('hl_m', 'LongHair', (0, 38.10, 2.40)),
    ('Ribbon', 'Hair', (-3.60, 40.00, 2.00)),
    ('Face', 'Head', (0, 38.00, -3.00)),
    ('Eyes', 'Face', (0, 38.00, -3.00)),
    ('Eyebrow', 'Eyes', (0, 40.30, -3.10)),
    ('RightEyebrow', 'Eyebrow', (-1.20, 40.30, -3.10)),
    ('LeftEyebrow', 'Eyebrow', (1.20, 40.30, -3.10)),
    ('Eyelid', 'Eyes', (0, 39.10, -3.10)),
    ('RightEyelid', 'Eyelid', (-1.20, 39.10, -3.10)),
    ('RightEyesBase', 'RightEyelid', (-1.20, 39.10, -3.12)),
    ('RightPupil', 'RightEyesBase', (-1.20, 39.10, -3.16)),
    ('LeftEyelid', 'Eyelid', (1.20, 39.10, -3.10)),
    ('LeftEyesBase', 'LeftEyelid', (1.20, 39.10, -3.12)),
    ('LeftPupil', 'LeftEyesBase', (1.20, 39.10, -3.16)),
    ('LeftShoulderLocator', 'Head', (3.00, 34.20, 0)),
    ('RightShoulderLocator', 'Head', (-3.00, 34.20, 0)),
    ('Breast', 'UpperBody', (0, 30.80, -2.00)),
    ('Arm', 'UpperBody', (0, Y_SHLDR, 0)),
    ('LeftArm', 'Arm', (X_ARM, 34.05, 0)),
    ('LeftForeArm', 'LeftArm', (X_ARM + 0.15, 28.65, 0)),
    ('LeftHand', 'LeftForeArm', (X_ARM + 0.15, 23.60, 0)),
    ('LeftHandLocator', 'LeftHand', (X_ARM + 0.15, 23.60, 0)),
    ('SheathLocator', 'LeftHand', (X_ARM + 0.15, 23.60, 0)),
    ('LeftWaistLocator', 'LeftHand', (X_ARM + 0.15, 23.60, 0)),
    ('RightArm', 'Arm', (-X_ARM, 34.05, 0)),
    ('RightForeArm', 'RightArm', (-X_ARM - 0.15, 28.65, 0)),
    ('RightHand', 'RightForeArm', (-X_ARM - 0.15, 23.60, 0)),
    ('RightHandLocator', 'RightHand', (-X_ARM - 0.15, 23.60, 0)),
    ('BladeLocator', 'RightHand', (-X_ARM - 0.15, 23.60, 0)),
    ('Collar', 'UpperBody', (0, 34.20, 0)),
    ('ElytraLocator', 'UpperBody', (0, 31.65, 2.00)),
    ('RifleLocator', 'UpperBody', (0, 25.15, 2.30)),
    ('BackpackLocator', 'UpperBody', (0, 30.00, 0)),
    ('PistolLocator', 'UpBody', (-4.00, 24.75, -1.60)),
    ('RightWaistLocator', 'UpBody', (-3.00, 26.60, 0)),
    ('DownBody', 'AllBody', (0, Y_CROTCH, 0)),
    ('Leg', 'DownBody', (0, Y_CROTCH, 0)),
    ('LeftLeg', 'Leg', (X_LEG, Y_CROTCH, 0)),
    ('LeftLowerLeg', 'LeftLeg', (X_LEG, Y_KNEE, 0)),
    ('LeftFoot', 'LeftLowerLeg', (X_LEG, Y_ANKLE, 0.10)),
    ('RightLeg', 'Leg', (-X_LEG, Y_CROTCH, 0)),
    ('RightLowerLeg', 'RightLeg', (-X_LEG, Y_KNEE, 0)),
    ('RightFoot', 'RightLowerLeg', (-X_LEG, Y_ANKLE, 0.10)),
    ('Skirt', 'DownBody', (0, Y_WAIST, 0)),
    ('FrontSkirt', 'Skirt', (0, Y_WAIST, 0)),
    ('BackSkirt', 'Skirt', (0, Y_WAIST, 0)),
    ('LeftSkirt', 'Skirt', (0, Y_WAIST, 0)),
    ('RightSkirt', 'Skirt', (0, Y_WAIST, 0)),
    ('Effect', 'Root', (0, 26.00, -1.00)),
    ('molang', 'Root', (0, -0.35, 0)),
]

# ------------------------------------------------------------------ MATERIALS
M = {}
M['hair']    = Mat(C['hair_lt'], C['hair_mid'], up=C['hair_lt'], dn=dk(C['hair_dk'], 0.92), deco=deco_hair(1, 4))
M['hair2']   = Mat(C['hair_mid'], C['hair_dk'], up=C['hair_lt'], dn=dk(C['hair_deep'], 0.95), deco=deco_hair(7, 4))
M['hair3']   = Mat(C['hair_dk'], C['hair_deep'], up=C['hair_mid'], dn=C['hair_sh'], deco=deco_hair(13, 3))
M['hair_hi'] = Mat(C['hair_hi'], C['hair_lt'], up=C['hair_lt'], dn=C['hair_mid'], deco=deco_hair(21, 3), side_k=0.98)
M['hair_dp'] = Mat(C['hair_deep'], C['hair_sh'], up=C['hair_dk'], dn=dk(C['hair_sh'], 0.85), deco=deco_hair(31, 3))
M['hair_df'] = Mat(C['hair_sh'], dk(C['hair_sh'], 0.82), up=C['hair_deep'], dn=dk(C['hair_sh'], 0.7), deco=deco_hair(41, 2))

M['skin']    = Mat(C['skin'], C['skin_sh'], up=C['skin_lt'], dn=C['skin_deep'])
M['skin2']   = Mat(C['skin_lt'], C['skin'], up=C['skin_lt'], dn=C['skin_sh'])

M['bk']      = Mat(C['bk2'], C['bk1'], up=C['bk3'], dn=C['bk0'], deco=deco_cloth(3, 0.05))
M['bk_l']    = Mat(C['bk3'], C['bk2'], up=C['bk4'], dn=C['bk1'], deco=deco_cloth(5, 0.05))
M['bk_d']    = Mat(C['bk1'], C['bk0'], up=C['bk2'], dn=C['bk0'], deco=deco_cloth(9, 0.04))
M['bk_m']    = Mat(C['bk4'], C['bk3'], up=lt(C['bk4'], 1.16), dn=C['bk2'], deco=deco_cloth(19, 0.04))
M['bk_gl']   = Mat(C['bt2'], C['bt1'], up=C['bt3'], dn=C['bt0'])

M['bkf']     = Mat(C['bk2'], dk(C['bk2'], 0.93), up=C['bk3'], dn=dk(C['bk1'], 0.9), deco=deco_fold(3))
M['bklf']    = Mat(C['bk3'], dk(C['bk3'], 0.93), up=C['bk4'], dn=C['bk2'], deco=deco_fold(5))
M['bkmf']    = Mat(C['bk4'], dk(C['bk4'], 0.94), up=lt(C['bk4'], 1.12), dn=C['bk3'], deco=deco_fold(19))
M['blf']     = Mat(C['bl2'], dk(C['bl2'], 0.93), up=C['bl3'], dn=C['bl1'], deco=deco_fold(4))
M['blf2']    = Mat(C['bl1'], dk(C['bl1'], 0.93), up=C['bl2'], dn=C['bl0'], deco=deco_fold(8))
M['whf']     = Mat(hx('#C9CFDC'), hx('#ADB4C4'), up=hx('#DDE2EC'), dn=hx('#949CAE'), deco=deco_fold(15, 1.16, 0.84))
M['ivory']   = Mat(hx('#D9D6EA'), hx('#B6B2D2'), up=hx('#EFEDF7'), dn=hx('#9E9ABC'), deco=deco_cloth(21, 0.03))
M['ivory2']  = Mat(hx('#E6E3F4'), hx('#C6C2E0'), up=hx('#F4F2FB'), dn=hx('#AAA6C8'), deco=deco_cloth(22, 0.03))
M['panel']   = Mat(hx('#3A3856'), hx('#2C2A42'), up=hx('#4A4768'), dn=hx('#222033'), deco=deco_cloth(23, 0.04))
M['panel2']  = Mat(hx('#46436A'), hx('#34314F'), up=hx('#585478'), dn=hx('#28263A'), deco=deco_cloth(24, 0.04))
M['shpad']   = Mat(hx('#4E4A66'), hx('#3B3850'), up=hx('#615C7C'), dn=hx('#2C2A3C'), deco=deco_cloth(41, 0.05))
M['shpad2']  = Mat(hx('#413E58'), hx('#312E44'), up=hx('#544F6C'), dn=hx('#252333'), deco=deco_cloth(42, 0.05))

M['sv']      = Mat(C['sv2'], C['sv1'], up=C['wh'], dn=C['sv0'], deco=deco_metal(11))
M['sv_d']    = Mat(C['sv1'], C['sv0'], up=C['sv2'], dn=dk(C['sv0'], .8), deco=deco_metal(12))
M['wh_p']    = Mat(C['wh'], C['sv2'], up=C['wh'], dn=C['sv1'], deco=deco_cloth(15, 0.03))

M['bl']      = Mat(C['bl2'], C['bl1'], up=C['bl3'], dn=C['bl0'], deco=deco_cloth(4, 0.05))
M['bl_l']    = Mat(C['bl3'], C['bl2'], up=C['bl4'], dn=C['bl1'], deco=deco_cloth(6, 0.05))
M['bl_d']    = Mat(C['bl1'], C['bl0'], up=C['bl2'], dn=dk(C['bl0'], 0.85), deco=deco_cloth(8, 0.05))
M['bl_hem']  = Mat(C['bl2'], C['bl1'], up=C['bl3'], dn=C['bl0'], deco=deco_lace(17, 3, 0.62))

M['gem']     = Mat(C['gem'], C['gem_d'], up=C['gem'], dn=C['gem_d'], deco=deco_metal(23))
M['gold']    = Mat(C['gold'], dk(C['gold'], .7), up=lt(C['gold'], 1.15), dn=dk(C['gold'], .6), deco=deco_metal(25))
M['st']      = Mat(C['st1'], C['st0'], up=C['st2'], dn=C['st0'], deco=deco_cloth(27, 0.05))
M['st_l']    = Mat(C['st2'], C['st1'], up=lt(C['st2'], 1.2), dn=C['st0'], deco=deco_cloth(28, 0.04))
M['boot']    = Mat(C['bt2'], C['bt1'], up=C['bt3'], dn=C['bt0'], deco=deco_metal(29))


# ------------------------------------------------------------------ FACE PAINT
def paint_face(img):
    FH_, FW_ = img.shape[0], img.shape[1]
    Y, X = np.mgrid[0:FH_, 0:FW_]

    def fill(x0, x1, y0, y1, col, alpha=1.0):
        px0 = max(0, int(round(fx(x0)))); px1 = min(FW_, int(round(fx(x1))))
        py0 = max(0, int(round(fy(y1)))); py1 = min(FH_, int(round(fy(y0))))
        if px1 <= px0 or py1 <= py0:
            return
        img[py0:py1, px0:px1, :3] = img[py0:py1, px0:px1, :3] * (1 - alpha) + np.array(col, float) * alpha

    def ell(cx, cy, rx, ry, col, alpha=1.0, soft=1.0):
        ex = (X + 0.5 - fx(cx)) / (rx * DF)
        ey = (Y + 0.5 - fy(cy)) / (ry * DF)
        d = ex * ex + ey * ey
        m = (np.clip((1.02 - d) / 0.30, 0, 1) if soft > 0 else (d <= 1.0))[:, :, None] * alpha
        img[:, :, :3] = img[:, :, :3] * (1 - m) + np.array(col, float) * m

    t = (Y / max(FH_ - 1, 1))[:, :, None]
    img[:, :, :3] = C['skin_lt'] * (1 - t) + C['skin_sh'] * t
    img[:, :, 3] = 255

    fill(-3.1, 3.1, 41.4, 45.0, dk(C['skin_sh'], 0.78), 0.94)
    ell(-2.86, 39.0, 0.64, 2.35, dk(C['skin_sh'], 0.88), 0.78)
    ell(2.86, 39.0, 0.64, 2.35, dk(C['skin_sh'], 0.88), 0.78)
    ell(-2.40, 36.9, 0.88, 1.18, C['skin_sh'], 0.80)
    ell(2.40, 36.9, 0.88, 1.18, C['skin_sh'], 0.80)
    ell(0, 36.24, 1.18, 0.46, dk(C['skin_sh'], 0.92), 0.66)
    ell(-1.70, 37.9, 0.70, 0.38, C['rose'], 0.34)
    ell(1.70, 37.9, 0.70, 0.38, C['rose'], 0.34)

    EYE_CY = 38.95
    for s in (-1, 1):
        cx = 1.26 * s
        ell(cx, EYE_CY, 1.20, 1.08, dk(C['skin_sh'], 0.93), 0.58)
        fill(cx - 1.00, cx + 1.00, EYE_CY - 0.72, EYE_CY + 0.80, hx('#FCFAFA'), 1.0)
        ell(cx + 0.02 * s, EYE_CY + 0.02, 0.72, 0.86, C['eye_b'], 1.0, soft=0.0)
        ell(cx + 0.02 * s, EYE_CY - 0.18, 0.68, 0.56, C['eye_c'], 1.0, soft=0.0)
        ell(cx + 0.02 * s, EYE_CY - 0.36, 0.54, 0.33, C['eye_d'], 0.92)
        ell(cx + 0.02 * s, EYE_CY + 0.20, 0.47, 0.35, C['eye_a'], 0.88)
        ell(cx + 0.02 * s, EYE_CY + 0.02, 0.24, 0.41, hx('#2E1B06'), 0.95)
        ell(cx - 0.36 * s, EYE_CY + 0.50, 0.18, 0.22, hx('#FFFFFF'), 1.0)
        ell(cx + 0.37 * s, EYE_CY - 0.28, 0.10, 0.11, hx('#FFFFFF'), 0.85)
        fill(cx - 0.92, cx + 0.92, EYE_CY - 0.80, EYE_CY - 0.68, C['lip'], 0.7)
        fill(cx - 1.04, cx + 1.04, EYE_CY + 0.74, EYE_CY + 1.02, C['lash'], 1.0)
        for i in range(9):
            u = i / 8.0
            xx = cx + (-1.06 + 2.12 * u)
            fill(xx - 0.055, xx + 0.055, EYE_CY + 0.56, EYE_CY + 0.76, C['lash'], 0.75)
        xo = cx + 1.06 * (1 if s > 0 else -1)
        fill(xo - 0.20, xo + 0.20 * (1 if s > 0 else -1), EYE_CY + 0.86, EYE_CY + 1.10, C['lash'], 0.92)
        bx = cx * 1.02
        fill(bx - 0.86, bx + 0.78, EYE_CY + 1.36, EYE_CY + 1.56, hx('#8B7B70'), 0.90)
        fill(bx - 0.90, bx - 0.62, EYE_CY + 1.34, EYE_CY + 1.46, hx('#8B7B70'), 0.74)

    ell(0.0, 37.66, 0.17, 0.14, C['skin_sh'], 0.9)
    fill(-0.11, 0.11, 37.48, 37.64, dk(C['skin_sh'], 0.9), 0.55)
    fill(-0.45, 0.45, 36.76, 36.94, C['lip'], 0.92)
    fill(-0.34, 0.34, 36.64, 36.72, dk(C['lip'], 0.72), 0.5)
    ell(0, 36.50, 0.24, 0.10, C['skin_lt'], 0.55)
    return img


# ------------------------------------------------------------------ BUILD
def build(D=6.0):
    global FX0, FY0
    b = Builder(SKEL, TS, D)
    fr = b.atlas.alloc(FW, FH)
    FX0, FY0 = fr[0], fr[1]
    RS = face_rect(-3.10, 3.10, Y_JAW, Y_SKULL)
    RJ = face_rect(-2.55, 2.55, Y_CHIN, Y_JAW)

    H = M['hair']; H2 = M['hair2']; H3 = M['hair3']; HH = M['hair_hi']
    HD = M['hair_dp']; HF = M['hair_df']
    BK = M['bk']; BKL = M['bk_l']; BKD = M['bk_d']; BKM = M['bk_m']; BKGL = M['bk_gl']
    SV = M['sv']; SVD = M['sv_d']; BL = M['bl']; BLL = M['bl_l']

    # ================================================== HEAD
    b.cube('Head', (-3.10, Y_JAW, -3.05), (6.20, Y_SKULL - Y_JAW, 6.05), M['skin2'],
           faces={'north': RS}, facename='skull')
    b.cube('Head', (-2.55, Y_CHIN, -2.78), (5.10, Y_JAW - Y_CHIN + 0.12, 5.78), M['skin2'],
           faces={'north': RJ}, facename='jaw')
    b.cube('Head', (-0.95, 33.50, -0.95), (1.90, 2.60, 1.90), M['skin2'], facename='neck')
    b.cube('Head', (2.72, 38.80, -2.62), (0.50, 3.40, 3.10), M['skin2'],
           rot=(0, -7, 0), piv=(2.72, 40.4, 0), facename='cheekL')
    b.cube('Head', (-3.22, 38.80, -2.62), (0.50, 3.40, 3.10), M['skin2'],
           rot=(0, 7, 0), piv=(-2.72, 40.4, 0), facename='cheekR')
    b.cube('Head', (3.02, 38.20, -0.95), (0.30, 1.25, 0.95), M['skin'], facename='earL')
    b.cube('Head', (-3.32, 38.20, -0.95), (0.30, 1.25, 0.95), M['skin'], facename='earR')

    # ================================================== HAIR : crown
    b.cube('Hair', (-2.94, 45.00, -2.94), (5.88, 0.46, 5.88), H, facename='crownT')
    b.cube('Hair', (-3.34, 44.28, -3.32), (6.68, 0.80, 6.72), H, facename='crown0')
    b.cube('Hair', (-3.26, 43.40, -3.36), (6.52, 0.96, 6.68), H, facename='crown1')
    b.cube('Hair', (-3.16, 42.55, -3.42), (6.32, 1.00, 0.54), H, facename='crownF')
    b.cube('Hair', (-3.16, 43.10, 2.88), (6.32, 2.60, 0.56), H2, facename='crownB')
    for i, (x, wd, yy) in enumerate([(-2.60, 0.66, 43.70), (-1.40, 0.72, 43.70),
                                     (-0.10, 0.66, 43.70), (1.24, 0.72, 43.70),
                                     (2.50, 0.62, 43.70)]):
        b.cube('Hair', (x, yy, -3.30), (wd, 1.10, 0.28), H2, facename='cridge%d' % i)
    b.cube('Hair', (-0.24, 42.50, -3.50), (0.48, 1.95, 0.28), H2,
           rot=(0, 0, -9), piv=(-0.24, 44.4, -0.3), facename='parting')
    b.cube('Hair', (0.36, 45.10, -0.30), (0.46, 1.55, 0.42), H,
           rot=(0, 0, 13), piv=(0.36, 45.15, -0.10), facename='ahoge1')
    b.cube('Hair', (0.66, 46.30, -0.34), (0.34, 1.00, 0.32), HD,
           rot=(0, 0, 24), piv=(0.66, 46.35, -0.18), facename='ahoge2')

    # ---- BANGS
    xs = [-3.00, -2.58, -2.16, -1.74, -1.32, -0.90, -0.46, 0.0,
          0.46, 0.90, 1.32, 1.74, 2.16, 2.58, 3.00]
    bot = [38.30, 39.10, 39.95, 40.30, 40.62, 40.90, 40.55, 41.05,
           40.55, 40.90, 40.62, 40.30, 39.92, 39.06, 38.25]
    mats = [HD, H3, H2, H, H, H2, H, HH, H, H2, H, H, H2, H3, HD]
    for i, x in enumerate(xs):
        w = 0.44
        top = 43.60
        b.cube('Bangs', (x - w / 2, bot[i], -3.44), (w, top - bot[i], 0.38), mats[i],
               facename='bang%d' % i)
        b.cube('Bangs', (x - 0.10, bot[i] - 0.80, -3.40), (0.20, 0.88, 0.28),
               mats[i], facename='bangt%d' % i)
    for i, (x, bt) in enumerate([(-2.86, 40.55), (-2.40, 40.95), (-1.53, 41.05), (-0.68, 41.20),
                                 (0.18, 41.15), (0.70, 41.10), (1.53, 41.00), (2.38, 40.85),
                                 (2.88, 40.30)]):
        b.cube('Bangs', (x - 0.29, bt, -3.08), (0.58, 43.00 - bt, 0.36), H2, facename='bangb%d' % i)
    b.cube('Hair', (-3.30, 42.74, -3.58), (6.60, 0.66, 0.34), H3, facename='overhang')
    # braid rings on her left temple lock (from the official close-up)
    for i, (ry, rx, rw) in enumerate([(34.40, 2.60, 0.66), (32.30, 2.66, 0.62), (30.20, 2.72, 0.58)]):
        b.cube('SideLockL', (rx, ry, -3.30), (rw, 0.26, 0.62), SV, facename='braid%d' % i)

    # ---- SIDE HAIR (layered, flares outward toward the jaw)
    for s, bn, pre in ((1, 'SideLockL', 'sl'), (-1, 'SideLockR', 'sr')):
        def X0(a, wd):
            return a if s > 0 else -a - wd
        b.cube(bn, (X0(2.74, 0.55), 38.00, -3.30), (0.55, 5.20, 0.44), H, facename=pre + '1')
        b.cube(bn, (X0(2.22, 0.50), 31.40, -3.36), (0.50, 7.20, 0.42), H2, facename=pre + '2')
        b.cube(bn, (X0(2.06, 0.40), 29.60, -3.32), (0.40, 2.30, 0.34), H3, facename=pre + '3')
        b.cube(bn, (X0(2.62, 0.54), 29.60, -3.12), (0.54, 11.00, 0.42), H2, facename=pre + '4')
        b.cube(bn, (X0(2.78, 0.42), 27.60, -3.10), (0.42, 2.60, 0.34), H3, facename=pre + '5')
        b.cube(bn, (X0(3.12, 0.58), 28.20, -2.84), (0.58, 13.00, 0.44), H3, facename=pre + '6')
        b.cube(bn, (X0(3.28, 0.46), 25.40, -2.82), (0.46, 3.00, 0.36), HD, facename=pre + '7')
        b.cube(bn, (X0(2.96, 0.54), 36.40, 0.55), (0.54, 5.80, 1.35), H2, facename=pre + '8')
        # side shell : fully covers the side of the head (no bare skin)
        b.cube(bn, (X0(3.02, 0.54), 37.00, -3.20), (0.54, 6.50, 6.30), H2, facename=pre + 'sh')
        b.cube(bn, (X0(3.10, 0.50), 36.20, -2.60), (0.50, 4.00, 4.20), H3, facename=pre + 'sh2')
        b.cube(bn, (X0(2.72, 0.36), 26.00, -2.96), (0.36, 3.20, 0.30), HD, facename=pre + '9')
        b.cube(bn, (X0(3.34, 0.44), 33.60, -2.60), (0.44, 4.60, 0.40), H2, facename=pre + 'a')

    # ---- BACK MASS
    for i, (x, wd, m) in enumerate([(-2.96, 1.00, H3), (-1.92, 1.00, H2), (-0.88, 1.00, H),
                                    (0.16, 1.00, H), (1.20, 1.00, H2), (2.24, 1.00, H3)]):
        b.cube('BackHair1', (x, 37.70 - (i % 3) * 0.30, 2.80), (wd, 4.90, 0.58), m, facename='bk1_%d' % i)
    for i, (x, wd, m) in enumerate([(-3.36, 1.04, H3), (-2.24, 1.04, H2), (-1.12, 1.04, H),
                                    (0.0, 1.04, H), (1.12, 1.04, H), (2.24, 1.04, H2), (3.36, 1.04, H3)]):
        b.cube('BackHair2', (x, 32.30 - (i % 3) * 0.40, 3.02), (wd, 5.80, 0.58), m, facename='bk2_%d' % i)
    for i, (x, wd, m) in enumerate([(-3.16, 1.06, H3), (-2.06, 1.06, H2), (-0.96, 1.06, H),
                                    (0.14, 1.06, H), (1.24, 1.06, H2), (2.34, 1.06, H3)]):
        b.cube('BackHair3', (x, 26.80 - (i % 3) * 0.38, 2.90), (wd, 5.40, 0.56), m, facename='bk3_%d' % i)
    for i, (x, w, yy) in enumerate([(-2.70, 0.86, 22.90), (-1.60, 0.82, 22.10), (-0.50, 0.80, 22.70),
                                    (0.62, 0.82, 22.20), (1.78, 0.86, 22.80), (2.86, 0.76, 21.70)]):
        b.cube('BackHair3', (x, yy, 2.76), (w, 26.90 - yy + 0.30, 0.48), HD, facename='bktip%d' % i)

    # ---- SIDE TAILS
    tailL = [(38.60, 3.20, 3.36, 1.30, -0.55, 2.30, H2),
             (35.20, 3.60, 3.52, 1.44, -0.42, 2.55, H),
             (31.40, 3.90, 3.62, 1.56, -0.28, 2.70, H2),
             (27.40, 4.10, 3.66, 1.46, -0.10, 2.75, H),
             (23.30, 3.90, 3.60, 1.24, 0.14, 2.60, H3),
             (19.90, 2.90, 3.48, 0.96, 0.36, 2.20, HD)]
    for i, (y0, hh, x0, wdt, z0, dd, m) in enumerate(tailL):
        bone = 'TailL1' if i < 2 else ('TailL2' if i < 4 else 'TailL3')
        b.cube(bone, (x0, y0, z0), (wdt, hh, dd), m, facename='tl%d' % i)
    b.cube('TailL1', (2.82, 36.60, 1.30), (0.80, 6.40, 1.00), HD, facename='tlin0')
    b.cube('TailL2', (3.30, 28.90, 1.55), (0.84, 7.40, 1.00), HD, facename='tlin1')
    b.cube('TailL3', (3.76, 21.30, 1.30), (0.78, 2.40, 1.70), HD, facename='tl3ti')

    tailR = [(-4.32, 38.60, 1.12, -0.50, 2.00, H2),
             (-4.44, 35.20, 1.22, -0.38, 2.20, H),
             (-4.50, 31.80, 1.24, -0.22, 2.24, H3),
             (-4.42, 28.70, 1.06, 0.02, 2.00, HD)]
    for i, (x0, y0, wdt, z0, dd, m) in enumerate(tailR):
        bone = 'TailR1' if i < 2 else 'TailR2'
        b.cube(bone, (x0, y0, z0), (wdt, 3.40, dd), m, facename='tr%d' % i)
    b.cube('TailR2', (-4.20, 26.60, 0.10), (0.86, 2.50, 1.70), HD, facename='trb1')

    # ---- RIBBONS
    for s, bone, tag in ((1, 'RibbonL', 'rl'), (-1, 'RibbonR', 'rr')):
        def X0(a, wd):
            return a if s > 0 else -a - wd
        b.cube(bone, (X0(3.05, 1.20), 40.95, 0.05), (1.20, 0.82, 1.70), BK, facename=tag + 'k')
        b.cube(bone, (X0(2.92, 1.04), 41.35, 0.58), (1.04, 0.38, 0.70), BKL, facename=tag + 'w1')
        b.cube(bone, (X0(2.92, 1.04), 41.35, -0.68), (1.04, 0.38, 0.70), BKL, facename=tag + 'w2')
        b.cube(bone, (X0(3.38, 0.60), 37.30, 0.34), (0.60, 3.90, 0.38), BK, facename=tag + 't1')
        b.cube(bone, (X0(3.00, 0.54), 36.50, 0.06), (0.54, 4.60, 0.36), BK, facename=tag + 't2')

    # ================================================== HORNS
    def horn(s, tag):
        th = 30.0
        x, y, z = 3.02 * s, 43.35, -0.95
        L = 0.84
        pts = [(x, y, z)]
        for i in range(9):
            a = math.radians(th)
            x += 0.265 * s * L
            y += math.cos(a) * L
            z += math.sin(a) * 0.95 * L
            pts.append((x, y, z))
            th -= 10.2
        for i in range(9):
            x0, y0, z0 = pts[i]; x1, y1, z1 = pts[i + 1]
            cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
            ln = math.dist((x0, y0, z0), (x1, y1, z1)) + 0.32
            r = 2.26 - i * 0.135
            pitch = math.degrees(math.atan2(z1 - z0, y1 - y0))
            m = BKD if i < 7 else BK
            b.cube('HornL' if s > 0 else 'HornR',
                   (cx - r / 2, cy - ln / 2, cz - r / 2), (r, ln, r), m,
                   rot=(pitch, 0, 0), piv=(cx, cy, cz), facename='%s%d' % (tag, i))
            if i in (1, 3, 5, 7):
                rr = r + 0.22
                b.cube('HornL' if s > 0 else 'HornR',
                       (cx - rr / 2, cy - 0.18, cz - rr / 2), (rr, 0.36, rr),
                       BKL, rot=(pitch, 0, 0), piv=(cx, cy, cz), facename='%srg%d' % (tag, i))
        b.cube('HornL' if s > 0 else 'HornR',
               (pts[9][0] - 0.34, pts[9][1] - 0.55, pts[9][2] - 0.34), (0.68, 1.10, 0.68),
               BKL, facename='%stip' % tag)
    horn(1, 'hl'); horn(-1, 'hr')

    # ================================================== TORSO
    b.cube('UpperBody', (-3.20, 23.00, -2.12), (6.40, 2.30, 4.24), BK, facename='hip')
    b.cube('UpperBody', (-2.38, 25.20, -1.68), (4.76, 2.70, 3.36), BKD, facename='waist')
    b.cube('UpperBody', (-2.90, 27.80, -1.92), (5.80, 3.60, 3.82), BK, facename='ribs')
    b.cube('UpperBody', (-3.30, 31.30, -2.10), (6.60, 2.70, 4.18), BKL, facename='chest')
    b.cube('UpperBody', (-3.46, 33.85, -2.16), (6.92, 0.86, 4.30), BK, facename='shldr')
    for s in (1, -1):
        def X0(a, wd):
            return a if s > 0 else -a - wd
        b.cube('UpperBody', (X0(2.96, 0.50), 27.80, -1.92), (0.50, 6.10, 3.82), BKL,
               rot=(0, 14 * s, 0), piv=(2.74 * s, 31.0, 0), facename='bev%d' % s)
    b.cube('Breast', (-3.06, 31.05, -2.36), (2.72, 2.35, 0.72), BKL,
           rot=(-14, 0, 0), piv=(-1.70, 32.4, -2.02), facename='bustR')
    b.cube('Breast', (0.34, 31.05, -2.36), (2.72, 2.35, 0.72), BKL,
           rot=(-14, 0, 0), piv=(1.70, 32.4, -2.02), facename='bustL')
    b.cube('Breast', (-2.66, 32.30, -2.48), (5.32, 0.76, 0.52), BL, facename='ruffle')
    b.cube('Breast', (-2.40, 32.96, -2.32), (4.80, 0.42, 0.42), BLL, facename='ruffle2')
    b.cube('UpperBody', (-1.34, 27.90, -2.34), (2.68, 3.50, 0.36), M['panel'], facename='frontpanel')
    b.cube('UpperBody', (-1.06, 30.55, -2.38), (2.12, 0.90, 0.30), M['panel2'], facename='frontpanel2')
    for s in (1, -1):
        b.cube('UpperBody', (0.10 * s if s > 0 else -1.30, 31.55, -2.44), (1.20, 0.24, 0.22), SV,
               rot=(0, 0, 30 * s), piv=(0, 32.2, -2.3), facename='vneck%d' % s)
    b.cube('UpperBody', (-1.68, 27.62, -2.42), (3.36, 0.24, 0.20), SV, facename='boneT')
    b.cube('UpperBody', (-1.68, 31.25, -2.42), (3.36, 0.22, 0.20), SV, facename='boneB')
    # bodice edge trim (breaks the dark mass)
    for s in (1, -1):
        b.cube('UpperBody', (1.40 * s if s > 0 else -1.62, 27.85, -2.38), (0.22, 3.60, 0.24), SVD,
               facename='pedge%d' % s)
    b.cube('UpperBody', (-2.92, 34.32, -2.20), (5.84, 0.22, 0.26), SV, facename='shline')
    b.cube('UpperBody', (-2.60, 25.62, -2.20), (5.20, 0.22, 0.24), SV, facename='beltline')
    b.cube('UpperBody', (-2.66, 25.55, -1.92), (5.32, 0.78, 3.84), BK, facename='cincher')
    b.cube('UpperBody', (-2.80, 25.70, -2.16), (5.60, 0.26, 0.26), SV, facename='cincherT')

    # ================================================== COLLAR / BOW
    b.cube('Collar', (-2.40, 34.22, -1.96), (4.80, 0.92, 3.92), BK, facename='col1')
    b.cube('Collar', (-1.30, 34.55, -1.58), (2.60, 1.20, 3.16), BK, facename='neck')
    b.cube('Collar', (-1.04, 35.20, -1.44), (2.08, 0.56, 2.88), BKD, facename='neck2')
    b.cube('Collar', (-1.26, 35.08, -1.66), (2.52, 0.34, 3.32), BKD, facename='choker')
    b.cube('Collar', (-1.08, 35.40, -1.84), (2.16, 0.28, 0.24), SV, facename='chokerT')
    for s in (1, -1):
        def X0(a, wd):
            return a if s > 0 else -a - wd
        b.cube('Collar', (X0(0.18, 2.00), 32.72, -2.52), (2.00, 1.52, 0.56), BKM,
               rot=(0, 18 * s, 0), piv=(0, 33.4, -2.24), facename='bow%d' % s)
        b.cube('Collar', (X0(0.26, 1.96), 31.55, -2.40), (1.96, 1.30, 0.52), BKL,
               rot=(0, 27 * s, 0), piv=(0, 32.5, -2.14), facename='bowt%d' % s)
        b.cube('Collar', (X0(0.06, 0.30), 32.98, -2.66), (0.30, 0.26, 0.18), SV, facename='bowe%d' % s)
    b.cube('Collar', (-0.54, 32.50, -2.74), (1.08, 1.52, 0.58), BKM, facename='bowk')
    b.cube('Collar', (-0.36, 33.10, -2.94), (0.72, 0.72, 0.32), M['gem'],
           rot=(0, 45, 0), piv=(0, 33.46, -2.8), facename='gem')
    b.cube('Collar', (-0.14, 33.00, -3.00), (0.28, 2.00, 0.16), SV, facename='star1')
    b.cube('Collar', (-1.00, 33.70, -3.00), (2.00, 0.26, 0.16), SV, facename='star2')
    b.cube('Collar', (-0.64, 34.26, -3.00), (1.28, 0.20, 0.14), SVD, facename='star3')
    b.cube('Collar', (-0.58, 32.88, -3.00), (1.16, 0.18, 0.14), SVD, facename='star4')

    # ================================================== ARMS
    for s, arm, fore, hand, tag in ((1, 'LeftArm', 'LeftForeArm', 'LeftHand', 'L'),
                                    (-1, 'RightArm', 'RightForeArm', 'RightHand', 'R')):
        def X0(a, wd):
            return a if s > 0 else -a - wd
        b.cube(arm, (X0(3.31, 2.52), 33.90, -1.30), (2.52, 0.78, 2.62), M['shpad'], facename='pad%s' % tag)
        b.cube(arm, (X0(3.25, 2.76), 33.05, -1.42), (2.76, 1.05, 2.86), M['shpad'], facename='puff%s0' % tag)
        b.cube(arm, (X0(3.19, 2.88), 32.10, -1.50), (2.88, 1.10, 2.98), M['shpad2'], facename='puff%s1' % tag)
        b.cube(arm, (X0(3.27, 2.68), 31.15, -1.42), (2.68, 1.05, 2.78), M['shpad'], facename='puff%s2' % tag)
        b.cube(arm, (X0(3.41, 2.36), 30.30, -1.26), (2.36, 0.95, 2.48), M['shpad2'], facename='puff%s3' % tag)
        b.cube(arm, (X0(3.73, 1.94), 28.75, -1.02), (1.94, 1.90, 2.04), BK, facename='uparm%s' % tag)
        b.cube(fore, (X0(3.67, 2.08), 28.26, -1.10), (2.08, 0.48, 2.22), SV, facename='cuff%s' % tag)
        b.cube(fore, (X0(3.79, 1.82), 24.30, -0.96), (1.82, 4.00, 1.92), BKGL, facename='fore%s' % tag)
        b.cube(fore, (X0(3.75, 1.90), 27.80, -1.00), (1.90, 0.44, 2.00), BKL, facename='fore2%s' % tag)
        b.cube(fore, (X0(3.77, 1.86), 25.30, -0.98), (1.86, 0.26, 1.96), SV, facename='fore3%s' % tag)
        b.cube(hand, (X0(3.87, 1.74), 22.25, -0.90), (1.74, 2.10, 1.80), BKGL, facename='hand%s' % tag)
        b.cube(hand, (X0(3.83, 1.98), 23.95, -1.04), (1.98, 0.55, 2.08), BKL, facename='glovec%s' % tag)
        b.cube(hand, (X0(3.07, 0.52) if s > 0 else -3.61, 23.35, -1.22), (0.52, 1.32, 0.62),
               BKGL, rot=(0, 0, -13 * s), piv=(X_ARM * s + 0.3 * s, 23.95, -0.92), facename='thumb%s' % tag)

    # ================================================== SKIRT
    def stripbone(ang, key):
        nm = 'Sk_' + str(key)
        if nm not in b.bmap:
            b.bone(nm, 'Skirt', (0, Y_WAIST, 0))
        b.bmap[nm]['rotation'] = [0, ang, 0]
        return nm

    def panel(bone, y_top, y_bot, r_top, r_bot, width, thick, mat, name):
        Lv = y_top - y_bot
        dr = r_bot - r_top
        if Lv <= 0.05:
            return
        L = math.hypot(Lv, dr) * 1.03
        pitch = math.degrees(math.asin(max(-0.9, min(0.9, dr / L))))
        # NOTE: Blockbench applies the Z roll with the opposite sense to the
        # right-handed formula, so the sign is negated here to flare OUTWARD.
        b.cube(bone, (r_top - thick / 2, y_top - L, -width / 2), (thick, L, width), mat,
               rot=(0, 0, -pitch), piv=(r_top, y_top, 0), facename=name)

    def curtain(n, prof, mats, thick, phase=0.0, angjit=0.0, name='sk', wmul=1.24):
        for i in range(n):
            ang = phase + i * 360.0 / n + ((i * 53) % 7 - 3) * angjit
            bone = stripbone(ang, '%s_%d' % (name, i))
            for j in range(len(prof) - 1):
                y0, r0 = prof[j]; y1, r1 = prof[j + 1]
                ravg = (r0 + r1) * 0.5
                w = 2 * math.pi * ravg / n * wmul
                panel(bone, y0, y1, r0, r1, w, thick, mats[i % len(mats)],
                      '%s%d_%d' % (name, i, j))

    GLASS_HEM = []

    def curtain(n, ytop, rtop, ybot, rbot, mats, thick, phase=0.0, hemvar=0.0, rvar=0.0,
                wmul=1.24, name='sk'):
        for i in range(n):
            ang = phase + i * 360.0 / n + ((i * 53) % 7 - 3) * 0.12
            hb = ybot + (((i * 7) % 5) - 2) * hemvar
            rb = rbot + (((i * 5) % 3) - 1) * rvar
            ravg = (rtop + rb) * 0.5
            w = 2 * math.pi * ravg / n * wmul
            panel(stripbone(ang, '%s_%d' % (name, i)), ytop, hb, rtop, rb, w, thick,
                  mats[i % len(mats)], '%s%d' % (name, i))

    # black outer skirt: wavy hem so nothing reads as a flat ring
    curtain(18, 27.10, 3.62, 15.30, 6.36,
            [M['bkf'], M['bklf'], M['bkf'], M['bkmf'], M['bkf'], M['bklf'], M['bkf'], M['bkmf']],
            0.40, phase=0.0, hemvar=0.62, rvar=0.20, name='sk')
    # over-skirt layer (shorter, outside, own hem edge)
    curtain(14, 27.40, 3.86, 21.00, 6.05, [BK, M['bklf'], BK, M['bk_m']], 0.42,
            phase=12.86, hemvar=0.55, rvar=0.16, wmul=1.30, name='sko')
    # hip yoke
    for i in range(14):
        ang = i * 360.0 / 14 + 3.0
        bone = stripbone(ang, 'yoke_%d' % i)
        r = 3.86 + (0.03 if i % 2 else -0.03)
        w = 2 * math.pi * r / 14 * 1.24
        panel(bone, 26.60, 24.90, r, r + 0.16, w, 0.34, M['bklf'], 'yk%d' % i)
    # periwinkle petticoat : NARROWER than the black hem so it only peeks underneath
    for i in range(18):
        ang = i * 360.0 / 18 + 10.0
        bone = stripbone(ang, 'pb_%d' % i)
        r0 = 4.62
        r1 = 5.34 + (((i * 5) % 3) - 1) * 0.13
        w = 2 * math.pi * 5.0 / 18 * 1.30
        hb = 14.05 + (((i * 7) % 5) - 2) * 0.42
        panel(bone, 17.20, hb, r0, r1, w, 0.36, (M['blf'] if i % 3 else M['blf2']), 'pb%d' % i)
        GLASS_HEM.append((ang, hb, r1))
    # silver-white edging that follows the petticoat hem (not a ring)
    for k, (ang, hb, r) in enumerate(GLASS_HEM):
        bone = stripbone(ang, 'fr_%d' % k)
        w = 2 * math.pi * r / 18 * 1.08
        panel(bone, hb + 0.12, hb - 0.34, r + 0.01, r + 0.12, w, 0.24, M['whf'], 'fr%d' % k)
    # back train
    for i, (x, w, y0, hh, dz) in enumerate([(-2.30, 1.55, 24.20, 8.40, 0.0),
                                            (-0.72, 1.62, 24.90, 10.10, 0.06),
                                            (0.90, 1.56, 24.40, 8.80, 0.0),
                                            (-3.44, 1.14, 22.20, 5.80, -0.06),
                                            (2.46, 1.14, 22.20, 5.40, -0.06)]):
        b.cube('BackSkirt', (x, y0 - hh, 3.42 + dz), (w, hh, 0.40), BKD, facename='train%d' % i)
    b.cube('BackSkirt', (-2.20, 13.40, 3.40), (5.20, 0.80, 0.42), M['bl_d'], facename='trainhem')
    # back waist bow
    b.cube('Skirt', (-1.90, 25.62, 3.06), (3.80, 0.46, 0.58), BKL, facename='bwband')
    for s in (1, -1):
        b.cube('Skirt', (0.10 * s if s > 0 else -2.30, 25.10, 3.16), (2.20, 1.70, 0.60), BKL,
               piv=(0, 25.9, 3.2), facename='bwloop%d' % s)
    b.cube('Skirt', (-0.70, 25.40, 3.32), (1.40, 1.20, 0.50), BK, facename='bwknot')
    for i, (x, w, hh) in enumerate([(-1.70, 0.86, 4.20), (-0.40, 0.80, 3.40),
                                    (0.90, 0.84, 4.60)]):
        b.cube('Skirt', (x, 25.50 - hh, 3.26), (w, hh, 0.42), BK, facename='bwtail%d' % i)

    # ================================================== LEGS / BOOTS
    for s, leg, low, foot, tag in ((1, 'LeftLeg', 'LeftLowerLeg', 'LeftFoot', 'L'),
                                   (-1, 'RightLeg', 'RightLowerLeg', 'RightFoot', 'R')):
        def X0(a, wd):
            return a if s > 0 else -a - wd
        b.cube(leg, (X0(0.40, 3.00), 21.60, -1.72), (3.00, 1.90, 3.44), M['st'], facename='thigh3%s' % tag)
        b.cube(leg, (X0(0.44, 2.92), 18.00, -1.62), (2.92, 5.10, 3.24), M['st'], facename='thigh2%s' % tag)
        b.cube(leg, (X0(0.52, 2.80), 14.20, -1.50), (2.80, 4.20, 3.00), M['st'], facename='thigh1%s' % tag)
        b.cube(leg, (X0(0.42, 2.96), 20.85, -1.66), (2.96, 0.46, 3.32), M['st_l'], facename='stband%s' % tag)
        b.cube(low, (X0(0.66, 2.48), 12.60, -1.34), (2.48, 1.85, 2.68), M['st'], facename='knee%s' % tag)
        b.cube(low, (X0(0.62, 2.56), 10.00, -1.40), (2.56, 2.80, 2.80), M['boot'], facename='bshaft%s' % tag)
        b.cube(low, (X0(0.66, 2.48), 6.80, -1.42), (2.48, 3.30, 2.72), M['boot'], facename='bshaft2%s' % tag)
        b.cube(low, (X0(0.58, 2.64), 9.90, -1.48), (2.64, 0.72, 2.94), BKL, facename='bcuff%s' % tag)
        b.cube(low, (X0(0.56, 2.68), 9.55, -1.50), (2.68, 0.26, 0.26), SV, facename='buck%s' % tag)
        b.cube(low, (X0(0.64, 2.52), 5.60, -1.44), (2.52, 0.55, 2.78), M['boot'], facename='bshaft3%s' % tag)
        b.cube(foot, (X0(0.62, 2.56), 2.60, -1.36), (2.56, 3.40, 2.78), M['boot'], facename='ankle%s' % tag)
        b.cube(foot, (X0(0.58, 2.64), 1.05, -1.26), (2.64, 1.80, 2.58), M['boot'], facename='foot%s' % tag)
        b.cube(foot, (X0(0.58, 2.64), 2.70, -2.52), (2.64, 1.55, 4.00), M['boot'], facename='toe%s' % tag)
        b.cube(foot, (X0(0.58, 2.64), 2.05, -2.92), (2.64, 0.90, 0.56), BKL, facename='toe2%s' % tag)
        b.cube(foot, (X0(0.96, 1.92), 0.00, 1.05), (1.92, 1.30, 1.36), M['boot'], facename='heel%s' % tag)
        b.cube(foot, (X0(0.56, 2.70), 0.00, -2.90), (2.70, 0.60, 4.56), BKD, facename='sole%s' % tag)

    # ================================================== EFFECTS
    for i, (ex, ey, ez, sc) in enumerate([(-6.35, 30.20, -1.30, 1.05),
                                          (-7.30, 25.40, 0.55, 0.85),
                                          (-5.40, 35.40, 0.90, 0.70)]):
        b.cube('Effect', (ex - 0.32 * sc, ey - 0.26 * sc, ez - 0.10 * sc),
               (0.64 * sc, 0.50 * sc, 0.20 * sc), M['gem'], facename='note%d' % i)
        b.cube('Effect', (ex + 0.17 * sc, ey - 0.26 * sc, ez - 0.06 * sc),
               (0.11 * sc, 1.45 * sc, 0.12 * sc), M['gem'], facename='stem%d' % i)
        b.cube('Effect', (ex + 0.10 * sc, ey + 0.95 * sc, ez - 0.06 * sc),
               (0.36 * sc, 0.15 * sc, 0.12 * sc), M['gem'], facename='flag%d' % i)

    return b


def main():
    b = None; D = None
    for dd in (7.2, 6.8, 6.4, 6.0, 5.6, 5.2):
        try:
            b = build(dd); D = dd
            break
        except RuntimeError as e:
            print('D=%.1f overflow -> retry' % dd)
    img = b.render_texture()
    face = np.zeros((FH, FW, 4), float)
    face[:, :, :3] = C['skin']; face[:, :, 3] = 255
    face = paint_face(face)
    img[FY0:FY0 + FH, FX0:FX0 + FW, :] = face

    out = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), 'RGBA')
    out.save(os.path.join(OUT, 'default.png'))
    a = np.array(out, float)
    a[:, :, 0] *= 0.80; a[:, :, 1] *= 0.90
    a[:, :, 2] = np.minimum(255, a[:, :, 2] * 1.10 + 6)
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'RGBA').save(os.path.join(OUT, 'blue.png'))

    model = b.to_json()
    with open(os.path.join(OUT, 'main.json'), 'w', encoding='utf-8') as f:
        json.dump(model, f, separators=(',', ':'))
    ncubes = sum(len(x.get('cubes', [])) for x in model['minecraft:geometry'][0]['bones'])
    print('D=%.2f cubes=%d bones=%d atlas=%.1f%%' % (
        D, ncubes, len(model['minecraft:geometry'][0]['bones']),
        100.0 * b.atlas.used / (TS * TS)))


if __name__ == '__main__':
    main()
