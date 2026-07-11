# Handoff: T1 Company Evidence -> evidence-ingest

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `normal` |
| current_stage | `T1 Company Evidence` |
| target_skill | `evidence-ingest` |

## Objective

执行 R5 Bundle 5.1 的本地真实输入清点：核对五类核心 reviewed input 和可选 sentiment 输入，验证 source/evidence/provenance/reviewer 字段，复核正式 source-request queue；不得 promotion。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| user_request | 应用并执行最新补丁包 | true | 按包内 stop condition 执行 |
| canonical_docs | `docs/workflows/RESEARCH_WORKFLOW.md` | true | canonical T1/G1 边界 |
| orchestration_spec | `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | true | runtime/handoff 规则 |
| task_card | `codex_tasks/r5_after_bundle4/R5_BUNDLE_5_1_REAL_INPUT_INVENTORY_AND_PROVENANCE_MATRIX.md` | true | Bundle 5.1 事实边界 |
| expected_manifest | `config/r5_bundle5_expected_artifacts.yaml` | true | producer ownership 与 hard boundary |
| reviewed_input_root | `data/reviewed_inputs/wf_20260703_stock_first_002837_invic` | true | 缺失也必须如实登记 |
| evidence_manifest | `data/manifests/evidence_manifest.csv` | true | 全局证据锚点 |
| workflow_manifest | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/evidence_manifest_delta.csv` | true | workflow-local candidate/fixture 边界 |
| source_request_queue | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_request_queue.yaml` | true | 复核/刷新，不另造 queue |
| review_ledger | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_request_review_ledger.yaml` | true | accepted/pending 事实 |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| inventory | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_real_input_inventory.yaml` | true | 不得放入 dropzone |
| dropzone_validation | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_dropzone_validation_initial.json` | true | `pass + checked_files=0` 仍为 source-gapped |
| source_request_queue | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_request_queue.yaml` | true | 使用现有正式 builder/contract |
| focused_test | `tests/test_r5_bundle5_real_input_inventory.py` | true | 覆盖 zero-file fail-closed 与 evidence anchor |

## Required Artifacts

| artifact_type | path | required | notes |
|---|---|---:|---|
| readout | `reports/p1_6/R5_BUNDLE_5_1_REAL_INPUT_INVENTORY_READOUT.md` | true | 由编排器在 quality review 后关闭 |

## Guardrails

- 不创建、下载或补写真实数据；本卡只使用已归档本地材料。
- 不伪造 reviewer、reviewed_at、evidence_id、source rank、日期或 limitations。
- validator 的空目录 `pass` 不能解释为输入已就绪。
- 夹具、模板、样例报告、pending/rejected/TODO 不能计为 accepted evidence。
- 不写 canonical registry，不改变 real pilot/render/sample-quality/P2 gate。
- 不输出交易建议。

## Completion Criteria

- inventory 精确覆盖五类 core 与一类 optional input，并包含 nullable provenance/reviewer/freshness/conflict/limitation/missing 字段。
- 每个阻塞 core gap 关联至少一个 source request；缺口无法满足时明确 `blocked_source_gapped`。
- promotion、sample-quality、P2 均为 false。

## Next Gate

| field | value |
|---|---|
| next_gate | `G1 Evidence Gate` |
| gate_owner | `quality-review` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| `B5-REAL-INPUT-001` | high | `evidence-ingest` + authorized reviewer | 提供真实物理输入、证据锚点和审核元数据；缺失时保持 blocked |
