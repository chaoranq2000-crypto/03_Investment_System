# Handoff: T9_quality_review -> stock-deep-dive

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `normal` |
| current_stage | `T9_quality_review` |
| target_skill | `stock-deep-dive` |

## Objective

根据真实人工反馈，把 Reader v4 的机械化十节审计脚手架重构为 Reader v5 的连贯研究叙事；保留全部证据、预测、估值、风险和边界，不新增事实或模型数值。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| user_request | 当前报告机械化、干涩；执行修改重构 | true | 人工审阅结论为 `revision_required` |
| source_payload | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_reader_payload_v4.yaml` | true | 只消费已审阅结构化内容 |
| historical_reader | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_reader_v4.md` | true | 保留原文件与精确哈希 |
| traceability | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_traceability_v4.yaml` | true | v5 引用必须重新生成并唯一解析 |
| style_contract | `docs/reporting/STOCK_REPORT_EXPRESSION_GUIDE.md` | true | 有主线、有分歧、有节奏、有反证 |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| normalized payload | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_reader_payload_v5.yaml` | true | 仍绑定当前 9R model generation |
| Reader v5 | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_reader_v5.md` | true | 自然段落叙事，不重复七标签 |
| traceability appendix | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_traceability_v5.yaml` | true | 每个显示引用唯一解析 |
| revision log | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_reader_v5_revision_log.md` | true | 记录 v4 问题和 v5 改法 |

## Guardrails

- 不覆盖或改写 Reader v4、v4 scorecard、v4 generation lock。
- 不新增事实、预测、估值数字、客户、订单、份额或交易建议。
- 事实、估计、推断、管理层表述和分析师观点继续分离。
- 正文移除模型工件哈希、质量门、候选状态和工作流收口等审计术语。
- 缺失的液冷独立经济性、DCF、SOTP 与同业可比性继续显式保留。

## Completion Criteria

- Reader v5 形成清晰研究主线，正文不再逐节重复“本节判断/关键事实/因果机制/经济含义/反向证据/不确定性/验证条件”。
- 预测、估值、技术/事件、风险和跟踪指标仍可追溯。
- v5 可确定性重建，引用唯一解析，no-advice 扫描通过。

## Next Gate

| field | value |
|---|---|
| next_gate | `G7`；附加本地 `R5-G9` Narrative Coherence Gate |
| gate_owner | `quality-review` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| `R5B10R-NARRATIVE-001` | high | `stock-deep-dive` | 生成 Reader v5 并通过反机械化质量门 |
