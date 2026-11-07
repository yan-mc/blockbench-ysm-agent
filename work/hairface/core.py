import sys, os, re, json, math
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ysmlib as Y

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)

# ---------- classification ----------
RE_ORNAMENT = re.compile(r"(flower|ribbon|band|pin\b|pin_|clip|bell|lingdang|ornament|accessor|bow\b|bow[0-9]|crown|tiara|hat\b|hat[0-9]|headdress|decor|jewel|gem|bead|tassel|wood|plate|ring|冠|饰|花|铃|帯|带|簪|结)", re.I)
RE_HAIR = re.compile(r"(hair|bangs?|ahoge|ponytail|twintail|braid|fringe|刘海|头发|发|髪|呆毛|马尾|辫|鬓|side_?lock|hime)", re.I)
RE_FACE = re.compile(r"(face|eye|eyelid|pupil|iris|sclera|brow|lash|mouth|lip|nose|cheek|blush|tear|tongue|fang|tooth|muzzle|ear\b|ears\b)", re.I)

FRONT = re.compile(r"(front|bangs?|fringe|forehead|刘海|前)", re.I)
SIDE = re.compile(r"(side|temple|sidelock|鬓)", re.I)
BACK = re.compile(r"(back|rear|behind|后)", re.I)
TOP = re.compile(r"(top|upper|头顶|crown)", re.I)
AHOGE = re.compile(r"(ahoge|呆毛|cowlick|antenna|sprout|hair_?stand)", re.I)
TAIL = re.compile(r"(tail|马尾|ponytail|twintail|twin_?tail)", re.I)
BRAID = re.compile(r"(braid|辫|plait)", re.I)
CURL = re.compile(r"(curl|spiral|drill|卷|螺)", re.I)


def tail_index(n):
    """trailing integer or letter-index used for chain detection"""
    m = re.search(r"(\d+)$", n or "")
    return int(m.group(1)) if m else None


def is_ornament(n):
    return bool(RE_ORNAMENT.search(n or ""))


def hair_kind(n):
    n = n or ""
    if AHOGE.search(n):
        return "ahoge"
    if TAIL.search(n):
        return "tail"
    if BRAID.search(n):
        return "braid"
    if CURL.search(n):
        return "curl"
    if FRONT.search(n):
        return "front"
    if SIDE.search(n):
        return "side"
    if BACK.search(n):
        return "back"
    if TOP.search(n):
        return "top"
    return "generic"


def struct_duplicate_factor(bnames):
    """Detect a full duplicated skeleton: X and X2 both present for most bones."""
    s = set(bnames)
    keys = [n for n in bnames if not re.search(r"\d$", n)]
    if len(keys) < 10:
        return 1
    dup = sum(1 for k in keys if (k + "2") in s)
    return 2 if dup / len(keys) > 0.55 else 1


def collect(model):
    doc = Y.load(model)
    if not doc:
        return None
    bs = Y.bones(doc)
    if not bs:
        return None
    byname = {}
    children = defaultdict(list)
    for b in bs:
        byname.setdefault(b.get("name"), b)
        children[b.get("parent")].append(b)

    hair_roots = []
    orn_roots = []
    for b in bs:
        n = b.get("name") or ""
        if "ClothHair" in n or "clothhair" in n.lower():
            orn_roots.append(b)
        elif RE_HAIR.search(n) and not is_ornament(n):
            hair_roots.append(b)
        elif RE_HAIR.search(n):
            orn_roots.append(b)

    def subtree_cubes(root):
        acc = []
        stack = [root]
        seen = set()
        while stack:
            b = stack.pop()
            if id(b) in seen:
                continue
            seen.add(id(b))
            acc.extend(b.get("cubes") or [])
            for c in children.get(b.get("name"), []):
                stack.append(c)
        return acc

    hair_bones = set()
    for r in hair_roots:
        stack = [r]
        while stack:
            b = stack.pop()
            if id(b) in hair_bones:
                continue
            hair_bones.add(id(b))
            for c in children.get(b.get("name"), []):
                stack.append(c)

    # ornament cubes = those in orn subtree not already hair
    orn_cubes = []
    for r in orn_roots:
        for c in subtree_cubes(r):
            orn_cubes.append((r, c))

    hair_cube_pairs = []
    for b in bs:
        if id(b) in hair_bones:
            for c in b.get("cubes") or []:
                hair_cube_pairs.append((b, c))

    return dict(doc=doc, bones=bs, byname=byname, children=children,
                hair_roots=hair_roots, hair_bones=hair_bones,
                hair_pairs=hair_cube_pairs, orn_pairs=orn_cubes,
                dup=struct_duplicate_factor([b.get('name') for b in bs]))


def cube_stats(pairs):
    rows = []
    for b, c in pairs:
        s = Y.sizes(c)
        t_i = min(range(3), key=lambda k: s[k])
        rows.append(dict(bone=b.get("name"), size=s, thick=s[t_i], thick_axis="xyz"[t_i],
                         long=max(s), long_axis="xyz"[max(range(3), key=lambda k: s[k])],
                         rot=Y.rot(c), has_rot=Y.has_rot(c),
                         origin=c.get("origin") or [0, 0, 0]))
    return rows


def pct(a, q):
    if not a:
        return 0
    a = sorted(a)
    k = (len(a) - 1) * q
    f = math.floor(k); c = math.ceil(k)
    if f == c:
        return a[int(k)]
    return a[f] * (c - k) + a[c] * (k - f)


def summarize(vals):
    if not vals:
        return dict(n=0)
    return dict(n=len(vals), med=round(pct(vals, .5), 3), p25=round(pct(vals, .25), 3),
                p75=round(pct(vals, .75), 3), p90=round(pct(vals, .9), 3),
                mn=round(min(vals), 3), mx=round(max(vals), 3),
                mean=round(sum(vals) / len(vals), 3))
