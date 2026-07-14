# Handoff: T1_company_evidence -> evidence-ingest

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `normal` |
| current_stage | `T1_company_evidence` |
| target_skill | `evidence-ingest` |

## Objective

消费 canonical Bundle 12R 的 BF12R-002：复核并补充九个未资格化经营驱动，安全继承已审阅财务分母，形成 Bundle 13R reviewed-backfill 输入；没有新披露时保留 `missing`。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| user_request | 执行完成最新补丁包中的计划 | true | 不进入 Reader 或 P2 |
| canonical_docs | `docs/workflows/RESEARCH_WORKFLOW.md` | true | canonical workflow kernel |
| orchestration_spec | `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | true | runtime rules |
| bundle12r_context | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle12r/` | true | generation `op_evidence_gen_r5_bundle12r_fd5d23c5eb35ac27` |
| evidence_review_ledger | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle12r/R5_bundle12r_evidence_review_ledger.yaml` | true | reviewed source boundaries |
| backfill_template | `templates/r5_bundle13r_reviewed_backfill_input.yaml` | true | canonical 9-question template |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| t1_review | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_t1_evidence_review.md` | true | source search, accepted uses, rejected promotions |
| reviewed_backfill | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_reviewed_backfill_input.yaml` | true | every item qualified or explicitly missing |
| manifest_delta | `data/manifests/evidence_manifest.csv` | false | only when genuinely new source is archived |

## Required Artifacts

| artifact_type | path | required | notes |
|---|---|---:|---|
| bundle13r_baseline_audit | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/baseline_audit.yaml` | true | must be pass |
| bundle12r_question_plan | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle12r/R5_bundle12r_research_question_plan.yaml` | true | 13 questions, 9 T1 driver items |

## Guardrails

- 不得把公司级销量或混合单价升级成机房/机柜分部驱动。
- 不得把累计 1.2GW、约 3 亿元旧期管理层口径推导成 2025A 项目数、单位价值、验收率或毛利率。
- 新来源必须先归档并登记 stable evidence ID 与 locator；无新来源时不制造 manifest 行。
- `sample_quality_allowed=false`，`p2_allowed=false`。

## Completion Criteria

- 九个 T1 响应均包含状态、单位、期间、置信度、来源等级、financial mapping 和缺口触发器。
- 财务分母与已审阅 12R 来源完全一致且有 locator。
- 任何新证据都有 raw/processed/manifest 链；没有新证据时明确记录 source exhaustion。
- reviewed-backfill 通过 Bundle 13R schema/qualification 校验，不以缺口伪造数值。

## Next Gate

| field | value |
|---|---|
| next_gate | `G1` |
| gate_owner | `quality-review` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| R5B13R-T1-001 | high | evidence-ingest | 查找同口径机房/机柜量价与产品组合披露 |
| R5B13R-T1-002 | high | evidence-ingest | 查找液冷单位价值、验收率和独立毛利披露 |
