"""Offline orthographic preview of the YSM model from cube data (no blockbench render)."""
import json, math, sys
from PIL import Image, ImageDraw
from collections import Counter

ROOT = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
PACK = ROOT + r"\pack"
doc = json.load(open(PACK + r"\models\main.json", encoding="utf-8"))
geo = doc["minecraft:geometry"][0]
bones = geo["bones"]
tex = Image.open(PACK + r"\textures\default.png").convert("RGBA")

BONE_REST = {b["name"]: b.get("rotation") or [0, 0, 0] for b in bones}
BONE_PIVOT = {b["name"]: b.get("pivot") or [0, 0, 0] for b in bones}
PARENT = {b["name"]: b.get("parent") for b in bones}


def rot_xyz(p, r):
    x, y, z = p
    rx, ry, rz = [math.radians(a) for a in r]
    # Blockbench/Bedrock order XYZ (R = Rx*Ry*Rz) applied ... use standard XYZ intrinsic
    # x
    y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
    x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
    x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
    return [x, y, z]


def bone_world(name):
    """returns function mapping model-space point -> world point for that bone's rest transform"""
    chain = []
    cur = name
    while cur and cur in BONE_REST:
        chain.append(cur)
        cur = PARENT.get(cur)
    chain.reverse()
    # Each bone rotates its subtree around pivot, in blockbench hierarchy order.
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
        return (20, 20, 24, 255)
    pick = None
    for k in ("south", "north", "east", "west", "up", "down"):
        if k in uvd and isinstance(uvd[k], dict):
            pick = uvd[k]
            if k == "south":
                break
    if not pick:
        return (20, 20, 24, 255)
    x, y = int(pick.get("uv", [0, 0])[0]), int(pick.get("uv", [0, 0])[1])
    c = tex.getpixel((max(0, min(511, x + 1)), max(0, min(511, y + 1))))
    return c if c[3] > 30 else (24, 22, 28, 255)


CUBES = []
for b in bones:
    for i, c in enumerate(b.get("cubes") or []):
        CUBES.append((b["name"], i, c))
print("cubes", len(CUBES))


def cube_points(c, xf):
    o = c["origin"]; s = c["size"]
    rot = c.get("rotation") or [0, 0, 0]
    cx = [o[0] + s[0] / 2, o[1] + s[1] / 2, o[2] + s[2] / 2]
    pts = []
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                lp = [(o[0] + dx * s[0]) - cx[0], (o[1] + dy * s[1]) - cx[1], (o[2] + dz * s[2]) - cx[2]]
                rp = rot_xyz(lp, rot)
                wp = [cx[0] + rp[0], cx[1] + rp[1], cx[2] + rp[2]]
                pts.append(xf(wp))
    return pts


def hull(pts2):
    pts = sorted(set(pts2))
    if len(pts) <= 2:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def render(angle_deg=180, w=900, h=1100, only=None, xlim=(-11, 11), ylim=(-1, 44), suffix=""):
    """angle 180 = looking at the back (+z side); 0 = front; 90 = left side"""
    ca, sa = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    img = Image.new("RGBA", (w, h), (30, 30, 34, 255))
    draw = ImageDraw.Draw(img)
    sx = w / (xlim[1] - xlim[0])
    sy = h / (ylim[1] - ylim[0])
    sc = min(sx, sy)
    ox = w / 2 - (xlim[0] + xlim[1]) / 2 * sc
    oy = h - (ylim[0]) * sc

    def proj(p):
        # rotate around Y by angle; camera looks along rotated -z
        x = p[0] * ca - p[2] * sa
        z = p[0] * sa + p[2] * ca
        y = p[1]
        return (ox + x * sc, oy - y * sc), z

    items = []
    for name, idx, c in CUBES:
        if only and name not in only:
            continue
        xf = bone_world(name)
        pts = cube_points(c, xf)
        pr = [proj(p) for p in pts]
        depth = sum(q[1] for q in pr) / len(pr)
        items.append((depth, name, idx, c, pr))
    items.sort(key=lambda t: t[0])
    for depth, name, idx, c, pr in items:
        poly = hull([q[0] for q in pr])
        if len(poly) < 3:
            continue
        col = face_color(c.get("uv"))
        draw.polygon(poly, fill=col)
    img.save(ROOT + rf"\artifacts\v5\r6\proj_{angle_deg}{suffix}.png")
    return img


if __name__ == "__main__":
    for ang in (180, 150, 90):
        render(ang)
    # with only skirt tree + hair
    render(180, suffix="_skirt", only={"Skirt", "BackSkirt", "LeftSkirt", "RightSkirt", "FrontSkirt", "Cape", "CapeLow"})
    render(90, suffix="_skirt", only={"Skirt", "BackSkirt", "LeftSkirt", "RightSkirt", "FrontSkirt", "Cape", "CapeLow"})
    print("ok")
