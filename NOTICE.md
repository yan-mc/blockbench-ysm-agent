# NOTICE / 第三方许可

本仓库自有代码与文档采用 MIT（见 LICENSE）。发布包 `release/bb-agent-*.zip` 还包含以下第三方内容：

| 组件 | 许可 | 来源 |
|---|---|---|
| Blockbench（修改构建） | **GPL-3.0-or-later** | https://github.com/JannisX11/blockbench tag `v5.2.2` |
| YSM-Utils-Plugins 默认模型模板 | CC0 / MIT（按其仓库声明） | https://github.com/YesSteveModel/YSM-Utils-Plugins |
| Electron | MIT | https://github.com/electron/electron |
| three.js | MIT | https://github.com/mrdoob/three.js |
| @electron/remote | MIT | https://github.com/electron/remote |

BAE（隐藏 Blockbench Agent Runtime）是 Blockbench 的修改构建；对应源码由两部分组成：

1. 本仓库 `packages/bb-agent-runtime/agent/` 下的 `main.js`、`preload.cjs`、`bb-agent-bridge.js`、`selftest.js`；
2. 上游 Blockbench `v5.2.2` 源码（上述 URL）。

发布包内的 `bb-agent-app/SOURCE.txt` 也包含同样的说明。

## 关于 YSM 模组

本仓库不包含 Yes Steve Model 模组本体。`game-test/` 下用于游戏内验证的脚本仅在本地下载 YSM 模组做兼容性测试，不随发布包分发。使用 YSM 模组请遵守其自身许可。
