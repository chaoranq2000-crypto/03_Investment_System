# Handoff: T5_analysis_pack_build -> stock-deep-dive

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `normal` |
| current_stage | `T5_analysis_pack_build` |
| target_skill | `stock-deep-dive` |

## Objective

以通过证据门的 source catalog、coverage matrix、reviewed claims/metrics 为输入，填写七个公司特异、可证伪的分析单元，并通过确定性构建器生成 Analysis Pack v2 与五个 subpack。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| user_request | 执行完补丁包中的计划 | true | 仅 Bundle 8 M4 |
| source_catalog | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8_evidence_source_catalog.yaml` | true | reviewed source/claim/metric IDs |
| coverage_matrix | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/evidence_coverage_matrix.yaml` | true | 7/7 `covered` |
| industry_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/industry_evidence_pack.yaml` | true | 独立 demand/supply 输入 |
| peer_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/peer_operating_pack.yaml` | true | 4 家 peer entity |
| company_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/company_operating_evidence_pack.yaml` | true | 发行人和 metric-only 经营输入 |
| reviewed_claims | `data/manifests/claims_registry.csv` 与 workflow-local `claims_registry.csv` | true | 类型与 locator 保持不变 |
| reviewed_metrics | `data/manifests/metrics_registry.csv` | true | period/unit/source/calculation_method 完整 |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| analysis_inputs | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8_analysis_inputs_v2.yaml` | true | analyst-authored，不由程序编造 |
| analysis_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/analysis_pack_v2.yaml` | true | 构建器生成 |
| thesis_tree | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/thesis_tree.yaml` | true | complete units 派生 |
| business_driver_tree | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/business_driver_tree.yaml` | true | complete units 派生 |
| segment_economics | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/segment_economics.yaml` | true | 不填造分业务收入/毛利 |
| competitive_position_matrix | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/competitive_position_matrix.yaml` | true | 明示可比/不可比边界 |
| risk_counterevidence_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/risk_counterevidence_pack.yaml` | true | 风险、反证、证伪条件、观察指标 |

## Guardrails

- 七个单元都必须区分 `fact`、`analyst_view` 与 `inference`，正文不新增未登记事实。
- 公司整体财务指标不得归因于液冷业务。
- 液冷收入、毛利率、客户、订单和产能未披露时，只能写“未披露/无法量化”，不能填数。
- 同业产品线索与公司整体指标不是可直接比较的液冷分部指标，不做排名。
- 政策和行业报告只能支持行业机制与技术路线，不能证明英维克商业兑现。
- 每个单元必须包含反证、证伪条件和可量化观察指标。
- 不进入 forecast/valuation、Reader/Writer、P2，不输出交易建议。

## Completion Criteria

- 七个 required sections 各有且仅有至少一个 `complete` 单元。
- 每个单元的 source/metric 引用都在 source catalog 中可解析。
- `scripts/build_r5_analysis_pack_v2.py` 非 `--allow-blocked` 模式返回 0。
- `.agents/skills/stock-deep-dive/scripts/validate_r5_analysis_pack_v2.py` 返回 0。
- 五个 subpack 可从 analysis inputs 确定性重建且不新增事实。

## Next Gate

| field | value |
|---|---|
| next_gate | `G7 Stock Report Gate` |
| gate_owner | `quality-review` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| `R5Q-B7-0BF5FA3E` | medium | stock-deep-dive | 建立七个闭环分析单元并通过 Analysis Pack v2 gate |
