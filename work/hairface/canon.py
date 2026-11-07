"""Canonical hair/face budget per model, excluding glow duplicates, ornaments, dup skeletons."""
import sys, os, json, re, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core as C
import ysmlib as Y
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

RE_GLOW = re.compile(r"(ysmglow|glow|emissive|_e\d|light)", re.I)
RE_CLOTH_HAIR = re.compile(r"(clothhair|cloth_hair|clothhair)", re.I)
RE_ORN = re.compile(
    r"(flower|ribbon|band|pin\b|pin_|clip|bell|lingdang|ornament|accessor|bow\b|bow\d|crown|tiara|"
    r"hat\b|hat\d|headdress|decor|jewel|gem|bead|tassel|choker|"
    r"花|饰|铃|簪|冠|帯|带|结|钗|chaizi|fashi|发饰)", re.I)
RE_HAIR = re.compile(
    r"(hair|bangs?|ahoge|ponytail|twintail|twin_?tail|braid|fringe|"
    r"刘海|头发|发|髪|呆毛|马尾|辫|鬓|side_?lock|hime|mao)", re.I)


def classify_bone(n):
    """-> 'glow' | 'ornament' | 'hair' | 'face' | 'other'"""
    if RE_GLOW.search(n):
        return "glow"
    if RE_CLOTH_HAIR.search(n):
        return "ornament"
    if RE_HAIR.search(n):
        if RE_ORN.search(n):
            return "ornament"
        return "hair"
    if C.RE_FACE.search(n):
        return "face"
    return "other"


def build(model):
    doc = Y.load(model)
    if not doc:
        return None
    bs = Y.bones(doc)
    if not bs:
        return None
    children = defaultdict(list)
    byname = defaultdict(list)
    for b in bs:
        children[b.get("parent")].append(b)
        byname[b.get("name")].append(b)

    # structural classification per bone; propagate hair-ness to children
    cls = {}
    for b in bs:
        n = b.get("name") or ""
        cls[b.get("name")] = classify_bone(n)

    # subtree inclusive cube list, avoiding infinite loops by name
    def subtree(name, seen=None):
        seen = seen or set()
        if name in seen:
            return []
        seen.add(name)
        acc = []
        for b in byname.get(name, []):
            acc.extend(b.get("cubes") or [])
            for c in children.get(name, []):
                acc.extend(subtree(c.get("name"), seen))
        return acc

    # hair roots = hair-class bones whose ancestors are not hair-class
    def ancestors(name):
        out = []
        seen = set()
        cur = None
        for b in byname.get(name, []):
            cur = b.get("parent")
            break
        while cur and cur not in seen:
            seen.add(cur)
            out.append(cur)
            nb = byname.get(cur)
            cur = nb[0].get("parent") if nb else None
        return out

    hair_roots = []
    for b in bs:
        n = b.get("name") or ""
        if cls[n] != "hair":
            continue
        if any(cls.get(a) == "hair" for a in ancestors(n)):
            continue
        hair_roots.append(b)

    hair_cubes = 0
    per_root = {}
    for r in hair_roots:
        n = r.get("name")
        k = len(subtree(n))
        per_root[n] = k
        hair_cubes += k

    orn_cubes = 0
    orn_bones = []
    for b in bs:
        n = b.get("name") or ""
        if cls[n] != "ornament":
            continue
        if any(cls.get(a) == "ornament" for a in ancestors(n)):
            continue
        orn_bones.append(n)
        orn_cubes += len(subtree(n))

    glow_cubes = 0
    for b in bs:
        n = b.get("name") or ""
        if cls[n] != "glow":
            continue
        if any(cls.get(a) == "glow" for a in ancestors(n)):
            continue
        glow_cubes += len(subtree(n))

    return dict(doc=doc, bones=bs, byname=byname, children=children, cls=cls,
                hair_roots=hair_roots, per_root=per_root, hair_cubes=hair_cubes,
                orn_cubes=orn_cubes, orn_bones=orn_bones, glow_cubes=glow_cubes,
                total=Y.model_total_cubes(bs), dup=C.struct_duplicate_factor([b.get('name') for b in bs]),
                subtree=subtree)


if __name__ == "__main__":
    models = Y.model_dirs()
    rows = []
    for m in models:
        r = build(m)
        if not r:
            continue
        d = r["dup"]
        rows.append(dict(model=m, total=r["total"], dup=d,
                         hair=r["hair_cubes"], hair_pc=round(r["hair_cubes"] / d, 1),
                         orn=r["orn_cubes"], orn_pc=round(r["orn_cubes"] / d, 1),
                         glow=r["glow_cubes"],
                         roots=len(r["hair_roots"]),
                         total_pc=round(r["total"] / d, 1),
                         per_root=r["per_root"]))
    json.dump(rows, open(os.path.join(OUT, "canon.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    have = [r for r in rows if r["hair_pc"] > 0]
    print("models", len(rows), "with structural hair", len(have))
    print("glow-dup models:", sum(1 for r in rows if r["glow"] > 0), " glow cubes total", sum(r["glow"] for r in rows))
    print("models with hair ornaments:", sum(1 for r in rows if r["orn_pc"] > 0))
    hc = [r["hair_pc"] for r in have]
    print("hair cubes/copy: med=%.0f p25=%.0f p75=%.0f p90=%.0f max=%.0f" %
          (C.pct(hc, .5), C.pct(hc, .25), C.pct(hc, .75), C.pct(hc, .9), max(hc)))
    rt = [r["roots"] for r in have]
    print("roots: med=%.0f p75=%.0f p90=%.0f max=%.0f" % (C.pct(rt, .5), C.pct(rt, .75), C.pct(rt, .9), max(rt)))
    sh = [r["hair_pc"] / r["total_pc"] for r in have]
    print("share: med=%.1f%% p75=%.1f%% p90=%.1f%%" % (100 * C.pct(sh, .5), 100 * C.pct(sh, .75), 100 * C.pct(sh, .9)))
    print("\ntop 20 canonical:")
    for r in sorted(have, key=lambda x: -x["hair_pc"])[:20]:
        print("%-40s hair=%4.0f roots=%3d orn=%4d glow=%4d total=%5.0f share=%3.0f%%" % (
            r["model"][:38], r["hair_pc"], r["roots"], r["orn_pc"], r["glow"], r["total_pc"],
            100 * r["hair_pc"] / max(r["total_pc"], 1)))
    print("\nzero-hair models:", [r["model"] for r in rows if r["hair_pc"] == 0])
