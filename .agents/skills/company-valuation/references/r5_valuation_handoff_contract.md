# R5 Valuation Handoff Contract

## Purpose

`R5_valuation_handoff` is the controlled handoff from `company-valuation` into `stock-deep-dive` R5 `valuation_pack`. It prevents writers from inventing valuation numbers and preserves no-advice / source-gap boundaries.

## Required Fields

```yaml
artifact_type: R5_valuation_handoff
valuation_as_of_date:
market_snapshot:
peer_context:
method_used:
scenario_values:
assumptions:
sensitivity:
source_evidence_ids:
missing_items:
no_advice_statement:
```

## Rules

- `market_snapshot.current_price`, `market_snapshot.market_cap`, and `market_snapshot.share_count` are required for an R5 valuation gate.
- Missing peer context must downgrade the valuation handoff.
- Scenario values may include target-price-style scenario outputs only as valuation scenarios, never as action recommendations.
- Every valuation number must carry at least one of `source_evidence_id`, `evidence_id`, `assumption_id`, `metric_id`, or `missing_reason`.
- Direct trading-action language is forbidden in the handoff.

## Boundary

This contract does not compute live valuation. It only validates that reviewed valuation outputs are safe to hand off into an R5 pack.
