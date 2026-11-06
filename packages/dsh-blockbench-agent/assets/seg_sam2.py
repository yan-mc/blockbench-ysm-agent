#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SAM2.1 ONNX 自动部件分割（T1 能力）。

给定一张立绘，用点网格提示自动分割出若干部件区域，输出：
  - parts.json  每个部件的 bbox / 面积 / iou / 质心 / 掩膜文件
  - montage.png 一张对照图：[原图] + 每个部件高亮（固定格子）
  - masks/*.png 每部件二值掩膜

设计要点：
  * 只用 CPU（onnxruntime CPUExecutionProvider），不要求 GPU —— 这是 T1 与 T2 的分界。
  * 逐批跑 decoder，避免 (P,3,256,256) 一次撑爆内存。
  * 结果做面积过滤 + 掩膜 NMS，避免同一物体被切成几十个碎块。

用法：
  python seg_sam2.py --model-dir <dir> --image <png> --out-dir <dir> [--grid 12] [--max-parts 10]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
from PIL import Image

MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)
SIZE = 1024
MASK_SIZE = 256


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def load_encoder(model_dir: str, threads: int):
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    if threads > 0:
        so.intra_op_num_threads = threads
    path = os.path.join(model_dir, "vision_encoder_int8.onnx")
    log(f"[sam2] loading encoder {path}")
    return ort.InferenceSession(path, so, providers=["CPUExecutionProvider"])


def load_decoder(model_dir: str, threads: int):
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    if threads > 0:
        so.intra_op_num_threads = threads
    path = os.path.join(model_dir, "prompt_encoder_mask_decoder_int8.onnx")
    log(f"[sam2] loading decoder {path}")
    return ort.InferenceSession(path, so, providers=["CPUExecutionProvider"])


def preprocess(img: Image.Image) -> np.ndarray:
    """RGBA->白底 RGB，resize 到 1024x1024，ImageNet 归一化，NCHW。"""
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, img)
    img = img.convert("RGB").resize((SIZE, SIZE), Image.BILINEAR)
    x = np.asarray(img, dtype=np.float32) / 255.0
    x = x.transpose(2, 0, 1)
    x = (x - MEAN) / STD
    return x[None, ...].astype(np.float32)


def grid_points(n: int) -> np.ndarray:
    """n x n 网格点（1024 坐标系），返回 (P,2)。"""
    step = SIZE / (n + 1)
    pts = []
    for iy in range(n):
        for ix in range(n):
            pts.append([step * (ix + 1), step * (iy + 1)])
    return np.asarray(pts, dtype=np.float32)


def mask_iou(a: np.ndarray, b: np.ndarray) -> float:
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter) / float(union) if union else 0.0


# 每个部件用固定色相高亮，比"原色+压暗背景"更易读
HUES = [
    (255, 82, 82), (82, 176, 255), (110, 226, 120), (255, 198, 62),
    (198, 120, 255), (72, 226, 214), (255, 138, 198), (186, 186, 92),
    (148, 214, 255), (232, 122, 122), (128, 232, 170), (255, 176, 96),
]


def make_overlay(src: np.ndarray, arr: np.ndarray, hue) -> Image.Image:
    """背景压暗到 12%，掩膜区刷成「原色 35% + 色相 65%」，一眼能看出是哪个部件。"""
    base = src.astype(np.float32) * 0.12
    tinted = src.astype(np.float32) * 0.35 + np.asarray(hue, dtype=np.float32) * 0.65
    base[arr] = tinted[arr]
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--grid", type=int, default=12, help="点网格边长，默认 12（144 点）")
    ap.add_argument("--batch", type=int, default=32, help="decoder 每次处理多少点")
    ap.add_argument("--max-parts", type=int, default=10)
    ap.add_argument("--min-area", type=float, default=0.004, help="最小面积占比")
    ap.add_argument("--max-area", type=float, default=0.72, help="最大面积占比（超过视为整图/背景）")
    ap.add_argument("--min-iou", type=float, default=0.35, help="最小 IoU 置信度")
    ap.add_argument("--nms-iou", type=float, default=0.62)
    ap.add_argument("--threads", type=int, default=0)
    args = ap.parse_args()

    t0 = time.time()
    img = Image.open(args.image)
    orig_w, orig_h = img.size
    pixel_values = preprocess(img)

    enc = load_encoder(args.model_dir, args.threads)
    t1 = time.time()
    embeds = enc.run(None, {"pixel_values": pixel_values})
    log(f"[sam2] encoder {time.time()-t1:.1f}s  outputs={[e.shape for e in embeds]}")

    dec = load_decoder(args.model_dir, args.threads)
    pts = grid_points(args.grid)
    total_px = float(orig_w * orig_h)

    cands = []
    t2 = time.time()
    # 关键：模型的 input_points 第二维固定为 1（一个「提示集」= 一个物体），
    # 多个点会被当成同一物体的多个正样本。所以自动分割要**沿 batch 维**放不同点，
    # 每个 batch 元素各自一个点 → 各自一个物体。
    for start in range(0, len(pts), args.batch):
        chunk = pts[start:start + args.batch]
        b = len(chunk)
        feeds = {
            "input_points": chunk[:, None, None, :].astype(np.float32),        # (B,1,1,2)
            "input_labels": np.ones((b, 1, 1), dtype=np.int64),                # (B,1,1)
            "input_boxes": np.zeros((b, 0, 4), dtype=np.float32),              # 只用点提示
            "image_embeddings.0": np.repeat(embeds[0], b, axis=0),
            "image_embeddings.1": np.repeat(embeds[1], b, axis=0),
            "image_embeddings.2": np.repeat(embeds[2], b, axis=0),
        }
        iou_scores, pred_masks, obj_logits = dec.run(None, feeds)
        iou_scores = np.asarray(iou_scores)          # (B,1,3)
        pred_masks = np.asarray(pred_masks)          # (B,1,3,256,256)
        for i in range(b):
            scores = iou_scores[i, 0]                # (3,)
            best = int(scores.argmax())
            m = pred_masks[i, 0, best] > 0.0
            area = int(m.sum())
            if area == 0:
                continue
            cands.append({
                "point": [round(float(chunk[i][0]), 1), round(float(chunk[i][1]), 1)],
                "iou": float(scores[best]),
                "mask": m,
                "area_ratio": area / float(MASK_SIZE * MASK_SIZE),
            })
    log(f"[sam2] decoder {time.time()-t2:.1f}s  candidates={len(cands)}")

    # 面积过滤 + IoU 下限（低置信掩膜噪声大，只会干扰判读）
    before = len(cands)
    cands = [c for c in cands
             if args.min_area <= c["area_ratio"] <= args.max_area and c["iou"] >= args.min_iou]
    log(f"[sam2] filter {before} -> {len(cands)} (area {args.min_area}..{args.max_area}, iou>={args.min_iou})")
    cands.sort(key=lambda c: c["area_ratio"] * max(0.05, c["iou"]), reverse=True)

    # 掩膜 NMS
    kept = []
    for c in cands:
        if any(mask_iou(c["mask"], k["mask"]) > args.nms_iou for k in kept):
            continue
        kept.append(c)
        if len(kept) >= args.max_parts:
            break
    log(f"[sam2] after NMS kept={len(kept)}")

    # 掩膜放大到原图尺寸，产出图与清单
    os.makedirs(args.out_dir, exist_ok=True)
    mask_dir = os.path.join(args.out_dir, "masks")
    os.makedirs(mask_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(args.image))[0]

    parts = []
    overlays = []
    src_rgb = np.asarray(img.convert("RGB"), dtype=np.uint8)
    partition = np.zeros_like(src_rgb)          # 所有部件各涂一色，一眼看分块
    for idx, c in enumerate(kept):
        m256 = Image.fromarray((c["mask"].astype(np.uint8) * 255), mode="L")
        m_full = m256.resize((orig_w, orig_h), Image.NEAREST)
        arr = np.asarray(m_full) > 127
        ys, xs = np.nonzero(arr)
        if len(xs) == 0:
            continue
        hue = HUES[idx % len(HUES)]
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
        area_px = int(arr.sum())
        mask_path = os.path.join(mask_dir, f"{base}_part{idx:02d}.png")
        Image.fromarray((arr.astype(np.uint8) * 255), mode="L").save(mask_path)

        # 部件主色（掩膜内像素中位数）
        px = src_rgb[arr]
        color = [int(v) for v in np.median(px, axis=0)] if len(px) else [128, 128, 128]

        overlays.append(make_overlay(src_rgb, arr, hue))
        partition[arr] = hue

        parts.append({
            "index": idx,
            "hue": list(hue),
            "bbox": bbox,
            "bbox_norm": [round(bbox[0] / orig_w, 4), round(bbox[1] / orig_h, 4),
                          round(bbox[2] / orig_w, 4), round(bbox[3] / orig_h, 4)],
            "area_px": area_px,
            "area_pct": round(area_px / total_px * 100, 2),
            "centroid": [round(float(xs.mean()) / orig_w, 4), round(float(ys.mean()) / orig_h, 4)],
            "color": color,
            "iou": round(c["iou"], 4),
            "mask": os.path.basename(mask_path),
        })

    # 对照图：原图 + 各部件彩色高亮 + 最终分块图
    cell = 220
    cells = [img.convert("RGB")] + overlays + [Image.fromarray(partition)]
    cols = min(4, max(1, len(cells)))
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * cell), (22, 22, 26))
    for i, im in enumerate(cells):
        w, h = im.size
        s = min(cell / w, cell / h)
        small = im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
        x = (i % cols) * cell + (cell - small.width) // 2
        y = (i // cols) * cell + (cell - small.height) // 2
        sheet.paste(small, (x, y))
    sheet_path = os.path.join(args.out_dir, "montage.png")
    sheet.save(sheet_path)

    result = {
        "ok": True,
        "image": os.path.abspath(args.image),
        "size": [orig_w, orig_h],
        "grid": args.grid,
        "candidates": len(cands),
        "parts": parts,
        "montage": sheet_path,
        "montage_size": list(sheet.size),
        "elapsed_ms": int((time.time() - t0) * 1000),
    }
    print(json.dumps(result, ensure_ascii=False))
    log(f"[sam2] done in {time.time()-t0:.1f}s  parts={len(parts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
