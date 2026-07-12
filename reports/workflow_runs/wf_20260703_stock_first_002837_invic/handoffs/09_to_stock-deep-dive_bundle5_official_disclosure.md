# Handoff: T1 Company Evidence -> stock-deep-dive

## Workflow

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| current_stage | `R5 Bundle 5.2 official disclosure onboarding` |
| target_skill | `stock-deep-dive` |
| reviewer | `codex` |
| authorization_source | `workspace_user: 授权, 2026-07-12` |

## Objective

Review the newly archived official filings, create evidence-anchored accepted `business_disclosure` records, and build candidate financial-history and business-breakdown subpacks without touching canonical registries.

## Inputs

| evidence_id | physical source | use |
|---|---|---|
| `ev_annual_report_002837_20260421_2cbfc5` | `data/raw/annual_reports/cninfo_2025_annual_report_full_002837_2026-04-21.pdf` | 2023-2025 financial history and 2025/2024 broad business lines |
| `ev_interim_report_002837_20250819_47054e` | `data/raw/announcements/cninfo_2025_interim_report_full_002837_2025-08-19.pdf` | interim cross-check |
| `ev_quarterly_report_002837_20260421_2f00c7` | `data/raw/announcements/szse_2026_q1_report_002837_2026-04-21.pdf` | latest quarterly company totals |

## Required Boundaries

- Label reported facts, arithmetic derivations, management comments, estimates, and unknowns separately.
- Reconcile disclosed product-line revenue to company revenue and record any residual.
- Keep liquid-cooling revenue share, gross margin, and profit contribution as `MISSING_DISCLOSURE`.
- Do not map all room/cabinet cooling revenue to liquid cooling.
- Every numeric value must include period, unit, currency where applicable, source evidence ID, and calculation method.
- `reviewer: codex` is permitted only for rows actually checked in this run.
- No canonical registry writes, sample-quality publication, P2 work, or trading advice.

## Expected Outputs

- accepted records under `data/reviewed_inputs/wf_20260703_stock_first_002837_invic/business_disclosure/`
- candidate financial-history and business-breakdown packs under the workflow run
- `R5_bundle5_business_disclosure_validation.json`
- `R5_bundle5_core_preflight_after_disclosure.yaml`
- `tests/test_r5_bundle5_official_disclosure_onboarding.py`
- `reports/p1_6/R5_BUNDLE_5_2_OFFICIAL_DISCLOSURE_FINANCIAL_READOUT.md`
