# Handoff: T1 Company Evidence -> quality-review

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `normal` |
| current_stage | `T1 Company Evidence` |
| target_skill | `quality-review` |

## Objective

对 Bundle 5.1 inventory、dropzone validation、正式 source-request queue 和 evidence manifests 执行 G1 Evidence Gate 审查，判断是否可进入 Card 5.2；不新增研究结论。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| canonical_docs | `docs/workflows/RESEARCH_WORKFLOW.md` | true | G1 唯一事实源 |
| task_card | `codex_tasks/r5_after_bundle4/R5_BUNDLE_5_1_REAL_INPUT_INVENTORY_AND_PROVENANCE_MATRIX.md` | true | stop condition |
| inventory | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_real_input_inventory.yaml` | true | evidence-ingest 输出 |
| dropzone_validation | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_dropzone_validation_initial.json` | true | 计数必须与 inventory 对账 |
| source_request_queue | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_request_queue.yaml` | true | 缺口 owner/next action |
| review_ledger | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_request_review_ledger.yaml` | true | pending/accepted 事实 |
| evidence_manifest | `data/manifests/evidence_manifest.csv` | true | evidence ID 与物理路径解析 |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| gate_decision | `reports/p1_6/R5_BUNDLE_5_1_REAL_INPUT_INVENTORY_READOUT.md` | true | 由编排器记录审查结论 |

## Required Artifacts

| artifact_type | path | required | notes |
|---|---|---:|---|
| inventory_test | `tests/test_r5_bundle5_real_input_inventory.py` | true | fail-closed 合同 |

## Guardrails

- `checked_files=0`、`record_count=0` 必须判 evidence source-gapped，即使 validator status 为 pass。
- accepted 记录必须能解析到真实 manifest evidence 和物理 source path，并有非占位 reviewer metadata。
- 同 hash 的年报路径只能作为 provenance alias/conflict，不可算两份独立 accepted evidence。
- workflow-local `local_tushare_fixture` 只能是 metric fixture/draft，不能计为真实 reviewed market/peer input。
- high evidence/reviewer/source gap 阻塞 Card 5.2；不得以 TODO 降级绕过。
- no-advice、sample-quality=false、p2=false。

## Completion Criteria

- 给出 G1 `pass` 或 `fail`，并列出每个 high issue 的 owner、目标产物与 next action。
- 若 core coverage 小于 5/5 或 reviewer/evidence metadata 不足，结论必须为 `blocked_source_gapped`，promotion 不允许。

## Next Gate

| field | value |
|---|---|
| next_gate | `G1 Evidence Gate` |
| gate_owner | `quality-review` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| `B5-G1-001` | high | `evidence-ingest` + authorized reviewer | 补齐真实 reviewed input、evidence anchor 与 reviewer metadata |
