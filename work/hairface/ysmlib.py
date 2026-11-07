"""Shared loader / geometry helpers for the decoded YSM corpus."""
import json, os, glob, math, re
from collections import Counter, defaultdict

ROOT = r"F:\Deepseek_harness\blockbench\material\refmodels\ysm_decoded"


def model_dirs():
    return sorted([d for d in os.listdir(ROOT) if os.path.isdir(os.path.join(ROOT, d))])


def main_json(name):
    a = os.path.join(ROOT, name, "main.json")
    b = os.path.join(ROOT, name, "models", "main.json")
    if os.path.isfile(a):
        return a
    if os.path.isfile(b):
        return b
    return None


_CACHE = {}


def _strip_json_lenient(txt):
    # remove // line comments and /* */ block comments outside strings
    out = []
    i, n = 0, len(txt)
    instr = False
    esc = False
    while i < n:
        ch = txt[i]
        if instr:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                instr = False
            i += 1
            continue
        if ch == '"':
            instr = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and txt[i + 1] == "/":
            while i < n and txt[i] not in "\r\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and txt[i + 1] == "*":
            i += 2
            while i + 1 < n and not (txt[i] == "*" and txt[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    txt = "".join(out)
    # strip trailing commas
    prev = None
    while prev != txt:
        prev = txt
        txt = re.sub(r",(\s*[}\]])", r"\1", txt)
    return txt


def load(name):
    if name in _CACHE:
        return _CACHE[name]
    p = main_json(name)
    if not p:
        return None
    with open(p, encoding="utf-8", errors="replace") as f:
        txt = f.read()
    try:
        d = json.loads(txt, strict=False)
    except Exception:
        d = json.loads(_strip_json_lenient(txt), strict=False)
    _CACHE[name] = d
    return d


def geometry(doc):
    g = doc.get("minecraft:geometry")
    if not g:
        return None
    return g[0]


def bones(doc):
    g = geometry(doc)
    if not g:
        return []
    return g.get("bones", []) or []


def bone_origin(b):
    return b.get("pivot") or [0, 0, 0]


def parent_of(b):
    return b.get("parent")


def walk_cubes(bones_list):
    """yield (bone, cube) pairs"""
    for b in bones_list:
        for c in (b.get("cubes") or []):
            yield b, c


def cube_aabb(c):
    o = c.get("origin") or [0, 0, 0]
    s = c.get("size") or [0, 0, 0]
    lo = [min(o[i], o[i] + s[i]) for i in range(3)]
    hi = [max(o[i], o[i] + s[i]) for i in range(3)]
    return lo, hi


def rot(c):
    r = c.get("rotation")
    if not r:
        return (0.0, 0.0, 0.0)
    return tuple(float(x) for x in r)


def has_rot(c):
    r = c.get("rotation")
    return bool(r) and any(abs(float(x)) > 1e-9 for x in r)


def thickness_axis(s):
    """return (index, value) of thinnest axis"""
    i = min(range(3), key=lambda k: abs(s[k]))
    return i, s[i]


def sizes(c):
    return [abs(float(x)) for x in (c.get("size") or [0, 0, 0])]


def model_total_cubes(bs):
    return sum(len(b.get("cubes") or []) for b in bs)


# ---------------- naming classifiers ----------------

HAIR_PAT = re.compile(
    r"(hair|bangs?|ahoge|ponytail|twintail|braid|fringe|刘海|发|髪|呆毛|马尾|辫|鬓|twin_?tail|sidehair|backhair|front_?hair|sidelock|sidelocks|himecut)",
    re.I)

FACE_PAT = re.compile(
    r"(face|eye|eyelid|pupil|iris|sclera|brow|lash|mouth|lip|nose|cheek|blush|tear|tongue|fang|tooth|ear\b|ears\b|muzzle|head_?detail)",
    re.I)

HAIR_EXCLUDE = re.compile(r"(hairband|hairpin|hairpin|hair_?clip|ribbon|flower|bell|ornament|accessor)", re.I)


def is_hair_bone(n):
    return bool(HAIR_PAT.search(n or ""))


def is_face_bone(n):
    return bool(FACE_PAT.search(n or ""))


def norm_name(n):
    """Strip trailing digits / side markers for grouping."""
    n = re.sub(r"[\s_\-\.]+$", "", n or "")
    return n.lower()
