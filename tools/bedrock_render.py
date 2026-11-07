#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bedrock 几何软渲染器（语料批量分析用）。

为什么自己写：语料有 400+ 个模型，逐个用 Blockbench 打开渲染太慢（每次 ~2s）。
这里直接解析 bedrock geometry（含旧版 geometry.* 格式），做正交投影 + 纹理采样，
一张 PNG 几十毫秒，可以成批出图再拼对照表。

坐标系按 Minecraft 约定：+Y 向上，-Z 为正面（朝向观察者）。
"""
import json, math, os, sys
import numpy as np
from PIL import Image

# ---------------------------------------------------------------- 几何解析

def geo_of(doc):
    if not isinstance(doc, dict):
        return None
    if "minecraft:geometry" in doc:
        g = doc["minecraft:geometry"][0]
        d = g.get("description", {})
        return g.get("bones", []), d.get("texture_width", 64), d.get("texture_height", 64)
    for k, v in doc.items():
        if k.startswith("geometry.") and isinstance(v, dict) and "bones" in v:
            return v["bones"], v.get("texturewidth", 64), v.get("textureheight", 64)
    return None


def mat_translate(t):
    m = np.eye(4); m[:3, 3] = t; return m


def mat_rot_xyz(rx, ry, rz):
    """bedrock 顺序：先 Z、再 Y、最后 X（Blockbench 默认 ZYX 内旋的等价实现）。"""
    rx, ry, rz = math.radians(rx), math.radians(ry), math.radians(rz)
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    X = np.array([[1, 0, 0, 0], [0, cx, -sx, 0], [0, sx, cx, 0], [0, 0, 0, 1]], dtype=float)
    Y = np.array([[cy, 0, sy, 0], [0, 1, 0, 0], [-sy, 0, cy, 0], [0, 0, 0, 1]], dtype=float)
    Z = np.array([[cz, -sz, 0, 0], [sz, cz, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=float)
    return X @ Y @ Z


FACE_DEFS = {
    "north": ([-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]),
    "south": ([1, -1, -1], [-1, -1, -1], [-1, 1, -1], [1, 1, -1]),
    "west": ([-1, -1, -1], [-1, -1, 1], [-1, 1, 1], [-1, 1, -1]),
    "east": ([1, -1, 1], [1, -1, -1], [1, 1, -1], [1, 1, 1]),
    "up": ([-1, 1, 1], [1, 1, 1], [1, 1, -1], [-1, 1, -1]),
    "down": ([-1, -1, -1], [1, -1, -1], [1, -1, 1], [-1, -1, 1]),
}


def collect_faces(bones, tex_size):
    """返回 [(顶点4, uv4, 深度参考点)]，已变换到世界空间。"""
    by_name = {}
    for b in bones:
        by_name[b.get("name")] = b

    cache = {}

    def bone_matrix(name, depth=0):
        if name in cache:
            return cache[name]
        if depth > 40 or name not in by_name:
            cache[name] = np.eye(4); return cache[name]
        b = by_name[name]
        piv = np.array(b.get("pivot", [0, 0, 0]), dtype=float)
        rot = np.array(b.get("rotation", [0, 0, 0]), dtype=float)
        if os.environ.get("NO_BONE_ROT"): rot = np.zeros(3)
        parent = b.get("parent")
        pm = bone_matrix(parent, depth + 1) if parent else np.eye(4)
        if os.environ.get("NO_BONE_TRANS"): m = mat_rot_xyz(*rot)
        else: m = pm @ mat_translate(piv) @ mat_rot_xyz(*rot) @ mat_translate(-piv)
        cache[name] = m
        return m

    faces = []
    for b in bones:
        bm = bone_matrix(b.get("name"))
        for c in b.get("cubes", []):
            o = np.array(c.get("origin", [0, 0, 0]), dtype=float)
            s = np.array(c.get("size", [0, 0, 0]), dtype=float)
            s = np.maximum(s, 0.01)
            crot = np.array(c.get("rotation", [0, 0, 0]), dtype=float)
            if os.environ.get("NO_CUBE_ROT"): crot = np.zeros(3)
            cpiv = np.array(c.get("pivot", [0, 0, 0]), dtype=float)
            cm = bm @ mat_translate(o) @ mat_translate(cpiv) @ mat_rot_xyz(*crot) @ mat_translate(-cpiv)
            uv = c.get("uv")
            box_uv = isinstance(uv, list) or "uv" not in c
            for fname, signs in FACE_DEFS.items():
                verts = []
                for sg in signs:
                    # 角点：sign 为负取 0，为正取整条边长（写成 s/2 会让方块只有一半大）
                    local = np.array([0.0 if sg[i] < 0 else s[i] for i in range(3)])
                    verts.append((cm @ np.array([local[0], local[1], local[2], 1.0]))[:3])
                # UV
                if box_uv:
                    u, v = (uv if isinstance(uv, list) and len(uv) >= 2 else [0, 0])
                    dx, dy, dz = s
                    if fname in ("north", "south"):
                        uw, uh = dx, dy
                        ox = 0 if fname == "north" else (dz + dx)
                        oy = dz
                    elif fname in ("east", "west"):
                        uw, uh = dz, dy
                        ox = dz if fname == "east" else (2 * dz + dx)
                        oy = dz
                    else:
                        uw, uh = dx, dz
                        ox = dz if fname == "up" else (dz + dx)
                        oy = 0 if fname == "up" else dy
                    uv_set = [(u + ox, v + oy), (u + ox + uw, v + oy),
                              (u + ox + uw, v + oy + uh), (u + ox, v + oy + uh)]
                else:
                    f = (c.get("uv") or {}).get(fname)
                    if not f or not isinstance(f, dict) or "uv" not in f:
                        uv_set = [(-1, -1)] * 4
                    else:
                        fu, fv = f["uv"][:2]
                        fw, fh = (f.get("uv_size") or s[:2])[:2]
                        uv_set = [(fu, fv), (fu + fw, fv), (fu + fw, fv + fh), (fu, fv + fh)]
                # 面顶点顺序与 uv 顺序对齐（上面 FACE_DEFS 已按此排）
                faces.append((np.array(verts), uv_set))
    return faces


# ---------------------------------------------------------------- 光栅化

def render(doc, tex_path, size=320, yaw=0.0, pitch=12.0, fov_pad=1.12, bg=(24, 24, 28)):
    g = geo_of(doc)
    if not g:
        return None
    bones, tw, th = g
    if not bones:
        return None
    tex = None
    if tex_path and os.path.exists(tex_path):
        try:
            tex = Image.open(tex_path).convert("RGB")
        except Exception:
            tex = None
    texarr = np.array(tex) if tex else None
    tsize = texarr.shape[:2] if texarr is not None else (th, tw)

    faces = collect_faces(bones, (tw, th))
    if not faces:
        return None
    allv = np.concatenate([f[0] for f in faces], axis=0)

    # 旋转到视空间
    ry, rp = math.radians(yaw), math.radians(pitch)
    Ry = np.array([[math.cos(ry), 0, math.sin(ry)], [0, 1, 0], [-math.sin(ry), 0, math.cos(ry)]])
    Rp = np.array([[1, 0, 0], [0, math.cos(rp), -math.sin(rp)], [0, math.sin(rp), math.cos(rp)]])
    R = Rp @ Ry

    world = allv @ R.T
    mn, mx = world.min(axis=0), world.max(axis=0)
    center = (mn + mx) / 2
    extent = max(mx[0] - mn[0], mx[1] - mn[1]) or 1.0
    scale = size / (extent * fov_pad)

    def to_screen(p):
        q = (p - center) * scale
        return np.array([q[0] + size / 2, size / 2 - q[1], q[2]])

    img = np.zeros((size, size, 3), dtype=np.float32)
    img[:] = bg
    zbuf = np.full((size, size), -1e9, dtype=np.float32)

    for verts, uv in faces:
        sv = np.array([to_screen(v @ R.T) for v in verts])
        # backface cull（按屏幕坐标系绕向）
        a, b, c = sv[0], sv[1], sv[2]
        area = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
        if abs(area) < 1e-9:
            continue
        xs = sv[:, 0]; ys = sv[:, 1]; zs = sv[:, 2]
        x0, x1 = int(max(0, np.floor(xs.min()))), int(min(size - 1, np.ceil(xs.max())))
        y0, y1 = int(max(0, np.floor(ys.min()))), int(min(size - 1, np.ceil(ys.max())))
        if x1 < x0 or y1 < y0:
            continue
        px, py = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        # 三角形 0-1-2 与 0-2-3
        for tri in ((0, 1, 2), (0, 2, 3)):
            i0, i1, i2 = tri
            ax, ay = xs[i0], ys[i0]; bx, by = xs[i1], ys[i1]; cx, cy = xs[i2], ys[i2]
            den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-9:
                continue
            w0 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / den
            w1 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / den
            w2 = 1 - w0 - w1
            mask = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
            if not mask.any():
                continue
            depth = w0 * zs[i0] + w1 * zs[i1] + w2 * zs[i2]
            uu = w0 * uv[i0][0] + w1 * uv[i1][0] + w2 * uv[i2][0]
            vv = w0 * uv[i0][1] + w1 * uv[i1][1] + w2 * uv[i2][1]
            sub = img[y0:y1 + 1, x0:x1 + 1]
            zsub = zbuf[y0:y1 + 1, x0:x1 + 1]
            update = mask & (depth > zsub)
            if not update.any():
                continue
            if texarr is not None:
                tx = np.clip((uu / max(1, tw) * texarr.shape[1]).astype(int), 0, texarr.shape[1] - 1)
                ty = np.clip((vv / max(1, th) * texarr.shape[0]).astype(int), 0, texarr.shape[0] - 1)
                col = texarr[ty, tx].astype(np.float32)
                # 简单定向光：按面的法线方向给 0.72~1.0 的明度
                n = np.cross(sv[1] - sv[0], sv[2] - sv[0])
                ln = np.linalg.norm(n)
                shade = 0.78 + 0.22 * abs(n[2] / ln) if ln else 0.85
                col = col * shade
            else:
                # 无贴图：整面灰，用来验证几何是否正确
                col = np.full((px.shape[0], px.shape[1], 3), 150, dtype=np.float32)
            sub[update] = col[update]
            zsub[update] = depth[update]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def main():
    src = sys.argv[1]
    out = sys.argv[2]
    size = int(sys.argv[3]) if len(sys.argv) > 3 else 320
    doc = json.load(open(src, encoding="utf-8"))
    tex = os.environ.get("BB_TEX") or (src[:-5] + ".png")
    im = render(doc, tex, size=size)
    if im is None:
        print("FAIL", src); return 1
    im.save(out)
    print("OK", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
