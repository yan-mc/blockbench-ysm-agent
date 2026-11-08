import json
P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\checkpoints\r0048.bbmodel"
d = json.load(open(P, encoding="utf-8"))
print("top keys:", list(d.keys())[:30])
print("meta:", {k: d.get(k) for k in ("meta","name","model_format","box_uv","texture_width","texture_height","resolution")})
els = d.get("elements", [])
print("elements:", len(els), "outliner groups:", len(d.get("outliner", [])))
# find skirt group
def walk(nodes, path=()):
    for n in nodes:
        if isinstance(n, str):
            continue
        nm = n.get("name")
        if nm in ("Skirt","RightSkirt","LeftSkirt","FrontSkirt","BackSkirt"):
            print("GROUP", nm, "keys", list(n.keys()), "children", len(n.get("children", [])))
            for ch in n.get("children", [])[:2]:
                if isinstance(ch, str):
                    el = next((e for e in els if e.get("uuid")==ch), None)
                    if el:
                        print("  child keys:", list(el.keys()))
                        print("  element:", json.dumps({k: el.get(k) for k in ("name","from","to","origin","size","rotation","uv_offset","inflate")}, ensure_ascii=False)[:600])
                        print("  faces:", {f: el.get("faces",{}).get(f) for f in ("north","south","east","west","up","down")})
        walk(n.get("children", []), path+(nm,))
walk(d.get("outliner", []))
print("cube-like elements with 'type':'cube':", sum(1 for e in els if e.get("type")=="cube"))
for e in els[:3]:
    print("sample element keys:", list(e.keys()))
