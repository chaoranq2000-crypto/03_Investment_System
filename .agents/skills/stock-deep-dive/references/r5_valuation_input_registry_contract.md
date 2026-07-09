# R5 Valuation Input Registry Contract

Valuation outputs require a registry that binds reviewed market snapshot, reviewed peer snapshot, forecast outputs, and method-level limitations.

## Required References

- reviewed market snapshot path and evidence IDs
- reviewed peer snapshot path and evidence IDs
- forecast model path and assumption IDs
- valuation method eligibility

Relative PE/PB/PS can become eligible only when both market and peer inputs are reviewed. SOTP can become eligible only when business-line split is reviewed or explicitly scoped. DCF can become eligible only when reviewed cashflow assumptions exist.

If any required input remains TODO, the registry must return `source_gapped_research_draft` or `blocked_for_sample_quality`.
