# Workflow Doc Responsibility Cleanup Readout

Date: 2026-07-07

## 1. 修改文件

| id | file |
|---|---|
| F1 | `docs/workflows/RESEARCH_WORKFLOW.md` |
| F2 | `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` |
| F3 | `.agents/skills/research-orchestrator/SKILL.md` |
| F4 | `.agents/skills/research-orchestrator/references/skill_routing_matrix.md` |
| F5 | `.agents/skills/research-orchestrator/assets/handoff_template.md` |
| F6 | `.agents/skills/research-orchestrator/references/workflow_state_schema.md` |
| F7 | `docs/plans/P1_6_WORKFLOW_BUILDOUT_PLAN.md` |
| F8 | `reports/p1_6/WORKFLOW_DOC_DEDUP_READOUT.md` |

| id | change |
|---|---|
| F1 | 保留唯一 global workflow kernel；移出 workflow_state 字段级 schema 和 P2 前建设顺序。 |
| F2 | 保留 runtime orchestration spec；删除内嵌 routing matrix、handoff 模板和 CSV 字段级 schema。 |
| F3 | 保留执行入口定位；将 ORCH-1 到 ORCH-8 瘦身为短流程并链接 runtime spec。 |
| F4 | 改为唯一 quick routing matrix；删除 P1.6 建设计划式矩阵。 |
| F5 | 改为唯一 handoff packet 模板，补齐必填字段。 |
| F6 | 改为 workflow_state、artifact_manifest、open_todos 的字段级 schema owner。 |
| F7 | 接收从 workflow kernel 迁出的 P2 前建设顺序。 |
| F8 | 新增本 readout。 |

## 2. 迁移内容

| moved content | from | to |
|---|---|---|
| P2 前建设顺序 | `RESEARCH_WORKFLOW.md` section 14 | `P1_6_WORKFLOW_BUILDOUT_PLAN.md` section 0 |
| workflow_state 字段级 schema 和 status 含义 | `RESEARCH_WORKFLOW.md` | `workflow_state_schema.md` |
| 完整 handoff packet 模板 | `WORKFLOW_ORCHESTRATION_SPEC.md` | `handoff_template.md` |
| 完整 routing matrix | `WORKFLOW_ORCHESTRATION_SPEC.md` | `skill_routing_matrix.md` |
| artifact manifest / open TODO 字段级 schema | `WORKFLOW_ORCHESTRATION_SPEC.md` | `workflow_state_schema.md` |
| backflow enum 正文复制 | `research-orchestrator/SKILL.md` | 引用 `RESEARCH_WORKFLOW.md` canonical owner |

## 3. 当前事实 owner

| owner_id | fact type |
|---|---|
| O1 | canonical `workflow_type` |
| O1 | canonical `stage_id` |
| O1 | canonical `gate_id` / G0-G10 gate definition |
| O1 | canonical `backflow_decision` |
| O1 | P2 readiness 条件 |
| O2 | runtime gate dispatch / fix loop / close readout rules |
| O3 | workflow_state / artifact_manifest / open_todos field schema |
| O4 | quick routing matrix |
| O5 | handoff packet template |
| O6 | orchestrator execution entry and read discipline |
| O7 | P1.6 build sequence |

| owner_id | unique owner |
|---|---|
| O1 | `docs/workflows/RESEARCH_WORKFLOW.md` |
| O2 | `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` |
| O3 | `.agents/skills/research-orchestrator/references/workflow_state_schema.md` |
| O4 | `.agents/skills/research-orchestrator/references/skill_routing_matrix.md` |
| O5 | `.agents/skills/research-orchestrator/assets/handoff_template.md` |
| O6 | `.agents/skills/research-orchestrator/SKILL.md` |
| O7 | `docs/plans/P1_6_WORKFLOW_BUILDOUT_PLAN.md` |

## 4. 语义不变确认

- 未修改五个永久 `workflow_type` 名称。
- 未修改 S/T 阶段 ID。
- 未修改 G0-G10 gate ID 或 gate 定义。
- 未修改 `backflow_decision` 枚举。
- 未进入 P2；`comparison_readiness_gate` 仍只作为 readiness gate。
- 未新增投资研究结论、个股报告、细分报告或交易建议。

## 5. 验证

```text
git diff --check -- <changed workflow docs>
=> no whitespace errors; Git only reported LF/CRLF conversion warnings

conda run -p .\.conda\investment-system python \
  .agents/skills/research-orchestrator/scripts/validate_workflow_state.py \
  .agents/skills/research-orchestrator/assets/workflow_state_template.yaml
=> OK: .agents\skills\research-orchestrator\assets\workflow_state_template.yaml

conda run -p .\.conda\investment-system python scripts/check_doc_drift.py
=> Doc drift check passed.
```

## 6. 剩余 TODO

| issue_id | severity | owner |
|---|---|---|
| workflow_state_validator_alignment | low | research-orchestrator |
| workflow_state_template_alignment | low | research-orchestrator |

| issue_id | next_action_ref |
|---|---|
| workflow_state_validator_alignment | A1 |
| workflow_state_template_alignment | A2 |

- A1: 可选：后续扩展 validator，使其也校验 `run_mode`
  和 `quality_gates[].status`。
- A2: 可选：后续将 `run_mode` 加入 `workflow_state_template.yaml`，
  与 orchestration runtime 字段保持更强一致。

## 7. Markdown formatting cleanup

Date: 2026-07-07

| cleanup area | files |
|---|---|
| wide Markdown tables | `RESEARCH_WORKFLOW.md`、`skill_routing_matrix.md` |
| wide Markdown tables | `WORKFLOW_DOC_DEDUP_READOUT.md` |
| long table notes | `workflow_state_schema.md` |
| long paragraphs / list items | `RESEARCH_WORKFLOW.md`、`SKILL.md` |
| checked, no edit needed | `WORKFLOW_ORCHESTRATION_SPEC.md`、`handoff_template.md` |

| semantic guardrail | result |
|---|---|
| workflow_type / stage_id / gate_id / backflow_decision | unchanged |
| P2 readiness semantics | unchanged |
| investment conclusions | none added |
| P2 execution | not entered |

| validation | result |
|---|---|
| `git diff --check` | pass; Git reported LF/CRLF conversion warnings only |
| `scripts/check_doc_drift.py` | pass |
| `validate_workflow_state.py` | pass |
