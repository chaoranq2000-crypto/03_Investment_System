# Orchestration Contract — research-orchestrator reference

This reference defines how `research-orchestrator` performs runtime orchestration.

It must not define global workflow types, global stages, or global gates.

For those facts, use:

```text
docs/workflows/RESEARCH_WORKFLOW.md
```

## Runtime objective

```text
classify request
→ create or update workflow_state
→ determine next stage
→ route to lower skill
→ write handoff packet
→ track artifacts and TODOs
→ call quality review when required
→ close workflow_readout
```

## Non-run diagnostic mode

If the user only asks for status, gaps, or next-step advice, the orchestrator may answer without creating a workflow run.

The answer must state:

```text
No workflow run was created.
```

## Workflow run directory

For full runs, resumes, debug runs, and closeouts:

```text
reports/workflow_runs/<workflow_id>/
├── workflow_state.yaml
├── run_log.md
├── artifact_manifest.csv
├── open_todos.csv
├── quality_gate_report.md
├── workflow_readout.md
└── handoffs/
```

## Handoff packet format

```md
# Handoff: <source_skill> -> <target_skill>

## Workflow

- workflow_id:
- workflow_type:
- current_stage:
- requested_skill:

## Objective

What this skill must complete.

## Inputs

- user input:
- canonical docs:
- input artifacts:
- optional references:

## Expected Outputs

- paths:
- required fields:
- status update:

## Guardrails

- prohibited actions:
- missing evidence handling:
- allowed file changes:

## Completion Criteria

- completion criteria:
- next gate or next skill:
```

## Artifact manifest format

```csv
artifact_id,artifact_type,path,created_by_skill,stage,required,exists,status,notes
```

## Open TODO format

```csv
issue_id,severity,stage,target_artifact,description,fix_owner_skill,status,created_at,resolved_at,notes
```

## Readout format

```md
# Workflow Readout: <workflow_id>

## Status

accepted / accepted_with_todos / needs_fix / blocked

## Scope

- workflow_type:
- object:
- date_range:
- depth:

## Skills Used

| skill | stages | outputs |
|---|---|---|

## Artifacts

| artifact | path | status |
|---|---|---|

## Quality Gates

| gate | status | notes |
|---|---|---|

## Backflow Decisions

| decision | target | action | status |
|---|---|---|---|

## Remaining TODOs

| issue | severity | owner_skill | next_action |
|---|---|---|---|

## P2 Readiness

- ready_for_limited_p2:
- reasons:
- blockers:
```

## Failure behavior

If a required artifact is missing, do not silently proceed. Update:

```yaml
status: blocked | needs_fix
blocked_by:
required_next_skill:
open_todos:
```

If high severity issues exist, do not mark accepted.
