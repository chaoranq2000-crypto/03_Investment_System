# R5 Patch 38 - Market Snapshot Reviewed Inputs

## Goal

Replace the market TODO stub pattern with a reviewed-input-ready market snapshot contract and validator. This patch may include an example with placeholder values, but it must not invent a live market snapshot.

## Background

Current `R5_market_snapshot_stub.yaml` intentionally has `status: TODO_MARKET_DATA`, `as_of_date: null`, and null valuation fields. R5 cannot write valuation or technical-state language until a reviewed, dated market snapshot exists.

## Allowed files

- `.agents/skills/stock-deep-dive/references/r5_market_snapshot_review_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_market_snapshot.reviewed.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_market_snapshot.py`
- `tests/test_validate_r5_market_snapshot.py`
- `reports/p1_6/R5_PATCH_38_MARKET_SNAPSHOT_REVIEWED_INPUTS_READOUT.md`

## Required behavior

1. Define required reviewed market fields:
   - `as_of_date`
   - `currency`
   - `current_price`
   - `market_cap`
   - `share_count`
   - `pe_ttm`
   - `pb`
   - `ps`
   - `source_evidence_ids`
   - `allowed_usage`
2. Optional fields:
   - `one_month_return`
   - `three_month_return`
   - `ytd_return`
   - `ma5`, `ma10`, `ma20`, `ma60`, `ma120`, `ma250`
   - `turnover`, `volume_percentile`, `52w_high`, `52w_low`
3. Validator decisions:
   - `sample_quality_candidate` only if all required fields and source IDs exist.
   - `source_gapped_research_draft` if status is TODO or required fields are null.
   - `blocked` if numeric fields exist but no source evidence IDs.
4. Must not fill real 002837 market numbers in this patch unless they are manually reviewed and include evidence IDs.

## Tests

```bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_market_snapshot.py
python -m pytest -q tests/test_validate_r5_market_snapshot.py --tb=short
```

## Readout

Add `reports/p1_6/R5_PATCH_38_MARKET_SNAPSHOT_REVIEWED_INPUTS_READOUT.md`.


## Global boundaries

- Do not call live APIs.
- Do not download unreviewed external files.
- Do not generate buy / sell / hold / position-size advice.
- Do not promote `TODO_*`, `MISSING_DISCLOSURE`, `LOW_CONFIDENCE_CLUE_ONLY`, or `evidence_id: null` into facts.
- Do not mark sample-quality or P2 ready unless the explicit readiness gate allows it.
- Do not rewrite historical legacy readouts; add canonical readouts only.
- Every patch must add a readout under `reports/p1_6/` with: files_added, files_modified, commands_run, exit_code, stdout/stderr summary, artifact_evidence, known_todos, and next_recommended_patch.
