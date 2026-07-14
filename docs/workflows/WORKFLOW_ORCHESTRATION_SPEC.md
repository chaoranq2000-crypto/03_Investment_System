# Workflow Orchestration Spec — research-orchestrator 运行时规范

> 本文件定义 `research-orchestrator` 如何消费全局 workflow kernel，
> 并创建可审计 workflow run。

This spec consumes canonical workflow_type/stage_id/gate_id/backflow_decision
from RESEARCH_WORKFLOW.md and MUST NOT redefine or extend them.

全局接口唯一事实源：

```text
docs/workflows/RESEARCH_WORKFLOW.md
```

字段级 schema 和唯一模板：

```text
.agents/skills/research-orchestrator/references/workflow_state_schema.md
.agents/skills/research-orchestrator/references/skill_routing_matrix.md
.agents/skills/research-orchestrator/assets/handoff_template.md
```

## 1. 编排目标

`research-orchestrator` 把用户请求转化为可审计的 workflow run：

```text
识别 workflow_type
→ 创建或更新 workflow_state
→ 判断 current_stage / next_stage
→ 选择 target_skill
→ 生成 handoff packet
→ 调度质量门禁
→ 必要时进入 fix loop
→ 输出 workflow_readout
```

它不直接承担行业研究、个股研究、证据抽取或质量审查的全部内容。

## 2. 用户意图分类

收到用户请求后，先分类为 canonical workflow type 或 diagnostic run mode。
`workflow_type` 的可选值来自 `RESEARCH_WORKFLOW.md`。

| 用户意图 | classification output | run_mode | 说明 |
|---|---|---|---|
| 输入一个细分，希望找公司池和样本个股 | canonical segment-led workflow | `normal` | 从细分启动闭环。 |
| 输入一个股票，希望做个股深度并映射细分 | canonical stock-led workflow | `normal` | 从股票或公司启动闭环。 |
| 处理细分和个股之间的回写、冲突或 exposure 变更 | canonical interlock workflow | `normal` | 维护连接层。 |
| 更新已有报告、watchlist 或旧结论 | canonical refresh workflow | `normal` | 新证据驱动刷新。 |
| 判断多个细分或个股是否可比较 | canonical readiness workflow | `normal` | 只做 P2 readiness 判断。 |
| 只问当前状态、缺口或下一步 | related workflow or blank | `diagnostic` | 可不创建 run。 |

分类记录至少说明：

| field | runtime requirement |
|---|---|
| `workflow_type` | 使用 `RESEARCH_WORKFLOW.md` 的 canonical 值，或在只读诊断中留空。 |
| `run_mode` | `normal` 或 `diagnostic`。 |
| `reason` | 说明为何选择该 workflow。 |
| `object_type` | `segment`、`company`、`mixed` 或 `system`。 |
| `object_id` | 可定位对象；缺失时写 `TODO` 或 `MISSING`。 |
| `recommended_start_stage` | 使用 canonical stage，不能新增全局 stage。 |
| `blocked_by` | 无法启动时列明缺口。 |

## 3. Workflow run 创建规则

当用户要求启动、续跑、调试或完整检查闭环时，创建或更新：

```text
reports/workflow_runs/<workflow_id>/
```

运行目录至少维护以下资产：

| asset | purpose |
|---|---|
| `workflow_state.yaml` | 记录当前状态，schema 见 `workflow_state_schema.md`。 |
| `run_log.md` | 记录关键执行步骤、跳过原因和人工决策。 |
| `artifact_manifest.csv` | 登记 run 相关产物，字段见 `workflow_state_schema.md`。 |
| `open_todos.csv` | 登记未解决问题，字段见 `workflow_state_schema.md`。 |
| `quality_gate_report.md` | 记录质量审查结果或未执行原因。 |
| `workflow_readout.md` | 收尾阶段生成最终 readout。 |
| `handoffs/` | 保存下层 skill 交接包。 |

如果只是一次简短诊断，可以不创建 workflow run，但最终回答必须说明：

```text
未创建运行目录
```

## 4. Handoff packet 规则

每次将任务交给下层 skill 前，必须准备 handoff packet：

```text
reports/workflow_runs/<workflow_id>/handoffs/<nn>_to_<skill>.md
```

唯一模板位于：

```text
.agents/skills/research-orchestrator/assets/handoff_template.md
```

本规范只保留必填字段清单，不内嵌完整模板。

| required field | requirement |
|---|---|
| `workflow_id` | 当前 run id。 |
| `workflow_type` | 来自 `RESEARCH_WORKFLOW.md`。 |
| `current_stage` | 来自 canonical stage。 |
| `target_skill` | 本次接收 handoff 的 skill。 |
| `objective` | 本次要完成的动作。 |
| `inputs` | 用户输入、必读文档、必读数据或报告。 |
| `expected_outputs` | 预期产物、路径和格式。 |
| `guardrails` | 本次禁止事项和缺证据处理规则。 |
| `completion_criteria` | 完成标准。 |
| `next_gate` | 下一步调度的 canonical gate。 |

## 5. 路由原则

具体全局阶段见 `RESEARCH_WORKFLOW.md`。

运行时只做三件事：

1. 根据 `current_stage` 和用户目标选择 `target_skill`。
2. 用 handoff packet 说明输入、输出、边界和完成标准。
3. 当 quick reference 与 kernel 冲突时，以 kernel 为准并记录 TODO。

快速路由矩阵唯一 reference：

```text
.agents/skills/research-orchestrator/references/skill_routing_matrix.md
```

## 6. Gate dispatch 规则

全局 gate id 和通过条件只在 `RESEARCH_WORKFLOW.md` 定义。

编排器只负责 gate dispatch：

| action | owner |
|---|---|
| 判断当前产物需要哪个 gate | `research-orchestrator` |
| 生成质量审查 handoff | `research-orchestrator` |
| 执行证据、claim、metric、报告、回写等质量检查 | `quality-review` |
| 记录 gate status 和 open TODO | `research-orchestrator` 或 `quality-review` |

只要存在 open high severity issue，workflow 不得标记为 `accepted`
或 `accepted_with_todos`。

## 7. Fix loop 规则

门禁失败时，`workflow_state.yaml` 必须进入 fix loop：

| field | expected update |
|---|---|
| `status` | `needs_fix` 或 `blocked`。 |
| `current_stage` | 当前质量门或发现问题的 stage。 |
| `next_stage` | 需要返回修复的 canonical stage。 |
| `required_next_skill` | 修复 owner skill。 |
| `open_todos` | 记录 issue、severity、target artifact 和 next action。 |

fix loop 不新增 `workflow_type`、global `stage_id` 或 global `gate_id`。

## 8. Close readout 规则

完整 workflow 的 `workflow_readout.md` 应说明：

| topic | requirement |
|---|---|
| final state | `workflow_id`、`workflow_type`、`run_mode`、`final_status`。 |
| scope | 本轮对象、范围、out_of_scope。 |
| skills used | 实际调用或明确跳过的 skills。 |
| artifacts | 产物路径和状态，细节来自 `artifact_manifest.csv`。 |
| quality | gates dispatched、open issues、blocked items。 |
| backflow | 使用 `RESEARCH_WORKFLOW.md` 的 canonical decision。 |
| unresolved TODOs | owner、severity、next action。 |
| P2 readiness | 仅在 readiness 任务中判断，不直接进入 P2。 |

## 9. 禁止事项

`research-orchestrator` 不得：

1. 新增 canonical workflow type。
2. 新增 global stage id 或 global gate id。
3. 把 diagnostic 当成永久 workflow_type。
4. 直接写长篇研究结论替代下层 skill。
5. 跳过 `quality-review` 直接 accepted。
6. 将 scorecard / watchlist / memo 写成交易建议。

<!-- BEGIN R5_BUNDLE11R_RUNTIME_INTEGRATION -->
## R5 Bundle 11R issue backflow contract

The orchestrator consumes `r5_bundle11r_backflow_plan` and must set `next_stage` and `required_next_skill` from the highest-severity blocking task. Typical routes are:

- missing operating drivers or excessive proxy share → `RP2_operating_evidence` / `evidence-ingest`;
- broken operating equation or missing model link → `RP4_operating_model` / `stock-deep-dive`;
- ineligible peer set → `RP5_peer_valuation` / `compare-stocks`;
- generic analysis or non-falsifiable watchpoints → `RP6_analysis_synthesis` / `stock-deep-dive`;
- duplicated narrative or flat emphasis → `RP7_report_planning` / `memo-writer`;
- direct trading language → `RP8_quality_review` / `quality-review`;
- generation mismatch → `T0_orchestration` / `research-orchestrator`.

A passing structure score cannot offset a high/critical research blocker.
<!-- END R5_BUNDLE11R_RUNTIME_INTEGRATION -->

<!-- BEGIN R5_BUNDLE12R_OPERATING_EVIDENCE_PROFILE -->
### Bundle 12R issue routing

`RP-12R-OE` routes source/metric gaps to `T1/evidence-ingest`, business-boundary,
overlap and independent-exposure gaps to `T2/stock-deep-dive`, and peer/DCF/SOTP
eligibility gaps to `RP6/company-valuation`. The local gate may not set
`sample_quality_allowed` or `p2_allowed` to true.
<!-- END R5_BUNDLE12R_OPERATING_EVIDENCE_PROFILE -->
