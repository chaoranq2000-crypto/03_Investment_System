# R5 Bundle 5.3 — Market and peer input onboarding

## Background

The Bundle 4 close state explicitly lists missing real market snapshot, peer set and peer metrics. These inputs must be dated, method-consistent and independently reviewable.

## Goal

Create reviewed `market_snapshot` and `peer_snapshot` inputs for 002837 without promoting them.

## Allowed files

- immutable raw market snapshots under existing `data/raw/market_data/`
- normalized market/peer tables under existing processed locations
- evidence/metric manifests
- `data/reviewed_inputs/wf_20260703_stock_first_002837_invic/market_snapshot/**`
- `data/reviewed_inputs/wf_20260703_stock_first_002837_invic/peer_snapshot/**`
- staging-only validation outputs
- focused validators/tests
- `reports/p1_6/R5_BUNDLE_5_3_MARKET_PEER_INPUT_READOUT.md`

## Forbidden scope

- Do not mix prices, share counts, financial periods or currencies without explicit normalization.
- Do not select peers solely to support a preferred valuation conclusion.
- Do not use user sample reports as market/peer evidence.
- Do not infer live/current values from stale snapshots.
- Do not promote registries or generate trading recommendations.

## Required work

### Market snapshot

Record stock code/exchange, as-of timestamp and timezone, close/adjustment convention, share count basis, market capitalization method, currency, source evidence ID, source rank, reviewer and limitations.

### Peer snapshot

Record peer inclusion/exclusion rationale, business/exposure comparability, metric name, period, unit, accounting basis, source and normalization method. Flag mixed-period or stale rows. Preserve an empty/insufficient peer set when comparability is weak.

### Validation

- unique input IDs and one workflow/stock per validated root;
- accepted rows contain no placeholder evidence;
- market and peer metrics reconcile to referenced source rows;
- stale/conflicting observations are visible in issues/TODOs.

## Acceptance gate

Both input types have at least one valid reviewed record or the card closes blocked with an explicit evidence request. Parsing success alone is not acceptance.

## Suggested commands

```bash
python scripts/validate_r5_reviewed_input_dropzone.py   --root data/reviewed_inputs/wf_20260703_stock_first_002837_invic/market_snapshot   --json reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_market_snapshot_validation.json
python scripts/validate_r5_reviewed_input_dropzone.py   --root data/reviewed_inputs/wf_20260703_stock_first_002837_invic/peer_snapshot   --json reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_peer_snapshot_validation.json
python -m pytest -q tests/test_r5_bundle5_market_peer_onboarding.py tests/test_r5_market_peer_input_registry.py --tb=short -p no:cacheprovider
git diff --check
```
