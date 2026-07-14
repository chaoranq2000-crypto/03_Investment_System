# Handoff: R5_bundle13r_quality_review -> research-orchestrator

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `normal` |
| current_stage | `R5_bundle13r_t1_t2_evidence_backflow` |
| target_skill | `research-orchestrator` |

## Objective

按 Bundle 13R 允许状态 `R5_BUNDLE13R_BACKFLOW_IN_PROGRESS` 完成技术关闭，固化 6 个 resolved、11 个 unresolved、0 个 validation blocker 的真实结果，并保持 12R 重跑、估值、Reader 与 P2 关闭。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| execution_result | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_backflow_execution_result.yaml` | true | canonical decision |
| quality_report | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_quality_report.md` | true | quality outcome needs_fix |
| quality_issues | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_quality_issues.csv` | true | four open high research gaps |
| generation_lock | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_generation_lock.yaml` | true | validated and deterministic |
| verification | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_verification_summary.yaml` | true | final test and boundary summary |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| close_readout | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_close_readout.md` | true | allowed technical close state |
| state_surfaces | `workflow_state.yaml`, `run_log.md`, `artifact_manifest.csv`, `open_todos.csv` | true | one canonical decision |
| canonical_index | `config/r5_readout_canonical_index.yaml`, `reports/p1_6/R5_READOUT_CANONICAL_INDEX.md` | true | Bundle 13R readout registered |

## Required Artifacts

| artifact_type | path | required | notes |
|---|---|---:|---|
| baseline_audit | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/baseline_audit.yaml` | true | pass |
| unresolved_items | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_unresolved_items.csv` | true | exact remaining queue |
| state_backup | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/workflow_state.yaml.pre_bundle13r_20260715.bak` | true | pre-13R single-file backup |

## Guardrails

- 技术执行链完成不等于经营证据 requalified。
- 不执行生成的 12R 重跑命令，因为前置决策为 false。
- 不启动 `company-valuation`，不生成 Reader，不继承旧人审。
- 不提交、不推送；`sample_quality_allowed=false`、`p2_allowed=false`。

## Completion Criteria

- run/state/manifest/TODO/quality/index/readout 指向同一 13R decision 和 generation。
- 最终回归、lock、determinism、schema、diff 检查均通过。
- 11 个 unresolved item 有 owner 和下一 trigger。

## Next Gate

| field | value |
|---|---|
| next_gate | `G8` |
| gate_owner | `research-orchestrator` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| R5B13R-DRIVER-001 | high | evidence-ingest | 新同口径发行人披露出现后从 T1 复跑 |
| R5B13R-OVERLAP-001 | high | stock-deep-dive | 收入/毛利扣减证据齐备后从 T2 复跑 |
