# R5 Patch 37 Reviewed Evidence Intake Readout

status: accepted_with_todos

## files_added

- `.agents/skills/evidence-ingest/references/r5_reviewed_evidence_intake_contract.md`
- `.agents/skills/evidence-ingest/assets/r5_reviewed_evidence_registry.example.yaml`
- `.agents/skills/evidence-ingest/scripts/validate_r5_reviewed_evidence_registry.py`
- `tests/test_validate_r5_reviewed_evidence_registry.py`

## files_modified

- none

## commands_run

- `.\\.conda\\investment-system\\python.exe -m py_compile .agents\\skills\\evidence-ingest\\scripts\\validate_r5_reviewed_evidence_registry.py .agents\\skills\\stock-deep-dive\\scripts\\validate_r5_market_snapshot.py .agents\\skills\\stock-deep-dive\\scripts\\validate_r5_peer_snapshot.py .agents\\skills\\evidence-ingest\\scripts\\validate_r5_official_disclosure_gap_review.py`
- `.\\.conda\\investment-system\\python.exe -m pytest -q tests\\test_validate_r5_reviewed_evidence_registry.py tests\\test_validate_r5_market_snapshot.py tests\\test_validate_r5_peer_snapshot.py tests\\test_validate_r5_official_disclosure_gap_review.py --tb=short`

## exit_code

- py_compile: 0
- pytest: 0

## stdout_or_stderr_summary

- pytest: `12 passed in 0.12s`
- stderr: none observed

## artifact_evidence

- critical_evidence: checked=4 declared Patch 37 files.
- Planned and `needs_review` rows with `evidence_id: null` remain valid only as visible TODO rows.
- `reviewed` rows require `evidence_id`, reviewer, no unresolved `TODO_SOURCE_REQUIRED`, and `as_of_date` for market/peer/event/sentiment usage.
- `allowed_usage` rejects direct trading language.

## known_todos

- The example registry intentionally keeps `TODO_SOURCE_REQUIRED` and `TODO_MARKET_DATA` because no reviewed dated market evidence was supplied.

## next_recommended_patch

- R5 Patch 38 - Market Snapshot Reviewed Inputs
