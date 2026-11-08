# Release 0.9.4 · 2026-11-08

> DSH × Blockbench Agent：隐藏建模 · 无头渲染 · 像素贴图 · 动画 · YSM 导出

## 亮点

- **44 个 `bb_*` 工具定义 / 42 个默认暴露**，5 个命令、1 个 Skill、56 个 bridge 方法 / 7 事件 / 22 错误码。
- **参考图管线 T3 > T2 > T1**：Nano Banana Pro 三视图/拆解板（付费 key，可降级 T2/T1）、See-through 29 语义层、SAM2 轻量分割。
- **视觉闭环**：编辑即看、isolate 局部、多格拼图、环绕转台、动画采样、watchdog-v2。
- **完整 YSM 交付**：创建/打开/保存/校验/导出目录+zip；检查点/回滚；303 动画与控制器可保留。
- **案例模型 v7**：丰川祥子「旋律的主人」**72 骨 / 1182 块 / 2×512 贴图 / 303 动画**；裙体对齐 + 斜面截断锥、头发全覆盖平滑化；`bb_validate` 0 error。
- **发布包**：`bb-agent-0.9.4-*.zip`，含隐藏 BAE、dsh 插件 bundle、文档、契约、SHA256SUMS、INSTALL。

## 校验

- 单元测试 **84/84**（7 个 `*.test.mjs`）。
- host-smoke **35 步**（schema lint 42 工具）。
- 契约：`spec/tool-manifest.json` **44 工具**；`spec/bridge-methods.json` **56/7/22**；`generate_spec.py` 重跑 0 diff。
- 模型：`bb_validate` strict 0 error（3 个已知 warning：512 贴图 ×2、可选 ViewLocator）。

## 安装

```text
plugin_manager install_bundle target=<解压目录>/dsh-blockbench-agent
```

配置参考 `INSTALL.md` 与 `docs/SETUP.md`。**API key 只放本机 dsh profile / 环境变量，不要写进仓库。**

## 资产

- `bb-agent-0.9.4/<...>/`：BAE + 插件 + 文档 + 契约
- `bb-agent-0.9.4-*.zip`：便携发布包（226 文件，约 9.8MB，10,241,125 B）
- `SHA256SUMS.txt`：逐文件校验和

## 许可

BAE 包含 Blockbench 5.2.2（GPL-3.0-or-later）构建产物；dsh 插件为 MIT。详见 `NOTICE.md` 与 `bb-agent-app/SOURCE.txt`。
