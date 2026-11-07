#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第一遍扫描：骨骼名词表、语义验证、区域归类探针。"""
import json
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import ysm_lib as L


def main():
    names = L.all_models()
    print("models:", len(names))
    vocab = Counter()
    vocab_cubes = Counter()
    models_of = defaultdict(set)
    per_model = {}
    for n in names:
        m = L.load_model(n)
        cnt = {}
        for bn, b in m.bones.items():
            low = bn.lower()
            vocab[low] += 1
            vocab_cubes[low] += len(b.cubes)
            models_of[low].add(n)
            cnt[bn] = len(b.cubes)
        per_model[n] = {
            "bones": len(m.bones),
            "cubes": m.total_cubes(),
            "desc": m.desc,
        }
    print("unique bone names:", len(vocab))
    with open(r"F:\Deepseek_harness\blockbench\tools\curve\out_vocab.json", "w", encoding="utf-8") as f:
        json.dump({
            "vocab": vocab.most_common(),
            "vocab_cubes": vocab_cubes.most_common(),
            "models_of": {k: len(v) for k, v in models_of.items()},
            "per_model": per_model,
        }, f, ensure_ascii=False)
    for k, v in vocab.most_common(80):
        print(f"{v:4d}  {k}  cubes={vocab_cubes[k]} models={len(models_of[k])}")


if __name__ == "__main__":
    main()
