# R5 Bundle 5.2 — Official disclosure and financial-history onboarding

## Background

Financial history and business breakdown must be grounded in official company/exchange disclosures before forecasts and valuation assumptions are accepted.

## Goal

Onboard reviewed `business_disclosure` inputs for 002837, link them to immutable official evidence, and rebuild the financial-history and business-breakdown subpacks without registry promotion.

## Allowed source classes

Prefer source-rank A official materials already archived or newly archived under repository rules, including annual/interim/quarterly reports and exchange/company announcements. External analyst prose may be retained as a lower-rank clue but cannot replace official evidence for reported figures.

## Allowed files

- official raw/processed evidence paths defined by `AGENTS.md`
- evidence/claim/metric manifests
- `data/reviewed_inputs/wf_20260703_stock_first_002837_invic/business_disclosure/**`
- staging-only outputs for the real workflow
- existing financial-history/business-breakdown subpack inputs and generated candidate outputs
- focused validators/tests
- `reports/p1_6/R5_BUNDLE_5_2_OFFICIAL_DISCLOSURE_FINANCIAL_READOUT.md`

## Forbidden scope

- Do not overwrite raw files.
- Do not infer segment revenue, margin, capacity or customer exposure where disclosures are absent.
- Do not mark a candidate accepted without real reviewer metadata.
- Do not promote canonical registries in this card.
- Do not convert management guidance into reported fact.

## Required work

1. Register official disclosure evidence with publication date, reporting period, units and source path.
2. Populate reviewed business-disclosure records from the repository template.
3. Separate `fact`, `management_comment`, `estimate`, `inference` and `unknown`.
4. Reconcile reported totals to segment/metric rows; record residuals and accounting-scope changes.
5. Generate candidate financial-history and business-breakdown subpacks.
6. Validate all metrics for period, unit, currency, source and method.
7. Record conflicts between different filings rather than selecting silently.

## Acceptance gate

- At least one current official disclosure chain is accepted with valid reviewer metadata.
- Required historical periods for the existing core-subpack contract are either evidenced or explicitly missing.
- Candidate subpacks validate at the report level allowed by current gates.
- No canonical registry is changed.

## Suggested commands

```bash
python scripts/validate_r5_reviewed_input_dropzone.py   --root data/reviewed_inputs/wf_20260703_stock_first_002837_invic/business_disclosure   --json reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_business_disclosure_validation.json
python scripts/run_r5_core_asset_preflight.py --repo-root . --workflow-id wf_20260703_stock_first_002837_invic --json reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle5_core_preflight_after_disclosure.yaml
python -m pytest -q tests/test_r5_bundle5_official_disclosure_onboarding.py tests/test_r5_financial_history_subpack.py tests/test_r5_business_breakdown_subpack.py --tb=short -p no:cacheprovider
git diff --check
```

Inspect actual script `--help` output before execution and use the repository's existing CLI flags if they differ; do not add duplicate wrappers merely to match this card's example.
