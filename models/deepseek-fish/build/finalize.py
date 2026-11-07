# -*- coding: utf-8 -*-
"""Finalise deliverable: build sakiko-melodia pack from export (dir or zip), fix ysm.json, re-zip."""
import json, os, shutil, zipfile

WS = r"F:\Deepseek_harness\blockbench\models\deepseek-fish"
EXPORT = os.path.join(WS, "exports", "sakiko-melodia-v9")
SRC_DIR = os.path.join(EXPORT, "pack")
SRC_ZIP = os.path.join(EXPORT, "pack.zip")
DST = os.path.join(WS, "sakiko-melodia")
DEL = os.path.join(WS, "deliverables", "sakiko-melodia-v8")

if os.path.isdir(DST):
    shutil.rmtree(DST)

if os.path.isdir(SRC_DIR):
    shutil.copytree(SRC_DIR, DST)
else:
    os.makedirs(DST)
    with zipfile.ZipFile(SRC_ZIP) as z:
        z.extractall(DST)

p = os.path.join(DST, "ysm.json")
j = json.load(open(p, encoding="utf-8"))
j["metadata"].update({
    "name": "丰川祥子 - 旋律的主人",
    "tips": "明日方舟 x BanG Dream! 丰川祥子「旋律的主人」\n黑裙 / 蓝衬裙 / 银白边 · 羊角 · 冰蓝长发 · 琥珀瞳 · 自定义 idle",
    "license": {"type": "CC BY-NC-SA 4.0"},
    "authors": [{
        "name": "dsh-blockbench-agent",
        "role": "建模 / 贴图",
        "avatar": "avatar/null.png",
        "contact": {},
        "comment": "手写几何 + 1024 贴图，四层法：标准档 / 剪影 / 形态 / 方块",
    }],
})
j["metadata"].pop("link", None)
j["properties"]["height_scale"] = 0.70
j["properties"]["width_scale"] = 0.70
json.dump(j, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

zpath = os.path.join(DEL, "sakiko-melodia.zip")
if os.path.exists(zpath):
    os.remove(zpath)
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(DST):
        for f in files:
            full = os.path.join(root, f)
            z.write(full, os.path.join("sakiko-melodia", os.path.relpath(full, DST)))

n = sum(len(fs) for _, _, fs in os.walk(DST))
print("pack  ->", DST, n, "files")
print("zip   ->", zpath, os.path.getsize(zpath), "bytes")
