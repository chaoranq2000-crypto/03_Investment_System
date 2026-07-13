# Handoff: T9 Quality Review -> quality-review

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `normal` |
| current_stage | `T9 Quality Review`（local: `R5_bundle10r_non_compensating_gate`） |
| target_skill | `quality-review` |

## Objective

对 Bundle 10R Reader v4 执行不可抵消质量审查：模型代际、claim boundary、10 个分析单元、引用唯一解析、来源多样性、技术/情绪/未来事件日期、正文卫生和禁止直接行动语言必须分别通过；总分不得抵消核心失败。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| reader_input | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_reader_input_pack.yaml` | true | 审阅输入与 claim boundary |
| payload | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_reader_payload_v4.yaml` | true | 结构化分析单元 |
| reader | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_reader_v4.md` | true | 主报告 |
| traceability | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_traceability_v4.yaml` | true | 展示引用到内部来源的独立附录 |
| binding | `config/r5_bundle10r_generation_binding.yaml` | true | 精确模型代际 |
| reader_contract | `config/r5_bundle10r_reader_contract.yaml` | true | 10 节及分析单元最低要求 |
| quality_contract | `config/r5_bundle10r_quality_contract.yaml` | true | 正向计分且核心失败不可抵消 |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| scorecard | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_quality_scorecard.yaml` | true | truth/core/candidate blockers 分开 |
| quality_issues | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_quality_issues.csv` | true | 保留 medium/low TODO 与 owner |
| quality_report | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_quality_gate_report.md` | true | 记录 G1/G2/G3/G7/G9 与 local gate 结果 |

## Required Artifacts

| artifact_type | path | required | notes |
|---|---|---:|---|
| generation_binding | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10r_generation_binding_validation.yaml` | true | 13/13 哈希通过 |
| model_lock | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_model_generation_lock.yaml` | true | 当前模型事实源 |

## Guardrails

- 核心章节任一失败即阻断，不得用总分抵消。
- consensus 只能是 `analyst_view` 或 `estimate`。
- 液冷独立经济性必须保持未量化、`non_additive`。
- 低置信度同业不得形成确定性排序。
- 主报告不得泄露内部路径、内部 IDs、机器状态 token、直接行动语言或虚构人审状态。
- 自动门通过只允许生成 `pending` 人审交接；sample-quality 与 P2 继续为 false。

## Completion Criteria

- `decision=candidate_ready_for_human_review`。
- truthfulness、core-section、candidate blocker 均为 0。
- 22 个展示引用全部唯一解析；issuer、industry、peer、market 四类来源均存在，peer 独立来源不少于 3。
- G1、G2、G3、G7、G9 通过；未解决事项有 severity、owner 和 next action。

## Next Gate

| field | value |
|---|---|
| next_gate | `G10 Close Gate`（自动候选通过后仍需真实人审状态与 generation lock） |
| gate_owner | `research-orchestrator` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| `R5B10R-TODO-DCF` | medium | `company-valuation` | 保留方法输入缺口 |
| `R5B10R-TODO-SOTP` | medium | `company-valuation` | 等待液冷独立经济性披露 |
| `R5B10R-TODO-HUMAN` | medium | `human` | 对锁定后的精确 Reader generation 进行真实复核 |
