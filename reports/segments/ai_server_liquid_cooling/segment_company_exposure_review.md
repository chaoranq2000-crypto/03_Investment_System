# Segment-company exposure review

> 本内容用于研究流程与证据管理，不构成任何买入、卖出、持有或其他交易建议。

## Review Result

- 多对多映射已落在 `data/processed/normalized/segment_company_exposure.csv`。
- 本轮所有记录均有 evidence_ids；没有使用无证据高分。
- `revenue_pct` 和 `profit_pct` 未披露时均保留 `MISSING: 暂无直接披露`。

## Score Discipline

- 4分：产品暴露较清楚，但未确认液冷收入占比。
- 3分：产品线索存在，但客户/收入证据不足。
- 2分：技术或宽口径热管理线索，等待财务兑现核验。

## Open Checks

- Tushare代理配置已按指南修复，stock_basic公司基础信息已入库。证据：evidence_id=market_data_tushare_stock_basic_20260701_a6d9f2; claim_id=claim_data_tushare_20260701_002
- 补抽取定期报告中的分业务收入、订单和客户表格。
