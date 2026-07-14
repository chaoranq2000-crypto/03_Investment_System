# Handoff: T2_stock_analysis -> stock-deep-dive

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `normal` |
| current_stage | `T2_stock_analysis` |
| target_skill | `stock-deep-dive` |

## Objective

消费 Bundle 13R 的 T1 reviewed-backfill，复核三个重大业务口径的独立量化暴露及三组两两关系；能证明的关系予以分类，缺少收入/毛利扣减时保留 `missing`，避免液冷主题与机房、机柜产品线重复相加。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| user_request | 执行完成最新补丁包中的计划 | true | 不进入 Reader 或 P2 |
| canonical_docs | `docs/workflows/RESEARCH_WORKFLOW.md` | true | canonical workflow kernel |
| orchestration_spec | `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | true | runtime rules |
| reviewed_backfill | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_reviewed_backfill_input.yaml` | true | T1 已审阅输入 |
| t1_review | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_t1_evidence_review.md` | true | 九个驱动仍为 missing |
| operating_metric_registry | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle12r/R5_bundle12r_operating_metric_registry.csv` | true | 独立暴露 metric IDs |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| t2_review | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_t2_overlap_review.md` | true | 独立暴露、关系、扣减与残差边界 |
| reviewed_backfill | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle13r/R5_bundle13r_reviewed_backfill_input.yaml` | true | 关系与调整字段保持可验证状态 |

## Required Artifacts

| artifact_type | path | required | notes |
|---|---|---:|---|
| annual_report_text | `data/processed/text/002837/cninfo_2025_annual_report_full_002837_2026-04-21.txt` | true | lines 497-528，2025A 产品线收入、成本、毛利率 |
| investor_relations_text | `data/processed/text/ev_official_disclosure_002837_20250423_e78396.md` | true | lines 84-88，2024A 液冷收入管理层表述 |
| bundle12r_question_plan | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle12r/R5_bundle12r_research_question_plan.yaml` | true | overlap acceptance contract |

## Guardrails

- 液冷约 3 亿元为 `management_comment` 的 2024A bounded estimate，不得当作 2025A 审计分部值。
- 机房/机柜 2025A 宽产品线与液冷主题口径不同；没有可核验扣减时不得相加或计算覆盖率。
- `overlaps` 关系需要收入与毛利调整同时资格化后才算 resolved。
- 不新增报告事实、不进入估值、不生成 Reader，`sample_quality_allowed=false`，`p2_allowed=false`。

## Completion Criteria

- 三个重大口径均有独立暴露、metric ID 或明确证据边界。
- 三组两两关系均分类，并给出证据、locator 和 allocation method。
- 两组液冷重叠的收入/毛利调整未获披露时明确标为 `missing`，不伪造数值。
- T2 review 明确 Bundle 12R 是否具备重跑前提。

## Next Gate

| field | value |
|---|---|
| next_gate | `G6` |
| gate_owner | `quality-review` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| R5B13R-T2-001 | high | evidence-ingest | 获取液冷主题计入机房产品线的收入与毛利扣减 |
| R5B13R-T2-002 | high | evidence-ingest | 获取液冷主题计入机柜产品线的收入与毛利扣减 |
