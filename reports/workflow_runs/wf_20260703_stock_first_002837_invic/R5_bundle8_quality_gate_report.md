# R5 Bundle 8 Quality Gate Report

- workflow_id: `wf_20260703_stock_first_002837_invic`
- workflow_type: `stock_first_closed_loop`
- review_scope: `M3_evidence_coverage_and_research_inputs + M4_research_analysis_engine`
- review_date: `2026-07-12`
- decision: `accepted_with_todos`
- decision_scope: `bundle8_local_m3_m4_input_gate_only`
- integration_gate: `bundle8_research_depth_inputs_ready`
- bundle_closed: `false`
- reader_regenerated: `false`
- workflow_state_mutated: `false`

## 1. 结论

Bundle 8 的真实 M3/M4 输入已通过本地质量审查：Evidence Coverage Matrix 为 `7/7 covered`，Analysis Pack v2 为 `7/7 complete`，两类 validator 均为 `pass`，组合 gate 为 `bundle8_research_depth_inputs_ready`。

该结论只表示证据覆盖和分析输入已准备好进入后续 close 审查，不表示 Reader 已完成、Bundle 8 已关闭、现有 workflow TODO 已解决，也不表示可以进入 P2。

## 2. Gate 结果

| gate | status | evidence |
|---|---|---|
| G1 Evidence Gate | pass | global manifest 与 workflow-local manifest 的 schema/path 校验均为 `[]` / `PASS`；14 个 reviewed underlying sources，10 个 independent underlying sources |
| G2 Claim Gate | pass | 发行人事实、研究机构 `analyst_view`、政策事实、反向推断和 `counter_evidence` 分离；搜索摘要未直接晋升为证据 |
| G3 Metric Gate | pass_with_visible_todo | 新增指标均有 period、value、unit、source_evidence_id、calculation_method 与 locator；液冷分项收入/毛利仍为可见缺口 |
| G4 Segment Report Gate | pass_for_source_handoff | `industry_evidence_pack.yaml` validator：demand=2、supply=2、errors=0；本轮不写完整细分报告 |
| G7 Stock Report Gate | not_applicable_to_reader | 本轮只审查 Analysis Pack v2，不重新生成 Reader；七个分析单元均有 judgment/trend/mechanism/financial impact/counterevidence/falsification/watch metrics |
| G9 No Advice Gate | pass | 对 source catalog、analysis inputs/pack、五个 subpack 和 integration gate 扫描，直接交易语言命中数为 0 |
| G10 Close Gate | not_checked | Bundle 8 close 必须由独立 close-only patch 完成，并在明确发布后核验 GitHub Actions |

### R5 local gate representation

`R5_bundle8_quality_issues.csv` 显式记录 `R5-G1` 至 `R5-G11`，并通过质量问题校验器。这里的 `waived_with_reason` 只表示对应模块不属于 Bundle 8 的 M3/M4 输入门，不表示完整 R5 gate 已通过。

| R5 gate | Bundle 8 record | boundary |
|---|---|---|
| R5-G1 Evidence Completeness | resolved | 7/7 coverage，14 个 reviewed underlying sources |
| R5-G2 Financial Model | out_of_scope (`waived_with_reason`) | 本轮只审查历史财务质量；完整模型留给 Bundle 9 |
| R5-G3 Business Breakdown | accepted_todo | 液冷分项收入、毛利、客户订单和回款仍缺失 |
| R5-G4 Industry Context | resolved | demand=2、supply=2，反证可见 |
| R5-G5 Forecast Model | out_of_scope (`waived_with_reason`) | Bundle 9 |
| R5-G6 Valuation | out_of_scope (`waived_with_reason`) | Bundle 9 |
| R5-G7 Market / Technical | out_of_scope (`waived_with_reason`) | Bundle 10 |
| R5-G8 Sentiment / Event | out_of_scope (`waived_with_reason`) | Bundle 10 |
| R5-G9 Narrative Coherence | resolved_for_analysis_pack | 七个分析单元内部闭环；不代表 Reader 已改写 |
| R5-G10 No-Advice | resolved | 直接交易语言扫描零命中 |
| R5-G11 Sample Benchmark | out_of_scope (`waived_with_reason`) | 当前 Reader 仍 rejected；Bundle 10 后再审查 |

## 3. Evidence Coverage 审查

| item | result |
|---|---:|
| blocking requirements | `7 / 7 covered` |
| reviewed underlying sources | `14` |
| independent underlying sources | `10` |
| industry demand independent sources | `2` |
| industry supply/competition independent sources | `2` |
| reviewed peer entities | `4` |
| open evidence blockers | `0` |

关键边界：

- 中国信通院 2025 报告保留为 `analyst_view/context`；物理页 32 的 30kW、PUE 案例及冷板/浸没路线已用渲染页核验。
- 国家发改委等四部门政策保留为政策事实；物理页 1-4 的上架率、PUE 目标与多技术路线已核验。
- 两份来源均同时提供支持证据和反向约束：液冷需求存在，但不是唯一高效制冷路线。
- 公司和同业结构化财务快照保持 metric-only，不证明液冷收入、订单、客户或份额。

## 4. Analysis Pack v2 审查

| section | analysis_id | status | confidence |
|---|---|---|---|
| core_thesis | `AN-CORE-001` | complete | medium |
| financial_quality | `AN-FINANCIAL-001` | complete | medium |
| business_driver | `AN-BUSINESS-DRIVER-001` | complete | medium |
| segment_economics | `AN-SEGMENT-ECONOMICS-001` | complete | low |
| industry_context | `AN-INDUSTRY-001` | complete | medium |
| competitive_position | `AN-COMPETITION-001` | complete | low |
| risk_counterevidence | `AN-RISK-001` | complete | medium |

审查确认：

- 公司整体收入、利润、毛利率和现金流没有被归因到液冷分部。
- 分业务经济性明确拒绝填造液冷收入、毛利率、客户、订单与项目回款。
- 同业比较只比较证据层级和公司整体指标限制，没有形成份额或优劣排名。
- 七个单元均包含反证、证伪条件和可复核观察指标。
- 五个 subpack 仅由 complete units 确定性拆分，没有新增事实。

## 5. 可重复性与回归验证

| check | result |
|---|---|
| Bundle 8 evidence builder | `pass; 7/7; blockers=0` |
| Industry evidence validator | `pass; demand=2; supply=2; errors=0` |
| Bundle 8 analysis builder | `pass; 7/7; blockers=0` |
| Analysis pack validator | `pass; complete=7; errors=0` |
| Integration gate | `bundle8_research_depth_inputs_ready` |
| deterministic rebuild | `12 artifacts checked; 0 hash changes` |
| focused pytest | `22 passed` |
| full repository pytest | `575 passed, 2 skipped` |
| Reader truthfulness recheck | `pass; truthfulness_blockers=0` |
| no-advice scan | `0 hits` |

## 6. 状态与 Reader 不变性

- `workflow_state.yaml` SHA256 before/after: `74DD6D7C067C7A218B594B8A98535AA2E4A08E3833281E256A26B8D79B976891`
- `R5_stock_research_report_reader_v2.md` SHA256 before/after: `54EC29F5E1BB6302CC63BD3CFC2AE91DCF60AC2A4754918A15C308B1AAE96309`
- Reader 复检仍为 `score=59`、`quality_band=research_draft`、`decision=rejected`、`truthfulness=pass`。

这证明 Bundle 8 gate 没有通过修改 Reader 或 canonical state 来制造“完成”外观。

## 7. 保留 TODO

1. `R5B8-G3-001`（medium，accepted_todo）：液冷分项收入、毛利、客户订单和项目现金回款仍未披露；owner=`evidence-ingest`。
2. `R5B8-QR-CI-001`（low，accepted_todo）：未发布变更没有对应 GitHub Actions 结果；owner=`research-orchestrator`，仅在明确发布后核验。

## 8. Research Boundary

本报告用于证据、分析输入和工作流质量审查，不构成任何买入、卖出、持有、目标价、仓位或其他交易建议。
