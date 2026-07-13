# Handoff: quality-review -> research-orchestrator

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| current_stage | `R5_bundle8b_close_quality_review` |
| target_skill | `research-orchestrator` |
| dispatch_status | `ready_for_local_close` |

## Decision

`accepted_with_todos`；无 active critical/high issue，允许本地关闭 Bundle 8，并把下一路由切换到 Bundle 9 的 `stock-deep-dive`。该决定不授权提交、推送、远端 CI 声明或 Reader 发布。

## Authoritative Inputs

| input | path | status |
|---|---|---|
| quality report | `bundle8_close_quality_report.md` | accepted_with_todos |
| quality issues | `R5_bundle8b_close_quality_issues.csv` | validator accepted_with_todos |
| deterministic validation | `R5_bundle8b_close_input_validation.json` | pass |
| route quality | `R5_bundle8b_source_route_quality_report.yaml` | pass; 12 capabilities; 0 blocking |
| full regression | repository pytest | 605 passed, 2 skipped |

## Required Close Mutations

- `workflow_state.yaml`: add Bundle 8A/8B/close stages; keep `status=needs_fix`; set next stage to Bundle 9.
- `open_todos.csv`: resolve evidence/industry/peer/technical input gaps that are now proven; retain disclosure, valuation, sentiment, writer and CI TODOs.
- `artifact_manifest.csv`: register every Bundle 8A/8B close artifact with unique IDs and existing paths.
- `run_log.md`: append a changelog; do not rewrite historical Bundle 7/8 entries.
- Reader and scorecard: unchanged.

## Guardrails

- 2024 年约 3 亿元保持 B 类 `management_comment`。
- 新结构化候选不自动 promotion。
- Bundle 8 close 不等于 Bundle 9/10、Reader 或样例质量完成。
- 不进入 P2，不输出交易建议。

## Next Gate

Bundle 9 M5/M6：自下而上预测、三情景、敏感性、同业经营比较、reverse valuation 与 scenario value range。
