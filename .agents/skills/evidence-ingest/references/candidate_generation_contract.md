# Candidate Generation Contract

## Principle

`evidence-ingest` may generate draft candidates. It must not generate final conclusions.

```text
claim_candidates / metric_candidates = draft candidates
claims_registry / metrics_registry = reviewed, stable, citable objects
```

## Claim candidate schema

```csv
claim_candidate_id,evidence_id,source_type,source_name,reliability_rank,entity_type,entity_id,segment_id,company_id,stock_code,claim_text,claim_type,claim_scope,quote_or_excerpt,page_no_or_section,table_id,confidence,materiality,support_level,needs_review_reason,review_status,promote_to_claim_id,created_at,notes
```

## Claim types

```text
fact
metric_statement
management_comment
company_claim
analyst_view
estimate
inference
clue
risk
counter_evidence
```

## Claim rules

1. A-level official disclosures may generate `fact`, `metric_statement` and `management_comment` candidates.
2. B-level structured data should generate metric statements or metric candidates, not business-exposure facts.
3. C-level materials default to `management_comment`, `company_claim`, `analyst_view`, `estimate` or `clue`.
4. D-level materials can only generate `clue` or TODO.
5. Estimates must be marked as estimates.
6. Inferences require supporting claim IDs or metric IDs before promotion.

## Metric candidate schema

```csv
metric_candidate_id,source_evidence_id,source_name,source_type,entity_type,entity_id,segment_id,company_id,stock_code,metric_name,metric_category,period,period_type,value,unit,currency,original_value_text,original_unit_text,table_id,page_no_or_section,calculation_method,is_estimate,is_reported,confidence,review_status,promote_to_metric_id,created_at,notes
```

## Metric boundary

Metric candidates answer: what number was reported or snapshotted, with what period, unit and source.

They do not answer what the number means for a segment or whether it supports an investment thesis.

Allowed:

- extracting revenue, gross margin and business-composition rows from filings;
- registering Tushare/Baostock market or financial snapshots;
- registering market-size or penetration estimates from third-party reports as estimates;
- keeping period/unit/source/locator.

Not allowed:

- attributing company-wide revenue to a segment without segment-specific evidence;
- confusing orders, capacity, revenue, shipment and market share;
- treating brokerage estimates as facts;
- treating management comments as verified facts;
- producing trading decisions.

## Promotion rule

Promotion from draft to registry requires quality review:

```text
claim_candidates.csv  → quality/manual review → claims_registry.csv
metric_candidates.csv → quality/manual review → metrics_registry.csv
```

Promotion requires:

1. valid evidence ID;
2. quote/table/page locator;
3. entity identifiers;
4. allowed claim type or metric name;
5. rank/claim-type compatibility;
6. no D-level material claim;
7. estimate/inference flags and support fields where needed.
