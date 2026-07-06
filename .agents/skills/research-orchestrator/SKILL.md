---
name: research-orchestrator
description: A股投研总工作流编排入口。当用户要求启动、续跑、诊断、关闭、复盘一个 workflow，或询问下一步应调用哪个 skill 时使用。该 skill 只负责编排、状态、handoff、路由和 readout；不替代 evidence-ingest、segment-research、stock-deep-dive、quality-review 等下层技能。
---

# Research Orchestrator Skill

## Purpose

`research-orchestrator` turns a user request into an auditable workflow run.

It is an execution entry point, not a workflow fact source.

This skill must not redefine global `workflow_type`, global `stage_id`, global `gate_id`, run status enums, or project-level ownership.

## Canonical sources

### Always read

Before creating, resuming, closing, or diagnosing a workflow run, read:

```text
AGENTS.md
docs/workflows/RESEARCH_WORKFLOW.md
```

If the run already exists, also read:

```text
reports/workflow_runs/<workflow_id>/workflow_state.yaml
reports/workflow_runs/<workflow_id>/open_todos.csv
reports/workflow_runs/<workflow_id>/artifact_manifest.csv
```

Before routing to a lower skill, read that lower skill's `SKILL.md`.

### Read when needed

Read these only when the task requires them:

```text
.agents/skills/research-orchestrator/references/orchestration_contract.md
.agents/skills/research-orchestrator/references/workflow_state_schema.md
.agents/skills/research-orchestrator/references/skill_routing_matrix.md
docs/policies/EVIDENCE_AND_CITATION_POLICY.md
docs/policies/QUALITY_GUARDRAILS.md
docs/architecture/RESEARCH_OBJECT_MODEL.md
docs/reporting/
```

If a referenced file is missing, record `blocked_by` or an explicit TODO. Do not pretend it was read.

## When to use

Use this skill when the user asks to:

- start a segment-led research workflow;
- start a stock-led research workflow;
- handle segment-stock interlock or backflow;
- refresh existing research;
- check P2 readiness;
- resume, diagnose, close, or review a workflow run;
- decide which lower skill should run next.

## Do not use as the main executor when

If the user asks for one concrete research action, route to the lower skill after creating a handoff if needed.

| User need | Main skill |
|---|---|
| acquire, parse, register, or deduplicate evidence | `evidence-ingest` |
| define or research one segment | `segment-research` |
| build an A-share company universe | `company-universe` |
| maintain segment-company exposure | `segment-company-mapping` |
| write or update one stock deep dive | `stock-deep-dive` |
| review evidence, claims, metrics, exposure, or no-advice boundary | `quality-review` |
| write a memo or watchlist note from accepted research | `memo-writer` |
| refresh existing research with new evidence | `refresh-research` |

## Inputs

Expected input may include:

```yaml
workflow_type:
segment_name:
segment_id:
stock_code:
company_name:
company_id:
depth: quick | standard | deep
target: build_workflow | run_workflow | resume | diagnose | readout | p2_readiness
workflow_id:
constraints:
out_of_scope:
```

If optional details are missing but the workflow can proceed safely, continue with conservative assumptions and record them in `workflow_state.yaml` or the user-facing readout.

Do not block only because a non-critical field is missing.

## Local procedure

### 1. Classify request

Classify the request using the canonical workflow types and rules in `docs/workflows/RESEARCH_WORKFLOW.md`.

If the user only wants a status check or routing advice, use non-run diagnostic mode and explain that no workflow run was created.

### 2. Create or locate workflow run

For a full run, resume, debug, or closeout, create or update:

```text
reports/workflow_runs/<workflow_id>/
```

Use the workflow run structure defined by the canonical workflow docs and orchestrator references.

### 3. Update workflow state

Update `workflow_state.yaml` rather than relying on chat memory.

At minimum, record:

```text
workflow_id
workflow_type
status
current_stage
next_stage
active_skill
required_next_skill
artifacts
open_todos
quality_gates
notes
```

Schema details live in `references/workflow_state_schema.md`.

### 4. Prepare handoff

Before routing to a lower skill, write a handoff packet under:

```text
reports/workflow_runs/<workflow_id>/handoffs/
```

The packet should state:

```text
workflow_id
current_stage
requested_skill
objective
inputs
expected_outputs
guardrails
completion_criteria
next_gate_or_review
```

Handoff format details live in `references/orchestration_contract.md`.

### 5. Route to lower skill

Choose the lower skill according to:

```text
docs/workflows/RESEARCH_WORKFLOW.md
.agents/skills/research-orchestrator/references/skill_routing_matrix.md
```

The orchestrator may summarize what the lower skill must do, but must not perform the lower skill's full research work.

### 6. Enforce backflow and quality review

A full segment-led or stock-led workflow cannot close unless segment-stock backflow has either been executed or explicitly marked `no_backflow_needed` / `blocked` with a reason.

Do not mark a workflow `accepted` while any high severity issue remains open.

### 7. Produce close readout

At closeout, write or update:

```text
reports/workflow_runs/<workflow_id>/workflow_readout.md
```

The readout must include:

```text
status
scope
skills used
artifacts produced
quality gates
backflow decisions
remaining TODOs
P2 readiness, if relevant
```

## Outputs

This skill may create or update:

```text
reports/workflow_runs/<workflow_id>/workflow_state.yaml
reports/workflow_runs/<workflow_id>/run_log.md
reports/workflow_runs/<workflow_id>/artifact_manifest.csv
reports/workflow_runs/<workflow_id>/open_todos.csv
reports/workflow_runs/<workflow_id>/quality_gate_report.md
reports/workflow_runs/<workflow_id>/workflow_readout.md
reports/workflow_runs/<workflow_id>/handoffs/*.md
```

It should not directly create final research claims, stock conclusions, or segment conclusions without the relevant lower skill.

## Guardrails

- Do not invent `evidence_id`, `claim_id`, `metric_id`, stock data, financial figures, customer names, orders, revenue shares, or valuation numbers.
- Do not bypass `quality-review` to mark a run accepted.
- Do not run formal P2 comparison before the comparison readiness gate.
- Do not use `memo-writer`, scorecards, or watchlists as sources of new research conclusions.
- Do not silently overwrite raw evidence or old reports.
- Preserve missing data and uncertainty through TODO / MISSING / LOW_CONFIDENCE / UNVERIFIED labels.
- Keep fact, estimate, inference, management comment, analyst view, and opinion separated.
- Do not output direct buy/sell/hold instructions, position sizing, or guaranteed-return language.

## Minimal close checklist

Before closing a full workflow run, confirm:

```text
[ ] workflow_state.yaml exists and is current
[ ] run_log.md records major steps or skipped steps
[ ] artifact_manifest.csv lists required artifacts
[ ] open_todos.csv lists unresolved gaps
[ ] quality_gate_report.md exists or blocked reason is explicit
[ ] required lower-skill handoffs are recorded or explicitly skipped
[ ] segment-company exposure is updated or no-update reason is recorded
[ ] no high severity quality issue remains open
[ ] workflow_readout.md states accepted / accepted_with_todos / needs_fix / blocked
```
