# Workflow Orchestration Spec — compatibility pointer

This file is kept only for backward-compatible links.

It no longer defines global workflow facts.

## Canonical sources

Use these sources instead:

```text
docs/workflows/RESEARCH_WORKFLOW.md
    Global workflow_type, global stage_id, global gate_id, backflow decision, P2 readiness.

.agents/skills/research-orchestrator/references/orchestration_contract.md
    Runtime handoff format, workflow state handling, routing procedure, readout procedure.

.agents/skills/research-orchestrator/SKILL.md
    Thin execution entrypoint.
```

## Rule

This file must not define:

```text
workflow_type enum
global stage table
global gate_id table
run status enum
```

If a future edit needs one of those facts, update `RESEARCH_WORKFLOW.md` instead.
