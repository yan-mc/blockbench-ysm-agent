#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并 OCR 切条结果，清理 CJK 空格与常见错字，重建阅读顺序。

用法: python tools/merge_ocr.py
输入: workspace/_ocr/ocr_*.json
输出: workspace/_ocr/merged/*.txt  + workspace/_ocr/merged/*.md
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCR_DIR = os.path.join(REPO, "workspace", "_ocr")
OUT_DIR = os.path.join(OCR_DIR, "merged")

# ---------------------------------------------------------------- 文本清洗
CJK = r"\u4e00-\u9fff\u3400-\u4dbf"

# 常见 OCR 错字（针对 Blockbench/YSM 语境）
FIXES = [
    (r"\bBIockbench\b", "Blockbench"),
    (r"\bB1ockbench\b", "Blockbench"),
    (r"Blockbench?中", "Blockbench 中"),
    (r"Minecr\s*酣", "Minecraft"),
    (r"Minecraf(?![t])", "Minecraft"),
    (r"Minecr(?:af|afl|at)\b", "Minecraft"),
    (r"彳\s*氵\s*亍\s*生", "衍生"),
    (r"\bwp\s*y\b", "lowpoly"),
    (r"\blow\s*[pP]\s*oly\b", "lowpoly"),
    (r"\bgeo\s*[.．]\s*json\b", "geo.json"),
    (r"[.．]\s*json\b", ".json"),
    (r"[.．]\s*png\b", ".png"),
    (r"([0-9])\s*[．\.]\s*([0-9])", r"\1.\2"),      # 22．5 -> 22.5
    (r"(?<=\d)\s*[Xx×]\s*(?=\d)", "x"),              # 3X3X3 -> 3x3x3
    (r"枢轴点?为匝", "枢轴点为轴"),
    (r"以方块的枢轴点", "以方块的枢轴点"),
    (r"\bTACZ\b", "TACZ"),
    (r"龙核", "龙核"),
]


def clean(text: str) -> str:
    s = text
    # 合并 CJK 之间的空格（Windows OCR 逐字加空格）
    s = re.sub(rf"(?<=[{CJK}])\s+(?=[{CJK}])", "", s)
    # CJK 与全角/半角标点之间
    s = re.sub(rf"(?<=[{CJK}])\s+(?=[，。、；：！？（）《》“”‘’])", "", s)
    s = re.sub(rf"(?<=[，。、；：！？（）《》“”‘’])\s+(?=[{CJK}])", "", s)
    # 数字与单位之间
    s = re.sub(r"(?<=\d)\s+(?=[%个层倍秒帧度])", "", s)
    for pat, rep in FIXES:
        s = re.sub(pat, rep, s)
    return s.strip()


def cjk_ratio(s: str) -> float:
    if not s:
        return 0.0
    n = sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff")
    return n / len(s)


# ---------------------------------------------------------------- 合并
def load_strips(json_path: str) -> list[dict]:
    """把切条 OCR 结果展开成绝对坐标的行。"""
    data = json.load(open(json_path, encoding="utf-8"))
    out = []
    for item in data:
        m = re.search(r"strip_(\d+)\.png", item["file"])
        if not m:
            continue
        off = int(m.group(1))
        for ln in item.get("lines") or []:
            txt = (ln.get("text") or "").strip()
            if not txt:
                continue
            out.append({
                "text": txt,
                "x": float(ln["x"]),
                "y": float(ln["y"]) + off,
                "x2": float(ln["x2"]),
                "y2": float(ln["y2"]) + off,
                "h": float(ln["y2"]) - float(ln["y"]),
            })
    return out


def dedupe_overlap(lines: list[dict]) -> list[dict]:
    """切条有 120px 重叠：同一行会在相邻两条里各出现一次。按 (文本, y) 去重。"""
    lines = sorted(lines, key=lambda r: (r["y"], r["x"]))
    out: list[dict] = []
    for ln in lines:
        dup = False
        for prev in out[-12:]:
            if abs(prev["y"] - ln["y"]) < 8 and prev["text"] == ln["text"]:
                dup = True
                break
        if not dup:
            out.append(ln)
    return out


def group_columns(lines: list[dict], gap: float = 40.0) -> list[list[dict]]:
    """按 y 聚成视觉行，再按 x 分列。"""
    rows: list[list[dict]] = []
    for ln in sorted(lines, key=lambda r: r["y"]):
        placed = False
        for row in rows:
            if abs(row[0]["y"] - ln["y"]) < gap:
                row.append(ln)
                placed = True
                break
        if not placed:
            rows.append([ln])
    return [sorted(r, key=lambda x: x["x"]) for r in rows]


def render_text(path: str, lines: list[dict]) -> str:
    """按视觉行输出：同行的多段用 ' | ' 分隔；不同列缩进体现 x 位置。"""
    rows = group_columns(lines)
    out = []
    for row in rows:
        parts = []
        for ln in row:
            indent = int(ln["x"] / 60)
            parts.append(" " * indent + clean(ln["text"]))
        out.append(" ‖ ".join(p.strip() for p in parts))
    return "\n".join(out)


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(OCR_DIR, "ocr_*.json")))
    if not files:
        print("no ocr json found", file=sys.stderr)
        return 2
    total = 0
    for fp in files:
        name = os.path.basename(fp)[len("ocr_"):-len(".json")]
        lines = load_strips(fp)
        before = len(lines)
        lines = dedupe_overlap(lines)
        total += len(lines)
        txt = render_text(os.path.join(OUT_DIR, name), lines)
        out = os.path.join(OUT_DIR, name + ".txt")
        open(out, "w", encoding="utf-8").write(txt)
        # 统计
        cjk = sum(cjk_ratio(l["text"]) for l in lines) / max(1, len(lines))
        print(f"{name}: {before} -> {len(lines)} 行 (去重 {before-len(lines)}), "
              f"平均中文占比 {cjk*100:.0f}% -> {os.path.relpath(out, REPO)}")
    print(f"\n合计 {total} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
