#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共用：区域归类、分位数、球面拟合、薄片判定。"""
from __future__ import annotations

import json
import math
import re
import statistics as st

FACTS = r"F:\Deepseek_harness\blockbench\tools\curve\out_facts.json"


def load():
    return json.load(open(FACTS, encoding="utf-8"))


# ---------------------------------------------------------------- 区域正则
RE_BREAST = re.compile(r"breast|boob|bust|oppai|胸|乳")
RE_CLOTH = re.compile(r"cloth|clothes|clothing|bra|shirt|dress|armor|plate|uniform|suit|衣|服|甲")
RE_HAIR = re.compile(r"hair|bangs|ponytail|braid|马尾|发")
RE_CAPE = re.compile(r"cape|cloak|robe|coat|披风|斗篷|羽|wing|tail|veil|scarf|shawl")
RE_SKIRT = re.compile(r"skirt|dress|裙|下摆|hem|petticoat|pants|shorts|裤")
RE_TORSO = re.compile(r"^(upbody|upperbody|upper_body|body|downbody|allbody|torso|waist|spine|chest|"
                      r"body1|body2|body3|body4|body5|upbody1|upbody2|upbody3|downbody1|downbody2)$")
RE_TORSO_LOOSE = re.compile(r"upbody|upperbody|upper_body|downbody|allbody|torso|waist|spine")
RE_PELVIS = re.compile(r"hip|butt|pelvis|glute|臀|胯")
RE_LEG_UP = re.compile(r"leg|thigh|大腿")
RE_LEG_LOW = re.compile(r"lowerleg|calf|knee|shin|小腿|膝")
RE_FOOT = re.compile(r"foot|feet|shoe|boot|sock|toe|脚|靴|袜")
RE_ARM = re.compile(r"arm|shoulder|elbow|wrist|袖|sleeve")
RE_HAND = re.compile(r"hand|palm|finger|thumb|glove|手|指")
RE_NECK = re.compile(r"neck|throat|颈|脖")
RE_HEAD = re.compile(r"head|face|eye|brow|mouth|ear|nose|cheek|mask|helmet|头|脸|眼")
RE_WEAPON = re.compile(r"weapon|sword|gun|rifle|pistol|blade|katana|bow|arrow|枪|刀|剑")


def is_cloth(name: str) -> bool:
    return bool(RE_CLOTH.search(name.lower()))


def is_hair(name: str) -> bool:
    return bool(RE_HAIR.search(name.lower()))


def is_cape(name: str) -> bool:
    return bool(RE_CAPE.search(name.lower()))


def is_skirt(name: str) -> bool:
    return bool(RE_SKIRT.search(name.lower()))


# ---------------------------------------------------------------- 统计
def q(vals, p):
    """线性插值分位数（与 numpy 默认一致）。"""
    v = sorted(vals)
    if not v:
        return None
    if len(v) == 1:
        return float(v[0])
    k = (len(v) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(v[int(k)])
    return float(v[f] * (c - k) + v[c] * (k - f))


def stat(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return {}
    return {
        "n": len(vals),
        "median": round(st.median(vals), 3),
        "p25": round(q(vals, 0.25), 3),
        "p75": round(q(vals, 0.75), 3),
        "min": round(min(vals), 3),
        "max": round(max(vals), 3),
        "mean": round(sum(vals) / len(vals), 3),
    }


# ---------------------------------------------------------------- 球面拟合
def fit_sphere(pts):
    """最小二乘球拟合：|p-c|^2 = r^2 → 线性方程。返回 (c, r, rms)。"""
    n = len(pts)
    if n < 4:
        return None
    # 2x^2+2y^2+2z^2 = 2ax+2by+2cz + (r^2 - a^2-b^2-c^2)
    A = [[2 * p[0], 2 * p[1], 2 * p[2], 1.0] for p in pts]
    b = [p[0] ** 2 + p[1] ** 2 + p[2] ** 2 for p in pts]
    # 正规方程
    AtA = [[sum(A[k][i] * A[k][j] for k in range(n)) for j in range(4)] for i in range(4)]
    Atb = [sum(A[k][i] * b[k] for k in range(n)) for i in range(4)]
    # 高斯消元
    M = [AtA[i][:] + [Atb[i]] for i in range(4)]
    for i in range(4):
        piv = max(range(i, 4), key=lambda r: abs(M[r][i]))
        if abs(M[piv][i]) < 1e-12:
            return None
        M[i], M[piv] = M[piv], M[i]
        pv = M[i][i]
        M[i] = [x / pv for x in M[i]]
        for r in range(4):
            if r != i and abs(M[r][i]) > 1e-15:
                f = M[r][i]
                M[r] = [M[r][k] - f * M[i][k] for k in range(5)]
    cx, cy, cz, d = M[0][4], M[1][4], M[2][4], M[3][4]
    c = (cx, cy, cz)
    r2 = d + cx * cx + cy * cy + cz * cz
    if r2 <= 0:
        return None
    r = math.sqrt(r2)
    res = [abs(math.dist(p, c) - r) for p in pts]
    rms = math.sqrt(sum(x * x for x in res) / n)
    return c, r, rms


def norm(v):
    l = math.sqrt(sum(x * x for x in v))
    return (v[0] / l, v[1] / l, v[2] / l) if l > 1e-12 else (0, 0, 0)


def rot_axes(rx, ry, rz):
    """返回方块局部三轴在世界空间的方向（与 ysm_lib 同样的 ZYX 顺序）。"""
    ax, ay, az = math.radians(rx), math.radians(ry), math.radians(rz)
    cx, sx = math.cos(ax), math.sin(ax)
    cy, sy = math.cos(ay), math.sin(ay)
    cz, sz = math.cos(az), math.sin(az)
    Rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    Ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    Rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]

    def mm(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

    R = mm(Rz, mm(Ry, Rx))
    return [(R[0][0], R[1][0], R[2][0]),
            (R[0][1], R[1][1], R[2][1]),
            (R[0][2], R[1][2], R[2][2])]
