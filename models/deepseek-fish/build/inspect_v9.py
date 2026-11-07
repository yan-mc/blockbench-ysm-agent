"""Inspect the sakiko-melodia pack model JSON: list head-region cubes with origins/sizes."""
import json, sys

path = r"F:\Deepseek_harness\blockbench\models\deepseek-fish\sakiko-melodia\models\main.json"
data = json.load(open(path, encoding="utf-8"))

# bedrock geometry format
print("keys:", list(data.keys()))
geo = data.get("minecraft:geometry", [data])[0]
print("format:", geo.get("format_version"), "desc:", geo.get("description"))
bones = geo["bones"]
print("bones:", len(bones))

want_bones = sys.argv[1].split(",") if len(sys.argv) > 1 else ["Head"]
for b in bones:
    if b["name"] not in want_bones:
        continue
    print(f"\n=== {b['name']} pivot={b.get('pivot')} rot={b.get('rotation')} parent={b.get('parent')}")
    for i, c in enumerate(b.get("cubes", [])):
        o, s, r, p = c.get("origin"), c.get("size"), c.get("rotation"), c.get("pivot")
        print(f"  [{i}] o={o} s={[round(v,2) for v in s]} r={r} p={p} uv={c.get('uv')}")
