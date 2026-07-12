# R5 Industry Evidence Pack Contract v0.1

## Purpose

`industry_evidence_pack.yaml` is a reviewed-source handoff for industry demand, supply, competition, technology and counterevidence. It is not a narrative industry report and must not contain unsupported market-size claims.

## Minimum content

```yaml
artifact_type: R5_industry_evidence_pack
schema_version: v0.1
workflow_id:
as_of_date:
sources:
  - source_id:
    underlying_source_id:
    owner_type:
    independence: independent
    review_status: reviewed
    evidence_classes:
      - industry_demand | industry_supply_competition
    claim_ids: []
    metric_ids: []
    source_path:
    coverage_ids: []
source_count:
underlying_source_count:
```

## Acceptance rules

- Demand must have at least two independent underlying sources.
- Supply/competition must have at least two independent underlying sources.
- Repeated extracts from one source count once.
- Company annual reports may supplement context but do not count toward the independent minimum.
- Market-size, penetration, pricing and market-share metrics must retain period, unit, definition and source.
- Conflicting definitions must be preserved and explained; do not average them silently.
- At least one counterevidence source must be available to the downstream thesis/risk unit.

Use `.agents/skills/segment-research/scripts/validate_r5_industry_evidence_pack.py` for the local gate.
