#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BB-Agent 规范生成器（唯一契约源 -> 机器可读 JSON）

用法：python spec/generate_spec.py
产物：
  spec/tool-manifest.json   # dsh 模型可见工具的 JSON Schema 清单
  spec/bridge-methods.json  # dsh <-> Blockbench 的 JSON-RPC 方法目录

说明：
- 这里只维护“结构/枚举/默认值/超时”，行为语义见 docs/03、docs/02。
- 生成后可用 `python -m json.tool` 校验；CI 中应校验生成结果与提交结果一致。
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ---------------------------------------------------------------- common types
COLOR = {"type": "string", "pattern": "^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$",
         "description": "颜色：#RRGGBB 或 #RRGGBBAA（alpha=00 表示透明）"}
VEC3 = {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}
REVISION = {"type": "integer", "minimum": 0,
            "description": "期望的 revision；省略时由 DBA 自动填入最近已知值"}
LIMIT = {"type": "integer", "minimum": 1, "maximum": 100, "default": 40}
REF = {"type": "object", "required": ["kind", "id"],
       "properties": {"kind": {"enum": ["bone", "cube", "texture", "animation", "controller"]},
                      "id": {"type": "string"}},
       "additionalProperties": False}


def obj(props: dict, required: list | None = None, **kw) -> dict:
    out = {"type": "object", "properties": props, "additionalProperties": False}
    if required:
        out["required"] = required
    out.update(kw)
    return out


def schema_ref(name: str) -> dict:
    return {"$ref": f"#/$defs/{name}"}


def common_defs() -> dict:
    return {
        "Color": COLOR,
        "Vec3": VEC3,
        "Revision": {"type": "integer", "minimum": 0},
        "Ref": REF,
        "Warning": obj({
            "code": {"type": "string"},
            "target": {"type": "string"},
            "detail": {"type": "string"},
            "fix_hint": {"type": "string"},
        }, ["code"]),
        "Digest": obj({
            "revision": {"type": "integer"},
            "bones": {"type": "integer"},
            "cubes": {"type": "integer"},
            "textures": {"type": "integer"},
            "animations": {"type": "integer"},
        }),
        "ModelOp": {
            "type": "object",
            "required": ["op"],
            "description": "模型变更操作；op 决定其余字段（见 docs/03 §3.6 与 bridge-methods.json）",
            "properties": {"op": {
                "enum": ["add_bone", "update_bone", "reparent", "add_cube", "update_cube",
                         "set_uv", "auto_uv", "mirror", "delete", "rename", "move_cube", "move_bone"]}},
            "additionalProperties": True,
        },
        "TextureOp": {
            "type": "object",
            "required": ["op"],
            "description": "像素绘制操作；op 决定其余字段（见 docs/03 §3.8）",
            "properties": {"op": {
                "enum": ["pixel", "rect", "line", "shade", "replace", "clear", "outline",
                         "copy_mirror", "import_png", "noise"]}},
            "additionalProperties": True,
        },
        "AnimationOp": {
            "type": "object",
            "required": ["op"],
            "properties": {"op": {
                "enum": ["create_animation", "update_animation", "set_keyframes",
                         "delete_keyframes", "delete_animation", "bind_controller"]}},
            "additionalProperties": True,
        },
    }


# ---------------------------------------------------------------- tools
TOOLS = [
    {
        "name": "bb_session_start",
        "title_zh": "创建/打开 YSM 项目",
        "description": "创建默认 YSM 皮肤骨架或打开已有资源包；返回骨骼顶层、贴图与 revision。后续所有工具都作用于该项目。",
        "mutating": True, "requires_project": False, "concurrency_safe": False,
        "protocol_method": "project.create_ysm", "timeout_ms": 120000,
        "returns": "ProjectSummary",
        "errors": ["PACK_EXISTS", "PACK_INVALID", "PROJECT_NOT_CLOSED", "RESOURCE_LIMIT"],
        "parameters": obj({
            "mode": {"enum": ["new_ysm", "open_pack"], "description": "新建默认骨架 / 打开已有包"},
            "name": {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$"},
            "pack_dir": {"type": "string", "description": "workspace 内相对路径（mode=open_pack 必填）"},
            "gender": {"enum": ["male", "female"], "default": "male"},
            "resolution": {"type": "array", "items": {"type": "integer", "minimum": 16, "maximum": 2048},
                           "minItems": 2, "maxItems": 2, "default": [128, 128]},
            "height_scale": {"type": "number", "minimum": 0.1, "maximum": 2, "default": 0.7},
            "width_scale": {"type": "number", "minimum": 0.1, "maximum": 2, "default": 0.7},
            "template": {"enum": ["default", "minimal"], "default": "default"},
            "overwrite": {"type": "boolean", "default": False},
        }, ["mode"]),
    },
    {
        "name": "bb_session_status",
        "title_zh": "引擎/会话状态",
        "description": "查看状态机、revision、预算与引擎健康；卡住或怀疑降级时调用。",
        "mutating": False, "requires_project": False, "concurrency_safe": True,
        "protocol_method": "session.status", "timeout_ms": 5000,
        "returns": "SessionStatus", "errors": [],
        "parameters": obj({}),
    },
    {
        "name": "bb_project_open",
        "title_zh": "打开资源包",
        "description": "打开 workspace 内已有 YSM 资源包，保留 ysm.json 元数据与文件映射。",
        "mutating": True, "requires_project": False, "concurrency_safe": False,
        "protocol_method": "project.open_pack", "timeout_ms": 120000,
        "returns": "ProjectSummary", "errors": ["PACK_INVALID", "PROJECT_NOT_CLOSED"],
        "parameters": obj({
            "pack_dir": {"type": "string"},
            "save_current": {"type": "boolean", "default": True},
        }, ["pack_dir"]),
    },
    {
        "name": "bb_scene",
        "title_zh": "读取场景摘要",
        "description": "读取压缩后的场景信息；默认 summary。需要细节时按 scope 分页查询，禁止读取原始 JSON。",
        "mutating": False, "requires_project": True, "concurrency_safe": True,
        "protocol_method": "project.get_scene", "timeout_ms": 10000,
        "returns": "SceneView", "errors": ["PROJECT_NOT_OPEN", "INVALID_REFERENCE"],
        "parameters": obj({
            "scope": {"enum": ["summary", "bones", "bone", "cube", "textures", "animations", "uv"],
                      "default": "summary"},
            "id": {"type": "string", "description": "scope=bone/cube 时必填"},
            "cursor": {"type": "string"},
            "limit": LIMIT,
            "include_uv": {"type": "boolean", "default": False},
        }),
    },
    {
        "name": "bb_get_element",
        "title_zh": "读取单个元素",
        "description": "取单个骨骼/方块的完整字段（含 UV）；bb_scene 已有的信息不要重复取。",
        "mutating": False, "requires_project": True, "concurrency_safe": True,
        "protocol_method": "project.get_element", "timeout_ms": 5000,
        "returns": "ElementDetail", "errors": ["PROJECT_NOT_OPEN", "INVALID_REFERENCE"],
        "parameters": obj({
            "id": {"type": "string"},
            "include_uv": {"type": "boolean", "default": False},
            "include_siblings": {"type": "boolean", "default": False},
        }, ["id"]),
    },
    {
        "name": "bb_apply_model_patch",
        "title_zh": "模型原子变更",
        "description": "唯一的模型写入口：骨骼/方块/UV/镜像/重命名/删除，一组 ops 一个事务与一个 revision。",
        "mutating": True, "requires_project": True, "concurrency_safe": False,
        "protocol_method": "model.apply_patch", "timeout_ms": 30000,
        "returns": "PatchReceipt", "errors": ["PROJECT_NOT_OPEN", "REVISION_CONFLICT",
                                              "INVALID_REFERENCE", "INVALID_OPERATION",
                                              "VALIDATION_FAILED", "RESOURCE_LIMIT"],
        "parameters": obj({
            "expected_revision": REVISION,
            "atomic": {"type": "boolean", "default": True},
            "note": {"type": "string", "maxLength": 200},
            "ops": {"type": "array", "minItems": 1, "maxItems": 4096, "items": schema_ref("ModelOp")},
        }, ["ops"]),
    },
    {
        "name": "bb_texture_create",
        "title_zh": "新建贴图",
        "description": "新建一张纹理（YSM 多套皮肤）；默认包通常已有 default/blue。",
        "mutating": True, "requires_project": True, "concurrency_safe": False,
        "protocol_method": "texture.create", "timeout_ms": 15000,
        "returns": "TextureInfo", "errors": ["PROJECT_NOT_OPEN", "RESOURCE_LIMIT"],
        "parameters": obj({
            "name": {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$"},
            "width": {"type": "integer", "minimum": 16, "maximum": 2048, "default": 128},
            "height": {"type": "integer", "minimum": 16, "maximum": 2048, "default": 128},
            "fill": {"type": "string", "description": "默认全透明；可给 #RRGGBB[AA]", "default": "#00000000"},
            "make_active": {"type": "boolean", "default": True},
        }, ["name"]),
    },
    {
        "name": "bb_texture_patch",
        "title_zh": "像素绘制",
        "description": "按像素坐标绘制纹理：单像素/矩形/线/渐变/替换/镜像/导入；一次调用一个 Undo 与 revision。",
        "mutating": True, "requires_project": True, "concurrency_safe": False,
        "protocol_method": "texture.apply_patch", "timeout_ms": 60000,
        "returns": "TexturePatchReceipt",
        "errors": ["PROJECT_NOT_OPEN", "REVISION_CONFLICT", "INVALID_REFERENCE",
                   "RESOURCE_LIMIT", "INVALID_PARAMS"],
        "parameters": obj({
            "expected_revision": REVISION,
            "texture": {"type": "string", "description": "纹理名或 id；省略时为当前激活纹理"},
            "clip": {"type": "boolean", "default": True,
                     "description": "越界像素自动裁剪并计数；false 时越界报错"},
            "return_palette": {"type": "boolean", "default": True},
            "note": {"type": "string", "maxLength": 200},
            "ops": {"type": "array", "minItems": 1, "maxItems": 4096, "items": schema_ref("TextureOp")},
        }, ["ops"]),
    },
    {
        "name": "bb_texture_read",
        "title_zh": "读取贴图局部",
        "description": "读取纹理区域：调色板统计 / ASCII 字符网格 / 小图 base64；默认禁止整图展开。",
        "mutating": False, "requires_project": True, "concurrency_safe": True,
        "protocol_method": "texture.read", "timeout_ms": 10000,
        "returns": "TextureReadResult", "errors": ["PROJECT_NOT_OPEN", "INVALID_REFERENCE", "RESOURCE_LIMIT"],
        "parameters": obj({
            "texture": {"type": "string"},
            "region": {"type": "array", "items": {"type": "integer"}, "minItems": 4, "maxItems": 4},
            "format": {"enum": ["palette", "ascii", "png"], "default": "palette"},
            "max_cells": {"type": "integer", "minimum": 16, "maximum": 4096, "default": 1024},
            "max_colors": {"type": "integer", "minimum": 1, "maximum": 64, "default": 16},
        }),
    },
    {
        "name": "bb_texture_layer",
        "title_zh": "纹理图层",
        "description": "纹理图层 list/create/select/delete/flatten；保存时合成回单张 PNG。",
        "mutating": True, "requires_project": True, "concurrency_safe": False,
        "protocol_method": "texture.layer_*", "timeout_ms": 30000,
        "returns": "TextureReadResult", "errors": ["PROJECT_NOT_OPEN", "INVALID_REFERENCE", "UNSUPPORTED"],
        "parameters": obj({
            "op": {"enum": ["list", "create", "select", "delete", "flatten"]},
            "texture": {"type": "string"},
            "name": {"type": "string"},
            "layer": {"type": "string"},
            "fill": COLOR,
        }, ["op"]),
    },
    {
        "name": "bb_texture_pbr",
        "title_zh": "PBR 贴图",
        "description": "创建/列出现代光影使用的 Iris/YSM 约定 PBR 贴图（_n normal / _s specular）。",
        "mutating": True, "requires_project": True, "concurrency_safe": False,
        "protocol_method": "texture.pbr_*", "timeout_ms": 30000,
        "returns": "TextureReadResult", "errors": ["PROJECT_NOT_OPEN", "INVALID_REFERENCE", "INVALID_OPERATION"],
        "parameters": obj({
            "op": {"enum": ["list", "create"]},
            "texture": {"type": "string"},
            "channel": {"enum": ["normal", "specular"]},
            "fill": COLOR,
        }, ["op"]),
    },
    {
        "name": "bb_animation_patch",
        "title_zh": "动画/关键帧变更",
        "description": "创建/修改 YSM 动画与关键帧；避免覆盖内置语义动画名（idle/walk/run 等）。",
        "mutating": True, "requires_project": True, "concurrency_safe": False,
        "protocol_method": "animation.apply_patch", "timeout_ms": 30000,
        "returns": "PatchReceipt", "errors": ["PROJECT_NOT_OPEN", "REVISION_CONFLICT",
                                              "INVALID_REFERENCE", "INVALID_OPERATION"],
        "parameters": obj({
            "expected_revision": REVISION,
            "note": {"type": "string", "maxLength": 200},
            "ops": {"type": "array", "minItems": 1, "maxItems": 256, "items": schema_ref("AnimationOp")},
        }, ["ops"]),
    },
    {
        "name": "bb_animation_list",
        "title_zh": "动画清单",
        "description": "列出动画名、时长、循环方式、关键帧数量与绑定控制器。",
        "mutating": False, "requires_project": True, "concurrency_safe": True,
        "protocol_method": "animation.list", "timeout_ms": 5000,
        "returns": "AnimationList", "errors": ["PROJECT_NOT_OPEN"],
        "parameters": obj({}),
    },
    {
        "name": "bb_render_views",
        "title_zh": "多机位无头渲染",
        "description": "用固定机位渲染当前模型，默认透明背景、768px、3 个机位；图片以多模态附件返回（默认最多 4 张）。",
        "mutating": False, "requires_project": True, "concurrency_safe": False,
        "protocol_method": "render.views", "timeout_ms": 120000,
        "returns": "RenderResult", "attachments": True,
        "errors": ["PROJECT_NOT_OPEN", "RENDER_FAILED", "TIMEOUT", "RESOURCE_LIMIT",
                   "ENGINE_DEGRADED", "GUI_BUSY"],
        "parameters": obj({
            "expected_revision": REVISION,
            "views": {"type": "array", "maxItems": 8, "default": ["front", "right", "iso_fr"],
                      "items": {"enum": ["front", "back", "left", "right", "top", "bottom",
                                         "iso_fr", "iso_fl", "iso_br", "iso_bl", "closeup"]}},
            "size": {"type": "array", "items": {"type": "integer", "minimum": 32, "maximum": 2048},
                     "minItems": 2, "maxItems": 2, "default": [768, 768]},
            "transparent": {"type": "boolean", "default": True},
            "background": {"type": ["string", "null"], "default": None},
            "antialias": {"enum": ["off", "msaa", "ssaa"], "default": "msaa"},
            "focus": {"type": ["object", "null"], "description": "局部特写 {element, padding?}"},
            "shading": {"type": "boolean", "default": True},
            "show_gizmos": {"type": "boolean", "default": False},
            "pose": {"enum": ["rest", "current"], "default": "rest"},
            "focus": {
                "type": ["object", "null"],
                "properties": {"element": {"type": "string"}, "padding": {"type": "number",
                                                                          "minimum": 0, "maximum": 1,
                                                                          "default": 0.1}},
                "additionalProperties": False,
            },
            "inline": {"type": "boolean", "default": False},
            "attach_images": {"type": "boolean", "default": True},
        }),
    },
    {
        "name": "bb_render_texture",
        "title_zh": "贴图放大预览",
        "description": "把纹理按最近邻放大输出 PNG，用于检查像素细节、色带与接缝。",
        "mutating": False, "requires_project": True, "concurrency_safe": True,
        "protocol_method": "render.texture", "timeout_ms": 30000,
        "returns": "TextureRenderResult", "attachments": True,
        "errors": ["PROJECT_NOT_OPEN", "INVALID_REFERENCE", "RESOURCE_LIMIT"],
        "parameters": obj({
            "texture": {"type": "string"},
            "scale": {"type": "integer", "minimum": 1, "maximum": 16, "default": 8},
            "region": {"type": "array", "items": {"type": "integer"}, "minItems": 4, "maxItems": 4},
            "grid": {"type": "boolean", "default": False},
        }),
    },
    {
        "name": "bb_validate",
        "title_zh": "YSM 规范校验",
        "description": "按 YSM 规范与几何规则校验；导出前必须调用。A 级定位组缺失/改名=error，B 级默认层级偏离=warning。",
        "mutating": False, "requires_project": True, "concurrency_safe": True,
        "protocol_method": "project.validate", "timeout_ms": 30000,
        "returns": "ValidationResult", "errors": ["PROJECT_NOT_OPEN"],
        "implementation_notes": [
            "errors：spec!=2、metadata.name/license.type、model.main、贴图/动画/控制器引用文件缺失、A 级 Locator 缺失、export_empty_groups 被关闭。",
            "warnings：B 级默认层级偏离、主动画名缺失、贴图非 128x128、UV 越界/重叠、arm 缺失、未知字段保留。",
        ],
        "parameters": obj({
            "profile": {"enum": ["ysm", "generic"], "default": "ysm"},
            "strict": {"type": "boolean", "default": True},
            "include": {"type": "array",
                        "items": {"enum": ["bones", "hierarchy", "texture", "uv", "ysm_json", "animation"]}},
        }),
    },
    {
        "name": "bb_checkpoint",
        "title_zh": "创建检查点",
        "description": "把当前项目序列化为 .bbmodel 检查点，便于回滚/对比；大改或导出前调用。",
        "mutating": True, "requires_project": True, "concurrency_safe": False,
        "protocol_method": "project.checkpoint", "timeout_ms": 30000,
        "returns": "CheckpointResult", "errors": ["PROJECT_NOT_OPEN", "CHECKPOINT_FAILED"],
        "parameters": obj({
            "label": {"type": "string", "maxLength": 100},
            "note": {"type": "string", "maxLength": 200},
        }),
    },
    {
        "name": "bb_restore",
        "title_zh": "恢复检查点",
        "description": "恢复到指定 revision 的检查点；会丢弃当前未保存改动，必须 confirm:true。",
        "mutating": True, "requires_project": True, "concurrency_safe": False,
        "protocol_method": "project.restore", "timeout_ms": 60000,
        "returns": "RestoreResult", "errors": ["PROJECT_NOT_OPEN", "INVALID_REFERENCE", "CHECKPOINT_FAILED"],
        "parameters": obj({
            "revision": {"type": "integer", "minimum": 0},
            "confirm": {"type": "boolean", "const": True},
        }, ["revision", "confirm"]),
    },
    {
        "name": "bb_save_project",
        "title_zh": "保存到工作副本",
        "description": "把当前项目写回 pack/（模型、贴图、动画、ysm.json），不生成发布目录。",
        "mutating": True, "requires_project": True, "concurrency_safe": False,
        "protocol_method": "project.save", "timeout_ms": 120000,
        "returns": "SaveResult", "errors": ["PROJECT_NOT_OPEN", "CHECKPOINT_FAILED"],
        "implementation_notes": [
            "必须显式编排：export_empty_groups=true → codec.write(codec.compile(), export_path) → 动画/控制器 exportFile → saveTextures → ysm.json saveNormalization + 固定 writer。",
            "不能依赖 ysm-utils（只写 ysm.json）或 Blockbench 自动保存；exportFile 只写已绑定路径的脏项。",
            "目标模型文件存在但非法 JSON 时 write() 会弹 native messagebox；导出前必须校验目标文件。",
        ],
        "parameters": obj({
            "checkpoint": {"type": "boolean", "default": False},
        }),
    },
    {
        "name": "bb_export_ysm",
        "title_zh": "导出 YSM 资源包",
        "description": "校验并导出可被 YSM 模组加载的资源包目录（可选 zip）；导出前强制 validate。",
        "mutating": True, "requires_project": True, "concurrency_safe": False,
        "protocol_method": "project.export_ysm", "timeout_ms": 300000,
        "returns": "ExportResult", "errors": ["PROJECT_NOT_OPEN", "VALIDATION_FAILED", "CHECKPOINT_FAILED"],
        "implementation_notes": [
            "新目录导出不能用 exportFile（只写已绑定路径脏项）：模型 compile({raw:true})/compile()；动画/控制器 compileFile()；贴图 canvas.toDataURL + writeFile；ysm.json saveNormalization。",
            "多模型包要 project.select() 后逐个编译；lang/avatar/sounds/functions 需宿主/原生 fs 复制。",
            "导出字节级幂等需固定 JSON 缩进/换行/键序；动画保存会重排同文件内键序（语义幂等）。",
        ],
        "parameters": obj({
            "out_dir": {"type": "string", "description": "workspace 相对路径；默认 exports/<ts>/"},
            "include_preview": {"type": "boolean", "default": True},
            "validate": {"type": "boolean", "default": True},
            "zip": {"type": "boolean", "default": False},
        }),
    },
    {
        "name": "bb_batch",
        "title_zh": "原子批处理",
        "description": "把多个 bb_* 调用合并成一次往返；服务端顺序执行，atomic 时任一失败整体回滚。",
        "mutating": True, "requires_project": True, "concurrency_safe": False,
        "protocol_method": "system.batch", "timeout_ms": 300000,
        "returns": "BatchResult", "errors": ["PROJECT_NOT_OPEN", "REVISION_CONFLICT",
                                             "VALIDATION_FAILED", "RESOURCE_LIMIT"],
        "parameters": obj({
            "calls": {"type": "array", "minItems": 1, "maxItems": 16,
                      "items": obj({"tool": {"type": "string", "pattern": "^bb_"},
                                    "args": {"type": "object"}}, ["tool", "args"])},
            "atomic": {"type": "boolean", "default": True},
            "stop_on_error": {"type": "boolean", "default": True},
        }, ["calls"]),
    },
    {
        "name": "bb_show_gui",
        "title_zh": "显示 Blockbench 窗口（默认不暴露）",
        "description": "显示并聚焦后台 Blockbench 窗口，把控制权交给用户；期间 Agent 写操作被冻结。",
        "mutating": True, "requires_project": True, "concurrency_safe": False,
        "protocol_method": "gui.show", "timeout_ms": 10000,
        "returns": "GuiState", "errors": ["PROJECT_NOT_OPEN"],
        "parameters": obj({
            "mode": {"enum": ["inspect", "edit"], "default": "inspect"},
            "message": {"type": "string", "maxLength": 300},
        }),
    },
    {
        "name": "bb_hide_gui",
        "title_zh": "隐藏窗口并同步（默认不暴露）",
        "description": "隐藏 Blockbench 窗口；返回用户改动摘要与新 revision。",
        "mutating": True, "requires_project": True, "concurrency_safe": False,
        "protocol_method": "gui.hide", "timeout_ms": 15000,
        "returns": "GuiResyncResult", "errors": ["PROJECT_NOT_OPEN"],
        "parameters": obj({
            "resync": {"type": "boolean", "default": True},
        }),
    },
    {
        "name": "bb_revisions",
        "title_zh": "检查点列表",
        "description": "列出最近的 .bbmodel 检查点与当前 revision。",
        "mutating": False, "requires_project": True, "concurrency_safe": True,
        "protocol_method": "project.revisions", "timeout_ms": 10000,
        "returns": "CheckpointResult", "errors": ["PROJECT_NOT_OPEN"],
        "parameters": obj({
            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
        }),
    },
    {
        "name": "bb_project_close",
        "title_zh": "关闭项目",
        "description": "关闭当前项目（先保存/检查点自行负责）；force=true 跳过未保存提示。",
        "mutating": True, "requires_project": True, "concurrency_safe": False,
        "protocol_method": "project.close", "timeout_ms": 15000,
        "returns": "CloseResult", "errors": ["PROJECT_NOT_OPEN"],
        "parameters": obj({
            "force": {"type": "boolean", "default": True},
        }),
    },
    {
        "name": "bb_animation_create",
        "title_zh": "创建动画",
        "description": "创建动画并挂到主动画文件；随后用 bb_animation_patch 写关键帧。",
        "mutating": True, "requires_project": True, "concurrency_safe": False,
        "protocol_method": "animation.create", "timeout_ms": 30000,
        "returns": "PatchReceipt", "errors": ["PROJECT_NOT_OPEN", "REVISION_CONFLICT", "INVALID_OPERATION"],
        "parameters": obj({
            "name": {"type": "string", "minLength": 1, "maxLength": 120},
            "length": {"type": "number", "minimum": 0.1, "maximum": 3600, "default": 1},
            "loop": {"enum": ["loop", "once", "hold"], "default": "loop"},
            "file": {"type": "string"},
        }, ["name"]),
    },
    {
        "name": "bb_animation_delete",
        "title_zh": "删除动画",
        "description": "删除一个动画（按名字或 UUID）。",
        "mutating": True, "requires_project": True, "concurrency_safe": False,
        "protocol_method": "animation.delete", "timeout_ms": 30000,
        "returns": "PatchReceipt", "errors": ["PROJECT_NOT_OPEN", "INVALID_REFERENCE"],
        "parameters": obj({
            "animation": {"type": "string"},
        }, ["animation"]),
    },
    {
        "name": "bb_texture_export_png",
        "title_zh": "导出贴图 PNG",
        "description": "把指定纹理导出为 workspace 内 PNG，返回宽高与路径。",
        "mutating": False, "requires_project": True, "concurrency_safe": True,
        "protocol_method": "texture.export_png", "timeout_ms": 30000,
        "returns": "TextureRenderResult", "errors": ["PROJECT_NOT_OPEN", "INVALID_REFERENCE"],
        "parameters": obj({
            "texture": {"type": "string"},
            "out_dir": {"type": "string", "description": "workspace 相对目录，默认 artifacts/textures"},
        }),
    },
    {
        "name": "bb_texture_import_png",
        "title_zh": "导入 PNG 到贴图",
        "description": "把 workspace 内 PNG 或 base64 图片导入到指定纹理位置；支持源区域裁剪。",
        "mutating": True, "requires_project": True, "concurrency_safe": False,
        "protocol_method": "texture.import_png", "timeout_ms": 60000,
        "returns": "TexturePatchReceipt", "errors": ["PROJECT_NOT_OPEN", "INVALID_REFERENCE", "INVALID_PARAMS"],
        "parameters": obj({
            "texture": {"type": "string"},
            "path": {"type": "string"},
            "base64": {"type": "string"},
            "at": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2, "default": [0, 0]},
            "region": {"type": "array", "items": {"type": "integer"}, "minItems": 4, "maxItems": 4},
        }),
    },
    {
        "name": "bb_diagnostics",
        "title_zh": "运行诊断",
        "description": "输出连接/进程/端口/日志尾部/图像链路诊断，用于排障。",
        "mutating": False, "requires_project": False, "concurrency_safe": True,
        "protocol_method": "system.diagnostics", "timeout_ms": 10000,
        "returns": "DiagnosticsResult", "errors": [],
        "parameters": obj({}),
    },
]

TOOL_RETURN_DEFS = {
    "ProjectSummary": obj({
        "project_id": {"type": "string"},
        "revision": {"type": "integer"},
        "pack_dir": {"type": "string"},
        "summary": {"type": "object"},
        "root_bones": {"type": "array", "items": {"type": "object"}},
        "textures": {"type": "array", "items": {"type": "object"}},
        "warnings": {"type": "array", "items": schema_ref("Warning")},
    }),
    "SessionStatus": obj({
        "state": {"type": "string"},
        "project_id": {"type": ["string", "null"]},
        "revision": {"type": "integer"},
        "gui_visible": {"type": "boolean"},
        "render_queue": {"type": "integer"},
        "gpu_ok": {"type": "boolean"},
        "uptime_s": {"type": "number"},
        "budgets": {"type": "object"},
        "last_error": {"type": ["object", "null"]},
    }),
    "SceneView": {"type": "object", "description": "按 scope 变化；见 docs/03 §3.4"},
    "ElementDetail": {"type": "object", "description": "骨骼/方块详情；见 docs/03 §3.5"},
    "PatchReceipt": obj({
        "ok": {"type": "boolean"},
        "revision": {"type": "integer"},
        "changed": {"type": "array", "items": {"type": "object"}},
        "warnings": {"type": "array", "items": schema_ref("Warning")},
        "digest": schema_ref("Digest"),
        "next": {"type": "string"},
    }),
    "TextureInfo": obj({
        "texture": {"type": "string"}, "id": {"type": "string"},
        "size": {"type": "array", "items": {"type": "integer"}}, "revision": {"type": "integer"},
    }),
    "TexturePatchReceipt": obj({
        "ok": {"type": "boolean"}, "revision": {"type": "integer"},
        "texture": {"type": "string"}, "painted_pixels": {"type": "integer"},
        "clipped_pixels": {"type": "integer"},
        "bounds": {"type": ["array", "null"], "items": {"type": "integer"}},
        "palette": {"type": "array", "items": {"type": "object"}},
        "warnings": {"type": "array", "items": schema_ref("Warning")},
    }),
    "TextureReadResult": {"type": "object", "description": "按 format 变化；见 docs/03 §3.9"},
    "AnimationList": obj({
        "animations": {"type": "array", "items": {"type": "object"}},
        "controllers": {"type": "array", "items": {"type": "string"}},
    }),
    "RenderResult": obj({
        "revision": {"type": "integer"}, "render_id": {"type": "string"},
        "images": {"type": "array", "items": obj({
            "view": {"type": "string"}, "path": {"type": "string"},
            "sha256": {"type": "string"}, "bytes": {"type": "integer"},
            "width": {"type": "integer"}, "height": {"type": "integer"},
            "alpha_ratio": {"type": ["number", "null"]},
            "empty": {"type": "boolean"}, "changed": {"type": "boolean"},
            "previous_sha256": {"type": ["string", "null"]},
            "attachment_path": {"type": "string"},
        })},
        "changed_any": {"type": "boolean"},
        "warnings": {"type": "array", "items": {"type": "object"}},
        "cache_hit": {"type": "boolean"}, "elapsed_ms": {"type": "number"},
        "note": {"type": "string"},
    }),
    "TextureRenderResult": obj({
        "revision": {"type": "integer"}, "path": {"type": "string"},
        "sha256": {"type": "string"}, "width": {"type": "integer"}, "height": {"type": "integer"},
    }),
    "ValidationResult": obj({
        "ok": {"type": "boolean"}, "revision": {"type": "integer"},
        "errors": {"type": "array", "items": {"type": "object"}},
        "warnings": {"type": "array", "items": {"type": "object"}},
        "checks": {"type": "array", "items": {"type": "object"}},
        "stats": {"type": "object"},
    }),
    "CheckpointResult": obj({
        "revision": {"type": "integer"}, "checkpoint": {"type": "string"},
        "bytes": {"type": "integer"},
    }),
    "RestoreResult": obj({
        "restored_from": {"type": "integer"}, "revision": {"type": "integer"},
        "summary": {"type": "object"}, "warning": {"type": "string"},
    }),
    "SaveResult": obj({
        "saved": {"type": "boolean"}, "revision": {"type": "integer"},
        "pack_dir": {"type": "string"}, "files": {"type": "array", "items": {"type": "object"}},
    }),
    "ExportResult": obj({
        "revision": {"type": "integer"}, "export_dir": {"type": "string"},
        "zip_path": {"type": ["string", "null"]},
        "zip_files": {"type": ["integer", "null"]},
        "zip_bytes": {"type": ["integer", "null"]},
        "files": {"type": "object"}, "validation": {"type": "object"},
        "manifest": {"type": "string"}, "next": {"type": "string"},
    }),
    "BatchResult": obj({
        "results": {"type": "array", "items": {"type": "object"}},
        "revision": {"type": "integer"}, "rolled_back": {"type": "boolean"},
        "elapsed_ms": {"type": "number"},
    }),
    "GuiState": obj({
        "gui_visible": {"type": "boolean"}, "revision": {"type": "integer"},
        "frozen": {"type": "boolean"},
    }),
    "GuiResyncResult": obj({
        "gui_visible": {"type": "boolean"}, "revision": {"type": "integer"},
        "user_edits": {"type": "array", "items": {"type": "object"}},
    }),
    "CloseResult": obj({
        "closed": {"type": "boolean"}, "revision": {"type": "integer"},
    }),
    "DiagnosticsResult": {"type": "object", "description": "dsh/runtime/remote/logs 诊断视图"},
}


# ---------------------------------------------------------------- bridge methods
def m(name, direction="client_to_server", kind="read", timeout=10000,
      idempotent=True, params=None, result=None, method_type="sync", description=""):
    return {
        "name": name,
        "direction": direction,
        "kind": kind,          # read | write | long | stream | lifecycle
        "idempotent": idempotent,
        "timeout_ms": timeout,
        "type": method_type,   # sync | long | notification
        "params": params or {"type": "object"},
        "result": result or {"type": "object"},
        "description": description,
    }


BRIDGE_METHODS = [
    m("system.hello", timeout=5000, idempotent=False, kind="lifecycle",
      description="握手：鉴权、版本协商、capabilities、返回 session/project 状态"),
    m("system.ping", timeout=3000, description="RTT/健康探测"),
    m("system.batch", kind="write", timeout=300000, idempotent=False,
      description="原子批处理（顺序执行；失败回滚）"),
    m("system.shutdown", kind="lifecycle", timeout=10000, idempotent=False,
      description="写 checkpoint、关窗口、退出进程"),
    m("system.log_tail", timeout=5000, description="取最近 N 行日志（脱敏）"),
    m("session.status", timeout=5000, description="状态机/revision/预算/健康"),
    m("project.create_ysm", kind="write", timeout=120000, idempotent=False),
    m("project.open_pack", kind="write", timeout=120000, idempotent=False),
    m("project.close", kind="write", timeout=30000, idempotent=False),
    m("project.save", kind="long", timeout=120000, idempotent=False),
    m("project.export_ysm", kind="long", timeout=300000, idempotent=False),
    m("project.get_scene", timeout=10000),
    m("project.get_element", timeout=5000),
    m("project.validate", timeout=30000),
    m("project.checkpoint", kind="write", timeout=30000, idempotent=False),
    m("project.restore", kind="write", timeout=60000, idempotent=False),
    m("project.revisions", timeout=5000),
    m("model.apply_patch", kind="write", timeout=30000, idempotent=False),
    m("model.get_tree", timeout=10000),
    m("model.get_cube", timeout=5000),
    m("model.auto_uv", kind="write", timeout=30000, idempotent=False),
    m("texture.create", kind="write", timeout=15000, idempotent=False),
    m("texture.apply_patch", kind="write", timeout=60000, idempotent=False),
    m("texture.read", timeout=10000),
    m("texture.select", timeout=5000),
    m("texture.export_png", timeout=30000),
    m("texture.import_png", kind="write", timeout=60000, idempotent=False),
    m("texture.layer_list", timeout=5000),
    m("texture.layer_create", kind="write", timeout=30000, idempotent=False),
    m("texture.layer_select", timeout=5000),
    m("texture.layer_delete", kind="write", timeout=30000, idempotent=False),
    m("texture.layer_flatten", kind="write", timeout=30000, idempotent=False),
    m("texture.pbr_list", timeout=5000),
    m("texture.pbr_create", kind="write", timeout=30000, idempotent=False),
    m("system.diagnostics", timeout=10000),
    m("animation.create", kind="write", timeout=30000, idempotent=False),
    m("animation.apply_patch", kind="write", timeout=30000, idempotent=False),
    m("animation.list", timeout=5000),
    m("animation.delete", kind="write", timeout=30000, idempotent=False),
    m("animation.bind_controller", kind="write", timeout=30000, idempotent=False),
    m("render.views", kind="long", timeout=120000, idempotent=True),
    m("render.texture", kind="long", timeout=30000, idempotent=True),
    m("render.cancel", timeout=5000),
    m("render.artifacts", timeout=5000),
    m("gui.show", kind="write", timeout=10000, idempotent=False),
    m("gui.hide", kind="write", timeout=15000, idempotent=False),
    m("gui.state", timeout=5000),
    m("gui.capture_page", timeout=15000),
]

BRIDGE_EVENTS = [
    {"name": "event.project_changed", "params": {"revision": "int", "source": "agent|user|external|restore",
                                                 "changed": "array"}},
    {"name": "event.render_progress", "params": {"request_id": "string", "done": "int", "total": "int",
                                                 "view": "string"}},
    {"name": "event.gui_state", "params": {"visible": "bool", "focused": "bool", "revision": "int",
                                           "user_editing": "bool"}},
    {"name": "event.heartbeat", "params": {"revision": "int", "queue_len": "int", "mem_mb": "int",
                                           "gpu_ok": "bool"}},
    {"name": "event.recovered", "params": {"from_revision": "int", "checkpoint": "string",
                                           "reason": "string"}},
    {"name": "event.engine_degraded", "params": {"reason": "string",
                                                 "fallback": "no_gpu|swiftshader|no_webgl"}},
    {"name": "event.log", "params": {"level": "string", "message": "string", "fields": "object?"}},
]

ERROR_CODES = [
    {"jsonrpc": -32700, "code": "PARSE_ERROR", "recoverable": False},
    {"jsonrpc": -32600, "code": "INVALID_REQUEST", "recoverable": False},
    {"jsonrpc": -32601, "code": "METHOD_NOT_FOUND", "recoverable": False},
    {"jsonrpc": -32602, "code": "INVALID_PARAMS", "recoverable": False},
    {"jsonrpc": -32603, "code": "INTERNAL_ERROR", "recoverable": True},
    {"jsonrpc": -32800, "code": "REQUEST_CANCELLED", "recoverable": True},
    {"jsonrpc": -32001, "code": "UNAUTHORIZED", "recoverable": False},
    {"jsonrpc": -32002, "code": "PROTOCOL_MISMATCH", "recoverable": False},
    {"jsonrpc": -32003, "code": "SESSION_BUSY", "recoverable": True},
    {"jsonrpc": -32010, "code": "PROJECT_NOT_OPEN", "recoverable": True},
    {"jsonrpc": -32011, "code": "REVISION_CONFLICT", "recoverable": True},
    {"jsonrpc": -32012, "code": "INVALID_REFERENCE", "recoverable": True},
    {"jsonrpc": -32013, "code": "VALIDATION_FAILED", "recoverable": True},
    {"jsonrpc": -32014, "code": "RENDER_FAILED", "recoverable": True},
    {"jsonrpc": -32015, "code": "TIMEOUT", "recoverable": True},
    {"jsonrpc": -32016, "code": "GUI_BUSY", "recoverable": True},
    {"jsonrpc": -32017, "code": "USER_TAKEOVER", "recoverable": True},
    {"jsonrpc": -32018, "code": "RESOURCE_LIMIT", "recoverable": True},
    {"jsonrpc": -32019, "code": "UNSUPPORTED", "recoverable": False},
    {"jsonrpc": -32020, "code": "CHECKPOINT_FAILED", "recoverable": True},
    {"jsonrpc": -32021, "code": "ENGINE_DEGRADED", "recoverable": True},
    {"jsonrpc": -32022, "code": "INVALID_OPERATION", "recoverable": True},
]


def build_tool_manifest() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "manifest_version": "1.0.0",
        "protocol": "bb-agent/1",
        "generated_by": "spec/generate_spec.py",
        "notes": [
            "parameters 是 wire 级 JSON Schema；dsh 侧可用 defineTool 的 DSL 或原始 JSON Schema。",
            "description 为模型可见文本，修改会改变 KV 前缀，需版本化。",
            "returns 使用 $defs 中的命名 schema；attachments=true 表示结果含多模态图片块。",
            "expected_revision 可省略；DBA 自动填入最近已知 revision。",
        ],
        "$defs": {**common_defs(), **TOOL_RETURN_DEFS},
        "tools": TOOLS,
    }


def build_bridge_manifest() -> dict:
    return {
        "manifest_version": "1.0.0",
        "protocol": "bb-agent/1",
        "transport": {
            "default": "ws",
            "url": "ws://127.0.0.1:<port>/bb-agent/v1",
            "subprotocol": "bb-agent.v1",
            "fallback": "http-sse",
            "http": {"rpc": "POST /rpc", "events": "GET /events", "health": "GET /health"},
            "framing": "utf-8 json text (binary frames reserved; not used in v1)",
            "max_message_bytes": 8388608,
            "max_batch": 64,
            "max_patch_ops": 4096,
            "max_inflight": 8,
        },
        "auth": {
            "scheme": "first-message-token",
            "token_bits": 256,
            "compare": "constant-time",
            "bind": "127.0.0.1",
        },
        "revision": {
            "semantics": "project-level monotonic integer; any successful mutation +1; restore appends",
            "mutation_requires_expected_revision_unless_forced": True,
            "idempotency_key": "_meta.client_request_id (LRU 5min)",
        },
        "methods": BRIDGE_METHODS,
        "events": BRIDGE_EVENTS,
        "errors": ERROR_CODES,
    }


def main() -> None:
    tool_manifest = build_tool_manifest()
    bridge_manifest = build_bridge_manifest()
    (ROOT / "tool-manifest.json").write_text(
        json.dumps(tool_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "bridge-methods.json").write_text(
        json.dumps(bridge_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"tools={len(TOOLS)} bridge_methods={len(BRIDGE_METHODS)} events={len(BRIDGE_EVENTS)}")
    print("wrote spec/tool-manifest.json, spec/bridge-methods.json")


if __name__ == "__main__":
    main()
