# Handoff: T9_quality_review -> quality-review

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `normal` |
| current_stage | `T9_quality_review` |
| target_skill | `quality-review` |

## Objective

对 Bundle 8 的真实 M3/M4 输入执行证据、claim、metric、分析闭环和 no-advice 审查，验证所有生成物可由原始输入重复构建，并运行组合 gate；不得修改 canonical workflow state、重新生成 Reader 或自动关闭 Bundle 8。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| user_request | 执行完补丁包中的计划 | true | 完成 Bundle 8 本地执行链 |
| source_catalog | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8_evidence_source_catalog.yaml` | true | reviewed sources only |
| coverage_matrix | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/evidence_coverage_matrix.yaml` | true | 7/7 covered |
| analysis_inputs | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8_analysis_inputs_v2.yaml` | true | 7 analyst-authored units |
| analysis_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/analysis_pack_v2.yaml` | true | 7/7 complete |
| global_manifest | `data/manifests/evidence_manifest.csv` | true | schema/path validator input |
| run_manifest | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/data/manifests/evidence_manifest.csv` | true | 相对 run 根目录校验 |
| claims_registry | `data/manifests/claims_registry.csv` | true | claim type 与 locator |
| metrics_registry | `data/manifests/metrics_registry.csv` | true | period/unit/source/method |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| integration_gate | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8_research_depth_gate.yaml` | true | 脚本生成 |
| integration_readout | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8_research_depth_gate.md` | true | 脚本生成 |
| quality_report | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8_quality_gate_report.md` | true | 记录 G1/G2/G3/G7/G9 与本地门 |
| quality_issues | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8_quality_issues.csv` | true | 零 open high issue |

## Guardrails

- 不把 gate 通过解释为 Reader 已完成或 Bundle 8 已 close。
- 不解决 Bundle 9/10 的 forecast、valuation、market、Reader TODO。
- 公司整体指标不得证明液冷业务贡献；分项缺口必须继续可见。
- 行业研究观点保留 `analyst_view`，政策与行业需求不证明公司订单。
- 同业经营口径不完整时禁止份额/优劣排名。
- 禁止买卖建议、目标价、仓位、保证收益或技术信号操作化。

## Completion Criteria

- evidence coverage gate 和 analysis pack gate 均为 `pass`。
- source catalog、matrix、analysis pack 与五个 subpack 可重复构建。
- global/run-local manifest schema/path 校验均通过。
- claim type、metric period/unit/source/method 与反证链可抽样回溯。
- no-advice/truthfulness 检查和 Bundle 8 focused tests 通过。
- 全仓库 pytest 通过；未发布变更的远端 CI 状态单独披露。
- workflow state hash 和 Reader hash 在 gate 前后不变。

## Next Gate

| field | value |
|---|---|
| next_gate | `G10 Close Gate` |
| gate_owner | `research-orchestrator` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| `B8-CI-PENDING` | low | research-orchestrator | 仅在后续明确发布后由 GitHub Actions 验证未发布变更 |
