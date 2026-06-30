# Template Change Log

> 本内容用于研究流程与证据管理，不构成任何买入、卖出、持有或其他交易建议。

## Result

status: NO_SCHEMA_BREAKING_CHANGE

## Decisions

- 现有 `templates/segment_report.md` 和 `templates/stock_report.md` 已能承接 P1 所需字段。
- P1新增实践要求：company_universe和segment_company_exposure必须保留 `MISSING: 暂无直接披露`，不得猜测 revenue_pct/profit_pct。
- P1新增实践要求：Tushare等结构化数据源必须先做代理URL健康检查；失败时进入 quality_issues 和 refresh_tasks，不允许静默跳过。
- P1路径约定：标准化记录落在 `data/processed/normalized/`。


## Case-study calibration

- 已新增 `src/report/enhance_p1_stock_reports_case_quality.py`，用于把优秀案例拆解中的财务概览、业务拆分、因果链、情景、催化剂和风险/反证结构落到P1两个个股样本。
- 新增 `data/manifests/metrics_draft.csv` 作为个股财务指标中间层，避免报告直接堆数字而无 `metric_id`。
- 财务指标仅代表公司整体口径，不能直接归因到AI服务器液冷业务。
