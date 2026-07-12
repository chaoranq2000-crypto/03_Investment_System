# Handoff: T2_evidence_acquire_parse -> evidence-ingest

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `normal` |
| current_stage | `T2_evidence_acquire_parse` |
| target_skill | `evidence-ingest` |

## Objective

为 Bundle 8 建立真实、已审查、按 `underlying_source_id` 去重的 source catalog，补齐公司经营、独立行业需求/供给、至少三家同业经营数据和反向证据，并生成可重复构建的 evidence coverage matrix 与三类 source-only handoff packs。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| user_request | 执行完补丁包中的计划 | true | 只执行 Bundle 8 M3/M4，不进入 Bundle 9/P2 |
| canonical_docs | `docs/workflows/RESEARCH_WORKFLOW.md` | true | canonical workflow/gate 事实源 |
| orchestration_spec | `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | true | handoff 与状态边界 |
| bundle_plan | `reports/p1_6/R5_BUNDLE_8_0_RESEARCH_DEPTH_PLAN.md` | true | Bundle 8 最低门槛 |
| source_manifest | `data/manifests/evidence_manifest.csv` | true | 只复用 reviewed/accepted 来源 |
| claims_registry | `data/manifests/claims_registry.csv` | true | claim 引用需可解析 |
| metrics_registry | `data/manifests/metrics_registry.csv` | true | metric 引用需含口径和来源 |
| bundle7_backflow | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle7_quality_backflow_plan.yaml` | true | 接收四个 M3/M4 blocker |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| source_catalog | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8_evidence_source_catalog.yaml` | true | 示例来源不得进入真实 catalog |
| coverage_matrix | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/evidence_coverage_matrix.yaml` | true | 必须由构建器生成 |
| industry_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/industry_evidence_pack.yaml` | true | source-only |
| peer_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/peer_operating_pack.yaml` | true | 至少三家 peer entity |
| company_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/company_operating_evidence_pack.yaml` | true | 不推断液冷收入占比 |

## Guardrails

- 原始文件只新增版本，不覆盖 `data/raw/` 既有内容。
- 搜索结果摘要不能直接升级为 reviewed evidence；必须归档原始官方文件并保留页码。
- 同一文档的多个摘录只按一个 `underlying_source_id` 计数。
- 发行人材料不满足独立行业来源门槛。
- 结构化财务数据仅支持 metric/context，不证明液冷收入、客户或订单。
- 保留技术路线替代、政策多路径和口径不可比等反向证据。
- 不生成买入、卖出、持有、目标价或仓位建议。

## Completion Criteria

- 7/7 blocking coverage rows 为 `covered`。
- reviewed underlying sources 至少 7 个，independent underlying sources 至少 4 个。
- 行业需求和供给/竞争各至少 2 个独立底层来源。
- peer operating evidence 覆盖至少 3 家独立 peer entity。
- 所有新增 source、claim、metric 路径和 locator 可复核。
- `scripts/build_r5_evidence_coverage_matrix.py` 非 `--allow-blocked` 模式返回 0。

## Next Gate

| field | value |
|---|---|
| next_gate | `G1 Evidence Gate` |
| gate_owner | `quality-review` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| `R5Q-B7-44F6297D` | medium | evidence-ingest | 补齐独立底层研究来源并生成 coverage matrix |
| `R5Q-B7-E54AC257` | medium | evidence-ingest | 补齐至少三家同业经营证据 |
| `P2-BLOCK-002` | medium | evidence-ingest | 液冷收入/利润占比继续保留 `MISSING_DISCLOSURE`，不在 Bundle 8 猜测 |
