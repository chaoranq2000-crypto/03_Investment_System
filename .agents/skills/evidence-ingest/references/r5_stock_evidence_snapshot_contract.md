# R5 Stock Evidence Snapshot Contract

## Purpose

The R5 stock evidence snapshot plan tells `evidence-ingest` what to register before `stock-deep-dive` builds `R5_stock_research_pack.yaml`.

It is a plan and handoff contract. It does not download evidence by itself, does not call live APIs, and does not create research conclusions.

## Required evidence families

| Family | Required coverage | Allowed use |
|---|---|---|
| `official_filings` | recent 3 annual reports, latest interim/quarterly report, major announcements and inquiry replies for the last 12-18 months | fact support, business exposure, risk, financial notes |
| `structured_financial_metrics` | income statement, balance sheet, cash flow, financial indicators | reviewed metrics only |
| `market_snapshot` | price, market cap, share count, multiples with `as_of_date` | valuation and technical context only |
| `peer_snapshot` | peer set, financial/valuation snapshots with `as_of_date` | peer context only |
| `industry_context_clues` | price, supply-demand, policy, cycle, technology clues | context or TODO, not company proof |
| `news_event_clues` | news, social, event clues | clue/TODO only |
| `investor_relations` | IR records, company website/product pages | management_comment/company context |

## Required fields per evidence request

```yaml
request_id:
evidence_need:
source_type:
source_rank: A | B | C | D | unknown
as_of_date:
freshness_policy:
allowed_usage: []
required_for_pack: []
status: planned | collected | TODO | MISSING | not_applicable
evidence_id:
missing_reason:
```

If `status` is `collected`, `evidence_id` or `source_path` is required. If evidence is not yet collected, `missing_reason` or `next_action` must stay visible.

## Source-rank usage boundary

- A/B official disclosures can support material facts after review.
- Structured financial/market data is metric-only unless reconciled with official disclosure.
- Market snapshot, peer snapshot, industry clues, news, and investor-relations material cannot independently prove business exposure, business-line revenue, customer contribution, capacity, or profit contribution.
- D-level sources can only create clues, TODOs, or search tasks.

## Handoff to stock-deep-dive

The plan must expose these R5 handoff fields:

```yaml
handoff_to_stock_deep_dive:
  evidence_manifest_path:
  claim_candidates_path:
  metric_candidates_path:
  source_gap_register_path:
  evidence_counts:
  official_filing_requests:
  structured_metric_requests:
  market_snapshot_requests:
  peer_snapshot_requests:
  context_clue_requests:
  missing_inputs:
```

`stock-deep-dive` may consume the handoff but must not fetch sources itself.

