# Bundle 9 Forecast and Valuation Quality Report

- workflow_id: `wf_20260703_stock_first_002837_invic`
- review_date: `2026-07-13`
- reviewer_skill: `quality-review`
- decision: `accepted_with_todos`
- close_recommendation: `bundle9_can_close_locally`
- reader_regenerated: `false`
- sample_quality_allowed: `false`
- remote_ci_claimed: `false`

## 结论

Bundle 9 的预测与估值模型已形成可追溯、可复算的本地候选：42 条审阅假设覆盖三条宽口径业务线、三种情景和三年预测；收入、毛利、费用、税率、少数股东损益、营运资本、经营现金流与资本开支分别建桥，九个年度情景的利润勾稽差额均为零。估值层已生成静态与动态倍数、四家同业上下文、三情景市值区间、反向估值、敏感性及两家机构预测差异。

该决定不把缺失输入藏起来：液冷独立经济性、同业远期倍数、企业价值与净负债、DCF 折现与终值输入仍为显式 TODO；同业集合保持 `LOW_CONFIDENCE_PEER_SET`，估值 pack 保持 `partial`，全部新产物继续 `sample_quality_allowed=false`。Reader 仍为原有 `59/82`、`rejected`，等待 Bundle 10。

## Gate 结果

| gate | status | evidence |
|---|---|---|
| G1 Evidence Gate | pass | 42/42 假设同时有 evidence 与 metric 锚点 |
| G2 Financial Model Gate | pass | 三情景、三年、显式利润与现金流桥；最大勾稽差额 0 |
| G3 Business Breakdown Gate | pass_with_todos | 三条审计宽口径业务线可用；液冷独立经济性继续缺失 |
| G4 Context Gate | pass | 既有独立行业来源与反证继续有效 |
| G5 Forecast Gate | pass | 四个预测契约校验器接受；敏感性 12 行 |
| G6 Valuation Gate | pass_with_todos | 输入、pack 与 handoff 校验接受；DCF/SOTP 显式跳过 |
| G7 Market Gate | pass | 2026-07-10 主体与四家同业同日快照可追溯 |
| G8 Sentiment / Event Gate | pass_with_todos | 两家机构仅作 analyst_view；完整分层留给 Bundle 10 |
| G9 Narrative Gate | pass | fact/estimate/inference/analyst_view/unknown 分离 |
| G10 No Advice Gate | pass | 9 个核心文件边界词扫描 0 命中 |
| G11 Sample Benchmark | waived_with_reason | Reader 未重生成，样例许可保持 false |

## 可重复性与测试

| check | result |
|---|---|
| Bundle 9 deterministic close validator | `pass`; 23 artifacts; 42 assumptions; scenario checks=6; reverse checks=5 |
| forecast focused tests | `3 passed` |
| valuation focused tests | `3 passed` |
| close focused test | `1 passed` |
| normalized valuation input validator | `accepted`; 0 issues |
| forecast validators | `accepted / accepted / accepted / accepted_with_todos` |
| valuation validators | input registry=`source_gapped_research_draft`; company output=`accepted_with_todos`; pack=`accepted`; handoff=`accepted` |
| quality issue validator | `accepted_with_todos` |
| full repository regression | `617 passed, 2 skipped` |

## 关键模型边界

1. 2025 基期使用年报披露的机房温控、机柜温控与审计总额残差，不把液冷单列成未经披露的分部。
2. 2024 年约 3 亿元液冷技术相关收入只作为 `management_comment` 方向锚，不外推为 2025 事实。
3. 分析师比较只有两家不同机构，且股本口径未独立核验，只能作为 `analyst_view`。
4. 情景市值区间使用显式研究倍数，不能解释为历史公允区间。
5. 现金流桥存在不等于 DCF 输入充分；缺折现率、终值和净负债时方法保持跳过。
6. 四家同业的市场倍数同日同源，但业务组合与液冷纯度差异使排名无效。

## Accepted TODOs

- `R5B9-G3-001`：液冷独立收入、毛利和利润仍未披露。
- `R5B9-G6-001`：同业远期倍数、企业价值、净负债和内在价值方法输入待补。
- `R5B9-G8-001`：机构样本与股本口径限制需在 Bundle 10 Reader 中继续披露。
- `R5B9-QR-VAL-PEER-001`：同业官方数值逐项对账与业务纯度不足。
- `R5B9-QR-VAL-DCF-001`：DCF 方法门未满足。
- `R5B9-QR-VAL-SOTP-001`：SOTP 方法门未满足。
- `R5B9-QR-CI-001`：未获发布授权，不声明远端 CI。

## Research Boundary

本报告只审查研究模型、估值上下文、证据缺口和工作流状态，不形成交易动作或收益承诺。
