# B1 Evidence-Ingest Debug Readout

## Metadata

- phase: P1.6 Phase B1
- skill: evidence-ingest
- run_date: 2026-07-02 15:38:31 +08:00
- operator: Codex
- repo_commit: 3359b758abdbb923ddec0d8f9d65964225757d30
- branch: codex/p1-6-b1-evidence-ingest-verify

## Scope

This readout validates the evidence-ingest contract. It does not create research conclusions, scorecards, watchlist decisions or trading advice.

B1-only boundary observed:

- Did not use `codex_prompts/P1_6_DETAILED_PLAN_FOR_CODEX.md`.
- Did not start B2 or later phases.
- Did not modify non-B1 skill directories.
- Did not bulk-migrate existing `data/manifests/*` files.

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
| Manifest gate | PASS for B1 fixtures; BLOCKED for existing repo manifest | Existing `data/manifests/evidence_manifest.csv` lacks B1 columns: `candidate_status`, `ingest_mode`, `material_claim_allowed`, `parse_status`, `raw_archive_policy`. |
| Path gate | PASS for B1 debug fixtures | Existing manifest path gate was not fully evaluated because schema validation stops at missing required columns. |
| Candidate gate | PASS for B1 examples and debug fixtures; BLOCKED for existing drafts | Existing `claims_draft.csv` has a D-level Tushare probe evidence row generating a `fact` claim, and C-level structured data rows generating `fact` claims. |
| No-advice gate | PASS | No B1 output created buy/sell/hold language, target-price calls or trading instructions. |
| Source registry gate | PASS_WITH_FIX | `config/source_registry.yaml` now preserves the old registry and adds the B1 `sources:` matrix. |

## Source Registry Reconciliation

`config/source_registry.yaml` was reconciled conservatively:

- Preserved the existing `source_types`, `rank_meaning`, `manifest_fields`, and `guardrails` sections.
- Added B1 `sources:` matrix entries for `cninfo`, `sse`, `szse`, `bse`, `tushare`, `baostock`, `brokerage_report`, and `news`.
- Enforced B1 defaults:
  - official disclosure sources can support material claims only with archived/locatable evidence;
  - `tushare` is `metric_only`;
  - `baostock` is `metric_only`;
  - `brokerage_report` is analyst/estimate/context only;
  - `news` is clue-only and `material_claim_allowed: false`.

## Issues

| severity | issue | fix | blocking_for_stage |
|---|---|---|---|
| critical | Existing `data/manifests/evidence_manifest.csv` uses pre-B1 schema and is missing required B1 columns. | Create a separately approved manifest schema migration plan; do not bulk-migrate inside B1 verification. | B1 acceptance / B2 start |
| high | Existing `claims_draft.csv` row 14 uses D-level `market_data_tushare_probe_20260701_8bbf20` evidence for a `fact` claim. | During migration, convert to clue/TODO or mark as failed/superseded diagnostic metadata; do not promote as material claim. | B1 acceptance / B2 start |
| medium | Existing `claims_draft.csv` rows 15-23 use C-level structured data rows as `fact` claims. | During migration, convert structured data rows to metric candidates or metric statements under `metric_only` rules. | B1 acceptance / B2 start |
| medium | Existing `claims_draft.csv` and `metrics_draft.csv` use pre-B1 column names (`claim_id`, `metric_id`) rather than B1 candidate schemas. | Add draft schema migration TODO and map old IDs to B1 `claim_candidate_id` / `metric_candidate_id` fields. | B1 acceptance / B2 start |

## Files Changed In B1 Scope

| File | Change |
|---|---|
| `.agents/skills/evidence-ingest/scripts/validate_manifest.py` | Added `--manifest` option while preserving positional manifest argument. |
| `.agents/skills/evidence-ingest/scripts/validate_candidates.py` | Added plan-compatible `--repo`, `--claims`, and `--metrics` aliases. |
| `tests/test_phase_b1_evidence_ingest_contract.py` | Added coverage for the plan-compatible CLI forms. |
| `config/source_registry.yaml` | Added B1 `sources:` matrix without replacing legacy registry content. |
| `reports/p1_6/B1_EVIDENCE_INGEST_DEBUG_READOUT.md` | Filled this readout. |

## Decision

- B1 status: `blocked`
- High severity issue count: 1 critical + 1 high existing-data issue
- Medium TODO count: 2 migration workstreams, including 9 C-level structured-data claim rows
- Ready for B2: no

Decision rationale:

B1 debug runner and pytest pass, and B1-local script compatibility issues were repaired. However, the existing repo manifest/draft files require a broader schema and claim-type migration before the B1 evidence-ingest contract can be safely treated as accepted for the live evidence base. The B1 plan explicitly says not to perform a risky bulk migration without separate approval.

## Remaining TODO

- `manifest_schema_migration_needed`: migrate `data/manifests/evidence_manifest.csv` to B1 columns and enums, including `raw_archive_policy`, `ingest_mode`, `material_claim_allowed`, `parse_status`, and `candidate_status`.
- `candidate_schema_migration_needed`: migrate `claims_draft.csv` and `metrics_draft.csv` to B1 candidate schemas.
- `structured_data_claim_type_review_needed`: convert Tushare/Baostock structured data uses to `metric_only` metric candidates or metric statements; do not use them for business-exposure facts.
- `d_source_probe_review_needed`: convert the superseded Tushare probe failure row from fact-like claim usage into diagnostic metadata, clue/TODO, or failed/superseded evidence handling.

## Not Started

- B2 segment-research
- B3 company-universe
- B4 segment-company-mapping
- B5 stock-deep-dive
- B6 quality-review
- B7 memo-writer
- B8 refresh-research
- Phase C/D/E/F debug and P2 readiness
