import json

W = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
d = json.load(open(W + r"\checkpoints\r0025.bbmodel", encoding="utf-8"))
els = {e["uuid"]: e for e in d["elements"]}
cubes = json.load(open(W + r"\artifacts\v7g_haircap_dump.json"))
# show faces of a few top cubes and lower cubes
for c in cubes[:3] + [c for c in cubes if (c["f"][1] + c["t"][1]) / 2 > 42][:2]:
    e = els[c["uuid"]]
    print(e["name"], e["from"], e["to"], "uv_offset", e.get("uv_offset"), "box_uv", e.get("box_uv"))
    print("  faces", json.dumps(e.get("faces"), ensure_ascii=False))
    print("  color", e.get("color"), "texture", e.get("texture"))
    print("  origin", e.get("origin"), "rotation", e.get("rotation"))
