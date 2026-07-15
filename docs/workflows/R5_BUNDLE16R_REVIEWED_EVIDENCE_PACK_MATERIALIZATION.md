# R5 Bundle 16R — Reviewed Evidence Pack Materialization

## Purpose

Bundle 16R closes the runtime gap between already-reviewed repository evidence and
the Bundle 15R qualification compiler.

```text
reviewed physical official sources
+ reviewed claim/metric records
+ Bundle 14R case contracts
+ explicit reviewer mapping
+ hash-bound overlap/forecast/valuation/quality artifacts
        ↓
Bundle 15R-compatible evidence-pack candidates
+ source-request queue
+ mapping queue
+ owner/stage backflow queue
        ↓
existing Bundle 15R compiler
        ↓
existing Bundle 14R golden regression, selectively
```

It does not fetch, extract, review or fabricate evidence. It does not rewrite the
Bundle 14R or 15R qualification logic. It does not mutate canonical workflow
state, generate a Reader, accept human review, or authorize sample quality/P2.

## Inputs

1. Bundle 14R case contracts under `tests/fixtures/r5_bundle14r/cases/`.
2. One or more reviewed source/record catalogs in YAML, JSON or CSV.
3. One reviewer-authored Bundle 16R mapping per case.
4. Optional hash-bound artifacts for overlap reconciliation, forecast bridge,
   valuation eligibility, semantic quality, determinism and exact-hash review.

The mapping may classify and link records, but cannot override catalog values,
units, periods, definitions, confidence or source IDs.

## Outputs

A preview run writes only under `--output-dir`:

```text
R5_bundle16r_materialization_suite.json
R5_bundle16r_catalog_inventory.json
R5_bundle16r_source_request_queue.csv
R5_bundle16r_mapping_queue.csv
R5_bundle16r_backflow_queue.csv
R5_bundle16r_status_proposal.yaml
R5_bundle16r_generation_lock.yaml
R5_BUNDLE16R_MATERIALIZATION_READOUT.md
pack_candidates/<case_id>.yaml
```

Publishing pack candidates requires both `--apply-packs` and `--packs-dir` and
uses atomic replacement. Canonical workflow state is never edited.

## Fail-closed rules

- physical source path and SHA-256 must match;
- source must be official and accepted/accepted-with-limitations;
- narrative samples and generated reports cannot be evidence;
- reviewer mapping must carry a real reviewer and timestamp;
- driver and question IDs must match the case contract;
- confirmed/bounded records require high or medium confidence;
- record value/unit/period/definition/source overrides are rejected;
- passed overlap, forecast, valuation, semantic and determinism blocks must be
  extracted from physically hash-bound artifacts;
- missing blocks remain explicitly blocked;
- all release flags remain false.

## Normal execution

```bash
python scripts/run_r5_bundle16r_evidence_pack_materializer.py \
  --repo-root . \
  --cases-dir tests/fixtures/r5_bundle14r/cases \
  --catalog-dir data/processed/normalized \
  --mapping-dir reports/golden_regressions/reviewed_mappings \
  --output-dir reports/p1_6/r5_bundle16r/materialization_preview \
  --expected-base <exact-head>
```

After human inspection, publish the candidates and invoke the existing compiler:

```bash
python scripts/run_r5_bundle16r_evidence_pack_materializer.py \
  --repo-root . \
  --cases-dir tests/fixtures/r5_bundle14r/cases \
  --catalog-dir data/processed/normalized \
  --mapping-dir reports/golden_regressions/reviewed_mappings \
  --output-dir reports/p1_6/r5_bundle16r/materialization \
  --packs-dir reports/golden_regressions/reviewed_evidence_packs \
  --apply-packs \
  --run-bundle15r \
  --bundle15r-output-dir reports/p1_6/r5_bundle16r/qualification \
  --run-bundle14r \
  --bundle14r-output-dir reports/p1_6/r5_bundle16r/golden_regression \
  --expected-base <exact-head>
```

A blocked or partial result is valid. Lowering the gate to manufacture a pass is
not permitted.
