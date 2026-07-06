# Workflow State Schema

`workflow_state.yaml` records the current state of one research workflow run.

This schema consumes canonical workflow types from:

```text
docs/workflows/RESEARCH_WORKFLOW.md
```

It must not introduce additional permanent workflow types.

## Required fields

```yaml
workflow_id: wf_YYYYMMDD_<workflow_type>_<slug>
workflow_type: segment_to_stock_closed_loop | stock_first_closed_loop | segment_stock_interlock | refresh_existing_research | comparison_readiness_gate
run_mode: normal | diagnostic
status: planned | in_progress | blocked | needs_fix | ready_for_review | accepted | accepted_with_todos | archived
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
owner: human | codex | mixed
active_segment_id: null
active_company_id: null
current_stage: string
completed_stages: []
next_stage: string
active_skill: research-orchestrator
required_next_skill: string
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
artifacts: []
open_todos: []
quality_gates: []
entry_criteria: []
exit_criteria: []
notes: null
```

`run_mode: diagnostic` is for read-only status / gap / next-step checks. It is not a workflow type.

## Status rules

- `accepted` requires no high severity issue.
- `accepted_with_todos` allows medium / low TODOs only if explicitly listed.
- `blocked` requires `blocked_by` in notes or open_todos.
- `needs_fix` requires `required_next_skill` and target stage.

## Minimal artifact item

```yaml
- artifact_type:
  path:
  created_by_skill:
  stage:
  status: missing | draft | current | stale | needs_fix
  required: true
```

## Minimal quality gate item

```yaml
- gate_id: one of G0, G1, G2, G3, G4, G5, G6, G7, G8, G9, G10
  status: pass | fail | not_checked | not_applicable
  checked_by:
  notes:
```
