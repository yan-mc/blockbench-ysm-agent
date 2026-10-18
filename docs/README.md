# docs · 分章索引

| 章节 | 内容 | 建议读者 |
|---|---|---|
| [01-总体架构与数据流](01-总体架构与数据流.md) | 设计目标、事实基线、架构图、进程/生命周期、数据流、ADR、目录规范、非功能指标 | 所有人 |
| [02-通信协议规范](02-通信协议规范.md) | WebSocket/HTTP 绑定、JSON-RPC 2.0 扩展、方法目录、错误码、revision/幂等、超时/取消、示例 | 后端/协议 |
| [03-Tool-API-清单](03-Tool-API-清单.md) | 21 个 `bb_*` 工具的参数/返回/错误/Token 预算、工具门控、系统提示词片段 | Agent/工具 |
| [04-闭环状态机](04-闭环状态机.md) | 状态机/正交区域、预算与收敛、VLM 评审协议、缺陷分类、回滚、失败恢复、伪代码 | Agent/QA |
| [05-工程难点与避坑指南](05-工程难点与避坑指南.md) | 隐藏窗口/WebGL、启动/注入、Undo/保存、贴图/UV、YSM 格式、协议并发、Token、Windows、许可 | 工程实现 |
| [06-实施路线图与验收](06-实施路线图与验收.md) | M0–M6 里程碑、测试策略、DoD、发布、团队分工、第一天任务 | 负责人/QA |

**合并版**：`../系统开发与设计方案.md`（由本目录 6 章拼接生成，建议先读合并版，遇细节再回分章）。

**机器可读契约**：`../spec/tool-manifest.json`、`../spec/bridge-methods.json`，由 `../spec/generate_spec.py` 生成。

**研究证据**：`../research/blockbench-core.md`、`../research/ysm-format.md`、`../research/dsh-integration.md`。

**骨架代码**：`../prototype/README.md`。
