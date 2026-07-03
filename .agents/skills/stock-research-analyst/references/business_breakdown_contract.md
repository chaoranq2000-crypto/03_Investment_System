# Business Breakdown Contract

## 1. Purpose

Business breakdown is the core bridge between company evidence and segment exposure.

## 2. Required fields per business line

```yaml
business_line:
  business_line_id:
  name:
  description:
  revenue:
    value:
    unit:
    period:
    metric_id:
    disclosure_status: disclosed | estimated | missing
  revenue_pct:
    value:
    metric_id:
    disclosure_status:
  gross_margin:
    value:
    metric_id:
    disclosure_status:
  gross_profit:
    value:
    calculation_method:
    supporting_metric_ids: []
  growth_driver:
    text:
    supporting_claim_ids: []
  products:
    - name:
      claim_ids: []
  customers:
    - name_or_type:
      claim_ids: []
      confidentiality_note:
  capacity_or_projects:
    - name:
      status:
      claim_ids: []
  linked_segments:
    - segment_id:
      exposure_type:
      exposure_score:
      confidence:
      supporting_claim_ids: []
      gaps: []
  risks:
    - risk_text:
      supporting_claim_ids: []
```

## 3. Exposure type enum

```yaml
exposure_type:
  - revenue
  - gross_profit
  - product
  - capacity
  - customer
  - project
  - technology
  - management_comment
  - narrative
  - todo_insufficient_evidence
```

## 4. Exposure score guide

```yaml
0: no evidence or rejected
1: clue only / narrative only
2: product or management comment but no revenue evidence
3: disclosed product/project/customer relevance, revenue unknown
4: revenue/gross profit disclosed or strongly inferable with reviewed evidence
5: core business line with explicit revenue/profit exposure and high confidence
```

## 5. Guardrails

```text
- If revenue_pct is not disclosed, write MISSING_DISCLOSURE.
- If product exists but revenue is unknown, exposure_type is product/project/technology, not revenue.
- If customer or order is a framework agreement, do not treat as recognized revenue.
- If management comment is positive, keep claim_type=management_comment.
```
