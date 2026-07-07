# Workflow Doc Responsibility Cleanup Readout

Date: 2026-07-07

## 1. 修改文件

| file | change |
|---|---|
| `docs/workflows/RESEARCH_WORKFLOW.md` | 保留唯一 global workflow kernel；移出 workflow_state 字段级 schema 和 P2 前建设顺序。 |
| `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | 保留 runtime orchestration spec；删除内嵌 routing matrix、handoff 模板和 CSV 字段级 schema。 |
| `.agents/skills/research-orchestrator/SKILL.md` | 保留执行入口定位；将 ORCH-1 到 ORCH-8 瘦身为短流程并链接 runtime spec。 |
| `.agents/skills/research-orchestrator/references/skill_routing_matrix.md` | 改为唯一 quick routing matrix；删除 P1.6 建设计划式矩阵。 |
| `.agents/skills/research-orchestrator/assets/handoff_template.md` | 改为唯一 handoff packet 模板，补齐必填字段。 |
| `.agents/skills/research-orchestrator/references/workflow_state_schema.md` | 改为 workflow_state、artifact_manifest、open_todos 的字段级 schema owner。 |
| `docs/plans/P1_6_WORKFLOW_BUILDOUT_PLAN.md` | 接收从 workflow kernel 迁出的 P2 前建设顺序。 |
| `reports/p1_6/WORKFLOW_DOC_DEDUP_READOUT.md` | 新增本 readout。 |

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

| fact type | unique owner |
|---|---|
| canonical `workflow_type` | `docs/workflows/RESEARCH_WORKFLOW.md` |
| canonical `stage_id` | `docs/workflows/RESEARCH_WORKFLOW.md` |
| canonical `gate_id` / G0-G10 gate definition | `docs/workflows/RESEARCH_WORKFLOW.md` |
| canonical `backflow_decision` | `docs/workflows/RESEARCH_WORKFLOW.md` |
| P2 readiness 条件 | `docs/workflows/RESEARCH_WORKFLOW.md` |
| runtime gate dispatch / fix loop / close readout rules | `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` |
| workflow_state / artifact_manifest / open_todos field schema | `.agents/skills/research-orchestrator/references/workflow_state_schema.md` |
| quick routing matrix | `.agents/skills/research-orchestrator/references/skill_routing_matrix.md` |
| handoff packet template | `.agents/skills/research-orchestrator/assets/handoff_template.md` |
| orchestrator execution entry and read discipline | `.agents/skills/research-orchestrator/SKILL.md` |
| P1.6 build sequence | `docs/plans/P1_6_WORKFLOW_BUILDOUT_PLAN.md` |

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

| issue_id | severity | owner | next_action |
|---|---|---|---|
| workflow_state_validator_alignment | low | research-orchestrator | 可选：后续扩展 validator，使其也校验 `run_mode` 和 `quality_gates[].status`。 |
| workflow_state_template_alignment | low | research-orchestrator | 可选：后续将 `run_mode` 加入 `workflow_state_template.yaml`，与 orchestration runtime 字段保持更强一致。 |
