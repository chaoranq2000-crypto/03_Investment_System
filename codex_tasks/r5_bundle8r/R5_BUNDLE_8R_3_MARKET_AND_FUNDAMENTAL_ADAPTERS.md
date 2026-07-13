# R5 Bundle 8R.3 — Market and fundamental adapters

## Scope
Implement independently authored adapters for mootdx bars/F10/finance, Tencent quote/valuation, Baidu K-line fallback, Sina statements and Eastmoney stock information.

## Guardrails
- Preserve upstream warnings about unadjusted mootdx prices and field drift.
- Use source-specific rate policies.
- Archive raw responses before normalization.
- Market/structured data remains metric-only.

## Acceptance
Each adopted core adapter passes fixture, live smoke, raw/manifest, schema-drift and independent-fallback tests for 002837 and one cross-exchange fixture.
