#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基于 _dataset.json 做深度统计，产出 skill 需要的规律。

输出:
  - 标准 YSM 骨架层级（父子关系出现率）
  - 各部位方块配额（head/hair/body/arm/leg/skirt/foot/other）
  - 头发占比、层级深度、Locator 清单
  - 贴图规格（从 bbmodel 内嵌 / zip 内 png 读取）
  - 比例（模型高度、头身比近似）

用法: python tools/mine_deep.py
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import zipfile
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(REPO, "材料", "03-语料")
DATASET = os.path.join(REPO, "材料", "_dataset.json")

# ---------------------------------------------------------------- 部位归类
# 顺序重要：先匹配更具体的规则
REGION_RULES = [
    ("hair", r"hair|bang|ponytail|ahoge|fringe|twin|braid|马尾|发"),
    ("head", r"head|face|eye|brow|mouth|ear|nose|cheek|horn|头盔|头"),
    ("arm", r"arm|hand|finger|shoulder|elbow|wrist|手|臂|肩"),
    ("leg", r"leg|thigh|knee|foot|feet|shoe|toe|腿|脚|靴"),
    ("skirt", r"skirt|dress|cloak|cape|coat|hem|裙|披风|外套"),
    ("body", r"body|torso|chest|breast|waist|hip|neck| abdomen|腹|腰"),
]


def region_of(bone: str) -> str:
    low = (bone or "").lower()
    for name, pat in REGION_RULES:
        if re.search(pat, low):
            return name
    return "other"


def load() -> list[dict]:
    return json.load(open(DATASET, encoding="utf-8"))


def models(recs):
    return [r for r in recs if "error" not in r and r.get("kind") in ("bedrock", "bbmodel")]


# ---------------------------------------------------------------- 骨架层级
def report_skeleton(sub):
    print("=" * 70)
    print("一、标准骨架层级（父子关系出现率）")
    print("=" * 70)
    pair = Counter()
    total = Counter()
    depth_hist = Counter()
    for r in sub:
        parents = r.get("parents") or {}
        names = set(r.get("bone_names") or [])
        for n in names:
            total[n] += 1
        for child, par in parents.items():
            if not child or not par:
                continue
            pair[(par, child)] += 1
        # 深度：沿 parent 链
        def depth(n, seen=None):
            seen = seen or set()
            if n in seen or n not in parents:
                return 0
            seen.add(n)
            return 1 + depth(parents[n], seen)
        dmax = max((depth(n) for n in names), default=0)
        depth_hist[dmax] += 1

    print("\n高频父子边（>=40% 模型出现）:")
    for (par, child), c in pair.most_common(40):
        rate = c / len(sub)
        if rate >= 0.40:
            print(f"  {par:<22} -> {child:<22} {c:3d} ({rate*100:4.0f}%)")

    print("\n层级深度分布（每个模型的根到叶最大深度）:")
    for d, c in sorted(depth_hist.items()):
        print(f"  深度 {d:2d}: {c:3d} 个模型 ({c/len(sub)*100:.0f}%)")

    # 根骨骼
    roots = Counter()
    for r in sub:
        parents = r.get("parents") or {}
        for n in set(r.get("bone_names") or []):
            if n and n not in parents:
                roots[n] += 1
    print("\n顶层根骨骼:", ", ".join(f"{n}({c})" for n, c in roots.most_common(8)))


# ---------------------------------------------------------------- 方块配额
def report_quota(sub):
    print("\n" + "=" * 70)
    print("二、各部位方块配额")
    print("=" * 70)
    per_region = defaultdict(list)
    hair_ratio = []
    cube_totals = []
    for r in sub:
        cp = r.get("cubes_per_bone") or {}
        if not cp:
            continue
        agg = defaultdict(int)
        for bone, n in cp.items():
            agg[region_of(bone)] += n
        tot = sum(agg.values())
        if tot <= 0:
            continue
        cube_totals.append(tot)
        for k, v in agg.items():
            per_region[k].append(v / tot)
        hair_ratio.append(agg.get("hair", 0) / tot)

    def med(xs):
        xs = sorted(xs)
        return xs[len(xs) // 2] if xs else 0

    print(f"\n样本 {len(cube_totals)} 个模型，方块总数中位 = {med(cube_totals)}")
    print("\n部位                        占比中位   说明")
    desc = {
        "hair": "头发（最容易做薄的地方，占比高说明要重点投入）",
        "head": "头部/面部",
        "arm": "手臂/手",
        "leg": "腿/脚/鞋",
        "skirt": "裙/外套/披风",
        "body": "躯干",
        "other": "其他/未归类（locator、道具、动物部件等）",
    }
    for k in ("hair", "head", "arm", "leg", "skirt", "body", "other"):
        if per_region.get(k):
            print(f"  {k:<24} {med(per_region[k])*100:5.1f}%   {desc[k]}")
    print(f"\n头发占比 中位 = {med(hair_ratio)*100:.1f}%")


# ---------------------------------------------------------------- Locator
def report_locators(sub):
    print("\n" + "=" * 70)
    print("三、Locator 挂点清单")
    print("=" * 70)
    cnt = Counter()
    for r in sub:
        for n in set(r.get("bone_names") or []):
            if n and "locator" in n.lower():
                cnt[n] += 1
    for n, c in cnt.most_common(20):
        print(f"  {n:<28} {c:3d} ({c/len(sub)*100:4.0f}%)")


# ---------------------------------------------------------------- 贴图规格
def report_textures(sub):
    print("\n" + "=" * 70)
    print("四、贴图规格")
    print("=" * 70)
    try:
        from PIL import Image
    except ImportError:
        print("  (PIL 不可用，跳过)")
        return
    sizes = Counter()
    # bbmodel：内嵌 base64
    d_bb = os.path.join(CORPUS, "bbmodel")
    if os.path.isdir(d_bb):
        for f in os.listdir(d_bb):
            if not f.lower().endswith(".bbmodel"):
                continue
            try:
                doc = json.loads(open(os.path.join(d_bb, f), "rb").read().decode("utf-8", "replace"))
            except Exception:
                continue
            for t in doc.get("textures") or []:
                src = t.get("source") or ""
                if isinstance(src, str) and "base64," in src:
                    try:
                        raw = base64.b64decode(src.split("base64,", 1)[1])
                        im = Image.open(io.BytesIO(raw))
                        sizes[im.size] += 1
                    except Exception:
                        pass
    # zip：textures/*.png
    d_zip = os.path.join(CORPUS, "ysm包")
    if os.path.isdir(d_zip):
        for f in os.listdir(d_zip):
            if not f.lower().endswith(".zip"):
                continue
            try:
                with zipfile.ZipFile(os.path.join(d_zip, f)) as z:
                    for n in z.namelist():
                        if n.lower().endswith(".png") and z.getinfo(n).file_size < 4_000_000:
                            try:
                                im = Image.open(io.BytesIO(z.read(n)))
                                sizes[im.size] += 1
                            except Exception:
                                pass
            except Exception:
                continue
    tot = sum(sizes.values()) or 1
    print(f"\n共读取 {tot} 张贴图，尺寸分布:")
    for (w, h), c in sizes.most_common(12):
        print(f"  {w}x{h:<5} {c:4d}  ({c/tot*100:4.1f}%)")


# ---------------------------------------------------------------- 高度/比例
def report_proportion(sub):
    print("\n" + "=" * 70)
    print("五、模型高度与比例")
    print("=" * 70)
    hs = [r["height"] for r in sub if r.get("height")]
    if not hs:
        print("  (无数据)")
        return
    hs.sort()
    print(f"\n模型顶点高度 Y  min/中位/max = {hs[0]:.1f} / {hs[len(hs)//2]:.1f} / {hs[-1]:.1f}")
    print("（YSM 人体标准约 33-37；>60 多为带道具/坐骑/兽形）")


# ---------------------------------------------------------------- 动画
def report_anim(recs):
    print("\n" + "=" * 70)
    print("六、动画片段")
    print("=" * 70)
    for r in recs:
        if r.get("kind") != "animation":
            continue
        print(f"\n  {r['source']}: {r['anim_count']} 条动画")
        print(f"    名称: {', '.join(r.get('anim_names') or [])[:200]}")
        bu = r.get("bones_used") or []
        print(f"    涉及骨骼({len(bu)}): {', '.join(bu[:25])}")


def main() -> int:
    recs = load()
    sub = models(recs)
    print(f"语料样本: {len(sub)} 个模型\n")
    report_skeleton(sub)
    report_quota(sub)
    report_locators(sub)
    report_textures(sub)
    report_proportion(sub)
    report_anim(recs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
