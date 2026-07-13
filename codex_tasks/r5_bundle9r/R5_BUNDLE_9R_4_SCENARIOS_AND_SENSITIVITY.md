# 9R.4 — Scenarios and sensitivity

## Goal

Create bear/base/bull scenarios whose differences are attributable to named business drivers.

## Required work

- Use the same model structure for all scenarios.
- Enforce `bear <= base <= bull` for revenue, attributable profit and scenario equity value by period.
- Produce one-way sensitivities for the most material variables, including room-cooling growth, gross margin, expense ratios and cash conversion.
- Add a two-way sensitivity for the two variables with the largest profit impact.
- Explain differences versus the external EPS distribution rather than fitting the model to consensus.

## Outputs

`R5_bundle9r_scenario_pack.yaml` and `R5_bundle9r_sensitivity.csv`.
