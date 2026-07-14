# Handoff: T2_stock_analysis -> quality-review

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `normal` |
| current_stage | `R5_bundle13r_t1_t2_evidence_backflow` |
| target_skill | `quality-review` |

## Objective

复核 Bundle 13R 的 canonical 绑定、证据追溯、claim type、指标字段、独立暴露、重叠双计、回流决策、状态同步和 no-advice 边界，并把未解决项分配给明确 owner。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| canonical_docs | `docs/workflows/RESEARCH_WORKFLOW.md` | true | global gates |
| execution_result | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_backflow_execution_result.yaml` | true | 6 resolved / 11 unresolved / 0 validation blockers |
| generation_lock | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_generation_lock.yaml` | true | deterministic exact-hash lock |
| t1_review | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_t1_evidence_review.md` | true | source refresh and rejected promotions |
| t2_review | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_t2_overlap_review.md` | true | overlap and exposure boundary |
| workflow_state | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/workflow_state.yaml` | true | adapter-synchronized state |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| quality_issues | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_quality_issues.csv` | true | owner, severity and next action |
| quality_report | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_quality_report.md` | true | non-compensating gate result |

## Required Artifacts

| artifact_type | path | required | notes |
|---|---|---:|---|
| baseline_audit | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/baseline_audit.yaml` | true | pass |
| reviewed_backfill | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_reviewed_backfill_input.yaml` | true | reviewed; sample quality/P2 false |
| unresolved_items | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_unresolved_items.csv` | true | exact 11-item queue |

## Guardrails

- 质量结论不得用已解决分母或独立暴露补偿九个 driver 和两组 overlap 缺口。
- 旧 Bundle 11R 人审不得迁移为 Bundle 13R 人审。
- 不执行 Bundle 12R 重跑、估值、Reader 或 P2，除非前置决策真实达到要求。
- 无买卖建议、目标价、仓位或确定收益表达。

## Completion Criteria

- G1/G2/G3/G6/G8/G9 均有明确结果、证据和限制。
- 所有 open high issue 有 owner 与 next action；已修复 preflight critical 保留历史并标为 resolved。
- 技术执行关闭状态与研究资格状态分开表达。

## Next Gate

| field | value |
|---|---|
| next_gate | `G8` |
| gate_owner | `research-orchestrator` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| R5B13R-G3-001 | high | evidence-ingest | 补齐九个同口径经营驱动 |
| R5B13R-G6-001 | high | stock-deep-dive | 获得两组液冷 overlap 的收入与毛利扣减后复核 |
