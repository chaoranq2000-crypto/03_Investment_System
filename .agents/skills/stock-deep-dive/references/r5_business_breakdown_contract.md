# R5 Business Breakdown Pack Contract

## 1. Purpose

`business_breakdown_pack` turns company operations into an auditable profit-pool structure. It is the core input for business narrative and later forecast assumptions.

## 2. Required fields per business line

```yaml
business_name: null
role: null
revenue:
  value: null
  unit: CNY_mn
  evidence_id: null
  missing_reason: TODO_SOURCE_REQUIRED
revenue_pct:
  value: null
  evidence_id: null
  missing_reason: TODO_SOURCE_REQUIRED
gross_margin:
  value: null
  evidence_id: null
  missing_reason: TODO_SOURCE_REQUIRED
gross_profit:
  value: null
  unit: CNY_mn
  evidence_id: null
  missing_reason: TODO_SOURCE_REQUIRED
gross_profit_pct:
  value: null
  evidence_id: null
  missing_reason: TODO_SOURCE_REQUIRED
products: []
customers: []
capacity: []
orders: []
pricing_driver: null
cost_driver: null
linked_segments: []
confidence: not_assessed
```

## 3. role enum

```text
core_cash_cow
core_growth_engine
cyclical_drag
option_business
strategic_transition
non_core
unknown
```

## 4. Missing-value discipline

If the company does not disclose segment revenue, set `revenue.value: null` and `missing_reason: MISSING_DISCLOSURE`. If only product lines are disclosed, keep revenue_pct and profit_pct missing. Do not reverse-engineer business-line revenue from company total revenue, industry space, or peer mix.

Customer, order, project, and capacity clues remain clue-level unless the source and review status support a stronger claim.

## 5. confidence enum

```text
high: official disclosure or reviewed structured metric.
medium: official wording with incomplete quantification, or cross-checked third-party data.
low: product/news/investor-interaction clue only.
not_assessed: not reviewed.
blocked: identity, metric, or source conflict.
```

## 6. profit_pool_summary

The summary should identify where profit comes from, whether revenue and gross profit are mismatched, which businesses drag margins, which businesses are options without profit contribution, and what disclosure is most needed next.

## 7. Report readiness

A strong business section requires business-line revenue or explicit gaps, at least two of revenue_pct/gross_margin/gross_profit contribution or explicit reasons, source IDs or missing reasons for product/customer/capacity/order fields, and visible structural contradictions.
