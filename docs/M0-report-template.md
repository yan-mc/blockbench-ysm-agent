# M0 · 可行性 Spike 报告（模板）

> 用途：M0 是 **Go / No-Go** 关卡。完成本表并附 5 张机位 PNG 与性能数据后，才能进入 M1。
> 状态：**未执行**（本仓库当前只完成设计与源码级研究；请在有 Node/npm/Electron 的目标机执行）。

## 1. 环境

| 项 | 值 |
|---|---|
| 日期 / 执行人 | |
| OS / 版本 | |
| CPU / GPU / 驱动 | |
| 显示器 / 是否远程桌面 | |
| Node / npm | |
| Blockbench tag / commit | |
| Electron 版本 | |

## 2. 构建

- [ ] `npm ci` 成功（记录耗时）
- [ ] `npm run build-electron` 成功（记录产物大小）
- [ ] `node prototype/blockbench-agent/build.mjs` 成功
- [ ] BAE 以 `show:false` 启动，任务栏无窗口
- [ ] bridge 插件注入成功（日志 `bridge plugin: injected`）
- [ ] dsh 工具 `bb_session_status` 返回 connected

## 3. 渲染

| 机位 | 分辨率 | 是否非空 | 尺寸正确 | alpha 存在 | 耗时 ms |
|---|---|---|---|---|---|
| front | 768×768 | | | | |
| back | 768×768 | | | | |
| left | 768×768 | | | | |
| right | 768×768 | | | | |
| iso_fr | 768×768 | | | | |
| closeup | 512×512 | | | | |

- [ ] 连续渲染 50 次无崩溃/context lost
- [ ] 内存增长：______ MB（目标 <200MB）
- [ ] `show → hide → 再渲染` 正常
- [ ] `--disable-gpu` / SwiftShader 可出图（耗时 ______ ms）
- [ ] 空图检测逻辑能识别全透明/全黑图

## 4. 启动/静默

- [ ] 离线启动 ≤8s（外部请求被拦截）
- [ ] 无自动更新/插件商店请求
- [ ] 无 native 对话框卡死
- [ ] 启动后 1s 内进入工作区（无启动屏依赖）
- [ ] 窗口 close → 隐藏而非退出

## 5. 结论

- Go / No-Go：______
- 若 No-Go，触发条件与备选方案（OSR / 透明窗口 / 虚拟屏 / Linux xvfb）：
- 遗留问题 / 需要在 M1 处理的项：

## 6. 附件

- `artifacts/renders/...` 5 张 PNG
- `logs/agent.log`、`logs/bridge.jsonl`
- 性能原始数据（CSV/JSON）
