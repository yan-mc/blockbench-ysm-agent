import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core as C
import ysmlib as Y
from collections import Counter

models = Y.model_dirs()
rows = []
fails = []
for m in models:
    r = C.collect(m)
    if r is None:
        fails.append(m); continue
    tot = Y.model_total_cubes(r["bones"])
    dupe = r["dup"]
    cs = C.cube_stats(r["hair_pairs"])
    n_hair_bones = len(r["hair_roots"])
    # count distinct hair strands = roots
    rows.append(dict(
        model=m, total=tot, dup=dupe,
        hair_bones=n_hair_bones, hair_cubes=len(cs),
        hair_cubes_per=round(len(cs) / dupe, 1),
        total_per=round(tot / dupe, 1),
        orn_bones=len(r["orn_pairs"]), orn_cubes=len(r["orn_pairs"]),
        thick=[round(x["thick"], 3) for x in cs],
        long=[round(x["long"], 3) for x in cs],
        w1=[round(sorted(x["size"])[1], 3) for x in cs],
        rotratio=round(sum(1 for x in cs if x["has_rot"]) / len(cs), 3) if cs else 0,
    ))

json.dump(rows, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "hair_overview.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("models", len(models), "fails", fails)
have = [r for r in rows if r["hair_cubes"] > 0]
print("models with hair:", len(have))
print("dup models:", sum(1 for r in rows if r["dup"] == 2))

tot_per = [r["total_per"] for r in rows]
print("\ntotal cubes per copy: n=%d med=%.0f p75=%.0f max=%.0f" % (len(tot_per), C.pct(tot_per, .5), C.pct(tot_per, .75), max(tot_per)))

hc = [r["hair_cubes_per"] for r in have]
print("hair cubes/copy: n=%d med=%.0f p25=%.0f p75=%.0f p90=%.0f max=%.0f" % (len(hc), C.pct(hc, .5), C.pct(hc, .25), C.pct(hc, .75), C.pct(hc, .9), max(hc)))
hb = [r["hair_bones"] for r in have]
print("hair bone roots: med=%.0f p75=%.0f p90=%.0f max=%.0f" % (C.pct(hb, .5), C.pct(hb, .75), C.pct(hb, .9), max(hb)))
share = [r["hair_cubes_per"] / r["total_per"] for r in have if r["total_per"]]
print("hair share of model: med=%.1f%% p75=%.1f%% max=%.1f%%" % (100 * C.pct(share, .5), 100 * C.pct(share, .75), 100 * C.pct(share, .9)))

print("\n=== top 25 by hair cubes/copy ===")
for r in sorted(have, key=lambda x: -x["hair_cubes_per"])[:25]:
    print("%-42s hair=%4d bones=%3d total=%5d share=%4.0f%% dup=%d orn=%d" % (
        r["model"][:40], r["hair_cubes_per"], r["hair_bones"], r["total_per"],
        100 * r["hair_cubes_per"] / max(r["total_per"], 1), r["dup"], r["orn_cubes"]))

print("\n=== distribution: how many models in each hair-cube bucket ===")
buckets = Counter()
for r in have:
    v = r["hair_cubes_per"]
    b = "<30" if v < 30 else "30-60" if v < 60 else "60-120" if v < 120 else "120-250" if v < 250 else "250-500" if v < 500 else "500+"
    buckets[b] += 1
for k in ["<30", "30-60", "60-120", "120-250", "250-500", "500+"]:
    print("  %-9s %d" % (k, buckets[k]))
