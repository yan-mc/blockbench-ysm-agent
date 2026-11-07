"""v9 geometry pass (P1-3): thicken legs, scale horns up 15% around their roots.
Edits models/main.json in place. Run while the project is CLOSED."""
import json, shutil, os

P = r"F:\Deepseek_harness\blockbench\models\deepseek-fish\sakiko-melodia\models\main.json"
shutil.copy(P, P + ".v9bak")
d = json.load(open(P, encoding="utf-8"))
g = d["minecraft:geometry"][0]

LEG_UP = {"LeftLeg", "RightLeg"}
LEG_LO = {"LeftLowerLeg", "RightLowerLeg"}
HORN = {"HornL": (2.3, 43.6, 0.6), "HornR": (-2.3, 43.6, 0.6)}

n_leg = n_horn = 0
for b in g["bones"]:
    nm = b["name"]
    if nm in LEG_UP or nm in LEG_LO:
        dx, dz = (0.34, 0.24) if nm in LEG_UP else (0.26, 0.20)
        for c in b["cubes"]:
            # do not fatten the thin decorative rings beyond a hair
            thin = min(c["size"][0], c["size"][2]) < 0.4
            fx = 0.4 if thin else 1.0
            ox, oy, oz = c["origin"]
            sx, sy, sz = c["size"]
            c["origin"] = [ox - dx * fx / 2, oy, oz - dz * fx / 2]
            c["size"] = [sx + dx * fx, sy, sz + dz * fx]
            n_leg += 1
    elif nm in HORN:
        rx, ry, rz = HORN[nm]
        s = 1.15
        for c in b["cubes"]:
            ox, oy, oz = c["origin"]
            sx, sy, sz = c["size"]
            ctr = [ox + sx / 2, oy + sy / 2, oz + sz / 2]
            nctr = [rx + (ctr[0] - rx) * s, ry + (ctr[1] - ry) * s, rz + (ctr[2] - rz) * s]
            ns = [sx * s, sy * s, sz * s]
            c["origin"] = [nctr[0] - ns[0] / 2, nctr[1] - ns[1] / 2, nctr[2] - ns[2] / 2]
            c["size"] = ns
            n_horn += 1

json.dump(d, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("legs updated:", n_leg, "horns updated:", n_horn)

# report new bounds
xs, ys, zs = [], [], []
for b in g["bones"]:
    for c in b["cubes"]:
        o, s = c["origin"], c["size"]
        xs += [o[0], o[0] + s[0]]
        ys += [o[1], o[1] + s[1]]
        zs += [o[2], o[2] + s[2]]
print("bounds x", round(min(xs), 2), round(max(xs), 2),
      "y", round(min(ys), 2), round(max(ys), 2),
      "z", round(min(zs), 2), round(max(zs), 2))
