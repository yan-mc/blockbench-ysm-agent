# -*- coding: utf-8 -*-
import json, os, sys
p = r"F:\Deepseek_harness\blockbench\models\deepseek-fish\pack\ysm.json"
j = json.load(open(p, encoding="utf-8"))
md = j["metadata"]
md["name"] = "丰川祥子 - 旋律的主人"
md["tips"] = "明日方舟 x BanG Dream! 丰川祥子「旋律的主人」\n黑裙 / 蓝衬裙 / 银白边 · 羊角 · 冰蓝长发 · 琥珀瞳"
md["license"] = {"type": "CC BY-NC-SA 4.0"}
md["authors"] = [{
    "name": "dsh-blockbench-agent",
    "role": "建模",
    "avatar": "avatar/null.png",
    "contact": {},
    "comment": "YSM 皮肤：手写几何 + 1024 贴图"
}]
md.pop("link", None)
j["properties"]["height_scale"] = 0.70
j["properties"]["width_scale"] = 0.70
j["properties"]["preview_animation"] = "gui"
json.dump(j, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("ysm.json updated:", j["metadata"]["name"])
