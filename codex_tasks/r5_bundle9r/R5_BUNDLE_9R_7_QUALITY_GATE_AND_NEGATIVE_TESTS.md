# 9R.7 — Quality gate and negative tests

## Goal

Make core forecast or valuation failures non-compensable.

## Required negative tests

The gate must reject:

- stale or missing evidence-generation ID;
- changed Bundle 8R locked-input hash;
- liquid-cooling estimate presented as issuer fact;
- double counting of analytical liquid cooling inside disclosed revenue;
- missing segment or bridge line;
- unexplained residual/plug;
- segment-to-company arithmetic mismatch;
- bear/base/bull monotonicity failure;
- market cap inconsistent with price × shares;
- low-confidence peer ranking enabled;
- missing reverse or scenario valuation;
- consensus mislabeled as fact;
- direct action language.

## Acceptance

All mutation/negative fixtures fail for the intended reason, while one fully traced fixture passes.
