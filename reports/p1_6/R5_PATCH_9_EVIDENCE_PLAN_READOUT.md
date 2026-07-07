# R5 Patch 9 Readout — evidence-ingest R5 stock evidence plan

## Result

Status: completed_plan_schema_validator

This patch adds the R5 stock evidence plan contract, example, validator, and tests. It does not add a downloader, call a real API, download announcements/market/news, modify `data/raw/` or `data/processed/`, or generate real claims/metrics.

## Files changed

- `.agents/skills/evidence-ingest/references/r5_stock_evidence_plan_contract.md`
- `.agents/skills/evidence-ingest/assets/r5_stock_evidence_plan.example.yaml`
- `.agents/skills/evidence-ingest/scripts/validate_r5_stock_evidence_plan.py`
- `tests/test_validate_r5_stock_evidence_plan.py`
- `reports/p1_6/R5_PATCH_9_EVIDENCE_PLAN_READOUT.md`

## Tests

```bash
python .agents/skills/evidence-ingest/scripts/validate_r5_stock_evidence_plan.py .agents/skills/evidence-ingest/assets/r5_stock_evidence_plan.example.yaml
pytest tests/test_validate_r5_stock_evidence_plan.py
```

Result:

```text
validator decision: accepted
tests/test_validate_r5_stock_evidence_plan.py: 6 passed
```

## Boundary

The plan preserves missing official disclosures as `MISSING_DISCLOSURE` and requires expected artifacts for manifest rows, claim candidates, metric candidates, and ingest log.
