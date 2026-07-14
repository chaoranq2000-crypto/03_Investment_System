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

Reader v5 的精确哈希人工审阅结论为 `revision_required`。在取得可执行的人审意见后，创建版本化后继 Reader，修复人工指出的问题，并保持证据、claim、metric、估值方法和无建议边界不变。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| user_request | `审阅结果为不通过；执行完成最新补丁包中的计划` | true | 人工结论优先于自动分数 |
| canonical_docs | `docs/workflows/RESEARCH_WORKFLOW.md` | true | 全局阶段与门禁事实源 |
| orchestration_spec | `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | true | fix loop 与状态同步规则 |
| human_feedback | `R5_bundle10r_human_feedback_v5.yaml` | true | 绑定 Reader v5 精确哈希 |
| source_artifact | `R5_bundle10r_reader_v5.md` | true | 历史锁定，不得原地覆盖 |
| source_payload | `R5_bundle10r_reader_payload_v5.yaml` | true | 不得新增未审查事实 |
| traceability | `R5_bundle10r_traceability_v5.yaml` | true | 22 个显示引用当前均可解析 |
| reviewer_detail | `MISSING_ACTIONABLE_REVIEW_DETAIL` | true | 需至少一条章节或段落级意见 |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| actionable feedback mapping | `R5_bundle10r_human_feedback_v5.yaml` 或后续补充记录 | true | 每条反馈映射到章节、owner 和验收标准 |
| versioned narrative plan | `R5_bundle10r_reader_narrative_plan_v6.yaml` | true | 取得反馈后创建 |
| versioned Reader | `R5_bundle10r_reader_v6.md` | true | 不覆盖 v5 |
| versioned traceability | `R5_bundle10r_traceability_v6.yaml` | true | 所有显示引用唯一解析 |
| quality handoff | `handoffs/33_to_quality-review_bundle10r_reader_v6.md` | true | 重新执行 G7/G9 与局部门禁 |

## Required Artifacts

| artifact_type | path | required | notes |
|---|---|---:|---|
| human review failure record | `R5_bundle10r_human_feedback_v5.yaml` | true | `revision_required` |
| v5 generation lock | `R5_bundle10r_reader_generation_lock_v5.yaml` | true | 保持原始字节和哈希 |
| current issue ledger | `open_todos.csv` | true | high issue 必须保持 open |

## Guardrails

- 不得创建买入、卖出、持有、仓位或目标价指令。
- 不得新增证据、事实、预测、估值数值、液冷收入占比或客户订单结论。
- 不得把自动分数当成人工通过。
- 不得在缺少可执行反馈时凭空推测失败原因或盲目生成 v6。
- v5 报告及六项 generation-lock 工件必须保持原始字节。

## Completion Criteria

- 至少一条人工反馈被映射到具体章节、段落或表达问题。
- 后继 Reader 以新版本生成，v5 历史哈希不变。
- 所有 material 句子继续可追溯，claim 类型与缺口未被加强。
- 非补偿质量门、无建议门、确定性重建和精确哈希人审重新完成。

## Next Gate

| field | value |
|---|---|
| next_gate | `G7 Stock Report Gate`、`G9 No Advice Gate`、Bundle 10R local narrative gate |
| gate_owner | `quality-review` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| `R5B10R-V5-HUMAN-FAIL-001` | high | `stock-deep-dive` | 取得可执行反馈后创建版本化后继 Reader |
| `R5B10R-DCF-001` | medium | `company-valuation` | 补齐方法输入后重检 DCF 资格 |
| `R5B10R-SOTP-001` | medium | `company-valuation` | 补齐分部经济性与消除关系后重检 SOTP 资格 |
