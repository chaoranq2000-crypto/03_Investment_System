# Handoff: T4 Modeling -> company-valuation

## Invocation Boundary

`company-valuation` is invoked only as a sub-skill of `stock-deep-dive` for Bundle 5.4 method eligibility and valuation-context review.

| field | value |
|---|---|
| workflow_id | `wf_20260703_stock_first_002837_invic` |
| stock_code | `002837` |
| valuation_date | `2026-07-10` |
| reviewer | `codex` |
| quality_target | `reviewed_input_research_draft` |
| no_advice_boundary | `true` |

## Reviewed Inputs

- Official financial history: `R5_bundle5_financial_history_candidate.yaml`.
- Broad business breakdown: `R5_bundle5_business_breakdown_candidate.yaml`.
- Market input: `r5_b5_market_002837_20260710`.
- Peer set: `301018` and `300499`, same-date trailing multiples, explicitly low confidence.
- Latest share count: `1,274,349,692` shares.
- 2026Q1 net-debt bridge components: cash `917,139,183.43 CNY`; short-term debt `939,000,000.00`; current non-current liabilities `246,338,651.34`; long-term debt `351,026,719.14`; lease liabilities `78,909,142.62`; derived net debt `698,135,329.67 CNY`.

## Forecast Method

- 2026 revenue growth: carry the reported 2026Q1 year-on-year rate through the year as a transparent model assumption.
- 2026 net profit: apply the 2025 Q1/full-year seasonal share to reported 2026Q1 attributable profit.
- 2027-2028: explicit analyst/model assumptions with slowing revenue growth and partial margin normalization; sensitivity ranges must remain visible.
- All outputs are `estimate` or `inference`, never reported facts or management guidance.

## Method Eligibility

- `relative_pe`: eligible only as low-confidence context because there are two peers and business mixes differ.
- `dcf`: excluded because tax, capex, working-capital, discount-rate and terminal assumptions are not sufficiently reviewed.
- `sotp`: excluded because liquid-cooling-specific revenue and profit splits are not disclosed.

## Prohibited Output

No price target, rating, position instruction, expected return, certainty statement, sample-quality gate, P2 gate, or registry promotion.
