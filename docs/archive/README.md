# docs/archive · 历史归档

> **这里的文件是历史稿 / 旧证据，不随当前实现维护。**
> 现状以 [HANDOVER.md](../../HANDOVER.md)、[ENGINEERING.md](../../ENGINEERING.md)、[MANUAL.md](../../MANUAL.md) 为准；
> 现行设计文档索引见 [docs/README.md](../README.md)。

## 为什么归档

0.9.1 复核（2026-11-07）后，以下内容被新文档取代或已不再代表真实状态，但保留下来供追溯：

| 文件 | 原位置 | 说明 |
|---|---|---|
| `08-语料挖掘与技能归纳.md` | `docs/` | 早期语料挖掘方法，已被 `docs/20` + `docs/21*` 取代 |
| `09-模型结构深挖.md` | `docs/` | 早期结构分析（样本偏旧），已被 `docs/20` + `docs/21*` 取代 |
| `19-参考模型拆解-脸型眼睛与曲线.md` | `docs/` | 第一轮拆解，样本是女仆移植品，部分结论已被 `docs/20` 修正 |
| `M0-report.md` / `M0-report-safe.md` | `docs/` | 2026-10 的 M0 渲染闸门报告（GPU / SwiftShader 两条路径）；对应 `workspace/_m0*` 产物已清理 |
| `M0-report-template.md` | `docs/` | M0 报告模板，历史工具链遗留 |
| `test-evidence-0.4.0/` | `docs/test-evidence/` | 0.4.0 时期的回归证据（e2e-result、hosttest-result、test-all-final.log、test-quick-after-reorg.log、旧 README） |
| `BUGS-deepseek-fish-testmodel.md` | `models/deepseek-fish/` | 已删除的测试模型「DeepSeek 鲸鱼娘 / 大肥鱼」的 BUG 记录 |
| `cleanup-2026-11-07.md` | — | 2026-11-07 仓库清理记录（删除项/大小/保留理由） |

## 使用注意

- 归档文件里的数字、路径、工具数量**不代表当前状态**，不要据此写新文档或做验收。
- 引用时请注明「历史（归档）」。
- 归档目录统一用 `docs/archive/`；仓库不再使用 `_archive/`（该目录从未提交，已不存在）。
