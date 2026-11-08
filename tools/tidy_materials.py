#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""整理仓库根目录下的 material/ 材料目录。

用法:
    python tidy_materials.py --dry     # 只打印计划
    python tidy_materials.py           # 执行

原则:
  1. 先建目录结构，再逐个 move；同目标已存在则加序号，绝不覆盖。
  2. 只删除"确认无用且有替代"的文件（重复副本 / 完整 Blockbench 安装包）。
  3. 其余低价值但可能有用的，移到 99-归档/ 而不是删。
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "材料")
R = lambda *p: os.path.join(ROOT, *p)

# ---------------------------------------------------------------- 目录结构
DIRS = [
    "01-工具",
    "02-教程/建模/blockbench入门到出门",
    "02-教程/动画-molang",
    "02-教程/像素画",
    "02-教程/绘画基础",
    "03-语料/bbmodel",
    "03-语料/ysm包",
    "03-语料/成品ysm",
    "03-语料/动画片段",
    "99-归档/mc-mods",
    "99-归档/旧版本工具",
    "99-归档/重复副本",
    "99-归档/大体积书籍",
]

# ---------------------------------------------------------------- 移动规则
# (源相对路径, 目标目录相对路径)
MOVE: list[tuple[str, str]] = [
    # 工具（ysm-utils 保留最高版本 2.6.0）
    ("BlockBench插件/ysm-utils.js", "01-工具"),
    ("制作模型相关/shape_generator.js", "01-工具"),
    # 教程 - 建模
    ("制作模型相关/YSM模组说明书.pdf", "02-教程/建模"),
    ("制作模型相关/免责声明.pdf", "02-教程/建模"),
    ("教程补充/基岩版模型填缝思路.pdf", "02-教程/建模"),
    # 教程 - 动画 / molang
    ("制作模型相关/常用的molang语言整理与收集1.6.pdf", "02-教程/动画-molang"),
    ("教程补充/控制函数、贝塞尔曲线算法、一阶响应处理阶跃.pdf", "02-教程/动画-molang"),
    # 教程 - 像素画
    ("像素画焚诀/[教程]汉化版PixelLogic-monkiearz.pdf", "02-教程/像素画"),
    ("像素画焚诀/[教程]配色原理&色板使用.pdf", "02-教程/像素画"),
    ("像素画焚诀/[教程]线条原则.pdf", "02-教程/像素画"),
    ("像素宝典.zip", "02-教程/像素画"),
    # 教程 - 绘画基础
    ("教程补充/绘画的成功秘诀.pdf", "02-教程/绘画基础"),
    ("教程补充/CG参考网址.docx", "02-教程/绘画基础"),
    # 教程 - Blockbench 长截图
    ("教程文档更新记录/Blockbench-入门到出门10.13.png", "02-教程/建模/blockbench入门到出门"),
    ("教程文档更新记录/Blockbench-入门到出门10.14.png", "02-教程/建模/blockbench入门到出门"),
    ("教程文档更新记录/Blockbench-入门到出门10.15.png", "02-教程/建模/blockbench入门到出门"),
    ("教程文档更新记录/Blockbench-入门到出门10.16【大纲】.png", "02-教程/建模/blockbench入门到出门"),
    # 归档
    ("教程补充/肖玮春_人体结构原理与绘画教学.PDF", "99-归档/大体积书籍"),
    ("制作模型相关/ysm-utils.js", "99-归档/旧版本工具"),   # 2.5.0，保留 2.6.0
]

# 通配移动：(源目录, 扩展名, 目标目录)
MOVE_GLOB: list[tuple[str, str, str]] = [
    ("制作模型相关", ".jar", "99-归档/mc-mods"),   # Minecraft 模组，建模用不到
]

# 目录整体迁移：源目录下所有文件 → 目标目录
MOVE_DIR: list[tuple[str, str]] = [
    ("共享模型（bbmodel文件）", "03-语料/bbmodel"),
    ("共享模型（压缩包）", "03-语料/ysm包"),
    ("ysm格式文件(直接放入文件夹即可使用)", "03-语料/成品ysm"),
    ("动作文件夹", "03-语料/动画片段"),
    ("案例模型文件", "03-语料/bbmodel"),
]

# 删除（确认无用：有更新的替代 / 纯安装包）
DELETE: list[tuple[str, str]] = [
    ("制作模型相关/Blockbench_4.10.3.exe", "完整 Blockbench 4.10.3 安装包；本项目用 vendor/ 构建的 5.2.2"),
    ("制作模型相关/ysm-utils (1).js", "ysm-utils 1.1.0 重复副本，已有 2.6.0"),
    ("制作模型相关/ysm-utils (2).js", "ysm-utils 1.1.0 重复副本，已有 2.6.0"),
    ("制作模型相关/YSM模组说明书 (1).pdf", "与 YSM模组说明书.pdf 完全相同"),
    ("共享模型（bbmodel文件）/蚊子 (1).bbmodel", "与 蚊子.bbmodel 完全相同"),
    ("共享模型（bbmodel文件）/真实系人物模型 简版 1.0 (1).bbmodel", "与 无后缀版本完全相同"),
    ("共享模型（bbmodel文件）/球 (1).bbmodel", "与 球.bbmodel 完全相同"),
    ("ysm格式文件(直接放入文件夹即可使用)/umy (1).ysm", "与 umy.ysm 完全相同"),
    ("ysm格式文件(直接放入文件夹即可使用)/sl (1).ysm", "与 sl.ysm 完全相同"),
    ("ysm格式文件(直接放入文件夹即可使用)/merry (1).ysm", "与 merry.ysm 完全相同"),
]


def ensure_dirs(dry: bool) -> None:
    for d in DIRS:
        p = R(d)
        if not os.path.isdir(p):
            if not dry:
                os.makedirs(p, exist_ok=True)
            print(f"  [mkdir] {d}")


def unique_dest(folder: str, name: str) -> str:
    dst = R(folder, name)
    if not os.path.exists(dst):
        return dst
    stem, ext = os.path.splitext(name)
    i = 1
    while True:
        cand = R(folder, f"{stem} ({i}){ext}")
        if not os.path.exists(cand):
            return cand
        i += 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    dry = args.dry

    if not os.path.isdir(ROOT):
        print(f"材料 目录不存在: {ROOT}", file=sys.stderr)
        return 2

    print(f"{'[DRY] ' if dry else ''}根目录: {ROOT}\n")
    print("== 建立目录 ==")
    ensure_dirs(dry)

    print("\n== 删除 ==")
    freed = 0
    for rel, why in DELETE:
        src = R(*rel.replace("/", os.sep).split(os.sep))
        if not os.path.exists(src):
            print(f"  [skip] {rel}（不存在）")
            continue
        sz = os.path.getsize(src)
        freed += sz
        print(f"  [del] {rel}  ({sz/1024/1024:.2f} MB)  -- {why}")
        if not dry:
            os.remove(src)

    print("\n== 单文件移动 ==")
    moved = 0
    for rel, folder in MOVE:
        src = R(*rel.replace("/", os.sep).split(os.sep))
        if not os.path.exists(src):
            print(f"  [skip] {rel}（不存在）")
            continue
        dst = unique_dest(folder, os.path.basename(src))
        print(f"  [move] {rel}\n         -> {os.path.relpath(dst, ROOT)}")
        if not dry:
            shutil.move(src, dst)
        moved += 1

    print("\n== 通配移动 ==")
    for src_dir, ext, folder in MOVE_GLOB:
        d = R(src_dir)
        if not os.path.isdir(d):
            continue
        hits = [f for f in os.listdir(d) if f.lower().endswith(ext)]
        print(f"  [move-glob] {src_dir}/*{ext} -> {folder}/  ({len(hits)} files)")
        for f in hits:
            if not dry:
                shutil.move(os.path.join(d, f), unique_dest(folder, f))
        moved += len(hits)

    print("\n== 目录整体迁移 ==")
    for src_dir, folder in MOVE_DIR:
        src = R(src_dir)
        if not os.path.isdir(src):
            print(f"  [skip] {src_dir}/（不存在）")
            continue
        files = [f for f in os.listdir(src) if os.path.isfile(os.path.join(src, f))]
        subs = [f for f in os.listdir(src) if os.path.isdir(os.path.join(src, f))]
        print(f"  [move-dir] {src_dir}/ -> {folder}/  ({len(files)} files, {len(subs)} subdir)")
        if dry:
            continue
        for f in files:
            shutil.move(os.path.join(src, f), unique_dest(folder, f))
        for s in subs:
            target = R(folder, s)
            if os.path.exists(target):
                target = unique_dest(folder, s)
            shutil.move(os.path.join(src, s), target)
        # 清空后删除空目录
        try:
            os.rmdir(src)
        except OSError:
            print(f"    [warn] 目录非空，保留: {src_dir}")

    print(f"\n合计: 删除 {freed/1024/1024:.2f} MB, 移动 {moved} 个单文件 + {len(MOVE_DIR)} 个目录")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
