# dsh（DeepSeek Harness）侧集成技术事实

> 研究任务：为「Blockbench 无头建模/贴图 Agent 插件系统」提供 dsh 侧集成依据。
> 运行环境：DeepSeek Harness（Electron）`0.2.1-rc.2`，安装目录 `<DSH_INSTALL>`，asar 内源码/文档 `<DSH_INSTALL>\resources\app.asar\dsh`，`DSH_HOME=<USER_HOME>\.dsh`，profile `<USER_HOME>\.dsh\profiles\desktop`，Web GUI `http://127.0.0.1:14771`。
> 取证方式：只读源码/文档 + `cordis_inspect_list/query`（host）+ 一个 `read_image` 实测。**未安装/启用/修改任何插件与 profile 配置**。
> 标注约定：**[已证实]** = 有源码/文档/运行时证据；**【未验证/建议实验】** = 机制存在但未端到端跑通。

---

## 0. 结论速览（对设计最关键的 8 条）

1. **Host 插件就是普通 Cordis 插件**：`export function apply(ctx, config)` + 可选 `export const inject = ['tools']` + 可选 `export const Config`；用 `ctx.tools.register(defineTool({...}))` 注册模型工具，返回 disposer，用 `ctx.effect()` 管清理。**[已证实]**
2. **工具返回值可以内嵌图片**：`ToolDefinition.output.render(args, value)` 返回 `ContentBlock[]`，其中 `{ type: 'image', attachment: ImageAttachmentRef }` 是原生图片块；图片先用 `ctx.attachments.saveImage({ data, mediaType, name? })` 持久化。**[已证实：类型 + 文档 + read_image 实测]**
3. **"PNG → 模型可见"最稳的是"路径 + 模型调 `read_image`"**；本次已用真实 PNG 实测 `read_image` 成功把图送进了当前 deepseek-flash 会话上下文（当前路由支持图片输入）。 **[已实测]**
4. **`/show` 原生可行**：dsh 有完整的 slash 命令注册表 `ctx.commands.register({ name, description, input?, handler })`，斜杠命令不产生模型消息、结果由前端单独渲染；本 profile 的 Web 应用包含命令 UI 包 `dsh-client-ui-commands` + `dsh-client-ui-input-trigger`。**[Host 侧已证实；Client 侧 live slot 未验证]**
5. **`/show` 要把截图喂给模型**，需在 handler 里 `ctx.attachments.saveImage()` + `agent.inject({ content: [ImageBlock], source })`（可选 `agent.followup()` 唤醒）。`inject` 不发请求、只进下一步；图片块是否被 inject 端到端接受**【未验证/建议实验】**。
6. **Host 插件能力近乎不受限**：在本进程内运行，直接 `import node:child_process / node:fs`、`fetch('http://127.0.0.1:...')` 均可（现网已有 `minecraft-mod-dev` 插件如此做）；也可用 `ctx.subprocess`/`ctx.webServer.registerUpgrade` 等官方 seam。**[已证实，含现网实例]**
7. **安装/热更新**：`plugin_manager.install_bundle` 走 pnpm；本地目录安装记成 `link:` 依赖并加入 `dsh.profile.bundles`；有 HMR 时配置变更立即生效，**替换已安装包需要重启**；安装前校验 `engines.dsh` / DSH peerDependencies 版本。**[已证实]**
8. **Token 优化有现成积木**：工具 schema 固定成本 + `deferLoading`、read 截断、`dsh-output-retention` 库、spill 策略（文本/图片共享预算 + 落盘文件）、tool-result pruner、compaction（80% 阈值、`/compact`）、skill 目录懒加载。**图片会在此后每次请求重复计费直到压缩**，是最主要的长期成本风险。**[已证实]**

---

## 1. 插件模型：bundle / manifest / patch / Host / Client

### 1.1 Bundle 与 manifest

- **定义**：bundle = 在 `package.json` 里声明 `dsh.bundle.patch` 的 npm 包；patch（Loader YAML）负责插入插件行。**[已证实]** 依据 `<DSH_INSTALL>\resources\app.asar\dsh\node_modules\@deepseek-ai\dsh-agent-preset\skills\cordis-plugin-development\references\host-plugin.md:1-3`。
- **Host-only 最小 manifest（官方模板原文）**（`host-plugin.md:7-18`）：

```json
{
  "name": "@local/my-plugin",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "exports": { ".": "./index.js" },
  "dsh": { "bundle": { "patch": "./cordis.patch.yml" } }
}
```

- **cordis.patch.yml 最小插入**（`host-plugin.md:20-27`）：

```yaml
- insert:
    - id: my-plugin
      name: '@local/my-plugin'
      config: {}
```

- **patch 可以是数组**（多 patch 文件）：现网插件 `<WORKSPACE_ROOT>\MC模组开发\plugin\minecraft-mod-dev\package.json:22-29` 的 `dsh.bundle.patch` 是 `["./cordis.patch.yml", "./presets/mcmod.patch.yml"]`；官方 `dsh-web-app` 同理（`<DSH_INSTALL>\resources\app.asar\dsh\node_modules\@deepseek-ai\dsh-web-app\package.json:46-56`）。
- **patch 的三种能力**：`insert` 新行、按 `id` override（含 `config` 整体替换）、`disabled: true` 禁行；支持 `!!js` 表达式。**[已证实]** profile patch 实例见 `<USER_HOME>\.dsh\profiles\desktop\cordis.patch.yml:1-4`（注释原文），`minecraft-mod-dev\cordis.patch.yml:3-10`（按 id 禁用 4 个 subagent 行）与 `:12-31`（insert 6 行）。
- **patch 里插入的行可以引用官方安装包**（不需要自己依赖它们）：`minecraft-mod-dev\cordis.patch.yml:12-31` 直接 insert `@deepseek-ai/dsh-experimental-agent-team` 等包；官方说明见安装/解析章节 6.2。

### 1.2 Host 插件 export 形式

`host-plugin.md:57-64` 明确两种、不可混用：

- `export function apply(ctx, config) {}`，可加 `export const inject = ['tools']` 与 `export const Config`；
- 默认导出一个 service class。

并规定：**每个资源都在 `apply` 里用 `ctx.effect` 或 `ctx.on` 注册并返回 cleanup**；声明了 `Config` 的插件在激活时会校验该行 `config`。

真实官方实例（最完整）：`<DSH_INSTALL>\resources\app.asar\dsh\node_modules\@deepseek-ai\dsh-tool-fs\lib\index.js:1186-1231`：

```js
const name = "tool-fs";
const inject = ["tools", "fs", "systemPrompt", "workingDirectory"];
const Config = z.object({
  read: z.boolean().default(true),
  readImage: z.boolean().default(true), ...
});
function apply(ctx, config) { ... }
export { Config, apply, inject, name };
```

（`z` 即 `@deepseek-ai/schemastery`，同文件 `:1`；插件入口在 `apply` 里 `ctx.inject(["attachments"], ...)` 按可选服务挂载子工具 `:1221-1223`。）

真实第三方实例：`<WORKSPACE_ROOT>\MC模组开发\plugin\minecraft-mod-dev\index.js:20-21` 为 `export const name = 'mcdev'`、`export const inject = ['tools']`；`:844-860` 的 `apply(ctx)` 里用 `ctx.effect(() => () => { ...kill 所有子进程... })` 做卸载清理；`:862` 起一批 `ctx.tools.register(stringTool(...))`。

### 1.3 Client 插件

- manifest 增加 `dsh.client` 段与 `./client` export（`references/ui-plugin.md:3`；模板 `templates/decoration/package.json`）：

```json
"exports": { ".": "./index.js", "./client": "./client.js", "./locale/*.json": "./locale/*.json", "./icon": "./icon.svg" },
"dsh": {
  "bundle": { "patch": "./cordis.patch.yml" },
  "client": { "platform": "web", "immediately": true, "inject": ["@deepseek-ai/dsh-client-ui-conversation"] }
}
```

- Client 产物格式（`templates/decoration/client.js:1-22`）：`window.__ModuleLoader__.load({ id: '<package name>', factory(require) { ... return { inject: ['slots'], apply(ctx) { ctx.slots.inject(...); ctx.slots.register({ name: slot, id, order }, Component) } } } })`；React 从浏览器 module table 取，不要重复安装。
- 约束（`ui-plugin.md:9-13`、`practices.md:33-37`）：不要在 Host 起 HTML 再 iframe（拿不到主题/locale）；不要 `require('@deepseek-ai/dsh-client-ui-primitives')`；用 `--dsw-alias-*` 主题 token；资源在 `apply` 里注册并返回 cleanup。
- **本机 Client Slots 无法实时取证**：`cordis_inspect_query(platform=client, provider=Slots, method=listSubTree)` 两次均 `timed out after 10000ms`（提示 "Open or reconnect the Harness page"）。因此具体 Slot props 需在真正做 Client 插件时再查。**【未验证/建议实验】**

### 1.4 对 Blockbench 设计的含义

- 一个 bundle 可同时含 Host + Client 两半：Host 负责进程/端口/工具，Client 只做按钮/面板。
- 插件包名必须唯一；`id` 全局唯一；patch 用 `insert`/`override` 分层，用户 patch 层最高（升级不丢配置，`practices.md:22`）。
- 复杂功能建议拆成 **Host bundle（必须）** + 可选 Client bundle / 可选 preset 层，避免一个包同时承担进程管理与 UI。

---

## 2. Tool 注册 API（精确签名）

> 来源：`cordis_inspect_query(platform=host, provider=Service, input={service:"tools"})` 返回的 live 契约；文档 `<DSH_INSTALL>\resources\app.asar\dsh\node_modules\@deepseek-ai\dsh-tools\README.md`；官方实现 `dsh-tool-fs\lib\index.js`。

### 2.1 服务与注册

```ts
// ctx.tools（硬依赖 inject: ['tools']；可选 ctx.get('tools')）
presentAs(mode: ToolPresentationMode): () => void
register(definition: ToolDefinition): () => void      // 全局或调用方 agent scope；返回 disposer
restrict(filter: ToolRestriction): () => void          // allow/deny 全局工具（agent scope）
guard(guard: ToolGuard): () => void                    // 同步否决（返回字符串=拒绝）
get(name: string, scope?: ScopeKey): ToolDefinition | undefined
schemas(scope?: ScopeKey): ToolSchema[]
executionMode(exec: ToolExecutionInput): ToolExecutionMode
execute(exec: ToolExecutionInput): Promise<ToolExecutionResult>
```

要点：**scoped 工具遮蔽 global；同层重名与保留名 `run_code` 会失败**；`register` 返回 disposer（`tools` Service 契约）。

### 2.2 ToolDefinition / Schema / Output 类型（inspect 原文）

```ts
interface ToolSchema {
  deferLoading?: true;
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

interface ToolDefinition extends ToolSchema {
  readonly output: ToolOutputDefinition;
  execute(args: unknown, exec: ToolRunContext): Promise<unknown>;
  projectContent?(exec, result): ContentBlock[] | undefined;
  finalizeContent?(exec, result): ContentBlock[] | undefined;
  timeoutMs?: number;
  isConcurrencySafe?(args: unknown): boolean;
  presentCall?(args: unknown): ToolCallView | undefined;
  presentResult?(args: unknown, result: ToolResult): ToolResultView | undefined;
}

interface ToolOutputDefinition {
  readonly schema: JsonSchemaNode;
  render(args: unknown, value: JsonValue): ContentBlock[];
  presentationMeta?(args: unknown, value: JsonValue): JsonValue;
}

interface ToolRunContext extends ToolExecution {
  deferContext(context: UserMessage): void;
  concludeTurn(): void;
}
```

`ToolExecutionInput = { callId, rootCallId?, name, schema?, arguments, agent?, parent?, signal: AbortSignal }`。

### 2.3 推荐写法：`defineTool`（官方 DSL）

`dsh-tools\README.md:38-62` 原文示例：

```ts
import { defineTool } from '@deepseek-ai/dsh-tools'
ctx.tools.register(defineTool({
  name: 'read_file',
  description: 'Read a file from disk.',
  parameters: {
    path: { type: 'string', required: true, description: 'Absolute file path' },
    offset: { type: 'number' }, limit: { type: 'number' },
  },
  output: {
    schema: { type: 'string' },
    render: (_args, value) => [{ type: 'text', text: value }],
  },
  async execute(args, exec) { return readFile(args.path, { encoding: 'utf8', signal: exec.signal }) },
}))
```

- 参数 DSL 支持 `string/number/integer/boolean/null/array/object`、author-only `json`、exact-one `oneOf`；`InferValue` 保持 16 层容器类型（README:64-65）。也接受原始 `JsonSchemaNode`（wire 级别，subagent/workflow/MCP 共用）。
- `execute` **只返回 output.schema 声明的 JSON 值**；模型参数在执行前校验，非法入参自动变成普通错误结果（README:34）。
- 结果渲染：模型只看到 `render` 产生的 ContentBlock；原始 canonical value 另存供程序化调用/programmatic caller（README:36）。`presentCall/presentResult` 是 Host-local 的，本代 Web Client **不消费**，UI 卡片由 `tool.call.toolview` + raw args/result 派生（README:95）。
- 现网写法（非 TS，纯 JS 插件）：`minecraft-mod-dev\index.js:41-60` 自建 `stringTool()`：`output: { schema: { type:'object', properties:{ text:{type:'string',required:true} } }, render: (_a,v)=>[{type:'text',text:v.text}] }`，`execute` 返回 `{ text }`。这是可照抄的最小模式。

### 2.4 错误、超时、并发、取消

- 抛错/拒绝 → 模型看到 `Error: <message>`，**不会结束 turn**；结构化 code 供调用方/programmatic consumers（README:126, 215）。未知工具 → `UNKNOWN_TOOL`。
- 取消：`exec.signal` 必须被 body 观察；dispatch 前取消 = `ABORTED_BEFORE_DISPATCH`，已开始后取消 = 结果替换为 `ABORTED`（仍会 drain）。**"超时"不是注册表保证**：`timeoutMs` 是声明式，真正强制需要 `@deepseek-ai/dsh-tool-call-timeout-policy` wrapper（README:235）。本 profile 该行状态为 `absent`（见 §5.4 Config 目录），所以 **Blockbench 工具必须自己在 execute 内部 `Promise.race`/`AbortSignal.timeout` 控制时限**，并把 cancellation 传给子进程/HTTP。
- 并发：`isConcurrencySafe(args)` 只对定义自己的插件生效；`executionMode()` fail-closed（未知/未声明=exclusive）。
- 策略扩展点：`tools/pre-execute`（可 allow/deny/ask）、`tools/guard`（单调同步否决）、`tools/execute`（包裹 dispatch）、`tools/post-execute`（改内容/附加 context）、`tools/result`（只观察）；`pre-execute` **不能改写 args**（README:233）。Blockbench 写操作建议：只读工具声明并发安全，写/导出/破坏性操作用 guard 或审批。

### 2.5 注册后的可见性

- 注册即进入系统提示的 tool 清单（`dsh-tools\README.md:30`），无需额外声明。
- **实证**：本会话 `cordis_inspect_query(provider=Tool, listTools)` 中能看到 profile 插件 `minecraft-mod-dev` 注册的 `mcdev_*`（14 个）与 `@dsh-external/dsh-sogou-skin` 注册的 `skin_*`（约 17 个）工具，说明"profile 安装的 Host 插件注册的工具 = 模型可调用工具"闭环成立。

---

## 3. 多模态：渲染 PNG 如何让模型看见

### 3.1 底层链路（为什么可行）

- ContentBlock 类型里有原生图片块：`ImageBlock = { type: 'image', attachment: ImageAttachmentRef, offloaded?: true }`（`Service:commands` referencedTypes；`ImageMediaType = image/png|jpeg|webp|gif`）。
- 附件服务（`Service:attachments` 契约）：

```ts
abstract saveImage(input: SaveImageAttachment): Promise<ImageAttachmentRef>
// SaveImageAttachment = { data: Uint8Array; mediaType: ImageMediaType; name?: string }
// ImageAttachmentRef  = { attachmentId, mediaType, bytes, width, height, name?, originalDimensions? }
abstract validateImage(input): Promise<void>
abstract readImage(ref, signal?): Promise<StoredImageAttachment>
imageHostPath(ref): string | undefined        // 归一化对象在宿主机上的绝对路径
readImageRequest(ref, target, signal?): Promise<RequestImageAttachment>
```

- 官方 `read_image` 的模型可见结果（`dsh-tool-fs\README.md:203-205`）：返回 `<path>…</path><type>image</type><content>…media type/dimensions/bytes…</content>` + **图片本体作为 native image block**；结果在下次模型请求前已用 durable reference 记日志。工具注册门槛：有 durable `ctx.attachments`，且执行时路由的 exact model 声明 image input（README:42）。
- MCP 工具同样支持图片结果（`dsh-mcp-client\README.md:85-87,111`：`projectContent` 在 retention 之前装真实图片块）。
- 图片存储/规范化默认（`dsh-attachment-local\README.md:41-49,86`）：单图源 ≤20 MiB、单消息 ≤20 张/200 MiB、源像素 ≤64MP、单边 ≤8192；存储归一化到 2048×2048 总像素预算、长边 8192、编码目标 4 MiB；有 alpha→WebP、无 alpha→JPEG（85/75/60 质量梯）；EXIF 旋转、去 ICC、16-bit PNG 会转 8-bit。
- 代价（`dsh-tool-fs\README.md:207-209`）：**图片在后续每次请求都计费，直到 compaction**；内容寻址只去重存储字节，不去重 token。

### 3.2 可行路径对比

| # | 路径 | 机制 | 证据 | 优点 | 缺点 |
|---|---|---|---|---|---|
| A | **工具结果内嵌图片** | `execute` 里 `ctx.attachments.saveImage({data, mediaType})` 得到 ref → `output.render` 返回 `[{type:'text',...},{type:'image',attachment:ref}]` | `Service:attachments.saveImage`；`dsh-tool-fs\README.md:203-205`；`dsh-spill-policy\README.md:49`（图片按 budget 整块保留/省略） | 下一步模型直接看到，无需二次调用；一次 tool result 完成 | 每次请求重复计费；图片大小受 attachment 上限；需要 attachments 服务挂载 |
| B | **写文件 + 模型调 `read_image`** | 工具写 PNG 返回绝对路径 → 模型按描述调 `read_image(file_path)` | `dsh-tool-fs\README.md:49,53`；`minecraft-mod-dev\index.js` 的 `mcdev_screenshot` description（"Returns JSON with path/…; Use read_image on the returned path"）；**本次实测成功** | 模型自主决定看不看/看哪张，不看不花 token；可用 offset/多次重看；无需 attachments 写代码 | 多一次 tool call；模型可能不调用；read_image 仍要求图片路由 |
| C | **attachment 对象路径复用** | 用 `ctx.attachments.imageHostPath(ref)` 或直接存 `<DSH_HOME>\attachments\v1\objects\…` 路径，交给 read_image（支持无扩展名按签名识别） | `dsh-tool-fs\README.md:49,253`；`dsh-attachment-local\README.md:84`（path 规则） | 与 A 组合：A 内嵌小图，C 留全分辨率大图供后续细看 | 对象区只读（read_image 会重新 admit 一次源字节） |
| D | **MCP server 返回 image content** | Blockbench 侧 MCP server 返回 image 块，dsh `dsh-mcp-client` 投影成图片 | `dsh-mcp-client\README.md:85-87,111` | dsh 侧零代码；自动重连；工具命名空间 `mcp__blockbench__*` | 需要 Blockbench 侧能跑 MCP server（超出本次范围） |
| E | PTC `run_code` 内图片子结果 | 图片型子调用成功后在程序结果之后以 deferred user-message context 附加 | `dsh-tools\README.md:134,198` | 批量操作时非常省界面 | 需要 PTC runtime；不是主要交付形态 |

### 3.3 实测（关键）

```
read_image(file_path = "<WORKSPACE_ROOT>\输入法皮肤\03-皮肤工程\复刻-雷电将军\preview\render.png")
→ image/png 1236x816 px, 245512 bytes
→ Normalized copy: <USER_HOME>\.dsh\attachments\v1\objects\60\604e25b6…（1236x816, image/png）
→ 模型上下文里收到了图片本体（本次会话确实"看见"了该皮肤预览图）
```

即：**当前 desktop profile 的模型路由（deepseek-flash）声明并接受图片输入**，路径 B 已在真实环境跑通。这是 Blockbench 渲染回灌的直接可行性证据。

### 3.4 推荐方案（对 Blockbench）

1. **主路径 = A + B 组合**：
   - `bb_render_preview` 工具：无头渲染一帧 → 写 `preview/<timestamp>.png`（项目内可复用/可回溯）→ 返回**文本摘要**（尺寸/相机/对象数/耗时/路径）+ **一张 downscale 预览图**（`saveImage` 内嵌，走工具结果图片块）。
   - 全分辨率图留在文件系统；模型需要细看时自己 `read_image`（路径 B）。
2. **不要每步都回灌图片**：图片从产生起每次请求重复计费；默认只在"显式截图/预览"工具里附带小图，其余工具只回结构化数据 + 文件路径。
3. **控制图片尺寸**：成品截图先缩到长边 ≤1024~1536（远低于 2048 归一化上限），既省 token 又避免 attachment 拒绝；透明贴图注意 alpha→WebP。
4. **失败兜底**：若 `ctx.attachments` 未挂载或路由不支持图片（`read_image` 会报 `cannot read "…" as an image: model "…" does not declare image input`），工具降级为"只返回路径 + 提示用户/让模型读文件"，不要静默丢图。
5. **工具返回不要塞大 JSON**：Blockbench 场景（场景树/材质列表）极易超大，用下面的 `dsh-output-retention`/spill 机制截断（见 §7）。

---

## 4. 用户命令 `/show`

### 4.1 结论：dsh **原生支持** slash 命令，`/show` 可作为 Host 插件命令实现

- 服务 `ctx.commands`（`Service:commands` 契约）：

```ts
register(definition: CommandDefinition): () => void
registerFileReceiptResolver(resolver): () => void
list(agent): readonly CommandDescriptor[]
find(agent, name): CommandDefinition | undefined
execute(agent, line, submittedAttachments, signal): Promise<CommandExecution | undefined>

interface CommandDefinition {
  definitionId?: CommandDefinitionId; name: string; description: string;
  input?: { hint: string; attachments?: boolean };
  recordInput?: boolean;
  handler: (invocation: CommandInvocation) => CommandResult | Promise<CommandResult>;
}
interface CommandInvocation { commandId; agent: Agent; rawInput: string; attachments: readonly (ImageBlock|FileBlock)[]; signal: AbortSignal }
type CommandResult = { kind:'success'; text?: string; sourceEventSeq?: SessionSeq } | { kind:'error'; text: string }
```

- 语义（`<DSH_INSTALL>\resources\app.asar\dsh\node_modules\@deepseek-ai\dsh-commands\README.md:12,32-46,50-54,58,62,88`）：
  - 语法：行首 `/` + 小写名（字母/数字/`_`/`-`），其后全部（含空格）是 `rawInput`，语法由命令自理；
  - **命令不产生模型消息**，handler 直接对 agent 执行；结果由适配器在模型历史之外渲染；`command/run`/`command/done` 写入 session log；
  - 同一 scope 重名注册会抛错；Global 注册 vs agent-scoped 注册（后者遮蔽同名全局）；
  - 可声明 `input.attachments` 接收 composer 图片/文件；
  - `list(agent)`/`find` 供 UI 发现。
- 文档实例（`dsh-commands\README.md:34-44`）：

```text
ctx.commands.register({
  name: 'plan', description: 'Enter plan mode', input: { hint: '<message>' },
  handler: ({ agent, rawInput }) => ({ kind: 'success', text: 'plan mode selected' }),
})
```

- **前端支持链已具备**：`@deepseek-ai/dsh-web-app` 的依赖里含 `@deepseek-ai/dsh-client-ui-commands`（`dsh-web-app\package.json:81`）与 `@deepseek-ai/dsh-client-ui-input-trigger`（`:88`）；Client 文档描述 `/` 命令源、菜单、三种 dispatch、附件拒绝提示（`<DSH_INSTALL>\resources\app.asar\dsh\node_modules\@deepseek-ai\dsh-client-ui-commands\README.md:12,28,32,42,46`）。本 profile 的 bundle 列表为 `@deepseek-ai/dsh-base` + `@deepseek-ai/dsh-web-app`（`<USER_HOME>\.dsh\profiles\desktop\package.json:5-11`）。
- **未验证**：Client `Slots` 查询超时，无法现场确认本 GUI 的实际菜单/Slot；命令是否已挂载也无法用 Client inspect 验证。**【未验证/建议实验】**

### 4.2 `/show` 设计的 5 条落地路线

| 路线 | 做法 | 证据/可行性 | 适用 |
|---|---|---|---|
| **1. Host 命令（推荐主路径）** | Host 插件 `inject:['commands']`，`ctx.commands.register({ name:'show', description:'让模型看到当前 Blockbench 画面', input:{hint:'[可选说明]'}, handler })`；handler 内截图 → `ctx.attachments.saveImage` → `agent.inject()` 图片 + 可选 `agent.followup()` 触发下一轮 | commands 契约 + README；`dsh-agent\README.md:47-59`（`inject/steer/followup` 的 content 为 `ContentBlock[]`）；`practices.md:18`（inject 记 `agent/inbox/spliced`、进下一 admitted step） | 用户显式 `/show` |
| 1b. 命令只回文本 | handler 返回 `{kind:'success', text:'已截图: <path>'}`，模型不参与；用户再发消息 | 同上 | 只想让用户看 |
| **2. 模型工具 `show_gui`** | 与普通工具一致：截图并 `render` 返回图片块；模型自己决定调用 | §2/§3.2-A；最可靠、无前端依赖 | 模型自主查看 |
| 3. Client 按钮 | Client 插件在 `conversation.composer.dock` slot 注册按钮，点击执行 `ctx.remote.commands.execute(...)` 或自定义 Remote | `templates/decoration/client.js`；`references/user-actions.md:6-10`（UI action 调 Host entry，如 `ctx.remote.commands.execute()`）；Client Slots 未实测 | 想要 GUI 按钮 |
| 4. 可被用户调用的 Skill | 插件注册 `modelInvocable:false, userInvocable:true` 的 skill；用户输入 `/show` token 触发注入指令 | `dsh-tool-skill\README.md:56,89`；`dsh-skill\README.md:52,55`（`ctx.skills.register`） | 只是个提示词快捷方式 |
| 5. 自然语言 | 系统提示/工具描述里写"用户说'给我看/看屏幕'时调用 show_gui" | `ctx.systemPrompt.section()`（Service:systemPrompt） | 兜底 |

### 4.3 `/show` handler 实现要点（伪代码）

```js
export const inject = ['tools', 'commands']        // commands 可放 ctx.get() 做成可选
ctx.commands.register({
  name: 'show', description: 'Capture the current Blockbench view for the model',
  input: { hint: '[区域/说明]' },
  async handler({ agent, rawInput, signal }) {
    const png = await captureBlockbenchView({ region: rawInput, signal })   // 自建 bridge
    if (!png) return { kind: 'error', text: 'Blockbench 未运行或截图失败' }
    const ref = await ctx.attachments.saveImage({ data: png, mediaType: 'image/png', name: 'blockbench-view.png' })
    agent.inject({ content: [
      { type: 'text', text: `以下是当前 Blockbench 画面（${rawInput || '全窗口'}）。` },
      { type: 'image', attachment: ref },
    ], source: { kind: 'plugin:blockbench' } })
    agent.followup({ content: [{ type: 'text', text: '请先观察这张 Blockbench 截图，再继续。' }], source: { kind: 'user' } })
    return { kind: 'success', text: '已把当前画面发给模型' }
  },
})
```

注意事项：
- `inject` 不唤醒 driver；想让模型立刻反应要 `followup()`（会新增一个 user turn；`dsh-agent\README.md:47`）。
- `saveImage` 是 async，长截图要在 handler 内自己设超时；`command/run`→`command/done` 会记录生命周期，超长命令 UI 体验**【未验证/建议实验】**。
- 图片块进 `inject`/`followup` 的结构可行性来自 `ContentBlock` 含 `ImageBlock` + `attachments` 服务；**未做端到端验证**，实现前先做一个最小实验。
- 命令名 `show` 可能与现有命令冲突（同 scope 重名抛错）。上线前用 `ctx.commands.find(agent,'show')` / Client 目录检查；冲突就改 `bb-show`。

---

## 5. 插件工程与安装

### 5.1 manifest / 展示资源要求（`host-plugin.md:29-53`）

- `locale/en.json`（及 `locale/zh.json` 等）必须写：

```json
{ "meta": { "title": "…", "description": "…" } }
```

- 图标：`exports` 增加 `"./icon": "./icon.svg"`（或 png/jpeg/webp），或 package 顶层 `icon` 字段（优先级更高，路径相对 manifest）；**SVG/PNG/JPEG/WebP ≤ 256 KiB，必须在包内，拒绝绝对路径/URL/越界符号链接**；缺失时回退 `name`/`description` 与默认美术。
- `files` 要包含 patch、locale、icon 与所有运行时文件；**本地目录安装是 link，`files` 不过滤**，所以本地测试时以实际文件为准；打包发布时校验真实打包清单。
- 客户端：`dsh.client.platform: "web"`、`immediately`、`inject`（仅排序，不是运行时依赖）；`./client` export。

### 5.2 最小可落地 bundle 骨架（无需实现，仅清单）

```
blockbench-agent/                      ← 发布/链接目录，绝对路径交给 install_bundle
├─ package.json                        ← 身份 + 入口 + dsh.bundle.patch + dsh.client(可选) + exports/files + peerDependencies
├─ cordis.patch.yml                    ← insert Host 行（id/name/config）；可 insert Client 行
├─ index.js                            ← Host：export { name, inject, apply, Config }
│                                         apply 内：ctx.effect 清理（杀 Blockbench 子进程/关端口）、
│                                         ctx.tools.register(defineTool(...)) × N、
│                                         ctx.commands.register({name:'show',...})、
│                                         ctx.systemPrompt.section(...)（可选）、
│                                         ctx.skills.register?（可选，内嵌使用说明 skill）
├─ client.js                           ← 可选 Client：window.__ModuleLoader__.load({id, factory})，注册 composer 按钮/面板
├─ locale/
│  ├─ en.json                          ← meta.title / meta.description
│  └─ zh.json                          ← 同上（中文）
├─ icon.svg                            ← 原创/可再分发图标，≤256KiB
├─ presets/
│  └─ agent.patch.yml                  ← 可选：只在某 preset 里挂载/限制工具集
└─ README.md                           ← 可选：人类文档（不参与运行时）
```

每个文件职责：
- `package.json`：`name` 全局唯一、`type:"module"`、`exports` 至少 `.`/`./locale/*.json`/`./icon`（有 Client 再加 `./client`）、`files` 列全部运行时文件、`dsh.bundle.patch`（字符串或数组）、可选 `dsh.client`、`peerDependencies` 写 `@deepseek-ai/cordis`、`@deepseek-ai/dsh-tools` 等（版本对齐安装的运行版本）。
- `cordis.patch.yml`：仅 `insert` 一行/几行；配置值写在该行 `config` 里（可被用户 patch 覆盖，`practices.md:22`）。
- `index.js`：唯一 Host 入口；所有注册必须返回 disposer / 包在 `ctx.effect` 内；长生命周期资源（子进程、HTTP/WS server、定时器）在 effect cleanup 里释放。
- `client.js`：可选，仅 UI；不要读别的插件 DOM、不要塞 document.body。
- `locale/*.json` + `icon.svg`：Plugin Manager / Settings 在**不激活插件**时读取的展示元数据（`host-plugin.md:31`）。
- `presets/*.patch.yml`：可选 preset 层（官方 `dsh-web-app` 同款机制，`dsh-web-app\package.json:48-55`）。

### 5.3 安装 / 热更新（`plugin_manager` 的 `install_bundle`）

- 机制（`<DSH_INSTALL>\resources\app.asar\dsh\node_modules\@deepseek-ai\dsh-plugin-manager\README.md`）：
  - 安装 = pnpm 包操作 + bundle 选择；本地目录安装保存为 `link:` 依赖（`:44,50,52`）；本 profile 已是这种形态（`package.json:15-17`：`"minecraft-mod-dev": "link:F:/Deepseek_harness/MC模组开发/plugin/minecraft-mod-dev"`；`node_modules` 里对应条目是 Junction，已用 PowerShell 实测）。
  - 选择 bundle = 改 `package.json` 的 `dsh.profile.bundles` 有序列表；安装默认启用并追加到末尾，会改变配置优先级（`:40`）。
  - **HMR**：启用 HMR 时配置变更立即重组合生效；否则运行中的组合等重启（`:14,98-100`）。**替换已安装包需要重启才能载入新的 JS 模块代**（`host-plugin.md:70`；`plugin-manager README:141`）。新装 bundle 可以经 HMR 激活。
  - **版本兼容检查**：安装前读本地 package.json 或 registry 该版本，检查 `engines.dsh`、否则检查 DSH peer 包名与需求；不满足**拒绝安装/激活**（`:69`）。本 profile 运行版本 `0.2.1-rc.2`（`<DSH_INSTALL>\resources\app.asar\dsh\package.json:4`），所以 peerDependencies 应写 `0.2.1-rc.2`（或兼容范围）。
  - 构建脚本需显式批准：pnpm 11 拦截时列 `pendingBuilds`，Web 页提供"允许并重试"，工具用 `approvedBuilds`（只有用户明确同意才能传）（`:64`；工具描述同）。
  - 失败回滚：pnpm/校验失败恢复 `package.json`+`pnpm-lock.yaml`（`README:104,155`）。
- 安装后校验：`cordis_inspect_query(Config/Tool)` 确认新行与工具出现，不要只看日志（`host-plugin.md:66-70` 同义）。

### 5.4 本 profile 现状（可直接引用的事实）

- bundles：`@deepseek-ai/dsh-base`、`@deepseek-ai/dsh-web-app`、`minecraft-mod-dev`、`@dsh-external/dsh-sogou-skin`（`<USER_HOME>\.dsh\profiles\desktop\package.json:5-11`）。
- `cordis.yml` 是空数组（组合由 patch 叠加，`...\cordis.yml:1-4`）；用户 patch 层是 `...\cordis.patch.yml`（`:1-4` 注释、`:4-41` 覆盖若干行 config）。
- Host 行形态参考：`include:mcdev`、`include:dsh-sogou-skin` 在 Config 目录中出现，证明外部 bundle 行与官方行同构。
- 内置工具行示例（Config 目录）：`tools`、`system-prompt`、`agent-loop`、`token-meter`、`compaction-basic`、`compaction-tool-result-pruner`、`spill-local`、`spill-policy`、`attachment-local`、`webserver`、`commands`、`skill`/`skill-filesystem`、`mcp-client` 包等均存在于安装中（是否 enabled 视行状态而定；`absent/inactive/schema` 的确切语义以 Plugin Manager UI 为准）。

### 5.5 生命周期清理（必须遵守）

- `host-plugin.md:64`：所有资源在 `apply` 内用 `ctx.effect`/`ctx.on` 注册并返回 cleanup。
- `practices.md:8`：注册是**被 context 拥有的 effect**；插件卸载/agent 销毁/preset 变更会自动移除。跨 context 注册（如 `agent.ctx`）有双 owner：既要在 plugin effect 里保存 disposer，也要在 `agent.ctx` 的 effect 里注册，保证两种 teardown 都能拆（`:19`）。
- 现网样板：`minecraft-mod-dev\index.js:844-860`，`ctx.effect(() => () => { for (const entry of processes.values()) entry.child.kill(); processes.clear() })`。
- Blockbench 插件必做：`apply` 里 `ctx.effect(() => () => { kill Bridge 子进程; 关 HTTP/WS; 清定时器 })`；每个 tool 返回的 disposer 不用手管（注册即 effect），但自己 spawn 的进程/端口/文件监听必须挂在 effect 里。

---

## 6. Host 插件能力边界

### 6.1 能做什么（有现网证据）

`<WORKSPACE_ROOT>\MC模组开发\plugin\minecraft-mod-dev\index.js` 是一个已在此 profile 运行的 Host 插件，证明：

| 能力 | 证据 |
|---|---|
| `import node:child_process` 的 `spawn/spawnSync`，设置 `cwd/shell/windowsHide`、捕获 stdout/stderr、`child.kill('SIGKILL')`、超时 kill | `:2, 80-85, 102-141, 266-300` |
| `import node:fs`（`createWriteStream/readFileSync/mkdirSync/mkdtempSync/rmSync/statSync`） | `:3-12, 78-99, 262-270` |
| 全局 `fetch('http://127.0.0.1:<port>/…', { headers, signal: AbortSignal.timeout(15000) })` 访问本地 HTTP 探针 | `:23-39, 169-181` |
| `node:os`/`node:path`/Map 维持长生命周期子进程表 | `:13-18, 255-300` |
| 跨平台 Windows 路径/进程处理 | `:74, 108-113, 260-270` |

并且插件代码在主进程内运行、**在 workspace 沙箱之外**（`dsh-plugin-manager\README.md:31`："installed Host code executes in-process outside the workspace sandbox"）。因此启动/监管 Blockbench 子进程、监听本地端口、读写项目文件都可行。

### 6.2 依赖解析（ws / node-pty / 第三方包）

- **官方 dsh 包不需要声明为 dependencies**：从 dsh 安装解析（skill 明确 "Packages shipped with dsh resolve from the dsh installation, so the bundle declares no dependencies on them"；现网插件用 `import { defineTool } from '@deepseek-ai/dsh-tools'` 而自身目录**没有 node_modules**，只声明 peerDependencies）。peerDependencies 写运行版本便于安装期版本检查（`plugin-manager README:69`）。
- **第三方 npm 包（ws、node-pty 等）**：
  - registry 安装的 bundle：`installBundle` 用 pnpm 安装到 profile，依赖落在 profile 的 node_modules，正常 Node 解析可用（`plugin-manager README:52,60,100`）。
  - 本地目录（`link:`）安装：官方文档明确 "**Linked packages use that checkout's dependencies and peers**"（`:50`）→ 需要在插件 checkout 里自行 `pnpm install`，依赖装在 checkout 自己的 `node_modules`。当前 profile 的两个插件都没有自建 node_modules（`MC模组开发\plugin\minecraft-mod-dev` 下 glob `package.json` 只命中根文件），说明它们只用了 dsh 安装提供的包与 Node 内建。**【未验证/建议实验】ws/node-pty 在 link 场景下的具体解析，建议先做一个 5 行 spike。**
  - 替代方案（省依赖）：
    - 本地 HTTP + 轮询：`fetch` 已现网验证（mcdev 模式，推荐 MVP）；
    - WebSocket：可用 `ctx.webServer.register/registerUpgrade` 在 GUI 的 HTTP server 上加路由（`Service:webServer` 契约 + `<DSH_INSTALL>\resources\app.asar\dsh\node_modules\@deepseek-ai\dsh-host-webserver\README.md:12,39,61,65`；`WebUpgradeRoute = { path, handler(req, socket: Duplex, head) }`，官方 webserver 只交原始 socket，WS 握手/帧要自己写或用 ws）。注意 `dsh-host-webserver` 文档说 Electron 用 `file://` + IPC 载入 dist，浏览器才走 HTTP；本 GUI 实际 URL 是 `http://127.0.0.1:14771`，以实测为准。
    - 或者直接 `node:http.createServer` 起独立端口（与 GUI server 无关，最省事）。
- **不建议**依赖 `electron` API / 渲染进程能力：Host 插件是 Node 侧，文档无相关授权描述。**【未验证】**

### 6.3 管理子进程的官方 seam（可选）

`ctx.subprocess`（`<DSH_INSTALL>\resources\app.asar\dsh\node_modules\@deepseek-ai\dsh-subprocess\README.md:39-76`）：

```ts
const exe = await ctx.subprocess.resolveExecutable('Blockbench.exe')
const handle = ctx.subprocess.spawn({
  argv: [exe, '--headless', project], cwd, 
  stdio: { stdin:'ignore', stdout:{maxBytes:64*1024}, stderr:'inherit' }, graceMs: 5000,
})
const { exitCode, signal } = await handle.done
await handle.terminate() / handle.waitForExit()
ctx.subprocess.spawnTerminal({...})   // 真 PTY
```

优点：托管进程树、环境变量清洗（凭据/`DSH_*` 被剥离，`:80`）、`control` 管道（`:64-66`）。**本 profile 是否挂载了 `dsh-subprocess-local` 未确认**（Config 目录该行状态 `absent`），所以要写成可选：`ctx.get('subprocess')` 优先、否则 `node:child_process`（mcdev 即后者）。

### 6.4 权限/安全边界

- 插件安装/启用需要 `danger-full-access` 或逐次审批；安装后 Host 代码就在 harness 进程里跑，**没有 workspace 沙箱**（`plugin-manager README:31`）。因此 Blockbench 插件的文件写入/子进程属于"可信插件代码"，安全要靠自身设计（路径白名单、仅 localhost、process allowlist）。
- 工具调用侧仍可被 `ctx.tools.guard/restrict`、approval、permission presets 约束（`dsh-tools README:89`）；写入类工具可复用 fs-sandbox 的 escalation 模式，但**自建子进程/端口不受 fs sandbox 管辖**。**【建议实验：确认是否需要走 ctx.fs 而非 node:fs】**

---

## 7. 长会话 Token 优化机制（可复用点）

### 7.1 工具 schema 侧

- 模型看到的工具 schema 是**固定每请求成本**；`ctx.tools.restrict` 隐藏工具能完全去掉其 schema 成本（`dsh-tools\README.md:170-176`）。
- **注册/注销/restriction 变化会让 KV 前缀失效**：从第一个变化的 schema token 起不可复用（`:174-176`）。→ **不要每步动态注册/注销工具**；把可选工具组放进 agent-scoped 注册或 `restrict`，一次成型。
- `ToolSchema.deferLoading?: true`：定义与 `defineTool`/schema 投影/系统提示装配都保留该标记，请求延迟加载（`Service:tools` 类型；`dsh-tools README:240`）。provider 支持程度有限，**建议实验**。
- PTC 模式（`dsh-tools README:178-209`）：`run_code` 替代逐工具 schema，用生成的 SDK 文本；适合"一次写程序做很多建模操作"的场景，能显著降 schema/往返成本。需要 `ptc-runtime`（本 profile 有 `include:ptc-runtime` 行与 `preset-ptc`）。
- 多工具时按功能拆 preset/子 agent：不同 preset 的工具集不同，是天然瘦身手段（`practices.md`、`dsh-web-app` 的 presets 机制）。

### 7.2 工具输出侧（现成、强烈建议直接复用）

| 机制 | 作用 | 证据 |
|---|---|---|
| **read 工具自带截断** | `readLimit` 2000 行、单行 2000 字符、单次 51200 字节、大文件流式 | `dsh-tool-fs\README.md:64-68` |
| **`@deepseek-ai/dsh-output-retention` 库** | `ItemRetainer`（列表头窗口 + 精确 omitted 计数）、`TextRetainer`（head/tail/headTail 字节窗口，UTF-8 安全）、`formatRetentionNotice`（统一省略脚注） | `dsh-output-retention\README.md:12,28-56,61-70`；作为**库直接 import**，不需要挂载 |
| **spill 策略** | 文本+图片共享 `maxInlineTokens` 预算；超限结果保留有序头尾 + 落盘完整文件路径；模型可 `read`/`grep`/`read_image` 恢复；图片按块保留或整体省略 | `dsh-spill-policy\README.md:12,28-57,61-69,87-88`；本 profile Config 目录有 `spill-local`/`spill-policy` 行 |
| **tool-result pruner** | 仅在 compaction 触发时启用；默认 >8192 字符裁成 head 4096 + marker + tail 1024；保留图片/结构化块顺序 | `dsh-compaction-tool-result-pruner\README.md:12,44-56,60`；本 profile 有该行（状态 inactive） |
| **compaction-basic** | 默认窗口 80% 触发、保留最近 16%、`/compact` 手动、溢出后压缩重试；压缩只留摘要文本 | `dsh-compaction-basic\README.md:12,28-32,62-77` |
| **图片专门优化** | `dsh-compaction-image-offload`（图片 offload）存在于安装（desktop package.json:113）但本 profile 行 absent；图片仍按每条后续请求计费 | `dsh-tool-fs\README.md:209` |
| **PTC 结果** | 成功带图子调用在程序结果后作为 deferred context 附加；其余中间结果不进对话 | `dsh-tools\README.md:134,198` |

**对 Blockbench 工具的直接要求**：自定义工具不要返回 MB 级 JSON。用 `dsh-output-retention` 保留头窗口 + 精确省略数，把完整内容写文件并给路径；图片默认只回一张缩略预览（见 §3.4）。

### 7.3 上下文/知识加载侧

- **Skill 懒加载**（本会话正在用的机制）：`dsh-tool-skill` 在首个请求前注入"技能名 + ≤500 字描述"的 durable catalog，模型按需调用 `skill` 加载全文（`<DSH_INSTALL>\resources\app.asar\dsh\node_modules\@deepseek-ai\dsh-tool-skill\README.md:12,52-56,61`；`catalogDescriptionMaxLength` 默认 500）。→ 把 **Blockbench 建模/贴图用法长文档做成 skill**，不要塞进工具描述或系统提示。
- **插件可注册内嵌 skill**：`ctx.skills.register(...)`（`dsh-skill\README.md:52`），带 `modelInvocable`/`userInvocable` 策略；`userInvocable` 还能被用户以 `/name` 直接调用（`tool-skill README:56,89`）——另一个 `/show` 式入口。
- **系统提示分段**：`ctx.systemPrompt.section()` / `context()` / `tools()`（`Service:systemPrompt`）；官方实践是按工具可见性门控段落（`dsh-tool-fs\README.md:141-145`），即"没挂载/不可见的工具不产生提示成本"。
- **派生上下文用 `agent.inject()`**：把随会话变化的状态作为 per-agent context 注入，记 `agent/inbox/spliced`，下次 admitted step 才进上下文（`practices.md:18`），不要写自定义 session event（`practices.md:21`：自定义 `type` 会让 session 无法重开；`appendPluginRecord` 仅官方实验包可用）。
- **Session projection**：每会话派生状态放 `ctx.sessionProjections`（纯同步 fold、引用不变零成本、`stateVersion` 支持 checkpoint）（`practices.md:24-29`）。→ Blockbench 的"当前模型/选中对象"状态应做成 projection，而不是每步重扫日志。

### 7.4 对设计最关键的 token 结论

1. **不要把 Blockbench 渲染图作为"每步上下文"常驻**：一张图从产生起每次请求重复计费，长会话里几张图就吃掉大量窗口。默认只在 `show`/`preview` 显式工具里附图，且小图。
2. **工具集稳定 > 动态增减**：schema 变化会废掉 KV 前缀；按 preset 拆工具集比运行时注册/注销划算。
3. **长文本一律"摘要进上下文、全文落盘 + 路径"**：`dsh-output-retention` + spill 已是官方模式。
4. **用法文档做成 skill**，不要写进每个工具 description（description 固定每请求成本）。

---

## 8. 对 Blockbench 插件系统的设计含义（汇总）

1. **推荐两条可并行路线**：
   - **路线 A（dsh 侧可控性最高）**：自写 Host bundle `blockbench-agent`：`ctx.tools.register` 一组语义工具（`bb_launch/bb_status/bb_render_preview/bb_screenshot/bb_apply_texture/…`），内部用 `node:child_process` 启动 Blockbench + 本地 HTTP（mcdev 已证明此模式），`ctx.effect` 管进程清理；`/show` 用 `ctx.commands.register`；图片回灌用 §3.4 的 A+B 组合；用法文档注册成 skill。
   - **路线 B（dsh 侧零代码）**：若 Blockbench 侧能提供 MCP server，用**配置型 bundle** insert `@deepseek-ai/dsh-mcp-client`（`transport: streamable-http` 或 `stdio`；模板 `templates/mcp/cordis.patch.yml`；`<DSH_INSTALL>\...\dsh-mcp-client\README.md:28-53,61-67,75,87`）。工具自动叫 `mcp__blockbench__*`，图片结果原生支持，带自动重连（500ms→30s，最多 10 次）；缺点是 dsh 侧无法精细控制 Blockbench 生命周期/GUI 进度。
   - 两者可同时存在：MCP 做"工具面"，Host 插件做"进程生命周期 + `/show` + 预览图 + GUI 按钮"。
2. **工具面建议**：只读查询类工具声明 `isConcurrencySafe`，写/导出类 exclusive + guard；每个工具内部自管超时（声明式 `timeoutMs` 不强制，且本 profile 无 timeout-policy 行）；错误用稳定 code + 可操作提示（参考 `dsh-tool-fs\README.md:231-233` 的错误文案风格）。
3. **`/show` 语义建议明确**：`/show` = "截图 + inject 图片 + followup 让模型继续"；另配 `/bb` 或按钮做"打开/关闭 Blockbench 窗口"。若只想让人看，命令返回路径即可。
4. **状态与日志**：会话中"Blockbench 当前状态"用 `ctx.sessionProjections`/工具返回重建，不写自定义事件；截图用 attachment（持久、去重、可重放）或项目内文件（可 `read_image`）。
5. **工程与安装**：单 bundle、`peerDependencies` 对齐 `0.2.1-rc.2`、locale 中英 + 图标齐全；本地开发用 `link:` 安装（本 profile 已是）→ 改代码后**重启 harness**（HMR 只保证配置/新装 bundle 激活）；发布时走 registry 让依赖自动安装。
6. **安全**：Host 代码在进程内、沙箱外——只绑定 `127.0.0.1`、只 spawn 配置允许的可执行文件、项目路径白名单、不信任 Blockbench 返回的任意路径执行。

### 风险清单

| 风险 | 说明 | 缓解 |
|---|---|---|
| 图片 token 长期成本 | 每请求重复计费直到 compaction | 只在显式 show/preview 附图、小图、默认不附图 |
| schema/KV 抖动 | 动态注册/restrict 会废 KV 前缀 | 工具集固定、按 preset 拆分 |
| 客户端 `/show` 未验证 | Slots/命令目录无法现场 inspect | 先做 Host 命令；Client 按钮二期 |
| `agent.inject` 图片未端到端验证 | 类型支持但未实测 | 先写 20 行 spike：saveImage→inject→followup |
| 替换插件需重启 | 开发迭代慢 | 用 `link:` + 重启脚本；配置改动用 HMR |
| 子进程失控 | 无 timeout 强制、无 sandbox | 自管超时、process tree kill、effect cleanup |
| 图片路由依赖 | 换到无图片输入的路由会拒图 | 工具内检测/降级为路径；提示切模型 |

---

## 9. 未验证 / 建议实验清单

1. **Client `Slots` 实时拓扑**：两次 `listSubTree` 超时（10s），未拿到 composer 按钮 slot 的 props/options；以模板 `conversation.composer.dock` 为准，实现前重试（打开/重连页面）。
2. **`agent.inject()` / `followup()` 接受 ImageBlock 的端到端行为**：类型上 `ContentBlock` 含 `ImageBlock`，但未实际跑过"命令注入图片 → 模型下一步看见"。
3. **本 profile 的 `commands` 行与 `ui-commands` 是否真的 enabled**：文档 + bundle 依赖 + Host 服务存在，但无法用 Client inspect 确认 GUI 菜单；建议实机敲 `/` 观察。
4. **`ws` / `node-pty` 在 `link:` 插件目录的依赖解析**：文档说 linked 包用自己 checkout 的 dependencies/peers，未实测。
5. **`ctx.subprocess` 是否挂载**：Config 目录该行状态 `absent`；代码应按可选服务写。
6. **`spill-policy` 在本 profile 的实际 `maxInlineTokens` 值**：未读 dsh-base 的 patch 内容；需要时用 `Config.listConfigs` 查该行或读 `@deepseek-ai/dsh-base/cordis.patch.yml`。
7. **`deferLoading` 的实际 provider 生效度**：README 自述有局限。
8. **命令 handler 长耗时（截图 >10s）的前端体验/超时**：未验证。
9. **Electron 运行时是否可用全局 `WebSocket`/`fetch` 细节**：`fetch` 现网已用；`WebSocket` 未测。
10. **`/show` 名称冲突**：未列出当前全部命令；实现前用 `find` 检查。

---

## 10. 关键证据索引（按用途）

**官方 skill（安装包内，read 可读）**
- `<DSH_INSTALL>\resources\app.asar\dsh\node_modules\@deepseek-ai\dsh-agent-preset\skills\cordis-plugin-development\references\host-plugin.md`（bundle/manifest/展示资源/Host export/安装观察）
- 同目录 `references\ui-plugin.md`、`references\practices.md`、`references\user-actions.md`、`references\mcp-bundle.md`
- 同目录 `templates\decoration\{package.json,cordis.patch.yml,index.js,client.js,locale\en.json}`、`templates\mcp\cordis.patch.yml`

**核心 API 文档（dsh 安装包）**
- `<DSH_INSTALL>\resources\app.asar\dsh\node_modules\@deepseek-ai\dsh-tools\README.md`（defineTool、pipeline、错误/取消、token/KV、deferLoading）
- `...\@deepseek-ai\dsh-tool-fs\README.md` + `lib\index.js`（read/read_image/write/edit、工具实现样板、Config/apply/inject/name 导出）
- `...\@deepseek-ai\dsh-commands\README.md`、`...\@deepseek-ai\dsh-client-ui-commands\README.md`（slash 命令 Host/Client 两侧）
- `...\@deepseek-ai\dsh-agent\README.md`（followup/steer/inject/agent.ctx/agent events）
- `...\@deepseek-ai\dsh-attachment-local\README.md`（图片限制/归一化/存储路径）
- `...\@deepseek-ai\dsh-spill-policy\README.md`、`...\dsh-compaction-tool-result-pruner\README.md`、`...\dsh-compaction-basic\README.md`、`...\dsh-output-retention\README.md`（token 优化）
- `...\@deepseek-ai\dsh-skill\README.md`、`...\dsh-tool-skill\README.md`（skill 懒加载/可调用 skill）
- `...\@deepseek-ai\dsh-host-webserver\README.md`、`...\dsh-subprocess\README.md`（HTTP/WS 路由、子进程/PTY seam）
- `...\@deepseek-ai\dsh-mcp-client\README.md`（MCP 替代路线）
- `...\@deepseek-ai\dsh-plugin-manager\README.md`（安装/HMR/版本检查/失败回滚）
- `...\@deepseek-ai\dsh-cordis-host-runner\README.md`（动态插件/VM 沙箱语义，区别于持久 bundle）

**运行时 inspect 契约（本次查询）**
- `Service: tools`（ToolDefinition/ToolOutputDefinition/ToolSchema/ToolExecutionResult）、`Service: commands`、`Service: attachments`、`Service: webServer`、`Service: systemPrompt`、`Service: agents`、`Service: compaction`、`Service: toolResultPruner`、`Service: tokenMeter`、`Service: spillStore`、`Tool: listTools`、`Config: listConfigs`（199 行目录）

**本机 profile / 现网插件**
- `<USER_HOME>\.dsh\profiles\desktop\package.json`、`cordis.yml`、`cordis.patch.yml`
- `<WORKSPACE_ROOT>\MC模组开发\plugin\minecraft-mod-dev\{package.json,cordis.patch.yml,index.js}`（可照抄的 Host 插件 + 子进程 + 本地 HTTP 探针样板）
- 实测：`read_image` 读取 `<WORKSPACE_ROOT>\输入法皮肤\03-皮肤工程\复刻-雷电将军\preview\render.png` → 图片进入当前模型上下文（`<USER_HOME>\.dsh\attachments\v1\objects\60\604e25b6…`）

