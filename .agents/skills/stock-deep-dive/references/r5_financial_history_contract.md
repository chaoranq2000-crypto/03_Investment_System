# R5 Financial History Pack Contract

## 1. Purpose

`financial_history_pack` is the factual source for the R5 “财务概览” section. It is not a generic financial summary.

It must help answer:

```text
Where did revenue growth come from?
Is profit growth operating growth or one-off items?
Did gross margin change because of mix, price, cost, or accounting effects?
Does operating cash flow match reported profit?
Do receivables, inventories, or contract liabilities support the business trend?
Is ROE/ROIC improvement real or distorted by leverage, one-offs, or cycle pricing?
```

## 2. Required shape

```yaml
financial_history_pack:
  status: TODO | partial | ready | blocked
  currency: CNY
  periods: []
  income_statement: []
  balance_sheet: []
  cashflow_statement: []
  key_metrics: []
  financial_quality:
    revenue_growth_driver: null
    gross_margin_driver: null
    adjusted_profit_bridge: null
    cashflow_quality: null
    working_capital_flags: []
    roe_roic_commentary: null
  evidence_ids: []
  missing_items: []
```

## 3. Metric rules

Every metric must include `metric_name`, `period`, `value`, `unit`, `source_type`, `source_path` or `evidence_id`, `calculation_method` if derived, and `confidence`.

If a value is missing, keep `value: null` and add `missing_reason: TODO_SOURCE_REQUIRED | MISSING_DISCLOSURE | NOT_APPLICABLE`.

## 4. Allowed observations

Allowed outputs include profit-quality observation, cash-flow matching observation, working-capital pressure observation, margin-driver observation, and non-recurring-item observation.

Forbidden outputs include unsupported profit-quality conclusions, replacing annual trends with single-quarter data without disclosure, promoting management outlook to fact, or hiding impairments, investment income, fair-value changes, or other non-recurring items.

## 5. Report readiness

A strong financial overview requires at least three annual periods or explicit gaps, latest interim/quarterly data or explicit gaps, triangulation across profit/cash flow/balance sheet, explicit treatment of abnormal items, and traceable evidence or metric IDs.
