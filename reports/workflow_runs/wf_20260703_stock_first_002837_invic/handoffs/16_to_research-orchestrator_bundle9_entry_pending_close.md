# Handoff: T9_quality_review -> research-orchestrator

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `normal` |
| current_stage | `T9_quality_review` |
| target_skill | `research-orchestrator` |
| dispatch_status | `pending_bundle8_close_gate` |

## Objective

在 Bundle 8 的 M3/M4 本地输入门通过后，保留独立 close-only patch 与 Bundle 9 调度边界。当前 handoff 只登记下一步，不修改 canonical workflow state、不关闭 Bundle 8，也不启动 Bundle 9。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| user_request | 执行完补丁包中的计划 | true | 本轮只完成 Bundle 8 本地执行链 |
| canonical_docs | `docs/workflows/RESEARCH_WORKFLOW.md` | true | workflow 事实源 |
| orchestration_spec | `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | true | handoff 与 close 规则 |
| integration_gate | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8_research_depth_gate.yaml` | true | `bundle8_research_depth_inputs_ready` |
| quality_report | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8_quality_gate_report.md` | true | 本地决定为 accepted_with_todos |
| quality_issues | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8_quality_issues.csv` | true | 分项披露与未发布 CI TODO 可见 |
| workflow_state | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/workflow_state.yaml` | true | 本轮必须保持原 hash |
| reader_report | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_report_reader_v2.md` | true | 本轮必须保持原 hash |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| bundle8_close_only_patch | `TODO_AFTER_EXPLICIT_PUBLISH_AND_CI` | false | 必须是后续独立任务；本轮不创建 |
| bundle9_execution_plan | `TODO_AFTER_BUNDLE8_CLOSE` | false | M5财务预测与M6估值；本轮不启动 |

## Required Artifacts

| artifact_type | path | required | notes |
|---|---|---:|---|
| evidence_coverage_matrix | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/evidence_coverage_matrix.yaml` | true | 7/7 covered |
| industry_evidence_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/industry_evidence_pack.yaml` | true | demand=2 and supply=2 |
| analysis_pack_v2 | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/analysis_pack_v2.yaml` | true | 7/7 complete |
| integration_readout | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8_research_depth_gate.md` | true | state and Reader immutability recorded |

## Guardrails

- 不创建买入、卖出、持有、目标价、仓位或保证收益表述。
- 不把公司整体财务指标写成液冷分项收入、利润、客户、订单或现金回款。
- 不修改 `workflow_state.yaml`、`open_todos.csv`、canonical index 或现有 Reader 来制造完成状态。
- 不把本地测试替代为 GitHub Actions 已通过；只有明确发布后才能核验远端 CI。
- 不自动 close Bundle 8，不自动启动 Bundle 9，不进入 P2。

## Completion Criteria

- 用户明确授权发布后，变更经过提交、推送且对应 GitHub Actions 全绿。
- 另建 close-only patch，只同步经审查的 Bundle 8 状态并保留所有 TODO。
- close-only patch 通过 truthfulness 与 no-advice 复检后，才由 `research-orchestrator` 显式创建 Bundle 9 handoff。
- 上述条件满足前，本 handoff 保持 `pending_bundle8_close_gate`。

## Next Gate

| field | value |
|---|---|
| next_gate | `G10 Close Gate` |
| gate_owner | `research-orchestrator` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| `R5B8-G3-001` | medium | evidence-ingest | 取得液冷分项收入、毛利、客户订单和项目现金回款的可复算官方口径 |
| `R5B8-QR-CI-001` | low | research-orchestrator | 仅在明确发布后提交推送并核验 GitHub Actions |
