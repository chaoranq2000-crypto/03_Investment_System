# Segment Exposure Schema

## Purpose

`segment_exposure.yaml` is the stock-to-segment handoff artifact consumed by `segment-company-mapping`. It records one company's exposure to one or more segments without turning clues into unsupported business facts.

## Required top-level identity

At least these fields must be present:

```yaml
company_id: company_example_000000_sz
stock_code: "000000"
company_name: 示例公司
```

Equivalent identity may be carried under `company_identity`, but validators should prefer explicit top-level identity for handoffs.

## Exposure row shape

```yaml
exposures:
  - segment_id: segment_example
    segment_name: 示例细分
    exposure_type: product_line_clue
    exposure_score: 2
    confidence: low
    revenue_pct: MISSING_DISCLOSURE
    profit_pct: MISSING_DISCLOSURE
    evidence_ids:
      - ev_example_annual_report_2025
    claim_ids: []
    metric_ids: []
    missing_reason: MISSING_DISCLOSURE
    backflow_decision: no_backflow_needed
    next_action: keep TODO visible until official disclosure is available
```

## exposure_type enum

```text
revenue
profit
product_line_clue
customer_clue
order_clue
capacity_clue
technology_reserve
project_clue
narrative_only
```

## exposure_score guide

| score | Meaning |
|---:|---|
| 0 | Excluded or not material, with evidence or explicit reason. |
| 1 | Narrative or clue only. |
| 2 | Product, technology, customer, project, capacity or order clue with low confidence. |
| 3 | Confirmed product/project/customer exposure, revenue share may still be missing. |
| 4 | Meaningful business exposure supported by official evidence or reviewed claims. |
| 5 | High-purity or revenue-confirmed exposure with disclosed revenue/profit share. |

`narrative_only` exposure cannot score above 1.

`technology_reserve` exposure cannot score above 2 unless product, project, or customer support is explicit in `supporting_exposure_types`.

## Missing disclosure rules

`revenue_pct` and `profit_pct` must never be guessed. If unavailable, use one of:

```text
MISSING_DISCLOSURE
NOT_DISCLOSED
```

Blank strings and null values are invalid unless wrapped in an object with an explicit `missing_reason`.

## Support requirement

Each exposure row must carry at least one of:

```text
evidence_ids
claim_ids
metric_ids
missing_reason
TODO / todo
```

Unsupported exposure rows are not accepted as state updates.
