# R5 Bundle 9 Local Close Readout

- workflow_id: `wf_20260703_stock_first_002837_invic`
- close_date: `2026-07-13`
- decision: `accepted_with_todos`
- bundle_closed: `true`
- reader_regenerated: `false`
- reader_state: `59/82, research_draft, rejected`
- sample_quality_allowed: `false`
- repository_publish: `not_authorized_not_performed`
- remote_ci: `TODO_AFTER_EXPLICIT_PUBLISH`

## Outcome

Bundle 9 已在本地完成自下而上预测、显式利润与现金流桥、三情景、敏感性、分析师差异、静态/动态估值、四家同业上下文、反向估值和情景市值区间。Canonical workflow 继续保持 `needs_fix`，下一路由切换到 Bundle 10 的动态 Writer、跨行业回归与人工审查；这不是 Reader 或样例质量许可。

## Close Evidence

| item | result |
|---|---|
| forecast assumptions | 42 rows; all carry evidence and metric anchors |
| forecast model | three business lines; three scenarios; 2026E-2028E |
| profit bridge | nine scenario-years; maximum reconciliation difference 0 |
| forecast sensitivity | 12 rows across revenue, margin, opex and working capital |
| market inputs | one reviewed subject row and four same-date peer rows |
| dynamic valuation | base PE 193.6x / 137.2x / 105.7x for 2026E-2028E |
| scenario valuation | three 2027E market-cap ranges with explicit multiple assumptions |
| reverse valuation | five PE stress points reconciled to current market cap |
| analyst context | two-broker midpoint comparison; three analyst_view rows |
| quality decision | accepted_with_todos; no active critical/high issue |
| full regression | 617 passed, 2 skipped |

## Preserved Gaps

1. 液冷独立收入、毛利率与利润贡献仍为 `MISSING_DISCLOSURE`。
2. 同业远期倍数与全部官方年报逐项数值对账尚未完成，peer set 保持低置信。
3. 企业价值、净负债、折现率和终值增速缺失，DCF 保持跳过。
4. 液冷独立经济性与未分配成本缺失，SOTP 保持跳过。
5. Reader、动态 Writer、两个跨行业样本、人工审查与最终样例质量门仍属 Bundle 10。

## Next Route

`research-orchestrator -> stock-deep-dive -> quality-review`，进入 Bundle 10；动态 Writer 必须消费结构化 pack，不得自由新增公司事实或估值数字。

## Research Boundary

本 readout 记录研究模型与工作流状态，不形成交易动作或收益承诺。
