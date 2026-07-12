# Handoff: T5_analysis_pack_build -> segment-research

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| workflow_type | `stock_first_closed_loop` |
| run_mode | `normal` |
| current_stage | `T5_analysis_pack_build` |
| target_skill | `segment-research` |

## Objective

审查 Bundle 8 的独立行业需求、供给/竞争、技术路线和同业可比性输入，确保它们能作为 `competitive_position_matrix.yaml` 的证据底座，同时保留政策多路径、技术替代与口径不可比等反向证据。

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| user_request | 执行完补丁包中的计划 | true | Bundle 8 M3/M4 范围 |
| canonical_docs | `docs/workflows/RESEARCH_WORKFLOW.md` | true | 不进入 P2 |
| source_catalog | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle8_evidence_source_catalog.yaml` | true | reviewed source IDs |
| coverage_matrix | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/evidence_coverage_matrix.yaml` | true | 7/7 coverage 决策面 |
| peer_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/peer_operating_pack.yaml` | true | peer entity 与不可比性 |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|
| industry_evidence_pack | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/industry_evidence_pack.yaml` | true | source-only，不新增结论 |
| competitive_evidence_base | `reports/workflow_runs/wf_20260703_stock_first_002837_invic/peer_operating_pack.yaml` | true | 供 M4 构建器消费 |

## Guardrails

- 发行人年报不能满足独立行业来源门槛。
- 市场规模、渗透率、PUE、机柜功率密度必须保留日期、单位、定义和上下界。
- 政策同时推广液冷、蒸发冷却、热管和氟泵；不得写成液冷唯一技术路径。
- 同业仅按产品/经营证据比较；缺少液冷收入占比时保留不可比性。
- 不生成交易建议，不把评分或竞争判断写成买卖信号。

## Completion Criteria

- 行业需求有至少 2 个独立 `underlying_source_id`。
- 行业供给/竞争有至少 2 个独立 `underlying_source_id`。
- 至少 1 项反向证据进入下游风险/论点单元。
- 至少 3 家 peer entity 有 reviewed operating evidence。
- `.agents/skills/segment-research/scripts/validate_r5_industry_evidence_pack.py` 返回 0。

## Next Gate

| field | value |
|---|---|
| next_gate | `G4 Segment Report Gate` |
| gate_owner | `quality-review` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| `R5Q-B7-8E0E9760` | medium | segment-research | 以两份独立新来源补齐行业需求和供给/竞争输入 |
