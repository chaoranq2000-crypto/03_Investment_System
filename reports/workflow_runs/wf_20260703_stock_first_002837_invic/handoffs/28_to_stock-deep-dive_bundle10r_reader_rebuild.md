# Handoff: T7 Stock Report Draft -> stock-deep-dive

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `normal` |
| current_stage | `T7 Stock Report Draft`（local: `R5_bundle10r_reader_rebuild`） |
| target_skill | `stock-deep-dive` |

## Objective

从已关闭的 Bundle 9R 模型代际前向重建 002837 Reader v4，形成可复算的 Reader 输入、动态分析 payload、正文与独立追溯附录；不得继承旧 Reader v3 或旧证据代际的当前性。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| user_request | 执行完成最新补丁包中的计划 | true | 完成 Bundle 10R.0–10R.8，不止应用 overlay |
| canonical_docs | `docs/workflows/RESEARCH_WORKFLOW.md` | true | 全局 workflow/gate 事实源 |
| orchestration_spec | `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | true | 状态、handoff 与 close 规则 |
| package_plan | `docs/plans/R5_BUNDLE_10R_READER_REBUILD_PLAN.md` | true | 10R 执行顺序与边界 |
| model_lock | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_model_generation_lock.yaml` | true | 必须验证 13 项哈希 |
| evidence_lock | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8r_evidence_generation_lock_v2.yaml` | true | 唯一可前向消费的证据代际 |
| historical_candidate | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle10r/` | false | 仅作叙事素材；其旧 `b82...` generation 结论不可复用 |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| reader_input | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_reader_input_pack.yaml` | true | claim type、引用、反证、不确定性、观察点齐全 |
| normalized_payload | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_reader_payload_v4.yaml` | true | 精确绑定 9R model generation |
| reader | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_reader_v4.md` | true | 无内部路径、raw IDs、机器状态 token 或行动语言 |
| traceability | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_traceability_v4.yaml` | true | 每个 display reference 唯一解析 |

## Required Artifacts

| artifact_type | path | required | notes |
|---|---|---:|---|
| generation_binding | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_generation_binding_validation.yaml` | true | 13 项真实哈希通过 |
| workflow_state | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/workflow_state.yaml` | true | 历史 Bundle 10 块保留 |

## Guardrails

- 旧 `R5_bundle8r_evidence_generation_lock.yaml` 已被纠正，只能历史保留；前向消费必须使用 v2 lock。
- 9R 预测和三情景属于 `estimate`，不是发行人指引。
- 液冷独立经济性保持 `unknown`、`non_additive`，不得用公司整体指标替代。
- 四家同业保持低置信度上下文，不做确定性排名。
- 缺失 DCF、SOTP 或未来事件官方日期时，正文使用自然语言说明边界，不泄露机器 token。
- 不输出买入、卖出、持有、目标价、仓位或确定收益；不进入 sample-quality 或 P2。

## Completion Criteria

- 10 个必需章节均满足判断、至少两项事实、因果、经济含义、反证、不确定性、至少两个观察点及 display references。
- 技术、情绪和未来事件具备日期、影响路径、验证指标与反证条件。
- Writer 对发行人无硬编码，Reader 对相同输入字节稳定。
- 所有正文引用在独立追溯附录中唯一解析。

## Next Gate

| field | value |
|---|---|
| next_gate | `G7 Stock Report Gate`，随后 `G9 No Advice Gate` |
| gate_owner | `quality-review` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| `R5B10R-TODO-DCF` | medium | `company-valuation` | 保留方法输入不足，不在 Writer 层补齐 |
| `R5B10R-TODO-SOTP` | medium | `company-valuation` | 等待可复算的液冷独立经济性 |
| `R5B10R-TODO-HUMAN` | medium | `human` | 自动门通过后对精确 Reader generation 执行真实人工复核 |
