# -*- coding: utf-8 -*-
"""Final verification of the v7d pack against the v7c backup."""
import json, io, os

ROOT = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models"
new = json.load(io.open(os.path.join(ROOT, "main.json"), encoding="utf-8"))["minecraft:geometry"][0]["bones"]
old = json.load(io.open(os.path.join(ROOT, "main.v7c-bak.json"), encoding="utf-8"))["minecraft:geometry"][0]["bones"]
NEW = {b["name"]: b for b in new}
OLD = {b["name"]: b for b in old}

print("bones: old %d new %d" % (len(old), len(new)))
tc_new = sum(len(b.get("cubes", [])) for b in new)
tc_old = sum(len(b.get("cubes", [])) for b in old)
print("cubes: old %d new %d (limit 1600)" % (tc_old, tc_new))

added = [n for n in NEW if n not in OLD]
removed = [n for n in OLD if n not in NEW]
print("added bones:", added, "removed:", removed)

changed_other = []
for n in OLD:
    if n in ("Hair", "HairBack", "hl_side", "front_h1", "corner_h1", "HairCap"):
        continue
    o = OLD[n].get("cubes", [])
    nw = NEW[n].get("cubes", [])
    if len(o) != len(nw):
        changed_other.append((n, len(o), len(nw)))
print("other bones with changed cube count:", changed_other or "none")

print("\nhair bones:")
for n in ["Hair", "HairCap", "HairBack", "hl_side", "front_h1", "corner_h1", "TwinTail_L", "TwinTail_R", "Ribbon", "HairBow_R"]:
    b = NEW.get(n)
    print("  %-11s %3d  parent=%s" % (n, len(b.get("cubes", [])), b.get("parent")))

# rotations used by hair
import collections
rot = collections.Counter()
maxrot = 0.0
for n in ["HairCap", "HairBack", "hl_side", "front_h1", "corner_h1"]:
    for c in NEW[n].get("cubes", []):
        r = c.get("rotation") or [0, 0, 0]
        nz = sum(1 for v in r if abs(v) > 0.01)
        rot[nz] += 1
        maxrot = max(maxrot, max(abs(v) for v in r))
print("\nnonzero rotation components per hair cube:", dict(sorted(rot.items())))
print("max |rotation| component: %.1f deg" % maxrot)

# twin tails untouched?
same = all(OLD[n].get("cubes") == NEW[n].get("cubes") for n in
           ["TwinTail_L", "TwinTail_R", "Ribbon", "HairBow_R", "Head", "Horn_L", "Horn_R",
            "Skirt", "FrontSkirt", "BackSkirt", "LeftSkirt", "RightSkirt"])
print("untouched: twin tails / ribbons / head / horns / skirt ->", same)
