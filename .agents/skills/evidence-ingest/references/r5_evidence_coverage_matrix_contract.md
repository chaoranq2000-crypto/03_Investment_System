# R5 Evidence Coverage Matrix Contract v0.1

## Purpose

`evidence_coverage_matrix.yaml` is the M3 decision surface between reviewed evidence and downstream analysis. It answers whether each research question has enough **distinct underlying sources**, not merely enough extracts or citation labels.

The matrix must never create facts. It consumes a reviewed source catalog and explicit requirements.

## Source catalog minimum fields

```yaml
source_id:
underlying_source_id:
title:
owner_type:
source_type:
review_status:
as_of_date:
evidence_classes: []
sections: []
peer_ids: []
counterevidence_for: []
claim_ids: []
metric_ids: []
source_path:
```

`underlying_source_id` is the deduplication key. Multiple pages, extracts or evidence cards from one document count once.

## Required coverage row

```yaml
coverage_id:
section:
research_question:
blocking:
owner_skill:
target_artifacts: []
required_evidence_classes: []
requirements:
  min_underlying_sources:
  min_independent_sources:
  min_peer_count:
  freshness_max_days:
  requires_counterevidence:
source_ids: []
underlying_source_ids: []
independent_underlying_source_ids: []
issuer_underlying_source_ids: []
peer_ids: []
counterevidence_source_ids: []
checks: {}
status: covered | blocked | partial | missing
reason_codes: []
```

## Hard rules

1. Only `reviewed`, `promoted` or explicitly accepted sources may support coverage.
2. Source age must satisfy the requirement-specific freshness limit.
3. Issuer documents cannot satisfy independent-industry minimums.
4. Peer coverage requires unique peer entities with operating evidence, not valuation multiples alone.
5. Counterevidence must be directly referenced when required.
6. `covered` is legal only when every row check passes.
7. Missing data remains blocked/TODO; it is not converted into a low-confidence fact.

## Bundle 8 minimums

- Seven blocking research requirements covered.
- At least seven reviewed underlying sources overall.
- At least four independent underlying sources overall.
- At least two independent sources for industry demand.
- At least two independent sources for supply/competition.
- At least three credible peers with operating data.

## Producer and consumer

- Producer: `evidence-ingest`, with `segment-research` responsible for industry inputs.
- Consumers: `stock-deep-dive`, `company-valuation` in Bundle 9, and quality gates.
