# Stock Evidence Plan Contract

## Purpose

A stock evidence plan is the handoff between `research-orchestrator`, `evidence-ingest`, and `stock-deep-dive` for `stock_first_closed_loop`.

It answers:

1. What evidence is needed before a stock report can be drafted?
2. Which evidence can support business exposure?
3. Which data is metric-only?
4. Which gaps must remain TODO/MISSING?

## Required fields

```yaml
workflow_id:
stock_code:
ts_code:
company_id:
company_name:
exchange:
date_range:
  start:
  end:
as_of_date:
required_evidence:
  official_filings: []
  structured_financial_data: []
  optional_context: []
rules: {}
expected_outputs: {}
```

## Evidence priority

1. Annual report, interim report, quarterly report and announcements from official disclosure channels.
2. Exchange/regulator materials and inquiry replies.
3. Structured data snapshots for metrics only.
4. Investor relations, company website and product pages as management/company context.
5. News, social media, hot lists and concept pages as clues only.

## Guardrails

- Annual report or official disclosure is required before claiming revenue, product, customer, order or project exposure as fact.
- Structured data snapshots can support metrics such as revenue, margin, cash flow, assets and liabilities, but cannot prove segment exposure alone.
- News/social clues must generate TODOs, not material claims.
- Missing annual report, missing order details, missing customer evidence, and missing revenue share must remain explicit TODO/MISSING.

## Completion criteria

A stock evidence package is minimally usable when:

```text
- evidence_manifest has rows for required evidence or explicit TODO rows/notes;
- structured financial data generated metric_candidates or explicit adapter TODOs;
- official filing evidence has source_url or raw_file_path;
- raw_file_path and source_url are separated;
- stock-deep-dive can consume evidence_snapshot without fetching data itself.
```
