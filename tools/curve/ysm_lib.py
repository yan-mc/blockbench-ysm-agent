#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""YSM 解码语料读取与几何计算库（身体曲线分析专用）。

- 容忍 Blockbench 导出的 JSON 注释 / 尾逗号
- 骨骼层级 → 累积变换（Bedrock 约定：pivot 为模型空间绝对坐标，
  子骨骼随父骨骼旋转，cube origin 亦为模型空间绝对坐标，旋转绕 bone.pivot）
- 提供世界空间 8 角点、AABB、按 Y 切片宽度剖面
"""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict

CORPUS = r"F:\Deepseek_harness\blockbench\material\refmodels\ysm_decoded"


# ---------------------------------------------------------------- 容错 JSON
def _strip_comments(s: str) -> str:
    out = []
    i, n = 0, len(s)
    in_str = False
    esc = False
    while i < n:
        c = s[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            while i < n and s[i] not in "\r\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "*":
            i += 2
            while i + 1 < n and not (s[i] == "*" and s[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _strip_trailing_commas(s: str) -> str:
    out = []
    i, n = 0, len(s)
    in_str = False
    esc = False
    while i < n:
        c = s[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == ",":
            j = i + 1
            while j < n and s[j] in " \t\r\n":
                j += 1
            if j < n and s[j] in "}]":
                i += 1
                continue
        out.append(c)
        i += 1
    return "".join(out)


def load_json(path: str):
    raw = open(path, "r", encoding="utf-8-sig", errors="replace").read()
    try:
        return json.loads(raw, strict=False)
    except Exception:
        cleaned = _strip_trailing_commas(_strip_comments(raw))
        return json.loads(cleaned, strict=False)


def model_path(name: str) -> str:
    for cand in ("main.json", os.path.join("models", "main.json")):
        p = os.path.join(CORPUS, name, cand)
        if os.path.exists(p):
            return p
    return ""


def all_models():
    out = []
    for d in sorted(os.listdir(CORPUS)):
        if os.path.isdir(os.path.join(CORPUS, d)) and model_path(d):
            out.append(d)
    return out


# ---------------------------------------------------------------- 矩阵
def mat_identity():
    return [[1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 1.0, 0], [0, 0, 0, 1.0]]


def mat_mul(a, b):
    r = [[0.0] * 4 for _ in range(4)]
    for i in range(4):
        for j in range(4):
            r[i][j] = (a[i][0] * b[0][j] + a[i][1] * b[1][j]
                       + a[i][2] * b[2][j] + a[i][3] * b[3][j])
    return r


def mat_apply(m, p):
    x, y, z = p
    return (m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
            m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
            m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3])


def rot_matrix(rx, ry, rz):
    """Blockbench 使用 Euler order ZYX（R = Rz·Ry·Rx）。角度为度。"""
    ax, ay, az = math.radians(rx), math.radians(ry), math.radians(rz)
    cx, sx = math.cos(ax), math.sin(ax)
    cy, sy = math.cos(ay), math.sin(ay)
    cz, sz = math.cos(az), math.sin(az)
    Rx = [[1, 0, 0, 0], [0, cx, -sx, 0], [0, sx, cx, 0], [0, 0, 0, 1.0]]
    Ry = [[cy, 0, sy, 0], [0, 1, 0, 0], [-sy, 0, cy, 0], [0, 0, 0, 1.0]]
    Rz = [[cz, -sz, 0, 0], [sz, cz, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1.0]]
    return mat_mul(Rz, mat_mul(Ry, Rx))


def about_pivot(pivot, rot):
    px, py, pz = pivot
    return mat_mul(mat_mul([[1, 0, 0, px], [0, 1, 0, py], [0, 0, 1, pz], [0, 0, 0, 1]],
                           rot),
                   [[1, 0, 0, -px], [0, 1, 0, -py], [0, 0, 1, -pz], [0, 0, 0, 1]])


# ---------------------------------------------------------------- 模型加载
class Cube:
    __slots__ = ("origin", "size", "rotation", "pivot", "inflate", "bone")

    def __init__(self, d, bone):
        self.origin = [float(x) for x in d.get("origin", [0, 0, 0])]
        self.size = [float(x) for x in d.get("size", [0, 0, 0])]
        self.rotation = [float(x) for x in (d.get("rotation") or [0, 0, 0])]
        self.pivot = [float(x) for x in (d.get("pivot") or [0, 0, 0])]
        self.inflate = float(d.get("inflate") or 0.0)
        self.bone = bone

    @property
    def has_rot(self):
        return any(abs(a) > 0.05 for a in self.rotation)

    @property
    def dims(self):
        return sorted(self.size)

    def corners_world(self, bone_mat):
        m = mat_mul(bone_mat, about_pivot(self.pivot, rot_matrix(*self.rotation)))
        x0, y0, z0 = self.origin
        x1, y1, z1 = x0 + self.size[0], y0 + self.size[1], z0 + self.size[2]
        inf = self.inflate
        pts = []
        for x in (x0 - inf, x1 + inf):
            for y in (y0 - inf, y1 + inf):
                for z in (z0 - inf, z1 + inf):
                    pts.append(mat_apply(m, (x, y, z)))
        return pts

    def aabb_world(self, bone_mat):
        pts = self.corners_world(bone_mat)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        zs = [p[2] for p in pts]
        return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


class Bone:
    __slots__ = ("name", "parent", "pivot", "rotation", "cubes", "children", "depth", "mat")

    def __init__(self, d):
        self.name = d.get("name") or ""
        self.parent = d.get("parent")
        self.pivot = [float(x) for x in (d.get("pivot") or [0, 0, 0])]
        self.rotation = [float(x) for x in (d.get("rotation") or [0, 0, 0])]
        self.cubes = [Cube(c, self.name) for c in (d.get("cubes") or [])]
        self.children = []
        self.depth = 0
        self.mat = mat_identity()

    @property
    def has_rot(self):
        return any(abs(a) > 0.05 for a in self.rotation)


class Model:
    def __init__(self, name, path):
        self.name = name
        self.path = path
        data = load_json(path)
        geos = data.get("minecraft:geometry") or []
        self.geo_count = len(geos)
        self.bones = {}
        self.order = []
        self.desc = {}
        for g in geos:
            self.desc = g.get("description") or {}
            for bd in g.get("bones") or []:
                b = Bone(bd)
                if b.name in self.bones:
                    # 同名骨骼合并（极少）
                    self.bones[b.name].cubes.extend(b.cubes)
                else:
                    self.bones[b.name] = b
                    self.order.append(b.name)
        for n in self.order:
            b = self.bones[n]
            p = b.parent if b.parent in self.bones else None
            if p:
                self.bones[p].children.append(n)
        # 计算矩阵（先按父链递归，缺失父按根）
        for n in self.order:
            self._resolve(n, set())

    def _resolve(self, name, stack):
        b = self.bones[name]
        if b.mat is not None and id(b) in getattr(self, "_done", set()):
            return b.mat
        if not hasattr(self, "_done"):
            self._done = set()
        if id(b) in self._done:
            return b.mat
        if name in stack:
            return b.mat
        stack.add(name)
        parent = b.parent if b.parent in self.bones else None
        if parent:
            pm = self._resolve(parent, stack)
        else:
            pm = mat_identity()
        local = about_pivot(b.pivot, rot_matrix(*b.rotation))
        b.mat = mat_mul(pm, local)
        self._done.add(id(b))
        stack.discard(name)
        return b.mat

    # ---- 查询
    def bone_cubes(self):
        for n in self.order:
            b = self.bones[n]
            for c in b.cubes:
                yield b, c

    def cube_cloud(self, bone_filter=None):
        """返回 [(x,y,z,bone_name,cube)] 世界角点。"""
        pts = []
        for n in self.order:
            b = self.bones[n]
            if bone_filter and not bone_filter(n):
                continue
            for c in b.cubes:
                for p in c.corners_world(b.mat):
                    pts.append((p[0], p[1], p[2], n, c))
        return pts

    def bone_cube_bone_aabb(self, n):
        b = self.bones[n]
        xs, ys, zs = [], [], []
        for c in b.cubes:
            a = c.aabb_world(b.mat)
            xs += [a[0], a[3]]
            ys += [a[1], a[4]]
            zs += [a[2], a[5]]
        if not xs:
            return None
        return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))

    def total_cubes(self):
        return sum(len(b.cubes) for b in self.bones.values())


def load_model(name):
    return Model(name, model_path(name))
