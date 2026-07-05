# Stock Deep Dive Skill Merge Readout

- report_date: 2026-07-05
- phase: P1.6
- status: validated_passed
- final_decision: accepted_p1_6_no_p2
- validated_at: 2026-07-06

## Scope

This patch consolidates the stock analysis-pack layer and report-writing layer
into `stock-deep-dive` as the single active stock research entry point.

This is P1.6 skill consolidation only.
No P2 gate is opened.
No live API was executed.
No trading advice was generated.
R4 disclosure TODOs remain visible.

## Files migrated

- analyst reference: analysis pack contract
- analyst reference: business breakdown contract
- analyst reference: forecast and valuation contract
- analyst reference: market sentiment and event contract
- writer reference: report style guide
- analyst asset: stock analysis pack template
- writer asset: stock deep dive report template

## Old skill directories removed

- stock research analyst legacy directory
- stock report writer legacy directory
- stock report write alias directory, if present

## Active config check

- `stock-deep-dive` remains the active stock deep dive skill.
- Legacy stock analysis/report-writing skill names should not appear in active routing or config.

## Docs updated

The patch attempts to remove legacy stock skill references from active docs and routing:

- `README.md`
- `docs/workflows/RESEARCH_WORKFLOW.md`
- `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md`
- `.agents/skills/research-orchestrator/references/skill_routing_matrix.md`
- `.agents/skills/research-orchestrator/SKILL.md`

Historical reports are not rewritten.

## Tests to run

```bash
python .agents/skills/stock-deep-dive/scripts/validate_stock_deep_dive_merge.py
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_stock_deep_dive_merge.py
python -m pytest -q tests/test_stock_deep_dive_skill_merge.py
git diff --check
```

Optional full regression:

```bash
python -m pytest -q
```

## Local validation result

- merge validator: PASS
- py_compile: PASS
- targeted pytest: PASS, 7 passed
- git diff --check: PASS
- strict legacy-name check outside reports/logs/patch prompt: PASS
- live API execution: not run
- P2 gate: not opened

## Remaining TODOs

- Keep R4 disclosure TODOs visible if official disclosure remains missing.
