# Stock Report Production Workflow — compatibility pointer

This file is kept only for backward-compatible links.

`stock_report_production` is not a permanent `workflow_type`.

It is a local stock-deep-dive profile:

```yaml
profile_id: stock_report_production
parent_workflow_type: stock_first_closed_loop
```

## Canonical sources

Use these sources instead:

```text
docs/workflows/RESEARCH_WORKFLOW.md
    Global `stock_first_closed_loop` workflow, stages, gates, and backflow decisions.

.agents/skills/stock-deep-dive/references/report_production_profile.md
    Stock report production profile, report quality target, local T0-T11 production steps.

.agents/skills/stock-deep-dive/SKILL.md
    Execution contract for stock deep dive.
```

## Rule

This file must not define the old stock-report-production value as a `workflow_type`.

If stock report production details change, update the stock-deep-dive reference profile rather than adding another workflow doc.
