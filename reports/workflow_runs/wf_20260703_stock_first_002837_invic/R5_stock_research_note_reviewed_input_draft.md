# reviewed_input_research_draft: 002837 英维克

metadata:
- output_type: reviewed_input_research_draft
- pack_status: research_draft
- allowed_report_level: reviewed_input_research_draft
- no_advice_boundary: True

## 重要结论与可追溯锚点

下表区分 fact、estimate 与 inference；每条重要结论均保留证据或审查输入锚点。

| claim_id | 类型 | 期间 | 结论 | 证据/输入锚点 | 来源与方法 |
| --- | --- | --- | --- | --- | --- |
| financial_history_revenue_2025 | fact | 2025A | 公司营业收入为 6,067,759,091.55 CNY，归母净利润为 521,914,773.00 CNY。 | ev_annual_report_002837_20260421_2cbfc5 | reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_financial_history_candidate.yaml / direct_reported_value |
| financial_q1_profit_divergence | fact | 2026Q1 | 营业收入同比增长 26.03%，归母净利润同比下降 81.97%，收入与利润表现发生背离。 | ev_quarterly_report_002837_20260421_2f00c7 | reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_financial_history_candidate.yaml / direct_reported_yoy_values |
| financial_q1_operating_cashflow | fact | 2026Q1 | 经营现金流为 -386,363,968.71 CNY，且 2025A 低于 2023A 与 2024A。 | ev_annual_report_002837_20260421_2cbfc5, ev_quarterly_report_002837_20260421_2f00c7 | reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_financial_history_candidate.yaml / direct_reported_value_and_period_comparison |
| business_broad_product_split | fact | 2025A | 机房温控与机柜温控是年报披露的宽口径产品线，收入分别为 3,448,477,492.62 与 1,977,423,139.19 CNY。 | ev_annual_report_002837_20260421_2cbfc5 | reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_business_breakdown_candidate.yaml / direct_reported_product_line_values |
| business_liquid_cooling_exposure | fact | 2025A | 官方材料披露液冷相关产品线索，但没有单列相应收入占比、毛利率和利润贡献。 | ev_annual_report_002837_20260421_2cbfc5 | reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_business_breakdown_candidate.yaml / product_narrative_review_with_visible_missing_metrics |
| forecast_base_path | estimate | 2026E-2028E | 基准情景采用机械外推与显式模型假设，2026E-2028E EPS 分别为 0.073854、0.252034、0.455462 CNY/share。 | ev_annual_report_002837_20260421_2cbfc5, ev_quarterly_report_002837_20260421_2f00c7, ev_structured_market_data_002837_20260710_eb0c08, r5_b5_forecast_eps_base | reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_forecast_model_candidate.yaml / reviewed_assumption_model |
| valuation_cross_multiple_context | inference | 2026-07-10 | PE TTM 低于两家同业中位数，而 PB 与 PS TTM 高于对应中位数，方向不一致，不能形成单一估值标签。 | ev_structured_market_data_002837_20260710_eb0c08, r5_b5_valuation_context_002837_20260710 | reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_valuation_pack_candidate.yaml / same_date_cross_multiple_comparison |
| valuation_net_debt_proxy | inference | 2026Q1 | 净债务代理值为 698,135,329.67 CNY；受受限资金和金融资产重分类未复核影响，置信度为 low。 | ev_quarterly_report_002837_20260421_2f00c7 | reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_valuation_pack_candidate.yaml / reviewed_debt_components_minus_cash |

## 公司背景与研究边界

- readiness: covered
- evidence_ids: ev_annual_report_002837_20260421_2cbfc5

当前证据支持公司存在数据中心温控和液冷相关产品线索；研究边界停留在产品暴露，不能把公司整体财务数据归因到液冷业务。

| 项目 | 状态 | 置信度 | 锚点 |
| --- | --- | --- | --- |
| ai_server_liquid_cooling | product_exposure_needs_review | medium | ev_annual_report_002837_20260421_2cbfc5 |
- limitation: liquid-cooling-specific financial contribution is not separately disclosed
- visible_gap: MISSING_DISCLOSURE

## 财务历史与现金流质量

- readiness: covered
- evidence_ids: ev_annual_report_002837_20260421_2cbfc5, ev_quarterly_report_002837_20260421_2f00c7

2026Q1 收入增长与利润下降并存，经营现金流为负；单季结果不直接外推为全年事实。

| 期间 | 收入 | 归母净利润 | 经营现金流 | 单位 | 类型 | 证据 | 方法 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2023A | 3,528,859,077.13 | 344,006,335.07 | 453,072,040.34 | CNY | fact | ev_annual_report_002837_20260421_2cbfc5 | direct_reported_value |
| 2024A | 4,588,819,487.27 | 452,664,369.42 | 199,835,014.95 | CNY | fact | ev_annual_report_002837_20260421_2cbfc5 | direct_reported_value |
| 2025A | 6,067,759,091.55 | 521,914,773.00 | 157,273,222.36 | CNY | fact | ev_annual_report_002837_20260421_2cbfc5 | direct_reported_value |
| 2026Q1 | 1,175,329,313.61 | 8,657,602.27 | -386,363,968.71 | CNY | fact | ev_quarterly_report_002837_20260421_2f00c7 | direct_reported_value |
- limitation: 2026Q1 is unaudited and should not be treated as a full-year pattern

## 业务拆分与细分经济性

- readiness: partial
- evidence_ids: ev_annual_report_002837_20260421_2cbfc5

宽口径机房与机柜温控数据可核验，但这些数据不等同于液冷单独口径。

| 披露口径 | 收入 CNY | 收入占比 % | 毛利率 % | 置信度 | 证据 |
| --- | --- | --- | --- | --- | --- |
| 机房温控节能产品 | 3,448,477,492.62 | 56.83 | 28.36 | high | ev_annual_report_002837_20260421_2cbfc5 |
| 机柜温控节能产品 | 1,977,423,139.19 | 32.59 | 27.24 | high | ev_annual_report_002837_20260421_2cbfc5 |
| 液冷单独口径 | MISSING_DISCLOSURE | MISSING_DISCLOSURE | MISSING_DISCLOSURE | medium | ev_annual_report_002837_20260421_2cbfc5 |
- limitation: The issuer discloses liquid-cooling products but reports revenue and margin in broader room/cabinet cooling categories.
- limitation: Broad product-line totals therefore cannot be relabeled as liquid-cooling-specific financials.
- visible_gap: MISSING_DISCLOSURE

## 行业结构与竞争

- readiness: missing

当前没有审查后的行业供需与竞争证据，本节不生成事实性行业判断。
- limitation: industry evidence is outside the current reviewed-input set
- visible_gap: TODO_SOURCE_REQUIRED

## 预测假设与敏感性

- readiness: covered
- evidence_ids: ev_annual_report_002837_20260421_2cbfc5, ev_quarterly_report_002837_20260421_2f00c7, ev_structured_market_data_002837_20260710_eb0c08

以下均为 estimate：2026E 使用机械外推，2027E-2028E 使用显式放缓与利润率假设，并保留宽范围敏感性。

| 期间 | 收入 CNY | 毛利率 % | 归母净利润 CNY | EPS CNY/share | 类型 | 假设锚点 |
| --- | --- | --- | --- | --- | --- | --- |
| 2026E | 7,647,141,176.21 | 24.2935 | 94,115,513.02 | 0.073854 | estimate | r5_b5_forecast_eps_base |
| 2027E | 9,176,569,411.45 | 25.5000 | 321,179,929.40 | 0.252034 | estimate | r5_b5_forecast_eps_base |
| 2028E | 10,553,054,823.17 | 26.5000 | 580,418,015.27 | 0.455462 | estimate | r5_b5_forecast_eps_base |
- limitation: The path is a mechanical research scenario, not management guidance or consensus.
- limitation: 2026Q1 profitability was unusually weak relative to 2025, so uncertainty is wide.

## 估值方法与可比性

- readiness: partial
- evidence_ids: ev_structured_market_data_002837_20260710_eb0c08, ev_quarterly_report_002837_20260421_2f00c7

同日比较中，公司 PE TTM 为 194.2045，同业中位数为 310.1249；PB 与 PS TTM 的方向相反，因此保持 mixed_multiple_signal_not_assessable。

| 指标 | 数值 | 单位 | 口径 | 证据 |
| --- | --- | --- | --- | --- |
| close | 73.54 | CNY_per_share | 2026-07-10 unadjusted close | ev_structured_market_data_002837_20260710_eb0c08 |
| PE TTM | 194.2045 | multiple | trailing earnings multiple | ev_structured_market_data_002837_20260710_eb0c08 |
| PB | 27.0715 | multiple | price-to-book | ev_structured_market_data_002837_20260710_eb0c08 |
| PS | 15.4449 | multiple | non-TTM PS field from physical registry | ev_structured_market_data_002837_20260710_eb0c08 |
| PS TTM | 14.8507 | multiple_TTM | TTM sales multiple; kept separate from PS | ev_structured_market_data_002837_20260710_eb0c08 |
- limitation: Relative PE is low confidence because only two exposure-grounded peers are available.
- limitation: PE is below the peer median while PB and PS TTM are above their peer medians; no single valuation label is supportable.
- limitation: No intrinsic or segment-sum method is active.
- limitation: Scenario multiples are research context, not price outputs.
- visible_gap: LOW_CONFIDENCE_CLUE_ONLY
- visible_gap: UNREVIEWED_FCFF_INPUTS
- visible_gap: UNDISCLOSED_SEGMENT_SPLIT

## 有日期的市场状态

- readiness: partial
- evidence_ids: ev_structured_market_data_002837_20260710_eb0c08

仅呈现 2026-07-10 的收盘与估值快照；缺少审查后的历史序列，因此不生成趋势判断。

| 指标 | 数值 | 单位 | 口径 | 证据 |
| --- | --- | --- | --- | --- |
| close | 73.54 | CNY_per_share | 2026-07-10 unadjusted close | ev_structured_market_data_002837_20260710_eb0c08 |
| PE TTM | 194.2045 | multiple | trailing earnings multiple | ev_structured_market_data_002837_20260710_eb0c08 |
| PB | 27.0715 | multiple | price-to-book | ev_structured_market_data_002837_20260710_eb0c08 |
- limitation: single-date snapshot only
- visible_gap: MISSING_PRICE_HISTORY

## 有日期的情绪与事件

- readiness: missing

当前没有进入审查输入集的有日期事件或情绪证据，本节保持空缺。
- limitation: dated sources are absent
- visible_gap: TODO_SOURCE_REQUIRED

## 风险、反证与开放问题

- readiness: covered
- evidence_ids: ev_annual_report_002837_20260421_2cbfc5, ev_quarterly_report_002837_20260421_2f00c7, ev_structured_market_data_002837_20260710_eb0c08

风险与反证保留在正文，不因报告可渲染而弱化。

| 类别 | 内容 | 锚点 |
| --- | --- | --- |
| risk | 2026Q1 利润与经营现金流显著弱于收入表现 | ev_quarterly_report_002837_20260421_2f00c7 |
| risk | 2025A 经营现金流低于 2023A 与 2024A | ev_annual_report_002837_20260421_2cbfc5 |
| counter_evidence | 宽口径产品线不能证明液冷单独财务贡献 | ev_annual_report_002837_20260421_2cbfc5 |
| counter_evidence | PE、PB 与 PS TTM 的同业信号方向不一致 | ev_structured_market_data_002837_20260710_eb0c08 |
- visible_gap: MISSING_DISCLOSURE
- visible_gap: LOW_CONFIDENCE_CLUE_ONLY

## 研究结论与后续观察条件

- readiness: partial
- evidence_ids: ev_annual_report_002837_20260421_2cbfc5, ev_quarterly_report_002837_20260421_2f00c7, ev_structured_market_data_002837_20260710_eb0c08

研究状态为 evidence_watch：产品暴露可继续验证，但收入与利润暴露仍为 unknown；预测和估值仅作低置信研究情景。

| 观察条件 | 原因 | 后续来源 |
| --- | --- | --- |
| 液冷单独收入与毛利率 | 验证产品暴露能否转化为财务贡献 | future official disclosure |
| 利润与经营现金流 | 验证盈利质量是否改善 | future periodic report |
| 可比口径与方法输入 | 改善估值可比性与方法资格 | reviewed structured inputs |
- limitation: research-draft level only
- visible_gap: MISSING_DISCLOSURE
- visible_gap: LOW_CONFIDENCE_CLUE_ONLY

## 数据时点与口径冲突处理

- market_ps_vs_ps_ttm_definition | resolved_by_separate_labels | PS and PS TTM are rendered as distinct metrics; neither value is relabeled.
- broad_product_line_vs_liquid_specific | unresolved_disclosure_gap | Broad product-line values remain separate from the missing liquid-cooling-specific metrics.

## company_context

- readiness: ready
- evidence_ids: ev_annual_report_002837_20260421_2cbfc5
- limitation: liquid-cooling-specific financial contribution is not separately disclosed

## financial_history_and_cash_flow_quality

- readiness: ready
- evidence_ids: ev_annual_report_002837_20260421_2cbfc5, ev_quarterly_report_002837_20260421_2f00c7
- limitation: 2026Q1 is unaudited and should not be treated as a full-year pattern

## business_breakdown_and_segment_economics

- readiness: ready_with_limitations
- evidence_ids: ev_annual_report_002837_20260421_2cbfc5
- limitation: The issuer discloses liquid-cooling products but reports revenue and margin in broader room/cabinet cooling categories.
- limitation: Broad product-line totals therefore cannot be relabeled as liquid-cooling-specific financials.

## industry_structure_and_competition

- readiness: source_gapped
- next_action: keep source gaps visible until reviewed inputs exist.
- issue: TODO_SOURCE_REQUIRED

## forecast

- readiness: ready
- evidence_ids: ev_annual_report_002837_20260421_2cbfc5, ev_quarterly_report_002837_20260421_2f00c7, ev_structured_market_data_002837_20260710_eb0c08
- limitation: The path is a mechanical research scenario, not management guidance or consensus.
- limitation: 2026Q1 profitability was unusually weak relative to 2025, so uncertainty is wide.

## valuation

- readiness: ready_with_limitations
- evidence_ids: ev_structured_market_data_002837_20260710_eb0c08, ev_quarterly_report_002837_20260421_2f00c7
- limitation: Relative PE is low confidence because only two exposure-grounded peers are available.
- limitation: PE is below the peer median while PB and PS TTM are above their peer medians; no single valuation label is supportable.
- limitation: No intrinsic or segment-sum method is active.
- limitation: Scenario multiples are research context, not price outputs.

## dated_market_or_technical_state_when_supported

- readiness: ready_with_limitations
- evidence_ids: ev_structured_market_data_002837_20260710_eb0c08
- limitation: single-date snapshot only

## dated_sentiment_and_events_when_supported

- readiness: source_gapped
- next_action: keep source gaps visible until reviewed inputs exist.
- issue: TODO_SOURCE_REQUIRED

## risks_counterevidence_and_open_questions

- readiness: ready
- evidence_ids: ev_annual_report_002837_20260421_2cbfc5, ev_quarterly_report_002837_20260421_2f00c7, ev_structured_market_data_002837_20260710_eb0c08

## research_conclusion_and_watch_conditions

- readiness: ready_with_limitations
- evidence_ids: ev_annual_report_002837_20260421_2cbfc5, ev_quarterly_report_002837_20260421_2f00c7, ev_structured_market_data_002837_20260710_eb0c08
- limitation: research-draft level only

## Source Gap Appendix

- R5_B5_GAP_LIQUID_COOLING_SPLIT | business_breakdown_and_segment_economics | MISSING_DISCLOSURE: liquid-cooling-specific revenue share, margin and profit contribution | retain the gap until an official split is published
- R5_B5_GAP_INDUSTRY_STRUCTURE | industry_structure_and_competition | TODO_SOURCE_REQUIRED: reviewed industry supply and competition evidence | onboard reviewed industry evidence in a later scoped task
- R5_B5_GAP_PRICE_HISTORY | dated_market_or_technical_state_when_supported | MISSING_PRICE_HISTORY: one dated snapshot does not support a trend statement | keep trend assessment absent until reviewed history exists
- R5_B5_GAP_SENTIMENT_EVENTS | dated_sentiment_and_events_when_supported | TODO_SOURCE_REQUIRED: dated sentiment and event evidence | collect dated official event sources if the section is later activated
- R5_B5_GAP_PEER_CONFIDENCE | valuation_methods_and_comparability | LOW_CONFIDENCE_CLUE_ONLY: peer set contains two non-identical business mixes | retain low confidence until a broader evidence-grounded peer set is reviewed
- R5_B5_GAP_INTRINSIC_METHODS | valuation_methods_and_comparability | UNREVIEWED_FCFF_INPUTS and UNDISCLOSED_SEGMENT_SPLIT | keep methods excluded until required inputs are reviewed

## Open Questions

- liquid-cooling-specific financial split remains undisclosed
- industry and dated event evidence remain source-gapped
- peer set and relative valuation context remain low confidence
- intrinsic and segment-sum methods remain ineligible
