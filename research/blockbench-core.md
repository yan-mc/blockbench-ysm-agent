# Blockbench 核心机制研究报告（无头建模/贴图 Agent 插件系统设计依据）

- 研究对象：`F:\Deepseek_harness\blockbench\vendor\blockbench`，**Blockbench v5.2.2**（`package.json:5`），Electron `^43.4.0`（`package.json:171`）、three.js `^0.129.0`（`package.json:185`）、Vue `2.7.16`（`package.json:191`）。
- 入口：`package.json:16` `"main": "electron/main.js"`；渲染进程入口 `index.html:74` `<script type="module" src="dist/bundle.js">`（源码入口 `js/main.ts`）。
- 全部结论均以本仓库源码行号为依据；标【未验证】的条目表示仅凭本仓库源码无法确证，需实机/GUI 验证。
- 本报告只覆盖 Blockbench 侧事实，不涉及 YSM 格式与 dsh 侧实现。

---

## 0. 结论速览（给设计决策用）

| # | 结论 | 关键证据 |
|---|---|---|
| 1 | 主进程写死 `show:false` → `loadURL` → `.finally(()=>win.show())`，没有任何"不开窗"开关；`--userData <dir>` 可完全隔离用户数据/插件目录 | `electron/main.js:22-29`, `69`, `174-176` |
| 2 | 窗口 `webPreferences` **没有** `backgroundThrottling`、`offscreen`、`paintWhenInitiallyHidden` 等无头相关项；只有 `webgl/webSecurity/nodeIntegration/contextIsolation:false/enableRemoteModule` | `electron/main.js:77-83` |
| 3 | 启动即 `animate()`（rAF 主循环）；未聚焦且 `settings.background_rendering=false` 时直接 return；默认 `background_rendering=true` | `js/boot_loader.js:64`、`js/preview/preview.ts:2551-2554`、`js/interface/setup_settings.js:137` |
| 4 | 渲染器 `preserveDrawingBuffer: true` + `alpha: true` + `setClearColor(0x000000, 0)` ⇒ 默认透明背景，任何时刻可 `canvas.toDataURL()` 读像素 | `js/preview/preview.ts:397-402`, `436` |
| 5 | 内置两个 offscreen Preview（`MediaPreview`、`Screencam.NoAAPreview`）：不挂 DOM、`resize(w,h)` 可指定任意分辨率、可离屏渲染后取 PNG | `js/preview/preview.ts:2542-2543`, `503-548` |
| 6 | `Screencam.advancedScreenshot(preview, options, cb)` 是"指定机位+分辨率+抗锯齿→PNG dataURL"的官方内部路径，`cb` 存在时**不弹任何 UI** | `js/preview/screenshot.js:279-353`, `388-393` |
| 7 | 已安装插件列表在 `localStorage` 的 `StateMemory.installed_plugins`；`source:'file'` 的插件会按绝对路径在启动时自动加载（`fs.existsSync` 存在即加载，无需复制到 plugins 目录） | `js/plugin_loader.ts:112-113`, `1240-1246`, `659-675` |
| 8 | 但 `loadInstalledPlugins()` 先 `await Plugins.loading_promise`——即访问 `cdn.jsdelivr.net`/`blckbn.ch` 的插件仓库 JSON，默认超时 10s；离网/慢网会拖慢启动 | `js/plugin_loader.ts:40`, `1133-1179`, `1188-1191` |
| 9 | `boot_loader` 用 `plugin_await_loading_timeout`（默认 **2s**）兜底触发 `app-loaded`，所以"app-loaded 时插件一定已加载"**不成立** | `js/boot_loader.js:158-176`, `js/plugin_loader.ts:1129-1132` |
| 10 | 贴图改像素后必须走 `Texture.updateChangesAfterEdit()`（或 `Painter.edit()`），它负责 `map.needsUpdate`、img 刷新、`saved=false`、layer 合并；撤销用 `Undo.initEdit({textures:[t], bitmap:true})` | `js/texturing/textures.js:1851-1871`、`js/texturing/painter.js:18-51` |
| 11 | 套接字级"要不要弹窗"的分界：`Codec.compile()` 纯函数可直调；`Codec.export()`/`Blockbench.exportFile()` 会 `showSaveDialogSync` 阻塞；`window.confirm/alert` 被 Electron **同步原生模态框**覆盖 | `js/io/codec.ts:198-257`, `js/file_system.ts:359-437`, `js/desktop.ts:139-156` |
| 12 | 网络副作用集中在：插件仓库 JSON/更新信息、插件下载统计、启动屏 news.json、新装/复访埋点 POST、自动更新（仅非 dev 模式） | `js/plugin_loader.ts:1133-1186`, `js/interface/start_screen.ts:632-636`, `js/boot_loader.js:104-125`, `electron/main.js:273-327` |

---

## 1. 启动链路与自定义 bridge 插件的注入

### 1.1 主进程：窗口参数、单实例锁、`--userData`、show 时序

**结论**：`createWindow()` 是唯一的窗口构造点；窗口创建后**必定** `show()`；单实例锁在 `createWindow()` 内部获取（不是模块顶层）；`--userData` 在 `app.setPath('userData')` 之前读取，决定整个用户目录（settings、插件、备份、缩略图）。

证据：

```js
// electron/main.js:22-29  --userData，必须在 app ready 之前
const index = process.argv.findIndex(arg => arg === '--userData');
if (index !== -1) { app.setPath('userData', process.argv[index + 1]); }

// electron/main.js:62-65  单实例锁写在 createWindow 里
if (app.requestSingleInstanceLock && !app.requestSingleInstanceLock()) { app.quit(); return; }

// electron/main.js:67-84  窗口参数（注意：无 backgroundThrottling / offscreen / paintWhenInitiallyHidden）
let win_options = {
  icon: 'icon.ico', show: false, backgroundColor: '#21252b',
  frame: native_frame, titleBarStyle: native_frame ? 'default' : 'hidden',
  minWidth: 640, minHeight: 480, width: 1080, height: 720,
  webPreferences: { webgl: true, webSecurity: true, nodeIntegration: true,
                    contextIsolation: false, enableRemoteModule: true }
};

// electron/main.js:166 / 174-176
if (options.maximize !== false) win.maximize()
win.loadURL(url_path).finally(() => { win.show(); });
```

其它相关事实：

- GPU 开关在模块层就 `appendSwitch`：`ignore-gpu-blacklist`、`ignore-gpu-blocklist`、`enable-accelerated-video`（`electron/main.js:187-189`）。
- `launch_settings.json` 里 `hardware_acceleration === false` 时：`app.disableHardwareAcceleration()`；**非 win32** 额外 `enable-unsafe-swiftshader`（`electron/main.js:32-59`）。Windows 上不追加该 flag，Software 路径需自行加。
- `app.on('ready')` → `createWindow()`；`ipcMain.on('app-loaded')` 触发自动更新检查（仅 `dev_mode === false`，即打包版；`dev_mode` 通过 `process.execPath` 是否匹配 `node_modules/electron` 判断）（`electron/main.js:273-328`）。
- 渲染层 `ipcRenderer.send('app-loaded')` 只发一次，位置在 `boot_loader` 的 `proceed()` 里（`js/boot_loader.js:167`）。

**对设计的含义**：
1. 想"不开窗又渲染"，**必须改主进程**（把 `.finally(()=>win.show())` 去掉，并补 `backgroundThrottling:false`），这是最小侵入改动点，且不影响渲染链路。
2. `--userData` 给了我们天然的"agent 独立 profile"：settings/localStorage/plugins 全隔离，多个 agent 实例互不污染；配合单实例锁（每个 userData 目录各自一把锁）可以并行多实例。
3. 打包版会自动更新：agent 发行版应固定版本，避免 `autoUpdater` 在后台改二进制（见 §6）。

### 1.2 渲染进程启动顺序

`js/main.ts` 是纯 import 清单（137 行），顺序即执行顺序，关键次序：

- `js/main.ts:29` `api`（定义 `Blockbench` 对象）→ `:47` `undo` → `:70` `preview/preview` → `:72-73` `screenshot`/`canvas` → `:88-96` texturing → `:110` `plugin_loader` → `:111-115` `io/*` → `:119-135` `formats/*` → **`:136` `boot_loader`** → `:137` `globals`。
- `js/main.ts:23` 先 `state_memory`，`:28` `misc`（`isApp`、`guid`、`BarItems` 等全局基建）、`:30` `modes`、`:32` `vue_components`。
- 因此：**插件/格式注册表（`Formats`、`Codecs`）在 `boot_loader` 之前已就绪**，启动插件可以直接 `Formats.xxx`。

`js/boot_loader.js` 关键行：

```js
// 54-64：先建 Preview / Canvas / 菜单，然后启动 rAF 主循环
setupPreviews()
initCanvas()
...
animate()

// 158-176：插件加载与 app-loaded
loadInstalledPlugins().then(proceed);
let timeout = ExperimentalSettings.get('plugin_await_loading_timeout') ?? 2;
setTimeout(proceed, timeout * 1000);
...
// 178：进入启动屏
setStartScreen(true);
// 188：Blockbench.setup_successful = true
```

- `setupPreviews()` 会创建 `MediaPreview`、`Screencam.NoAAPreview`（`offscreen:true`）和 `main_preview`（`fullscreen()`）（`js/preview/preview.ts:2508-2548`）。
- `initCanvas()` 建 `Canvas.scene`、灯光、Transformer、网格（`js/preview/canvas.js:904-1074`）。
- `setStartScreen(true)` 显示启动屏；`setStartScreen` 定义在 `js/io/project.ts:889-892`。

### 1.3 `Plugins` 对象、`Plugins.path`、`installed`、`loadInstalledPlugins` 时序

**核心符号**（`js/plugin_loader.ts`）：

```ts
export const Plugins = {
  installed: [] as PluginInstallation[],   // :26  "哪个插件装着"（持久化到 localStorage）
  all: [] as Plugin[],                     // :33  所有已知 Plugin 实例（含商店未安装）
  registered: {} as Record<string, Plugin>,// :34  id → 预注册实例（插件文件运行时用）
  path: '',                                // :41  插件文件目录
  api_path: settings.cdn_mirror.value ? 'https://blckbn.ch/cdn/plugins'
           : 'https://cdn.jsdelivr.net/gh/JannisX11/blockbench-plugins/plugins', // :40
  loading_promise: null as null|Promise<void>, // :36 插件仓库 JSON 的加载 Promise
  currently_loading: '',                   // :35
}
```

- `StateMemory.init('installed_plugins','array')` + 过滤非对象条目（`:112-113`）。持久化键为 `localStorage["StateMemory.installed_plugins"]`（`js/util/state_memory.ts:6,36-39`）。
- `Plugins.path`：app 模式为 `app.getPath('userData') + osfs + 'plugins' + osfs`，并尝试 `mkdir`（`:1114-1120`）；web 模式为插件 CDN 路径（`:1121-1123`）。
- `PluginInstallation` 结构（`:136-143`）：`{id, version, path, source:'store'|'file'|'url', dependencies?, disabled?}`。

`loadInstalledPlugins()`（`:1188-1347`）时序：

1. `await Plugins.loading_promise`（`:1189-1191`）——**这一步会等 `$.ajax` 插件仓库 `.json`，超时 `plugin_load_timeout` 默认 10s**（`:1125-1179`）。
2. 若在线，按仓库 JSON 为每个插件 `new Plugin(id, json[id])`，再 `Plugins.sort()`（`:1197-1202`）。
3. 依赖排序（`resolveDependencies`，`:1207-1235`）。
4. 逐个 `loadPlugin(installation)`（`:1239-1328`）：
   - `source === 'file'`：`isApp && fs.existsSync(installation.path)` → `new Plugin(id,{disabled}).loadFromFile({path,name,content:''}, false)`；**文件不存在则直接从 installed 列表移除**（`:1240-1254`）。
   - `source === 'url'`：`loadFromURL`（`:1256-1265`）。
   - 在线 + `store`：版本比对后 `plugin.load(false)`；`update_available && allow_updates` 时走 `download()`，**只有 `plugin.await_loading === true` 才把该 promise 放进 `install_promises`**（`:1267-1319`）。
   - 离线 + `store`：仍 `plugin.load(false)`（`:1320-1324`）。
5. `StateMemory.save('installed_plugins')`（`:1339`）。
6. `await Promise.allSettled(install_promises)` 后打印 "All plugin installations resolved"（`:1342-1346`）。

`await_loading` 的语义（重要，容易误解）：

- 字段定义在 `PluginOptions`：`await_loading?: boolean`，注释是 "Set to true if the plugin must finish loading before a project is opened, i. e. because it adds a format"（`:186-189`）。
- 但**在 5.2.2 里它只影响"商店插件有可用更新、走 download 时是否等待"**（`:1282-1284`、`:1300-1302`）；`source:'file'`/`'url'` 的加载**总是**被 await（`:1244`、`:1260`、`:1290-1291`）。
- 而整个 `loadInstalledPlugins()` 又被 `boot_loader` 的 **2s 兜底**抢跑（`js/boot_loader.js:174-175`），所以 `app-loaded` 事件**不保证**插件已加载完。

插件文件执行方式（无模块系统、无 await）：

```ts
// :775-803
async #runPluginFile(path) { file_content = fs.readFileSync(path,{encoding:'utf-8'}); this.#runCode(file_content); return file_content; }
// :804-815
#runCode(code) {
  const func = new Function('requireNativeModule','require', code + `\n//# sourceURL=PLUGINS/(Plugin):${this.id}.js`);
  const scoped_require = isApp ? getPluginScopedRequire(this) : undefined;
  func(scoped_require, scoped_require);
}
```

插件注册与 `disabled` 语义：

```ts
// :1078-1106  Plugin.register(id, data)
var plugin = Plugins.registered[id];
if (!plugin) { plugin = Plugins.registered.unknown; ... }
plugin.extend(data);
if (plugin.isInstallable() == true && plugin.disabled == false) { plugin.runOnLoad(); }
```

- `loadPlugin` 的 file 分支先 `new Plugin(id, {disabled: installation.disabled})`（`:1243`），`Plugin` 构造里 `Merge.boolean(this,data,'disabled')`（`:331`，字段声明 `:281`）→ 插件 JS 顶层代码**仍会执行**，但 `onload()` 不会跑。这就是"禁用但文件仍在"的机制。
- `toggleDisabled()` 运行时不改文件，只 `unload()/runOnLoad()` 并 `#remember()`（`:816-829`）。

### 1.4 让自定义 bridge 插件启动时自动加载：3 种可编程注入路线

#### 路线 A（推荐，产品化）：主进程 patch + `webContents.executeJavaScript` 引导

不依赖 localStorage，也不怕仓库网络卡顿；只需在 `webContents` 上执行一次脚本：

```js
// 伪代码：在我们自己的 electron/main.js（fork）里，loadURL 之后
const bridgePath = path.join(BRIDGE_ROOT, 'bb-bridge.js');
win.webContents.once('did-finish-load', () => {
  win.webContents.executeJavaScript(`
    new Plugin().loadFromFile(${JSON.stringify({path: bridgePath, name: 'bb-bridge.js', content: ''})}, false)
  `);
});
```

依据：`Plugin` 是全局类（`js/globals.js:44`、`js/plugin_loader.ts:2249`）；`loadFromFile(file, first=false)` 在 app 模式读文件并执行（`:548-585`），`first=false` 时**不会**触发 `confirm()`（`:551-557`），执行完会 `#remember()` 把自己写进 `Plugins.installed` + `StateMemory.save`（`:582-584`、`:659-675`）——即**首次注入后，下次启动会自动按 `source:'file'` 加载**。

注意：
- 时机必须晚于 `boot_loader` 加载（`did-finish-load` 通常早于 `setup_successful`）。更稳的是从主进程监听 `app-loaded` IPC 再注入，或在渲染层轮询 `window.Blockbench?.setup_successful`（置 true 于 `js/boot_loader.js:188`）；插件之间可以用 `Blockbench.on('loaded_plugin', ...)`（`js/plugin_loader.ts:424`）协调先后。
- bridge 插件若要注册 Format/Codec，必须**在项目打开前**完成（`await_loading` 的真实用途）；若我们的 agent 自己控制"何时开项目"，其实无碍。

#### 路线 B（零源码改动）：`--userData` 预置 + 一次性注册

1. 启动参数加 `--userData F:\...\bb-agent-profile`（`electron/main.js:22-29` 生效）。
2. 插件文件放 `F:\...\bb-agent-profile\plugins\bb-bridge.js`（`Plugins.path` 规则，`:1115`）。
3. 首次用 CDP/`executeJavaScript` 执行一次：
   ```js
   StateMemory.installed_plugins.push({id:'bb-bridge', path:'F:/.../bb-bridge.js', source:'file'});
   StateMemory.save('installed_plugins');
   ```
   （条目结构见 `:136-143`；`source:'file'` 分支见 `:1240-1246`。也可以直接 `new Plugin().loadFromFile({path,...}, true)` 让它自己 `#remember()`，但 `first=true` 会弹原生 `confirm`，见 `js/desktop.ts:139-149`。）
4. 之后每次启动由 `loadInstalledPlugins()` 自动加载（仍需等 §1.3 的网络等待）。

风险：localStorage 存在 `<userData>/Local Storage/leveldb`，**不能可靠地离线预写**，必须至少成功跑一次；多实例同时写同一 userData 有竞争。

#### 路线 C（最省事、最"agent 友好"）：用 Chromium 远程调试端口跑 CDP

启动参数 `--remote-debugging-port=<port>`，外部 agent 用 CDP `Runtime.evaluate` 在渲染进程里执行任意 JS（包括 `new Plugin().loadFromFile(...)`、`newProject(...)`、`Texture...`、`Screencam...`）。优点：**完全不改 vendor 源码**、无需预置状态、可同步拿返回值（`awaitPromise:true`）、可随时断言。缺点：需确认目标发行版允许该 Chromium switch【未验证：Electron 43 打包版是否保留 `--remote-debugging-port`；通常保留，但部分发布配置会剥离】。

> 结论：设计上把 "bridge 插件"做成**独立 JS 文件 + 两条装载通道**（A/B 持久化自启；C 作为调试/首装通道）最稳。不要把"插件已被安装"当作启动即可用的前提。

---

## 2. 程序化项目 API（全局暴露面）

### 2.1 全局符号表（`window` 上可见）

| 符号 | 暴露方式 | 证据 | 备注 |
|---|---|---|---|
| `Blockbench` | `Object.assign(window,{LastVersion,Blockbench,isApp})` | `js/api.ts:354-363` | 主命名空间 |
| `Project` | `Object.defineProperty(window,'Project',{get})` → `Blockbench.Project` | `js/io/project.ts:687-691`、`js/api.ts:306` | 当前项目或 `0`；**只读引用** |
| `Format` | 同上，getter → `Blockbench.Format` | `js/io/format.ts:65-69` | 当前格式 |
| `Undo` | `Object.defineProperty(window,'Undo',{get})` → `Blockbench.Project?.undo` | `js/undo.js:1139-1143`、`js/api.ts:307-309` | **每项目一个 `UndoSystem`**，无项目时为 `undefined` |
| `Formats` | `export const Formats: Record<string,ModelFormat>`，`new ModelFormat()` 自动注册 | `js/io/format.ts:63,368` | `Formats.bedrock`、`Formats.bedrock_block`、`Formats.free`… |
| `Codecs` | `export const Codecs: Record<string,Codec>`，`new Codec()` 自动注册 | `js/io/codec.ts:110-113,386` | `Codecs.project`、`Codecs.bedrock`、`Codecs.image`… |
| `ModelProject` / `ProjectData` | `Object.assign(window, global)` | `js/io/project.ts:1489-1522` | `ModelProject.all` 全部标签页 |
| `Cube` `Group` `Texture` `Mesh` `Locator` `NullObject` `TextureMesh` `SplineMesh` … | 各模块 `Object.assign(window, global)` | `js/globals.js:1-81`（`Blockbench.*` 兼容别名） | 直接 `new Cube()` 可用 |
| `Animator` `Animation` `Keyframe` `BoneAnimator` `Timeline` … | 同上 | `js/globals.js:24-35` | |
| `Preview` / `main_preview` / `MediaPreview` / `DefaultCameraPresets` | `const global = {main_preview, DefaultCameraPresets, Preview, ...}` 末尾 `Object.assign(window, global)` | `js/preview/preview.ts:2877-2900, 2927`；`js/globals.js:45` | |
| `Screencam` | 声明 `export const Screencam = {...}`，末尾 `Object.assign(window,{...,Screencam})` | `js/preview/screenshot.js:121`、`:924-926` | |
| `StateMemory` `Settings` `settings` `Interface` `Panels` `BarItems` `Action` `Dialog` … | 各自 `Object.assign(window, global)` | 见各文件尾部 | |
| `newProject` `setupProject` `selectNoProject` `setStartScreen` `showUnsavedWorkDialog` | `Object.assign(window, global)` | `js/io/project.ts:1489-1521` | |
| `loadModelFile` `loadImages` | `Object.assign(window, global)` | `js/io/io.js:505-513` | |
| `Plugin` / `BBPlugin` | `globals.js:44`、`plugin_loader.ts:1111,2249` | | `Plugin.register` 静态方法 |

`Blockbench` 上与我们相关的成员（`js/api.ts:304-321`）：

```ts
Format: 0 as (ModelFormat|number)
Project: 0 as (ModelProject|number)
get Undo() { return Blockbench.Project instanceof ModelProject ? Blockbench.Project.undo : undefined }
import/importFile/pickDirectory/read/readFile/export/exportFile/writeFile/findFileFromContent/addDragHandler
```

### 2.2 从零建一个 Bedrock entity 项目（最小路径，纯代码）

Bedrock entity 格式 id = `'bedrock'`，codec id = `'bedrock'`（`js/formats/bedrock/bedrock.js:1258`、`:1555-1597`）；方块格式 id = `'bedrock_block'`（`:1602`）。**`newProject` 不弹任何对话框**：

```js
// js/io/project.ts:738-754
export function newProject(format: ModelFormat | string): boolean {
  if (typeof format == 'string') format = Formats[format] ?? Formats.free;
  let project = new ModelProject({format});
  project.select();                                   // ← 触发 setStartScreen(!Project)、UI 切到工作区
  Preview.selected.loadAnglePreset(DefaultCameraPresets[0]);
  if (format.edit_mode) { /* 切 edit 模式 */ }
  if (typeof Format.onSetup == 'function') Format.onSetup(Project, true);  // bedrock: 建 BedrockEntityManager
  Blockbench.dispatchEvent('new_project', {project});
  return true;
}
```

最小完整脚本（在渲染进程上下文执行）：

```js
// 1) 建项目（bedrock entity）
newProject(Formats.bedrock);
Project.name = 'demo';
Project.geometry_name = 'demo';        // codec.compile 里用 Project.geometry_name 生成 identifier
Project.texture_width = 16;            // 若用默认 16 可省
Project.texture_height = 16;

// 2) 骨骼（Bedrock 的 group 即 bone；Format.bone_rig 时默认名 'bone'）
const bone = new Group({name: 'root', origin: [0, 0, 0]}).init();   // init(): Project.groups.push + preview setup
// 嵌套：new Group({name:'child'}).addTo(bone).init();

// 3) 立方体（挂在骨骼下）
const cube = new Cube({
  from: [-2, 0, -2], to: [2, 4, 2],
  origin: [0, 0, 0], uv_offset: [0, 0]
}).addTo(bone).init();                  // .addTo() 再 .init()，与内置 add_cube 的写法一致
if (!cube.box_uv) cube.mapAutoUV();

// 4) 贴图（先建项目再 new Texture，因为构造里读 Project.texture_width）
const tex = new Texture({name: 'skin'});
await new Promise(r => { tex.img.onload = r; tex.img.src = 'data:image/png;base64,...'; });
tex.add(false);                         // push 到 Project.textures + 事件 + single_texture 时 updateAllFaces
tex.select();                           // Texture.selected = tex（多贴图项目的"当前贴图"）
// 单贴图格式下把面绑到贴图：
for (const f in cube.faces) cube.faces[f].texture = tex.uuid;
Canvas.updateAllFaces();
```

要点与证据：

- `new Cube(data, uuid)`：`from/to` 默认 `[0,0,0]`/`[size,size,size]`，`size` 取 `settings.default_cube_size`（默认 2）；`box_uv` 继承 `Project.box_uv`；构造后需 `.init()`（`js/outliner/types/cube.js:137-176,249-259`）。
- `.init()` 语义：`OutlinerNode.init()` 把节点挂到 `Outliner.root`（`js/outliner/abstract/outliner_node.ts:46-52`），`OutlinerElement.init()` 再 `Project.elements.safePush(this)` 并建 preview（`js/outliner/abstract/outliner_element.ts:29-36`）；`Group.init()` 推 `Project.groups`（`js/outliner/types/group.js:58-66`）。
- `.addTo(target)` 会先 `removeFromParent()` 再插入目标 `children`/root（`js/outliner/abstract/outliner_node.ts:96-139`）。
- 内置 `add_cube` 动作的标准写法可直接照抄（含 undo/group/autoUV/单贴图绑定/收尾 `Undo.finishEdit`）：`js/outliner/types/cube.js:1617-1673`；`add_group` 动作为 `js/outliner/types/group.js:720-764`（`new Group({...}).init()` 后把选中项 `addTo` 进去），`group_elements` 为 `:765-800`。
- `Cube.all`/`Group.all`/`Texture.all` 都是"当前项目"过滤后的 getter（`js/outliner/abstract/outliner_element.ts:290-298`、`js/outliner/types/group.js:535-570`、`js/texturing/textures.js` 中 `Texture.all` 相关定义）。

### 2.3 保存 / 导出 API

| 需求 | 纯代码调用 | 是否弹窗 | 证据 |
|---|---|---|---|
| 生成 bbmodel JSON | `Codecs.project.compile()` | 否 | `js/formats/bbmodel.js:101`；`js/io/codec.ts:198-201` |
| 写 bbmodel 到指定路径 | `Codecs.project.write(content, path)` | **否**（`write()` 直写磁盘） | `js/io/codec.ts:321-327`；`js/formats/bbmodel.js:873-886`（`save_project` 就是 `codec.write(codec.compile(), Project.save_path)`） |
| 生成 bedrock geometry JSON | `Codecs.bedrock.compile(options?)` | 否 | `js/formats/bedrock/bedrock.js:1324+` |
| 写 bedrock JSON | `Codecs.bedrock.write(content, path)` | 否 | `js/io/codec.ts:321-327` |
| 导出后置状态（`Project.export_path`、`saved=true`、最近项目） | `codec.afterSave(path)` / `afterDownload(path)` | 否 | `js/io/codec.ts:330-362` |
| 弹保存对话框 | `codec.export()` / `Blockbench.export()` / `Blockbench.exportFile()` | **是**（`showSaveDialogSync`） | `js/io/codec.ts:242-257`；`js/file_system.ts:359-437` |
| 写任意内容/PNG | `Blockbench.writeFile(path, {content, savetype})` | 否 | `js/file_system.ts:450-497`；`savetype:'image'` 支持 `data:image/...` base64 直写（`:458-470`） |
| 读文件 | `Blockbench.readFile(paths, options, cb)` | 否（app 模式直接同步读后回调） | `js/file_system.ts:158-230`；`Blockbench.readFile` 绑定见 `js/api.ts:315` |
| 打开模型文件 | `loadModelFile(fileResult, args?)` | 取决于 codec | `js/io/io.js:67-108`；`FileResult={name,path,content}` |
| 关闭/新建标签页 | `Project.close(force?)`、`newProject(fmt)`、`setupProject(fmt)` | `close()` 在未保存时会弹"未保存"对话框 | `js/io/project.ts:489-528,716-754` |
| 导出贴图文件 | `saveTextures(lazy?)`（内部函数，返回 Promise） | 可能弹目录选择 | `js/texturing/textures.js:2284+` |

补充：

- `Project` **没有** `save()` 方法；"保存"是 Action：`BarItems.save_project.trigger()`（`js/formats/bbmodel.js:873-886`）、`BarItems.export_over.trigger()`（`js/io/io.js:378-439`）。`export_over` 的"智能保存"逻辑会按 `Project.save_path`/`export_path` 决定写入还是弹窗，并在 `settings.dialog_save_codec=true` 时弹 codec 选择器（`js/io/io.js:396-431`）——**agent 不要用这个**。
- 让工程处于"已保存"状态以便关窗不弹框：`Project.saved = true`（setter 见 `js/io/project.ts:228-241`），或 `Blockbench.addFlag('allow_closing')`（`js/desktop.ts:683-703`）。
- `Codec.compile` 依赖 `Project.geometry_name`（bedrock）、`Project.export_options[codec.id]`（`js/io/codec.ts:143-151`），无 UI 时用 `codec.getExportOptions()` 的默认值即可。

**设计含义**：agent 的 `save_project` / `export_model` 必须走 **`compile()` + `write()`**（或 `Blockbench.writeFile`），不要 `export()`；返回路径由我们传入，天然可确定、可校验。

---

## 3. 预览 / 渲染 / 截图

### 3.1 `Preview` 类与 renderer 生命周期

核心字段与构造（`js/preview/preview.ts:219-499`）：

```ts
export class Preview {
  id: string
  canvas: HTMLCanvasElement          // 自建 canvas，挂在 this.node 内
  node: HTMLElement                   // div.preview
  width: number; height: number
  isOrtho: boolean
  camPers: THREE.PerspectiveCamera    // fov=settings.fov, near=settings.camera_near_plane, far=30000 (:340)
  camOrtho: THREE.OrthographicCamera & {axis, backgroundHandle}   // :342-345
  renderer: THREE.WebGLRenderer
  controls: OrbitControls
  offscreen?: boolean                 // :337
  static selected: Preview            // :1926
  static all: Preview[]               // :1930

  constructor(options: {id: string, antialias?: boolean, offscreen?: boolean}) // :211-215
  render(): void                      // :734-759
  resize(width?: number, height?: number): this   // :503-548
  loadAnglePreset(preset: AnglePreset): this       // :874-909
  setProjectionMode(orthographic: boolean, toggle?: boolean): this // :764-790
  copyView(preview: Preview): void    // :1848-1869
  screenshot(options, callback)       // :1873-1875 → Screencam.screenshotPreview
  fullscreen(): this                  // :1876-1904
}
```

WebGLRenderer 参数（关键）：

```ts
// js/preview/preview.ts:397-402
this.renderer = new THREE.WebGLRenderer({
  canvas: this.canvas,
  antialias: typeof options.antialias == 'boolean' ? options.antialias : Settings.get('antialiasing'),
  alpha: true,
  preserveDrawingBuffer: true
});
// :436-437
this.renderer.setClearColor(0x000000, 0);
this.renderer.setSize(500, 400);
```

`render()` 只做 `controls.update()` + `renderer.render(Canvas.scene, this.camera)`（ortho 且有 cube 背景时两段渲染），最后 `css_renderer.render(...)`（`:734-759`）。

**`resize()` 的坑（必须记住）**：

```ts
// :503-548
if (this.canvas.isConnected && this !== MediaPreview) {
  this.height = this.node.parentElement.clientHeight;   // 已挂 DOM 的 preview 忽略参数，跟父容器走
  this.width  = this.node.parentElement.clientWidth;
} else if (height && width) { this.height = height; this.width = width; }  // 离屏才有自定义分辨率
else { return this; }
...
this.renderer.setSize(this.width, this.height);
if (this.canvas.isConnected) this.renderer.setPixelRatio(window.devicePixelRatio);
```

⇒ **要精确控制输出分辨率，必须用未挂 DOM 的 Preview（`MediaPreview` / `Screencam.NoAAPreview` / 自己 `new Preview({id, offscreen:true})`）**；`main_preview` 的画面尺寸由窗口决定。

### 3.2 默认机位预设 `DefaultCameraPresets`（`js/preview/preview.ts:85-209`）

| id | 投影 | position / target | 其它 | 行号 |
|---|---|---|---|---|
| `initial` | perspective | position 依 `Format.forward_direction`：`+x:[40,32,-40]`、`-x:[-40,32,40]`、`+z:[40,32,40]`、`-z(默认):[-40,32,-40]`，再乘 `Format.block_size/16`；target=`[0, block_size*0.75, 0]` | `default:true` | 86-106 |
| `top` | orthographic | `[0,512,0]` → `[0,0,0]`，`zoom:.5` | `locked_angle:'top'` | 107-117 |
| `bottom` | orthographic | `[0,-512,0]`，`zoom:.5` | `locked_angle:'bottom'` | 118-128 |
| `south` | orthographic | `[0,0,512]`，`zoom:.5` | `locked_angle:'south'` | 129-139 |
| `north` | orthographic | `[0,0,-512]`，`zoom:.5` | `locked_angle:'north'` | 140-150 |
| `east` | orthographic | `[512,0,0]`，`zoom:.5` | `locked_angle:'east'` | 151-161 |
| `west` | orthographic | `[-512,0,0]`，`zoom:.5` | `locked_angle:'west'` | 162-172 |
| `isometric_right` | orthographic | `[-512, 512*0.8165+8, -512]` → `[0,8,0]`，`zoom:.5` | 常用 45° 视角 | 173-181 |
| `isometric_left` | orthographic | `[512, 512*0.8165+8, -512]` → `[0,8,0]` | | 182-190 |
| `true_isometric_right` | orthographic | `[-512, 512+8, -512]` → `[0,8,0]` | 真等轴测 | 191-199 |
| `true_isometric_left` | orthographic | `[512, 512+8, -512]` → `[0,8,0]` | | 200-208 |

补充：`loadAnglePreset` 同时处理 projection、zoom、fov/focal_length、`setLockedAngle`（`:874-909`）；`setLockedAngle` 里 `'south'/'north'/'east'/'west'/'top'/'bottom'` 会设 `camOrtho.axis` 与背景轴（`:800-868`）。用户自定义机位存 `localStorage['camera_presets']`（`js/preview/screenshot.js:173-183`）。

### 3.3 Canvas / 场景生命周期

- `Canvas` 是单例对象（`js/preview/canvas.js:38+`），`Canvas.scene` 在模块层 `new THREE.Scene()`（`:35`）并在 `initCanvas()` 里加 `outlines`、`Transformer`、`SplineGizmos`、灯光、网格、地面（`:904-1074`）。
- `Canvas.withoutGizmos(cb)`：截图前隐藏 gizmo/网格/选中轮廓/`hide_in_screenshot` 元素，回调后恢复（`canvas.js:455-499`）。
- `Canvas.updateView({elements, element_aspects})`：局部刷新 transform/geometry/faces/uv/visibility（`canvas.js:517-555`）；全量用 `Canvas.updateAllFaces()`（`:609+`）、`Canvas.updateAll()`（`:582+`）、`Canvas.updateAllUVs()`。
- 渲染循环：`animate()` 用 `requestAnimationFrame`，**先**排下一帧，再判 `settings.background_rendering` / `document.hasFocus()` / `#preview:hover`，再按 `settings.fps_limit`（默认 144）限速；然后 `TickUpdates.Run()`，再对 `Preview.all` 中 `canvas.isConnected` 的 preview 调 `render()`（`preview.ts:2551-2583`）。
  - ⇒ **离屏 Preview 永远不会被主循环渲染**（`isConnected === false`），必须手动 `render()`；这正是官方截图路径的做法。
  - ⇒ 窗口失焦且 `background_rendering=false` 时整条渲染链停摆；默认 `background_rendering=true`（`js/interface/setup_settings.js:137`），所以**失焦**通常没问题，**隐藏/最小化**才是问题（见 §4）。
- `js/preview/canvas.js` 的 `Canvas` 不是 DOM canvas，而是"场景/材质/更新函数"聚合器；真正的 canvas 在 `Preview.canvas`。

### 3.4 `Screencam` 能力（`js/preview/screenshot.js`）

```ts
export const Screencam = {
  NoAAPreview: Preview|null,          // :122   offscreen + antialias:false（setupPreviews 中创建）
  screenshotPreview(preview, options, cb): void,   // :224-278
  advancedScreenshot(preview=Preview.selected, options=0, cb): Promise<void>, // :279-353
  fullScreen(options, cb): void,      // :354-373 —— 用 currentwindow.capturePage()
  screenshot2DEditor(options, cb): void, // :374-387
  returnScreenshot(dataUrl, cb, blob): Promise<void>, // :388-461
  cleanCanvas(options, cb), createGif(options, cb), recordTimelapse(options), stopTimelapse()
}
```

`advancedScreenshot` 支持的能力（全部无 UI，显式传 options 即可）：

| 能力 | option | 实现证据 |
|---|---|---|
| 分辨率（任意，甚至大于窗口） | `resolution: [w,h]` | `render_viewport.resize(w*sample, h*sample)`（`:299`） |
| 机位 | `angle_preset: 'view' \| 预设id \| '_<index>'`（`_0`=自定义机位数组下标） | `:291-298` |
| 缩放 | `zoom`（透视走 `setFocalLength`，正交走 `zoom`） | `:301-308` |
| 抗锯齿 | `anti_aliasing: 'off'\|'msaa'\|'ssaa'`（msaa→`MediaPreview`，其它→`NoAAPreview`，ssaa=4x 超采样+1px 模糊） | `:288-290, 314-338` |
| 阴影/明暗 | `shading: boolean`（临时切换 `settings.shading`） | `:284-287, 344-346` |
| 是否含 gizmo | `show_gizmos: boolean`（默认经 `Canvas.withoutGizmos`） | `:348-352` |
| 输出 | `cb(dataURL)`；**cb 存在时不弹任何 UI**（`returnScreenshot` 立即回调，`:388-393`） | `:388-393` |

`screenshotPreview` 的能力：`options.crop=false` 去掉自动裁剪；`options.width/height` 按比例内缩居中（`:229-276`）；内部同样先 `preview.render()`（`:227`）。

`fullScreen` 用 `currentwindow.capturePage()`（Electron API）抓**窗口**（`:354-373`），包含 UI/对齐窗口像素，不适合做资产图。

背景透明度：`renderer.setClearColor(0x000000, 0)` + `alpha:true`（`preview.ts:436,400`），且 `Canvas.scene.background` 默认为 `null`（仅当激活 `PreviewScene` 才设为 cubemap，`js/preview/preview_scenes.ts:183-198`）⇒ **默认输出 PNG 自带 alpha**。若要白底，需自行合成（`CanvasFrame`/2D canvas）或临时设 `Canvas.scene.background = new THREE.Color(...)`。

### 3.5 "代码触发一次指定机位渲染并输出 PNG"的最短可靠路径

**路径 1（最省事，官方内部函数；推荐）**

```js
const preview = Preview.selected;   // 或 main_preview
Screencam.advancedScreenshot(preview, {
  angle_preset: 'south',            // 或 'initial' / 'isometric_right' / '_0'(自定义)
  resolution: [1024, 1024],
  zoom: 42,                          // 可选；省略用当前 fov
  anti_aliasing: 'msaa',
  show_gizmos: false,
  shading: settings.shading.value
}, (dataUrl) => {
  Blockbench.writeFile('C:/out/model_south.png', {content: dataUrl, savetype: 'image'});
});
```

依据：`advancedScreenshot`（`js/preview/screenshot.js:279-353`）+ `writeFile` 的 image 分支（`js/file_system.ts:450-470`）——**全程无对话框**。官方自己也这么干：`updateRecentProjectThumbnail()` 就是 `MediaPreview.resize(270,150)` → `loadAnglePreset(...)` → `screenshot({crop:false}, url => Blockbench.writeFile(...))`（`js/desktop.ts:260-291`）。

**路径 2（最可控，自己管 renderer）**

```js
const p = MediaPreview;                     // offscreen，可任意分辨率
p.loadAnglePreset(DefaultCameraPresets.find(x => x.id === 'north'));
p.resize(2048, 2048);                       // 离屏分支生效
p.render();                                 // 手动渲染一帧（主循环不管离屏 preview）
const dataUrl = p.canvas.toDataURL('image/png');
Blockbench.writeFile('C:/out/north.png', {content: dataUrl, savetype: 'image'});
```

**像素读取注意点（three.js/WebGL）**

- Blockbench 的 renderer **已经** `preserveDrawingBuffer: true`（`preview.ts:401`），因此 `canvas.toDataURL()` 在**任意时刻**（不必同帧）都能拿到上一帧内容，不会像默认 WebGL 那样得到空白。这消除了头号坑。
- 但仍建议"`render()` 后立刻 `toDataURL()`"，避免同一 canvas 被下一帧覆盖；且 `toDataURL` 是同步的，中间不要 `await`。
- 若走 `Electron webContents.capturePage()`（`win.capturePage`），窗口必须"可见/被捕获计数 > 0"，官方文档要求隐藏窗口场景传 `{stayHidden:true}`；Blockbench 自己的 `fullScreen()` 是 `setTimeout(...,40)` 后 `capturePage()`（`screenshot.js:354-357`），属于"窗口可见"路线。
- 若自己 `new Preview()`：注意 `new Preview()` 会 `Preview.all.push(this)`（`preview.ts:497`），且构造函数里访问 `Preview.selected`/`Canvas.global_light_color` 等，必须在 `setupPreviews()` 之后（即 `boot_loader` 运行后）才能创建。
- `antialias` 是 renderer 构造参数（`preview.ts:399`），建后不可改；要改抗锯齿用 `Screencam.NoAAPreview` 或 ssaa 后处理。

---

## 4. 隐藏窗口下 WebGL 渲染的可行性

### 4.1 Electron 侧硬事实（官方文档）

- `webPreferences.backgroundThrottling`（默认 `true`）："Whether to throttle animations and timers when the page becomes background. This also affects the Page Visibility API. **When at least one webContents displayed in a single browserWindow has disabled backgroundThrottling then frames will be drawn and swapped for the whole window**." — [Electron WebPreferences](https://www.electronjs.org/docs/latest/api/structures/web-preferences)
- Page Visibility 规则（[Electron BrowserWindow](https://www.electronjs.org/docs/latest/api/browser-window)）：
  - 所有平台：`hidden` 追踪窗口是否被隐藏/最小化；macOS 额外追踪遮挡。
  - **`show:false` 创建时，初始 visibilityState 是 `visible`（尽管实际隐藏）**。
  - **`backgroundThrottling` 关闭时，即使窗口被最小化/遮挡/隐藏，visibilityState 也保持 `visible`**。
- `paintWhenInitiallyHidden`（BrowserWindow 构造项，默认 `true`）："Whether the renderer should be active when `show` is false and it has just been created… Setting this to false will cause the `ready-to-show` event to not fire." — 官方文档镜像 [browser-window-options.md](https://github.com/Hawthorne001/electron/blob/main/docs/api/structures/browser-window-options.md)；`ready-to-show` 文档也说"using this event implies that the renderer will be considered visible and paint even though show is false"（同上 BrowserWindow 文档）。
- 离屏渲染（[Offscreen Rendering](https://www.electronjs.org/docs/latest/tutorial/offscreen-rendering)）：`webPreferences.offscreen: true` 有两种模式——GPU 加速（`useSharedTexture` 或 CPU 共享位图，支持 WebGL/3D CSS）与 Software output device（需 `app.disableHardwareAcceleration()`）；离屏窗口**总是无边框**；用 `webContents.on('paint',(e,dirty,image)=>image.toPNG())` 取帧，`webContents.setFrameRate(n)`；"When nothing is happening on a webpage, no frames are generated"。
- `win.capturePage([rect,opts])`：页面"可见"的定义是"窗口隐藏但 capture 计数非 0"；隐藏捕获要传 `{stayHidden:true, stayAwake:true}`（BrowserWindow 文档）。
- 隐藏/最小化窗口里 rAF 会被 Chromium 暂停是公认行为（社区证据：Chromium catapult 提交注释 "When the document is hidden, it is possible that the browser stops triggering the rAF callbacks"；以及 Electron 项目里 "Chromium pauses rAF for a renderer it considers hidden… backgroundThrottling:false and process-level switches cover blurred and occluded cases, but not a minimized window" 的实践记录【社区，非官方文档】）。

### 4.2 Blockbench 自身对无头的友好/不友好点

**友好**：
- `animate()` 先排下一帧再 return（`preview.ts:2552`），所以即使某帧被跳过，循环仍在。
- `background_rendering` 默认 `true`（`js/interface/setup_settings.js:137`）⇒ 失焦（`document.hasFocus()===false`）时仍渲染；只有 `background_rendering=false` 才会因失焦停摆（`js/preview/preview.ts:2553`、`js/interface/interface.js:391`）。
- 离屏 Preview 尺寸完全由代码控制（`preview.ts:521-523`），`setPixelRatio` 只在挂 DOM 时应用（`:541-546`）⇒ 输出分辨率 = `resize(w,h)` 的像素数。
- `preserveDrawingBuffer:true`（`preview.ts:401`）⇒ 不依赖"同帧读取"。
- 所有渲染与截图逻辑都是 renderer 进程内同步代码，可被 `executeJavaScript` 直接驱动。

**不友好**：
- 主进程硬编码 `win.show()`（`electron/main.js:174-176`），且 `maximize()`（`:166`）会顺带显示窗口；没有 CLI 开关。
- 窗口参数**没有** `backgroundThrottling:false`、`offscreen`、`paintWhenInitiallyHidden`（`electron/main.js:77-83`）。
- `Preview.resize()` 对挂 DOM 的 preview 强制跟父容器（`preview.ts:504-506`）⇒ 即使隐藏窗口也需要真实布局尺寸（隐藏窗口仍有布局，但 `clientWidth/Height` 取决于窗口大小；`show:false` 的窗口在首次 show 前尺寸可能为 0 或默认值【未验证具体表现】）。
- 无头场景里 `document.hasFocus()` 必然 false，所以**必须**保证 `settings.background_rendering` 为 true（默认即 true）。

### 4.3 可落地方案排序（含风险）

| 优先级 | 方案 | 做法 | 风险 |
|---|---|---|---|
| **A（首选）** | **隐藏窗口 + 保持"visible"语义 + 手动 `render()`** | 主进程 patch：去掉 `win.show()`/`maximize()`；`webPreferences.backgroundThrottling:false`；保持 `paintWhenInitiallyHidden` 默认 true；永不 `win.hide()`（创建即隐藏）；渲染全部走 `MediaPreview`/`NoAAPreview` + `toDataURL` | 需改 `electron/main.js`（一行）；`main_preview` 尺寸可能为 0（但我们不用它出图）；`show:false` 窗口的 GPU 初始化在极少数驱动上失败【未验证】 |
| **B（推荐并行验证）** | **OSR（`webPreferences.offscreen:true`）** | 用 Electron 官方离屏渲染：窗口无边框、不需要显示器；GPU 模式支持 WebGL；仍可用 `toDataURL`（Blockbench renderer 自己有 `preserveDrawingBuffer`），或订阅 `paint` 事件拿 `NativeImage` | OSR 与 `@electron/remote`/`currentwindow` 等 API 可能冲突【未验证】；OSR 窗口"nothing happening → no frames"，但我们是主动 render，不受影响；`offscreen` 下 `win.capturePage` 行为不同 |
| **C** | **透明/不遮挡窗口** | `show:true` 但 `win.setOpacity(0)` / `setIgnoreMouseEvents` / 放到屏幕外 (`setPosition(-10000,-10000)`) / `setContentProtection` | 仍占用桌面焦点与 GPU；`setOpacity(0)` 在部分平台会被 DWM 优化掉渲染；屏幕外窗口在 Windows 仍可能被判定可见（可渲染），但会被"窗口不在任何显示器"影响【未验证】；不优雅 |
| **D** | **Windows 虚拟桌面/独立 session** | 用 `CreateDesktop`/Windows Sandbox/独立 RDP session 跑可见窗口 | 工程复杂度高；CI 里常见做法是 `xvfb`（Linux）或 `RDP`（Windows），Windows 无官方 xvfb 等价物；可行但重 |
| **E** | **Linux xvfb** | `xvfb-run -s "-screen 0 1920x1080x24" npm run electron -- --userData ...` | 只在 Linux；无 GPU 时需 `--disable-gpu`/SwiftShader（Blockbench 已有非 win32 的 `enable-unsafe-swiftshader`，`main.js:54-59`）；软件 WebGL 慢但可用 |
| **F（兜底）** | **纯 CPU/离屏 Canvas 路径** | 不依赖窗口：`MediaPreview` + `renderer.readRenderTargetPixels`/`readPixels` + 自己编码 PNG；或直接 `CanvasFrame` 2D 合成 | 需要自己写 PNG 编码（`CanvasFrame.toDataURL` 已封装）；ortho 相机可行，但等价于 A 的离屏部分，仍需要 GPU 上下文 |

**推荐组合**：A（改 main.js 三行：不 show、`backgroundThrottling:false`、`offscreen` 可选开）+ 所有出图统一走 `MediaPreview`/`Screencam`（不依赖窗口可见性）；CI/Linux 再叠加 E；**不要**依赖"最小化窗口"或 `paintWhenInitiallyHidden:false`（后者会让 renderer 初始不激活，`ready-to-show` 永不触发，反而更糟）。

补充验证清单（实机）：
1. `show:false` + `backgroundThrottling:false` 时，`document.visibilityState` 与 `requestAnimationFrame` 是否持续（用 `executeJavaScript` 每 100ms 记 `performance.now()`/rAF 计数）。
2. 同一状态下 `MediaPreview.resize(2048,2048); render(); toDataURL()` 是否出非空 PNG（检查 alpha 与像素直方图）。
3. 无 GPU（`--disable-gpu`）时 WebGL 是否回落 SwiftShader、`getContext('webgl2')` 是否成功。

---

## 5. 纹理 API（像素写入 / 刷新 / 撤销 / 多贴图）

### 5.1 `Texture` 结构

```ts
// js/texturing/textures.js:16-95（构造）
export class Texture {
  // 逻辑属性（Property 注册表 :2239-2265）：path/name/folder/namespace/id/group/scope/
  //   width/height/uv_width/uv_height/particle/use_as_default/layers_enabled/
  //   sync_to_project/file_format/render_mode/render_sides/wrap_mode/pbr_channel/fps/...
  img: HTMLImageElement          // :32/:67  用于 2D 显示 / 缩略 / 导出 source
  width: number; height: number  // 逻辑像素尺寸（onload 时同步）
  canvas: HTMLCanvasElement      // :64-65  16x16 起步，像素真源
  ctx: CanvasRenderingContext2D  // :66  {willReadFrequently:true}
  layers: TextureLayerItem[]     // :39     像素图层（layers_enabled）
  layers_enabled: boolean        // :40
  selected_layer: TextureLayerItem|null
  internal: boolean              // :42     是否内部位图（非链接文件）
  source: string                 // :24     当前位图的 dataURL / 路径
  material: THREE.ShaderMaterial // :77-94  uniforms.map = new THREE.Texture(canvas)，NearestFilter
  uv_width / uv_height           // 与 Project 分辨率解耦（per_texture_uv_size）
  uuid
  saved: boolean
  // 方法：load(:390) fromFile(:444) fromPath(:468) fromDataURL(:651) updateSource(:710)
  //       updateMaterial(:718) refresh(:775) select(:894) add(:950) remove(:986)
  //       getDataURL(:1798) convertToInternal(:1808) updateLayerChanges(:1814)
  //       updateChangesAfterEdit(:1851) updateImageFromCanvas(:1868) getActiveCanvas(:1872)
}
```

要点：
- 材质绑定的是 **`this.canvas`**（`new THREE.Texture(this.canvas)`，`:71`），不是 `img`；因此**直接画 canvas 就能影响 3D**，只需让 three 重传纹理。
- `img` 是 `assets/missing.png` 起手（`:67-69`），在 `img.onload` 里同步 `width/height`、必要时重建 texture、把 `img` 画进 `canvas`（`:99-130`）。⇒ 新建贴图后 `width/height` 在图片加载完成前是 0，**要 await 一次 `img.onload`**。
- `Texture.all`/`Texture.selected`/`Texture.getDefault()`：
  - `Texture.selected = this`（`select()` 内，`:918`）；`Texture.getDefault()` 优先 `use_as_default` → `Texture.selected` → 第一个可见（`:2220-2238`）。
  - 多贴图项目里"当前贴图"就是 `Texture.selected`/`Texture.getDefault()`；单贴图格式下 cube 面通过 `face.texture = tex.uuid` 绑定（`cube.js:251-256`、`io/io.js:138-158`）。

### 5.2 改像素后如何正确刷新（这是最容易漏的一步）

**官方约定：所有修改必须走 `Painter.edit()` 或手动等价序列**。

```js
// js/texturing/painter.js:18-51（节选）
edit(texture, callback, options) {
  if (!options.no_undo && !options.no_undo_init) Undo.initEdit({textures:[texture], bitmap:true});
  if (!texture.internal) texture.convertToInternal();
  let {canvas, ctx, offset} = texture.getActiveCanvas();   // 有 layer 时返回当前 layer
  callback(canvas, Painter.current);
  Blockbench.dispatchEvent('edit_texture', {texture, options, canvas, ctx, offset});
  if (options.use_cache && options.no_update === true) return;
  if (options.no_undo && options.use_cache) { texture.updateLayerChanges(); texture.getOwnMaterial().map.needsUpdate = true; UVEditor.vue.updateTextureCanvas(); }
  else { texture.updateChangesAfterEdit(); if (!options.no_undo && !options.no_undo_finish) Undo.finishEdit(edit_name); }
}
```

`updateChangesAfterEdit()` 到底做什么（`textures.js:1851-1867`）：

```js
updateChangesAfterEdit() {
  if (this.layers_enabled) { this.updateLayerChanges(true); }        // 合成所有 layer 到 canvas，map.needsUpdate=true
  else {
    if (!this.internal) this.convertToInternal();
    if (!Format.image_editor) this.getOwnMaterial().map.needsUpdate = true;   // ← 3D 刷新关键
    this.source = this.canvas.toDataURL('image/png', 1);
    this.updateImageFromCanvas();                                    // ← img.src = source；2D 面板/UV 覆盖层
  }
  if (pbr_channel 是 mer/height && 材质视图) this.getGroup().updateMaterial();
  this.saved = false;                                                // 贴图自身脏标记
  this.syncToOtherProject();
}
```

`updateMaterial()` 也会 `mat.map.needsUpdate = true`（`:718-739`），但**不更新 source/img**；`updateLayerChanges(true)` 负责"layer → 主 canvas"合成并置 `needsUpdate`（`:1814-1850`）。

⇒ 只画 canvas 不调用上面任何方法时，**3D 预览不会更新**（three 不会自动重传 canvas）。这是设计里最容易踩的 bug。

### 5.3 Undo 集成

- `Undo` 是"当前项目的 `UndoSystem`"（`js/undo.js:1139-1143`），`initEdit(aspects, amended=false)` / `finishEdit(message, aspects)`（`:17-100`）。
- **位图**编辑的 aspects 是 `{textures: [tex], bitmap: true}`（配合 `layers` 时用 `addTextureOrLayer`）；官方调用点：`painter.js:20,2685,2757`、`textures.js:1520,1538,2107,2192`、`edit_image.js` 全篇、`texture_flipbook.js:719`。
- `finishEdit` 会把 `Project.saved = false`（`:92-94`，除非 `aspects.keep_saved`），并 `push` 历史、裁剪 `settings.undo_limit`（`:65-75`）。
- `Undo.initEdit` 的合法 aspects 全表见 `types/custom/undo.d.ts:2-42`：`selection / elements / outliner / groups / group / collections / textures / texture_order / texture_groups / selected_texture / bitmap / layers / settings / uv_mode / animations / animation_controllers / keyframes / display_slots / exploded_view / mirror_modeling / uv_only`。
- `Undo.finishEdit` 里 `Project.EditSession` 会同步协作（可忽略）。

### 5.4 `draw_pixel` / `fill_rect` 的正确实现要点（可直接落地）

```js
function bb_edit_texture(tex, drawFn, label = 'Agent edit texture') {
  // 1. 选层：有图层则用当前 layer 的 canvas/ctx（getActiveCanvas 与官方一致）
  const active = tex.getActiveCanvas();          // Texture.getActiveCanvas(): textures.js:1872
  const canvas = active.canvas, ctx = active.ctx, offset = active.offset ?? [0, 0];

  // 2. undo：位图 + 贴图对象；图层时补 layers
  Undo.initEdit({textures: [tex], bitmap: true, ...(tex.layers_enabled ? {layers: [tex.selected_layer]} : {})});

  // 3. 画（坐标要考虑 offset；ctx 是 2D context，clearRect/fillRect 直接可用）
  if (!tex.internal) tex.convertToInternal();    // 链接贴图必须先转内部，否则改动会丢/被文件覆盖
  drawFn(ctx, offset, canvas);

  // 4. 刷新：3D 材质 + source + img + saved + layer 合成
  tex.updateChangesAfterEdit();

  // 5. 收尾 undo（同一次调用内必须配对）
  Undo.finishEdit(label, {textures: [tex]});
}

// draw_pixel(x,y,#rrggbbaa)
bb_edit_texture(tex, (ctx, off) => {
  ctx.fillStyle = '#ff0000ff';
  ctx.fillRect(x + off[0], y + off[1], 1, 1);    // 像素 = 1x1 fillRect
}, 'Agent draw_pixel');

// fill_rect(x,y,w,h,color)
bb_edit_texture(tex, (ctx, off) => {
  ctx.fillStyle = color;
  ctx.fillRect(x + off[0], y + off[1], w, h);
}, 'Agent fill_rect');
```

要点补充：
- **缩放/`canvas.width`**：若贴图为空（`width===0`），先 `await new Promise(r => tex.img.onload = r)` 或直接 `tex.width = tex.height = size; tex.canvas.width = tex.canvas.height = size;`，否则 `ctx` 尺寸是 16×16 占位。
- **不要用 `ctx.getImageData/putImageData` 绕开 `updateChangesAfterEdit`**：仍要调用刷新（`source`/`img` 不会自动同步）。
- **批量修改**应合并到一次 `initEdit...finishEdit`（避免 undo 爆炸）；跨多张贴图的原子操作可以用 `textures: [a,b]`。
- **图层**：`layers_enabled` 时主 canvas 只是合成结果，直接写主 canvas 会在下次 `updateLayerChanges()` 被覆盖；必须写 `tex.getActiveCanvas()`（即当前 layer）。
- **撤销后的 UI/渲染**：`UndoSystem.loadSave()`（`js/undo.js:274`）在恢复贴图时会 `convertToInternal/updateLayerChanges(true)/updateSource/load` 并 `Canvas.updateAllFaces()`（`js/undo.js:610-652`），一般无需手工 `render()`；但如果我们的 bridge 在 undo 后立即截图，建议显式再渲染一帧以防时序问题。
- **单贴图格式的 UV 原点**：本报告不展开 UV 映射细节；`Cube.mapAutoUV()`/`Texture.apply()` 是官方入口（`js/texturing/textures.js:1058-1096`）；bedrock 加载后会把首张贴图自动套到所有 cube（`js/formats/bedrock/bedrock.js:1305-1311`）。

---

## 6. UI / 网络干扰：agent 模式下如何静默

### 6.1 启动屏（start_screen）

- `boot_loader` 末尾 `setStartScreen(true)`（`js/boot_loader.js:178`），切到 `#start_screen`；`project.select()` 里 `setStartScreen(!Project)`（`js/io/project.ts:403`）⇒ **一旦 `newProject()/setupProject()` 成功，启动屏自动消失**（`setStartScreen` 实现：`project.ts:889-892`）。
- 启动屏内容副作用：`$.ajax('https://web.blockbench.net/content/news.json')`（`js/interface/start_screen.ts:632-636`）、Discord/Bluesky 广告区块（`:639-682`，受 `settings.classroom_mode`/`startup_count` 控制）、首启 quick setup（`:685+`）、`addStartScreenSection` 系列。
- **跳过方式**：agent 启动后立即 `newProject(Formats.bedrock)`（或加载项目）；如需连启动屏都不渲染，`setStartScreen(false)` 也可直接调（全局函数）。`settings.always_show_splash_art`/`classroom_mode` 可减少广告区块（`setup_settings.js:20,53`）。

### 6.2 对话框 / 原生模态（最大的"卡死"风险）

`js/desktop.ts` 覆盖了 `window.confirm` / `window.alert` 为 **Electron 同步原生模态框**：

```ts
// js/desktop.ts:139-156
window.confirm = function(message, title) {
  let index = electron.dialog.showMessageBoxSync(currentwindow, { ... buttons:[ok, cancel] });
  return index == 0;
}
window.alert = function(message, title) { electron.dialog.showMessageBoxSync(...) }
```

⇒ 任何走到 `confirm()` 的代码都会**阻塞整个 renderer 进程**，直到有人点按钮。已知高危路径：

| 路径 | 触发条件 | 证据 |
|---|---|---|
| `new Plugin().loadFromFile(file, first=true)` | 手动"从文件安装插件" | `js/plugin_loader.ts:551-557`（`confirm(tl('message.load_plugin_app'))`） |
| `Plugin.loadFromURL(url, first=true)` | 从 URL 安装 | `:604-611` |
| `Plugin.install()`（商店安装）/依赖安装 | 安装/更新商店插件 | `:354-386`、`:426-477` |
| `Project.close()` 未保存 | 关标签页 | `js/io/project.ts:489-528` → `showUnsavedWorkDialog`（`:801-870`） |
| 退出应用且有未保存项目 | `window.onbeforeunload` | `js/desktop.ts:677-704` |
| `Blockbench.showMessageBox` | 大量错误/提示路径（依赖、更新、codec 选择器等） | `js/api.ts:170-211` |
| `export_over` 的 codec 选择器 | `settings.dialog_save_codec=true` 且无 save_path | `js/io/io.js:396-431` |
| 各 `settings.dialog_*` 提示 | 大立方体/旋转限制/纹理目录/非法字符等 | `js/interface/setup_settings.js:295-301` |

**规避原则**：
1. agent 只调用 **`compile()` + `write()` / `writeFile()`**，永不 `export()` / `exportFile()` / `Action.trigger()`。
2. 插件装载走 `loadFromFile(..., first=false)`（不弹 confirm）或直接用 `executeJavaScript` 注入代码。
3. 关闭/退出前把 `Project.saved = true`，或调 `Blockbench.addFlag('allow_closing')` 跳过 `onbeforeunload` 的未保存拦截（`desktop.ts:683-703`）。
4. 若必须调用可能弹框的 API，可临时替换 `window.confirm/alert`（在 renderer 里覆盖为返回固定值）——**注意这会改变用户 GUI 行为，仅 agent profile 使用**。
5. `Blockbench.showMessageBox(options, cb)` 是异步回调式，不会阻塞 JS 线程，但会阻塞"等待用户"的流程；agent 路径里要判断 `Dialog.open`/等待 callback 超时。

### 6.3 网络请求清单与静默策略

| 请求 | 触发点 | 频次 | 证据 |
|---|---|---|---|
| `https://cdn.jsdelivr.net/gh/JannisX11/blockbench-plugins/plugins.json`（或 `blckbn.ch/cdn/plugins.json`，取决于 `settings.cdn_mirror`） | `Plugins.loading_promise`，模块加载即发，**阻塞 `loadInstalledPlugins`** | 每次启动 | `js/plugin_loader.ts:40,1133-1179` |
| `https://cdn.jsdelivr.net/gh/JannisX11/blockbench-plugins/updates.json` | 上一个成功后串行发 | 每次启动 | `:1146-1158` |
| `https://blckbn.ch/api/stats/plugins?weeks=2` | `$.getJSON` | 每次启动 | `:1181-1186` |
| `https://web.blockbench.net/content/news.json` | 启动屏模块加载即发 | 每次启动 | `js/interface/start_screen.ts:632-636` |
| `https://blckbn.ch/api/event/new_installation` / `recurring_user` | `startup_count==1` / `==3` | 首启/第 3 次 | `js/boot_loader.js:104-125` |
| 商店插件安装统计 `install_plugin` | 安装插件时 | 偶发 | `js/plugin_loader.ts:485-496`（注释：`register()`） |
| 商店插件详情/更新（GitHub API commits、about.md、changelog.json） | 打开插件详情/更新检查 | 偶发 | `:866-995` |
| electron-updater `checkForUpdates()` | `app-loaded` 且非 dev 模式 | 每次启动 | `electron/main.js:293-326` |
| 加载带纹理/模型的远程 URL、`share` 上传 | 用户操作 | 偶发 | `js/io/io.js:370`（share 下载）等 |

**静默策略（按侵入性排序）**：

1. **profile 级设置**（写进 `<userData>` 的 `localStorage['settings']` / `launch_settings.json`）：
   - `settings.automatic_updates.value = false`（`setup_settings.js:307`）——但主进程仍会 `checkForUpdates()`（`electron/main.js:325`），只是在 renderer 侧不自动下载；要彻底不检查必须改 main 或离线。
   - `settings.automatic_plugin_updates.value = false`（`:309`）——避免启动时 `plugin.download()`。
   - `settings.classroom_mode.value = true`（`setup_settings.js:20`）——可减少启动屏广告区块（`start_screen.ts:643,657,671`）。
   - `settings.cdn_mirror.value` 切换 CDN 源（`plugin_loader.ts:40`）。
2. **hosts/DNS 黑洞 + 代理**：把 `blckbn.ch`、`web.blockbench.net`、`cdn.jsdelivr.net` 指向 127.0.0.1（离线 profile）。效果：插件仓库请求快速失败 ⇒ `Plugins.loading_promise` 立即 resolve（`error` 分支 `:1160-1173`），启动不再被 10s 拖住；自动更新检查报错但被 `catch`（`main.js:325`）。
3. **启动参数**：`--userData` 隔离 profile；如需更强，`app.commandLine.appendSwitch` 级别的东西（`disable-background-networking` 等 Chromium flag）只能从 main 侧加——vendor 主进程未加，需我们 fork【未验证这些 flag 是否能完全阻止 electron-updater】。
4. **代码级短路**：在 bridge 插件里提前 `Plugins.loading_promise = null`（在 `boot_loader` 之前？不行，插件在 boot_loader 之后加载）——只能在 `executeJavaScript` 阶段（`did-finish-load` 早于 `boot_loader`）设置 `window.Plugins.loading_promise = null` 之类，属于 hack，不推荐；更干净的是离线。
5. **关闭启动埋点**：`startup_count==1/3` 的 POST 有 try/catch（`boot_loader.js:104-125`），离线无害。

**对设计的含义**：agent profile 应默认 **离线/白名单网络**，并显式关闭 `automatic_updates`、`automatic_plugin_updates`；bridge 插件必须是 `source:'file'`（本地文件）而不是从商店安装，避免启动强依赖网络。

---

## 7. 官方 Plugin API / 类型文件（可作为设计契约）

### 7.1 本仓库的类型资产

- `types/index.d.ts`（2 行）：
  ```
  /// <reference types="./custom/blockbench"/>
  /// <reference types="./generated/main"/>
  ```
  ⇒ 类型分两部分：手写 `types/custom/*.d.ts`（老 JS 文件的全局声明） + 由 `npm run generate-types`（`package.json:153`：`tsc --project tsconfig.json && node ./scripts/convert_types.js`）从 TS 源码生成的 `types/generated/main`。
- **注意：本仓库里 `types/generated/` 不存在**（只在发布 npm 包 `blockbench-types@5.2.1` 里，`types/package.json:2-6`）。所以本地只有 `types/custom/` 的签名可用；完整 `Preview`/`Project` 等生成类型需要 `npm i blockbench-types` 或跑 `generate-types`（需要依赖，本任务不安装）。
- 官方文档：`blockbench.net/wiki`（插件教程/Plugin API 页）与 typedoc 站点（`typedoc.json` 配置生成）；仓库 `types/custom/documentation.md` 只是占位（933 字节）。

### 7.2 可直接引用的官方签名（来自 `types/custom/`）

```ts
// types/custom/undo.d.ts:127-212
declare class UndoSystem {
  initEdit(aspects: UndoAspects, amended?: boolean): UndoEntry
  finishEdit(action: string, aspects?: UndoAspects): UndoEntry
  cancelEdit(revert_changes?: boolean): void
  undo(remote?: boolean): void; redo(remote?: boolean): void
  amendEdit(form: InputFormConfig, callback): void
  loadSave(save: UndoSave, reference: UndoSave, mode?: 'session'): void
  history: UndoEntry[]; index: number; current_save?: UndoSave
}
declare let Undo: UndoSystem   // 每项目

// types/custom/screencam.d.ts:2-71
interface ScreenshotOptions { crop?: boolean; width?: number; height?: number }
type ScreenshotReturn = (dataURL: string) => void
declare namespace Screencam {
  let NoAAPreview: Preview
  function screenshotPreview(preview: Preview, options: ScreenshotOptions, cb: ScreenshotReturn): void
  function fullScreen(options: ScreenshotOptions, cb: ScreenshotReturn): void
  function screenshot2DEditor(options: ScreenshotOptions, cb: ScreenshotReturn): void
  function returnScreenshot(dataUrl: any, cb: ScreenshotReturn, blob: any): void
  function cleanCanvas(options: any, cb: ScreenshotReturn): void
  function createGif(options: RecordGIFOptions, cb: ScreenshotReturn): void
  function recordTimelapse(options: RecordTimelapseOptions): void
  function stopTimelapse(): void
}
// 注意：advancedScreenshot 未进 d.ts（内部方法），但 5.2.2 源码可调（js/preview/screenshot.js:279）

// types/custom/textures.d.ts:255-384（关键子集）
updateSource(dataUrl: string): this
updateMaterial(): this
select(event?: Event): this
add(undo?: boolean, uv_size_from_resolution?: boolean): Texture
getDataURL(): string
updateLayerChanges(update_data_url?: boolean): void
updateChangesAfterEdit(): void
updateImageFromCanvas(): void
getActiveCanvas(): any            // 有 layer 返回 layer，否则返回 texture
static getDefault(): Texture

// types/custom/io.d.ts
function loadModelFile(file: any, args?: any): void
```

插件注册的官方写法（`Plugin.register` 与 `PluginOptions` 的完整字段见 `js/plugin_loader.ts:154-244`）：

```js
Plugin.register('my_bridge', {
  title: 'Agent Bridge',
  author: 'us',
  description: '...',
  icon: 'icon-blockbench_file',
  variant: 'desktop',        // 'both' | 'desktop' | 'web'
  min_version: '5.2.0',
  await_loading: true,       // 若注册 Format/Codec，语义上应设 true（但见 §1.3 的实现局限）
  onload() { /* 注册 Action / 监听事件 / 暴露 window.__bridge */ },
  onunload() { /* 清理 */ }
});
```

补充：`Blockbench.on/once/dispatchEvent`（`js/api.ts:286-297`、`:262-285`）是官方事件总线；已验证存在的事件名包括 `'loaded_plugin'`（`js/plugin_loader.ts:424`）、`'setup_project'`（`js/io/project.ts:734`）、`'new_project'`（`:752`）、`'render_frame'`（每帧，`js/preview/preview.ts:2582`）、`'finished_edit'`（`js/undo.js:95`）、`'select_texture'`（`js/texturing/textures.js:946`）、`'add_cube'`（`js/outliner/types/cube.js:1664`）、`'add_group'`（`js/outliner/types/group.js:761`）、`'update_project_resolution'`（`js/io/project.ts:886`）。**没有**名为 `app-ready` 的事件（已核实），启动就绪请用 `Blockbench.setup_successful`。

### 7.3 与官方文档的交叉核对（web）

- Electron 侧（官方文档，已验证）：`backgroundThrottling`、Page Visibility、`paintWhenInitiallyHidden`、`capturePage(stayHidden)`、Offscreen Rendering 语义——见 §4.1 链接。
- Blockbench 插件 API：`Plugin.register` 的字段与 `PluginOptions` 一致（第三方教程/模板引用，如 [jasonjgardner 的 blockbench-mcp SKILL](https://github.com/tomevault-io/tomes/blob/main/jasonjgardner--blockbench-mcp-project/skills/blockbench-development/SKILL.md) 给出的模板 `Plugin.register('my_plugin', { title, author, ..., onload(){...} })` 与本仓库 `js/plugin_loader.ts:154-244,1078-1106` 完全一致）。**官方 wiki 的版本可能滞后于 5.2.2，以本仓库类型/源码为准。**

---

## 8. 未验证项清单（需实机/GUI 才能确认）

1. `show:false` + `backgroundThrottling:false` 下，Electron 43 的 WebGL 帧是否稳定产出（不同 GPU/驱动）；`document.visibilityState` 是否为 `visible`。
2. `--remote-debugging-port` 在 Blockbench 打包版是否可用（发布配置未发现剥离，但未实测）。
3. `webPreferences.offscreen:true` 与 Blockbench 的 `@electron/remote`、`currentwindow`、`capturePage`、`CSS3DRenderer` 的兼容性。
4. `show:false` 未 show 前 `Preview.resize()`（挂 DOM 分支）读到的 `parentElement.clientWidth/Height` 是否为 0，以及对 `main_preview` 的影响。
5. Windows 下 `--userData` + 多实例并行（单实例锁是否真的按 userData 隔离）——`requestSingleInstanceLock` 的作用域实测。
6. 无网络时 `Plugins.loading_promise` 的失败时延（DNS 黑洞 vs 连接拒绝差异）与对 `app-loaded` 时序的影响。
7. `Screencam.advancedScreenshot` 在 `ssaa` 下 4 倍分辨率的显存/性能上限（`2_000_000` 像素空图检查，`screenshot.js:330`）。
8. `Texture.updateChangesAfterEdit()` 在 `Format.image_editor`（纯图片编辑器格式）下的行为差异（代码里跳过 `needsUpdate`，`textures.js:1856`）。
9. `types/generated/main` 的生成需要安装依赖（本任务禁止安装）；`blockbench-types` npm 包内容未拉取。

---

## 9. 对插件系统设计的直接含义（摘要）

1. **启动器形态**：fork `electron/main.js`（3 处小改：不 `show()`、`backgroundThrottling:false`、可选 `offscreen`）+ `--userData` 独立 profile；这是"无头 + 可截图"的最低成本方案。
2. **bridge 插件**：独立 `bb-bridge.js`（普通 Blockbench 插件格式），通过 `executeJavaScript → new Plugin().loadFromFile({path}, false)` 注入并持久化；或 CDP 远程注入（零源码改动）。
3. **渲染服务**：不依赖主窗口；全部出图走 `MediaPreview`/`NoAAPreview` + `Screencam.advancedScreenshot`（机位/分辨率/抗锯齿/透明背景一次到位）+ `Blockbench.writeFile`。
4. **贴图服务**：`Texture.getActiveCanvas()` 写像素 → `updateChangesAfterEdit()`；批量操作用 `Undo.initEdit({textures:[...], bitmap:true})...finishEdit()` 包住，保证可撤销、可脏标记。
5. **UI/网络**：离线 profile + 关自动更新/插件更新；永不调用 `export()/exportFile()/Action.trigger()`；关闭前 `Project.saved = true`。
6. **契约来源**：以本仓库 `js/*.ts` + `types/custom/*.d.ts` 为准（v5.2.2），官方 wiki/`blockbench-types` 仅作补充；升级 Blockbench 时重点复核 `plugin_loader` 的加载时序、`preview.ts` 的 `resize/render` 语义、`textures.js` 的刷新链。
