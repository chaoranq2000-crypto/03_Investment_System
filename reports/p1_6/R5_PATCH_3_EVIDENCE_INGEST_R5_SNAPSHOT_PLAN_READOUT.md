# R5 Patch 3 Readout — evidence-ingest R5 snapshot plan

## Result

Status: completed_plan_validator

This patch adds an R5 evidence snapshot plan contract and validator. It is plan-only: no downloader, no live API call, no raw-data modification, and no research conclusion generation.

## Files changed

- `.agents/skills/evidence-ingest/references/r5_stock_evidence_snapshot_contract.md`
- `.agents/skills/evidence-ingest/assets/r5_stock_evidence_plan_template.yaml`
- `.agents/skills/evidence-ingest/scripts/validate_r5_evidence_plan.py`
- `tests/test_r5_evidence_snapshot_plan.py`
- `reports/p1_6/R5_PATCH_3_EVIDENCE_INGEST_R5_SNAPSHOT_PLAN_READOUT.md`

## Diff summary

- Defined required R5 evidence request families: official filings, structured financial metrics, market snapshot, peer snapshot, industry clues, news/event clues, and investor-relations context.
- Required every evidence request to carry source type, source rank, `as_of_date`, freshness policy, allowed usage, R5 pack dependency, and visible missing-data handling.
- Added context-only guardrails so market, peer, industry, and news/event clues cannot independently prove business exposure.
- Added handoff fields for `stock-deep-dive` consumption.

## Tests

Pending in this readout until the patch test command is run:

```bash
python -m py_compile .agents/skills/evidence-ingest/scripts/validate_r5_evidence_plan.py
pytest tests/test_r5_evidence_snapshot_plan.py
```

## Source gaps and TODOs

- Official filings, market snapshot, peer snapshot, and context clue requests remain planned/TODO fixture rows.
- The validator checks the plan structure only; it does not register evidence or validate real manifests.
