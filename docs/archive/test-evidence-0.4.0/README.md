# 测试证据

| 文件 | 说明 |
|---|---|
| `test-all-final.log` | 2026-10-18 全量回归：assemble / M0 / e2e WS / e2e HTTP+SSE / hosttest / 动画语义 diff，6/6 PASSED |
| `test-quick-after-reorg.log` | 目录重组后的快速回归（hosttest + 动画语义 diff），2/2 PASSED |
| `hosttest-result.json` | Host 插件 30 工具集成冒烟详细步骤 |
| `e2e-result.json` | WebSocket / HTTP+SSE 协议 e2e 详细步骤 |

复现：`npm run test`（全量）或 `npm run test:quick`。
