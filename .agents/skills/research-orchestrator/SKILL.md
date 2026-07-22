---
name: research-orchestrator
description: >
  A股投研总工作流编排。当用户要求研究一个细分、深挖一个股票、刷新已有研究、
  检查是否能进入 P2、续跑/复盘一个 workflow，或询问下一步应调用哪个 skill 时使用。
  该 skill 负责按 docs/workflows/RESEARCH_WORKFLOW.md 的事实源路由下层 skills，
  不替代 evidence-ingest、segment-research、stock-deep-dive、quality-review 等具体研究技能。
---

# Research Orchestrator Skill

## Purpose

把用户请求转化为可审计的研究工作流运行：识别 canonical
`workflow_type`，创建或更新 workflow state，路由下层 skills，
生成 handoff，调度门禁，推动 fix loop，并输出 workflow readout。

本 skill 是执行入口，不是全局事实源。

## Canonical boundary

本 skill 不重新定义以下全局接口：

```text
workflow_type
global stage_id
global gate_id
backflow_decision
P2 readiness criteria
```

这些接口只以以下文件为准：

```text
docs/workflows/RESEARCH_WORKFLOW.md
```

运行时 handoff 和状态规则见：

```text
docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md
.agents/skills/research-orchestrator/references/workflow_state_schema.md
.agents/skills/research-orchestrator/references/skill_routing_matrix.md
.agents/skills/research-orchestrator/assets/handoff_template.md
```

## When to use

使用本 skill 当用户要求：

- 研究一个细分，并希望跑完整细分到个股闭环。
- 深挖一个股票，并希望独立个股研究后映射 / 回写细分。
- 刷新已有研究。
- 检查是否可以进入 P2。
- 判断当前下一步该做什么 / 应该调用哪个 skill。
- 续跑、复盘、诊断某个 workflow。
- 搭建或调试细分 / 个股研究总工作流。

## Do not use as main executor when

如果用户只要求完成单一具体动作，应直接路由到下层 skill：

| 用户只要求 | 主 skill |
|---|---|
| 导入一个公告、PDF、CSV、网页、数据源 | `evidence-ingest` |
| 写一个细分报告 | `segment-research` |
| 找某细分 A 股公司池 | `company-universe` |
| 维护 exposure 映射 | `segment-company-mapping` |
| 写一个个股深度 | `stock-deep-dive` |
| 检查报告证据、幻觉、反证、口径 | `quality-review` |
| 写 memo / watchlist note | `memo-writer` |

本 skill 可以先生成 handoff 或更新 workflow state，但不应替代下层 skill 的专业流程。

## Read discipline

Always read or inspect before creating / updating a workflow run:

1. `AGENTS.md`
2. `docs/workflows/RESEARCH_WORKFLOW.md`
3. Current `workflow_state.yaml` if resuming a run
4. The target lower-level skill's `SKILL.md`

Read when needed:

- `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` for handoff / state / close rules.
- `docs/policies/EVIDENCE_AND_CITATION_POLICY.md` for evidence / citation / source rank questions.
- `docs/policies/QUALITY_GUARDRAILS.md` for quality boundary questions.
- `docs/architecture/RESEARCH_OBJECT_MODEL.md` when changing object model or schema.
- Skill `references/` when entering that skill's specific execution contract.

Do not require normal execution to read `docs/plans/`, `docs/logs/`, or historical Codex tasks.

## Inputs

Possible input fields:

```yaml
workflow_type:
run_mode: normal | diagnostic
segment_name:
segment_id:
stock_code:
company_name:
company_id:
depth: quick | standard | deep
date_range:
target: build_workflow | run_workflow | resume | diagnose | readout | p2_readiness
workflow_id:
constraints:
out_of_scope:
```

If optional information is missing but the task can still progress, use
conservative assumptions and record them in `workflow_state.yaml` or the
response. Do not block on non-critical fields.

## Local procedure

### ORCH-1 Read canonical docs

Read `AGENTS.md`, `RESEARCH_WORKFLOW.md`, and when needed
`WORKFLOW_ORCHESTRATION_SPEC.md`. Use the spec for runtime rules.

### ORCH-2 Classify workflow_type

Classify against canonical workflow types in `RESEARCH_WORKFLOW.md`.
For status / gap / next-step checks, use `run_mode: diagnostic`.
See `WORKFLOW_ORCHESTRATION_SPEC.md`.

### ORCH-3 Create or update workflow_state

Create or update `reports/workflow_runs/<workflow_id>/workflow_state.yaml`
when the run requires persisted state. Use `workflow_state_schema.md`
and the runtime rules in `WORKFLOW_ORCHESTRATION_SPEC.md`.

New or updated active runs must set `state_schema_version: r5_v1`. The retained
`references/orchestration_contract.md` path is a compatibility pointer, not a second
runtime contract or a template for active state.

### ORCH-4 Select next stage and target skill

Use canonical stages from `RESEARCH_WORKFLOW.md`; use
`skill_routing_matrix.md` only as a quick reference. Runtime dispatch follows
`WORKFLOW_ORCHESTRATION_SPEC.md`.

### ORCH-5 Emit handoff packet

Write handoff packets from `assets/handoff_template.md` under
`reports/workflow_runs/<workflow_id>/handoffs/`. Required fields are governed
by `WORKFLOW_ORCHESTRATION_SPEC.md`.

### ORCH-6 Dispatch quality gate

Dispatch the next canonical gate from `RESEARCH_WORKFLOW.md`.
`quality-review` owns issue finding and severity; dispatch rules live in
`WORKFLOW_ORCHESTRATION_SPEC.md`.

### ORCH-7 Route fix loop if needed

If review finds blocking issues, update state to `needs_fix` or `blocked`
and route to the owner skill. Fix loop rules live in
`WORKFLOW_ORCHESTRATION_SPEC.md`.

### ORCH-8 Close with workflow_readout

For complete runs, write `workflow_readout.md` with final status, artifacts,
quality results, backflow decision, TODOs, and P2 readiness only if relevant.
Close rules live in `WORKFLOW_ORCHESTRATION_SPEC.md`.

## Output style

When answering the user, stay operational:

```text
current workflow_type
current stage
next skill
files to read
files to write
quality gates
blocking items / TODOs
```

Do not write long investment opinions from this skill.

## Guardrails

- Do not define new canonical workflow types, global stage IDs or global gate IDs.
- Do not invent evidence_id、claim_id、metric_id、stock data、收入占比、订单、客户、估值数字。
- Do not bypass `quality-review` to mark workflow accepted.
- Do not enter formal P2 comparison before `comparison_readiness_gate`.
- Do not treat `memo-writer` or scorecard as a new conclusion source.
- Do not silently overwrite raw evidence or old reports.
- Separate fact、estimate、inference、management_comment、analyst_view、opinion。
- Record uncertainty、missing data and TODO。
- Do not output buy/sell/hold advice.

## Minimal close checklist

This checklist is an operational close check, not a second global gate table.

```text
[ ] workflow_state.yaml exists and is current
[ ] run_log.md records major steps or skipped-run reason is explicit
[ ] artifact_manifest.csv lists required artifacts
[ ] open_todos.csv lists unresolved gaps
[ ] quality_gate_report.md exists for complete runs
[ ] lower-level skill handoffs are recorded or explicitly skipped
[ ] segment-company exposure is updated or no-update reason is recorded
[ ] no high-severity quality issues remain
[ ] workflow_readout.md states accepted / accepted_with_todos / needs_fix / blocked
```

<!-- BEGIN R5_BUNDLE11R_RUNTIME_INTEGRATION -->
## Bundle 11R runtime routing

For a stock research workflow that has reached the post-10R research-depth stage, invoke `scripts/run_r5_bundle11r_runtime.py` with the business-line driver plan, evidence status, peer pack, and semantic payload. Persist its question matrix, driver pack, peer eligibility, semantic scorecard, and backflow plan under the workflow-run directory. Route the next action from `backflow_plan.tasks`; do not replace a failed operating-research gate by asking the Writer to add prose.
<!-- END R5_BUNDLE11R_RUNTIME_INTEGRATION -->

<!-- BEGIN R5_BUNDLE12R_OPERATING_EVIDENCE_PROFILE -->
## Bundle 12R operating-evidence orchestration

When operating evidence, overlap reconciliation or valuation-method eligibility
is in scope, read `references/bundle12r_backflow_profile.md` and
`docs/workflows/R5_BUNDLE12R_OPERATING_EVIDENCE_PROFILE.md`. Run the local gate,
consume its backflow plan, and do not transfer Bundle 11R human review to a new
Bundle 12R generation.
<!-- END R5_BUNDLE12R_OPERATING_EVIDENCE_PROFILE -->
