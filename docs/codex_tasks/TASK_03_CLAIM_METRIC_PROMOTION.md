# TASK 03 — Candidate Review and Promotion

## Goal

Create a controlled path from draft claim/metric candidates to reviewed claims/metrics used in analysis packs.

## Files to create or modify

```text
src/review/promote_claim_candidates.py
src/review/promote_metric_candidates.py
src/review/validate_candidate_promotion.py
data/manifests/claims_registry.csv
data/manifests/metrics_registry.csv
tests/test_candidate_promotion.py
```

## Required behavior

1. Input claim_candidates / metric_candidates.
2. Validate evidence_id exists in manifest.
3. Validate page/table locator exists for material claims.
4. Validate metric unit, period and source.
5. Promote accepted candidates to registry.
6. Leave rejected or low-confidence candidates as TODO.
7. Write promotion_log.

## Acceptance criteria

```text
- Candidate without evidence_id cannot be promoted.
- Material claim without locator cannot be promoted.
- D-level source cannot support material claim.
- Estimate remains is_estimate=true.
```
