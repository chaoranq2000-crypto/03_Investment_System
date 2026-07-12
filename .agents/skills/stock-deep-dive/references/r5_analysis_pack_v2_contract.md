# R5 Analysis Pack v2 Contract

## Purpose

`analysis_pack_v2.yaml` replaces the former non-empty-field notion of analysis readiness. It validates analyst-authored reasoning units against reviewed evidence and a passed evidence coverage matrix.

The engine does **not** invent a judgment. Analysts or a constrained research step must provide the reasoning text and references; the deterministic engine decides whether the unit is complete.

## Analysis unit schema

```yaml
analysis_id:
section:
judgment:
trend:
causal_mechanism:
financial_impact:
supporting_source_ids: []
supporting_metric_ids: []
counter_evidence_source_ids: []
confidence: low | medium | high
falsification_condition:
watch_metrics:
  - metric_name:
    metric_id:
    expected_direction:
    threshold:
    review_frequency:
    source_id:
dependencies: []
status: complete | blocked
blockers: []
```

## Required closed loop

```text
reviewed facts / metrics
    -> change trend
    -> causal mechanism
    -> financial impact
    -> counterevidence
    -> falsification condition
    -> measurable watchpoint
```

## Required sections

1. `core_thesis`
2. `financial_quality`
3. `business_driver`
4. `segment_economics`
5. `industry_context`
6. `competitive_position`
7. `risk_counterevidence`

`catalyst_watchpoints` is optional in Bundle 8 because the complete market/event layer remains in Bundle 10.

## Fail-closed rules

- Unknown or unreviewed source references block the unit.
- Metric-dependent sections require known metric IDs.
- Industry, competition and risk sections require independent evidence.
- Financial and segment units require issuer evidence.
- Generic filler, duplicated core text, missing markers, circular dependencies and unsupported watch metrics block the unit.
- A passed section-level coverage row is required before a dependent unit can be complete.
- Bundle 8 passes only when all seven required sections have complete units and no submitted unit remains blocked.

## Derived assets

Complete units are split deterministically into:

- `thesis_tree.yaml`
- `business_driver_tree.yaml`
- `segment_economics.yaml`
- `competitive_position_matrix.yaml`
- `risk_counterevidence_pack.yaml`

No new facts are added during this split.
