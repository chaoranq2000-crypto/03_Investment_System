# Workflow State Schema

This is the only field-level reference for `workflow_state.yaml`,
`artifact_manifest.csv`, and `open_todos.csv` in
`research-orchestrator` workflow runs.

This schema consumes canonical workflow_type/stage_id/gate_id and
backflow_decision from:

```text
docs/workflows/RESEARCH_WORKFLOW.md
```

It must not introduce additional permanent workflow types.

## Validator-aligned enums

The current validator is:

```text
.agents/skills/research-orchestrator/scripts/validate_workflow_state.py
```

| enum | field | owner / current rule |
|---|---|---|
| canonical workflow type | `workflow_type` | Owned by `RESEARCH_WORKFLOW.md`; validator checks the same five values. |
| workflow_status | `status` | This schema and validator use the values listed below. |
| gate_status | `quality_gates[].status` | Listed below; validator currently checks only list type. |
| todo_severity | `open_todos[].severity` | Uses `high`, `medium`, `low`; open `high` TODOs block acceptance. |
| review_status | artifact-specific fields | Local scripts and manifests own artifact-specific values. |

`workflow_status` values:

| value | meaning |
|---|---|
| `planned` | 工作流已定义，尚未开始。 |
| `in_progress` | 正在执行某一步。 |
| `blocked` | 缺关键输入、证据、配置或路径，无法继续。 |
| `needs_fix` | 产物存在质量问题，需要回到具体 stage 修复。 |
| `ready_for_review` | 主要产物完成，等待质量审查或人工复核。 |
| `accepted` | 关键门禁通过，无 open high severity issue。 |
| `accepted_with_todos` | 无 open high severity issue，但保留 medium / low TODO。 |
| `archived` | 历史运行，保留但不作为当前状态。 |

`gate_status` values:

| value | meaning |
|---|---|
| `pass` | Gate dispatched and passed. |
| `fail` | Gate dispatched and failed. |
| `not_checked` | Gate has not been dispatched yet. |
| `not_applicable` | Gate does not apply to this run or artifact. |

## Validator-enforced required fields

These fields are required by the current validator:

```yaml
workflow_id: wf_YYYYMMDD_<workflow_type>_<slug>
workflow_type: <canonical value from RESEARCH_WORKFLOW.md>
status: planned
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
current_stage: <canonical stage or runtime label>
completed_stages: []
next_stage: <canonical stage or null>
active_skill: research-orchestrator
required_next_skill: null
evidence_snapshot: {}
claims_snapshot: {}
metrics_snapshot: {}
artifacts: []
open_todos: []
quality_gates: []
```

## Orchestration fields

These fields are part of the runtime contract even when older validators
do not enforce every one of them:

```yaml
run_mode: normal | diagnostic
owner: human | codex | mixed
active_segment_id: null
active_company_id: null
entry_criteria: []
exit_criteria: []
notes: null
```

`run_mode: diagnostic` is for read-only status / gap / next-step checks.
It is not a workflow type.

## Snapshot fields

```yaml
evidence_snapshot:
  manifest_path: data/manifests/evidence_manifest.csv
  evidence_count: null
  notes: null
claims_snapshot:
  draft_path: data/manifests/claims_draft.csv
  registry_path: data/manifests/claims_registry.csv
  claim_count: null
  notes: null
metrics_snapshot:
  draft_path: data/manifests/metrics_draft.csv
  registry_path: data/manifests/metrics_registry.csv
  metric_count: null
  notes: null
```

## State transition rules

- `accepted` requires no open high severity issue.
- `accepted_with_todos` allows medium / low TODOs only if explicitly listed.
- `blocked` requires `blocked_by` in `notes` or `open_todos`.
- `needs_fix` requires `required_next_skill` and target `next_stage`.

## Artifact item schema

Use this schema for `workflow_state.yaml` `artifacts[]` entries:

| field | required | allowed values / notes |
|---|---:|---|
| `artifact_type` | true | `workflow_state`, `report`, `manifest`, `handoff`, `readout`, or local type. |
| `path` | true | Repo-relative path. |
| `created_by_skill` | true | Skill id or `human`. |
| `stage` | true | Canonical stage or local stage label. |
| `status` | true | `missing`, `draft`, `current`, `stale`, `needs_fix`, `archived`. |
| `required` | true | Boolean. |
| `notes` | false | Missing data, TODO, or owner note. |

## Quality gate item schema

Use this schema for `workflow_state.yaml` `quality_gates[]` entries:

| field | required | allowed values / notes |
|---|---:|---|
| `gate_id` | true | Canonical gate id from `RESEARCH_WORKFLOW.md`. |
| `status` | true | `pass`, `fail`, `not_checked`, `not_applicable`. |
| `checked_by` | false | Usually `quality-review` or `research-orchestrator`. |
| `checked_at` | false | ISO date or datetime. |
| `notes` | false | Gate-specific notes or TODO pointer. |

## Artifact manifest CSV schema

Use this schema for:

```text
reports/workflow_runs/<workflow_id>/artifact_manifest.csv
```

| column | required | notes |
|---|---:|---|
| `artifact_id` | true | Stable id within the run. |
| `artifact_type` | true | Same type vocabulary as `artifacts[]` where possible. |
| `path` | true | Repo-relative path. |
| `created_by_skill` | true | Skill id or `human`. |
| `stage` | true | Canonical stage or local stage label. |
| `required` | true | `true` or `false`. |
| `exists` | true | `true` or `false` at readout time. |
| `status` | true | `missing`, `draft`, `current`, `stale`, `needs_fix`, `archived`. |
| `notes` | false | Missing data, TODO, or owner note. |

## Open TODO schema

Use this schema for `workflow_state.yaml` `open_todos[]` entries and:

```text
reports/workflow_runs/<workflow_id>/open_todos.csv
```

| field / column | required | notes |
|---|---:|---|
| `issue_id` | true | Stable id within the run. |
| `severity` | true | `high`, `medium`, or `low`. |
| `stage` | true | Canonical stage or local stage label. |
| `gate_id` | false | Canonical gate id if a gate produced the issue. |
| `target_artifact` | false | Repo-relative path. |
| `description` | true | What is missing, stale, contradicted, or blocked. |
| `fix_owner_skill` | true | Skill expected to fix or review. |
| `status` | true | `open`, `in_progress`, `blocked`, or `closed`. |
| `created_at` | false | ISO date or datetime. |
| `resolved_at` | false | ISO date or datetime. |
| `notes` | false | Next action, owner, or explicit TODO. |
