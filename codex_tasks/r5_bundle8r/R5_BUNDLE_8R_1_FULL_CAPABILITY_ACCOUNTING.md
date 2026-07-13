# R5 Bundle 8R.1 — Full 43-capability accounting

## Goal
Review all forty primary groups and three fallback groups from a-stock-data V3.4.0. Every row must have an adoption decision, claim boundary, priority, current status, target adapter and close requirement.

## Acceptance
- 43 unique capability IDs: 40 primary + 3 fallback.
- No blank adoption decision or claim boundary.
- Trading/option functions are explicitly out of scope rather than silently omitted.
- All `adopt_core` rows have an owner and target adapter.
