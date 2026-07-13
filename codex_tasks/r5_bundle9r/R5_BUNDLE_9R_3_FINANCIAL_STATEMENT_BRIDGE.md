# 9R.3 — Financial-statement bridge

## Goal

Build a complete, explicit bridge from segment gross profit to attributable profit and cash flow.

## Required lines

Revenue, gross profit, tax surcharge, selling expense, administrative expense, R&D expense, financial expense, operating profit, non-operating net, pretax profit, income tax, minority interest, nonrecurring items, attributable net profit, EPS, operating cash flow, capex and free cash flow.

## Prohibited shortcuts

- `implied_tax_finance_other_and_minority`;
- `other_operating_drag`;
- unexplained residual or balancing plug;
- a single aggregate expense rate standing in for all operating expenses.

## Acceptance

- Segment revenue and gross profit reconcile to the company bridge within the configured tolerance.
- All arithmetic is deterministic and independently recalculated in tests.
- Working-capital and capex assumptions are visible rather than hidden in a cash-flow residual.
