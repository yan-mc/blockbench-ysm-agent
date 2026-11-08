import json, math

W = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
cubes = json.load(open(W + r"\artifacts\v7g_haircap_dump.json"))
for band in [(39.5, 40.5), (38.0, 39.5), (32.0, 38.0)]:
    sel = [c for c in cubes if band[0] <= (c["f"][1] + c["t"][1]) / 2 < band[1]]
    print("== band", band, "count", len(sel))
    for c in sorted(sel, key=lambda c: math.hypot((c["f"][0] + c["t"][0]) / 2, (c["f"][2] + c["t"][2]) / 2)):
        cx = (c["f"][0] + c["t"][0]) / 2
        cy = (c["f"][1] + c["t"][1]) / 2
        cz = (c["f"][2] + c["t"][2]) / 2
        r = math.hypot(cx, cz)
        ang = math.degrees(math.atan2(cz, cx)) % 360
        print("r=%5.2f ang=%6.1f c=(%5.2f,%5.2f,%5.2f) size=(%4.2f,%4.2f,%4.2f) rot=%s" % (r, ang, cx, cy, cz, c["size"][0], c["size"][1], c["size"][2], c["rot"]))
