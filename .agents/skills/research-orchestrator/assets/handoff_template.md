# Handoff: <current_stage> -> <target_skill>

> This is the only handoff packet template for `research-orchestrator`.
> `WORKFLOW_ORCHESTRATION_SPEC.md` owns runtime rules and must not embed
> another full template.

## Workflow

| field | value |
|---|---|
| workflow_id |  |
| workflow_type |  |
| run_mode |  |
| current_stage |  |
| target_skill |  |

## Objective

TODO: state the exact action for the target skill.

## Inputs

| input | path_or_value | required | notes |
|---|---|---:|---|
| user_request |  | true |  |
| canonical_docs | `docs/workflows/RESEARCH_WORKFLOW.md` | true |  |
| orchestration_spec | `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` | true |  |
| source_artifact |  | false |  |

## Expected Outputs

| output | path | required | notes |
|---|---|---:|---|

## Required Artifacts

| artifact_type | path | required | notes |
|---|---|---:|---|

## Guardrails

- Do not create buy / sell / hold instructions.
- Do not invent evidence, claims, metrics, exposure, revenue share, or valuation numbers.
- Mark missing information as `TODO`, `MISSING`, `LOW_CONFIDENCE`, or `UNVERIFIED`.
- Preserve fact / estimate / inference / management_comment / analyst_view / opinion boundaries.

## Completion Criteria

- TODO: define observable completion criteria.
- TODO: identify the artifact paths that prove completion.

## Next Gate

| field | value |
|---|---|
| next_gate |  |
| gate_owner | `quality-review` or `research-orchestrator` |

## Open TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
