# YSM（Yes Steve Model）格式与 YSM-Utils-Plugins 集成侧技术事实

> **用途**：为《Blockbench 无头建模/贴图 Agent 插件系统设计方案》提供 YSM 侧事实依据（结构、规范、插件导入/导出链路、可复用边界、贴图与动态加载策略）。
> **基线**：`vendor/YSM-Utils-Plugins` v2.6.0（MIT，`package.json:1-5`）；`vendor/blockbench`（Blockbench 5.2.x 源码，`js/`）。
> **方法**：逐行读插件源码 + 默认资源包 JSON 实测 + Blockbench 源码调用链核对 + YSM 官方 wiki/文档/旧版完整指南交叉验证。无法确认处标 **【未验证】**。
> **约定**：`文件:行号` 均相对 `F:\Deepseek_harness\blockbench\`；`vendor/…` 指 `blockbench/vendor/…`。

---

## 0. 关键结论速览（TL;DR）

1. **YSM 资源包 = `ysm.json`（spec 2）+ 任意子目录里的模型/动画/控制器/贴图/lang/avatar/sounds/functions**。只有 `ysm.json` 是固定名、固定位置；其余路径全部由 `ysm.json` 索引，可任意命名（`assets/default/ysm.json:62-124`；官方 wiki「项目结构」）。
2. **模型是 Bedrock 1.12.0+ geometry**（`format_version: "1.12.0"`，`minecraft:geometry` 数组，`texture_width/height: 128`，per-face UV），YSM 用 geckolib 渲染；动画是 Bedrock 1.8.0 animation，控制器是 Bedrock 1.19.0 animation_controllers（`assets/default/models/main.json:1-15`、`animations/main.animation.json:1-3`、`controller/main.animation_controllers.json:1-3`；wiki「模型格式说明」）。
3. **默认主模型 64 根骨骼 / 172 cubes**，唯一根骨骼 `Root`，`Root→MAllBody→AllBody→{UpBody→UpperBody→…, DownBody→…}`；30 根空骨骼（无 cube），其中绝大多数是 **定位组（Locator）**，它们靠**骨骼名**而非 Blockbench `locator` 字段表达（`assets/default/models/main.json` 实测；见 §2.3）。
4. **运行时确有硬编码组名**（官方 wiki「模型制作」明确列出）：`Head`、`AllHead`、`ViewLocator`、`Left/RightHandLocator`（+数字 2-8）、`Left/RightWaistLocator`、`BladeLocator`、`SheathLocator`、`ElytraLocator`、`Left/RightShoulderLocator`、`PistolLocator`、`RifleLocator`、`BackpackLocator`、`ysmGlow*`；第一人称手臂模型要求 `LeftArm/RightArm` 作根分组、可选 `Background`。`Root/MAllBody/AllBody/UpBody/UpperBody` 的层级是**默认模型规范（动画兼容约定）**，未见官方文档声明为运行时强制 **【未验证】**。
5. **YSM-Utils-Plugins 是纯 UI 型插件**：`BBPlugin.register("ysm-utils", …)`（`src/index.js:9-31`），**不注册 Codec/Format、不注册 Project Property、不派发 Blockbench 事件、不导出任何函数**；全部能力是 1 个菜单 + 4 个 Action + 若干 Dialog/Vue（`src/index.js:33-44`）。rollup 以 `format:"cjs"` 打成单文件（`rollup.config.js:8-24`），Blockbench 用 `new Function("requireNativeModule","require", code)` 执行（`js/plugin_loader.ts:804-815`）→ **打包后所有内部符号都是闭包私有**。
6. **导入按钮不是“编辑”**：任务是“导入主模型/导入手臂模型”（`src/vue/import/player_files.vue:42-55,122-127`）；导入即 `loadModelFile()` **新开一个 Blockbench 项目 tab**，format 落在 **`bedrock`（Bedrock Model，entity_format，id=`bedrock`）**，不是 `bedrock_block`（`js/io/io.js:67-108`；`js/formats/bedrock/bedrock.js:1258-1323,1555-1597`；`js/interface/setup_settings.js:275`）。
7. **插件只负责写 `ysm.json`**：`saveYsmFile()` 只调 `saveNormalization()` + `PLUGINS_FS.writeFileSync(ysm.json)`（`src/import/open_import_dialog.js:42-46`）。**模型/动画/控制器/贴图的实际回写完全依赖 Blockbench 自己的“智能保存”**（`Codecs.bedrock.write/overwrite`、`AnimationCodec.exportFile`、`Texture.save`，`js/io/io.js:378-472`）。因此方案里的 `bb_save_project` **必须显式编排这些调用**，不能指望插件。
8. **纯代码导出是可行的、且可以不弹窗**：`Codecs.bedrock.compile()/write()`（`js/formats/bedrock/bedrock.js:1324-1461`）、`AnimationCodec.codecs.bedrock.compileFile/exportFile`（`js/formats/bedrock/bedrock_animation.js:551-717`）、`AnimationCodec.codecs.bedrock_animation_controller.compileFile/exportFile`（`js/formats/bedrock/animation_controller_codec.js:74-138`）、`Blockbench.writeFile(path,{content})`/`{savetype:"image"}`（`js/file_system.ts:450-497`）。注意：写回**已存在**的模型文件时 `write()` 会走 `overwrite()`，若目标文件不是合法 bedrock geometry 会弹 Electron messagebox（`bedrock.js:1399-1431`）。
9. **贴图**：`files.player.texture` 是有序数组（元素可为路径字符串或 `{uv,normal,specular}`，`src/import/load_normalization.js:75-90`）；`properties.default_texture` 的值是**不含路径与扩展名的文件名**（如 `"default"`，官方 wiki + 插件 `pathToName(...,false)` 用法 `src/vue/import/properties.vue:118-129`）。Blockbench 侧 `bedrock` 格式 `single_texture:true`，渲染/绘制目标由 **`Texture.selected`/`Texture.getDefault()`** 决定（`js/formats/bedrock/bedrock.js:1576`；`js/texturing/textures.js:2220-2238`）；像素改动后 `texture.save()` 会**原地写回原 PNG 路径**（`textures.js:1640-1726`）。
10. **插件没有可调用的运行期 API，也没有可挂接事件**。要在无头环境复用它只能：(a) 复制其 MIT 纯逻辑（`loadNormalization`/`saveNormalization` 等，推荐）；(b) 把不含 Vue 的模块 vendored 进自己的 bundle（需 stub `dialog`，注意 `native_module.js` 的 fs 权限弹窗）；(c) 通过 `BarItems['ysm_utils.*']` 触发其 UI（不可无头，只适合 GUI 共存模式）。检测插件是否加载：`Plugins.registered["ysm-utils"]` / `Plugins.installed`（`js/plugin_loader.ts:17-40,136-143,1078-1106`）。
11. **YSM 侧仅“格式正确”即可**，但有一个例外必须写进校验器：`export_empty_groups` 默认 `true`（`js/interface/setup_settings.js:329`），若用户关掉它，保存/导出会把 **30 根空定位骨骼整棵剪掉**，YSM 进游戏后手持物/鞘翅/拔刀剑全不显示——这是最隐蔽的“看起来对但进游戏不显示”来源。
12. **插件对规范有若干“会改字节”的副作用**：`load→save` 往返会补默认字段（`all_cutout/gui_*/disable_preview_rotation`、`extra_animation` 八个空槽）、删 `metadata.link`、删默认 `sound_path/function_path/language_path`、把贴图洗成对象并删空字段（`src/import/load_normalization.js` / `save_normalization.js` 对比见 §1.6）。方案的 YRL 应**自己实现规范化规则**，不要依赖“先 load 再 save”的顺手行为。

---

## 1. YSM 资源包结构

### 1.1 默认包文件清单（`assets/default/`，实测）

`assets/default/ysm.json` 是 v2.6.0 插件内置的“默认模型”模板（CC0 素材 + spec 2 描述符）。完整清单：

| 路径 | 用途 | 备注/尺寸 |
|---|---|---|
| `ysm.json` | 资源描述文件（唯一固定名/固定位置） | 3.3 KB，spec 2 |
| `models/main.json` | 主模型（玩家第三人称 + 大多数场景） | 91 KB，bedrock geometry 1.12.0，128×128，64 bones/172 cubes |
| `models/arm.json` | 第一人称手臂模型（独立模型，无 Root） | 1.9 KB，128×128，6 bones/7 cubes |
| `models/arrow.json` | 替换箭的投掷物模型 | 64×64 |
| `models/fishing_bobber.json` | 替换浮标的投掷物模型 | 16×16 |
| `models/boat.json` | 替换船的载具模型 | 128×128 |
| `models/minecart.json` | 替换矿车的载具模型 | 128×128 |
| `animations/main.animation.json` | 主动画 + 并行动画（50 条） | Bedrock 1.8.0，`geckolib_format_version:2` |
| `animations/arm.animation.json` | 手部条件动画（52 条 `hold_/use_/swing_`） | 1.8.0 |
| `animations/extra.animation.json` | 轮盘动画（extra0..extra7） | 1.8.0 |
| `animations/tac.animation.json` | TACZ（永恒枪械）联动动画（64 条） | 1.8.0 |
| `animations/carryon.animation.json` | Carry On 联动（4 条） | 1.8.0 |
| `animations/parcool.animation.json` | ParCool 联动（38 条） | 1.8.0 |
| `animations/swem.animation.json` | SWEM 联动（11 条） | 1.8.0 |
| `animations/slashblade.animation.json` | 拔刀剑联动（53 条） | 1.8.0 |
| `animations/tlm.animation.json` | 车万女仆联动（15 条） | 1.8.0 |
| `animations/fp.arm.animation.json` | 第一人称手臂并行动画（8 条 parallel0-7） | 1.8.0 |
| `animations/arrow.animation.json` / `boat.animation.json` | 投掷物/载具动画 | 1.8.0 |
| `controller/main.animation_controllers.json` | 控制器文件（默认 8 个空 stage） | Bedrock 1.19.0 |
| `textures/default.png` | 主贴图 1 | **128×128** ARGB |
| `textures/blue.png` | 主贴图 2（YSM 多贴图） | **128×128** |
| `textures/arrow.png` / `boat.png` / `minecart.png` / `fishing_bobber.png` | 投掷物/载具贴图 | 64×64 / 128×128 / 128×128 / 16×16 |
| `textures/gui/background.png` / `foreground.png` | 模型选择界面背景/前景 | **52×90** |
| `avatar/null.png` | 作者头像占位 | 128×128 |
| `lang/en_us.json` / `lang/zh_cn.json` | 语言文件（键见 §1.4/§3.4） | 与 `properties` 一一对应 |
| `sounds/`、`functions/` | 音效（ogg）与自定义 molang 函数目录 | **仓库里为空目录**，由“创建默认包”时 `mkdirSync` 生成（`src/create/create_default.js:53-55,64-66`） |

> 插件自身的 i18n 在 `assets/lang/{zh,en}.json`（不是资源包 lang），与 YSM 包无关。
> 插件内置 `assets/default/` 供“创建默认模型”复制（`src/create/create_default.js:3-33,71-107`），图片以 dataURL 形式被 `@rollup/plugin-image` 内联，运行时用 base64 解码写 PNG（`create_default.js:113-118`）。

### 1.2 `ysm.json` 顶层（spec 2）

```jsonc
{
  "spec": 2,                 // 必填；当前唯一合法值 2（PBR 代）。插件读写时都强制改回 2
  "metadata": { ... },       // 可选；游戏内列表/详情展示
  "properties": { ... },     // 可选；缩放、轮盘、GUI 等
  "files": { ... }           // 必填；资源索引（player 主模型必填）
}
```

- `spec` 取值：官方文档「项目结构」明确“当前必须为 2”（spec 2 = 加入 PBR 的一代）；插件 `loadNormalization`/`saveNormalization` 无条件 `ysmJson["spec"] = 2`（`vendor/YSM-Utils-Plugins/src/import/load_normalization.js:151`；`save_normalization.js:223`）。
- 更早的 1.2.0–2.2.0 版本没有 `ysm.json`（用 `info.json`/`main.json` 内嵌 `ysm_extra_info`），插件提供旧版迁移（`src/import/check_directory.js:23-68`；`src/import/old_version_transform.js:157-209`）。旧版几何的 `description.ysm_height_scale/ysm_width_scale/ysm_extra_info` 迁移后落到 `properties.height_scale/width_scale` 与 `metadata`（`old_version_transform.js:141-155,38-71`）。

### 1.3 `metadata`

| 字段 | 必填 | 语义 | 插件默认/清理（load → save） |
|---|---|---|---|
| `name` | **是**（官方） | 游戏内显示名 | load `??=""`；save 空则写 `"<Unknown>"`（`load_normalization.js:2`；`save_normalization.js:2-4`） |
| `tips` | 否 | 描述，支持 `\n` | 同上，空→`"<Unknown>"`（`save:6-8`） |
| `license.type` | **是**（官方） | 许可名 | load 默认 `"All Rights Reserved"`（`load:4-9`）；save 空→`"All Rights Reserved"`（`save:10-17`） |
| `license.desc` | 否 | 许可补充说明 | save 会删空 `desc`（`save:18-21`） |
| `authors[]` | 否 | 顺序保留；仅 `name` 必填 | load 每项补 `name/avatar/role/contact/comment`（`load:11-17`）；save 空 name→`"<Unknown>"`、删空 avatar/role/comment/contact，空数组给 `[{name:"<Unknown>"}]`（`save:24-37`） |
| `authors[].avatar` | 否 | 相对包根的 png（如 `avatar/null.png`），2.5+ 模组自动缩放 | — |
| `authors[].contact` | 否 | 任意键值（qq/email/Bilibili…），顺序保留 | — |
| `link.home` / `link.donate` | 否 | 主页/捐赠 | **save 会整个删除 `metadata.link`**（`save:40-41`） |

### 1.4 `properties`

| 字段 | 默认 | 语义 | 来源/证据 |
|---|---|---|---|
| `height_scale` / `width_scale` | 0.7 / 0.7 | 模型整体缩放（YSM 默认模型按 1/0.7 放大制作） | `load:27-28`；`save:45-46` |
| `extra_animation` | `{extra0..extra7:""}` | 轮盘槽位映射（键可任意名；值为动画名 / `#按钮id` / 键可 `#分类id`/`#return`） | `load:29-38`；`save:47-56`；官方 wiki「项目结构」 |
| `extra_animation_classify` | `[]` | 轮盘子菜单定义 `[{id, extra_animation:{…}}]` | `load:39`；`save:57,74-87` |
| `extra_animation_buttons` | `[]` | 轮盘配置表单 `[{id,name,config_forms:[…]}]` | `load:40`；`save:58,89-125` |
| `preview_animation` | `"idle"`（默认包为 `"gui"`） | 模型选择界面预览动画名 | `load:41`；`save:59`；`assets/default/ysm.json:53` |
| `default_texture` | `""`（默认包 `"default"`） | 默认贴图名 = **文件名去扩展名** | `load:42`；`save:60`（仅空值会删）；`assets/default/ysm.json:58` |
| `free` | false | true 后不可设为授权模型 | `load:43`；`save:61` |
| `render_layers_first` | false | 原版模型层是否先渲染 | `load:44`；`save:62` |
| `disable_preview_rotation` | false | 关闭选择界面旋转（做 GUI 动画） | `load:45`；save 不补默认（存在才保留） |
| `all_cutout` | false | 全启用面剔除（负尺寸描边模型） | `load:46` |
| `gui_no_lighting` | false | 关闭选择界面阴影 | `load:47` |
| `gui_foreground` / `gui_background` | `""` | 选择界面前景/背景 png（相对包根） | `load:48-49`；`save:64-71`（删空值、反斜杠转 `/`） |
| `merge_multiline_expr` | true | 2.6.4+：合并指令关键帧多行表达式 | 官方 wiki；**v2.6.0 插件未知此字段（会原样保留）** |

### 1.5 `files`

```jsonc
"files": {
  "player": {
    "model": { "main": "models/main.json", "arm": "models/arm.json" },     // main 必填
    "animation": {                                                          // 全部可选
      "main": "...", "arm": "...", "extra": "...", "tac": "...", "carryon": "...",
      "parcool": "...", "swem": "...", "slashblade": "...", "tlm": "...", "fp_arm": "..."
    },
    "animation_controllers": ["controller/main.animation_controllers.json"], // 可选，可多个
    "texture": [                                                            // 有序；默认贴图在最前
      "textures/default.png",
      { "uv": "textures/blue.png", "normal": "textures/pbr/blue_n.png", "specular": "textures/pbr/blue_s.png" }
    ]
  },
  "projectiles": [ { "match": ["minecraft:arrow", "#minecraft:arrows"], "model": "...", "texture": "...", "animation": "...", "controller": "..." } ],
  "vehicles":    [ { "match": ["minecraft:boat"], "model": "...", "animation": "...", "texture": "..." } ],
  "sound_path": "sounds",        // 可选，默认 sounds；save 时等于默认值则删除
  "function_path": "functions",  // 可选，默认 functions
  "language_path": "lang"        // 可选，默认 lang
}
```

字段语义与证据：

- `files.player` 是**必须**的；`files.player.model.main` 缺失时插件直接提示并中止（`src/import/file_import.js:15-24`）。`model.arm` 被插件默认补 `""`（`load:57-58`），UI 里只有 `.endswith(".json")` 才显示“导入手臂模型”按钮（`src/vue/import/import_type.vue:47-50`）。
- `animation` 的 10 个键来自官方文档 2.5.2+（比 2.4.x 多 `fp_arm`）。**插件 load 默认值漏了 `fp_arm`**（`load:61-70`；对比 `assets/default/ysm.json:68-79`），但 UI 的 `animation_type` 列表包含它（`player_files.vue:24`），编辑时会被 v-model 创建。
- `animation_controllers` 是**数组**（2.3.0+），可拆多个文件；控制器内的名字才是硬约束（§3.6）。
- `texture` 元素两种形态：字符串或 `{uv,normal,specular}`；`uv` 必填，`normal/specular` 是 Oculus/Iris PBR 贴图（官方 wiki）。插件把字符串洗成对象（`load:76-90`），save 时再洗回去、删空字段、丢空元素（`save:154-168`）。
- `projectiles`/`vehicles`：2.5.2+ 为数组、2.4.x 为对象（`{ "minecraft:arrow": {...} }`），load 会迁移对象→数组并补 `match`（`load:110-123`）；save 反向清理空项、`match` 为空的项整条删除（`save:171-202`）。
- 旧版 `files.arrow` 会被迁到 `files.projectiles["minecraft:arrow"]`（`load:100-108`）。
- `sound_path/function_path/language_path`：2.4.1 前 `sound_path` 在 `files.player` 下，load 会提到 `files`（`load:92-97`）；save 时**等于默认值就删除**（`save:204-217`）。

### 1.6 必填 / 默认值 / 规范化差异（load vs save）

`loadNormalization(ysmJson)`（`load_normalization.js:150-182`）用于 **UI 展示**，会**往对象里补**大量默认字段；`saveNormalization(ysmJson, ysmJsonPath)`（`save_normalization.js:222-251`）用于 **写盘前清理**。二者不对称，是“往返改字节”的根源：

| 行为 | load | save |
|---|---|---|
| `spec` | 强制 2 | 强制 2 |
| `metadata.link` | 补 `{home:"",donate:""}` | **整个删除** |
| `authors` 空 | 不处理 | 补 `[{name:"<Unknown>"}]` |
| `license.desc` | 补 `""` | 删空 |
| `properties` 补默认 | `height/width_scale`、`extra_animation` 8 空槽、`classify/buttons=[]`、`preview_animation="idle"`、`default_texture=""`、`free/render_layers_first/disable_preview_rotation/all_cutout/gui_no_lighting=false`、`gui_*= ""` | 只补 `height/width_scale`、`extra_animation`、`preview_animation`、`free`、`render_layers_first`；`default_texture` 空则删；`gui_*` 空则删 |
| `files.player.model` | 补 `main/arm=""` | 补 `main/arm=""`（注意：若 `files.player` 原本不存在，`save` 里 `let player = files["player"] ?? {}` **不会写回** `files`，见 `save:127-128`） |
| `files.player.animation` | 补 9 个键（漏 `fp_arm`） | 只做反斜杠归一 + 全空则删 |
| `files.player.animation_controllers` | `[]` | 过滤空串、全空则删 |
| `files.player.texture` | 全部洗成 `{uv,normal,specular}` | 洗回字符串/对象、删空、丢空对象 |
| `projectiles/vehicles` | 对象→数组、补 match/字段、贴图洗对象 | 归一化、删空、match 空则删条目、空数组则删 |
| `sound/function/language_path` | 补默认值 | 等于默认值则删 |
| 空字符串清理 | 否 | 是（`deleteField`/`deleteObject`，`save:280-299`） |
| 反斜杠路径 | 否 | 全部转 `/`（`save:253-278`） |

**设计含义**：
- 导出器应把 §1.6 视为“规范化的唯一事实源”。建议直接移植 `load/save_normalization.js`（纯函数、MIT，**无任何 UI/原生依赖**），但**只在导出时调用 `saveNormalization`**；不要先 `loadNormalization` 再 `save`，否则会把 UI 默认值写进包。
- 若追求导出幂等（同 revision → 字节级一致），需固定：JSON 缩进（Blockbench `compileJSON` 默认 Tab，受 `settings.json_indentation` 影响，`js/util/json.ts:37-53`）、末尾换行（`settings.final_newline`）、键顺序（沿用输入顺序，不排序）。建议 YRL 用固定 writer，而不是 `autoStringify`。

### 1.7 插件已知盲区（会影响“导出不丢字段”）

| 盲区 | 证据 | 风险 |
|---|---|---|
| `merge_multiline_expr`（2.6.4+）不识别 | 官方 wiki「项目结构」；插件代码无此键 | 插件 UI 保存时不会补/不会删 → 原样保留（安全）；但 YRL 校验器应认识它 |
| `#return` 轮盘特殊键（2.3.1+）无法在 UI 里创建 | `src/vue/import/extra_animation.vue:54-83,150-164` 只提供 `extra0-7`/动画名/`#分类id`，值只提供动画名或 `#按钮id` | 手工 JSON 才能写 `"#return"`；无头 agent 可直接写，GUI 用户受限 |
| 自定义 `language_path` 被语言编辑器忽略 | `language_edit.vue:111,117,124` 读的是 `ysmJson["language_path"]`（根级），实际在 `files.language_path` | 语言文件会写到包根 `lang/`；YRL 应按 `files.language_path` 处理 |
| 2.6.3+ 动态控制器/子控制器/`ysm-builtin` 状态 | 官方 wiki「动画控制器」2.6.3 节 | 校验器只校验“文件名 + 顶层控制器名”即可，不要过度限制 |
| 插件不导入 `normal/specular` 贴图 | `file_import.js:82-99` 只取 `uv`/`texture["uv"]` | 无头导入若需要 PBR 预览/绘制，要自行 `new Texture().fromFile()` 补齐 |

---

## 2. 模型格式

### 2.1 文件与 `format_version`

```jsonc
// assets/default/models/main.json:1-15（arm.json 同构，见 :1-12）
{
  "format_version": "1.12.0",
  "minecraft:geometry": [
    {
      "description": {
        "identifier": "geometry.unknown",
        "texture_width": 128,
        "texture_height": 128,
        "visible_bounds_width": 7,
        "visible_bounds_height": 7,
        "visible_bounds_offset": [0, 0.5, 0]
      },
      "bones": [ /* … */ ]
    }
  ]
}
```

- 官方：「YSM 采用 geckolib 作核心，支持基岩版 1.12.0 及以上模型文件和 1.8.0 动画文件」（wiki「模型格式说明」）。
- 默认包所有模型 `identifier` 都是 `"geometry.unknown"`（main/arm/arrow/boat/fishing_bobber/minecart 实测），且**每个文件只含 1 个 geometry**。Blockbench 保存时按 `identifier` 在原文件里定位并替换 geometry（`bedrock.js:1399-1461`），因此“一文件一 geometry”是安全前提。
- arm.json 的 `visible_bounds` 为 `3 / 4.5 / [0,1.75,0]`（`arm.json:9-11`），与主模型不同——第一人称模型是独立坐标系。

### 2.2 description 字段

| 字段 | 默认包值 | 语义 |
|---|---|---|
| `identifier` | `geometry.unknown` | 模型 id；Blockbench 用它回写定位（`bedrock.js:1401-1415`）。YSM 不依赖固定值 |
| `texture_width` / `texture_height` | 128 / 128（主/手臂、boat、minecart）；64/64（arrow）；16/16（bobber） | UV 分辨率；YSM 默认要求 128×128 |
| `visible_bounds_width/height/offset` | main `7/7/[0,0.5,0]` | 渲染裁剪盒；Blockbench 保存时**会按几何重新计算**（见 §2.8） |

### 2.3 骨骼全清单（`models/main.json`，64 根，实测）

树形（`name (parent) [pivot] cubes数 {rotation}`；`—` 表示无 cube 的空骨骼）：

```
Root (—) [0,0,0] —                         ← 唯一根骨骼
├ MAllBody (Root) [0,20.65,0] —
│ └ AllBody (MAllBody) [0,20.65,0] —
│   ├ UpBody (AllBody) [0,20.65,0] —
│   │ ├ UpperBody (UpBody) [0,20.65,0] cubes=11
│   │ │ ├ AllHead (UpperBody) [0,32.425,-0.025] cubes=1
│   │ │ │ └ MHead (AllHead) [0,33.05,0] —
│   │ │ │   └ Head (MHead) [0,33.05,0] cubes=1
│   │ │ │     ├ Hair (Head) cubes=24
│   │ │ │     │ ├ front_h1 cubes=13
│   │ │ │     │ ├ corner_h1 cubes=16
│   │ │ │     │ ├ FLongHair — → MLongHair — → LongHair —
│   │ │ │     │ │                           ├ hl_side cubes=12
│   │ │ │     │ │                           └ hl_m cubes=17
│   │ │ │     │ └ Ribbon cubes=11 {rot -1.82,33.02,8.40}
│   │ │ │     ├ Face — → Eyes —
│   │ │ │     │            ├ Eyebrow — → RightEyebrow cubes=2 / LeftEyebrow cubes=2
│   │ │ │     │            └ Eyelid —
│   │ │ │     │                 ├ RightEyelid cubes=1 → RightEyesBase cubes=2 → RightPupil cubes=1
│   │ │ │     │                 └ LeftEyelid cubes=1  → LeftEyesBase cubes=2  → LeftPupil cubes=1
│   │ │ │     ├ LeftShoulderLocator (Head) —
│   │ │ │     └ RightShoulderLocator (Head) —
│   │ │ ├ Breast (UpperBody) cubes=6 {rot -32.5,0,0}
│   │ │ ├ Arm (UpperBody) [−0.2,31.275,0] —
│   │ │ │ ├ LeftArm cubes=4 {rot 0,0,-18}
│   │ │ │ │ └ LeftForeArm cubes=2 → LeftHand — → {LeftHandLocator, SheathLocator, LeftWaistLocator}
│   │ │ │ └ RightArm cubes=4 {rot 0,0,18}
│   │ │ │   └ RightForeArm cubes=2 → RightHand — → {RightHandLocator, BladeLocator}
│   │ │ ├ Collar (UpperBody) cubes=5 {rot -15,0,0}
│   │ │ ├ ElytraLocator (UpperBody) —
│   │ │ ├ RifleLocator (UpperBody) — {rot 0,0,45}
│   │ │ ├ BackpackLocator (UpperBody) —
│   │ │ ├ PistolLocator (UpBody) — {rot -30,0,0}
│   │ │ └ RightWaistLocator (UpBody) — {rot -5,0,0}
│   │ └ DownBody (AllBody) [0,20.65,0] —
│   │   ├ Leg (DownBody) —
│   │   │ ├ LeftLeg cubes=1 → LeftLowerLeg cubes=1 → LeftFoot cubes=3
│   │   │ └ RightLeg cubes=1 → RightLowerLeg cubes=1 → RightFoot cubes=3
│   │   └ Skirt cubes=3
│   │     ├ RightSkirt cubes=3 {rot 0,0,17.5}
│   │     ├ LeftSkirt cubes=3 {rot 0,0,-17.5}
│   │     ├ FrontSkirt cubes=8 {rot -20,0,0}
│   │     └ BackSkirt cubes=4 {rot 12.5,0,0}
└ molang (Root) [0,-0.35,0] —               ← 默认模型的“脚本骨骼”（见 §3.7）
```

统计：`bones=64, cubes=172, 空骨骼=30, 带 rotation 的骨骼=12, 带 rotation/pivot 的 cube=84`（实测）。空骨骼 30 根中 26 根是定位组/关节，4 根是 `Root/MAllBody/AllBody/UpBody/molang` 这类结构/脚本骨骼。

`models/arm.json`（6 bones / 7 cubes，两个根骨骼，无 Root）：

| bone | parent | pivot | cubes | 说明 |
|---|---|---|---|---|
| `LeftArm` | —（根） | `[1.15,29.775,0]` | 2 | 第一人称手臂 |
| `LeftForeArm` | LeftArm | `[1.875,23.825,0.025]` | 2 | |
| `LeftHandLocator` | LeftForeArm | `[1.875,18.325,0.025]` | 1 | 兼作手部定位 |
| `RightArm` | —（根） | `[-1.15,29.775,0]` | 2 | |
| `RightForeArm` | RightArm | `[-1.875,23.825,0.025]` | 2 | |
| `RightHandLocator` | RightForeArm | `[-1.875,18.325,0.025]` | 1 | |

> 官方「模型制作」：第一人称模型只保留 `LeftArm`/`RightArm`（X/Y/Z 旋转归零、垂直向下），根目录可加 `Background` 分组做背景；「旧版完整指南」还要求删掉 `Root`。

### 2.4 pivot / 坐标 / 镜像约定

- Bedrock 坐标：**1 单位 = 1/16 格，Y 向上**。pivot 是骨骼的旋转中心（绝对坐标，相对模型原点）。
- YSM 默认主模型原点在**脚底中心**：`Root.pivot=[0,0,0]`，几何 Y 范围 `[0,43.3]` 单位（≈2.71 格）；`height_scale=0.7` 后渲染高 ≈30.3 单位（≈1.89 格）。头顶（Head cube 顶面）原始 40.05 单位 → ×0.7 = 28.0 单位（≈1.75 格）。
  > ⚠️ 现有设计文档 `docs/03-Tool-API-清单.md:28` 写“标准身高约 32 单位”，不精确：32 是 Minecraft 玩家 hitbox 高，不是默认 YSM 模型的原始几何高度。校验器应以“几何包围盒 × `height_scale`”判断，而不是硬编码 32。
- **X 轴镜像**：Bedrock JSON 用右手/左手对称坐标，Blockbench 在导入/导出时对 X 取反（`bedrock.js:696-705` 解析 cube origin；`928-937` 重新编译；`766-771` 骨骼 pivot/rotation 取反；`1001-1005` group 旋转取反）。这是 Blockbench 内部约定，不影响 JSON 格式本身。
- `mirror`：bone/cube 级镜像 UV 标记。默认主模型未使用（无 `mirror` 字段），arm.json 的 `RightHandLocator` cube 有 `"mirror": true`（`arm.json:61`）。
- `rotation` 可用在 bone 与 cube 上；cube 带 rotation 时同时带 `pivot`（默认模型 84 个 cube 如此，`main.json` 实测）。

### 2.5 cube 结构

```jsonc
// main.json 中 172 个 cube 全部是 per-face UV（没有 box_uv 数组）；示例 Head (main.json，经 PowerShell 解析)
{
  "origin": [-3.5, 33.05, -3.5],     // 最小角（Bedrock 空间）
  "size":   [7, 7, 7],               // 尺寸；隐含 inflate=0
  "uv": {
    "north": {"uv": [7, 17], "uv_size": [7, 7]},
    "east":  {"uv": [0, 17], "uv_size": [7, 7]},
    "south": {"uv": [21,17], "uv_size": [7, 7]},
    "west":  {"uv": [14,17], "uv_size": [7, 7]},
    "up":    {"uv": [7, 10], "uv_size": [7, 7]},
    "down":  {"uv": [14,17], "uv_size": [7,-7]}   // up/down 在 JSON 里是“预翻转”的值
  }
}
```

- cube 允许字段（默认包实测出现）：`origin/size/uv/pivot/rotation/mirror/inflate`；`mirror` 与 `inflate` 默认包主模型未用。
- 每面 `uv_size` 允许为 0（隐藏面）或负数（翻转）；`uv` 为左上角。
- **up/down 面在 Bedrock JSON 中存的是翻转后的 uv/uv_size**；Blockbench 解析时再翻回来、导出时再翻回去（`bedrock.js:732-734` / `966-971`）。YRL 若自己做 UV 编辑，必须与 Blockbench 的这套约定一致，否则贴图上下颠倒。
- `uv` 也允许是 `[u,v]` 数组（box_uv）；默认包主模型 **0 个** cube 用 box_uv，但 `arm.json` 与其它默认模型也全是 per-face。设计文档里的 `set_uv` 工具应同时支持两种（YSM 文档不限定）。

### 2.6 运行时硬编码的骨骼/组名（证据分级）

**A 级：官方 wiki 明确“特定组名/会被游戏自动添加功能”（`ysm.cfpa.team/wiki/tph2yetr/`）**

| 组名 | 作用 | 备注 |
|---|---|---|
| `Head` | 头部定位组 | 游戏默认添加“头部随视角摆动”动画；改名即失去该效果（旧版指南也确认“唯一代码添加的动画”） |
| `AllHead` | 更真实的第一人称 / Better Combat 定位组 | 第一人称会隐藏该组下模型 |
| `ViewLocator` | 视角定位组 | 头部高低由该 pivot 的 Y 决定 |
| `LeftHandLocator` / `RightHandLocator` | 主/副手手持物定位 | 缺失则不渲染对应手物品；2.4.0+ 可加数字 2-8 扩展 |
| `ElytraLocator` | 鞘翅定位 | 缺失不渲染鞘翅 |
| `LeftShoulderLocator` / `RightShoulderLocator` | 肩上鹦鹉定位 | 缺失不显示鹦鹉 |
| `LeftWaistLocator` / `RightWaistLocator` | 主/副手拔刀剑定位（官方原文“主手我没写错”） | 缺失不显示腰间拔刀剑 |
| `BladeLocator` / `SheathLocator` | 主手拔刀剑刀身/刀鞘定位（2.3.0+） | 缺失不显示对应部件 |
| `PistolLocator` / `RifleLocator` | TACZ 手枪/步枪背挂定位 | 缺失不渲染 |
| `BackpackLocator` | 背包定位（2.4.0+） | 女仆背包/mod 背包 |
| `ysmGlow*`（如 `ysmGlowHead`） | 发光组前缀 | 光影下渲染发光，仅作用于该组 |
| `Background` | 第一人称手臂背景组（arm.json 根目录） | 不受手持/使用状态影响 |
| `LeftArm` / `RightArm` | 第一人称手臂模型的根分组 | 必须垂直向下 |

**B 级：默认模型规范 / 动画兼容约定（官方未声明强制，但“不改默认模型的组，动画基本完美兼容”）** —— `Root→MAllBody→AllBody→{UpBody→UpperBody→AllHead→MHead→Head…, DownBody→Leg→…}`、`Arm→LeftArm/RightArm`、`LeftHand/RightHand`、`Leg/LeftLeg/RightLeg`、`molang` 等。凡是**默认动画文件里出现的骨骼名**都属于事实上的兼容集（见 §3），改名/删骨骼 = 对应动画失效，但模型仍能加载。**【未验证】**：YSM 运行时源码是否对 `Root/MAllBody/AllBody/UpBody/UpperBody` 有硬编码引用（本地无 YSM 源码；官方 wiki 未列）。
- 官方旧版完整指南还专门写了命名规范：“组名采用大驼峰 + 形容词+名称（`LeftArm`、`AllHead`）”，且“不遵守也能加载，但无法使用默认动作”。

> **设计含义**：`bb_validate(profile=ysm)` 的“必需骨骼”应分两级返回：
> `errors`: A 级定位组缺失/改名（会导致进游戏缺件）；`warnings`: B 级层级/名字偏离默认模型（动画会错位/失效）。不要把 B 级全列为 error，否则会阻止合法的“原创骨骼 + 原创动画”包。

### 2.7 尺寸、包围盒与比例

- 贴图 128×128（`main/arm/boat/minecart/default/blue`）、64×64（arrow）、16×16（bobber）、GUI 52×90（实测 System.Drawing 读 IHDR）。YSM 文档“模型支持多个贴图”，默认包 2 张（`default.png`、`blue.png`）。
- `visible_bounds`：默认 `width=7, height=7, offset=[0,0.5,0]`（main）/`3,4.5,[0,1.75,0]`（arm）。
- `properties.height_scale/width_scale=0.7` 是运行时缩放；**默认模型资产是按 1/0.7 ≈ 1.43 倍制作的**，所以“默认模型看起来比玩家大”是正常的。
- Blockbench 保存时 `visible_bounds` **会重算**：`calculateVisibleBox()` 用实际 cube mesh 包围盒 + 已有 `Project.visible_box` 取 max，Y 方向取整（floor/ceil，`bedrock.js:640-678,1364-1370`）。默认包当前值恰好稳定，但自定义模型导出后该字段可能被改写（只影响裁剪，不影响外观）。**【未验证】**：YSM 是否用 visible_bounds 做剔除（大概率是）。

### 2.8 Blockbench 往返（round-trip）影响（导出器必读）

| 行为 | 证据 | 影响 |
|---|---|---|
| 导入 format 判定 | `bedrock` codec 条件：`model['minecraft:geometry'] && format_version >= 1.12.0`（`bedrock.js:1265-1271`）；`bedrock_old` 只接 `<1.12.0` 或旧式 `geometry.*` 顶层键（`bedrock_old.js:132-139`） | YSM 模型稳定落在 `bedrock` codec |
| 每根 bone 变成一个 `Group` | `parseBone` `bedrock.js:755-771` | 空定位骨骼也是 Group（不是 Locator 元素） |
| 空组导出受设置控制 | `compileGroup`：`if (!settings.export_empty_groups.value && !g.children.find(child=>child.export)) return;`（`bedrock.js:991`）；默认 `true`（`setup_settings.js:329`） | **关闭该设置 → 空定位骨骼整棵消失**；导出器必须强制 `Settings.set('export_empty_groups', true)` 或前置校验 |
| format_version 可能升级 | `getFormatVersion()`：cube face rotation→`1.21.0`；`bedrock_binding`→`1.16.0`；否则 `1.12.0`（`bedrock.js:1216-1236`） | YSM 包应固定 `1.12.0`；若模型用了新特性会被升级 |
| identifier 由 `Project.geometry_name` 决定 | `compile` `bedrock.js:1333`；`parseGeometry` 设置 `Project.model_identifier`（`845-870`） | 只要导入时正常解析，导出 identifier 不变 |
| 覆盖写回按 identifier 匹配 | `overwrite`：读原文件→找同 id geometry→替换（`1399-1458`）；target 不存在则 append | 多 geometry 文件可能重复追加；一文件一 geometry 才安全 |
| 文件不可解析时弹窗 | `overwrite` catch 里 `dialog.showMessageBox`（`1416-1430`） | **无头导出前必须保证目标文件合法** |
| 多 geometry 文件导入会弹选择框 | `parse` 若 `geometries.length>1` 弹出 `bedrock_model_select` Dialog（`bedrock.js:1473-1535`） | 无头导入要避免/预判；建议包内一文件一 geometry |
| 保存时 `saveTextures()` 先跑 | `export_over`（`io.js:386`） | 贴图脏数据会先落盘 |
| 模型写入目标 = `Project.export_path` | `io.js:388-394`；`codec.ts:159-186`（`remember:true` 时设置） | 导入后不额外设置也能写回原文件 |

---

## 3. 动画与控制器

### 3.1 动画文件格式（Bedrock 1.8.0）

```jsonc
// animations/main.animation.json:1-3 + idle 片段（实测）
{
  "format_version": "1.8.0",
  "geckolib_format_version": 2,           // YSM/GeckoLib 附加字段；Blockbench 不解析但会保留
  "animations": {
    "idle": {
      "loop": true,
      "animation_length": 3,
      "bones": {
        "UpBody":  { "rotation": [0,0,0],
                     "position": { "0.0": {"post":[0,0,0],"lerp_mode":"catmullrom"}, "0.5417": {"post":[0,0.08201,0],"lerp_mode":"catmullrom"} } },
        "LeftArm": { "rotation": { "0.0": {"post":[0,0,0],"lerp_mode":"catmullrom"} } },
        "Head":    { "rotation": [0,0,0] },          // 常量通道允许直接给数组
        "molang":  { "rotation": ["v.bv=math.cos(1*query.anim_time*360/(72/24))*2",0,0] }
      }
    },
    "walk": { "loop": true, "animation_length": 1, "bones": { "Root": { "position": { "0.0": [0.2,-0.55,0], … } } } }
  }
}
```

- 通道：`rotation`/`position`/`scale`；关键帧可以是常量数组、单值、或 `{ "t": {post,pre,lerp_mode} }`（`pre/post` 与 `lerp_mode:"catmullrom"` 默认包大量使用）。
- 支持 Molang 表达式（字符串）作为通道值；YSM 额外注入了 `ysm.*`、`ctrl.*`、`tlm.*` 命名空间（§3.7）。
- 空动画可只写 `{"loop":true}`——默认包用 `——物理模拟——`、`——眨眼动画——`、`——并行动画——`、`——低优先级并行动画——` 四条**纯注释占位动画**做分组标记（实测，`main.animation.json`）。Blockbench 会把它当普通动画加载/保存，语义上只是分组线。

### 3.2 主动画命名（官方 wiki「玩家主动画」= 运行时硬编码语义）

`main.animation.json` 中以下名字是**约定语义**（游戏按名字播放）：

| 名称 | 触发 | 循环 |
|---|---|---|
| `idle` | 无操作 | 循环 |
| `walk` / `run` | 行走 / 疾跑 | 循环 |
| `sneaking` / `sneak` | 潜行不移动 / 潜行移动 | 循环 |
| `climb` / `climbing` | 活板门下趴行 / 趴下不动 | 循环 |
| `swim` / `swim_stand` | 游泳 / 站立式游泳 | 循环 |
| `jump` | 跳跃/离地（旧指南：飞行也调用） | 循环 |
| `fly` / `elytra_fly` | 创造飞行 / 鞘翅飞行 | 循环 |
| `boat` / `ride` / `ride_pig` / `sit` | 乘船 / 骑马驴 / 骑猪 / 坐下 | 循环 |
| `attacked` | 被攻击 | 单次 |
| `death` | 死亡 | 单次，1 秒 |
| `sleep` | 睡觉 | 循环 |
| `riptide` | 三叉戟激流 | 循环 |
| `use_mainhand` / `use_offhand` | 使用主/副手 | 单次 |
| `swing_hand` / `swing_offhand` | 挥动主/副手 | 单次 |
| `ladder_up` / `ladder_stillness` / `ladder_down` | 爬梯 | 循环 |
| `passenger$<entity_id>` | 骑乘特定实体（默认包 `passenger$touhou_little_maid:maid`） | 循环 |
| `empty` | 调试空动画（官方：不要修改） | — |
| `parallel0..7` | 并行动画（与主动画同时播放，优先级更高，覆盖同骨骼） | 循环 |
| `pre_parallel0..7` | 低优先级并行动画 | 循环 |
| `gui` | 默认包的模型选择界面预览动画名（`ysm.json properties.preview_animation`） | — |

> 没有 `attack` 这个动画名；攻击表现走 `swing_hand`/`swing_offhand` 与手部条件动画的 `swing:*`。

### 3.3 手部条件动画命名（`arm.animation.json`，官方 wiki「手部条件动画」）

命名语法：`<槽位><对象><修饰>`，修饰符三种：`:` 内部分类、`$` 物品 ID、`#` 物品 tag。

- 槽位/对象：`hold_mainhand` / `hold_offhand`、`use_mainhand` / `use_offhand`、`swing` / `swing_offhand`（注意主手挥动是 `swing`，不是 `swing_mainhand`）。
- 内部分类示例（默认包 52 条）：`hold_mainhand:empty`、`:sword`、`:axe`、`:bow`、`:shield`、`:crossbow`、`:charged_crossbow`、`:fishing`、`:fishing_rod`、`:eat`、`:drink`、`:spyglass`、`:spear`、`:throwable_potion`、`:slashblade`；`use_*:eat/drink/spyglass/bow/shield/spear/crossbow/brush/goat_horn`；`swing:sword/axe/pickaxe/shovel/hoe/shield/fishing_rod/throwable_potion`。
- `$` / `#` 示例：`hold_mainhand$minecraft:mace`、`swing$minecraft:mace`、`use_mainhand$minecraft:brush`（默认包 `arm.animation.json` 实测）。
- 这些动画**优先级高于主动画**，只应包含手部相关骨骼（官方警告）。

### 3.4 轮盘动画（extra）与 `ysm.json` 动态配置机制

三层机制（官方 wiki「轮盘动画」+「项目结构」+ 插件 GUI 代码）：

1. **动画本体**：`extra.animation.json` 的 `animations` 里放任意名字动画（默认包 `extra0..extra7`；2.2.1+ 不限数量/不限名字，循环方式由动画自身 `loop` 决定）。只有前 8 个槽可绑快捷键。
2. **轮盘槽 → 动画映射**：`properties.extra_animation` 是**有序 map**：
   - 键：`extra0..extra7` 或自定义名；也可以是 `#<extra_animation_classify.id>`（点击打开子轮盘），或固定键 `#return`（返回按钮，2.3.1+）。
   - 值：`<动画名>`（直接播放）、`#<extra_animation_buttons.id>`（打开配置界面）、或 `#<classify.id>`。
   - 默认包示例：`"extra0": "#extra_config"` + `extra_animation_buttons[0].id = "extra_config"`（`assets/default/ysm.json:28-51`）。
3. **子轮盘 / 配置按钮**：
   - `extra_animation_classify: [{ "id": "分类1", "extra_animation": { "extra0": "动画1", … } }]`（结构同 `extra_animation`）。
   - `extra_animation_buttons: [{ "id": "按钮1", "name": "随便写的名字", "config_forms": [ … ] }]`；`config_forms` 元素：
     - `{type:"range", title, description, value:"v.变量", step, min, max}`
     - `{type:"checkbox", title, description, value:"v.变量"}`
     - `{type:"radio", title, description, value:"v.变量", labels:{"显示名":"v.x=0;"}}`
     - `value` 必须是**变量名**（`v.xxx`），radio 的 labels 值是**执行语句**（官方明确）。
   - 插件 UI 会剥掉前端专用字段 `uuid/tmp_labels` 以及不适用的 `step/min/max/labels`（`save_normalization.js:89-125`）。

**插件 GUI 与 `ysm.json` 的对应关系**（动态配置怎么被编辑）：
- `properties.vue` 里三块：`extra_animation`（键值对列表 + `#` 预设下拉）、`extra_animation_classify`、`extra_animation_buttons`（`src/vue/import/properties.vue:164-229`）。
- `extra_animation.vue` 编辑单条：键候选 = `extra0..7` ∪ `extra.animation.json` 里的动画名 ∪ `#分类id`；值候选 = 自由文本 或 `#按钮id`（`extra_animation.vue:54-83,150-194`）。**没有 `#return` 候选**。
- `extra_animation_buttons.vue` 编辑配置表单：三种 type、可拖拽排序、radio 的 labels 列表，保存时直接 `saveYsmFile()` 写 `ysm.json`（`extra_animation_buttons.vue:24-121`）。
- `extra_animation_classify.vue` 编辑子轮盘（`extra_animation_classify.vue:53-71`）。
- 语言键（用于游戏内显示名）：`properties.extra_animation.<key>`、`...<key>.desc`、`properties.extra_animation_buttons.<id>.config_forms.<i>.title/description/labels.<i>`（`src/util/language.js:65-146`）。

### 3.5 并行动画

- `parallel0..7` + `pre_parallel0..7`，与主动画独立同时播放；并行动画优先级更高、覆盖同骨骼通道；`pre_parallel*` 为低优先级（旧版指南 + 默认包结构）。
- 官方文档的控制器里另有 `player.parallel_*` / `player.pre_parallel_*`（控制层，不是动画层，见 §3.6）。
- 默认包把“物理模拟/眨眼”分别放在 `parallel0`/`pre_parallel0` 等，并用 `molang` 骨骼算 `v.bv` 等中间变量供 `ysm.second_order` 等函数用（见 §3.7）。

### 3.6 控制器（`controller/main.animation_controllers.json`）

格式：

```jsonc
{
  "format_version": "1.19.0",
  "animation_controllers": {
    "player.pre_main": { "states": { "default": { "animations": [] } } },
    "player.post_main": { … },
    "player.pre_hold": { … }, "player.post_hold": { … },
    "player.pre_use": { … },  "player.post_use": { … },
    "player.pre_swing": { … },"player.post_swing": { … }
  }
}
```

- 文件可多个、文件名任意，程序启动时合并；**只有控制器的“名字”是硬约束**，写同名控制器 = 替换该阶段硬编码逻辑（官方 wiki「动画控制器」）。
- 可用控制器名清单（官方）：
  - 主动画：`player.main`、`player.pre_main`、`player.post_main`
  - 手部：`player.hold_mainhand`、`player.hold_offhand`、`player.pre_hold`、`player.post_hold`、`player.use`、`player.pre_use`、`player.post_use`、`player.swing`、`player.pre_swing`、`player.post_swing`
  - 并行动画：`player.parallel_0..7`、`player.pre_parallel_0..7`
  - 骑乘/盔甲：`player.passenger`、`player.vehicle`、`player.armor_head/chest/legs/feet`
  - GUI：`player.gui_hover`、`player.gui_focus`
  - 模组：`player.fire`（仅 TACZ 开火）、`player.carry_on`、`player.parcool`、`maid.misc`、`maid.statue`
  - 投掷物/载具/手臂（2.5.0+ 合并）：`projectile.main/pre_main/post_main/parallel_0..7`、`vehicle.main/pre_main/post_main/ride/move/parallel_0..7/pre_parallel_0..7`、`fp.arm.misc/parallel_0..7/armor_*`
- **2.6.3+ 新机制**（若目标运行时 ≥2.6.3，校验器要放行）：动态控制器前缀（`player.pre_main_<名>`、`player.post_hold_<名>` 等按字母序插入）、`ysm-builtin` 内置状态、子控制器 `{父}.{子}` 与 `ysm-entry-{子}` 状态、空状态连续跳转、子控制器最多嵌套 5 层（官方 wiki「动画控制器」2.6.3 节）。
- 控制器文件里 `states.*.transitions` 用 Molang；`ctrl.*` 是 YSM 注入的布尔/函数命名空间（官方列出：`ctrl.death/riptide/sleep/swim/climb/climbing/ladder_up/ladder_stillness/ladder_down/fly/elytra_fly/swim_stand/attacked/jump/sneak/sneaking/run/walk/idle`；函数 `ctrl.hold('mainhand','$minecraft:apple')`、`ctrl.swing('offhand','#minecraft:axes')`、`ctrl.use('offhand',':eat')`、`ctrl.armor('head','$minecraft:iron_helmet')`、`ctrl.ride('vehicle','$minecraft:pig')`；另有一批模组联动返回字符串/布尔的 `ctrl.*`）。
- 插件在 `ysm_molang.js` 里把同一套名字注册为 Blockbench Molang 自动补全（`src/molang/ysm_molang.js:349-478` 的 `ctrl` namespace），**这就是“运行时硬编码语义”的本地可核对清单**。

### 3.7 Molang 扩展（`ysm.*` / `ctrl.*` / `tlm.*`）

插件把 YSM 注入的 Molang 查询/函数注册为自动补全，可作为规范清单（`src/molang/ysm_molang.js`）：

- `ysm.*`（2-348 行，节选）：`ysm.head_yaw/head_pitch`、`ysm.has_helmet/has_chest_plate/has_leggings/has_boots`、`ysm.has_mainhand/has_offhand/has_elytra`、`ysm.is_*` 系列、`ysm.texture_name`、`ysm.bone_rot/bone_pos/bone_scale/bone_pivot_abs`、`ysm.second_order/first_order`、`ysm.perlin_noise`、`ysm.particle/abs_particle`、`ysm.play_sound/stop_sound`、`ysm.sync`、`ysm.relative_block_name`、`ysm.dump_*`、`ysm.fps`、`ysm.input_vertical/horizontal`、`ysm.armor_value`、属性类（`attack_damage` 等）。
- `tlm.*`（479-532 行）：车万女仆联动（`tlm.is_begging/favorability_point/...`）。
- 默认包的 `molang` 骨骼：在 `idle` 里 `rotation[0] = "v.bv=math.cos(...)"`，然后 `parallel0` 里 `ysm.second_order('胸部垂直', math.clamp(q.vertical_speed+v.bv,…), …)` —— **用一根不可见骨骼承载变量赋值**，是默认模型约定。**【未验证】**：该骨骼名 `molang` 是否为运行时硬编码（更可能是“任选一根空骨骼即可”）。

### 3.8 插件的动画导入行为（重要）

- `importAnimation()` 遍历 `files.player.animation` 的**全部值**导入，无筛选、无动画名过滤（`src/import/file_import.js:112-134`），再按配置导入控制器（`136-152`）。
- 用 `Animator.loadFile(file)`（已废弃但可用）→ `AnimationCodec.codecs.bedrock.loadFile(file, undefined)`（`js/animations/animation_mode.js:506-509`；`js/formats/bedrock/bedrock_animation.js:113`）。**注意 `loadFile` 不弹窗；`importFile` 才会弹“选择导入哪些动画”的 Dialog**（`bedrock_animation.js:27-112`）——无头复用应走 `loadFile`。
- 控制器 `AnimationCodec.codecs.bedrock_animation_controller.loadFile`（`js/formats/bedrock/animation_controller_codec.js:8-68`）。
- 保存：`BarItems.save_all_animations` 对每个动画路径调用 `exportFile(path)`，**只保存 `saved=false` 的动画**，且保留文件里其它键（`geckolib_format_version`、未加载的动画）——按动画逐条 merge，再 `compileJSON` 写回（`js/animations/animation.js:1029-1058`；`js/formats/bedrock/bedrock_animation.js:668-717,562-667`）。控制器同理（`animation_controller_codec.js:85-138`）。
- 风险：`saveAnimation` 会按 `Animation.all` 顺序**重排同一文件内的动画键**（`bedrock_animation.js:618-643`）→ 导出后键顺序可能变（字节不幂等，语义不变）。

### 3.9 对设计含义

- `bb_validate(profile=ysm)` 的动画项应校验：`main.animation.json` 是否含 A 级主动画名（缺失只 warning：YSM 会回退默认动画）；`arm.animation.json` 的条件动画命名是否合法（`^(hold|use|swing)_?…`）；控制器名是否落在 §3.6 白名单或 2.6.3 前缀规则内；`files.player.animation.*` / `animation_controllers` 引用文件存在。
- 新建动画工具（`bb_animation_patch`）应默认把动画写入 `main.animation.json`/`extra.animation.json` 对应文件，并保证 `Animation.path` 指向包内路径，否则保存会落到 `Blockbench.export` 对话框。

---

## 4. 插件导入流程（真实调用链）

### 4.1 入口

```
Blockbench 加载插件
└─ src/index.js:9  BBPlugin.register("ysm-utils", { await_loading:true, onload })
   └─ doLoadEvent()  (index.js:33-44)
      ├─ loadI18n()
      ├─ addYsmMolang()                    → MolangAutocomplete 命名空间 ysm/ctrl/tlm
      ├─ initCacheYsmFoldersAction()       → 读 localStorage["cacheYsmFolders"]
      └─ new BarMenu("ysm_utils", [
            "ysm_utils.create_default_model",   → create_default.js:140
            "ysm_utils.direct_import",          → direct_import.js:6
            "ysm_utils.current_info_menu",      → current_info_menu.js:5
            CACHE_YSM_INFO_ACTION               → cache_info_menu.js:7 (最近打开的包列表)
         ])
```

> 没有 CLI/无参入口；所有入口都是 Action 点击（`new Action(id, {click})`，`js/interface/actions.ts:388-538`）。

### 4.2 “导入一个已有 YSM 包”的真实链路

```
[菜单] ysm_utils.direct_import  (src/menu/direct_import.js:9-23)
  └─ PLUGINS_DIALOG.showOpenDialog({properties:["openDirectory"]})   ← 原生目录选择框
     └─ checkDirectory(packDir)                                      (src/import/check_directory.js:23-68)
        ├─ 有 ysm.json → true
        ├─ 有 info.json → 旧版 1.1.5 → 弹窗询问 → oldVersionTransform()
        └─ 有 main.json → 旧版 1.1.4 → 同上
     └─ openImportTypeDialog(packDir)                                (src/menu/direct_import.js:25-52)
        └─ readYsmFile(packDir)                                      (src/import/ysm_file_read.js:7-27)
           ├─ fs.readFileSync(packDir/ysm.json, "utf8")
           ├─ JSON5.parse(…)           ← 注释里说明“Blockbench 自带 JSON 解析有 bug”
           ├─ addToYsmCache(packDir)   ← localStorage["cacheYsmFolders"]
           └─ loadNormalization(ysmJson)   ← 只补默认值，供 UI 展示
        └─ new Dialog(... import_type.vue ...)                        (direct_import.js:28-51)
           ├─ [导入主模型] → importMainFile()        (import_type.vue:28-30)
           ├─ [导入手臂模型] → importArmFile()       (import_type.vue:31-33)
           └─ [模型信息] → openImportDialog(packDir) (import_type.vue:34-37)
```

另一条等价入口：`ysm_utils.current_info_menu`（当前项目已绑定包路径时）→ `openImportDialog(path)`（`src/menu/current_info_menu.js:9-16`）；以及最近包列表 `cache_info_menu.js:78-98`。

### 4.3 “导入主模型”的真实链路（核心）

```
importMainFile(packDir, ysmJson, dialog, config)          src/import/file_import.js:9-35
├─ 校验 files / files.player / files.player.model.main    :10-25
├─ PLUGINS_FS.existsSync(mainModelPath)                   :27-30
├─ Blockbench.readFile([mainModelPath], {readtype:"text"})  :31
│  └─ loadModelFile(files[0])                             :32
│     └─ js/io/io.js:67-108
│        ├─ 若同路径项目已开 → 直接 select 该 tab          io.js:69-71,81-83
│        ├─ 遍历 Codecs，匹配 load_filter(type:"json", ext:"json", condition)
│        │  └─ Codecs.bedrock.load(model, file, {})         bedrock.js:1258-1323
│        │     ├─ setupProject(entity_format)              bedrock.js:1290-1292
│        │     │   → Format.id = "bedrock"（Bedrock Model；single_texture/animation_files/animation_mode/controllers 全 true）
│        │     ├─ Project.name / export_path = file.path / export_codec="bedrock"   :1294-1299
│        │     ├─ parse(model) → 每 bone 一个 Group / 每 cube 一个 Cube             :1462-1535
│        │     └─ loadDataFromModelMemory()（恢复上次该路径的贴图/动画文件记忆）    :1303-1322
├─ importTexture(playerFiles, packDir, dialog, config)    file_import.js:82-110
│  ├─ 只收集 texture[].uv / texture 字符串（normal/specular 不导入）:83-99
│  ├─ Blockbench.readFile(images, {readtype:"image"})     :101
│  ├─ files.forEach(f => new Texture().fromFile(f).add()) :102   ← 每张图一个 Texture
│  ├─ if (config.load_animation) importAnimation(...)     :103-104
│  └─ addProjectInfo(packDir)                             :108
│     └─ Project["ysm_project_info"] = { path: packDir }  src/util/project_info_manager.js:6-13
└─ importAnimation(objFiles=playerFiles, packDir, dialog, config)   :112-134
   ├─ 收集 player.animation 的全部 .json 路径（10 个键值都导）      :117-123
   ├─ Blockbench.readFile(animations, {readtype:"text"})            :125
   ├─ files.forEach(f => Animator.loadFile(f))                      :126
   │  └─ AnimationCodec.codecs.bedrock.loadFile(f, undefined)       animation_mode.js:506-509
   └─ if (config.load_animation_controllers) importController(...)  :128-130
      └─ readFile(player.animation_controllers) → 同一个 loadFile  :136-152
```

- `config` 默认值：`getCacheYsmImportConfig()` 返回 `{load_animation:true, load_animation_controllers:true}`（`src/menu/cache_info_menu.js:62-72`），在 `import_type.vue` 里以复选框暴露并写回 localStorage（`import_type.vue:38-40,51-53,79-88`）。
- **`importArmFile` 传 `config={}`**（`player_files.vue:47`；`import_type.vue:31-33`）→ 手臂项目**不导入动画/控制器**；`importOtherFile` 传 `{load_animation:true}`（`other_files.vue:49-51`）→ 投掷物/载具导入动画但**不导入 controller 字段**（`importController` 只认 `animation_controllers` 数组，而 other file 是 `controller` 字符串）。
- **`player_files.vue` 没有“编辑模型”按钮**：它只有“导入主模型/导入手臂模型”两个按钮（`:122-127`），其余是文件路径选择（换文件=复制进包，`file_handler.js:12-57`）与贴图增删（`:226-277`）。任务描述里的“编辑”应理解为“在 Blockbench 里打开模型进行编辑”——插件不提供该动作，是 `loadModelFile` 打开项目后用户在视口编辑。

### 4.4 “模型信息”对话框（`openImportDialog`）

`src/import/open_import_dialog.js:57-162`：
- 读 `ysm.json` → 计算 `refLanguageMaps`（`getLanguageMap`，`util/language.js:41-121`）→ `new Dialog`（宽 1000，全量 Vue 侧边栏：metadata / properties / player_files / projectile_files / vehicle_files / language）。
- 按钮：保存（不关）、保存并退出、关闭（`:73-77`）；`onConfirm` 只调 `saveYsmFile(JSON.parse(JSON.stringify(ysmJson)), ysmJsonPath)`（`:78-83`），即**只写 ysm.json**。
- 取消时用 sha256 比对是否修改，弹“是否保存”原生对话框（`:13-37`）。
- 侧边栏还有“打开文件夹”Action（`PLUGINS_SHELL.openPath`，`:105-112`）。

### 4.5 Project 绑定信息的持久性

- `Project["ysm_project_info"] = {path}`（`project_info_manager.js:6-13`）只是**运行时挂在 Project 对象上的普通字段**。
- Blockbench 的 `.bbmodel` 序列化只写 `ModelProject.properties` 中注册过的属性 + 固定字段（`js/formats/bbmodel.js:200-238`），插件**没有** `new Property(ModelProject, …)` → 该字段**不会被持久化**。
- 而本流程通常**不产生 .bbmodel**（`Project.save_path` 为空，只写 `export_path`），所以包路径信息在关闭 Blockbench 后只剩 localStorage 的最近包缓存（`cacheYsmFolders`）。
- **设计含义**：我们的 bridge 必须自己持久化 `project ↔ packDir ↔ ysmJson 快照 ↔ 贴图名映射`（建议 `new Property(ModelProject, 'string', 'ysm_bridge_pack', …)` 或 host 侧数据库），不要复用 `ysm_project_info`。

---

## 5. 保存 / 导出流程（确定结论）

### 5.1 结论先行

| 资产 | 插件是否写盘 | 实际写盘者与触发方式 | 证据 |
|---|---|---|---|
| `ysm.json` | **是**（唯一） | `saveYsmFile()`：`saveNormalization()`+`PLUGINS_FS.writeFileSync` | `open_import_dialog.js:42-46` |
| 模型 `models/*.json` | **否** | Blockbench 智能保存（Ctrl+S / `export_over`）→ `Codecs.bedrock.write(compile(), Project.export_path)` → 已存在文件走 `overwrite()` | `js/io/io.js:378-472`；`codec.ts:321-327`；`bedrock.js:1399-1461` |
| 动画 `animations/*.json` | **否** | 智能保存尾部：`save_all_animations` → 每个 `Animation.path` 的 `exportFile` | `io.js:433-435`；`animation.js:1029-1058`；`bedrock_animation.js:668-717` |
| 控制器 `controller/*.json` | **否** | `save_all_animations` 里 `AnimationCodec.codecs.bedrock_animation_controller.exportFile(path)` | `animation.js:1049-1056`；`animation_controller_codec.js:85-138` |
| 贴图 `textures/*.png` | **否** | 智能保存开头 `saveTextures()` → `Texture.save()`（有 `path` 且文件存在则原地 base64 覆写） | `io.js:386`；`textures.js:2284-2312,1640-1726` |
| lang 文件 | 插件“语言”页手动按钮 | `writeLanguageFile()` | `language_edit.vue:110-114`；`util/language.js:4-21` |

即：**只点插件里的“保存”按钮，模型/动画/贴图不会落盘**。要么用户再按 Blockbench 的保存（Ctrl+S），要么我们的 bridge 显式调用。

### 5.2 Blockbench 智能保存的精确行为（`export_over`，`js/io/io.js:378-472`）

```js
// 伪代码（仅在 isApp 桌面版执行）
await saveTextures();                                   // io.js:386
if (Format) {
  if (Project.save_path) {                              // 只有“另存为项目”才有
    Codecs.project.write(Codecs.project.compile(), Project.save_path);   // bbmodel
  }
  if (Project.export_path && export_codec?.compile) {
    if (export_codec.id != 'image')
      export_codec.write(export_codec.compile(), Project.export_path);   // ← 模型 JSON 原地回写
  } else if (export_codec?.export && !Project.save_path) {
    … // 没有路径时才弹 Blockbench.export / 保存选择器
  }
}
if (Format.animation_mode && Format.animation_files && AnimationItem.all.length) {
  BarItems.save_all_animations.trigger();               // ← 动画 + 控制器回写
}
```

`Codecs.bedrock.write(content, path)`（`codec.ts:321-327`）：
- `fs.existsSync(path) && this.overwrite` → `overwrite(content, path, cb)`（bedrock.js:1399-1461）：读原 JSON → 按 `identifier` 找 geometry → 用 `compile({raw:true})` 的 geometry 替换 → `autoStringify` → `Blockbench.writeFile(path)`。**保留文件里其它 geometry 与顶层未知字段。**
- 文件不存在 → 直接 `Blockbench.writeFile(path,{content})`（父目录必须存在，否则 `fs.writeFileSync` 抛错）。
- 解析失败且用户点“取消” → 不写；点“覆盖” → 走 `data/index undefined` 分支做 append（`bedrock.js:1416-1460`）。**→ 无头导出必须保证目标文件是合法 bedrock geometry。**

### 5.3 设计必须补的“保存/导出”步骤（可直接调用的路径）

> 方案里 `bb_save_project`（写回 `pack/`）与 `bb_export_ysm`（写 `exports/<ts>/`）都需要自己编排，下列 API 均已核实存在且**不走原生对话框**（前提：目标目录存在、目标模型文件合法）。

```js
// ===== A. 保存回工作副本 pack/（模型/动画/控制器/贴图/ysm.json）=====
// 0) 确保“空组导出”开着，否则定位骨骼被剪
Settings.set('export_empty_groups', true);

// 1) 当前项目的模型（每个模型 tab 单独执行）
const codec = Codecs[Project.export_codec] ?? Codecs.bedrock;
if (Project.export_path) codec.write(codec.compile(), Project.export_path);   // 已存在→overwrite，保留其它 geometry

// 2) 动画：按文件分组，只写脏的（exportFile 内部会判 !saved）
const paths = [...new Set(Animation.all.map(a => a.path).filter(Boolean))];
paths.forEach(p => AnimationCodec.codecs.bedrock.exportFile(p));               // 已有文件→per-animation save
// 3) 控制器
const cpaths = [...new Set(AnimationController.all.map(c => c.path).filter(Boolean))];
cpaths.forEach(p => AnimationCodec.codecs.bedrock_animation_controller.exportFile(p));

// 4) 贴图（原地 PNG）
await saveTextures();                          // 全局函数；或 Texture.all.filter(t=>!t.saved).forEach(t=>t.save())

// 5) ysm.json
Blockbench.writeFile(join(packDir,'ysm.json'),
  { content: autoStringify(saveNormalization(ysmJsonCopy)) });                 // 规范化规则见 §1.6

// 一键替代（不推荐用于需要 await 的无头流程：trigger 返回 boolean，内部 async 不被等待）
BarItems.export_over.trigger();                // 等价于 Ctrl+S；会顺带 saveTextures + save_all_animations
```

```js
// ===== B. 导出发布副本 exports/<ts>/（目标路径全新）=====
// 1) 模型：编译成 JSON 字符串或对象
const modelJsonStr = codec.compile();                    // 字符串（autoStringify）
const modelObj     = codec.compile({raw:true});          // 对象（做 diff/manifest 用）
Blockbench.writeFile(outPath('models/main.json'), {content: modelJsonStr});
// 注意：compile() 依赖全局 Project —— 多模型包要逐个项目 tab 执行 project.select() 再 compile()

// 2) 动画/控制器：compileFile 聚合后再写（不要用 exportFile，它只写已加载路径）
Blockbench.writeFile(outPath('animations/main.animation.json'), {content: autoStringify(
  AnimationCodec.codecs.bedrock.compileFile(Animation.all.filter(a => a.path === srcMainAnimPath))
)});
Blockbench.writeFile(outPath('controller/main.animation_controllers.json'), {content: autoStringify(
  AnimationCodec.codecs.bedrock_animation_controller.compileFile(
    AnimationController.all.filter(c => c.path === srcControllerPath))
)});

// 3) 贴图：dataURL → PNG（writeFile 的 savetype:'image' 会 base64 解码）
for (const tex of Texture.all) {
  Blockbench.writeFile(outPath('textures/'+tex.name), {content: tex.canvas.toDataURL('image/png'), savetype:'image'});
}

// 4) ysm.json：写副本（路径仍指向相对路径，不需要改）
Blockbench.writeFile(outPath('ysm.json'), {content: autoStringify(saveNormalization(ysmJsonCopy))});

// 5) 其余原样复制（lang/avatar/sounds/functions）：Blockbench 无 copy API → 需宿主/原生 fs，或导出时忽略
```

注意事项（均为代码级事实）：
- **`Codecs.bedrock.compile()` 使用全局 `Project`**（`compileGroup` 读全局 `settings`/`Project.texture_width`；`bedrock.js:1324-1398`），因此编译 B 模型前必须 `project.select()`。`codec.context` 只用于 collection 局部导出，不是多 tab。
- **`AnimationCodec.codecs.bedrock.exportFile(path)`** 在目标文件存在时只保存 `!saved` 的动画（不会重写整个文件），因此**不能用来“导出到新目录”**；新目录导出要用 `compileFile`。
- `Blockbench.writeFile` = `Filesystem.writeFile`，桌面端直接 `fs.writeFileSync`（`file_system.ts:450-497`），**不需要插件原生 fs 权限**；但**不会自动建目录**。
- `saveNormalization` 是纯函数（`save_normalization.js:222-251`，`ysmJsonPath` 参数实际未使用），可以安全地在 bridge 内复用（若选择复制实现，按 MIT 附版权声明）。
- 导出幂等：`autoStringify` 依赖 `settings.minifiedout` 与 `settings.json_indentation`（`util/util.js:475-477`；`util/json.ts:37-53`），无头环境应固定这两个设置（或 YRL 自带固定 writer）。

### 5.4 保存相关的 UI 陷阱（无头环境必须规避）

| 陷阱 | 触发条件 | 证据 |
|---|---|---|
| `export_over` 无路径时弹保存选择器 | `!Project.save_path && !Project.export_path` 且 `Format.edit_mode` → `Codecs.project.export()`；或 `export_codec.export` 且未关 `dialog_save_codec` | `io.js:396-431` |
| `saveTextures()` 弹确认框 | ≥2 张脏贴图**没有**已存在路径时弹 `save_all_textures` 确认 | `textures.js:2290-2308` |
| `Codecs.bedrock.write` 弹覆盖询问 | 目标模型文件存在但不是合法 bedrock geometry | `bedrock.js:1416-1430` |
| `Project.close()` 弹“未保存”三选一 | 关闭 dirty 项目 | `project.ts:499-528` |
| 动画 `saveAnimation` 弹覆盖询问 | 目标动画文件存在但不是合法 animation JSON | `bedrock_animation.js:585-611` |
| 打开多 geometry 的模型文件弹选择框 | `geometries.length>1` | `bedrock.js:1473-1535` |

→ 无头流程应：导入后立即设置/确认 `Project.export_path`；不改项目 `save_path`（避免写 bbmodel）；导出前先 `saveTextures` 前保证贴图 `path` 存在；`Project.close({force:true})` 用 force 跳过警告（`Project.close(force)` 参数见 `project.ts:528`）。

---

## 6. 程序化复用：导出边界、函数清单、绕开 UI 的调用序列

### 6.1 打包形态与“是否导出”

- `rollup.config.js:8-24`：`input:"src/index.js"`，`output:{file:"ysm-utils.js", format:"cjs"}`，`external:["path"]`，插件 `vue()/json()/resolve()/commonjs()/terser({mangle:false})/image()`。
- 入口 `src/index.js` **只有副作用**（`BBPlugin.register(...)`、`new BarMenu(...)`），**没有任何 `export`**。rollup CJS 输出因此**不产生 `module.exports`/`exports` 赋值** → 打包产物是“一段脚本”，不是模块。
- Blockbench 加载插件的方式是 `new Function('requireNativeModule','require', code)`（`js/plugin_loader.ts:804-815`）——即**函数体作用域**，`var/const/function` 全部私有；两个 `require(...)` 由 Blockbench 注入（`getPluginScopedRequire`，`native_apis.ts:208-213`），所以 `import {join} from "path"`/`crypto` 能工作（path/crypto 属 SAFE_APIS，`native_apis.ts:34-47`）。
- 旁证：`replace.cjs` 把 `__vue_component__/__vue_script__/__vue_render__` 全部重命名——说明 bundle 是**单一扁平作用域**（否则不会撞名）。
- **结论**：即使我们拿到 `ysm-utils.js` 文本，也**拿不到** `createAllFiles/readYsmFile/loadNormalization/saveNormalization/importMainFile…` 中任何一个；它们既不在 `exports`，也不挂 `window`。**【未验证】**：构建产物未入库（`.gitignore` 排除 `ysm-utils.js`），结论由 rollup 语义 + 入口无 export + 执行方式推得（高置信）。

### 6.2 函数清单（源码级导出 → 实际可否复用）

| 函数 | 源文件:行 | 是否 `export` | 输入 | 输出 | UI / 原生依赖 | 可无头复用？ |
|---|---|---|---|---|---|---|
| `loadNormalization(ysmJson)` | `load_normalization.js:150` | 是 | ysm.json 对象 | 就地修改并返回（补默认值，见 §1.6） | **无** | ✅ 可直接抄（MIT） |
| `saveNormalization(ysmJson, ysmJsonPath)` | `save_normalization.js:222` | 是 | ysm.json 对象（`ysmJsonPath` 未使用） | 清理后的对象 | **无** | ✅ 可直接抄 |
| `readYsmFile(packDirectory)` | `ysm_file_read.js:7` | 是 | 包目录 | 规范化对象 / 解析失败 undefined | `PLUGINS_FS`（native fs）+ JSON5 + `addToYsmCache`(localStorage)；失败时 `autoParseJSON` 弹错误框 | ⚠️ 需替换 fs/去掉缓存；本质 = read+parse+loadNormalization |
| `importMainFile(packDir, ysmJson, dialog, config)` | `file_import.js:9` | 是 | 包目录、ysmJson、`Dialog`、config | 无返回值（异步回调链） | `loadModelFile`（全局）、`Blockbench.readFile`、`new Texture().fromFile().add()`、`Animator.loadFile`、`dialog.close()`、`addProjectInfo`；缺字段时 `Blockbench.showQuickMessage` | ⚠️ 可传 `{close(){}}` stub，但会新开项目、依赖 `Animator` 全局；建议自写编排（见 §6.3） |
| `importArmFile(packDir, ysmJson, dialog, config)` | `file_import.js:37` | 是 | 同上 | 同上 | 同上（config 默认 `{}` → 不导动画） | 同上 |
| `importOtherFile(packDir, file, dialog, config)` | `file_import.js:65` | 是 | 包目录、单个 projectile/vehicle 对象、Dialog、config | 同上 | 同上；不会导 controller 字符串 | 同上 |
| `createAllFiles(selectFilePaths, formResult)` | `create_default.js:36` | **否**（模块内） | `[输出父目录]`、`{packName}` | 无（写盘后 `openImportDialog()`） | `PLUGINS_FS.mkdirSync/writeFileSync`（native fs，BB5 需授权）、`Dialog/Action`（入口）、末尾弹 UI | ❌ 直接不可达；**目录骨架逻辑可照抄**（见 §6.3/§8.4） |
| `createDefaultModel` Action | `create_default.js:140` | 是（Action 对象） | — | — | `PLUGINS_DIALOG.showOpenDialog` + Dialog | ❌ 仅 UI |
| `openImportDialog(packDirectory)` | `open_import_dialog.js:57` | 是 | 包目录 | 无（展示 Dialog） | Dialog + 6 个 Vue 组件 + `onCancel` hash 逻辑 | ❌ 纯 UI |
| `saveYsmFile(ysmJson, ysmJsonPath)` | `open_import_dialog.js:42` | 是 | 对象、路径 | 无（写盘 + quickMessage） | `PLUGINS_FS.writeFileSync` + `Blockbench.showQuickMessage` | ⚠️ 可等价替换为 `Blockbench.writeFile` |
| `getLanguageMap(ysmJson)` | `util/language.js:41` | 是 | ysm.json | `{langKey: 默认值}` | **无** | ✅ 可抄（生成语言模板用） |
| `writeLanguageFile/readLanguageFile` | `util/language.js:4/23` | 是 | locale、目录、map | 写/读 `${locale}.json` | `PLUGINS_FS`、`autoStringify/autoParseJSON` | ⚠️ 可用 `Blockbench` 版 IO 重写 |
| `addProjectInfo/getProjectPathInfo` | `project_info_manager.js:6/19` | 是 | 包目录 | 挂/读 `Project["ysm_project_info"]` | 直接操作 `Project` 全局 + 状态栏文案 | ⚠️ 可用，但不持久（§4.5） |
| `editExtraAnimation*Dialog` 等 | `import/edit_*.js` | 是 | ysmJson、目录、index | Dialog | Dialog + Vue | ❌ 纯 UI |
| `PLUGINS_FS/SHELL/DIALOG` | `util/native_module.js:4-6` | 是 | — | BB5: `requireNativeModule("fs"/"shell"/"dialog")`；BB4: 全局 `fs/electron.*` | **BB5 首次 `requireNativeModule("fs")` 会弹权限框**（`native_apis.ts:95-184`） | ⚠️ 见 §8.4 权限策略 |

> `importAnimation` / `importController` / `importTexture` 是 `file_import.js` 内的**私有函数**（无 export，`file_import.js:82,112,136`），复用只能整段拷贝或自己写。

### 6.3 绕开 UI 的替代调用序列（推荐给 bridge/YRL）

```js
// ===== 打开已有包（不依赖插件、无 UI）=====
const text = await readText(packDir + '/ysm.json');          // Blockbench.readFile(...,{readtype:'text',errorbox:false})
const ysmJson = JSON.parse(text);                            // 需要容错时可内置 json5
normalizeForUi(ysmJson);                                     // = 复制 loadNormalization（可选，仅内存态）
validatePack(ysmJson, packDir);                              // 自己的校验：文件存在性/字段（用 Blockbench.readFile 探测）

// ===== 导入某个模型（main/arm/arrow/boat/...）=====
const modelText = await readText(abs(ysmJson.files.player.model.main));
loadModelFile({ path: abs(path), content: modelText });       // 全局函数；等价 Codecs.bedrock.load(JSON.parse(text), {path, content})
// 若目标 tab 已存在（同 path），loadModelFile 会直接 select 已有 tab（io.js:69-71）

// ===== 贴图：导入全部（含 normal/specular，插件本身不导）=====
const texEntries = ysmJson.files.player.texture;               // string | {uv,normal,specular}
for (const e of texEntries) {
  const uv = typeof e === 'string' ? e : e.uv;
  const tex = new Texture().fromFile({ path: abs(uv) }).add();
  textureMap[pathToName(uv, false)] = tex.uuid;                // YSM 名（无扩展名）→ Texture
}
Texture.all[0].select?.() ?? (Texture.selected = Texture.all[0]);   // 让第一张成为可见/绘制目标

// ===== 动画/控制器：loadFile（不弹窗）=====
for (const p of Object.values(ysmJson.files.player.animation).filter(Boolean)) {
  AnimationCodec.codecs.bedrock.loadFile({ path: abs(p), content: await readText(abs(p)) });
}
for (const p of ysmJson.files.player.animation_controllers ?? []) {
  AnimationCodec.codecs.bedrock_animation_controller.loadFile({ path: abs(p), content: await readText(abs(p)) });
}

// ===== 绑定/记录（桥接层私有，别用 ysm_project_info）=====
Project.ysm_bridge = { packDir, ysmJson, textureMap };         // 建议同时 new Property(ModelProject,...) 持久化
```

要点：
- `loadModelFile`/`Codecs.bedrock.load` 需要 `{path, content}`；`content` 给字符串即可（`io.js:102` 会 `autoParseJSON`；直接调 `Codecs.bedrock.load` 则传已解析对象）。
- `new Texture().fromFile({path})` 在桌面端只传 path 也能工作（`textures.js:444-467` → `fromPath`），无需先读内容。
- `Animator.loadFile` 是 deprecated 包装（`animation_mode.js:506-509`），等价且更推荐用 `AnimationCodec.codecs.bedrock.loadFile`。
- 不要用 `AnimationCodec.importFile`（会为多动画弹选择 Dialog，`bedrock_animation.js:27-112`）。

### 6.4 Vendoring（把插件无 Vue 模块复制进 bridge bundle）的可行性与边界

可行，但要注意依赖链：
- ✅ 可安全 vendored：`src/import/load_normalization.js`、`src/import/save_normalization.js`（纯函数、无 import）。
- ⚠️ `src/import/file_import.js`：import `path`、`project_info_manager`、`image_handle`、`native_module`（→ `requireNativeModule("fs")`）。vendored 后 `requireNativeModule` 由 Blockbench 注入**到 bridge 插件自己的作用域**，可用；但 `PLUGINS_FS` 在 BB5 首次加载会弹 fs 权限框；且 `addProjectInfo` 需要 `Project`。把 `dialog` 换成 `{close(){}}`，并确保 `load_animation*` 配置可控即可。
- ❌ 不要 vendored：`ysm_file_read.js`（→ `cache_info_menu` → `check_directory` → `open_import_dialog` → Vue，UI 链全被拖进来）；`create_default.js`（`openImportDialog` + Action）；所有 `src/vue/**`、`src/import/edit_*.js`、`src/import/open_import_dialog.js`、`src/menu/*`。
- ⚠️ `util/native_module.js` 的 fs 权限：见 §8.4。
- 许可：插件 MIT、默认模型素材 CC0（官方 wiki「模型制作」注明 default 模型以 CC0 发布）→ 复制/再分发需保留 MIT 声明。

---

## 7. 贴图与 UV

### 7.1 `ysm.json` 中的贴图声明

- `files.player.texture`：**有序数组**，顺序 = 游戏内材质列表顺序（官方“读取时保留顺序”）。
- 元素两种写法（`load_normalization.js:75-90` 会把字符串洗成对象）：
  - `"textures/default.png"`
  - `{ "uv": "textures/blue.png", "normal": "textures/pbr/blue_n.png", "specular": "textures/pbr/blue_s.png" }`（PBR，Oculus/Iris；仅 `uv` 必填）
- `properties.default_texture`：**默认材质名 = 文件名去掉路径与 `.png` 后缀**（官方原文；插件 `pathToName(element,false)` 生成候选值，`properties.vue:118-129`）。例如 `textures/default.png` → `"default"`。
- 游戏内显示名来自 lang：`files.player.texture.<name>`（默认包 `{"default":"默认","blue":"蓝色"}`，`assets/default/lang/zh_cn.json`；`util/language.js:104-118`）。
- 运行时“当前贴图”选择：`default_texture` 为切到该模型时的默认；之后由玩家在游戏内切换（模型选择界面/指令 `/ysm model set <player> <model> <texture>`）。**【未验证】**：命令的确切参数形式（来自 wiki 更新日志摘录，未逐字核对 2.6 文档）。

### 7.2 Blockbench 侧的贴图 ↔ YSM 贴图映射

- 插件导入时用 `new Texture().fromFile(file).add()`，**没有保存映射表**（`file_import.js:102`）；Blockbench `Texture.name` 是**带扩展名**的文件名（`textures.js:470` `pathToName(path,true)`），YSM 名是**不带扩展名**（`util.js:488-495`）。二者需要桥接层自建映射：`YSM name (basename w/o ext) ↔ Texture.uuid`。
- `bedrock` 格式 `single_texture: true`（`bedrock.js:1576`）→ 整模型共用“当前选中贴图”，渲染取 `Texture.getDefault()`：
  ```js
  Texture.getDefault() // textures.js:2220-2238
  // 1) Format.single_texture_default 且存在 use_as_default → 用它（bedrock 未开该 flag）
  // 2) Texture.selected 在 Texture.all 中 → 用它
  // 3) 否则 Texture.all[0]
  ```
  → **切换 `Texture.selected` 就是切换模型显示/绘制目标**；导入后建议把 `default_texture` 对应的 Texture 设为 selected。

### 7.3 像素绘制应写入哪个 Texture、如何落成 PNG

- 绘制对象：`Texture` 实例（canvas）。**不要**直接改文件；Blockbench 的撤销/预览都基于 `texture.canvas` + `texture.ctx`（`js/texturing/textures.js:16-120`；UI 编辑走 `edit_image.js`）。
- 画完必须同步：`texture.updateChangesAfterEdit()`（或等价的 `texture.saved = false` + `texture.updateChangesAfterEdit`/`Canvas.updateAll`），并把改动放进 `Undo` 事务。
- 保存：`Texture.prototype.save()`（`textures.js:1640-1726`）：
  - 若 `this.path` 存在且文件存在 → `Filesystem.writeFile(this.path,{content:dataURL,savetype:'image'})`，即**移动端/桌面端都会原地覆写 PNG**（desktop 走 `file_system.ts:458-461` 的 base64 分支）。
  - 否则走 `Blockbench.export` 保存对话框（无头环境要避免）。
- 因此无头导出 PNG 到任意路径：`Blockbench.writeFile(path, { content: tex.canvas.toDataURL('image/png'), savetype:'image' })`（父目录需存在）。
- 128×128：默认包主贴图 128×128；YSM 官方推荐 128×128（默认模型/文档）。PBR 的 `normal/specular` 应与 `uv` 同尺寸。

### 7.4 UV 与贴图的关系（贴图编辑必须遵守）

- 主模型 172 个 cube 全部 **per-face UV**（`uv`+`uv_size`），贴图坐标 = 像素坐标，范围应在 `[0,texture_width/height]`。
- `up/down` 面在 JSON 里预翻转（§2.5）；Blockbench 内部有 `face.uv` 与 `face.uv_size`，编辑 UV 时应走 Blockbench API（`js/uv/uv.js`），不要在 JSON 层面硬改。
- 校验器应检查：UV 越界（u+uv_size 超出 128）、同贴图内 UV 重叠（可当 warning）、`uv_size=0` 的隐藏面是否被误画（不报错）。

### 7.5 `normal / specular`（PBR）

- YSM 2.5+ 支持 Oculus/Iris PBR；`ysm.json` 只存**路径**；YSM-Utils-Plugins 只负责选择/复制文件，**不导入成 Blockbench 贴图**（`file_import.js:82-99` 只取 `uv`）。
- Blockbench `bedrock` 格式 `pbr: true`，但把 normal/specular 关联成 `TextureGroup`/material 需要额外逻辑（`js/texturing/texture_groups`；插件未用）。**【未验证】**：Blockbench 5.x 中不建 TextureGroup 时 PBR 预览效果（不在本次研究范围）。
- 设计建议：YRL 把 `{uv,normal,specular}` 作为**一个材质的三个文件**管理；绘制默认只改 `uv`，PBR 文件可原样复制或按用户输入生成。

---

## 8. 动态加载与“自研 YRL”边界

### 8.1 如何在运行时确认 ysm-utils 已加载

```js
// Blockbench 4.x / 5.x 通用
const ysmModuleId = 'ysm-utils';                                  // package.json name → BBPlugin.register 的 id
const ysmPlugin   = Plugins.registered[ysmModuleId];              // 本次会话已加载（plugin_loader.ts:34,1078-1106）
const ysmInstalled= Plugins.installed.find(p => p.id === ysmModuleId);   // 已安装（含 disabled 标记，:136-143）
const ysmUiReady  = !!(BarItems['ysm_utils.direct_import']          // Action 构造时写入 BarItems（actions.ts:104-105）
                    && BarItems['ysm_utils.current_info_menu']);
const ysmMenu     = !!(MenuBar && (MenuBar.menus ?? []).find?.(m => (m.id ?? m) === 'ysm_utils'));
// 版本：ysmPlugin?.version（"2.6.0"）；就绪：ysmPlugin && !ysmPlugin.disabled && ysmUiReady
```
- 证据：`src/index.js:9`（注册 id = `packageInfo.name` = `"ysm-utils"`，`package.json:3`）；`js/plugin_loader.ts:17-40,136-143,1078-1106`；`js/interface/actions.ts:104-105,388`。
- 插件是 `await_loading: true`（`src/index.js:18`），Blockbench 会在打开项目前等它加载完（`plugin_loader.ts:1130` 超时设置 `plugin_await_loading_timeout`）；bridge 若依赖它，需自行等 `Plugins.loading_promise`/超时。

### 8.2 是否存在可挂接的事件 / API

**结论：没有。**
- 插件源码中 `Blockbench.on(` / `dispatchEvent(` / `new Property(` / `new Codec(` / `new ModelFormat(` **全部为 0 命中**（对 `src/` grep 结果；唯一 `Project[...]` 赋值是 `ysm_project_info`）。
- 它注册到全局命名空间的“面”只有：`BarItems['ysm_utils.create_default_model' | 'ysm_utils.direct_import' | 'ysm_utils.current_info_menu']`（Action 实例）、`BarMenu("ysm_utils")`、`MolangAutocomplete` 的 3 个命名空间、localStorage 两个键（`cacheYsmFolders`、`cacheYsmImportConfig`），以及 `Project.ysm_project_info`（§4.5）。
- 这些“面”都不提供函数级复用：Action 只能 `trigger()` 打开 UI；MolangAutocomplete 只影响编辑体验；localStorage 只是缓存。

### 8.3 三种复用路线对比

| 路线 | 做法 | 优点 | 缺点/风险 | 建议 |
|---|---|---|---|---|
| **A. 自研 YRL（推荐）** | bridge 内实现 pack 读写/校验/导入/导出；**复制** MIT 的 `loadNormalization`/`saveNormalization`/`getLanguageMap` | 完全可控、无 UI、可用 `Blockbench` 自带 IO 绕过 fs 权限、可固定字节格式 | 需自己维护与上游 2.6.x 的规则差异（加 fixture 回归） | ✅ 主路线（与 ADR-4 一致） |
| **B. vendored 复用** | 把 `load_normalization.js`/`save_normalization.js`/`file_import.js` 等无 Vue 模块复制进 bridge bundle，`dialog` 传 stub | 少写代码、规则与上游同步 | `native_module.js` 在 BB5 会弹 fs 权限；`file_import` 仍会新开项目/依赖全局；`ysm_file_read` 会拖 Vue | ⚠️ 仅 vendored 两个 normalization + 自写编排 |
| **C. 驱动插件 UI** | `BarItems['ysm_utils.direct_import'].trigger()` 等 | 完全复用 | 需要人机交互（原生目录框/Dialog），无法无头 | ❌ 只在“GUI 共存模式”作为可选入口 |

### 8.4 自研 YRL 的最小实现清单（建议 ~400–600 行）

1. **数据模型**：`YsmPack { rootDir, ysmJson, files, textures: Map<ysmName, Texture>, models: Map<key, ModelProject> }`。
2. **规范化（复制 MIT）**：`loadNormalization` / `saveNormalization`（`src/import/load_normalization.js:150`；`save_normalization.js:222`）+ `getLanguageMap`（`util/language.js:41`）。**导出时只调 save，且不要先 load**（避免写回 UI 默认值）。
3. **IO 适配层**（避开原生 fs 权限弹窗）：
   - 读：`Blockbench.readFile([abs], {readtype:'text', errorbox:false})`；图片 `readtype:'image'`。
   - 写：`Blockbench.writeFile(path, {content})`；图片 `{content:dataURL, savetype:'image'}`。
   - **目录创建是唯一硬缺口**：Blockbench 无 mkdir API → 新包骨架必须在宿主侧建目录，或申请 `requireNativeModule("fs")`（BB5 弹一次权限框；可预置 `<userData>/plugin_permissions.json` 的 `{pluginId:{allowed:{fs:true}}}`，见 `native_apis.ts:76-87,121-168`）。
4. **包骨架生成**（照抄 `createAllFiles` 逻辑，`create_default.js:36-111`）：`animations/ avatar/ models/ textures/ textures/gui/ sounds/ functions/ controller/ lang/` + 默认 `main.json/arm.json/…` + 12 个动画 + 1 控制器 + 贴图 + `ysm.json`。素材来源三选一：bridge 内置模板（推荐，打包体积大但离线可靠）、从 vendored `assets/default/` 复制、从用户 YSM 包复制。
5. **导入编排**（§6.3）：模型 → 贴图（含 PBR 文件登记）→ 动画/控制器 → 建映射 → 记录到项目。
6. **保存编排**（§5.3-A）：`export_empty_groups=true` → 模型 `codec.write(compile(), export_path)` → 动画/控制器 `exportFile` → `saveTextures` → ysm.json `saveNormalization`+`writeFile`。
7. **导出编排**（§5.3-B）：`compile({raw:true})` + `compileFile` + `toDataURL` + 固定格式化 writer → `exports/<ts>/` + manifest。
8. **校验器 `profile=ysm`**（喂给 `bb_validate`）：
   - errors：A 级定位组（§2.6）缺失/改名；`spec!=2`；`files.player.model.main` 缺失或文件不存在；贴图文件不存在；动画/控制器引用文件不存在；空组导出设置被关。
   - warnings：B 级层级偏离默认模型；贴图非 128×128（自定义分辨率允许，但默认模型体系是 128）；B 级主动画名缺失；UV 越界/重叠；`height_scale/width_scale` 越界（插件 UI 范围 0.05–2，`properties.vue:144,158`）。
9. **多模型项目路由**：`main`/`arm`/`projectiles[]`/`vehicles[]` 各自一个 ModelProject tab（`loadModelFile` 自动新开）；导出时 `project.select()` 再 `compile`（§5.3 注意）。
10. **lang 管理（可选）**：`getLanguageMap` 生成键模板 + `readLanguageFile/writeLanguageFile` 等价实现（注意 `files.language_path`，别学插件的根级 bug）。
11. **PBR（可选）**：登记 `{uv,normal,specular}`，导出时按原路径复制/或按 canvas 重绘。
12. **GUI 共存（可选）**：启动时探测 §8.1；若已安装 ysm-utils，仅复用其“最近包列表/信息编辑”入口，不参与 YRL 数据流。

### 8.5 动态加载相关风险

- **插件版本差异**：2.6.0 的 `saveNormalization` 不认识 2.6.4 的 `merge_multiline_expr`（不删，安全）；2.6.3 的控制器新语法需要校验器放行。YRL 应对“未知字段”一律保留（白名单删除法，而不是白名单保留法）。
- **其它插件抢占 Codec**：GeckoLib 等插件也注册 `.json` codec（官方 wiki 提醒“无法导入控制器时移除 GeckoLib 插件”）。无头环境应使用干净 profile，或显式 `Codecs.bedrock.load(...)` 绕过 `loadModelFile` 的 codec 遍历。
- **fs 权限弹窗**：BB5 下 `requireNativeModule("fs")` 会弹 Electron 权限框（`native_apis.ts:95-184`），会卡住无头流程 → YRL 尽量不用原生 fs（§8.4-3）。
- **`Project.close` 的未保存确认**：无头收尾要用 `Project.close(true)`/`force` 跳过（`project.ts:528`），否则会弹三选一对话框阻塞。

---

## 附录 A：证据索引（claim → file:line）

| # | 结论 | 证据 |
|---|---|---|
| A1 | spec 2 / metadata / properties / files 结构 | `vendor/YSM-Utils-Plugins/assets/default/ysm.json:1-125`；官方 wiki「项目结构」 |
| A2 | 插件只写 ysm.json | `src/import/open_import_dialog.js:42-46` |
| A3 | 导入资产链（模型→贴图→动画→控制器→project info） | `src/import/file_import.js:9-152` |
| A4 | `loadModelFile` 全局来源 + codec 遍历 | `vendor/blockbench/js/io/io.js:67-108,505-513` |
| A5 | 落在 `bedrock`（entity）format | `js/formats/bedrock/bedrock.js:1258-1271,1555-1597`；`js/interface/setup_settings.js:275` |
| A6 | 项目导出路径/保存记录 | `js/io/codec.ts:159-186,321-327`；`js/formats/bedrock/bedrock.js:1294-1299,1399-1461` |
| A7 | 智能保存顺序（贴图→模型→动画） | `js/io/io.js:378-472` |
| A8 | 动画逐条 merge 保存 | `js/formats/bedrock/bedrock_animation.js:562-717`；`js/animations/animation.js:1029-1058` |
| A9 | 控制器保存 | `js/formats/bedrock/animation_controller_codec.js:74-138`；`js/animations/animation_controllers.js:927-…` |
| A10 | 贴图原地写回 PNG | `js/texturing/textures.js:1640-1726`；`js/file_system.ts:450-497` |
| A11 | 空组导出默认开 | `js/interface/setup_settings.js:329`；`js/formats/bedrock/bedrock.js:991` |
| A12 | Blockbench 插件执行方式（闭包） | `js/plugin_loader.ts:804-815`；`rollup.config.js:8-24`；`src/index.js:1-44` |
| A13 | `Plugins` 注册表/安装表 | `js/plugin_loader.ts:17-40,136-143,1078-1106` |
| A14 | `BarItems` 全局 Action 注册 | `js/interface/actions.ts:104-105,388,511-538` |
| A15 | 原生模块权限门控 | `js/native_apis.ts:34-61,95-184,208-213` |
| A16 | `Project` 持久化范围（无自定义字段） | `js/formats/bbmodel.js:200-238` |
| A17 | `ysm_project_info` 仅内存 | `src/util/project_info_manager.js:1-29`；A16 |
| A18 | 默认模型 64 bones/172 cubes/30 空骨骼 | `assets/default/models/main.json`（PowerShell 解析实测） |
| A19 | bone/cube 字段集合 | 同上（实测 keys：bone=`cubes,name,parent,pivot,rotation`；cube=`origin,pivot,rotation,size,uv`，全 per-face uv） |
| A20 | 贴图尺寸 | `assets/default/textures/*`（System.Drawing 读 IHDR 实测） |
| A21 | 动画名清单/格式 | `assets/default/animations/*.json`（实测）+ 官方 wiki「玩家主动画/轮盘动画/手部条件动画」 |
| A22 | 控制器名清单/格式 | `assets/default/controller/main.animation_controllers.json`；官方 wiki「动画控制器」 |
| A23 | `ctrl.*`/`ysm.*` Molang 清单 | `src/molang/ysm_molang.js:1-533` |
| A24 | 硬编码组名 | 官方 wiki「模型制作」（`ysm.cfpa.team/wiki/tph2yetr/`）；旧版完整指南（`mcmod.cn/post/2955.html`） |
| A25 | 轮盘 `#` 机制/classify/buttons config_forms | 官方 wiki「项目结构」；`src/vue/import/extra_animation*.vue`；`save_normalization.js:89-125` |
| A26 | 默认包贴图名→lang 键 | `assets/default/lang/zh_cn.json`；`src/util/language.js:104-118` |
| A27 | `default_texture` = 无扩展名文件名 | 官方 wiki「项目结构」；`src/vue/import/properties.vue:118-129` |
| A28 | single_texture 渲染选择 | `js/formats/bedrock/bedrock.js:1576`；`js/texturing/textures.js:2220-2238` |
| A29 | 读文件 API | `js/file_system.ts:158-235`；`js/api.ts:314-318` |
| A30 | 多 geometry 导入弹选择框 | `js/formats/bedrock/bedrock.js:1473-1535` |
| A31 | 关闭项目弹未保存确认 | `js/io/project.ts:490-539` |
| A32 | 默认包/项目记忆恢复 | `js/desktop.ts:207-226,317-344`；`bedrock.js:1303-1322` |
| A33 | 语言编辑器 `language_path` 根级 bug | `src/vue/import/language_edit.vue:110-126`；对比 `load_normalization.js:169-171` |

## 附录 B：【未验证】清单（需后续核实）

1. **YSM 运行时源码级硬编码**：`Root/MAllBody/AllBody/UpBody/UpperBody` 层级、`molang` 骨骼、`ViewLocator` 的具体行为是否在 YSM Java 代码中写死（本地无 YSM 源码；官方 wiki 只列了 A 级定位组与 Head/AllHead 行为）。→ 建议：以“默认模型 + 默认动画名”为兼容基线写 warning，不写 error。
2. **`molang` 骨骼名是否必须**：默认模型/动画把变量赋值放在名为 `molang` 的空骨骼上；可能是约定而非硬编码。→ 建议：保留该骨骼名，校验器只提示。
3. **`ysm-utils.js` 构建产物是否真的零导出**：`.gitignore` 排除构建产物，未实测；由 rollup 语义 + 入口无 export + `new Function` 执行方式推定（高置信）。
4. **`arm.json` 是否运行时强制**：spec2 文档把 `model.arm` 与 `model.main` 并列，但插件/默认值允许为空；1.2.0 旧文档称 arm 必需。→ 建议校验器对“缺失 arm”给 warning。
5. **`default_texture` 缺省时的运行时行为**（缺省是否取 `texture[0]`）：文档只说“默认材质名”，未写缺省回退逻辑。
6. **`visible_bounds` 是否参与 YSM 裁剪**：Blockbench 会重算，YSM 是否使用未查。
7. **`/ysm model set` 指令确切参数**：来自社区 wiki 摘录，未逐字核对 2.6 文档。
8. **多贴图重名/子目录**：YSM 用“无扩展名 basename”匹配 `default_texture`，若两张贴图同名不同目录，行为未验证。
9. **PBR 在 Blockbench 无 TextureGroup 时的预览**：未验证（且超出本次范围）。
10. **2.6.4+ `merge_multiline_expr` 的语义细节**：仅见 wiki 一句话。

## 附录 C：参考链接（外部，按可信度排序）

- 官方 wiki（新版，权威）：[项目结构/ysm.json spec](https://yesstevemodel.github.io/wiki/struct/)、[玩家主动画](https://yesstevemodel.github.io/wiki/animation/main/)、[轮盘动画](https://yesstevemodel.github.io/wiki/animation/extra/)、[手部条件动画](https://yesstevemodel.github.io/wiki/animation/condition/arm/)、[动画控制器](https://yesstevemodel.github.io/wiki/controller/)
- 官方 wiki 镜像（同内容、中文站）：[模型制作（含硬编码组名表）](https://ysm.cfpa.team/wiki/tph2yetr/)、[模型格式说明](https://ysm.cfpa.team/wiki/type/)
- 原作者旧版完整指南（部分过时，但硬编码组名/arm 制作/并行动画描述仍有效）：[mcmod.cn/post/2955](https://www.mcmod.cn/post/2955.html)
- YSM 源码/文档仓库（dev 分支，3.0 架构重写，仅作趋势参考）：[YesSteveModel/YesSteveModel](https://github.com/YesSteveModel/YesSteveModel)
- 插件仓库：[TartaricAcid/YSM-Utils-Plugins v2.6.0](https://github.com/TartaricAcid/YSM-Utils-Plugins)（MIT）

## 附录 D：对现有设计文档（`blockbench/docs/01、02、03`）的核对与修正

| 现有表述 | 核对结果 | 建议修改 |
|---|---|---|
| 01-F10：“YSM-Utils 是 UI 型插件，无 Codec/导出 API；核心可复用逻辑是纯函数但被 rollup 打进闭包” | ✅ 正确 | 可补充：**连 bundle 作用域也没有导出**；`createAllFiles` 未 export；`importMainFile` 等虽 export 但打包后不可达 |
| 01-F14：“`Codecs.bedrock.write()`、`Blockbench.writeFile()`、`Action.trigger()` 纯代码不弹窗” | ⚠️ 部分 | `Codecs.bedrock.write()` 在**目标文件存在且非法**时会弹 messagebox；`export_over.trigger()` 在 `export_path` 存在时确实不弹窗，但**内部 async 不会被等待**，且会连带 `saveTextures`（>=2 脏贴图且无路径时弹确认框）。建议写明“只在路径已就绪时安全，需 await 的流程改用 granular API” |
| 02：“`models: main, arm`，`animations: [main,arm,extra,tac,carryon,parcool,swem,slashblade,tlm,fp_arm]`，`controllers: true`” | ✅ 与 `assets/default/ysm.json:62-124` 一致 | 可补 `projectiles[]`/`vehicles[]` 与 `sound_path/function_path/language_path` |
| 03：“模型空间 1 单位=1/16 格；YSM 玩家模型原点在脚底中心，标准身高约 32 单位” | ⚠️ 原点正确；“32 单位”不精确 | 改为“默认 main.json 几何高 43.3 单位（≈2.71 格），`height_scale=0.7` 后 ≈30.3 单位（≈1.89 格）”；校验器用“包围盒 × height_scale”，不要硬编码 32 |
| 03 校验项：“必需骨骼与层级” | 需分级 | 按本报告 §2.6 A/B 级拆分：A 级缺失=error，B 级偏离=warning（避免误杀原创骨骼包） |
| 03：“`bb_save_project` 写回 pack/（模型 JSON、贴图 PNG、动画、ysm.json）” | 方向正确，但**不能依赖 ysm-utils 或 Blockbench 自动保存** | 补 §5.3 的显式调用序列；并写明 `export_empty_groups=true`、`export_path` 绑定、动画 `exportFile` 只存脏项 |
| 01 “导出是幂等的” | 需补前提 | 固定 `settings.json_indentation/minifiedout/final_newline`；动画保存会重排键顺序（`bedrock_animation.js:618-643`），需在导出层重排或接受“语义幂等、字节不幂等” |
| 01 “GUI 模式把 ysm-utils 作为可选项共存” | 可行 | 用 §8.1 探测；注意其 BB5 fs 权限弹窗与 `await_loading` |
