# 测试证据（当前版本 0.9.1）

> 0.4.0 时期的旧证据已归档到 [`../archive/test-evidence-0.4.0/`](../archive/test-evidence-0.4.0/)，
> 其中的数字与工具数量**不代表当前状态**。

## 0.9.1 复核证据（2026-11-07 19:16）

| 文件 | 说明 |
|---|---|
| `test-all-0.9.1.log` | `npm run test` 全量回归日志：**6/6 PASSED**（assemble / M0 / e2e WS / e2e HTTP+SSE / hosttest / 动画语义 diff） |
| `hosttest-result-0.9.1.json` | host-smoke 详细结果：**35 步全过，schema lint 检查 41 个暴露工具**，5 命令 |
| `e2e-result-0.9.1.json` | 协议 + BAE 端到端结果（创建 YSM 包→建模→贴图→渲染→保存→导出） |
| `animation-diff-0.9.1.json` | 动画语义 diff：模板 302 vs 工作包 303，仅新增 `hosttest_wave`，`equal=true` |
| `M0-2026-11-07.md` | M0 渲染自检报告（隐藏窗口 + 离屏 WebGL，GPU 路径） |

> 本轮实测结论（2026-11-07）：**62/62 单元测试通过**（6 个 `*.test.mjs`：imageprune 13 / refcanon 9 / segprobe 10 / spec 17 / tool-schema 5 / viewsheet 8）；**host-smoke 35 步全过，schema lint 检查 41 个工具**；全量回归 6/6。
> 证据目录 `workspace/` 为 gitignored 运行产物（复跑会重建），复核产物保留在本目录。

## 复现

```powershell
# 单元测试（6 个文件，62 项）
node --test packages/dsh-blockbench-agent/test/*.test.mjs

# Host 插件集成冒烟（真实 schema 校验，41 个暴露工具）
node packages/dsh-blockbench-agent/test/host-smoke.mjs

# 全量回归（assemble → M0 → e2e → hosttest → 动画语义 diff）
npm run test
```

> node 不在 PATH 时用 DSH 自带 node：`C:\Users\28988\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe`
> （也可用 `DSH_RUNTIME_ROOT` 环境变量推导，见 `packages/dsh-blockbench-agent/lib/seglite.js` 的 `pythonCandidates`）。
