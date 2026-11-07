"""Nearest-classified-ancestor model (v3)."""
import sys, os, json, re, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core as C
import ysmlib as Y
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

RE_GLOW = re.compile(r"(ysmglow|glow|emissive)", re.I)
RE_ORN = re.compile(
    r"(clothhair|flower|ribbon|band\b|band\d|hairpin|pin\b|pin_|clip|bell|lingdang|ornament|"
    r"accessor|\bbow\b|bow\d|crown|tiara|\bhat\b|hat\d|headdress|decor|jewel|gem|bead|tassel|"
    r"花|饰|铃|簪|冠|帯|带|结|钗|fashi|chaizi|maozi)", re.I)
RE_HAIR = re.compile(
    r"(hair|bangs?|ahoge|ponytail|twintail|twin_?tail|braid|fringe|"
    r"刘海|头发|发|髪|呆毛|马尾|辫|鬓|side_?lock|hime)", re.I)
RE_FACE = re.compile(
    r"(face|eye|eyelid|pupil|iris|sclera|brow|lash|mouth|lip|nose|cheek|blush|tear|tongue|"
    r"fang|tooth|muzzle|\bear\b|\bears\b|earring|ear_|_ear)", re.I)


def own_class(n):
    if RE_GLOW.search(n):
        return "glow"
    if RE_ORN.search(n):
        return "ornament"
    if RE_HAIR.search(n):
        return "hair"
    if RE_FACE.search(n):
        return "face"
    return None


class Model:
    def __init__(self, name):
        self.name = name
        self.doc = Y.load(name)
        self.bones = Y.bones(self.doc)
        self.parent = {}
        self.kids = defaultdict(list)
        self.by = defaultdict(list)
        for b in self.bones:
            n = b.get("name")
            self.parent[n] = b.get("parent")
            self.kids[b.get("parent")].append(b)
            self.by[n].append(b)
        self.own = {b.get("name"): own_class(b.get("name") or "") for b in self.bones}
        self.eff = {}
        for b in self.bones:
            n = b.get("name")
            e = None
            cur = n
            guard = 0
            while cur is not None and guard < 64:
                oc = self.own.get(cur)
                if oc:
                    e = oc
                    break
                cur = self.parent.get(cur)
                guard += 1
            self.eff[n] = e or "other"
        self.total = Y.model_total_cubes(self.bones)
        self.dup = C.struct_duplicate_factor([b.get("name") for b in self.bones])

    def bones_of(self, cls):
        return [b for b in self.bones if self.eff.get(b.get("name")) == cls]

    def cubes_of(self, cls):
        return sum(len(b.get("cubes") or []) for b in self.bones
                   if self.eff.get(b.get("name")) == cls)

    def pairs_of(self, cls):
        out = []
        for b in self.bones:
            if self.eff.get(b.get("name")) == cls:
                for c in (b.get("cubes") or []):
                    out.append((b, c))
        return out


if __name__ == "__main__":
    models = Y.model_dirs()
    rows = []
    for m in models:
        M = Model(m)
        if not M.bones:
            continue
        hc = M.cubes_of("hair")
        rows.append(dict(model=m, total=M.total, dup=M.dup, hair=hc,
                         hair_pc=round(hc / M.dup, 1),
                         orn=M.cubes_of("ornament"), glow=M.cubes_of("glow"),
                         face=M.cubes_of("face"),
                         strand_bones=len([b for b in M.bones_of("hair") if (b.get("cubes") or [])]),
                         hair_bones=len(M.bones_of("hair")),
                         total_pc=round(M.total / M.dup, 1)))
    json.dump(rows, open(os.path.join(OUT, "canon3.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    have = [r for r in rows if r["hair_pc"] > 0]
    print("models", len(rows), "with hair", len(have))
    for label, key in [("hair cubes", "hair_pc"), ("hair bones", "hair_bones"),
                       ("strand bones", "strand_bones"), ("ornament cubes", "orn")]:
        v = [r[key] for r in have]
        print("%-16s med=%.0f p25=%.0f p75=%.0f p90=%.0f max=%.0f" %
              (label, C.pct(v, .5), C.pct(v, .25), C.pct(v, .75), C.pct(v, .9), max(v)))
    sh = [r["hair_pc"] / r["total_pc"] for r in have]
    print("hair share med=%.1f%% p75=%.1f%% p90=%.1f%% max=%.1f%%" %
          (100 * C.pct(sh, .5), 100 * C.pct(sh, .75), 100 * C.pct(sh, .9), 100 * max(sh)))
    print("\ntop 24 structural hair:")
    for r in sorted(have, key=lambda x: -x["hair_pc"])[:24]:
        print("%-40s hair=%4.0f strands=%3d orn=%5d glow=%5d total=%5.0f share=%3.0f%%" % (
            r["model"][:38], r["hair_pc"], r["strand_bones"], r["orn"], r["glow"],
            r["total_pc"], 100 * r["hair_pc"] / max(r["total_pc"], 1)))
    print("\ntop 8 ornament:")
    for r in sorted(have, key=lambda x: -x["orn"])[:8]:
        print("%-40s orn=%5d hair=%4.0f" % (r["model"][:38], r["orn"], r["hair_pc"]))
