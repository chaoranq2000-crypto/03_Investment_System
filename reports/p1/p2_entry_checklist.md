# P2 Entry Checklist

> 本内容用于研究流程与证据管理，不构成任何买入、卖出、持有或其他交易建议。

metadata:

- stage: P1.5
- as_of_date: 2026-07-01
- generated_at: 2026-07-01
- decision: READY_FOR_LIMITED_P2
- boundary: 只允许在 P1.5 门禁通过后做有限 P2 pilot；不允许直接批量扩展细分或公司池。

| Condition | Status | Notes |
|---|---|---|
| P1细分报告模板稳定 | PASS | 已生成segment_report |
| P1个股报告模板稳定 | PASS | 已生成2家公司样本 |
| evidence_manifest可复用 | PASS | 15条证据已登记，并已拆分source_url/raw_file_path、review_status和archive_policy |
| claims/metrics registry可复用 | PASS | 已保留draft层，并新增claims_registry.csv、metrics_registry.csv |
| segment_company_exposure可复用 | PASS | 已输出CSV，并增加verification_status、next_evidence_needed、last_reviewed_at、reviewer_note |
| quality-review能发现问题 | PASS | Tushare配置问题和收入占比缺口已记录 |
| company_universe字段支持比较 | PASS | 暴露类型、分数、置信度、证据齐全 |
| scorecard维度基本稳定 | PASS | 细分scorecard已补齐scoring_frameworks.yaml定义的8个维度；不作为交易信号 |
| watchlist能解释纳入理由 | PASS | config/watchlist.yaml已更新 |
| Tushare结构化数据可用 | PASS | stock_basic已成功；财务和公告深字段待补 |
| 液冷收入占比补证 | TODO | 横向比较前建议补 |
| medium issue治理 | PASS | quality_issues.csv已增加owner、due_date、blocking_for_stage |
| CI门禁 | PASS | 已新增GitHub Actions运行py_compile和pytest |

P2 readiness: READY_FOR_LIMITED_P2

限制：

- 不能把 READY_FOR_LIMITED_P2 理解为正式批量 P2。
- P2 pilot 开始前仍需保留液冷收入占比、订单、客户侧证据为 medium research TODO。
- watchlist 和 scorecard 只表示研究优先级与证据状态，不表示买卖建议。
