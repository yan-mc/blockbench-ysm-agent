# 03 · AI 专属 Tool API 声明清单

> 这些 Tool 由 dsh Host 插件（DBA）通过 `ctx.tools.register()` 注册，直接出现在模型的工具列表中。
> 底层经 `02-通信协议规范.md` 的 JSON-RPC 转发给 BABP；模型**永远不直接读写** bbmodel/bedrock JSON。
> 完整 JSON Schema 见 `spec/tool-manifest.json`；本文件是设计说明与行为契约。

---

## 1. 设计原则

1. **语义化**：Tool 对应"艺术家的动作"（加一段肢体、把袖子涂成深蓝、转 45° 看看），不暴露 Blockbench 类名与文件格式字段。
2. **有界**：任何返回默认 ≤ 1.5k tokens；列表必须分页；像素读取禁止全图展开；图片默认只回传 3 张 512px 缩略图。
3. **可寻址**：骨骼用**名字**（YSM 名字本来就有语义）、方块/纹理/动画用**短 id + 名字**双寻址；所有 id 在 `bb_scene` 中可见。
4. **事务化**：一次调用 = 一次 Undo = 一个 revision；批量用 ops 数组，禁止"改一半"。
5. **自描述**：写失败时返回结构化错误（哪个字段、期望什么、下一步调什么），而不是一句 `error`。
6. **防滥用**：坐标/尺寸/颜色/像素数都有范围校验；越界默认裁剪并报告，而不是静默写坏。
7. **不打断闭环**：GUI 相关 Tool 默认不暴露给模型；人机协作用 `/show` 命令。
8. **可缓存**：只读 Tool 结果按 revision 缓存；渲染结果按 `(revision, view, size, options)` 缓存。

---

## 2. 命名、单位与通用参数

### 2.1 坐标与颜色

| 概念 | 约定 |
|---|---|
| 模型空间 | Y 轴向上；1 单位 = 1/16 格；YSM 默认主模型原点在脚底中心，几何高约 43.3 单位（`height_scale=0.7` 后约 30.3 单位 ≈ 1.89 格）。校验器按"包围盒 × height_scale"判断，不要硬编码 32 |
| 旋转 | 欧拉角（度），XYZ 顺序，绕元素 pivot |
| 纹理空间 | 左上角 `(0,0)`，x 右 y 下，与 PNG 一致；坐标必须为整数 |
| 颜色 | `#RRGGBB` 或 `#RRGGBBAA`；不接受颜色名；alpha=0 表示透明 |
| 像素矩形 | `[x1,y1,x2,y2]`，闭区间；默认 `clip=true` 时越界自动裁剪 |
| 版本 | `revision` 由 DBA 自动回填；模型通常不需要传，冲突时用返回的提示 |

### 2.2 双寻址

- **骨骼**：优先用 `bone:"LeftArm"`（唯一名字）；也接受 `bone_id:"b_left_arm"`。
- **方块**：`cube_id:"cu_7f3a"`（稳定短 id，创建时分配）；可附带 `name`。
- **纹理**：`texture:"default"`（YSM 贴图名）或 `texture_id:"tex_default"`。
- **动画**：`animation:"idle"`。

短 id 生成规则：`<前缀>_<uuid 前 4-8 位>`；`b_`=bone、`cu_`=cube、`tex_`=texture、`anim_`=animation、`ctrl_`=controller。重新打开项目时 id 稳定（由 uuid 派生）。

### 2.3 工具总览

| # | Tool | 作用 | 变更 | 返回预算 |
|---|---|---|---|---|
| 1 | `bb_session_start` | 新建 YSM 项目 / 打开已有包 | ✓ | ~600 tok |
| 2 | `bb_session_status` | 引擎状态、revision、预算、健康 | — | ~250 tok |
| 3 | `bb_project_open` | 打开另一个 YSM 包 | ✓ | ~600 tok |
| 4 | `bb_scene` | 场景摘要/树/元素/纹理/动画（分页） | — | 300–1200 tok |
| 5 | `bb_get_element` | 单个骨骼/方块详情（含 UV） | — | 150–500 tok |
| 6 | `bb_apply_model_patch` | 骨骼/方块/UV/镜像等统一变更 | ✓ | 200–500 tok |
| 7 | `bb_texture_create` | 新建贴图 | ✓ | ~150 tok |
| 8 | `bb_texture_patch` | 像素/矩形/线/替换/镜像绘制 | ✓ | 200–500 tok |
| 9 | `bb_texture_read` | 读调色板/局部位图/ASCII | — | 150–600 tok |
| 10 | `bb_animation_patch` | 动画与关键帧 | ✓ | 200–500 tok |
| 11 | `bb_animation_list` | 动画清单 | — | ~300 tok |
| 12 | `bb_render_views` | 多机位无头渲染 → 图片 | — | 文本 100 + 图片 |
| 13 | `bb_render_texture` | 贴图放大预览 → 图片 | — | 文本 80 + 1 图片 |
| 14 | `bb_validate` | YSM 规范/几何/UV 校验 | — | 300–1200 tok |
| 15 | `bb_checkpoint` | 创建检查点 | ✓ | ~120 tok |
| 16 | `bb_restore` | 恢复检查点 | ✓ | ~200 tok |
| 17 | `bb_save_project` | 保存到 pack/ | ✓ | ~200 tok |
| 18 | `bb_export_ysm` | 导出发布包 | ✓ | ~400 tok |
| 19 | `bb_batch` | 原子批处理（减少往返） | ✓ | 视内容 |
| 20 | `bb_show_gui` * | 显示 Blockbench 窗口（默认不暴露） | ✓ | ~120 tok |
| 21 | `bb_hide_gui` * | 隐藏窗口并同步用户改动 | ✓ | ~300 tok |

> `*` 默认关闭：人机协同由 dsh 原生命令 `/show`、`/hide` 完成，避免模型在闭环中突然弹出 GUI。

---

## 3. 工具详解

### 3.1 `bb_session_start`

**描述（给模型看的版本）**：创建或打开一个 YSM 皮肤项目，返回骨骼树顶层、贴图列表与当前 revision。后续所有工具都作用于这个项目。

**参数**

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `mode` | `"new_ysm" \| "open_pack"` | ✓ | — | 新建默认骨架 / 打开已有 YSM 包 |
| `name` | string | 新建必填 | — | 项目名（同时用作 pack 目录名，`^[A-Za-z0-9_-]{1,64}$`） |
| `pack_dir` | string | 打开必填 | — | workspace 内相对路径，如 `packs/steve_armor` |
| `gender` | `"male" \| "female"` | — | `"male"` | 选择默认骨架（影响比例与部分骨骼） |
| `resolution` | `[number, number]` | — | `[128,128]` | 贴图尺寸，YSM 推荐 128×128 |
| `height_scale` | number | — | `0.7` | 写入 ysm.json `properties.height_scale`，范围 0.1–2 |
| `width_scale` | number | — | `0.7` | 同上 |
| `template` | `"default" \| "minimal"` | — | `"default"` | default=完整默认包；minimal=仅 main+贴图，便于从零 |
| `overwrite` | boolean | — | false | 同名已存在时是否覆盖（危险） |

**返回**

```json
{
  "project_id": "steve_armor-8f3a2c1d",
  "revision": 1,
  "pack_dir": "packs/steve_armor",
  "summary": { "bones": 18, "cubes": 57, "textures": 2, "animations": 10, "controllers": 1, "bounds": [[-8,0,-4],[8,32,4]] },
  "root_bones": [
    { "bone": "Root", "id": "b_root", "parent": null, "cubes": 0 },
    { "bone": "MAllBody", "id": "b_mallbody", "parent": "Root", "cubes": 0 }
  ],
  "textures": [ { "texture": "default", "id": "tex_default", "size": [128,128] }, { "texture": "blue", "id": "tex_blue", "size": [128,128] } ],
  "next": "read bb_scene(scope:'bones') to see the full skeleton, or start with bb_apply_model_patch"
}
```

**错误**：`PACK_EXISTS`（用 overwrite）、`PACK_INVALID`（ysm.json 缺失/字段错）、`PROJECT_NOT_CLOSED`。

---

### 3.2 `bb_session_status`

**描述**：查看引擎是否就绪、当前状态机、revision、本轮预算与健康信息。卡住或怀疑降级时调用。

**参数**：无。

**返回**

```json
{
  "state": "editing",
  "project_id": "steve_armor-8f3a2c1d",
  "revision": 46,
  "gui_visible": false,
  "render_queue": 0,
  "gpu_ok": true,
  "uptime_s": 812,
  "budgets": { "edits_used": 12, "edits_max": 60, "renders_used": 5, "renders_max": 40, "wall_time_s": 210, "wall_time_max": 1800 },
  "last_error": null
}
```

---

### 3.3 `bb_project_open`

**描述**：打开 workspace 内已有的 YSM 资源包（保留 ysm.json 元数据与文件映射）。

**参数**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `pack_dir` | string | ✓ | workspace 相对路径 |
| `save_current` | boolean | — | 默认 true；先保存当前项目 |

**返回**：同 `bb_session_start` 的结构 + `warnings`（缺失贴图/动画文件会列出）。

---

### 3.4 `bb_scene`

**描述**：读取场景的压缩视图。默认 summary；需要细节时按 scope 分页取。

**参数**

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `scope` | `"summary" \| "bones" \| "bone" \| "cube" \| "textures" \| "animations" \| "uv"` | `"summary"` | 视图 |
| `id` | string | — | scope=bone/cube 时必填 |
| `cursor` | string | — | 分页游标（返回里有 `next_cursor`） |
| `limit` | integer | 40 | 1–100 |
| `include_uv` | boolean | false | cube/bone 视图是否带 UV 矩形 |

**summary 返回**

```json
{
  "revision": 46,
  "project": { "name": "steve_armor", "format": "bedrock", "box_uv": false },
  "counts": { "bones": 18, "cubes": 57, "textures": 2, "animations": 10 },
  "bounds": [[-8.2,0,-4.1],[8.2,32.4,4.1]],
  "textures": [
    { "texture": "default", "id": "tex_default", "size": [128,128], "opaque_ratio": 0.42, "top_colors": ["#3b6ea5","#2b4f75","#c8a27a"] }
  ],
  "animations": ["idle","walk","run","attack"],
  "warnings": []
}
```

**bones 视图**（有界树）

```json
{
  "revision": 46,
  "nodes": [
    { "bone": "Root", "id": "b_root", "parent": null, "pivot": [0,0,0], "cubes": 0, "children": ["MAllBody"] },
    { "bone": "AllBody", "id": "b_allbody", "parent": "MAllBody", "pivot": [0,20.65,0], "cubes": 0, "children": ["UpBody","LeftLeg","RightLeg"] },
    { "bone": "LeftArm", "id": "b_leftarm", "parent": "UpperBody", "pivot": [5,22,0], "cubes": 3, "children": [] }
  ],
  "total": 18, "next_cursor": null
}
```

**bone 视图**：`{ bone, id, parent, pivot, rotation, cubes:[{cube_id, name, size, origin}], children }`

**cube 视图**（`include_uv:true` 时）

```json
{
  "cube_id": "cu_7f3a", "name": "sleeve", "bone": "LeftArm",
  "origin": [5,18,-2], "size": [4,8,4], "rotation": [0,0,0], "pivot": [7,22,0], "inflate": 0,
  "texture": "default",
  "uv": { "mode": "faces",
    "faces": { "north": [40,16], "east": [36,16], "south": [48,16], "west": [44,16], "up": [40,12], "down": [44,16] } }
}
```

**textures 视图**：每张纹理的 size / opaque_ratio / top_colors / 被哪些 cube 引用（最多 20 条）。

**uv 视图**：列出 UV 越界、重叠、拉伸（按 cube face），可用 `limit` 分页；每个问题带 `fix_hint`。

---

### 3.5 `bb_get_element`

**描述**：取单个骨骼或方块的完整字段。`bb_scene` 已包含的信息不要重复取。

**参数**：`{ "id": "cu_7f3a", "include_uv": true, "include_siblings": false }`
**返回**：cube/bone 详情（同上），附 `texture_usage`（该 cube 各面落在纹理上的像素区域）。
**错误**：`INVALID_REFERENCE`（附相近名字建议）。

---

### 3.6 `bb_apply_model_patch`

**描述**：对模型进行一组原子变更（骨骼、方块、UV、镜像、重命名）。这是唯一的模型写入口。

**参数**

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `expected_revision` | integer | — | 自动 | 通常省略；恢复/并发时显式传 |
| `atomic` | boolean | — | true | 任一 op 失败则整体回滚 |
| `ops` | array | ✓ | — | 1–256 个操作（服务端上限 4096） |
| `note` | string | — | — | 人类可读说明，写入 Undo 标签与日志 |

**ops 目录**

| op | 字段 | 说明 |
|---|---|---|
| `add_bone` | `parent?`, `name`, `pivot`, `rotation?`, `mirror?` | 新建骨骼；`mirror:"x"` 时同时创建镜像骨骼（名字自动 `_R`/`_L` 或按 YSM 规则） |
| `update_bone` | `bone`, `pivot?`, `rotation?`, `scale?`, `name?` | 修改骨骼属性 |
| `reparent` | `bone`, `parent` | 改父级（保持世界变换或局部变换，默认局部） |
| `add_cube` | `bone`, `name?`, `origin`, `size`, `rotation?`, `pivot?`, `uv?`, `texture?`, `inflate?` | 加方块；`uv` 省略时自动按 Box UV 放置并避让已占用区域 |
| `update_cube` | `cube_id`, `origin?`, `size?`, `rotation?`, `pivot?`, `inflate?`, `texture?` | 改方块 |
| `set_uv` | `ids[]`, `mode:"box"\|"faces"\|"offset"`, `uv?`/`faces?`/`offset?` | 精确设置 UV |
| `auto_uv` | `ids[]`, `texture?`, `padding?`, `strategy:"pack"\|"grid"` | 自动展开（Box UV） |
| `mirror` | `ids[]`, `axis:"x"`, `mode:"copy"\|"flip"` | 镜像方块/骨骼 |
| `delete` | `refs:[{kind,id}]` | 删除骨骼/方块（骨骼级联） |
| `rename` | `id`, `name` | 改名（骨骼名受 YSM 规范约束） |

**add_cube 的 uv 语法**

```json
// 自动（推荐）：由适配器按 Box UV 规则排版并避让
{ "op": "add_cube", "bone": "LeftArm", "origin": [5,18,-2], "size": [4,8,4] }

// 手动 Box UV：指定左上角
{ "op": "add_cube", "bone": "LeftArm", "origin": [5,18,-2], "size": [4,8,4],
  "uv": { "mode": "box", "uv": [40, 16], "mirror": false } }

// 逐面 UV（像素级控制）
{ "op": "add_cube", "bone": "LeftArm", "origin": [5,18,-2], "size": [4,8,4],
  "uv": { "mode": "faces",
          "faces": { "north": [40,16], "east": [36,16], "south": [48,16],
                     "west": [44,16], "up": [40,12], "down": [44,16] } } }
```

**返回**

```json
{
  "revision": 47,
  "changed": [
    { "kind": "cube", "id": "cu_9b21", "op": "add", "bone": "LeftArm" },
    { "kind": "cube", "id": "cu_7f3a", "op": "update" }
  ],
  "warnings": [
    { "code": "UV_OVERLAP", "target": "cu_9b21", "detail": "up face overlaps cu_7f3a.up by 12 px", "fix_hint": "use auto_uv or move to [52,12]" }
  ],
  "digest": { "revision": 47, "bones": 18, "cubes": 58 }
}
```

**错误**：`INVALID_REFERENCE`、`INVALID_OPERATION`（如给 cube 加子骨骼、删除必需骨骼）、`VALIDATION_FAILED`（保留骨骼名被改）、`REVISION_CONFLICT`。

---

### 3.7 `bb_texture_create`

**描述**：新建一张纹理（YSM 多套皮肤/表情用）。YSM 默认包通常已有 `default` 与 `blue`，不需要重复创建。

**参数**：`{ "name": "armor_red", "width": 128, "height": 128, "fill": "#00000000", "make_active": true }`
**返回**：`{ "texture": "armor_red", "id": "tex_armor_red", "revision": 48, "size": [128,128] }`

---

### 3.8 `bb_texture_patch`（核心）

**描述**：在指定纹理上按像素坐标绘制。支持单像素、矩形、线、渐变、替换、镜像、导入。**一次调用只产生一个 Undo 与一个 revision。**

**参数**

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `expected_revision` | integer | — | 自动 | 并发保护 |
| `texture` | string | — | 当前激活纹理 | 纹理名或 id |
| `clip` | boolean | — | true | 越界像素裁剪并计数；false 时越界报错 |
| `ops` | array | ✓ | — | 1–4096 个绘制操作 |
| `return_palette` | boolean | — | true | 返回操作后纹理调色板 Top 8 |
| `note` | string | — | — | Undo 标签 |

**ops 目录**

| op | 字段 | 说明 |
|---|---|---|
| `pixel` | `x,y,color` | 单像素（"一笔一笔"的最小单位） |
| `rect` | `x1,y1,x2,y2,color,filled?` | 矩形（默认填充；`filled:false` 画边框） |
| `line` | `x1,y1,x2,y2,color,width?` | Bresenham 直线；width 1–8 |
| `shade` | `x1,y1,x2,y2,from,to,direction:"v"\|"h"\|"diag"` | 双色渐变（抖动可选 `dither:"none"\|"checker"\|"bayer2"`） |
| `replace` | `from,to,tolerance?` | 全局/区域颜色替换；`region?` 限定范围 |
| `clear` | `region?` | 清空为透明（不传 region 即整图） |
| `outline` | `region,color,thickness?` | 给非透明区域描边（像素画常用） |
| `copy_mirror` | `src:[x1,y1,x2,y2],axis:"x"\|"y"` | 镜像复制（做对称袖子/腿） |
| `import_png` | `path` 或 `base64`, `at?`, `region?` | 从 workspace 导入参考图/旧贴图 |
| `noise` | `region,colors[],density` | 像素噪点（做布料纹理） |

**示例：给左上臂画 4×8 的深蓝底 + 高光**

```json
{
  "texture": "default",
  "ops": [
    { "op": "rect",  "x1": 40, "y1": 16, "x2": 43, "y2": 23, "color": "#3b6ea5" },
    { "op": "line",  "x1": 40, "y1": 16, "x2": 43, "y2": 16, "color": "#5a8fc4" },
    { "op": "shade", "x1": 40, "y1": 17, "x2": 43, "y2": 23,
      "from": "#3b6ea5", "to": "#2b4f75", "direction": "v", "dither": "checker" }
  ]
}
```

**返回**

```json
{
  "revision": 49,
  "texture": "default",
  "painted_pixels": 118,
  "clipped_pixels": 0,
  "bounds": [40,16,43,23],
  "palette": [ {"color":"#3b6ea5","count":62}, {"color":"#2b4f75","count":33}, {"color":"#5a8fc4","count":4} ],
  "warnings": []
}
```

**约束**：单次 ops 总像素面积建议 ≤ 4096（超过会被拆帧，速度下降）；`pixel` 逐点调用适合微调（≤64 点/次），大面积请用 rect/shade。

---

### 3.9 `bb_texture_read`

**描述**：读取纹理的局部信息，用于检查颜色/接缝/透明区。默认只返回调色板统计。

**参数**

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `texture` | string | 当前 | 纹理名/id |
| `region` | `[x1,y1,x2,y2]` | 整图 | 读取区域 |
| `format` | `"palette" \| "ascii" \| "png"` | `"palette"` | palette=颜色统计；ascii=字符网格；png=base64 小图 |
| `max_cells` | integer | 1024 | ascii 最大格数；超出报 `RESOURCE_LIMIT` |
| `max_colors` | integer | 16 | palette 最大颜色数 |

**返回（palette）**：`{ "size":[128,128], "region":[...], "palette":[{"color":"#..","count":..}], "transparent_pixels":n }`
**返回（ascii）**：`{ "legend":{"a":"#3b6ea5",...}, "rows":["aaaa....","....bbbb"] }`（每字符一个调色板索引，空格=透明）
**返回（png）**：`{ "png_base64":"...", "width":.., "height":.. }`（≤ 32×32 区域时建议用，否则用 `bb_render_texture`）

---

### 3.10 `bb_animation_patch`

**描述**：创建/修改 YSM 动画与关键帧。YSM 的 idle/walk/run 等动画名是约定的，新增动画应避免覆盖内置语义名。

**参数**：`{ "expected_revision"?, "ops": [...] }`

**ops 目录**

| op | 字段 | 说明 |
|---|---|---|
| `create_animation` | `name`, `length`, `loop:"loop"\|"once"\|"hold"`, `fps?` | 新建动画 |
| `update_animation` | `animation`, `name?`, `length?`, `loop?` | 修改属性 |
| `set_keyframes` | `animation`, `bone`, `channel:"rotation"\|"position"\|"scale"`, `keys:[{time,value:[x,y,z],easing?}]` | 覆盖式设置该通道关键帧 |
| `delete_keyframes` | `animation`, `bone`, `channel`, `times?` | 删除指定时间或全部 |
| `delete_animation` | `animation` | 删除动画 |
| `bind_controller` | `animation[]`, `controller:"main"` | 绑定到控制器文件（YSM 用） |

**示例**

```json
{ "ops": [
  { "op": "create_animation", "name": "wave", "length": 1.5, "loop": "once" },
  { "op": "set_keyframes", "animation": "wave", "bone": "RightArm", "channel": "rotation",
    "keys": [ {"time":0,"value":[0,0,0]}, {"time":0.4,"value":[-120,0,0]}, {"time":1.0,"value":[-100,0,0]}, {"time":1.5,"value":[0,0,0]} ] }
] }
```

**返回**：`{ "revision": 50, "changed":[{"animation":"wave","op":"create"}], "warnings":[] }`

---

### 3.11 `bb_animation_list`

**描述**：列出动画名、时长、循环方式、关键帧数量与绑定控制器。
**返回**：`{ "animations":[{"animation":"idle","length":2.0,"loop":"loop","keyframes":48},{"animation":"wave",...}], "controllers":["main"] }`

---

### 3.12 `bb_render_views`（核心）

**描述**：用固定机位无头渲染当前模型，返回 PNG 图片给模型自检。默认透明背景、768px、3 个机位。

**参数**

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `views` | array | `["front","right","iso_fr"]` | 见下方枚举；最多 8 个 |
| `size` | `[w,h]` | `[768,768]` | 32–2048；超出报 `RESOURCE_LIMIT` |
| `transparent` | boolean | true | 透明背景 |
| `background` | color | null | 非透明背景色（与 transparent 互斥） |
| `antialias` | `"off"\|"msaa"\|"ssaa"` | `"msaa"` | ssaa 更慢但边缘更干净 |
| `shading` | boolean | true | 关闭后为纯色（看 UV/颜色更准） |
| `show_gizmos` | boolean | false | 一般保持 false |
| `pose` | `"rest"\|"current"` | `"rest"` | rest=绑定姿势；current=当前动画帧 |
| `focus` | object | null | `{ "element":"LeftArm", "padding":0.1 }` 局部特写 |
| `inline` | boolean | false | true 时把 ≤256KB 的图内联 base64（默认落盘 + 附件） |
| `attach_images` | boolean | true | 是否把图作为多模态附件回传（最多 4 张） |

**views 枚举**（相机语义，映射 Blockbench 预设）

| view | 含义 | 对应预设/位置 |
|---|---|---|
| `front` | 模型正面 | preset `north`（相机在 -Z） |
| `back` | 背面 | preset `south`（+Z） |
| `right` | 角色右侧 | preset `east`（+X） |
| `left` | 角色左侧 | preset `west`（-X） |
| `top` / `bottom` | 顶/底 | preset `top` / `bottom` |
| `iso_fr` | 前右 45° | 自定义 `[+0.707d, +0.35d, -0.707d]` |
| `iso_fl` | 前左 45° | `[-0.707d, +0.35d, -0.707d]` |
| `iso_br` | 后右 45° | `[+0.707d, +0.35d, +0.707d]` |
| `iso_bl` | 后左 45° | `[-0.707d, +0.35d, +0.707d]` |
| `closeup` | 配合 `focus` 使用 | 自动取景 |

**返回（文本部分）**

```json
{
  "revision": 49,
  "render_id": "r49-3a",
  "views": ["front","right","iso_fr"],
  "images": [
    { "view":"front", "path":"artifacts/renders/r0049/front_768.png", "sha256":"9f2c…", "bytes":184233 },
    { "view":"right", "path":"artifacts/renders/r0049/right_768.png", "sha256":"…" },
    { "view":"iso_fr", "path":"artifacts/renders/r0049/iso_fr_768.png", "sha256":"…" }
  ],
  "cache_hit": false,
  "elapsed_ms": 1180,
  "note": "front 与 right 已作为图片附件返回；iso_fr 已落盘，可再次请求或让用户查看"
}
```

**图片附件**：DBA 会把每张图降采样到最长边 512（PNG 无损缩放用最近邻+轻微锐化，避免像素画变糊）、校验图片大小、`ctx.attachments.saveImage()` 持久化，再通过 `output.render()` 的 `ImageBlock` 回传给模型。默认最多 4 张，避免 vision token 爆炸。

**错误**：`RENDER_FAILED`（附 reason：`no_webgl`/`context_lost`/`gpu_oom`）、`RESOURCE_LIMIT`、`TIMEOUT`。

---

### 3.13 `bb_render_texture`

**描述**：把纹理按最近邻放大输出 PNG，检查像素画细节（色带、错误像素、接缝）。

**参数**：`{ "texture":"default", "scale":8, "region":[32,16,47,31], "grid":true }`（scale 1–16，region 可选，grid 叠加网格线）
**返回**：文本元数据 + 1 张图片附件（≤ 512px）。

---

### 3.14 `bb_validate`

**描述**：按 YSM 规范与几何规则做校验。导出前必须调用；返回结构化问题与修复建议。

**参数**：`{ "profile":"ysm"|"generic", "strict": true, "include":["bones","hierarchy","texture","uv","ysm_json","animation"] }`

**返回**

```json
{
  "ok": false,
  "revision": 49,
  "errors": [
    { "code":"YSM_REQUIRED_BONE_MISSING", "severity":"error", "path":"bones.LeftArm",
      "message":"缺少 YSM 运行时必需骨骼 LeftArm", "fix_hint":"bb_apply_model_patch add_bone 或从默认骨架恢复" },
    { "code":"UV_OUT_OF_BOUNDS", "severity":"warning", "path":"cube.cu_9b21.east",
      "message":"east 面 UV 超出 128×128", "fix_hint":"set_uv east=[36,16]" }
  ],
  "warnings": [ ... ],
  "checks": [
    { "id":"required_bones", "status":"fail" },
    { "id":"hierarchy", "status":"pass" },
    { "id":"texture_size", "status":"pass" },
    { "id":"uv_bounds", "status":"warn" },
    { "id":"ysm_json_paths", "status":"pass" },
    { "id":"animations", "status":"pass" }
  ],
  "stats": { "bones":18, "cubes":58, "uv_overlaps":1, "nonmanifold":0 }
}
```

**YSM 校验项**（严格模式，按"错误 vs 警告"分级）：

- **errors（会导致进游戏缺件/加载失败）**：A 级定位组缺失或改名（`Head`、`AllHead`、`ViewLocator`、`Left/RightHandLocator`、`Left/RightWaistLocator`、`BladeLocator`、`SheathLocator`、`ElytraLocator`、`Left/RightShoulderLocator`、`PistolLocator`、`RifleLocator`、`BackpackLocator`、`ysmGlow*`）；`spec != 2`；`metadata.name`/`license.type` 缺失；`files.player.model.main` 缺失或文件不存在；贴图文件不存在；动画/控制器引用文件不存在；`export_empty_groups` 被关闭。
- **warnings（动画/外观偏离默认，但包仍可加载）**：B 级默认层级偏离（`Root→MAllBody→AllBody→UpBody→UpperBody` 等）；主动画名缺失；贴图不是 128×128；UV 越界/重叠；`height_scale/width_scale` 超出合理范围；`arm.json` 缺失。
- **info**：`default_texture` 缺省回退行为、PBR 贴图未关联、未知字段（保留不删）。

---

### 3.15 `bb_checkpoint`

**描述**：把当前项目序列化为 `.bbmodel` 检查点，便于回滚/对比。导出与大规模修改前自动调用。

**参数**：`{ "label":"before_armor", "note":"..." }` → `{ "revision":49, "checkpoint":"checkpoints/r0049.bbmodel", "bytes":2341234 }`

### 3.16 `bb_restore`

**描述**：恢复到某个 revision 的检查点。会丢弃当前未保存改动，属于破坏性操作，必须 `confirm:true`。

**参数**：`{ "revision":42, "confirm":true }`
**返回**：`{ "restored_from":49, "revision":50, "summary":{...}, "warning":"用户 GUI 改动已丢弃" }`

### 3.17 `bb_save_project`

**描述**：把当前项目写回 `pack/`（模型 JSON、贴图 PNG、动画、ysm.json）。不生成发布目录。

> **实现必须显式编排**（YSM-Utils 只写 ysm.json，Blockbench 自动保存只写"已绑定路径"的脏项）：
> 1. `Settings.set('export_empty_groups', true)`；
> 2. 当前项目 `codec = Codecs[Project.export_codec] ?? Codecs.bedrock`；`codec.write(codec.compile(), Project.export_path)`；若 `export_path` 未绑定，按 ysm.json 的 `files.player.model.main` 显式设置；
> 3. 动画/控制器按文件分组 `exportFile(path)`（只写 `saved=false`）；
> 4. `saveTextures()` 或逐张 `texture.save()`；
> 5. ysm.json 复制 → `saveNormalization()` → 固定 writer 写盘。
>
> 目标模型文件存在但非法 JSON 时 `write()` 会弹覆盖确认，必须提前校验目标文件。

**参数**：`{ "checkpoint": true }` → `{ "saved":true, "revision":49, "files":[{"path":"models/main.json","bytes":..},{"path":"textures/default.png","bytes":..}], "pack_dir":"packs/steve_armor" }`

### 3.18 `bb_export_ysm`

**描述**：校验并导出可被 YSM 模组加载的资源包目录（可选 zip）。

> 导出到新目录时**不能用 `exportFile`**（只写已绑定路径的脏项）：模型用 `compile({raw:true})`/`compile()`，动画/控制器用 `compileFile(animations)`，贴图用 `canvas.toDataURL('image/png')` + `Blockbench.writeFile`，ysm.json 用 `saveNormalization()`。多模型包要 `project.select()` 后逐个编译。`lang/avatar/sounds/functions` 需要用原生 fs 或宿主复制。

**参数**

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `out_dir` | string | `exports/<ts>` | workspace 相对路径 |
| `include_preview` | boolean | true | 生成 preview.png/thumbnail.png |
| `validate` | boolean | true | 导出前强制校验，errors>0 则中止 |
| `zip` | boolean | false | 同时生成 .zip |

**返回**

```json
{
  "revision": 49,
  "export_dir": "exports/20261018-2015/steve_armor",
  "zip_path": null,
  "files": { "models": 2, "animations": 10, "textures": 2, "controllers": 1, "total": 21 },
  "validation": { "ok": true, "errors": 0, "warnings": 2 },
  "manifest": "exports/20261018-2015/steve_armor/export-manifest.json",
  "next": "用户可把该目录放入 YSM 模型包目录，或运行 /show 查看"
}
```

### 3.19 `bb_batch`

**描述**：把多个工具调用合并成一次往返（服务端原子执行）。适合"改 3 个方块 + 画 2 块贴图 + 渲染"这种连续动作。

**参数**：`{ "calls":[{"tool":"bb_apply_model_patch","args":{...}},{"tool":"bb_texture_patch","args":{...}}], "atomic":true, "stop_on_error":true }`
**限制**：≤16 个调用；不可嵌套；渲染只能作为最后一个；`atomic:true` 时任一失败整体回滚。
**返回**：`{ "results":[...每项的紧凑结果...], "revision":51, "rolled_back":false, "elapsed_ms":840 }`

### 3.20 `bb_show_gui` / `bb_hide_gui`（默认不暴露）

- `bb_show_gui({ mode:"inspect"|"edit", message? })`：显示窗口并把控制权交给用户；DBA 拦截变更工具。
- `bb_hide_gui()`：隐藏窗口，返回 `{ "gui_visible":false, "revision":50, "user_edits":[{...diff摘要...}] }`。
- 默认由 dsh 命令 `/show`、`/hide` 调用；模型侧仅在配置 `exposeGuiTools:true` 时可见。

---

## 4. 返回模板与上下文预算

### 4.1 统一回执结构

所有变更类 Tool 返回同一"回执"骨架，便于模型快速解析：

```json
{
  "ok": true,
  "revision": 49,
  "changed": [ { "kind":"cube", "id":"cu_9b21", "op":"add" } ],
  "warnings": [ { "code":"UV_OVERLAP", "target":"cu_9b21", "fix_hint":"..." } ],
  "digest": { "bones":18, "cubes":58, "textures":2, "animations":10 },
  "next": "可选：建议的下一步（最多 3 条）"
}
```

### 4.2 预算表

| 返回 | 典型 tokens | 上限策略 |
|---|---|---|
| `bb_scene summary` | 350–700 | 固定字段，无长列表 |
| bones 树一页（40 节点） | 600–1100 | 分页，节点只含 id/name/parent/pivot/cubes |
| cube 详情 | 150–350 | UV 只在 `include_uv:true` 时返回 |
| 模型 patch 回执 | 180–450 | changed 最多 20 条，warnings 最多 8 条 |
| 纹理 patch 回执 | 180–400 | palette 最多 8 色 |
| render 结果 | 100 + 图片 | 文本只列 path/sha/bytes；图片 ≤4 张 512px |
| validate | 300–1200 | errors 最多 20 条，其余汇总为计数 |
| export | ~300 | 只给计数与 manifest 路径 |

> 视觉 token 估算：512×512 图约 500–1200 vision tokens/张（随模型 tokenizer 变化）。默认一轮 1–3 张；需要更多角度时按需追加，不要每轮 8 张。

### 4.3 dsh Host 侧落地约束

1. **注册方式**：用 `defineTool()`（`@deepseek-ai/dsh-tools`）+ `ctx.tools.register()`；`parameters` 可用 DSL（`{type, required, description}`）或原始 JSON Schema。`inject = ['tools','commands','attachments']`（attachments 可写成可选 `ctx.get('attachments')`）。
2. **工具集必须稳定**：注册/注销/`restrict` 变化会让模型请求的 KV 前缀失效。所有 `bb_*` 工具**一次注册到位**，可选工具（`bb_show_gui`、`bb_render_texture`）用 Config 开关在启动时决定是否注册，不要运行时增删。
3. **自管超时**：`timeoutMs` 是声明式的，本 profile 没有强制 timeout-policy；`execute()` 内必须 `AbortSignal.timeout(ms)` / `Promise.race`，并把 `exec.signal` 透传到 Bridge（取消时发 `$/cancel`）。
4. **图片返回**：`execute()` 里 `ctx.attachments.saveImage({data, mediaType:'image/png', name})` 拿 `ImageAttachmentRef`，`output.render()` 返回 `[{type:'text',...},{type:'image',attachment}]`。若 attachments 未挂载或模型路由不支持图片，降级为"返回绝对路径 + 提示模型调用 `read_image`"。
5. **图片成本**：图片从进入上下文起**每次请求都会重复计费**，直到 compaction。默认只在 `bb_render_views` / `bb_render_texture` 中附图，且：最长边 ≤512、单张 ≤200KB、每次 ≤4 张；其余工具（patch/validate/scene）只返回文本与路径。需要看全分辨率时，模型再调 `read_image`。
6. **错误风格**：`execute` 抛出带稳定 code 的错误对象（或返回 `{ok:false, code, hint}` 让 `render` 输出）；不要抛原始堆栈。模型看到的是 `render()` 的 ContentBlock，因此错误也应在 `render` 中格式化为可操作提示。
7. **并发声明**：只读工具 `isConcurrencySafe: () => true`；写/渲染/导出默认 exclusive。DBA 内部另有 project mutex + revision 校验，不依赖 dsh 调度器。
8. **命令**：`/show`、`/hide`、`/bb-status` 用 `ctx.commands.register({name, description, input?, handler})`。命令 handler 不产生模型消息，可直接调用 Bridge；`/show` 返回文本并让用户看到窗口。
9. **清理**：`apply(ctx)` 中用 `ctx.effect(() => () => { kill BBAR 进程; close WS server; stop timers })`；不要依赖进程退出时自然清理。
10. **安装**：bundle 的 `peerDependencies` 对齐当前 dsh 版本（本机 `0.2.1-rc.2`）；本地 `link:` 安装时第三方依赖（如 `ws`）需在插件 checkout 内 `pnpm install`，或使用零依赖的 HTTP+SSE 绑定。

---

## 5. 状态机门控（DBA 侧强制）

| 状态 | 允许的 Tool |
|---|---|
| `booting` / `recovering` | 仅 `bb_session_status` |
| `idle`（无项目） | `bb_session_start`、`bb_project_open`、`bb_session_status` |
| `editing` | 全部只读 + 建模/贴图/动画 + 渲染 + 校验 + checkpoint |
| `rendering` | 只读 + `bb_render_views` 排队；变更工具等待（或拒绝 `SESSION_BUSY`） |
| `reviewing` | 只读 + `bb_validate` + `bb_checkpoint` |
| `gui_visible` | 只读；变更工具 `GUI_BUSY` |
| `exporting` | 只读 |
| `degraded` | 只读 + `bb_session_status`（提示重试/重启） |
| `done` | 只读 + 重新开始 |

---

## 6. 给模型的系统提示词片段（可直接嵌入 Skill）

```text
你是 YSM 皮肤美术师，通过 bb_* 工具在无头 Blockbench 中工作。
规则：
1. 修改前先 bb_scene(scope="summary")；不要假设骨骼名或贴图尺寸。
2. 所有模型修改走 bb_apply_model_patch，所有贴图绘制走 bb_texture_patch；禁止尝试读取/写入原始 JSON。
3. 贴图是像素画：坐标必须是整数；颜色用 #RRGGBB；大面积用 rect/shade，微调用 pixel；对称部位用 copy_mirror。
4. 每完成一批修改（≤3 次写操作）必须 bb_render_views(["front","right","iso_fr"]) 自检；看图后先列缺陷再改。
5. 导出前必须 bb_validate(profile="ysm") 且 errors=0；导出用 bb_export_ysm。
6. 不要连续两轮做同样的修改；如果同一缺陷出现两次，换策略或 bb_checkpoint 后回滚。
7. 不确定 YSM 规范时，先 bb_scene 看默认包的骨骼/贴图结构，照抄结构而不是猜。
```

---

## 7. 错误 → 下一步动作映射

| 错误码 | 模型应做的动作 |
|---|---|
| `REVISION_CONFLICT` | 调 `bb_scene(scope="summary")` 获取新 revision，重试当前 patch |
| `INVALID_REFERENCE` | 用返回的 `suggestions` 纠正 id/name；仍失败则 `bb_scene(scope="bones")` |
| `INVALID_OPERATION` | 按 `fix_hint` 修改 op；不要原样重试 |
| `VALIDATION_FAILED` | 读 `errors[]`，逐条修复；不要忽略 warning 直接导出 |
| `UV_OUT_OF_BOUNDS`/`UV_OVERLAP` | 用 `set_uv`/`auto_uv` 修正；必要时换更大贴图 |
| `RENDER_FAILED` | 降级：`antialias:"off"`、`size:[512,512]`；仍失败则报告引擎降级，停止视觉判断 |
| `GUI_BUSY` / `USER_TAKEOVER` | 停止写操作，告知用户输入 `/hide`；恢复后重新 `bb_scene` |
| `RESOURCE_LIMIT` | 拆分 ops/降低分辨率/分页读取 |
| `TIMEOUT` | 减少一次渲染的机位数量，或缩小尺寸 |
| `ENGINE_DEGRADED` | 不再基于图片做精确判断；改跑 `bb_validate` 的确定性校验 |

---

## 8. 工具 Schema 评审清单

- [ ] 每个 Tool 的 `description` 说明"做什么 + 什么时候用 + 禁止什么"，不写实现细节。
- [ ] 每个参数有类型、范围、默认值、必填性；枚举值都列在 schema 里。
- [ ] 每个变更 Tool 都有 `expected_revision`（可省略）与 `note`。
- [ ] 每个返回都有 `ok/revision/warnings/digest/next` 中的适用字段。
- [ ] 列表类参数都有 `limit` 与 `cursor`；默认值保证单次 ≤ 1.5k tokens。
- [ ] 错误码在 `spec/bridge-methods.json` 与本文档一致。
- [ ] 破坏性操作（restore/overwrite/delete bone）要求显式确认或返回明确警告。
- [ ] 所有 Tool 在 `booting`/`gui_visible`/`degraded` 状态下的行为已定义。
- [ ] 工具名统一 `bb_` 前缀、snake_case、动词开头，避免与 dsh 其他工具冲突。
