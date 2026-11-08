import json
P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\checkpoints\r0048.bbmodel"
d = json.load(open(P, encoding="utf-8"))
els = d["elements"]
groups = d.get("groups", [])
print("groups:", len(groups), [g.get("name") for g in groups][:10], "...")
for g in groups:
    if g.get("name") in ("Skirt","RightSkirt","FrontSkirt","BackSkirt","LeftSkirt"):
        print("GROUP", g.get("name"), "keys", list(g.keys()), "children", len(g.get("children", [])), "pivot", g.get("origin"))
import collections
cnt = collections.Counter(e.get("name") for e in els)
print("element name counts (skirt):", {k:v for k,v in cnt.items() if "Skirt" in str(k) or "skirt" in str(k)})
for e in els:
    if e.get("name") == "Skirt":
        print("\nELEMENT keys:", list(e.keys()))
        print("name", e["name"], "from", e["from"], "to", e["to"], "origin", e.get("origin"), "uv_offset", e.get("uv_offset"), "box_uv", e.get("box_uv"), "autouv", e.get("autouv"))
        for f, v in e["faces"].items():
            print("  face", f, v)
        break
# distribution of uv sizes per face
sizes = collections.Counter()
for e in els:
    for f, v in e.get("faces", {}).items():
        uv = v.get("uv")
        if uv:
            sizes[(round(uv[2]-uv[0],2), round(uv[3]-uv[1],2), v.get("texture"))] += 1
print("\nface uv size top:", sizes.most_common(10))
