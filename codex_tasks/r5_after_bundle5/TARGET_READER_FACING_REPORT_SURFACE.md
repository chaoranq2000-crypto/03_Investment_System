# Target reader-facing report surface

This document defines presentation architecture only. It does not authorize any factual content.

## File separation

### Main report

`R5_stock_research_report_reader_v2.md`

Contains only reader-facing research analysis, concise source notes and disclosure boundaries.

### Traceability appendix

`R5_stock_research_report_traceability_v2.yaml`

Contains claim IDs, evidence IDs, source paths, methods, reviewer states, gap tokens and audit metadata.

The main report may reference stable display anchors such as `[E1]`, `[E2]`, but must not reveal raw internal identifiers or paths.

## Main report structure

### Title block

- company name and code;
- research cutoff date;
- report level: `reader-facing research candidate`;
- one-line no-advice boundary in natural language;
- no workflow metadata.

### 1. Core research view

Three to five concise findings covering:

- what is changing;
- what drives earnings;
- where the market debate sits;
- what evidence would confirm or disconfirm the thesis;
- the most important uncertainty.

### 2. Company context and research boundary

Explain the company, reported business structure and the distinction between broad temperature-control categories and liquid-cooling-specific disclosure.

### 3. Financial history and quality

At minimum:

- 2023A-2025A plus latest quarter;
- revenue, net profit, gross margin where available, operating cash flow;
- YoY/CAGR and net-margin/cash-conversion calculations;
- causal interpretation;
- latest-quarter divergence;
- a short quality judgment.

### 4. Business breakdown and economics

For each disclosed broad product line:

- revenue and share;
- gross margin;
- role in the portfolio;
- growth or margin driver;
- known limitation;
- watchpoint.

Undisclosed liquid-cooling economics must be described as a disclosure boundary, not shown as a raw `MISSING_DISCLOSURE` row.

### 5. Industry structure and competition

Use reviewed evidence to cover only decision-relevant issues:

- demand driver;
- supply structure;
- value-chain position;
- key competitors and business-mix differences;
- company advantage and disadvantage;
- observable industry variables.

Avoid generic market-size filler.

### 6. Forecast and scenarios

Present:

- historical-to-forecast bridge;
- explicit model drivers;
- 2026E-2028E base case;
- bull/bear or sensitivity table;
- which variable matters most;
- why latest-quarter weakness does or does not persist;
- model limitations.

### 7. Valuation and market expectations

Present:

- valuation date and share price;
- relevant trailing and forward multiples;
- peer-selection rationale;
- business-mix differences;
- scenario valuation context without target-price instructions;
- market-implied expectations;
- ineligible-method explanation when DCF/SOTP inputs are not reviewed.

### 8. Dated market state and events

When reviewed data exists:

- price trend and volatility using a clearly dated series;
- company announcements and scheduled verification points;
- no unsupported technical pattern claims;
- no social-media sentiment filler.

### 9. Risks, counter-evidence and disconfirming conditions

Tie each risk to the thesis. Include:

- operating risk;
- disclosure risk;
- model risk;
- valuation risk;
- evidence that would invalidate the current interpretation.

### 10. Research conclusion and watchlist

Conclude with:

- present research state;
- what is supported;
- what remains uncertain;
- three to six measurable watch conditions;
- no rating, target price, position size or timing instruction.

## Reader-surface hygiene

The main report must not contain:

```text
claim_id
evidence_ids
readiness:
visible_gap:
TODO_*
MISSING_*
LOW_CONFIDENCE_*
UNREVIEWED_*
reports/workflow_runs/
data/reviewed_inputs/
CNY_per_share
multiple_TTM
direct_reported_value
```

These belong in the traceability appendix.
