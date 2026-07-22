# Orchestration Contract — compatibility pointer

This path is retained only for links created before the runtime-owner cleanup. It is
not an active workflow fact source and must not be copied into a new run.

Use these current owners:

| concern | canonical owner |
|---|---|
| workflow types, stages, G0–G10 and backflow decisions | `docs/workflows/RESEARCH_WORKFLOW.md` |
| runtime dispatch, fix loop and close rules | `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md` |
| workflow state, artifact manifest and open TODO fields | `workflow_state_schema.md` |
| handoff packet fields | `../assets/handoff_template.md` |
| quick skill routing | `skill_routing_matrix.md` |

New and updated active states use `state_schema_version: r5_v1`. Unmarked states
are legacy compatibility evidence and must not be used as current templates.

This compatibility path defines no run tree, state schema, readout format, quality
outcome, P2 field, gate or completion fact. In particular, only canonical `p2_ready`
from `comparison_readiness_gate` may represent P2 readiness.
