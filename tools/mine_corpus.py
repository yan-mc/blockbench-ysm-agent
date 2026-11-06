#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""YSM 模型语料提取器。

扫描 `材料/03-语料/` 下的 bbmodel / zip(YSM 包) / json 动画，
统一抽取结构特征，输出 dataset.json 供后续统计与 skill 归纳。

支持:
  - .bbmodel          Blockbench 工程（elements + outliner + textures）
  - .zip/.rar(仅zip)  YSM 资源包（models/main.json bedrock 几何 + ysm.json）
  - .json             动画文件（animations/*.json）

用法:
    python tools/mine_corpus.py            # 提取并打印摘要
    python tools/mine_corpus.py --json out.json
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(REPO, "材料", "03-语料")

# ---------------------------------------------------------------- 工具

def norm_name(s: str) -> str:
    return (s or "").strip()


def zip_read_json(z: zipfile.ZipFile, candidates: list[str]):
    """按候选路径读取 zip 内 JSON（大小写不敏感，允许一层前缀）。"""
    names = z.namelist()
    lower = {n.lower(): n for n in names}
    for cand in candidates:
        c = cand.lower()
        if c in lower:
            try:
                return json.loads(z.read(lower[c]).decode("utf-8", "replace")), lower[c]
            except Exception:
                return None, None
    # 退一步：任何以候选名结尾的条目
    for cand in candidates:
        c = cand.lower()
        for low, real in lower.items():
            if low.endswith("/" + c):
                try:
                    return json.loads(z.read(real).decode("utf-8", "replace")), real
                except Exception:
                    return None, None
    return None, None


def bedrock_bones(geo: dict):
    """返回 (bones, cubes_count)。"""
    try:
        g = geo.get("minecraft:geometry")
        if not g:
            return [], 0
        g0 = g[0] if isinstance(g, list) else g
        bones = g0.get("bones", []) or []
        cubes = sum(len(b.get("cubes", []) or []) for b in bones)
        return bones, cubes
    except Exception:
        return [], 0


def record_bedrock(geo: dict) -> dict | None:
    bones, cubes = bedrock_bones(geo)
    if not bones:
        return None
    names = [norm_name(b.get("name")) for b in bones]
    parents = {norm_name(b.get("name")): norm_name(b.get("parent")) for b in bones if b.get("parent")}
    # 每个骨骼的方块数
    per_bone = Counter()
    ys = []
    for b in bones:
        n = norm_name(b.get("name"))
        cs = b.get("cubes", []) or []
        per_bone[n] = len(cs)
        for c in cs:
            org = c.get("origin") or [0, 0, 0]
            sz = c.get("size") or [0, 0, 0]
            try:
                ys.append(float(org[1]) + float(sz[1]))
            except Exception:
                pass
    uv_modes = Counter()
    for b in bones:
        for c in b.get("cubes", []) or []:
            uv = c.get("uv")
            uv_modes["per_face" if isinstance(uv, dict) else "box"] += 1
    return {
        "kind": "bedrock",
        "bones": bones,
        "bone_count": len(bones),
        "cube_count": cubes,
        "bone_names": names,
        "parents": parents,
        "cubes_per_bone": dict(per_bone),
        "height": (max(ys) if ys else None),
        "uv_modes": dict(uv_modes),
    }


def record_bbmodel(doc: dict) -> dict | None:
    els = doc.get("elements") or []
    outliner = doc.get("outliner") or []
    if not els and not outliner:
        return None

    def walk(nodes, parent, depth, acc):
        for n in nodes:
            if isinstance(n, str):
                continue
            name = norm_name(n.get("name"))
            acc.append((name, parent, depth, len(n.get("children") or [])))
            walk(n.get("children") or [], name, depth + 1, acc)

    acc: list[tuple[str, str, int, int]] = []
    walk(outliner, "", 0, acc)
    parent_of = {n: p for n, p, _, _ in acc if p}
    per_bone = Counter()
    # elements 属于某个 group：用 parent 链近似（bbmodel 里元素在 outliner 的 children 中）
    def count_cubes(nodes):
        for n in nodes:
            if isinstance(n, str):
                continue
            per_bone[norm_name(n.get("name"))] += sum(1 for c in (n.get("children") or []) if isinstance(c, str))
            count_cubes([c for c in (n.get("children") or []) if isinstance(c, dict) and "name" in c])

    count_cubes(outliner)

    ys, uv_modes = [], Counter()
    for e in els:
        try:
            ys.append(float(e.get("to", [0, 0, 0])[1]))
        except Exception:
            pass
        uv = e.get("uv")
        uv_modes["per_face" if isinstance(uv, dict) else "box"] += 1
    texs = []
    for t in doc.get("textures") or []:
        src = t.get("source") or ""
        if isinstance(src, str) and src.startswith("data:image"):
            m = re.search(r"base64,", src)
            texs.append("embedded")
        else:
            texs.append(norm_name(t.get("name")))
    return {
        "kind": "bbmodel",
        "bone_count": len(acc),
        "cube_count": len(els),
        "bone_names": [n for n, _, _, _ in acc],
        "parents": parent_of,
        "cubes_per_bone": dict(per_bone),
        "height": (max(ys) if ys else None),
        "uv_modes": dict(uv_modes),
        "textures": texs,
        "anim_count": len(doc.get("animations") or []),
        "depth_max": max((d for _, _, d, _ in acc), default=0),
        "empty_groups": sum(1 for n, _, _, ch in acc if ch == 0 and per_bone.get(n, 0) == 0),
    }


# ---------------------------------------------------------------- 主流程

def scan() -> list[dict]:
    out: list[dict] = []
    d_bb = os.path.join(CORPUS, "bbmodel")
    d_zip = os.path.join(CORPUS, "ysm包")
    d_anim = os.path.join(CORPUS, "动画片段")

    # bbmodel
    if os.path.isdir(d_bb):
        for f in sorted(os.listdir(d_bb)):
            fp = os.path.join(d_bb, f)
            if not f.lower().endswith(".bbmodel"):
                continue
            try:
                doc = json.loads(open(fp, "rb").read().decode("utf-8", "replace"))
                r = record_bbmodel(doc)
                if r:
                    r["source"] = f"bbmodel/{f}"
                    out.append(r)
            except Exception as e:
                out.append({"source": f"bbmodel/{f}", "error": str(e)[:120]})

    # zip 包
    if os.path.isdir(d_zip):
        for f in sorted(os.listdir(d_zip)):
            fp = os.path.join(d_zip, f)
            if not f.lower().endswith(".zip"):
                continue
            try:
                with zipfile.ZipFile(fp) as z:
                    geo, used = zip_read_json(z, ["models/main.json", "main.json"])
                    ysm, _ = zip_read_json(z, ["ysm.json"])
                    r = record_bedrock(geo) if geo else None
                    if r is None:
                        continue
                    r["source"] = f"ysm包/{f}:{used}"
                    r["has_ysm_json"] = bool(ysm)
                    if ysm:
                        prop = ysm.get("properties") or {}
                        r["ysm"] = {
                            "height_scale": prop.get("height_scale"),
                            "width_scale": prop.get("width_scale"),
                            "default_texture": prop.get("default_texture"),
                            "extra_anim": len(prop.get("extra_animation") or {}),
                            "extra_buttons": len(prop.get("extra_animation_buttons") or []),
                        }
                        fl = (ysm.get("files") or {}).get("player") or {}
                        r["ysm"]["anims"] = len((fl.get("animation") or {}))
                        r["ysm"]["textures"] = len(fl.get("texture") or [])
                    out.append(r)
            except Exception as e:
                out.append({"source": f"ysm包/{f}", "error": str(e)[:120]})

    # 动画片段
    if os.path.isdir(d_anim):
        for f in sorted(os.listdir(d_anim)):
            if not f.lower().endswith(".json"):
                continue
            fp = os.path.join(d_anim, f)
            try:
                doc = json.loads(open(fp, "rb").read().decode("utf-8", "replace"))
                anims = doc.get("animations") or {}
                keys = list(anims.keys())
                out.append({
                    "source": f"动画片段/{f}",
                    "kind": "animation",
                    "anim_count": len(anims),
                    "anim_names": keys[:12],
                    "bones_used": sorted({b for a in anims.values()
                                          for b in (a.get("bones") or {})})[:40],
                })
            except Exception as e:
                out.append({"source": f"动画片段/{f}", "error": str(e)[:120]})
    return out


def summarize(recs: list[dict]) -> None:
    ok = [r for r in recs if "error" not in r and r.get("kind") != "animation"]
    err = [r for r in recs if "error" in r]
    print(f"解析成功: {len(ok)}  失败: {len(err)}")
    for e in err[:10]:
        print(f"  ERR {e['source']}: {e['error']}")

    for kind in ("bedrock", "bbmodel"):
        sub = [r for r in ok if r["kind"] == kind]
        if not sub:
            continue
        bones = [r["bone_count"] for r in sub]
        cubes = [r["cube_count"] for r in sub]
        print(f"\n=== {kind} ({len(sub)} 个) ===")
        print(f"  骨骼数  min/中位/max = {min(bones)}/{sorted(bones)[len(bones)//2]}/{max(bones)}")
        print(f"  方块数  min/中位/max = {min(cubes)}/{sorted(cubes)[len(cubes)//2]}/{max(cubes)}")
        print(f"  方块/骨骼 中位 = {sorted(c/b for c,b in zip(cubes,bones) if b)[len(sub)//2]:.1f}")
        # 高频骨骼名
        cnt = Counter()
        for r in sub:
            for n in set(r["bone_names"]):
                cnt[n] += 1
        print("  最常见骨骼名(出现率):")
        for n, c in cnt.most_common(20):
            label = n if n else "(空)"
            print(f"    {label:<24} {c:3d}  {c/len(sub)*100:5.1f}%")
        # UV 模式
        uvm = Counter()
        for r in sub:
            for k, v in (r.get("uv_modes") or {}).items():
                uvm[k] += v
        tot = sum(uvm.values()) or 1
        print("  UV 模式:", {k: f"{v/tot*100:.0f}%" for k, v in uvm.items()})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=os.path.join(REPO, "材料", "_dataset.json"))
    args = ap.parse_args()
    if not os.path.isdir(CORPUS):
        print(f"语料目录不存在: {CORPUS}", file=sys.stderr)
        return 2
    recs = scan()
    json.dump(recs, open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"dataset -> {args.json}\n")
    summarize(recs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
