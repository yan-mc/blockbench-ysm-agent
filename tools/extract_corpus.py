import json, os, sys, collections, math, pickle, re, glob

from pathlib import Path
_REPO = Path(__file__).resolve().parents[1]
ROOT = str(_REPO / "material" / "refmodels" / "ysm_decoded")
OUT = str(_REPO / "material" / "refmodels" / "_cache.pkl")

def strip_jsonc(s):
    out = []
    i, n = 0, len(s)
    instr = False
    while i < n:
        c = s[i]
        if instr:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(s[i+1]); i += 2; continue
            if c == '"':
                instr = False
            i += 1
            continue
        if c == '"':
            instr = True; out.append(c); i += 1; continue
        if c == "/" and i + 1 < n and s[i+1] == "/":
            while i < n and s[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and s[i+1] == "*":
            i += 2
            while i + 1 < n and not (s[i] == "*" and s[i+1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c); i += 1
    t = "".join(out)
    # trailing commas
    t = re.sub(r",(\s*[}\]])", r"\1", t)
    return t

def load_json_any(p):
    with open(p, "r", encoding="utf-8-sig") as f:
        raw = f.read()
    try:
        return json.loads(raw)
    except Exception:
        try:
            return json.loads(strip_jsonc(raw))
        except Exception:
            return json.loads(strip_jsonc(raw), strict=False)

def find_model_file(d):
    cands = [os.path.join(d, "main.json"), os.path.join(d, "models", "main.json")]
    for p in cands:
        if os.path.exists(p):
            return p
    hits = glob.glob(os.path.join(d, "**", "main.json"), recursive=True)
    return hits[0] if hits else None

def find_png(d):
    # prefer main.png, else the largest png at top level
    p = os.path.join(d, "main.png")
    if os.path.exists(p):
        return p
    hs = [h for h in glob.glob(os.path.join(d, "*.png"))]
    if not hs:
        hs = glob.glob(os.path.join(d, "**", "*.png"), recursive=True)
    if not hs:
        return None
    hs.sort(key=lambda h: os.path.getsize(h), reverse=True)
    return hs[0]

recs = {}
for name in sorted(os.listdir(ROOT)):
    d = os.path.join(ROOT, name)
    if not os.path.isdir(d):
        continue
    p = find_model_file(d)
    if not p:
        recs[name] = {"err": "no_main_json"}; continue
    try:
        j = load_json_any(p)
        geo = j["minecraft:geometry"][0]
    except Exception as e:
        recs[name] = {"err": "parse:%s" % e, "path": p}; continue
    desc = geo.get("description", {})
    extra = desc.get("ysm_extra_info") or {}
    bones = []
    for b in geo["bones"]:
        bones.append({
            "name": b.get("name"),
            "parent": b.get("parent"),
            "pivot": b.get("pivot") or [0, 0, 0],
            "rot": b.get("rotation") or [0, 0, 0],
            "cubes": b.get("cubes") or [],
        })
    png = find_png(d)
    pnginfo = None
    if png:
        try:
            from PIL import Image
            with Image.open(png) as im:
                pnginfo = list(im.size)
        except Exception:
            pnginfo = None
    recs[name] = {
        "path": p, "tw": desc.get("texture_width"), "th": desc.get("texture_height"),
        "png": pnginfo, "png_path": png, "bones": bones,
        "format_version": j.get("format_version"),
        "cname": extra.get("name"),
        "author": extra.get("author"),
        "tip": extra.get("tip"),
        "files": sorted(os.listdir(d)),
    }

with open(OUT, "wb") as f:
    pickle.dump(recs, f)

ok = [k for k, v in recs.items() if "err" not in v]
bad = {k: v.get("err") for k, v in recs.items() if "err" in v}
print("models ok", len(ok), "bad", len(bad))
for k, v in bad.items():
    print("BAD", k, v)
tot = sum(len(b["cubes"]) for k in ok for b in recs[k]["bones"])
print("total cubes", tot)
print("tex", collections.Counter((recs[k]["tw"], recs[k]["th"]) for k in ok).most_common(8))
print("png", collections.Counter(tuple(recs[k]["png"]) if recs[k]["png"] else None for k in ok).most_common(10))
