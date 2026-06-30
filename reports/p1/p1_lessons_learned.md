# P1 Lessons Learned

> 本内容用于研究流程与证据管理，不构成任何买入、卖出、持有或其他交易建议。

- evidence_id/claim_id 在报告中可用，但需要脚本化检查，人工维护容易漏。
- 公司池最容易被“热管理宽口径”污染，必须保留 exposure_type 和 confidence。
- revenue_pct/profit_pct 不应猜测，缺失时用 MISSING 更可靠。
- Tushare适合补结构化股票和财务字段，但必须按指南设置代理URL并先做数据源健康检查。
- 下一阶段如果做多细分比较，应先把 `segment_company_exposure.csv` 扩成可累计表。
