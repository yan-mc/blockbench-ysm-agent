"""Find small floating ruffle chips in skirt bones and build ops to pull them onto the surface."""
import json, math

ROOT = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
main = json.load(open(ROOT + r"\pack\models\main.json", encoding="utf-8"))
bmd = json.load(open(ROOT + r"\checkpoints\r0022.bbmodel", encoding="utf-8"))
els = {e["uuid"]: e for e in bmd["elements"] if e.get("type") == "cube"}
bones = main["minecraft:geometry"][0]["bones"]
by_name = {b["name"]: b for b in bones}

names = ["BackSkirt", "LeftSkirt", "RightSkirt"]
ops = []
count = 0
for bn in names:
    for i, c in enumerate(by_name[bn]["cubes"]):
        o = c["origin"]; s = c["size"]
        if abs(s[2] - 0.24) > 1e-3:
            continue
        th = math.atan2(o[2] + s[2] / 2, o[0] + s[0] / 2)
        R = math.hypot(o[0] + s[0] / 2, o[2] + s[2] / 2)
        # find uuid in bbmodel by size + y + z (x may be mirrored)
        cands = []
        for u, e in els.items():
            es = [e["to"][k] - e["from"][k] for k in range(3)]
            if abs(es[2] - s[2]) < 1e-3 and abs(es[0] - s[0]) < 1e-3 and abs(es[1] - s[1]) < 1e-3 \
               and abs(e["from"][1] - o[1]) < 1e-3 and abs(e["from"][2] - o[2]) < 1e-3:
                cands.append(u)
        if len(cands) != 1:
            print("SKIP", bn, i, "cands", len(cands))
            continue
        u = cands[0]
        newR = R - 0.62
        ncx, ncz = newR * math.cos(th), newR * math.sin(th)
        no = [round(ncx - s[0] / 2, 4), round(o[1], 4), round(ncz - s[2] / 2, 4)]
        npv = [round(ncx, 4), round(o[1] + s[1] / 2, 4), round(ncz, 4)]
        ops.append({"op": "update_cube", "cube_id": u, "origin": no, "pivot": npv,
                    "rotation": [round(v, 4) for v in (c.get("rotation") or [0, 0, 0])],
                    "size": [round(v, 4) for v in s]})
        print(bn, i, "R %.2f->%.2f" % (R, newR), u[:8], "origin", o, "->", no)
        count += 1

json.dump(ops, open(ROOT + r"\artifacts\v5\r6\chip_ops.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ops", count)
