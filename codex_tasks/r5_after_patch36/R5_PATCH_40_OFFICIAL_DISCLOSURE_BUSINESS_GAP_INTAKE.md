# R5 Patch 40 - Official Disclosure Business Gap Intake

## Goal

Create a disciplined intake path for business-line disclosure gaps, especially `MISSING_DISCLOSURE` around 002837 liquid-cooling revenue, margin, profit contribution and segment exposure.

## Background

The 002837 R5 pack is allowed only as source-gapped draft because business exposure still carries official-disclosure gaps. This patch should convert the gap into an official-disclosure review queue, not into a fabricated business split.

## Allowed files

- `.agents/skills/evidence-ingest/references/r5_official_disclosure_gap_review_contract.md`
- `.agents/skills/evidence-ingest/assets/r5_official_disclosure_gap_review.example.yaml`
- `.agents/skills/evidence-ingest/scripts/validate_r5_official_disclosure_gap_review.py`
- `tests/test_validate_r5_official_disclosure_gap_review.py`
- `reports/p1_6/R5_PATCH_40_OFFICIAL_DISCLOSURE_BUSINESS_GAP_INTAKE_READOUT.md`

## Required behavior

1. Define business disclosure review fields:
   - `gap_id`
   - `requested_disclosure`
   - `official_source_candidates`
   - `reviewed_source_ids`
   - `finding_status`: `found`, `not_found`, `partial`, `needs_manual_review`
   - `extracted_metric_candidates`
   - `limitations`
   - `allowed_usage`
2. If the disclosure is not found, preserve `MISSING_DISCLOSURE` and produce a clear limitation.
3. If partial disclosure is found, it may support only the exact extracted scope.
4. No evidence source may be promoted unless it has an `evidence_id`, source rank, and as-of date or filing date.

## Tests

```bash
python -m py_compile .agents/skills/evidence-ingest/scripts/validate_r5_official_disclosure_gap_review.py
python -m pytest -q tests/test_validate_r5_official_disclosure_gap_review.py --tb=short
```

## Readout

Add `reports/p1_6/R5_PATCH_40_OFFICIAL_DISCLOSURE_BUSINESS_GAP_INTAKE_READOUT.md`.


## Global boundaries

- Do not call live APIs.
- Do not download unreviewed external files.
- Do not generate buy / sell / hold / position-size advice.
- Do not promote `TODO_*`, `MISSING_DISCLOSURE`, `LOW_CONFIDENCE_CLUE_ONLY`, or `evidence_id: null` into facts.
- Do not mark sample-quality or P2 ready unless the explicit readiness gate allows it.
- Do not rewrite historical legacy readouts; add canonical readouts only.
- Every patch must add a readout under `reports/p1_6/` with: files_added, files_modified, commands_run, exit_code, stdout/stderr summary, artifact_evidence, known_todos, and next_recommended_patch.
