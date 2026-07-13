# Handoff: R5_bundle9r_0_generation_binding -> stock-deep-dive

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `forward_rebuild_not_history_rewrite` |
| current_stage | `R5_bundle9r_1_input_review` |
| target_skill | `stock-deep-dive` |

## Objective

基于纠正版 Bundle 8R 证据代际，重建 002837 的 2026E-2028E 分部驱动、三情景预测、利润与现金流桥、敏感性及供估值消费的 model pack。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| user_request | `执行最新补丁包中的计划` | true | 最新包为 Bundle 9R |
| canonical_docs | `docs/workflows/RESEARCH_WORKFLOW.md` | true | 事实源 |
| orchestration_spec | `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | true | 运行规则 |
| evidence_generation_lock | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8r_evidence_generation_lock_v2.yaml` | true | 已通过输入哈希校验 |
| lock_correction | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8r_generation_lock_correction.yaml` | true | 原锁保留，不可消费 |
| financial_metrics | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/financial_metric_pack.csv` | true | reviewed metric anchors |
| normalized_statements | `data/processed/normalized/sina_financial_adapter_financial_statements_002837_2026-07-13_6e0ecd46.csv` | true | 2025A 显式科目 |
| source_gaps | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_failed_missing_disclosure_register.yaml` | true | 液冷分项缺口必须保留 |
| calculation_draft | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle9r/` | false | 仅作中间计算参考；旧代际且含禁用 plug，不得直接关闭 |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| input_review_ledger | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_input_review_ledger.yaml` | true | 输入逐项接受/拒绝/缺口 |
| forecast_assumptions | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_forecast_assumption_registry.yaml` | true | claim_type、证据、失效条件 |
| segment_driver_model | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_segment_driver_model.yaml` | true | 三个披露口径分部 |
| statement_bridge | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_financial_statement_bridge.yaml` | true | 禁止平衡 plug |
| scenario_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_scenario_pack.yaml` | true | bear/base/bull |
| sensitivity | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_sensitivity.csv` | true | 单变量及双变量 |
| consensus | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_consensus_comparison.csv` | true | 仅 analyst_view |
| model_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle9r_model_pack.yaml` | true | 供质量门与估值整合 |

## Required Artifacts

| artifact_type | path | required | notes |
|---|---|---:|---|
| generation_binding_validation | `.codex_tmp/R5_bundle9r_generation_binding_validation.yaml` | true | decision=pass |
| model_contract | `config/r5_bundle9r_model_contract.yaml` | true | 9R fail-closed contract |
| expected_artifacts | `config/r5_bundle9r_expected_artifacts.yaml` | true | 关闭清单 |

## Guardrails

- 不生成直接交易指令，不进入 P2，不允许 sample-quality。
- 液冷独立经济性不是发行人披露事实；若出现分析视图，必须为 `estimate`、关联 `missing_liquid_cooling_segment_economics`，且不得与三分部重复加总。
- 禁止 `other_operating_drag`、`plug`、`unexplained_residual` 等平衡项；营业利润必须由显式科目桥接。
- 旧 Bundle 9/10 与现有 `bundle10r/` 保持不变。

## Completion Criteria

- 所有预测期、情景与三个必需分部齐全，分部收入/毛利与公司桥精确勾稽。
- 收入、归母净利润及情景权益价值满足 bear <= base <= bull。
- 每个关键估计含 assumption_id、证据或显式 TODO、置信度与失效条件。
- 产物绑定 `evidence_gen_r5_bundle8r_231a51f4673156df`。

## Next Gate

| field | value |
|---|---|
| next_gate | `R5_bundle9r_5_valuation_rebuild` |
| gate_owner | `company-valuation` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| `missing_liquid_cooling_segment_economics` | medium | evidence-ingest | 保留未披露状态，后续刷新 |
| `missing_liquid_cooling_driver_conversion` | medium | stock-deep-dive | 不将订单/需求直接等同收入 |
| `missing_peer_liquid_cooling_purity` | medium | company-valuation | 同业集合维持低置信度且禁止排名 |
