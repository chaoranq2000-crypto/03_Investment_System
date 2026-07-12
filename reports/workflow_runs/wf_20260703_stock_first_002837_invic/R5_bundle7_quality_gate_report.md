# R5 Bundle 7 — Reader quality gate report

status: `needs_fix`
as_of_date: `2026-07-12`
checked_by: `quality-review`

## Decision surfaces

- source scorecard: `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_report_reader_v2_quality_scorecard.yaml`
- source backflow plan: `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle7_quality_backflow_plan.yaml`
- reader decision: `rejected`
- quality band: `research_draft`
- score: `59/100`
- candidate threshold: `82`
- truthfulness status: `pass`
- human review status: `not_ready`
- candidate blocker count: `12`
- sample-quality promotion: `false`
- P2 promotion: `false`

## Outcome separation

真实性与研究深度使用不同决策面：当前报告没有 active critical/high truthfulness issue，因此真实性检查通过；12 个 medium issue 在 limited-pilot 口径下保持可见 TODO，但它们共同导致 Reader 未达到本轮明确的 candidate-ready 目标。因此工作流保持 `needs_fix`，不能沿用 Bundle 6 的 100 分候选结论，也不能自动进入人审、sample-quality 或 P2。

## R5 local gates

| local gate | status | evidence or next action |
|---|---|---|
| `R5-G1` Evidence Completeness | `fail_candidate_target` | 独立研究与同业经营证据不足；回流 `evidence-ingest`。 |
| `R5-G3` Business Breakdown | `fail_candidate_target` | 分析单元覆盖不足；回流 `stock-deep-dive`。 |
| `R5-G4` Industry Context | `fail_candidate_target` | 缺独立行业底层证据；回流 `segment-research`。 |
| `R5-G5` Forecast Model | `fail_candidate_target` | 预测仍非分业务/自下而上；回流 `stock-deep-dive`。 |
| `R5-G6` Valuation | `fail_candidate_target` | 缺反向或情景价值区间与可信同业口径；回流 `company-valuation`。 |
| `R5-G7` Market / Technical | `fail_candidate_target` | 技术输入缺失；回流 `stock-deep-dive`。 |
| `R5-G8` Sentiment / Event | `fail_candidate_target` | 情绪与事件链输入缺失；回流 `stock-deep-dive`。 |
| `R5-G9` Narrative Coherence | `fail_candidate_target` | 主报告低于研究密度门槛；回流 `memo-writer`。 |
| `R5-G10` No-Advice | `pass` | 未发现直接交易指令。 |
| `R5-G11` Sample Benchmark | `fail_candidate_target` | 当前为 honest research draft，不是 sample-quality candidate。 |

## Issue ownership

| owner | open medium issues | next stage |
|---|---:|---|
| `evidence-ingest` | 2 | `T2_evidence_acquire_parse` |
| `segment-research` | 1 | `T5_analysis_pack_build` |
| `stock-deep-dive` | 6 | `T5/T6/T7` fix routes |
| `company-valuation` | 2 | `RP6_valuation` |
| `memo-writer` | 1 | `T8_report_draft` |

完整 issue ID、target artifact 和说明以 `open_todos.csv` 与 `R5_bundle7_quality_backflow_plan.yaml` 为准。首个修复 owner 是 `evidence-ingest`；本 close task 不执行 Bundle 8，也不派发新的下层 handoff。

## Backflow and exposure

- workflow backflow: `quality_failure_to_fix_loop`
- next stage: `T2_evidence_acquire_parse`
- required next skill: `evidence-ingest`
- segment-company exposure update: `no_update_in_bundle7`
- no-update reason: 本 Bundle 只重做判差与状态回流，没有新增公司/细分暴露证据。
