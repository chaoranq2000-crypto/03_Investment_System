# Handoff: stock-deep-dive -> quality-review

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| current_stage | `R5_bundle10_dynamic_writer_regression` |
| target_skill | `quality-review` |
| dispatch_status | `ready_for_reader_gate` |

## Scope

审查动态 Writer、Reader pack、v3 Reader、追溯附录、预测估值 gate adapter、技术/情绪/事件 pack、跨行业回归与外部人工复核边界。

## Automated Result

- Reader quality: `98/100`
- decision: `candidate_ready_for_human_review`
- truthfulness: `pass`
- blockers: `0`
- cross-industry regression: `2 cases / 2 industries / pass`
- external human review: `pending`
- sample quality / P2: `false / false`

## Guardrail

质量审查只能把产物路由到外部人工复核，不得生成外部审查者身份、签署时间或最终样例质量许可。
