# 9R.1 — Input review and promotion

## Goal

Create a reviewed input ledger from the Bundle 8R evidence generation before calculating any forecast.

## Required classifications

- issuer/exchange facts;
- reviewed structured metrics;
- management comments;
- analyst estimates and consensus distributions;
- analytical inferences;
- issuer nondisclosures and unknowns.

## Required work

- Reconcile the 2025 annual base and 2026Q1 anchors to official figures.
- Review each forecast driver and record evidence IDs, metric IDs, claim type, confidence, falsification condition and reviewer decision.
- Keep THS/Eastmoney forecasts as `analyst_view`/`estimate`, never issuer guidance.
- Carry forward the liquid-cooling disclosure gaps from `R5_failed_missing_disclosure_register.yaml`.
- Reject draft metrics that lack an allowed usage or review decision.

## Output

`R5_bundle9r_input_review_ledger.yaml`.
