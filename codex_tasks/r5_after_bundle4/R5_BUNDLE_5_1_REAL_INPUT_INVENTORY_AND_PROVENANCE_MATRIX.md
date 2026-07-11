# R5 Bundle 5.1 — Real input inventory and provenance matrix

## Background

Bundle 4 proved the transport and registry mechanics with synthetic fixtures. Bundle 5 must first prove that real 002837 inputs exist, are reviewable and have valid evidence anchors. Parsing is not review acceptance.

## Goal

Build a machine-readable inventory and reviewer-facing provenance matrix for all expected real inputs without promoting anything.

## Required input types

Core:

- `business_disclosure`
- `market_snapshot`
- `peer_snapshot`
- `forecast_assumptions`
- `valuation_inputs`

Optional enhancement:

- `sentiment_event_sources`

## Allowed files

- `data/reviewed_inputs/wf_20260703_stock_first_002837_invic/**`
- new immutable raw evidence versions under existing `data/raw/**` locations
- extracted/normalized derivatives under existing `data/processed/**` locations
- evidence/claim/metric manifests under `data/manifests/`
- `wf_20260703_stock_first_002837_invic` run artifacts limited to inventory, source-request and validation outputs
- focused scripts/tests only when existing tooling cannot express the inventory faithfully
- `reports/p1_6/R5_BUNDLE_5_1_REAL_INPUT_INVENTORY_READOUT.md`

## Forbidden scope

- Do not set accepted status automatically.
- Do not fabricate reviewer, reviewed_at, evidence ID, source rank, as-of date or limitations.
- Do not use templates, fixtures or sample reports as evidence.
- Do not promote registries.
- Do not mutate existing committed real gate/render outputs.

## Required work

1. Inspect the real dropzone and source manifests.
2. Produce `R5_bundle5_real_input_inventory.yaml` containing, for every expected item:
   - input ID/type/path;
   - workflow ID and stock code;
   - review status;
   - source evidence IDs and physical source paths;
   - source rank, as-of/publication date and freshness status;
   - reviewer/reviewed_at only when genuinely present;
   - conflicts, limitations and missing fields;
   - candidate registry target;
   - blocking/non-blocking classification.
3. Produce or refresh a source-request queue for missing evidence.
4. Run dropzone validation in read-only mode.
5. Fail closed when accepted records contain placeholders or unresolved critical TODO tokens.

## Acceptance gate

This card passes as an inventory card even when inputs are missing, provided the missing state is complete and truthful. It authorizes Card 5.2 only when official disclosure candidates have real evidence anchors; it does not authorize promotion.

## Suggested commands

```bash
python scripts/validate_r5_reviewed_input_dropzone.py   --root data/reviewed_inputs/wf_20260703_stock_first_002837_invic   --json reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_dropzone_validation_initial.json
python -m pytest -q tests/test_r5_bundle5_real_input_inventory.py tests/test_validate_r5_reviewed_input_dropzone.py --tb=short -p no:cacheprovider
git diff --check
```

## Stop condition

If no real files are present, close this card as `blocked_source_gapped`, emit the source-request queue and stop. Do not generate empty accepted records to continue.
