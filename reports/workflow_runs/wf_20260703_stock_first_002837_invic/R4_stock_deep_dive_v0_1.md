# R4 Stock Deep Dive v0.1 - 002837 英维克

## 1. Metadata

| field | value |
|---|---|
| company_id | cn_002837_invic |
| stock_code | 002837 |
| company_name | 英维克 |
| report_date | 2026-07-03 |
| workflow_run_id | wf_20260703_stock_first_002837_invic |
| evidence_snapshot | annual_report + structured metric packs + R4 reconciliation packs |
| data_layer_status | accepted_with_todos |
| quality_status | bridge_only |
| linked_segments | ai_server_liquid_cooling |

## 2. 一句话结论

- 事实: 官方摘要披露公司存在数据中心、算力设备及液冷相关产品线索，且披露 2025 年公司级收入、归母净利、经营现金流、EPS、ROE 等公司级指标。
- 推断: 这些产品线索支持继续跟踪 AI 服务器液冷相关暴露，但尚不能推出液冷收入占比、利润占比或订单贡献。
- 关键假设: 后续定期报告或公告需要补充可定位的分业务收入、订单、客户或产能证据。
- 最大风险: official_financial_reconciliation.csv 存在 mismatch rows，业务分部仍有 MISSING_DISCLOSURE，R4 gate 当前只能给出 bridge_only。

## 3. 公司财务质量

公司级财务指标已完成第一轮 official reconciliation。mismatch 与 official_missing 不被静默处理，未经过 quality-review 的结构化指标仍是 metric candidate。

| metric | period | structured | official | status | evidence |
| --- | --- | --- | --- | --- | --- |
| total_revenue | 20251231 | 3520000000 | 6067759091.55 | mismatch | ev_annual_report_002837_20260421_ce7f64 |
| n_income_attr_p | 20251231 | 450000000 | 521914773.00 | mismatch | ev_annual_report_002837_20260421_ce7f64 |
| basic_eps | 20251231 | 0.62 | 0.54 | mismatch | ev_annual_report_002837_20260421_ce7f64 |
| operating_cash_flow | 20251231 | structured_missing | 157273222.36 | structured_missing | ev_annual_report_002837_20260421_ce7f64 |
| total_assets | 20251231 | structured_missing | 7747255663.66 | structured_missing | ev_annual_report_002837_20260421_ce7f64 |
| roe | 20251231 | structured_missing | 16.58 | structured_missing | ev_annual_report_002837_20260421_ce7f64 |

## 4. 业务拆分

业务拆分来自官方年报摘要文本。当前可以记录产品线索和一条储能应用收入披露，但液冷业务收入占比、液冷毛利率和 AI 服务器液冷利润贡献继续缺失。

| reported segment | mapped segment | metric | value | status | locator |
| --- | --- | --- | --- | --- | --- |
| 机房温控节能产品 | ai_server_liquid_cooling | data_center_liquid_cooling_product_line | product_line_clue | product_line_clue | page:2; section:报告期主要业务或产品简介 |
| 机房温控节能产品 | ai_server_liquid_cooling | liquid_cooling_revenue_pct | MISSING_DISCLOSURE | missing_disclosure | missing_disclosure |
| 机房温控节能产品 | ai_server_liquid_cooling | liquid_cooling_gross_margin | MISSING_DISCLOSURE | missing_disclosure | missing_disclosure |
| 储能应用 | energy_storage_thermal_management_candidate | energy_storage_application_revenue | 1700000000 | reviewed_official | page:2; section:机柜温控节能产品 |
| 电子散热业务 | ai_server_liquid_cooling | server_liquid_cooling_customer_product_clue | product_line_clue | product_line_clue | page:3; section:电子散热业务 |
| 机柜温控节能产品 | energy_storage_thermal_management_candidate | cabinet_cooling_revenue_growth_text | narrative_only | narrative_only | page:3; section:机柜温控节能产品 |

## 5. 细分暴露

细分暴露只记录证据支持的产品层线索。revenue_pct 与 profit_pct 缺失时必须保持 MISSING_DISCLOSURE。

| segment_id | exposure_type | score | revenue_pct | profit_pct | confidence |
| --- | --- | --- | --- | --- | --- |
| ai_server_liquid_cooling | product | 2 | MISSING_DISCLOSURE | MISSING_DISCLOSURE | medium |

## 6. 估值上下文

估值字段只作为市场上下文，不形成交易动作。

| field | value | source_evidence_id |
| --- | --- | --- |
| price | 32.50 | ev_structured_market_data_002837_20260701_daa823 |
| market_cap | 2418000 | ev_structured_market_data_002837_20260701_daa823 |
| pe_ttm | 38.2 | ev_structured_market_data_002837_20260701_daa823 |
| pe_forward | TODO_MARKET_DATA | ev_structured_market_data_002837_20260701_daa823 |
| pb | 4.1 | ev_structured_market_data_002837_20260701_daa823 |
| ps | 6.7 | ev_structured_market_data_002837_20260701_daa823 |
| turnover_rate | 2.35 | ev_structured_market_data_002837_20260701_daa823 |

Peer context:

| stock_code | company_name | pe_ttm | pe_forward | pb | ps | status |
| --- | --- | --- | --- | --- | --- | --- |
| 002837 | 英维克 | 38.2 | TODO_MARKET_DATA | 4.1 | 6.7 | context_only |
| 301018 | 申菱环境 | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | context_only |
| 300499 | 高澜股份 | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | context_only |
| 300731 | 科创新源 | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | context_only |
| 300602 | 飞荣达 | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | context_only |

## 7. 技术/市场状态观察

技术快照只描述市场状态，不输出操作指令。

| field | value | status |
| --- | --- | --- |
| close | 32.5 | market_state_observation |
| ma5 | 32.02 | market_state_observation |
| ma10 | 31.19 | market_state_observation |
| ma20 | INSUFFICIENT_PRICE_WINDOW | market_state_observation |
| ma60 | INSUFFICIENT_PRICE_WINDOW | market_state_observation |
| trend_status | above_ma5 | market_state_observation |

## 8. 催化剂

催化剂只写事件窗口和待验证事项。

| date_window | event | impact_variable | evidence |
| --- | --- | --- | --- |
| next_reporting_window | 下一期定期报告或经营更新 | 收入增速、毛利率、现金流、分业务披露 | claim_cn_002837_invic_28149e07,claim_cn_002837_invic_e9580358,claim_cn_002837_invic_013e4cab |

## 9. 风险与反证

风险:

- 分业务收入和液冷收入占比缺失，不能把公司整体收入归因到液冷。
- 结构化财务指标来自公司整体，不能替代官方披露中的业务暴露证据。

反证清单:

- 如果后续年报/公告未继续披露相关产品或订单，产品暴露判断需下调。
- official reconciliation mismatch rows may indicate fixture or field-period drift.
- Business segment disclosure does not yet quantify liquid-cooling revenue_pct.
- Market valuation context can be stale or fixture-limited.

## 10. Source gaps

Source gaps are preserved in `R4_source_gap_report.md` and include the carried-forward `remaining_source_gaps_after_data_layer_bridge.md` content.

| gap | status |
|---|---|
| DLBR-001 | partial reconciliation completed with review TODO |
| DISCLOSURE-SEGMENT-001 | TODO_SOURCE_REQUIRED |
| DISCLOSURE-SEGMENT-002 | MISSING_DISCLOSURE |
| R4-GAP-001 | MISSING_DISCLOSURE |

## 11. 跟踪清单

| watch_item | next_evidence | owner |
|---|---|---|
| official reconciliation mismatch review | annual/interim/quarterly table extraction | quality-review |
| liquid-cooling revenue_pct | official segment/product revenue table | evidence-ingest |
| liquid-cooling gross margin | official segment/product margin table | evidence-ingest |
| peer market context | manual live smoke or refreshed fixture | evidence-ingest |

研究边界: 本文件用于证据管理和研究流程，不构成交易动作或组合配置指令。
