"""Offline orthographic preview of the YSM model from cube data (no blockbench render)."""
import json, math, sys
from PIL import Image, ImageDraw

ROOT = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
PACK = ROOT + r"\pack"
MODEL = sys.argv[1] if len(sys.argv) > 1 else PACK + r"\models\main.json"
TAG = sys.argv[2] if len(sys.argv) > 2 else "current"

doc = json.load(open(MODEL, encoding="utf-8"))
geo = doc["minecraft:geometry"][0]
bones = geo["bones"]
tex = Image.open(PACK + r"\textures\default.png").convert("RGBA")

BONE_REST = {b["name"]: b.get("rotation") or [0, 0, 0] for b in bones}
BONE_PIVOT = {b["name"]: b.get("pivot") or [0, 0, 0] for b in bones}
PARENT = {b["name"]: b.get("parent") for b in bones}


def rot_xyz(p, r):
    x, y, z = p
    rx, ry, rz = [math.radians(a) for a in r]
    y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
    x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
    x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
    return [x, y, z]


def bone_xf(name):
    chain = []
    cur = name
    while cur and cur in BONE_REST:
        chain.append(cur)
        cur = PARENT.get(cur)
    chain.reverse()

    def apply(p):
        q = p
        for bn in chain:
            piv = BONE_PIVOT[bn]
            r = BONE_REST[bn]
            local = [q[0] - piv[0], q[1] - piv[1], q[2] - piv[2]]
            local = rot_xyz(local, [-r[0], -r[1], -r[2]])
            q = [local[0] + piv[0], local[1] + piv[1], local[2] + piv[2]]
        return q
    return apply


def face_color(uvd):
    if not isinstance(uvd, dict):
        return (22, 20, 24, 255)
    pick = None
    for k in ("south", "north", "east", "west"):
        if k in uvd and isinstance(uvd[k], dict):
            pick = uvd[k]
            if k == "south":
                break
    if not pick:
        return (22, 20, 24, 255)
    u = pick.get("uv", [0, 0])
    c = tex.getpixel((max(0, min(511, int(u[0]) + 1)), max(0, min(511, int(u[1]) + 1))))
    return c if c[3] > 30 else (22, 20, 24, 255)


CUBES = []
for b in bones:
    for i, c in enumerate(b.get("cubes") or []):
        CUBES.append((b["name"], i, c))


def hull(pts2):
    pts = sorted(set(pts2))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo = []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    up = []
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def render(angle_deg=180, w=760, h=980, only=None, xlim=(-9.5, 9.5), ylim=(-0.5, 44.5), suffix=""):
    ca, sa = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    img = Image.new("RGBA", (w, h), (28, 28, 32, 255))
    draw = ImageDraw.Draw(img)
    sc = min(w / (xlim[1] - xlim[0]), h / (ylim[1] - ylim[0]))
    ox = w / 2 - (xlim[0] + xlim[1]) / 2 * sc
    oy = h + ylim[0] * sc

    def proj(p):
        x = p[0] * ca - p[2] * sa
        z = p[0] * sa + p[2] * ca
        return (ox + x * sc, oy - p[1] * sc), z

    items = []
    for name, idx, c in CUBES:
        if only and name not in only:
            continue
        xf = bone_xf(name)
        o = c["origin"]; s = c["size"]; rot = c.get("rotation") or [0, 0, 0]
        cen = [o[0] + s[0] / 2, o[1] + s[1] / 2, o[2] + s[2] / 2]
        pts = []
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    lp = [(o[0] + dx * s[0]) - cen[0], (o[1] + dy * s[1]) - cen[1], (o[2] + dz * s[2]) - cen[2]]
                    rp = rot_xyz(lp, rot)
                    pts.append(xf([cen[0] + rp[0], cen[1] + rp[1], cen[2] + rp[2]]))
        pr = [proj(p) for p in pts]
        items.append((sum(q[1] for q in pr) / len(pr), name, idx, c, pr))
    items.sort(key=lambda t: t[0])
    for depth, name, idx, c, pr in items:
        poly = hull([q[0] for q in pr])
        if len(poly) >= 3:
            draw.polygon(poly, fill=face_color(c.get("uv")))
    path = ROOT + rf"\artifacts\v5\r6\proj_{TAG}_{angle_deg}{suffix}.png"
    img.save(path)
    return path


if __name__ == "__main__":
    for ang in (180, 145):
        print(render(ang))
    skirt = {"Skirt", "BackSkirt", "LeftSkirt", "RightSkirt", "FrontSkirt", "Cape", "CapeLow"}
    print(render(180, suffix="_skirt", only=skirt))
    print(render(90, suffix="_skirt", only=skirt))
