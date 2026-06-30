# P1 Readout: AI服务器液冷

> 本内容用于研究流程与证据管理，不构成任何买入、卖出、持有或其他交易建议。

## 1. 本轮范围

- 试点细分：AI服务器液冷
- segment_id：ai_server_liquid_cooling
- 时间范围：最近3年 + 最新公告/财报
- 证据数量：15
- claims 数量：22
- 公司池数量：5
- 个股深度数量：2
- 财务指标数量：44

## 2. 核心产物

- segment_report: reports/segments/ai_server_liquid_cooling/2026-07-01_segment_report.md
- company_universe: reports/segments/ai_server_liquid_cooling/company_universe.csv
- scorecard: reports/segments/ai_server_liquid_cooling/scorecard.yaml
- evidence_map: reports/segments/ai_server_liquid_cooling/evidence_map.md
- stock_deep_dive: reports/stocks/002837_invic/2026-07-01_stock_deep_dive.md; reports/stocks/300731_cotran/2026-07-01_stock_deep_dive.md
- segment_exposure: data/processed/normalized/segment_company_exposure.csv
- quality_review: reports/p1/quality_review_ai_server_liquid_cooling.md

## 3. 主要结论

- fact: AI算力基础设施扩张提供需求背景。证据：policy_miit_compute_infra_20231008_9f2a30
- fact: 冷板式液冷是算力中心高功率密度散热路径之一。证据：industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91
- inference: 公司池需要分层，英维克/申菱环境产品暴露较清楚，科创新源/飞荣达应降权验证。
- 不确定性：液冷收入占比、利润贡献、客户订单和公告深字段仍需补证。

## 4. 系统验证结果

| Check | Result |
|---|---|
| 证据是否能沉淀 | PASS |
| 结论是否能追溯 | PASS |
| 公司是否能多对多映射 | PASS |
| 报告是否能重建 | PASS |
| 模板是否可复用 | PASS |
| skill边界是否清楚 | PASS |

## 5. P1 问题清单

- 数据问题：Tushare代理配置已修复，stock_basic、income、fina_indicator、cashflow、balancesheet 已形成快照；公告深字段和液冷收入占比仍待补。
- 证据问题：液冷收入占比和客户侧订单证据不足。
- 评分问题：评分可用于研究优先级，但不能转成交易信号。
- 路径问题：P1草案中的 `data/normalized/` 已按架构统一为 `data/processed/normalized/`。

## 6. 是否进入 P2

- 判断：P1验收通过，但进入P2前建议先修复中优先级TODO。
- 理由：闭环已成立，且质量审查能发现实际问题；但横向比较前仍需补液冷收入占比、客户订单和公告深字段。
- 前置修复项：
  - 用Tushare继续补公告线索；财务字段已完成P1样本快照。
  - 抽取2-3家公司液冷收入或订单证据。
  - 补客户侧采购/部署证据。

## P1 Acceptance

status: PASS_WITH_MEDIUM_TODOS
