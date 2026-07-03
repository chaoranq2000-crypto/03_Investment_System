# R4 Stock Report Data Layer Bridge Draft

workflow_id: wf_20260703_stock_first_002837_invic
source_data_layer_run: wf_20260703_data_layer_002837_invic
stock_code: 002837
company_id: cn_002837_invic
bridge_status: accepted_with_todos

## 1. Scope

This bridge draft imports data-layer packs into the stock-first workflow as metric context only. It is not a publishable stock report and does not change any business exposure conclusion.

Input packs:

| pack | status |
|---|---|
| `financial_metric_pack.csv` | available |
| `valuation_snapshot.yaml` | available_with_todo |
| `technical_snapshot.yaml` | available_with_todo |
| `peer_market_snapshot.csv` | available_with_low_todo |
| `source_gap_report.md` | available |
| `data_layer_quality_report.md` | accepted_with_todos |

## 2. Financial Quality Table

| metric | period | value | unit | evidence_id | status | boundary |
|---|---|---:|---|---|---|---|
| total_revenue | 20251231 | 3520000000 | CNY | ev_structured_financial_data_002837_20260701_1b506c | draft metric | company-level metric only |
| n_income_attr_p | 20251231 | 450000000 | CNY | ev_structured_financial_data_002837_20260701_1b506c | draft metric | company-level metric only |
| basic_eps | 20251231 | 0.62 | CNY | ev_structured_financial_data_002837_20260701_1b506c | draft metric | company-level metric only |
| total_revenue | 20241231 | 2980000000 | CNY | ev_structured_financial_data_002837_20260701_1b506c | draft metric | company-level metric only |
| n_income_attr_p | 20241231 | 328000000 | CNY | ev_structured_financial_data_002837_20260701_1b506c | draft metric | company-level metric only |
| basic_eps | 20241231 | 0.46 | CNY | ev_structured_financial_data_002837_20260701_1b506c | draft metric | company-level metric only |

These metrics can support financial context. They cannot support liquid-cooling revenue share, order evidence, customer evidence or segment profitability until official disclosure reconciliation is complete.

## 3. Valuation Context

| field | value | evidence_id | status |
|---|---:|---|---|
| price | 32.50 | ev_structured_market_data_002837_20260701_daa823 | metric context |
| market_cap | 2418000 | ev_structured_market_data_002837_20260701_daa823 | metric context |
| pe_ttm | 38.2 | ev_structured_market_data_002837_20260701_daa823 | metric context |
| pe_forward | TODO_MARKET_DATA | ev_structured_market_data_002837_20260701_daa823 | visible TODO |
| pb | 4.1 | ev_structured_market_data_002837_20260701_daa823 | metric context |
| ps | 6.7 | ev_structured_market_data_002837_20260701_daa823 | metric context |

Valuation fields are market context and scenario inputs only. They are not conclusions.

## 4. Technical / Market State Observation

| field | value | evidence_id | status |
|---|---:|---|---|
| close | 32.5 | ev_structured_market_data_002837_20260701_eaca20 | market-state observation |
| ma5 | 32.02 | ev_structured_market_data_002837_20260701_eaca20 | market-state observation |
| ma10 | 31.19 | ev_structured_market_data_002837_20260701_eaca20 | market-state observation |
| ma20 | INSUFFICIENT_PRICE_WINDOW | ev_structured_market_data_002837_20260701_eaca20 | visible TODO |
| ma60 | INSUFFICIENT_PRICE_WINDOW | ev_structured_market_data_002837_20260701_eaca20 | visible TODO |
| pct_chg_20d | INSUFFICIENT_PRICE_WINDOW | ev_structured_market_data_002837_20260701_eaca20 | visible TODO |
| pct_chg_60d | INSUFFICIENT_PRICE_WINDOW | ev_structured_market_data_002837_20260701_eaca20 | visible TODO |

Technical snapshot note: Technical snapshot is a market-state observation, not trading advice.

## 5. Peer Valuation Table

| stock_code | company_name | price | pe_ttm | pe_forward | pb | ps | source_evidence_id | status |
|---|---|---:|---:|---|---:|---:|---|---|
| 002837 | 英维克 | 32.50 | 38.2 | TODO_MARKET_DATA | 4.1 | 6.7 | ev_structured_market_data_002837_20260701_daa823 | fixture context |
| 301018 | 申菱环境 | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | fixture TODO |
| 300499 | 高澜股份 | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | fixture TODO |
| 300731 | 科创新源 | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | fixture TODO |
| 300602 | 飞荣达 | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | TODO_MARKET_DATA | fixture TODO |

Peer valuation table is context-only. It is not a ranking, rating or trading conclusion.

## 6. Source Gaps Carried Forward

| gap_id | severity | status | handling |
|---|---|---|---|
| DL-GAP-001 | low | lowered_to_low_todo | Peer snapshot exists in fixture-only mode; live peer market data hardening remains pending. |
| DL-GAP-002 | medium | TODO_DISCLOSURE_RECONCILIATION | Structured financial metrics need official filing reconciliation before material company facts. |
| DL-GAP-003 | low | TODO_MARKET_DATA | `pe_forward` remains missing from fixture. |

## 7. Business Exposure Boundary

The following remain blocked from promotion:

| candidate use | bridge decision | required next evidence |
|---|---|---|
| Liquid-cooling revenue share | keep `MISSING_DISCLOSURE` | official disclosure segment/product revenue table |
| Liquid-cooling gross margin | keep `MISSING_DISCLOSURE` | official disclosure segment/product gross margin table |
| Customer/order/capacity fact | keep `TODO_SOURCE_REQUIRED` | official disclosure, announcement, or reviewed primary source |
| Company-level financial metrics as segment facts | disallowed | official disclosure reconciliation plus quality review |

## 8. Handoff

Stock-deep-dive may use this bridge to fill financial, valuation, technical and peer context sections. It must carry forward DL-GAP-002 and DL-GAP-003 and must not convert structured snapshots into business exposure facts.
