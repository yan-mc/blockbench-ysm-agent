"""Canonical per-bone effective class + hair budget. Fixed subtree leakage."""
import sys, os, json, re, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core as C
import ysmlib as Y
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

RE_GLOW = re.compile(r"(ysmglow|glow|emissive)", re.I)
RE_CLOTH_HAIR = re.compile(r"(clothhair|cloth_hair)", re.I)
RE_ORN = re.compile(
    r"(flower|ribbon|band\b|band\d|pin\b|pin_|clip|bell|lingdang|ornament|accessor|bow\b|bow\d|"
    r"crown|tiara|hat\b|hat\d|headdress|decor|jewel|gem|bead|tassel|"
    r"花|饰|铃|簪|冠|帯|带|结|钗|chaizi|fashi|发饰|头饰)", re.I)
RE_HAIR = re.compile(
    r"(hair|bangs?|ahoge|ponytail|twintail|twin_?tail|braid|fringe|"
    r"刘海|头发|发|髪|呆毛|马尾|辫|鬓|side_?lock|hime)", re.I)


def own_class(n):
    if RE_GLOW.search(n):
        return "glow"
    if RE_CLOTH_HAIR.search(n):
        return "ornament"
    if RE_ORN.search(n) and RE_HAIR.search(n):
        return "ornament"
    if RE_HAIR.search(n):
        return "hair"
    if C.RE_FACE.search(n):
        return "face"
    return "other"


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
            chain = [n]
            cur = self.parent.get(n)
            guard = 0
            while cur is not None and guard < 64:
                chain.append(cur)
                cur = self.parent.get(cur)
                guard += 1
            e = "other"
            ownset = {self.own.get(x, "other") for x in chain}
            if "glow" in ownset:
                e = "glow"
            elif "ornament" in ownset:
                e = "ornament"
            elif "hair" in ownset:
                e = "hair"
            elif "face" in ownset:
                e = "face"
            self.eff[n] = e
        self.total = Y.model_total_cubes(self.bones)
        self.dup = C.struct_duplicate_factor([b.get("name") for b in self.bones])

    def bones_of(self, cls):
        return [b for b in self.bones if self.eff.get(b.get("name")) == cls]

    def cubes_of(self, cls):
        return sum(len(b.get("cubes") or []) for b in self.bones
                   if self.eff.get(b.get("name")) == cls)

    def cube_pairs(self, cls):
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
        oc = M.cubes_of("ornament")
        gc = M.cubes_of("glow")
        hb = [b for b in M.bones_of("hair") if (b.get("cubes") or [])]
        rows.append(dict(model=m, total=M.total, dup=M.dup,
                         hair=hc, hair_pc=round(hc / M.dup, 1),
                         orn=oc, orn_pc=round(oc / M.dup, 1), glow=gc,
                         strand_bones=len(hb), hair_bones=len(M.bones_of("hair")),
                         total_pc=round(M.total / M.dup, 1)))
    json.dump(rows, open(os.path.join(OUT, "canon2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    have = [r for r in rows if r["hair_pc"] > 0]
    print("models", len(rows), "with hair", len(have))
    for label, key in [("hair cubes/copy", "hair_pc"), ("hair bone count", "hair_bones"),
                       ("strand bones (cubes>0)", "strand_bones")]:
        v = [r[key] for r in have]
        print("%-24s med=%.0f p25=%.0f p75=%.0f p90=%.0f max=%.0f" %
              (label, C.pct(v, .5), C.pct(v, .25), C.pct(v, .75), C.pct(v, .9), max(v)))
    sh = [r["hair_pc"] / r["total_pc"] for r in have]
    print("hair share med=%.1f%% p75=%.1f%% p90=%.1f%% max=%.1f%%" %
          (100 * C.pct(sh, .5), 100 * C.pct(sh, .75), 100 * C.pct(sh, .9), 100 * max(sh)))
    print("\ntop 22:")
    for r in sorted(have, key=lambda x: -x["hair_pc"])[:22]:
        print("%-40s hair=%4.0f strands=%3d orn=%4d glow=%4d total=%5.0f share=%3.0f%%" % (
            r["model"][:38], r["hair_pc"], r["strand_bones"], r["orn_pc"], r["glow"],
            r["total_pc"], 100 * r["hair_pc"] / max(r["total_pc"], 1)))
