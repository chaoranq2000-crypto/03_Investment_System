# R4 Stock Deep Dive v0.2 - 002837 英维克

## 1. Metadata

| field | value |
|---|---|
| company_id | cn_002837_invic |
| stock_code | 002837 |
| company_name | 英维克 |
| report_date | 2026-07-03 |
| workflow_run_id | wf_20260703_stock_first_002837_invic |
| evidence_snapshot | official annual-report summary, structured metric packs, R4 review decisions |
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

| metric | status | decision | promotion_allowed |
| --- | --- | --- | --- |
| total_revenue | mismatch | reviewed_no_structured_promotion | false |
| n_income_attr_p | mismatch | reviewed_no_structured_promotion | false |
| gross_margin | official_missing | explicit_official_missing | false |
| net_margin | official_missing | explicit_official_missing | false |
| basic_eps | mismatch | reviewed_no_structured_promotion | false |
| operating_cash_flow | structured_missing | official_available_structured_missing | false |
| total_assets | structured_missing | official_available_structured_missing | false |
| total_liabilities | official_missing | explicit_official_missing | false |
| roe | structured_missing | official_available_structured_missing | false |
| debt_to_asset | official_missing | explicit_official_missing | false |

## 4. Liquid-cooling Exposure Evidence Review

液冷证据升级审查完成。结论是 product_line_clue 可用于 product exposure，收入与利润披露仍缺失。

| review_decision | count |
| --- | --- |
| clue_only_not_backflowable | 1 |
| not_ai_server_liquid_cooling_revenue | 1 |
| still_missing_disclosure | 2 |
| supports_product_exposure_only | 2 |

| metric | evidence_class | decision | allowed_exposure_type |
| --- | --- | --- | --- |
| data_center_liquid_cooling_product_line | product_line_clue | supports_product_exposure_only | product |
| liquid_cooling_revenue_pct | missing_disclosure | still_missing_disclosure | none |
| liquid_cooling_gross_margin | missing_disclosure | still_missing_disclosure | none |
| energy_storage_application_revenue | disclosed_revenue | not_ai_server_liquid_cooling_revenue | none |
| server_liquid_cooling_customer_product_clue | product_line_clue | supports_product_exposure_only | product |
| cabinet_cooling_revenue_growth_text | narrative_only | clue_only_not_backflowable | none |

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

估值和 peer 表只提供市场上下文，不形成排名、交易动作、价格指令或 exposure proof。当前 `company-valuation` 输出仍显示 `TODO_MARKET_DATA` / `TODO_PEER_DATA`，因此本节不写入未被 `valuation/valuation_snapshot.yaml` 支撑的 PE、PB、PS、市值或价格数字。

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
| valuation/valuation_model.yaml | TODO_MARKET_DATA / TODO_PEER_DATA / TODO_FORECAST_MODEL_NET_PROFIT | estimate / inference only |
| valuation/valuation_snapshot.yaml | market_data: MISSING; multiples: MISSING | market context only |
| valuation/peer_comparison.csv | TODO_PEER_DATA | no peer ranking |
| valuation/sensitivity_table.csv | TODO_VALUATION_CONTEXT | no trading action |

## 7. Technical And Market State

技术快照只描述市场状态。

| window | fields |
| --- | --- |
| daily | ma5,ma10,ma20,ma60,pct_chg_20d,pct_chg_60d,volume_ratio |
| weekly | ma5,ma10,ma20 |

## 8. Risks And Counter Evidence

- disclosure_gap: 液冷收入与利润指标仍缺官方直接披露。
- metric_reconciliation: 结构化指标与官方口径有 mismatch，已复核但未晋升。
- exposure_boundary: product exposure 不能外推为 revenue 或 profit exposure。
- market_context: 估值、技术、peer 数据可能受 fixture 或日期限制。

## 9. Source Gaps And Follow-up

详见 `R4_source_gap_report_v0_2.md` 与 `R4_open_questions_v0_2.md`。

| item | status | owner |
|---|---|---|
| official review decisions | resolved_review_completed | quality-review |
| liquid-cooling revenue_pct | MISSING_DISCLOSURE | evidence-ingest |
| liquid-cooling profit_pct | MISSING_DISCLOSURE | evidence-ingest |
| product-only backflow | resolved_product_only_update | segment-company-mapping |

研究边界: 本文件用于研究流程和证据管理，不构成交易或配置指令。
