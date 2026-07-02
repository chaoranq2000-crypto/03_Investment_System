# Stock Report Draft: 002837 英维克

> workflow_id: `wf_20260703_stock_first_002837_invic`
> status: draft / needs_fix
> boundary: 本文件仅验证 stock_first_closed_loop debug；不提供交易指令，不做横向比较。

## 0. Metadata And Evidence Snapshot

| Field | Value |
|---|---|
| workflow_type | stock_first_closed_loop |
| stock_code | 002837 |
| stock_name | 英维克 |
| company_id | cn_002837_invic |
| exchange | SZSE |
| as_of_date | 2026-07-03 |
| evidence_delta | evidence_manifest_delta.csv |
| metrics_delta | metrics_draft_delta.csv |
| prior_artifact | reports/stocks/002837_invic/2026-07-01_stock_deep_dive.md |

## 1. Evidence Package Used

| evidence_id | source_type | source_name | title | status | boundary |
|---|---|---|---|---|---|
| ev_annual_report_002837_20260421_ce7f64 | annual_report | szse | 002837 英维克 2025年年度报告摘要 | draft | official filing registered; page/table locator TODO |
| ev_structured_financial_data_002837_20260701_f82181 | structured_financial_data | local_tushare_fixture | stock_basic snapshot | draft | metric-only identity support |
| ev_structured_financial_data_002837_20260701_89213a | structured_financial_data | local_tushare_fixture | income snapshot | draft | metric-only |
| ev_structured_financial_data_002837_20260701_875a4c | structured_financial_data | local_tushare_fixture | fina_indicator snapshot | draft | metric-only |
| ev_structured_financial_data_002837_20260701_418339 | structured_financial_data | local_tushare_fixture | cashflow snapshot | draft | metric-only |
| ev_structured_financial_data_002837_20260701_bad80e | structured_financial_data | local_tushare_fixture | balancesheet snapshot | draft | metric-only |

## 2. Prior Artifact Reuse Decision

| Category | Content | Decision | Reason |
|---|---|---|---|
| 可复用内容 | 公司身份、股票代码、旧报告结构、既有 linked segment 名称 | reuse_as_structure_only | 只能作为 prior artifact，不作为证据来源 |
| 需要重新绑定证据的内容 | 2025 收入、利润率、现金流、资产负债等财务表述 | rebind_to_delta_metrics | 必须引用本轮 metrics_draft_delta.csv 的 metric_candidate_id |
| 必须重生成的内容 | evidence snapshot、metric table、evidence map、segment_exposure、quality issues、workflow readout | regenerate | 本轮验证 workflow-local delta 闭环 |
| 证据不足只能标 TODO 的内容 | 液冷收入占比、利润占比、客户、订单、产能、分业务毛利率、页码定位 | TODO_only | 年报仅完成登记，尚未抽取页码/表格/claim locator |

## 3. Company Identity Gate

| Check | Result | Support |
|---|---|---|
| stock_code | 002837 | evidence_id=ev_structured_financial_data_002837_20260701_f82181 |
| stock_name | 英维克 | evidence_id=ev_structured_financial_data_002837_20260701_f82181 |
| exchange | SZSE | stock_code suffix and source registry context; TODO: exchange field normalization |
| identity_confidence | medium | local fixture + official filing registration |

## 4. Financial Skeleton

| metric_name | period | value | unit | source_evidence_id | metric_candidate_id | boundary |
|---|---|---:|---|---|---|---|
| total_revenue | 20251231 | 6067759091.55 | CNY or ratio per source field | ev_structured_financial_data_002837_20260701_89213a | metric_income_002837_20251231_total_revenue_39fd77f5 | metric-only; not segment exposure evidence |
| n_income_attr_p | 20251231 | 521914773.0 | CNY or ratio per source field | ev_structured_financial_data_002837_20260701_89213a | metric_income_002837_20251231_n_income_attr_p_c027b560 | metric-only; not segment exposure evidence |
| grossprofit_margin | 20251231 | 27.8626 | CNY or ratio per source field | ev_structured_financial_data_002837_20260701_875a4c | metric_fina_indicator_002837_20251231_grossprofit_margin_f0bb18f0 | metric-only; not segment exposure evidence |
| netprofit_margin | 20251231 | 8.9437 | CNY or ratio per source field | ev_structured_financial_data_002837_20260701_875a4c | metric_fina_indicator_002837_20251231_netprofit_margin_13170531 | metric-only; not segment exposure evidence |
| debt_to_assets | 20251231 | 55.3038 | CNY or ratio per source field | ev_structured_financial_data_002837_20260701_875a4c | metric_fina_indicator_002837_20251231_debt_to_assets_8936c94f | metric-only; not segment exposure evidence |
| n_cashflow_act | 20251231 | 157273222.36 | CNY or ratio per source field | ev_structured_financial_data_002837_20260701_418339 | metric_cashflow_002837_20251231_n_cashflow_act_41540f22 | metric-only; not segment exposure evidence |
| inventories | 20251231 | 983397026.13 | CNY or ratio per source field | ev_structured_financial_data_002837_20260701_bad80e | metric_balancesheet_002837_20251231_inventories_a735b22c | metric-only; not segment exposure evidence |
| accounts_receiv | 20251231 | 3053959547.65 | CNY or ratio per source field | ev_structured_financial_data_002837_20260701_bad80e | metric_balancesheet_002837_20251231_accounts_receiv_0fa1f676 | metric-only; not segment exposure evidence |


## 5. Business And Segment Skeleton

| Business / Segment Question | Current Draft Treatment | Evidence / Metric / TODO | Status |
|---|---|---|---|
| 数据中心温控 / 液冷相关产品线 | TODO: 需要从年报原文重新抽取页码、表格或章节定位后才能形成 material claim | evidence_id=ev_annual_report_002837_20260421_ce7f64 plus TODO: page/table locator | needs_fix |
| liquid_cooling_revenue_pct | MISSING: 暂无直接披露 | TODO: extract annual report segment table | open |
| liquid_cooling_profit_pct | MISSING: 暂无直接披露 | TODO: extract annual report segment table | open |
| customer / order / capacity evidence | TODO: 需要公告、年报章节或投关记录复核 | TODO: official disclosure locator | open |
| company-level financial quality | Can be drafted as metric observation only | metric_candidate_id examples listed above | draft |

## 6. Linked Segment Discovery

| segment_id | link_status | exposure_type | support | confidence | note |
|---|---|---|---|---|---|
| ai_server_liquid_cooling | todo_insufficient_evidence | todo_insufficient_evidence | evidence_id=ev_annual_report_002837_20260421_ce7f64; TODO: claim locator | low | 旧报告可提示方向，但本轮尚未重新抽取足够证据，不能升级为 accepted exposure |

## 7. Risk, Counter-evidence, And TODO

| Item | Type | Reference | Owner |
|---|---|---|---|
| 年报登记未解析，缺页码/表格定位 | high issue | evidence_id=ev_annual_report_002837_20260421_ce7f64 | evidence-ingest |
| 结构化数据只能证明公司层指标，不证明液冷业务暴露 | guardrail | metrics_draft_delta.csv | stock-deep-dive |
| 液冷收入/利润占比缺失 | TODO / MISSING | TODO: annual report extraction | evidence-ingest |
| exposure registry 暂不更新 | workflow decision | exposure_change_note.md | segment-company-mapping |

## 8. Backflow Decision

`blocked`

Reason: 本轮能生成 workflow-local `segment_exposure.yaml`，但缺少本轮重新抽取的年报页码/claim locator，因此不更新全局 exposure registry。
