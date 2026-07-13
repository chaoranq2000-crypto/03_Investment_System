# Handoff: T2 Company Evidence -> evidence-ingest

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `normal` |
| current_stage | `T2 Company Evidence` |
| target_skill | `evidence-ingest` |

## Objective

执行 R5 Bundle 8A/8B 的证据获取韧性与真实缺口补齐：先为英维克 `002837.SZ` 生成 health-aware acquisition queue，再仅通过已启用且有执行权限的 adapter 获取、归档、登记和审查证据。任何无法取得或发行人未披露的数据必须保留为 `MISSING` / `TODO`。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| user_request | 执行完成补丁包的计划 | true | 授权执行包内阶段 A-D；不等于授权提交或推送 |
| canonical_docs | `docs/workflows/RESEARCH_WORKFLOW.md` | true | canonical stage/gate source |
| orchestration_spec | `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | true | runtime and handoff rules |
| source_artifact | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8_quality_gate_report.md` | true | Bundle 8 M3/M4 local gate and TODO boundary |
| source_artifact | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_evidence_plan_from_gaps.yaml` | true | existing gap inventory |
| route_catalog | `config/evidence_source_routes.yaml` | true | Bundle 8A capability routes |
| source_registry | `config/source_registry.yaml` | true | source permissions and adapter status |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| request_plan | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8a_evidence_acquisition_request.yaml` | true | 12 capabilities |
| adapter_queue | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8a_adapter_run_queue_dry_run.yaml` | true | dry-run first; zero blocked capability required |
| source_health_ledger | `data/manifests/source_health_ledger.yaml` | true | health events; no token values |
| live_run_log | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/live_acquisition_run_log.yaml` | true | every attempted/skipped source and result |
| manifest_delta | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/evidence_manifest_delta.csv` | true | append-only evidence linkage |
| schema_drift_issues | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/schema_drift_issue_list.csv` | true | explicit empty result allowed |
| disclosure_gap_register | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/liquid_cooling_disclosure_gap_register.yaml` | true | A/B/C disclosure classification |
| peer_evidence_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/peer_operating_evidence_pack.yaml` | true | comparable scope or visible TODO |
| market_event_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/market_event_pack.yaml` | true | metric/analyst_view/clue boundaries preserved |

## Required Artifacts

| artifact_type | path | required | notes |
|---|---|---:|---|
| manifest | `data/manifests/evidence_manifest.csv` | true | raw/snapshot rows must be registered |
| manifest | `data/manifests/metrics_draft.csv` | true | structured snapshots remain draft metric candidates |
| manifest | `data/manifests/clue_log.csv` | false | D-level outputs only |
| report | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle8_close_quality_report.md` | true | produced only after evidence review |
| readout | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle8_close_readout.md` | true | must not claim missing issuer disclosure exists |

## Guardrails

- 不创建买入、卖出、持有、目标价、仓位或保证收益表述。
- 不把公司整体财务、行情或结构化数据库字段写成液冷分项收入、毛利、客户、订单或回款事实。
- planned adapters `sina_finance`、`baidu_finance`、`cls_market`、`hkex`、`cninfo_ir` 不得获得 live 权限。
- public HTTP 串行执行，遵守间隔、bounded retry、`Retry-After`，且不立即重试 `401/403/404`。
- 原始证据不得覆盖；新版本必须新建并登记 hash。
- `analyst_view`、`management_comment`、`clue`、`estimate` 与 `fact` 必须分离。

## Completion Criteria

- route quality gate 无 critical/high issue，12 个 capability 的 dry-run queue 无阻断。
- 所有实际 acquisition attempt 均有 run log、source health 和 raw/metadata-only 结果。
- 所有可用材料均进入 manifest/candidate 流程，失败、字段漂移和发行人未披露分开登记。
- Bundle 8 close gate 经 `quality-review` 审查；未通过前不得进入 Bundle 9。

## Next Gate

| field | value |
|---|---|
| next_gate | `G1 Evidence Gate` |
| gate_owner | `quality-review` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| `R5B8-G3-001` | medium | evidence-ingest | 检索并审查液冷分项收入、毛利、客户订单和项目回款的正式披露；若不存在则记录 `MISSING_DISCLOSURE` |
| `R5B8A-CI-001` | low | research-orchestrator | 只有用户明确要求提交并推送后才核验远端 CI |
