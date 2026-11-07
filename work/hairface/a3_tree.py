import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core as C
import ysmlib as Y

M = sys.argv[1:] or ['hi3_elysia__ae12017978c2']
for m in M:
    r = C.collect(m)
    bs = r["bones"]
    tot = Y.model_total_cubes(bs)
    print("=" * 78)
    print(m, " bones", len(bs), " cubes", tot, " dup", r["dup"])
    # print hair subtree as tree
    def show(b, depth=0):
        n = len(b.get("cubes") or [])
        print("%s%-38s %4d cubes  parent=%s pivot=%s" % (
            "  " * depth, b.get("name"), n, b.get("parent"),
            [round(float(x), 2) for x in (b.get("pivot") or [0, 0, 0])]))
        for c in r["children"].get(b.get("name"), []):
            show(c, depth + 1)
    print("--- hair subtree ---")
    printed = set()

    def show(b, depth=0):
        n = len(b.get("cubes") or [])
        key = b.get("name")
        print("%s%-38s %4d cubes  parent=%s pivot=%s" % (
            "  " * depth, key, n, b.get("parent"),
            [round(float(x), 2) for x in (b.get("pivot") or [0, 0, 0])]))
        if key in printed:
            return
        printed.add(key)
        for c in r["children"].get(key, []):
            show(c, depth + 1)

    for b in r["hair_roots"]:
        if b.get("parent") is None or not any(
                (bb.get("name") == b.get("parent")) for bb in r["hair_roots"]):
            show(b)
    print("  [unreached hair bones]")
    for b in r["hair_roots"]:
        if b.get("name") not in printed:
            show(b)
    print("--- ornament subtree (ClothHair etc) ---")
    seen = set()
    for b, c in r["orn_pairs"]:
        if b.get("name") not in seen:
            seen.add(b.get("name"))
            print("   %-38s %4d cubes" % (b.get("name"), len(b.get("cubes") or [])))
    print()
