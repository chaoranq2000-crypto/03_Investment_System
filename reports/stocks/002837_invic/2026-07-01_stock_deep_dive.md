# 个股深度：002837 英维克

> 本内容用于研究流程与证据管理，不构成任何买入、卖出、持有或其他交易建议。

## 0. Metadata

| Field | Value |
|---|---|
| report_id | stock_report_002837_2026-07-01 |
| report_type | stock_report |
| company_id | cn_002837_invic |
| stock_code | 002837 |
| stock_name | 英维克 |
| linked_segments | ai_server_liquid_cooling |
| report_date | 2026-07-01 |
| evidence_snapshot | annual_report_002837_invic_2025_0f8fcf; market_data_tushare_stock_basic_20260701_a6d9f2; market_data_tushare_income_selected_stocks_20260701_f1c8b2; market_data_tushare_fina_indicator_selected_stocks_20260701_c3e4a9; market_data_tushare_cashflow_selected_stocks_20260701_d5b6c1; market_data_tushare_balancesheet_selected_stocks_20260701_a8f0d7 |
| claim_ids | claim_company_002837_invic_20260701_001; claim_company_002837_invic_20260701_002; claim_financial_cn_002837_invic_2025_001; claim_financial_cn_002837_invic_2025_002; claim_financial_cn_002837_invic_2025_003; claim_financial_cn_002837_invic_2026Q1_001 |
| metric_ids | metric_company_cn_002837_invic_total_revenue_20251231_0880d1; metric_company_cn_002837_invic_net_profit_attributable_20251231_73d111; metric_company_cn_002837_invic_gross_margin_20251231_d6a50d; metric_company_cn_002837_invic_debt_to_assets_20251231_ff6ca6 |
| confidence | medium |
| status | current |

## 1. 一页研究假设

- fact: 英维克披露数据中心热管理和液冷相关产品/解决方案，属于较清晰的产品暴露样本。 证据：evidence_id=annual_report_002837_invic_2025_0f8fcf; claim_id=claim_company_002837_invic_20260701_001
- fact: 2025年公司整体营业总收入为60.68 亿元，归母净利润为5.22 亿元。证据：evidence_id=market_data_tushare_income_selected_stocks_20260701_f1c8b2; claim_id=claim_financial_cn_002837_invic_2025_001
- fact: 2025年公司整体毛利率为27.86%，资产负债率为55.30%。证据：evidence_id=market_data_tushare_fina_indicator_selected_stocks_20260701_c3e4a9; claim_id=claim_financial_cn_002837_invic_2025_003
- inference: 本轮只能说明公司层财务质量和液冷相关暴露线索并存，不能把公司整体增长直接归因于AI服务器液冷。
- 最大不确定性：液冷收入占比和利润贡献尚未在本轮证据中直接披露。

## 2. 财务质量：增长、利润率、现金流、资产负债

| Metric | Period | Value | metric_id | source_evidence_id | claim_type |
|---|---|---:|---|---|---|
| 营业总收入 | 2025 | 60.68 亿元 | metric_company_cn_002837_invic_total_revenue_20251231_0880d1 | market_data_tushare_income_selected_stocks_20260701_f1c8b2 | fact |
| 归母净利润 | 2025 | 5.22 亿元 | metric_company_cn_002837_invic_net_profit_attributable_20251231_73d111 | market_data_tushare_income_selected_stocks_20260701_f1c8b2 | fact |
| 毛利率 | 2025 | 27.86% | metric_company_cn_002837_invic_gross_margin_20251231_d6a50d | market_data_tushare_fina_indicator_selected_stocks_20260701_c3e4a9 | fact |
| 净利率 | 2025 | 8.94% | metric_company_cn_002837_invic_net_profit_margin_20251231_f0977c | market_data_tushare_fina_indicator_selected_stocks_20260701_c3e4a9 | fact |
| 经营性现金流净额 | 2025 | 1.57 亿元 | metric_company_cn_002837_invic_net_operating_cash_flow_20251231_4e6c0a | market_data_tushare_cashflow_selected_stocks_20260701_d5b6c1 | fact |
| 资产负债率 | 2025 | 55.30% | metric_company_cn_002837_invic_debt_to_assets_20251231_ff6ca6 | market_data_tushare_fina_indicator_selected_stocks_20260701_c3e4a9 | fact |
| 2026Q1营业总收入 | 2026Q1 | 11.75 亿元 | metric_company_cn_002837_invic_total_revenue_20260331_a4342d | market_data_tushare_income_selected_stocks_20260701_f1c8b2 | fact |
| 2026Q1归母净利润 | 2026Q1 | 865.76 万元 | metric_company_cn_002837_invic_net_profit_attributable_20260331_dba127 | market_data_tushare_income_selected_stocks_20260701_f1c8b2 | fact |

### 财务变化解读

- fact: 2025年营业总收入同比约32.23%，归母净利润同比约15.30%。证据：claim_id=claim_financial_cn_002837_invic_2025_002
- fact: 2026Q1营业总收入为11.75 亿元，归母净利润为865.76 万元。证据：claim_id=claim_financial_cn_002837_invic_2026Q1_001
- inference: 财务数据提升了个股报告的“公司发生了什么”部分，但尚不能解释“液冷贡献了多少”。液冷收入占比仍标记 `MISSING: 暂无直接披露`。

## 3. 业务拆分：利润从哪里来

| 业务线 | 收入 | 毛利率 | 增速 | 关联细分 | 证据 | 备注 |
|---|---:|---:|---:|---|---|---|
| 公司整体 | 60.68 亿元 | 27.86% | 32.23% | multiple | market_data_tushare_income_selected_stocks_20260701_f1c8b2; market_data_tushare_fina_indicator_selected_stocks_20260701_c3e4a9 | 公司整体口径 |
| AI服务器液冷相关业务 | MISSING: 暂无直接披露 | MISSING: 暂无直接披露 | TODO: 需要补充证据 | ai_server_liquid_cooling | annual_report_002837_invic_2025_0f8fcf | 不能用公司整体财务替代液冷业务 |
| 其他业务 | TODO: 需要补充证据 | TODO: 需要补充证据 | TODO: 需要补充证据 | unknown | TODO | 等待完整年报分部抽取 |

## 4. 细分方向暴露：行业逻辑如何落到公司

| 因果环节 | claim_type | evidence / metric | confidence | 反证或缺口 |
|---|---|---|---|---|
| AI算力基础设施扩张带来热管理需求背景 | fact | policy_miit_compute_infra_20231008_9f2a30 | medium | 政策不等同订单 |
| 冷板式液冷是高功率密度散热路径之一 | fact | industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91 | medium | 路线存在替代与节奏不确定 |
| 公司存在液冷相关暴露线索 | fact | annual_report_002837_invic_2025_0f8fcf; claim_company_002837_invic_20260701_001 | medium | 收入占比未披露 |
| 公司整体财务表现可观察 | fact | market_data_tushare_income_selected_stocks_20260701_f1c8b2; market_data_tushare_fina_indicator_selected_stocks_20260701_c3e4a9 | medium | 不能归因到液冷业务 |

## 5. segment_company_exposure

| segment_id | exposure_type | exposure_score | revenue_pct | profit_pct | evidence_ids | confidence | notes |
|---|---|---:|---|---|---|---|---|
| ai_server_liquid_cooling | product | 4 | MISSING: 暂无直接披露 | MISSING: 暂无直接披露 | annual_report_002837_invic_2025_0f8fcf | medium | 较核心产品暴露样本 |

## 6. 客户、供应链与产能

| Topic | claim_type | Evidence | Reliability | Notes |
|---|---|---|---|---|
| 数据中心/AI服务器客户 | unknown | TODO | unknown | 需要客户侧订单、认证或投资者关系记录 |
| 液冷部件或系统能力 | fact / inference | annual_report_002837_invic_2025_0f8fcf | A | 仅证明相关线索，不证明收入占比 |
| 产能或募投项目 | unknown | TODO | unknown | 需公告或年报表格定位 |
| 供应链议价 | unknown | TODO | unknown | 需要采购、成本或客户集中度证据 |

## 7. 盈利假设与敏感性

| 层级 | 内容 | evidence_id / metric_id | claim_type | confidence |
|---|---|---|---|---|
| 历史事实 | 2025公司整体收入、利润、毛利率已有结构化快照 | metric_company_cn_002837_invic_total_revenue_20251231_0880d1; metric_company_cn_002837_invic_gross_margin_20251231_d6a50d | fact | medium |
| 关键假设 | 液冷业务若能披露收入占比，才可量化业绩弹性 | TODO | inference | low |
| 敏感性 | 若客户验证或订单披露不足，exposure_score应维持或下调 | annual_report_002837_invic_2025_0f8fcf | inference | medium |

## 8. 估值场景

本节只记录研究假设，不输出目标价、评级或交易动作。

| Scenario | Assumption type | Key assumptions | evidence_id / metric_id | confidence | Risk |
|---|---|---|---|---|---|
| base | inference | 公司整体财务可跟踪，液冷暴露等待收入占比验证 | market_data_tushare_income_selected_stocks_20260701_f1c8b2; annual_report_002837_invic_2025_0f8fcf | medium | 液冷贡献低于叙事 |
| upside_watch | unknown | 出现液冷订单、客户认证或分产品收入披露 | TODO | low | 需要官方证据 |
| downside | inference | 液冷停留在技术或产品线索，未形成显著财务贡献 | annual_report_002837_invic_2025_0f8fcf | medium | 概念映射降权 |

## 9. 催化剂与跟踪日历

| Catalyst | claim_type | evidence_id | expected_window | confidence | Follow-up |
|---|---|---|---|---|---|
| 年报/半年报披露液冷收入或订单 | unknown | TODO | 2026H2-2027H1 | medium | 抽取分部收入和订单 |
| 投资者关系活动记录更新客户验证 | management_comment | TODO | 2026H2 | low | 不能当事实，需标注管理层表述 |
| Tushare财务字段刷新 | fact | market_data_tushare_income_selected_stocks_20260701_f1c8b2 | 每次定期报告后 | medium | 更新metrics_draft.csv |

## 10. 风险、反证和可证伪条件

| Risk / Counter-evidence | Related claim_id | evidence_id | Impact | Follow-up |
|---|---|---|---|---|
| 公司整体收入增长不能证明液冷业务放量 | claim_financial_cn_002837_invic_2025_001 | market_data_tushare_income_selected_stocks_20260701_f1c8b2 | 高 | 寻找液冷收入、订单、客户证据 |
| 液冷收入占比和利润贡献尚未在本轮证据中直接披露。 | claim_company_002837_invic_20260701_002 | annual_report_002837_invic_2025_0f8fcf | 高 | 继续核验收入占比和客户验证 |
| 毛利率变化可能由非液冷业务或成本因素驱动 | claim_financial_cn_002837_invic_2025_003 | market_data_tushare_fina_indicator_selected_stocks_20260701_c3e4a9 | 中 | 补分业务毛利率和成本结构 |
| 2026Q1短期波动不能外推全年 | claim_financial_cn_002837_invic_2026Q1_001 | market_data_tushare_income_selected_stocks_20260701_f1c8b2 | 中 | 等待半年报/年报确认 |

## 11. 跟踪指标

| Metric | Current P1 status | Evidence source | Review frequency | Notes |
|---|---|---|---|---|
| liquid_cooling_revenue_pct | MISSING: 暂无直接披露 | 年报/半年报/公告 | 半年 | 核心缺口 |
| company_total_revenue | 已有2025和2026Q1 | market_data_tushare_income_selected_stocks_20260701_f1c8b2 | 季度/年度 | 公司整体口径 |
| gross_margin | 已有2025和2026Q1 | market_data_tushare_fina_indicator_selected_stocks_20260701_c3e4a9 | 季度/年度 | 不能直接归因液冷 |
| customer_validation_progress | TODO: 需要补充证据 | 投关/公告 | 月度 | 管理层表述需单独标注 |

## 12. TODO / Missing Data

- MISSING: 暂无直接披露 - 液冷收入占比、利润占比、订单金额。
- TODO: 需要补充证据 - 客户认证、产能、募投和分业务毛利率。
- LOW_CONFIDENCE: 当前证据质量不足 - 不应把公司整体财务改善直接归因于AI服务器液冷。

## 13. Evidence Map

详见 `evidence_map.md`。

## 14. Refresh Status

- status: current
- next_review_date: 2026-10-01
- reports_to_regenerate: 本公司年报/半年报、Tushare财务快照、segment_company_exposure
