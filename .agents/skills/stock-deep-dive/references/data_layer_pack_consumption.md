# Data Layer Pack Consumption

## Purpose

This reference tells `stock-deep-dive` how to consume data-layer packs produced by `evidence-ingest`.

Data-layer packs are inputs, not conclusions. They can support metric context and missing-data handling, but they cannot replace official disclosure for company business facts.

## Required Gate

Before using any pack, check:

```text
data_layer_quality_report.md exists
high_issues: 0
```

If the gate is missing or has high issues, downstream sections must use TODO/MISSING labels rather than inferred conclusions.

## Pack Rules

| pack | allowed use | if missing |
|---|---|---|
| `financial_metric_pack.csv` | financial metric table and financial quality inputs | `TODO_STRUCTURED_FINANCIAL_DATA` |
| `valuation_snapshot.yaml` | market valuation context and scenario inputs | `TODO_MARKET_DATA` |
| `technical_snapshot.yaml` | market-state observation only | `TODO_MARKET_DATA` |
| `market_sentiment_pack.yaml` | clue-only context | `LOW_CONFIDENCE_CLUE_ONLY` |
| `business_segment_metric_pack.csv` | business-composition metric candidates | `MISSING_DISCLOSURE` unless official filing supports the fact |
| `peer_market_snapshot.csv` | peer valuation comparison | `TODO_PEER_DATA` |
| `source_gap_report.md` | visible gap list | create/update TODOs |

## Boundaries

- Structured financial and market snapshots are metric-only.
- Tushare/Baostock data cannot prove customer orders, business exposure, capacity status or segment revenue.
- Fina_mainbz can create business-segment metric candidates, but official filing evidence is still required before writing a business exposure fact.
- Technical snapshot fields must not be phrased as trading instructions.
- Sentiment, hotlist and news packs stay clue-only unless later verified by stronger evidence.

## Handoff Fields

When passing packs into `stock_analysis_pack.yaml`, preserve:

```yaml
source_evidence_id:
api_params_hash:
as_of_date:
missing_fields:
quality_gate_status:
limitations:
```

## Quality Handoff

Send the following to `quality-review`:

```text
data_layer_quality_report.md
source_gap_report.md
valuation_snapshot.yaml
technical_snapshot.yaml
financial_metric_pack.csv
peer_market_snapshot.csv if used
```

The review must fail if a missing pack is silently replaced by an unsupported conclusion.
