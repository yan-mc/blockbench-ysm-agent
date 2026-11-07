# NOTICE / 第三方许可

本仓库自有代码与文档采用 MIT（见 LICENSE）。若把 BAE（`dist/bb-agent-app`）与插件一并分发，发布包还包含以下第三方内容：

| 组件 | 许可 | 来源 |
|---|---|---|
| Blockbench（修改构建） | **GPL-3.0-or-later** | https://github.com/JannisX11/blockbench tag `v5.2.2` |
| YSM-Utils-Plugins（含默认模型模板 assets/default） | **MIT**（默认模型按官方声明为 **CC0**） | https://github.com/YesSteveModel/YSM-Utils-Plugins tag `v2.6.0` |
| Electron | MIT | https://github.com/electron/electron |
| three.js | MIT | https://github.com/mrdoob/three.js |
| @electron/remote | MIT | https://github.com/electron/remote |

BAE（隐藏 Blockbench Agent Runtime）是 Blockbench 的修改构建；对应源码由两部分组成：

1. 本仓库 `packages/bb-agent-runtime/agent/` 下的 `main.js`、`preload.cjs`、`bb-agent-bridge.js`、`selftest.js`；
2. 上游 Blockbench `v5.2.2` 源码（上述 URL）。

发布包内的 `bb-agent-app/SOURCE.txt` 也包含同样的说明。

## 参考语料

`material/` 下的参考模型/贴图来自第三方社区，**版权归原作者所有**，仅本地研究使用（已 gitignore，不随仓库或发布包分发）。
使用其风格/结构做学习参考时请遵守原作者的许可与社区规范。

## 关于 YSM 模组

本仓库不包含 Yes Steve Model 模组本体，也不自带游戏测试环境（旧的 `game-test/` 已删除）。
游戏内加载验证需要自备 Minecraft/Forge/YSM 环境；使用 YSM 模组请遵守其自身许可。
