# B1 Evidence-Ingest Debug Readout

## Metadata

- phase: P1.6 Phase B1
- skill: evidence-ingest
- run_date: 2026-07-02 15:38:31 +08:00
- operator: Codex
- repo_commit: 357ca4e7a41cc0b4ceb81bb2b730df8c4ae21a4c
- branch: codex/p1-6-b1-evidence-ingest-verify
- migration_update_run_date: 2026-07-02

## Scope

This readout validates the evidence-ingest contract. It does not create research conclusions, scorecards, watchlist decisions or trading advice.

B1-only boundary observed:

- Did not use `codex_prompts/P1_6_DETAILED_PLAN_FOR_CODEX.md`.
- Did not start B2 or later phases.
- Did not modify non-B1 skill directories.
- Migrated existing `data/manifests/*` files only after explicit follow-up approval for the remaining B1 TODOs.

## Commands Run

| Command | Result | Notes |
|---|---|---|
| `conda run -p .\.conda\investment-system python --version` | PASS | Python 3.12.13 |
| Patch transport exact-path check | PASS | `README_PATCH.md`, `apply_phase_b1_patch.py`, `phase_b1_patch.zip`, `phase_b1_patch/`, `repo_overlay/`, and `codex_prompts/P1_6_DETAILED_PLAN_FOR_CODEX.md` were not present. |
| B1 required file presence check | PASS | All required Phase B1 files were present. |
| `conda run -p .\.conda\investment-system python .agents/skills/evidence-ingest/scripts/compute_hash.py .agents/skills/evidence-ingest/assets/debug_cases/manual_file_success/input/sample_policy.md` | PASS | SHA256: `6d42e50d3881c8b97614cf0c5f31b5061e2c7162e34a686a04ca18d92e900d57` |
| `conda run -p .\.conda\investment-system python .agents/skills/evidence-ingest/scripts/run_debug_cases.py --repo .` | PASS | `B1_DEBUG_READOUT=PASS` |
| `conda run -p .\.conda\investment-system python -m pytest -q tests/test_phase_b1_evidence_ingest_contract.py` | PASS | `5 passed in 0.61s` |
| `conda run -p .\.conda\investment-system python -m pytest -q` | PASS | `28 passed in 2.09s` |
| Source registry B1 contract check | PASS | Required B1 source entries and fields are present. |
| `conda run -p .\.conda\investment-system python .agents/skills/evidence-ingest/scripts/validate_manifest.py --repo . --manifest data/manifests/evidence_manifest.csv` | FAIL_EXPECTED | Existing manifest uses pre-B1 schema; see issues. |
| `conda run -p .\.conda\investment-system python .agents/skills/evidence-ingest/scripts/validate_candidates.py --repo . --claims .agents/skills/evidence-ingest/assets/claim_candidates.example.csv --metrics .agents/skills/evidence-ingest/assets/metric_candidates.example.csv --manifest .agents/skills/evidence-ingest/assets/evidence_manifest.example.csv` | PASS | Candidate example validation succeeded. |
| Existing draft candidate validation | FAIL_EXPECTED | Existing drafts have pre-B1 schema/content guardrail issues; see issues. |
| `conda run -p .\.conda\investment-system python .agents/skills/evidence-ingest/scripts/migrate_legacy_manifests_to_b1.py --repo .` | PASS | Migrated 15 manifest rows, 22 claim candidates, 44 metric candidates, and 1 clue row. |
| `conda run -p .\.conda\investment-system python .agents/skills/evidence-ingest/scripts/validate_manifest.py --repo . --manifest data/manifests/evidence_manifest.csv` | PASS | Existing manifest now passes B1 validator. |
| `conda run -p .\.conda\investment-system python .agents/skills/evidence-ingest/scripts/check_paths.py data/manifests/evidence_manifest.csv --repo .` | PASS | Path separation and local path existence passed. |
| `conda run -p .\.conda\investment-system python .agents/skills/evidence-ingest/scripts/validate_candidates.py --repo . --manifest data/manifests/evidence_manifest.csv --claims data/manifests/claims_draft.csv --metrics data/manifests/metrics_draft.csv` | PASS | Existing claim and metric drafts now pass B1 candidate gate. |
| UTF-8 `conda run -p .\.conda\investment-system python -m pytest -q` | PASS | `28 passed in 2.14s` |

## Contract Files Checked

| Area | Files | Status | Notes |
|---|---|---|---|
| SKILL | `.agents/skills/evidence-ingest/SKILL.md` | PASS | Evidence-layer scope and no-advice boundary present. |
| References | `references/*.md` and relevant `adapter_notes/*.md` | PASS | Source types, registry, storage, candidates, gates, failures, Tushare and Baostock boundaries reviewed. |
| Scripts | `scripts/*.py` | PASS_WITH_FIX | Added CLI compatibility aliases for B1 plan commands without weakening validation rules. |
| Assets | `assets/*` | PASS | Example manifest/candidate/log/card assets present. |
| Debug cases | `assets/debug_cases/*` | PASS | All debug cases passed through runner. |

## Debug Cases

| Case | Expected | Result | Notes |
|---|---|---|---|
| manual_file_success | manifest PASS | PASS | Manifest validation succeeded. |
| local_dir_duplicate | duplicate hash detected | PASS | Duplicate fixture hashes matched. |
| structured_api_pull_snapshot | metric-only manifest/candidate PASS | PASS | Tushare-style structured snapshot remained metric-only. |
| d_source_clue_blocked | clue-only PASS | PASS | D-source candidate remained clue-only. |
| invalid_manifest_failure | validator fails as expected | PASS | Invalid status, D-source material claim, URL-in-local-path, missing path and future date were caught. |

## Validation Summary

| Gate | Result | Issues |
|---|---|---|
| Manifest gate | PASS | Existing `data/manifests/evidence_manifest.csv` now uses B1 columns and enums. |
| Path gate | PASS | Existing manifest local paths and source URLs validate. |
| Candidate gate | PASS | Existing `claims_draft.csv` and `metrics_draft.csv` now use B1 candidate schemas and guardrails. |
| No-advice gate | PASS | No B1 output created buy/sell/hold language, target-price calls or trading instructions. |
| Source registry gate | PASS_WITH_FIX | `config/source_registry.yaml` now preserves the old registry, adds the B1 `sources:` matrix, and includes current `policy_document` / `industry_report` entries. |

## Source Registry Reconciliation

`config/source_registry.yaml` was reconciled conservatively:

- Preserved the existing `source_types`, `rank_meaning`, `manifest_fields`, and `guardrails` sections.
- Added B1 `sources:` matrix entries for `cninfo`, `sse`, `szse`, `bse`, `tushare`, `baostock`, `brokerage_report`, and `news`.
- Added current-manifest source entries for `policy_document` and `industry_report`.
- Enforced B1 defaults:
  - official disclosure sources can support material claims only with archived/locatable evidence;
  - `tushare` is `metric_only`;
  - `baostock` is `metric_only`;
  - `brokerage_report` is analyst/estimate/context only;
  - `news` is clue-only and `material_claim_allowed: false`.

## Issues

| severity | issue | fix | blocking_for_stage |
|---|---|---|---|
| resolved | Existing `data/manifests/evidence_manifest.csv` used pre-B1 schema and was missing required B1 columns. | Migrated to B1 manifest schema with `raw_archive_policy`, `ingest_mode`, `material_claim_allowed`, `parse_status`, and `candidate_status`. | none |
| resolved | Existing D-level Tushare probe claim used `fact`. | Converted to clue-only diagnostic lineage and added `data/manifests/clue_log.csv`. | none |
| resolved | Existing Tushare structured data rows were fact-like claims. | Converted structured uses to `metric_statement` claim candidates and B1 metric candidates under `metric_only` boundaries. | none |
| resolved | Existing claim/metric drafts used pre-B1 column names. | Migrated to `claim_candidate_id` and `metric_candidate_id` schemas. | none |
| resolved | Official disclosure and industry/policy rows were evidence-card-only in the current repo. | Archived original raw PDFs/pages/snapshots and updated manifest raw paths, file hashes, archive policies, and material-use flags according to source type. | none |
| resolved | Legacy Tushare rows lacked original API params JSON/hash. | Backfilled API parameter JSON files from the live fetch/diagnostic scripts and stored `api_params_hash` in the manifest. | none |

## Files Changed In B1 Scope

| File | Change |
|---|---|
| `.agents/skills/evidence-ingest/scripts/validate_manifest.py` | Added `--manifest` option while preserving positional manifest argument. |
| `.agents/skills/evidence-ingest/scripts/validate_candidates.py` | Added plan-compatible `--repo`, `--claims`, and `--metrics` aliases. |
| `tests/test_phase_b1_evidence_ingest_contract.py` | Added coverage for the plan-compatible CLI forms. |
| `config/source_registry.yaml` | Added B1 `sources:` matrix without replacing legacy registry content. |
| `reports/p1_6/B1_EVIDENCE_INGEST_DEBUG_READOUT.md` | Filled this readout. |
| `.agents/skills/evidence-ingest/scripts/migrate_legacy_manifests_to_b1.py` | Added deterministic migration script for legacy manifest and draft candidate CSVs. |
| `data/manifests/evidence_manifest.csv` | Migrated to B1 manifest schema. |
| `data/manifests/claims_draft.csv` | Migrated to B1 claim candidate schema. |
| `data/manifests/metrics_draft.csv` | Migrated to B1 metric candidate schema. |
| `data/manifests/clue_log.csv` | Added D-source diagnostic clue row. |
| `config/research_config.yaml` | Updated manifest required fields and claim type config for B1 schema. |
| `tests/test_p0_acceptance.py` | Made evidence manifest header check order-independent. |
| `tests/test_p1_acceptance.py` | Accepted B1 claim types and metric candidate IDs. |
| `tests/test_p1_5_hardening.py` | Updated D-level evidence guardrail assertion for B1 enums. |

## Decision

- B1 status: `accepted`
- High severity issue count: 0
- Medium TODO count: 0
- Ready for B2: yes, subject to explicit user approval

Decision rationale:

B1 debug runner, manifest validator, path validator, candidate validator, B1 pytest, and full pytest all pass after the approved migration and 2026-07-02 evidence-chain hardening. The live evidence manifest and draft candidates now follow the B1 evidence-ingest contract. The two former evidence-hardening TODOs have been closed.

## Remaining TODO

- DONE `manifest_schema_migration_needed`: `data/manifests/evidence_manifest.csv` now validates under B1.
- DONE `candidate_schema_migration_needed`: `claims_draft.csv` and `metrics_draft.csv` now validate under B1 candidate schemas.
- DONE `structured_data_claim_type_review_needed`: Tushare structured data rows are metric-only metric candidates / metric statements, not business-exposure facts.
- DONE `d_source_probe_review_needed`: superseded Tushare probe is clue-only diagnostic lineage and is represented in `clue_log.csv`.
- DONE `raw_archive_hardening_needed`: original official/industry/policy raw PDFs/pages/snapshots are archived and manifest raw paths/file hashes are filled.
- DONE `api_params_hash_backfill_or_next_pull_needed`: existing Tushare snapshots have API params JSON files and `api_params_hash`; future structured API pulls should continue this contract.

## Post-B1 Evidence-Chain Hardening

- hardening_date: 2026-07-02
- `evidence_card_only` rows after hardening: 0
- structured Tushare/Baostock rows missing `api_params_hash` after hardening: 0
- raw archive files added:
  - `data/raw/regulator_policy/policy_miit_compute_infra_20231008_9f2a30.html`
  - `data/raw/industry_reports/industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91.pdf`
  - `data/raw/annual_reports/*.pdf`
- API parameter backfill files added:
  - `data/raw/market_data/api_params/*__api_params.json`
- metadata correction:
  - `annual_report_002837_invic_2025_0f8fcf` source changed from `sse` to `szse` because the archived source URL is `disc.static.szse.cn`.

## Not Started

- B2 segment-research
- B3 company-universe
- B4 segment-company-mapping
- B5 stock-deep-dive
- B6 quality-review
- B7 memo-writer
- B8 refresh-research
- Phase C/D/E/F debug and P2 readiness
