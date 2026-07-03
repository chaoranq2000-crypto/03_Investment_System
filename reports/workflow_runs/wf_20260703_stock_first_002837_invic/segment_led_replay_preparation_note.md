# Segment-led Replay Preparation Note

workflow_id: wf_20260703_stock_first_002837_invic
status: prepared_not_executed

## Scope

- Prepare inputs for a later segment-led replay.
- Do not rewrite the full segment report.
- Do not create a P2 comparison.

## Inputs Prepared

| target | required next skill | note |
|---|---|---|
| company_universe notes | segment-company-mapping | 002837 product-only evidence note refreshed. |
| exposure confidence | segment-company-mapping | Revenue and profit fields remain missing. |
| evidence map | segment-research | Add R4 review decisions as references if replay runs. |
| scorecard evidence_quality | segment-research | Decide whether disclosure gap affects evidence quality. |
| A-share purity TODO | company-universe | No new company pool expansion in this run. |
