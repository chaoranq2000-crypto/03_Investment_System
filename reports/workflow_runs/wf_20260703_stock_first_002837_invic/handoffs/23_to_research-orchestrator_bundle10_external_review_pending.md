# Handoff: quality-review -> research-orchestrator

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| current_stage | `R5_bundle10_quality_review` |
| target_skill | `research-orchestrator` |
| dispatch_status | `ready_for_external_human_review` |

## Decision

Bundle 10 自动化候选为 `accepted_with_todos`：Reader 质量门 98 分、truthfulness 通过、零 blocker，动态 Writer 与两个跨行业合成样本的身份、引用和叙事质量回归通过；三域独立 AI 子 agent 复审也建议通过，但不构成外部真人签署。外部人工复核仍未发生，因此 Bundle 10 不能标记最终关闭，样例质量与 P2 许可继续为 false。

本地全仓库回归：`637 passed, 2 skipped`。

## Required State Synchronization

- `workflow_state.yaml`：当前阶段切换为 `R5_bundle10_external_human_review_pending`。
- v3 Reader 与 scorecard 成为当前候选；v2 作为历史 research_draft 保留。
- 关闭 Bundle 7 的 Reader 密度、情绪和事件链旧问题；保留液冷披露、估值方法、情绪来源与外部人工复核 TODO。
- 登记 Bundle 10 产物并追加 run log。
- 不提交、不推送、不声明远端 CI。

## External Gate

真实外部审查者必须确认 handoff 中绑定的 Reader SHA256，并填写 reviewer、reviewed_at、decision 与评论。任何报告变化都会使签署失效并要求重新审查。
