#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""深度拆解指定 YSM / bbmodel 模型：边角处理与结构细节。

关注点（对应"边边角角怎么处理"）：
  - inflate 使用（圆角/防 z-fighting）
  - rotation 使用（斜切、角度构件）
  - 方块尺寸分布（薄片/厚块）
  - UV 利用率（贴图是否用满）
  - 头发结构（骨骼数、方块数、分层）
  - 骨骼层级与命名质量
  - 空组数量

用法: python tools/mine_models.py --pick Femme,gura,kelala
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import sys
import zipfile
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(REPO, "材料", "03-语料")


# ---------------------------------------------------------------- 载入
def load_zip_model(path: str):
    """返回 (bones, texture_sizes, meta)。bones 统一为
    [{name, parent, pivot, cubes:[{origin,size,inflate,rotation,uv}]}]"""
    with zipfile.ZipFile(path) as z:
        names = {n.lower(): n for n in z.namelist()}
        key = names.get("models/main.json") or names.get("main.json")
        if not key:
            # 可能包了一层目录
            for n in z.namelist():
                if n.lower().endswith("main.json"):
                    key = n
                    break
        if not key:
            return None
        geo = json.loads(z.read(key).decode("utf-8", "replace"))
        g = geo.get("minecraft:geometry")
        g0 = g[0] if isinstance(g, list) else g
        bones_raw = g0.get("bones", []) or []
        bones = []
        for b in bones_raw:
            cubes = []
            for c in b.get("cubes", []) or []:
                cubes.append({
                    "origin": c.get("origin") or [0, 0, 0],
                    "size": c.get("size") or [0, 0, 0],
                    "inflate": c.get("inflate", 0) or 0,
                    "rotation": c.get("rotation") or [0, 0, 0],
                    "pivot": c.get("pivot") or [0, 0, 0],
                    "uv": c.get("uv"),
                })
            bones.append({
                "name": b.get("name") or "",
                "parent": b.get("parent") or "",
                "pivot": b.get("pivot") or [0, 0, 0],
                "rotation": b.get("rotation") or [0, 0, 0],
                "cubes": cubes,
            })
        # 贴图尺寸
        sizes = []
        try:
            from PIL import Image
            import io
            for n in z.namelist():
                if n.lower().endswith(".png") and z.getinfo(n).file_size < 4_000_000:
                    try:
                        im = Image.open(io.BytesIO(z.read(n)))
                        sizes.append((os.path.basename(n), im.size))
                    except Exception:
                        pass
        except ImportError:
            pass
        # ysm.json
        meta = {}
        yj = names.get("ysm.json")
        if yj:
            try:
                y = json.loads(z.read(yj).decode("utf-8", "replace"))
                meta = {
                    "name": (y.get("metadata") or {}).get("name"),
                    "height_scale": (y.get("properties") or {}).get("height_scale"),
                    "anims": (y.get("files", {}).get("player", {}).get("animation") or {}),
                }
            except Exception:
                pass
        return {"bones": bones, "textures": sizes, "meta": meta, "source": os.path.basename(path)}


def load_bbmodel(path: str):
    doc = json.loads(open(path, "rb").read().decode("utf-8", "replace"))
    outliner = doc.get("outliner") or []
    name_of: dict[str, str] = {}
    parent_of: dict[str, str] = {}
    cubemap: dict[str, list] = defaultdict(list)

    def walk(nodes, parent):
        for n in nodes:
            if isinstance(n, str):
                cubemap[parent].append(n)
                continue
            nm = n.get("name") or ""
            name_of[nm] = nm
            if parent:
                parent_of[nm] = parent
            walk(n.get("children") or [], nm)

    walk(outliner, "")
    el_by_uuid = {}
    for e in doc.get("elements") or []:
        el_by_uuid[e.get("uuid")] = e
    bones = []
    for nm in name_of:
        cubes = []
        for cu in cubemap.get(nm, []):
            e = el_by_uuid.get(cu)
            if not e:
                continue
            a, b = e.get("from") or [0, 0, 0], e.get("to") or [0, 0, 0]
            cubes.append({
                "origin": a,
                "size": [b[i] - a[i] for i in range(3)],
                "inflate": e.get("inflate", 0) or 0,
                "rotation": e.get("rotation") or [0, 0, 0],
                "pivot": e.get("origin") or [0, 0, 0],
                "uv": e.get("uv"),
            })
        bones.append({"name": nm, "parent": parent_of.get(nm, ""),
                      "pivot": [0, 0, 0], "rotation": [0, 0, 0], "cubes": cubes})
    return {"bones": bones, "textures": [], "meta": {}, "source": os.path.basename(path)}


# ---------------------------------------------------------------- 分析
HAIR = re.compile(r"hair|bang|ahoge|ponytail|fringe|braid|twin|发|马尾|刘海", re.I)


def analyze(m: dict) -> dict:
    bones = m["bones"]
    cubes = [c for b in bones for c in b["cubes"]]
    n_cube = len(cubes)
    n_bone = len(bones)
    empty = [b["name"] for b in bones if not b["cubes"]]

    # 尺寸（跳过零尺寸方块）
    sizes = [max(c["size"]) for c in cubes if any(x > 0 for x in c["size"])]
    thin = sum(1 for c in cubes
               if [x for x in c["size"] if x > 0] and min(x for x in c["size"] if x > 0) < 0.5)
    small = sum(1 for c in cubes if max(c["size"] or [0]) <= 1.0)

    # inflate
    infl = [c["inflate"] for c in cubes if c["inflate"]]
    infl_vals = Counter(round(x, 3) for x in infl)

    # rotation
    rots = [c for c in cubes if any(abs(v) > 1e-6 for v in c["rotation"])]
    rot_bone = sum(1 for b in bones if any(abs(v) > 1e-6 for v in b["rotation"]))
    ang = Counter()
    for c in rots:
        for v in c["rotation"]:
            if abs(v) > 1e-6:
                ang[round(abs(v) % 90)] += 1

    # UV：两种格式
    #   per-face: uv = {north:{uv:[x,y], uv_size:[w,h]}, ...}
    #   box     : uv = [x, y]（面积由几何推出）
    used = set()
    uv_area = 0.0
    per_face_cubes = 0
    tex_area = None
    for c in cubes:
        uv = c["uv"]
        w, h, d = (list(c["size"]) + [0, 0, 0])[:3]
        if isinstance(uv, dict):
            per_face_cubes += 1
            for face, fv in uv.items():
                if isinstance(fv, dict) and "uv" in fv and "uv_size" in fv:
                    x, y = fv["uv"]
                    uw, uh = fv["uv_size"]
                    uw, uh = abs(uw), abs(uh)
                    uv_area += uw * uh
                    for xx in range(int(x), int(x + uw) + 1):
                        for yy in range(int(y), int(y + uh) + 1):
                            used.add((xx, yy))
        elif isinstance(uv, list) and len(uv) >= 2:
            uv_area += 2 * (d * h) + 2 * (w * h) + 2 * (w * d)
    if m["textures"]:
        tex_area = m["textures"][0][1]

    # 层级深度
    parent = {b["name"]: b["parent"] for b in bones}

    def depth(n, seen=None):
        seen = seen or set()
        if not n or n in seen or n not in parent:
            return 0
        seen.add(n)
        return 1 + depth(parent[n], seen)
    dmax = max((depth(b["name"]) for b in bones), default=0)

    # 头发
    hair_bones = [b for b in bones if HAIR.search(b["name"])]
    hair_cubes = sum(len(b["cubes"]) for b in hair_bones)

    # 命名质量
    auto = sum(1 for b in bones if re.fullmatch(r"bone\d*", b["name"], re.I))

    return {
        "source": m["source"],
        "bones": n_bone, "cubes": n_cube, "empty_groups": len(empty),
        "auto_named": auto,
        "cube_per_bone": round(n_cube / max(1, n_bone), 2),
        "depth": dmax,
        "size_median": round(statistics.median(sizes), 2) if sizes else 0,
        "size_max": round(max(sizes), 2) if sizes else 0,
        "thin_plates": thin, "tiny_cubes": small,
        "inflate_count": len(infl),
        "inflate_vals": dict(infl_vals.most_common(6)),
        "rotated_cubes": len(rots), "rotated_bones": rot_bone,
        "angles_top": dict(ang.most_common(6)),
        "uv_pixels": len(used),
        "uv_area": round(uv_area, 1),
        "per_face_cubes": per_face_cubes,
        "tex_size": tex_area,
        "uv_fill_pct": round(len(used) / (tex_area[0] * tex_area[1]) * 100, 1) if tex_area and used else None,
        "uv_need_pct": round(uv_area / (tex_area[0] * tex_area[1]) * 100, 1) if tex_area else None,
        "hair_bones": len(hair_bones), "hair_cubes": hair_cubes,
        "hair_pct": round(hair_cubes / max(1, n_cube) * 100, 1),
        "textures": m["textures"][:3],
        "meta": m["meta"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick", default="", help="逗号分隔的模型名片段")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    picks = [p.strip() for p in args.pick.split(",") if p.strip()]
    d_zip = os.path.join(CORPUS, "ysm包")
    d_bb = os.path.join(CORPUS, "bbmodel")
    cands = []
    for d, loader, exts in ((d_zip, load_zip_model, (".zip",)), (d_bb, load_bbmodel, (".bbmodel",))):
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.lower().endswith(exts):
                continue
            cands.append((d, f, loader))

    results = []
    for d, f, loader in cands:
        if picks and not any(p.lower() in f.lower() for p in picks):
            continue
        try:
            m = loader(os.path.join(d, f))
            if not m or not m["bones"]:
                continue
            results.append(analyze(m))
        except Exception as e:
            print(f"  skip {f}: {e}", file=sys.stderr)

    results.sort(key=lambda r: -r["cubes"])
    for r in results:
        print("=" * 78)
        print(f"{r['source']}")
        print(f"  骨 {r['bones']} / 方 {r['cubes']} / 空组 {r['empty_groups']} / "
              f"自动命名 {r['auto_named']} / 方比骨 {r['cube_per_bone']} / 深 {r['depth']}")
        print(f"  尺寸 中位 {r['size_median']} 最大 {r['size_max']} | 薄片(<0.5) {r['thin_plates']} "
              f"小块(<=1) {r['tiny_cubes']}")
        print(f"  inflate {r['inflate_count']} 个 {r['inflate_vals']}")
        print(f"  旋转方块 {r['rotated_cubes']} / 旋转骨骼 {r['rotated_bones']} 常见角 {r['angles_top']}")
        print(f"  UV 显式占用 {r['uv_pixels']} px / 贴图 {r['tex_size']} = {r['uv_fill_pct']}%"
              f" | UV 面积需求 {r['uv_area']} px² = {r['uv_need_pct']}%"
              f" | 逐面方块 {r['per_face_cubes']}")
        print(f"  头发 骨 {r['hair_bones']} / 方 {r['hair_cubes']} = {r['hair_pct']}%")
        if r["textures"]:
            print(f"  贴图 {r['textures']}")
        if r["meta"]:
            print(f"  meta {r['meta']}")

    if args.json:
        json.dump(results, open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n-> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
