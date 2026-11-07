# BAE 工作区（Blockbench Agent Engine workspace）

> 这个目录是 **BAE 的模型工程根目录**。
> 所有 `bb_project_open({pack_dir})` / `bb_session_start({pack_dir})` 的路径都**相对这里**，
> 不是相对仓库根 `F:\Deepseek_harness\blockbench`。

## 现状

**当前没有模型工程** —— 上一个测试模型已按要求清理。

目录里只剩：
- `README.md`（本文件）
- `BUGS.md` —— 插件踩坑记录，交给接手人看
- `.gitignore`

## 怎么新建一个模型

```
bb_session_start({
  mode: "new_ysm",
  name: "my-character",          // 会创建 models/deepseek-fish/my-character/
  resolution: [512, 512],        // 重要：默认是 128，一定要显式指定
})
```

然后 `bb_project_open({pack_dir: "my-character"})` 打开。

## 目录约定（每个 YSM 工程长这样）

```
my-character/
├── ysm.json                 工程清单
├── models/
│   ├── main.json            主模型（bedrock 几何）
│   └── arm.json             第一人称手臂
├── textures/
│   ├── default.png          ★ 主贴图
│   ├── blue.png             备用皮肤
│   └── …
├── animations/
│   └── main.animation.json  动画
└── controller/              控制器
```

`bb_save_project` 会把内存里的模型/动画/贴图写回这个结构，`bb_export_ysm` 再打包成 zip。

## BAE 自己生成的运行时目录（可随时删，不影响工程）

| 目录 | 内容 |
|---|---|
| `.bb/` | 缩略图缓存、undo 等运行时数据（可能很大，几百 MB） |
| `artifacts/renders/` | `bb_render_views` 等渲染产物 |
| `checkpoints/` | `bb_checkpoint` 的 .bbmodel 快照 |
| `exports/` | `bb_export_ysm` 的 zip 产物 |

> 这些都在 `.gitignore` 里，不进仓库。

## 参考语料不在这里

现代 YSM 参考模型在 **`F:\Deepseek_harness\blockbench\material\refmodels\ysm_decoded\`**
（169 个解密工程）。如果要 `bb_project_open` 打开它们，需要先把它们复制到本目录下
并补一个 `ysm.json`（模板见 `F:\Deepseek_harness\blockbench\dist\bb-agent-app\templates\ysm_default\ysm.json`）。

## 交接文档

完整说明见仓库根的 **`HANDOVER.md`**。
