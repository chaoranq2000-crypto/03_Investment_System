# Handoff: R5_bundle10_external_human_review_pending -> quality-review

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `normal` |
| current_stage | `R5_bundle10_external_human_review_pending` |
| target_skill | `quality-review` |

## Objective

按用户要求，以三名相互独立的 AI 子 agent 分担复杂语义评审，分别复核证据追溯、预测估值、叙事风险，并形成一份可审计的合并建议，供真实用户作最后确认。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| user_request | `这个人工评审太过复杂，请用子agent帮我评审` | true | 用户授权子 agent 执行复杂复核，不等于真人签署 |
| canonical_docs | `docs/workflows/RESEARCH_WORKFLOW.md` | true | 全局门禁事实源 |
| orchestration_spec | `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | true | 运行时规则 |
| reader_report | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_report_reader_v3.md` | true | 审阅全文 |
| traceability_appendix | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_report_traceability_v3.yaml` | true | 引用与边界核验 |
| quality_scorecard | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_stock_research_report_reader_v3_quality_scorecard.yaml` | true | 自动门结果，仅作输入 |
| forecast_and_valuation | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/forecast_bridge.yaml`; `segment_forecast_model.yaml`; `valuation/valuation_model.yaml`; `scenario_valuation.yaml`; `reverse_valuation.yaml` | true | 独立重算与口径检查 |
| market_event_context | `R5_bundle10_technical_market_pack.yaml`; `R5_bundle10_sentiment_event_pack.yaml` | true | 日期、边界与反证检查 |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| panel_review_yaml | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10_independent_subagent_review.yaml` | true | 三个领域结果、HR-1 至 HR-6 建议、阻断项 |
| panel_review_md | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10_independent_subagent_review.md` | true | 给用户的一页式复核结论 |

## Required Artifacts

| artifact_type | path | required | notes |
|---|---|---:|---|
| bundle10_independent_subagent_review | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10_independent_subagent_review.yaml` | true | 机器可读面板结论 |
| bundle10_independent_subagent_review_readout | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10_independent_subagent_review.md` | true | 简化用户确认 |

## Guardrails

- 三名评审者均必须标记为 `independent_ai_subagent`，不得声称是 human 或 external reviewer。
- 只读评审；如发现实质问题，由主 agent 判断并路由修复。
- 不生成或代填真实评审者身份、时间戳、人工 attestations。
- 不创建买入、卖出、持有、目标价或仓位建议。
- 不编造 evidence、claim、metric、业务占比、订单、客户或估值数字。
- 保持 fact / estimate / inference / management_comment / analyst_view / opinion 边界。
- 精确哈希问题与语义内容问题分开记录。

## Completion Criteria

- 三名子 agent 均返回结构化、相互独立的结论。
- 证据域至少抽样回溯 10 个关键表述或数字。
- 预测估值域至少独立重算 8 个关键关系。
- 叙事风险域逐段检查可读性、风险、技术情绪事件边界和禁止事项。
- 合并产物覆盖 HR-1 至 HR-6，列出 blocker、nonblocker、分歧与主 agent 裁决。
- 明确说明子 agent 面板不能自行满足 `external_human_review`，最终关闭仍需真实用户明确确认。

## Next Gate

| field | value |
|---|---|
| next_gate | `R5_bundle10_external_human_review` |
| gate_owner | `quality-review` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| `R5B10-G11-001` | medium | `quality-review` | 子 agent 完成复杂复核后，交给真实用户作最终确认 |
| `R5B10-QR-HUMAN-001` | medium | `quality-review` | 保持 AI 面板与外部人工签署身份边界 |
