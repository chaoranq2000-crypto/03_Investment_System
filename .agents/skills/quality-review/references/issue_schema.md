# Quality Issue Schema

## Purpose

`quality_issues.csv` records review findings that decide whether an artifact is accepted, accepted with visible TODOs, needs fixes, or blocked.

The active V1 structure is used by `r5_quality_issues.example.csv`. Historical
compact files without mapping columns remain readable in compatibility mode but
must not be copied into a new run.

## Required fields

```csv
issue_id,severity,gate_id,local_check_id,mapped_global_gate_ids,stage,target_artifact,section,description,fix_owner_skill,impact_scope,active_disposition,affected_capabilities,blocks_current_goal,blocking_decision,next_action,status
```

Protected historical CSVs without the four current-goal fields remain readable only in
legacy compatibility mode. New or updated active V1 issue lists must include all four
fields and should validate with `--require-current-goal`. A partial four-field header is
invalid.

## severity enum

```text
critical
high
medium
low
```

Severity describes the potential research risk. It does not by itself decide whether the
current workflow goal is blocked. A visible, unused `unknown` can remain high severity and
still support `accepted_with_todos`; an actually used unsupported number remains an active
defect and requires `needs_fix`.

## gate_id values

Global workflow gates:

```text
G0
G1
G2
G3
G4
G5
G6
G7
G8
G9
G10
```

`gate_id` accepts only this canonical set. For a local check, it is the primary
owner gate and must also appear in `mapped_global_gate_ids`.

## Local check values

`local_check_id` records compatibility and skill-local identifiers. Examples:

```text
QR-*
R5-G1
R5-G2
R5-G3
R5-G4
R5-G5
R5-G6
R5-G7
R5-G8
R5-G9
R5-G10
R5-G11
```

R5 gate IDs are local to the R5 quality rubric. They do not extend the global
workflow gate table and never occupy `gate_id` in an active V1 row. The complete
R5 mapping, owner, boundary and failure route are defined in `r5_quality_gate.md`.

`mapped_global_gate_ids` is a pipe-separated, non-empty list of canonical gates
when `local_check_id` is present. Every listed value must be G0–G10 and the
primary `gate_id` must be included.

## blocking_decision values

```text
accepted
accepted_with_todos
needs_fix
blocked
```

`blocking_decision` is a compatibility/readout projection. For current-goal rows the
validator derives and verifies it from the following four fields; it cannot override them:

| field | values / format |
|---|---|
| `impact_scope` | `workflow`, `report`, `section`, `claim`, `method`, `none` |
| `active_disposition` | `active_defect`, `unknown`, `method_unavailable`, `report_limitation`, `historical_backlog`, `policy_retired`, `not_required_for_active_v1` |
| `affected_capabilities` | Pipe-separated capability IDs; empty only for `impact_scope=none`. |
| `blocks_current_goal` | Literal `true` or `false`. |

## Deterministic current-goal truth table

| active_disposition | scope / dependency | blocks_current_goal | derived decision |
|---|---|---:|---|
| `active_defect` | workflow identity/path/parse/source failure prevents any honest target output | `true` | `blocked` |
| `active_defect` | current artifact contains unsupported use, wrong calculation, real double-count, broken citation, hidden TODO, or no-advice violation | `true` | `needs_fix` |
| `unknown` | current claim, section, or calculation uses the field | `true` | `needs_fix` |
| `unknown` | field is visible and unused | `false` | `accepted_with_todos` |
| `method_unavailable` | the frozen goal requires the method and has no approved fallback | `true` | `blocked` |
| `method_unavailable` | method is not required or a visible fallback/unknown/omit is used | `false` | `accepted_with_todos` |
| `report_limitation` | visible with no unsupported use | `false` | `accepted_with_todos` |
| `historical_backlog`, `policy_retired`, `not_required_for_active_v1` | `impact_scope=none`, no affected capability | `false` | `accepted` |

`active_defect` always blocks the current goal. Workflow scope is reserved for failures
that prevent any honest target output and therefore derives `blocked`; defects scoped to
report/section/claim/method derive `needs_fix`. `method_unavailable` uses method scope.
The three history/policy dispositions have no canonical impact.

## status values

```text
open
resolved
accepted_todo
waived_with_reason
```

`open` is active. `accepted_todo` remains visible and requires
`blocks_current_goal=false`; severity does not change that result.
`waived_with_reason` requires a visible reason in `next_action` or notes.

## Mandatory high severity patterns

These issue classes must be `high`:

```text
direct trading instruction
hidden TODO
unsupported number
real double-count
no-advice violation
```

They must also use `active_disposition=active_defect` and
`blocks_current_goal=true`. They may be fixed later, but their recorded severity should
still reflect the original risk.
