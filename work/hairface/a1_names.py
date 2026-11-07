import json, os, sys, re
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ysmlib as Y

names = Y.model_dirs()
print("models:", len(names))

allbone = Counter()
hairlike = Counter()
model_hairbones = {}
fail = []
for n in names:
    doc = Y.load(n)
    if not doc:
        fail.append(n); continue
    bs = Y.bones(doc)
    hb = []
    for b in bs:
        nm = b.get("name") or ""
        allbone[nm] += 1
        if Y.is_hair_bone(nm):
            hairlike[nm] += 1
            hb.append(nm)
    model_hairbones[n] = hb

print("failed loads:", fail)
print("distinct bone names:", len(allbone))
print("\n=== top 40 bone names overall ===")
for k, v in allbone.most_common(40):
    print(f"{v:4d}  {k}")

print("\n=== hair-ish bone names (count>=3), %d distinct ===" % len([1 for v in hairlike.values() if v >= 3]))
for k, v in sorted(hairlike.items(), key=lambda x: -x[1])[:120]:
    print(f"{v:4d}  {k}")
