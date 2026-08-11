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
| gate_status | `quality_gates[].status` | Active V1 states accept only the four values below. |
| todo_severity | `open_todos[].severity` | Uses `high`, `medium`, `low`; severity describes risk but does not by itself decide the workflow outcome. |
| review_status | artifact-specific fields | Local scripts and manifests own artifact-specific values. |

`workflow_status` values:

| value | meaning |
|---|---|
| `planned` | 工作流已定义，尚未开始。 |
| `in_progress` | 正在执行某一步。 |
| `blocked` | 身份、路径、解析、证据源或必要方法输入损坏，使任何诚实目标产物都无法生成。 |
| `needs_fix` | 当前产物实际使用了无证据结论、错误计算、真实重复计数、断裂引用、隐藏缺口，或违反 no-advice，需要回到具体 stage 修复。 |
| `ready_for_review` | 主要产物完成，等待机器质量审查或自动 gate；最终报告审核 `pending` 只写入 `final_report_review_status`，不得改变 canonical `status`。 |
| `accepted` | 自动质量通过且没有活动限制或 TODO。 |
| `accepted_with_todos` | 自动质量通过；未使用的 unknown、不可用方法或可见限制保留为 TODO，不论其描述性 severity。 |
| `archived` | 历史运行，保留但不作为当前状态。 |

`gate_status` values:

| value | meaning |
|---|---|
| `pass` | Gate dispatched and passed. |
| `fail` | Gate dispatched and failed. |
| `not_checked` | Gate has not been dispatched yet. |
| `not_applicable` | Gate does not apply to this run or artifact. |

## Validator-enforced required fields

Every new or updated active V1 run must set:

```yaml
state_schema_version: r5_v1
decision_semantics_version: current_goal_v1
final_report_review_semantics_version: final_report_review_v1
run_mode: normal
```

`state_schema_version` activates canonical G0–G10 control-plane validation.
`decision_semantics_version` activates the current-goal truth table below. A protected
historical state without `decision_semantics_version` is accepted only through an explicit
read-only compatibility result; it is not a template for new execution and must not be
rewritten merely to satisfy the new schema. Any unknown version fails validation.
`final_report_review_semantics_version` activates the sole active human-review boundary.
It is bidirectionally required with `decision_semantics_version: current_goal_v1`;
removing the final-review marker is a schema downgrade and fails. P1-era content remains
recoverable from Git history, but it is not accepted as a current state or copied as a new
active template.

These fields are required by the validator:

```yaml
workflow_id: wf_YYYYMMDD_<workflow_type>_<slug>
workflow_type: <canonical value from RESEARCH_WORKFLOW.md>
run_mode: normal
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

## Final report review and sample-quality fields

The only active human-review status is:

```yaml
final_report_review_status: not_requested # not_requested | pending | approved | changes_requested
```

Marked active states also require:

```yaml
final_report_review_semantics_version: final_report_review_v1
sample_quality_ready: false
final_report_review:
  report_path: null
  report_sha256: null
  reviewer: null
  reviewed_at: null
  notes: null
  change_scope: null
```

Ordinary runs do not write `automated_report_quality_passed`,
`system_v1_complete`, `p2_ready`, or `release_ready`. Automated report quality is
derived from canonical `status` plus the complete G0-G10 gate set. Project
completion and release readiness belong to their project-level evidence owners.
`p2_ready` is written only by a `comparison_readiness_gate` run. Older states may
retain these boolean fields as read-only compatibility data.

The structural schema is `schemas/r5_final_report_review.schema.json`. Runtime validation
adds repository and byte-integrity checks:

- New review records omit the redundant `final_report_review.decision`. If an older
  record retains it, it must equal `final_report_review_status`.
- `not_requested` keeps the report binding, reviewer, time, notes and `change_scope`
  null.
- `pending` binds one existing final-report path under the canonical
  `reports/stocks/<id>/` or `reports/segments/<id>/` root and its
  machine-computed lowercase SHA-256. The same path must appear exactly once in
  `artifacts[]` as a required, current `artifact_type: final_report`. It has no reviewer,
  reviewed time or notes yet.
- `approved` binds the same current report bytes and also requires a non-machine
  reviewer identity, timezone-qualified ISO datetime and non-empty notes.
- `changes_requested` has the same human and byte binding, plus
  `change_scope: automated_quality_defect | report_revision`.
- A report-byte change makes the stored hash stale and validation fails; only the final
  report hash binds human review. Evidence, claim, metric, candidate and generation-lock
  hashes remain machine-integrity controls.
- If a committed `approved|changes_requested` record changes its report path, hash,
  top-level status, reviewer, notes or `change_scope`, the replacement must be a new
  human review event with a strictly later `reviewed_at`. Updating only the stored hash cannot migrate
  the old decision to new bytes. Resetting to `not_requested|pending` explicitly
  invalidates the prior human decision; any later return to a human decision must also be
  later than the most recent committed human-review event.
- Automated report quality is true exactly when all canonical G0-G10 entries are
  present and each is `pass` or `not_applicable`, and canonical `status` is
  `accepted` or `accepted_with_todos`. If an older state retains
  `automated_report_quality_passed`, its value must equal that derivation.
- `sample_quality_ready: true` is allowed only when derived automated report quality
  passed and the current-byte final report is `approved`. Approval does not force sample
  quality to true because other sample-level conditions may remain.
- `p2_ready: true`, when present, requires
  `workflow_type: comparison_readiness_gate`. A legacy false value remains compatible
  in other workflow types.
- `not_requested` and `pending` do not change `status`. They keep
  `sample_quality_ready: false`.
- `changes_requested` with `automated_quality_defect` requires canonical
  `status: needs_fix` and the normal scoped issue/fix-loop evidence.
  `change_scope: report_revision` does not itself change the machine-derived workflow
  outcome.

Marked states reject parallel or intermediate human-approval fields, including
`human_review*`, reviewer-authority, independent-receipt and candidate-decision fields.
Unmarked historical states remain read-only compatibility inputs and must not be rewritten
or treated as active templates. A validator can reject obvious machine/placeholder
reviewer identities, but a real reviewer identity and decision remain external human truth
and must never be synthesized.

## Orchestration fields

These fields are part of the runtime contract even when older validators
do not enforce every one of them:

```yaml
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

- `severity` is descriptive. It never decides status without the current-goal fields.
- `accepted` requires no active current-goal limitation or defect.
- `accepted_with_todos` requires every active issue to derive
  `blocks_current_goal: false`; high-severity visible unused unknowns are allowed.
- `needs_fix` requires at least one active row that derives `needs_fix`, plus
  `required_next_skill` and target `next_stage`.
- `blocked` requires at least one active row whose workflow identity/path/parse/source
  integrity failure or required unavailable method makes any honest target output
  impossible.
- A canonical gate or local Bundle/R5 check cannot bypass this issue-level derivation.

## Current-goal issue semantics

Every `open_todos[]` row in a new or updated active state separates:

```yaml
impact_scope: workflow | report | section | claim | method | none
active_disposition: active_defect | unknown | method_unavailable | report_limitation | historical_backlog | policy_retired | not_required_for_active_v1
affected_capabilities: []
blocks_current_goal: false
```

`affected_capabilities` is a unique YAML list of explicit capability IDs. It is empty
only when `impact_scope: none`. For all other scopes it names the unavailable or affected
claim, section, method, report, or workflow capability.

The validator applies this table row by row:

| active_disposition | scope / dependency | blocks_current_goal | row outcome |
|---|---|---:|---|
| `active_defect` | workflow identity/path/parse/source failure prevents any honest target output | `true` | `blocked` |
| `active_defect` | current report/section/claim/method has unsupported use, wrong calculation, real double-count, broken citation, hidden TODO, or no-advice failure | `true` | `needs_fix` |
| `unknown` | current claim/section/calculation uses the missing field | `true` | `needs_fix` |
| `unknown` | missing field is visible and unused | `false` | `accepted_with_todos` |
| `method_unavailable` | frozen goal requires the method and no approved fallback exists | `true` | `blocked` |
| `method_unavailable` | method is not required or a visible fallback/unknown/omit is used | `false` | `accepted_with_todos` |
| `report_limitation` | limitation is visible and unsupported use is absent | `false` | `accepted_with_todos` |
| `historical_backlog`, `policy_retired`, `not_required_for_active_v1` | `impact_scope: none` | `false` | no canonical impact |

Coherence constraints are strict: `active_defect` always blocks; `unknown` cannot use
workflow scope; `method_unavailable` uses method scope; a visible
`report_limitation` does not block; and the three history/policy dispositions require
`impact_scope: none`, no affected capability, and `blocks_current_goal: false`.

## Artifact item schema

Use this schema for `workflow_state.yaml` `artifacts[]` entries:

| field | required | allowed values / notes |
|---|---:|---|
| `artifact_type` | true | `workflow_state`, `report`, `final_report`, `manifest`, `handoff`, `readout`, or local type. A bound human-review target uses `final_report`. |
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
| `gate_id` | true | Canonical `G0`–`G10` id from `RESEARCH_WORKFLOW.md`; unique within the state. |
| `status` | true | `pass`, `fail`, `not_checked`, `not_applicable`. |
| `checked_by` | false | Usually `quality-review` or `research-orchestrator`. |
| `checked_at` | false | ISO date or datetime. |
| `notes` | false | Gate-specific notes or TODO pointer. |
| `local_check_id` | false | Compatibility or skill-local check id; never replaces `gate_id`. |
| `mapped_global_gate_ids` | conditional | Non-empty list of canonical gates when `local_check_id` is present; must include `gate_id`. |

Local R5, Bundle, Night, data-layer and report-production IDs may appear only in
`local_check_id`. Active V1 state rejects gates outside G0–G10, combined IDs such as
`G6_G7`, local IDs in `gate_id`, duplicate canonical gates, and local statuses such as
`fail_needs_fix`.

## Current-run singleton assets

An active run has exactly one current copy of each control asset:

```text
workflow_state.yaml
open_todos.csv
quality_gate_report.md
workflow_readout.md
```

Bundle/Night readouts, local scorecards and data-layer quality reports are supporting or
historical artifacts in `artifact_manifest.csv`; they are not parallel current state or
quality conclusions.

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
| `impact_scope` | true for `current_goal_v1` | `workflow`, `report`, `section`, `claim`, `method`, or `none`. |
| `active_disposition` | true for `current_goal_v1` | One of the seven dispositions in the current-goal truth table. |
| `affected_capabilities` | true for `current_goal_v1` | Unique YAML list; non-empty unless scope is `none`. |
| `blocks_current_goal` | true for `current_goal_v1` | Boolean validated against scope and disposition; never inferred from severity alone. |
