# R5 Bundle 8R.5 — Capital, event, news and independent fallbacks

## Scope
Implement holder count, lockup, dividend, margin, block trade, stock news, CLS telegraph and official exchange fallbacks. Lower-priority flow and ranking signals remain clue-only.

## Acceptance
- Future lockup/dividend dates enter an event calendar with source dates.
- News is deduplicated and never promoted directly to material fact.
- At least one forced primary-source failure demonstrates a different-domain fallback.
- 403/401/404 are not immediately retried.
