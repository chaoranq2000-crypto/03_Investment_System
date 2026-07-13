# Handoff: T2_evidence_acquire_parse -> quality-review

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| current_stage | `T9_bundle8b_close_quality_review` |
| target_skill | `quality-review` |

## Objective

审查 Bundle 8B 的 46 条真实抓取证据、液冷披露 A/B/C 边界、四家同业同口径指标、市场/事件输入、字段漂移和分源代理健康状态，并决定是否允许本地关闭 Bundle 8。不得自动晋升结构化候选、不得重写 Reader、不得把远端 CI 写成已通过。

## Required Inputs

| input | path | notes |
|---|---|---|
| live run log | `live_acquisition_run_log.yaml` | 46 live runs and proxy matrix |
| manifest delta | `R5_bundle8b_evidence_manifest_delta.csv` | 46 unique evidence rows |
| health ledger | `data/manifests/source_health_ledger.yaml` | push2 remains degraded |
| schema issues | `schema_drift_issue_list.csv` | six explicit alias/drift rows |
| disclosure register | `liquid_cooling_disclosure_gap_register.yaml` | 2024 category B; five category C gaps |
| peer pack | `peer_operating_evidence_pack.yaml` | five companies, 45 metrics |
| market/event pack | `market_event_pack.yaml` | technical, valuation, event and analyst context |
| deterministic validation | `R5_bundle8b_close_input_validation.json` | decision=pass |

## Guardrails

- 2024 年约 3 亿元只允许为 `management_comment` / B 类近似口径。
- 2025 液冷收入、液冷毛利、具体客户订单及液冷项目回款继续为 `MISSING_DISCLOSURE`。
- Tushare/Baostock/Eastmoney 新候选保持 `draft`；不得自动写入 reviewed registry。
- 同业指标只比较公司整体经营口径，不做液冷份额或优劣排名。
- 东方财富 `reportapi` 成功与 `push2` 代理失败必须分开记录。

## Completion Criteria

- G1/G2/G3 与 QR-DL 边界通过，无 active critical/high issue。
- 46 条 delta、45 项同业指标、事件日期和液冷口径可由证据重算。
- manifest、candidate、path、route gate、focused tests 和全仓库 tests 通过。
- 所有中低风险 TODO 具有 owner 与 next_action。

## Next Gate

`G10 Close Gate`，owner=`research-orchestrator`。
