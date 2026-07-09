# R5 Patch 39 - Peer Snapshot Reviewed Inputs

## Goal

Create a reviewed peer-set and peer valuation snapshot contract. This is the prerequisite for R5 valuation context.

## Background

Current `R5_peer_snapshot_stub.yaml` has `status: TODO_PEER_DATA`, empty `peer_set`, and empty `peer_metrics`. R5 should not produce peer relative valuation until the peer set is reviewed and dated.

## Allowed files

- `.agents/skills/stock-deep-dive/references/r5_peer_snapshot_review_contract.md`
- `.agents/skills/stock-deep-dive/assets/r5_peer_snapshot.reviewed.example.yaml`
- `.agents/skills/stock-deep-dive/scripts/validate_r5_peer_snapshot.py`
- `tests/test_validate_r5_peer_snapshot.py`
- `reports/p1_6/R5_PATCH_39_PEER_SNAPSHOT_REVIEWED_INPUTS_READOUT.md`

## Required behavior

1. Define peer set fields:
   - `peer_id`
   - `stock_code`
   - `company_name`
   - `exchange`
   - `selection_reason`
   - `segment_overlap`
   - `source_evidence_ids`
2. Define peer metric fields:
   - `as_of_date`
   - `market_cap`
   - `pe_ttm`
   - `forward_pe` if available
   - `pb`
   - `ps`
   - `gross_margin` if available
   - `revenue_growth` if available
   - `source_evidence_ids`
3. Validator must reject sample-quality peer context if:
   - fewer than 3 reviewed peers are present,
   - peer metrics have no as-of date,
   - a peer has no selection reason,
   - peer data has no source evidence IDs.
4. Validator may accept source-gapped drafts with explicit TODOs.

## Tests

```bash
python -m py_compile .agents/skills/stock-deep-dive/scripts/validate_r5_peer_snapshot.py
python -m pytest -q tests/test_validate_r5_peer_snapshot.py --tb=short
```

## Readout

Add `reports/p1_6/R5_PATCH_39_PEER_SNAPSHOT_REVIEWED_INPUTS_READOUT.md`.


## Global boundaries

- Do not call live APIs.
- Do not download unreviewed external files.
- Do not generate buy / sell / hold / position-size advice.
- Do not promote `TODO_*`, `MISSING_DISCLOSURE`, `LOW_CONFIDENCE_CLUE_ONLY`, or `evidence_id: null` into facts.
- Do not mark sample-quality or P2 ready unless the explicit readiness gate allows it.
- Do not rewrite historical legacy readouts; add canonical readouts only.
- Every patch must add a readout under `reports/p1_6/` with: files_added, files_modified, commands_run, exit_code, stdout/stderr summary, artifact_evidence, known_todos, and next_recommended_patch.
