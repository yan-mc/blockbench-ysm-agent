#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按世界坐标做竖向分布分析（不依赖骨骼命名，覆盖 auto-named bone）。

回答三个问题：
  1. 方块在高度上怎么分布（哪些部位最吃方块）
  2. 头部区域（含头发）占多少
  3. 方块数与贴图尺寸的关系

用法: python tools/mine_profile.py
"""
from __future__ import annotations

import base64
import io
import json
import os
import zipfile
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(REPO, "材料", "03-语料")
DATASET = os.path.join(REPO, "材料", "_dataset.json")

# YSM 人体竖向分段（世界 Y，脚底≈0，头顶≈37）
BANDS = [
    ("feet", 0.0, 3.0),
    ("lower_leg", 3.0, 12.0),
    ("upper_leg", 12.0, 21.0),
    ("hip_waist", 21.0, 25.0),
    ("torso", 25.0, 32.0),
    ("neck_head", 32.0, 40.0),
    ("above_head", 40.0, 999.0),
]


def band_of(y: float) -> str:
    for name, lo, hi in BANDS:
        if lo <= y < hi:
            return name
    return "outside"


def iter_cubes_bedrock(geo):
    g = geo.get("minecraft:geometry")
    if not g:
        return
    g0 = g[0] if isinstance(g, list) else g
    for b in g0.get("bones", []) or []:
        for c in b.get("cubes", []) or []:
            org = c.get("origin") or [0, 0, 0]
            sz = c.get("size") or [0, 0, 0]
            try:
                y = float(org[1]) + float(sz[1]) / 2
                yield y, b.get("name") or ""
            except Exception:
                continue


def iter_cubes_bbmodel(doc):
    for e in doc.get("elements") or []:
        try:
            a = e.get("from") or [0, 0, 0]
            b = e.get("to") or [0, 0, 0]
            yield (float(a[1]) + float(b[1])) / 2, e.get("name") or ""
        except Exception:
            continue


def collect():
    band_counter = Counter()
    per_model_head_share = []
    total_cubes = []
    tex_sizes = []
    cube_vs_tex = []

    # bbmodel
    d = os.path.join(CORPUS, "bbmodel")
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not f.lower().endswith(".bbmodel"):
            continue
        try:
            doc = json.loads(open(os.path.join(d, f), "rb").read().decode("utf-8", "replace"))
        except Exception:
            continue
        cubes = list(iter_cubes_bbmodel(doc))
        if not cubes:
            continue
        cnt = Counter(band_of(y) for y, _ in cubes)
        band_counter.update(cnt)
        n = len(cubes)
        total_cubes.append(n)
        head = cnt["neck_head"] + cnt["above_head"]
        per_model_head_share.append(head / n)
        # 贴图尺寸
        sizes = []
        for t in doc.get("textures") or []:
            src = t.get("source") or ""
            if isinstance(src, str) and "base64," in src:
                try:
                    from PIL import Image
                    im = Image.open(io.BytesIO(base64.b64decode(src.split("base64,", 1)[1])))
                    sizes.append(im.size)
                except Exception:
                    pass
        if sizes:
            tex_sizes.extend(sizes)
            cube_vs_tex.append((n, max(w for w, _ in sizes)))

    # zip 包
    dz = os.path.join(CORPUS, "ysm包")
    for f in sorted(os.listdir(dz)) if os.path.isdir(dz) else []:
        if not f.lower().endswith(".zip"):
            continue
        try:
            with zipfile.ZipFile(os.path.join(dz, f)) as z:
                names = {n.lower(): n for n in z.namelist()}
                key = names.get("models/main.json") or names.get("main.json")
                if not key:
                    continue
                geo = json.loads(z.read(key).decode("utf-8", "replace"))
                cubes = list(iter_cubes_bedrock(geo))
                if not cubes:
                    continue
                cnt = Counter(band_of(y) for y, _ in cubes)
                band_counter.update(cnt)
                n = len(cubes)
                total_cubes.append(n)
                per_model_head_share.append((cnt["neck_head"] + cnt["above_head"]) / n)
                for nn in z.namelist():
                    if nn.lower().endswith(".png") and z.getinfo(nn).file_size < 4_000_000:
                        try:
                            from PIL import Image
                            im = Image.open(io.BytesIO(z.read(nn)))
                            tex_sizes.append(im.size)
                        except Exception:
                            pass
        except Exception:
            continue
    return band_counter, per_model_head_share, total_cubes, tex_sizes


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0


def main() -> int:
    band, head_share, totals, tex = collect()
    grand = sum(band.values()) or 1
    print("=" * 68)
    print("一、方块竖向分布（按世界 Y 分段，不依赖骨骼命名）")
    print("=" * 68)
    print(f"\n样本方块总数: {grand}，模型数: {len(totals)}")
    print(f"\n{'区段':<14}{'Y 范围':<16}{'方块数':>8}{'占比':>8}  解读")
    note = {
        "feet": "鞋/脚",
        "lower_leg": "小腿/袜",
        "upper_leg": "大腿",
        "hip_waist": "臀/腰/裙摆",
        "torso": "躯干/外套",
        "neck_head": "颈/头/脸/发",
        "above_head": "头顶以上（呆毛/头饰/帽）",
        "outside": "Y 越界（坐骑/道具/异常）",
    }
    for name, lo, hi in BANDS + [("outside", -1, -1)]:
        if name == "outside":
            c = band.get("outside", 0)
            rng = "越界"
        else:
            c = band.get(name, 0)
            rng = f"{lo:.0f}–{hi:.0f}" if hi < 999 else f"{lo:.0f}+"
        print(f"{name:<14}{rng:<16}{c:>8}{c/grand*100:>7.1f}%  {note[name]}")

    print("\n" + "=" * 68)
    print("二、头部区域（Y>=32）方块占比")
    print("=" * 68)
    print(f"\n  每模型占比 中位 = {med(head_share)*100:.1f}%")
    q = sorted(head_share)
    if q:
        print(f"  四分位: 25%={q[len(q)//4]*100:.1f}%   75%={q[len(q)*3//4]*100:.1f}%")
    top = sorted(head_share, reverse=True)[:5]
    print(f"  最高 5 个: {', '.join(f'{v*100:.0f}%' for v in top)}")

    print("\n" + "=" * 68)
    print("三、方块总量与贴图尺寸")
    print("=" * 68)
    print(f"\n  方块数 中位 = {med(totals)}，四分位 25%={sorted(totals)[len(totals)//4]}，"
          f"75%={sorted(totals)[len(totals)*3//4]}")
    ts = Counter(tex)
    print(f"\n  贴图边长分布（{sum(ts.values())} 张）:")
    side = Counter()
    for (w, h), c in ts.items():
        side[max(w, h)] += c
    total_side = sum(side.values()) or 1
    for s, c in sorted(side.items())[:12]:
        print(f"    {s:>5}px: {c:4d} ({c/total_side*100:4.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
