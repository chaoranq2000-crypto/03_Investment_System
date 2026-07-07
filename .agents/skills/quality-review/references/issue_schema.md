# Quality Issue Schema

## Purpose

`quality_issues.csv` records review findings that decide whether an artifact is accepted, accepted with visible TODOs, needs fixes, or blocked.

For R5-MVP, the same structure is used by `r5_quality_issues.example.csv`.

## Required fields

```csv
issue_id,severity,gate_id,stage,target_artifact,section,description,fix_owner_skill,blocking_decision,next_action,status
```

## severity enum

```text
critical
high
medium
low
```

`critical` and `high` mean the artifact cannot be accepted while the issue is active.

## gate_id values

Global workflow gates:

```text
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

Quality-review local checks:

```text
QR-*
```

R5 local gates:

```text
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

R5 gate IDs are local to the R5 quality rubric. They do not extend the global workflow gate table.

## blocking_decision values

```text
accepted
accepted_with_todos
needs_fix
blocked
```

## status values

```text
open
resolved
accepted_todo
waived_with_reason
```

`open` is active. `accepted_todo` remains visible but does not block accepted-with-TODOs when severity is medium or low. `waived_with_reason` requires a visible reason in `next_action` or notes.

## Mandatory high severity patterns

These issue classes must be `high`:

```text
direct trading instruction
hidden TODO
unsupported number
```

They may be fixed later, but their recorded severity should still reflect the original risk.
