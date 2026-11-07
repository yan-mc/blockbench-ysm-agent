"""Head scale detection + normalization factors."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import canon3 as C3
import core as C
import ysmlib as Y
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


def head_info(M):
    """Return dict(head_dims, n_cubes, norm) where norm maps raw units -> MC units."""
    best = None
    for b in M.bones:
        n = (b.get("name") or "").lower()
        if "head" not in n or "hair" in n:
            continue
        cs = b.get("cubes") or []
        if not cs:
            continue
        los, his = [], []
        for c in cs:
            lo, hi = Y.cube_aabb(c)
            los.append(lo); his.append(hi)
        lo = [min(x[i] for x in los) for i in range(3)]
        hi = [max(x[i] for x in his) for i in range(3)]
        dims = [round(hi[i] - lo[i], 3) for i in range(3)]
        vol = dims[0] * dims[1] * dims[2]
        if best is None or vol > best[2]:
            best = (b.get("name"), dims, vol, lo, hi)
    if not best:
        return None
    dims = best[1]
    # reference: typical head is 7x7x7. use max(dims) as the "7" reference
    ref = max(dims)
    return dict(bone=best[0], dims=dims, lo=best[3], hi=best[4],
                norm=(7.0 / ref) if ref > 0 else 1.0,
                y_bottom_face=best[3][1], y_top=best[4][1])


if __name__ == "__main__":
    models = Y.model_dirs()
    rows = []
    for m in models:
        M = C3.Model(m)
        if not M.bones:
            continue
        h = head_info(M)
        desc = (Y.geometry(M.doc) or {}).get("description") or {}
        hs = desc.get("ysm_height_scale")
        row = dict(model=m, head=h, height_scale=hs,
                   tw=desc.get("texture_width"), th=desc.get("texture_height"))
        rows.append(row)
    json.dump(rows, open(os.path.join(OUT, "heads.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    dims = [max(r["head"]["dims"]) for r in rows if r["head"]]
    print("head max-dim: n=%d med=%.2f p10=%.2f p90=%.2f min=%.2f max=%.2f" %
          (len(dims), C.pct(dims, .5), C.pct(dims, .1), C.pct(dims, .9), min(dims), max(dims)))
    print("\n--- models whose head > 10 units (need normalization) ---")
    big = sorted([r for r in rows if r["head"] and max(r["head"]["dims"]) > 10],
                 key=lambda r: -max(r["head"]["dims"]))
    for r in big:
        print("%-40s dims=%-24s hs=%s" % (r["model"][:38], str(r["head"]["dims"]), r["height_scale"]))
    print("\ncount >10:", len(big), " >8:", sum(1 for r in rows if r["head"] and max(r["head"]["dims"]) > 8))
    print("\n--- height_scale distribution ---")
    c = Counter(round(float(r["height_scale"]), 3) for r in rows if r["height_scale"] is not None)
    for k, v in c.most_common(12):
        print("  ", k, v)
    print("\n--- texture sizes ---")
    c = Counter((r["tw"], r["th"]) for r in rows)
    for k, v in c.most_common(12):
        print("  ", k, v)
