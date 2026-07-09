# R5 Patch 37 - Reviewed Evidence Intake Protocol

## Goal

Create the intake contract that turns `R5_evidence_request_queue.yaml` planned requests into reviewed local inputs. This patch defines the protocol and schemas only; it does not fetch external evidence.

## Background

The current close gate keeps R5 at `R5_CONTRACTS_EXECUTABLE_WITH_TODOS_ONLY`. The next step is to convert planned evidence requests into reviewed input records with explicit source rank, as-of date, reviewer, allowed usage, and unresolved TODO handling.

## Allowed files

- `.agents/skills/evidence-ingest/references/r5_reviewed_evidence_intake_contract.md`
- `.agents/skills/evidence-ingest/assets/r5_reviewed_evidence_registry.example.yaml`
- `.agents/skills/evidence-ingest/scripts/validate_r5_reviewed_evidence_registry.py`
- `tests/test_validate_r5_reviewed_evidence_registry.py`
- `reports/p1_6/R5_PATCH_37_REVIEWED_EVIDENCE_INTAKE_READOUT.md`

## Required behavior

1. Define a reviewed evidence registry schema with at least:
   - `registry_id`
   - `workflow_id`
   - `stock_code`
   - `source_gap_id`
   - `request_id`
   - `evidence_id`
   - `source_type`
   - `source_rank`
   - `as_of_date`
   - `review_status`
   - `reviewer`
   - `allowed_usage`
   - `claim_scope`
   - `metric_scope`
   - `limitations`
   - `no_live_api: true`
2. Validator must reject:
   - missing `evidence_id` when `review_status: reviewed`
   - missing `as_of_date` for market, peer, event, or sentiment usage
   - `allowed_usage` containing trading instructions
   - `review_status: reviewed` with unresolved `TODO_SOURCE_REQUIRED`
3. Validator must accept `planned` / `needs_review` rows with `evidence_id: null`, but only as TODO rows.

## Tests

Run:

```bash
python -m py_compile .agents/skills/evidence-ingest/scripts/validate_r5_reviewed_evidence_registry.py
python -m pytest -q tests/test_validate_r5_reviewed_evidence_registry.py --tb=short
```

## Readout

Add `reports/p1_6/R5_PATCH_37_REVIEWED_EVIDENCE_INTAKE_READOUT.md`.


## Global boundaries

- Do not call live APIs.
- Do not download unreviewed external files.
- Do not generate buy / sell / hold / position-size advice.
- Do not promote `TODO_*`, `MISSING_DISCLOSURE`, `LOW_CONFIDENCE_CLUE_ONLY`, or `evidence_id: null` into facts.
- Do not mark sample-quality or P2 ready unless the explicit readiness gate allows it.
- Do not rewrite historical legacy readouts; add canonical readouts only.
- Every patch must add a readout under `reports/p1_6/` with: files_added, files_modified, commands_run, exit_code, stdout/stderr summary, artifact_evidence, known_todos, and next_recommended_patch.
