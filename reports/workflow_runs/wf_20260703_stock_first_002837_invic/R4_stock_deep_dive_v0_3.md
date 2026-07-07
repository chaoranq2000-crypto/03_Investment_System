# R4 Stock Deep Dive v0.3 - 002837 英维克

## 1. Metadata

| field | value |
|---|---|
| company_id | cn_002837_invic |
| stock_code | 002837 |
| company_name | 英维克 |
| report_date | 2026-07-03 |
| workflow_run_id | wf_20260703_stock_first_002837_invic |
| evidence_snapshot | official annual-report summary, structured metric packs, valuation input enrichment |
| quality_status | publishable_ready_with_disclosure_todos |
| linked_segments | ai_server_liquid_cooling |

## 2. 一句话结论

- fact: 官方披露支持公司级财务指标和数据中心/液冷相关产品线索；结构化指标仍按 metric-only 使用。
- inference: 当前证据支持 product exposure 的继续跟踪，不支持 revenue_pct、profit_pct 或订单贡献量化。
- assumption: 后续若披露更细业务表、公告或投资者关系记录，需要通过 evidence-ingest 登记并复核。
- uncertainty: 液冷业务收入、利润和客户贡献仍为 MISSING_DISCLOSURE。

## 3. Official Reconciliation Review

Mismatch、official_missing 与 structured_missing 均已逐条给出 review_decision；本节不把结构化值晋升为 reported fact。

| review_decision | count |
| --- | --- |
| explicit_official_missing | 4 |
| official_available_structured_missing | 3 |
| reviewed_no_structured_promotion | 3 |

## 4. Liquid-cooling Exposure Evidence Review

液冷证据升级审查完成。结论是 product_line_clue 可用于 product exposure，收入与利润披露仍缺失。

| metric | evidence_class | decision | allowed_exposure_type |
| --- | --- | --- | --- |
| data_center_liquid_cooling_product_line | product_line_clue | supports_product_exposure_only | product |
| liquid_cooling_revenue_pct | missing_disclosure | still_missing_disclosure | none |
| liquid_cooling_gross_margin | missing_disclosure | still_missing_disclosure | none |
| server_liquid_cooling_customer_product_clue | product_line_clue | supports_product_exposure_only | product |

## 5. Segment Exposure And Backflow

个股发现已回写到 segment-company 状态层，但仅限产品暴露证据和备注更新。

| field | value |
|---|---|
| segment_id | ai_server_liquid_cooling |
| exposure_type | product |
| exposure_score | 2 |
| revenue_pct | MISSING_DISCLOSURE |
| profit_pct | MISSING_DISCLOSURE |
| backflow_decision | update_exposure |

## 6. Valuation And Peer Context

估值和 peer 表只提供市场上下文，不形成排名、价格指令或 exposure proof。本版已把 input-side 缺口正规化为 parseable 文件：`market_snapshot.csv`、`peer_market_snapshot.csv`、`financial_metric_pack.csv` 与 `valuation_input_readiness.yaml`。由于 market 和 peer 输入仍是 TODO 占位，报告不写入未被 `valuation/valuation_snapshot.yaml` 支撑的 PE、PB、PS、市值或价格数字。

| field | value | source |
| --- | --- | --- |
| current_price | TODO_MARKET_DATA | valuation/valuation_snapshot.yaml#market_data.current_price |
| market_cap | TODO_MARKET_DATA | valuation/valuation_snapshot.yaml#market_data.market_cap |
| pe_ttm | TODO_MARKET_DATA | valuation/valuation_model.yaml#static_valuation.metrics.pe_ttm |
| pe_forward | TODO_FORECAST_MODEL_NET_PROFIT | valuation/valuation_model.yaml#dynamic_valuation.metrics |
| pb | TODO_MARKET_DATA | valuation/valuation_model.yaml#static_valuation.metrics.pb |
| ps | TODO_MARKET_DATA | valuation/valuation_model.yaml#static_valuation.metrics.ps |
| valuation_context_label | not_assessable | valuation/valuation_snapshot.yaml#labels.valuation_context_label |

| source_artifact | status | boundary |
| --- | --- | --- |
| market_snapshot.csv | TODO_MARKET_DATA | parseable placeholder only |
| peer_market_snapshot.csv | TODO_PEER_DATA | parseable placeholder only |
| financial_metric_pack.csv | partial | company-level metric-only support |
| valuation/valuation_model.yaml | TODO_MARKET_DATA / TODO_PEER_DATA / TODO_FORECAST_MODEL_NET_PROFIT | estimate / inference only |
| valuation/valuation_snapshot.yaml | market_data: MISSING; multiples: MISSING | market context only |
| valuation/peer_comparison.csv | TODO_PEER_DATA | no peer ranking |
| valuation/sensitivity_table.csv | TODO_VALUATION_CONTEXT | no action language |

## 7. Technical And Market State

技术快照只描述市场状态，不作为 segment exposure proof。

## 8. Risks And Counter Evidence

- disclosure_gap: 液冷收入与利润指标仍缺官方直接披露。
- metric_reconciliation: 结构化指标与官方口径有 mismatch，已复核但未晋升。
- exposure_boundary: product exposure 不能外推为 revenue 或 profit exposure。
- market_context: 估值、技术、peer 数据仍受 TODO 输入限制。
- valuation_input_boundary: financial_metric_pack 是公司整体 metric-only 输入，不能替代前瞻利润模型或 peer market data。

## 9. Source Gaps And Follow-up

详见 `R4_source_gap_report_v0_3.md` 与 `R4_open_questions_v0_3.md`。

| item | status | owner |
|---|---|---|
| valuation input files | resolved_to_parseable_inputs | stock-deep-dive |
| market valuation snapshot | TODO_MARKET_DATA | evidence-ingest |
| peer market snapshot | TODO_PEER_DATA | evidence-ingest |
| forward net profit EPS margin model | TODO_FORECAST_MODEL_NET_PROFIT | stock-deep-dive |
| liquid-cooling revenue_pct | MISSING_DISCLOSURE | evidence-ingest |
| liquid-cooling profit_pct | MISSING_DISCLOSURE | evidence-ingest |

研究边界: 本文件用于研究流程和证据管理，不构成操作指令。
