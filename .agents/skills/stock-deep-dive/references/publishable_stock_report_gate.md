# Publishable Stock Report Gate

## Purpose

This gate separates an internal bridge/readiness draft from a publishable stock deep dive.

It is a quality boundary for R4 stock reports. It does not create evidence, promote metrics, or relax the no-advice boundary.

## Required Inputs

```text
stock_report_draft
financial_metric_pack.csv
official_financial_reconciliation.csv
business_segment_metric_pack.csv
valuation_snapshot.yaml
technical_snapshot.yaml
peer_market_snapshot.csv
catalyst_calendar.yaml
risk_counter_evidence.yaml or equivalent
source_gap_report.md
quality_gate_report.md
```

## Required Conditions

1. Official financial reconciliation is at least partial and every core metric has either official evidence or explicit `official_missing`.
2. Company-level structured metrics remain metric-only until quality review promotes them.
3. Business segment metric pack exists.
4. Missing business segment disclosure is explicit as `MISSING_DISCLOSURE`.
5. Valuation context has source evidence or metric candidate linkage.
6. Peer context has `peer_market_snapshot.csv` or explicit `TODO_PEER_DATA`.
7. Technical snapshot is market-state observation only.
8. Risk and counter-evidence pack exists.
9. Source gaps are visible in the report body or linked source-gap report.
10. No-advice gate passes.

## Non-publishable Conditions

The report must not be marked `publishable_ready` when any of these are true:

1. Company-level financial metrics are unreconciled.
2. Segment disclosure is missing but the report writes deterministic segment revenue or profit contribution.
3. Valuation context lacks source evidence or metric candidate linkage.
4. Peer table is only TODOs but written as a ranking conclusion.
5. Source gaps are hidden.
6. Technical snapshot is framed as an operation signal.
7. Tushare or Baostock data is used as business exposure fact.
8. Management statements, analyst views or news clues are written as verified facts.
9. No-advice gate fails.

## Output Status

| status | meaning |
|---|---|
| `publishable_ready` | All core financial, business segment, valuation, risk and source-gap conditions pass. |
| `publishable_ready_with_disclosure_todos` | Internal research draft can circulate with explicit disclosure gaps; source gaps stay visible. |
| `bridge_only` | Useful bridge/readiness draft, but not a publishable stock deep dive. |
| `blocked` | High issue, evidence break, hidden source gap or no-advice violation exists. |

## Review Rules

- `official_missing` is allowed only when visible and not treated as matched.
- `mismatch` rows require quality-review before promotion.
- Product-line clues may support product exposure only after review; they do not generate revenue_pct or profit_pct.
- Market, valuation, technical and peer context cannot prove business exposure.
- The gate must be run again after every R4 draft regeneration.
