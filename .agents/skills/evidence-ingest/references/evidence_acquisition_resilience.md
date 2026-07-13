# Evidence Acquisition Resilience Contract

## Purpose

This contract defines how `evidence-ingest` routes a research data request to source adapters,
handles source failures and field drift, and preserves evidence boundaries before any data reaches
analysis or report-writing stages.

## Required chain

```text
data_request_plan
→ capability route
→ source health check
→ serial acquisition
→ independent fallback
→ schema fingerprint
→ raw snapshot/archive
→ evidence manifest / candidates / clue log
→ review and promotion
```

No adapter may write directly into a reader report, forecast model or valuation conclusion.

## Canonical files

```text
config/source_registry.yaml
config/evidence_source_routes.yaml
data/manifests/source_health_ledger.yaml
data/processed/logs/adapter_run_queue.yaml
reports/quality/source_route_quality_report.yaml
```

## Route requirements

Every capability route must define:

- `claim_boundary`;
- at least one enabled source;
- explicit source priority and role;
- an `independence_domain` for every source;
- a retry policy;
- expected fields for schema-drift detection;
- whether an official source is mandatory.

Material company facts require an official disclosure route. Structured database snapshots remain
metric-only. Management interactions remain management comments or clues. News, hotlists and fund
flow never become company facts without independent official verification.

## Independent fallbacks

A fallback only improves resilience when its failure domain is genuinely different. Two endpoints
behind the same vendor or the same undocumented field map do not count as two independent domains.
The route quality gate checks the number of enabled independence domains.

## Public HTTP operating rules

- Serial execution is the default.
- Reuse one opener/session per source runner.
- Apply a minimum request interval and bounded exponential retry with jitter.
- Respect numeric `Retry-After` when present.
- Retry transient network errors, `429`, and selected `5xx` responses.
- Do not immediately retry `401`, `403` or `404`.
- Record all attempts in the source-health ledger.
- Live execution requires an explicit switch; queue generation is dry-run by default.

These values are policies, not permanent truths. Source-specific thresholds must be configurable and
validated with fixtures rather than embedded throughout endpoint code.

## Source health states

```text
unknown
healthy
degraded
circuit_open
quarantined
```

A source enters `circuit_open` after repeated transient failures or immediately after a permission
denial. A known permanent endpoint failure enters `quarantined`. A successful later probe may restore
it to `healthy` after the configured cool-down period.

## Schema drift

Every adapter result exposes its observed field names. The orchestrator compares them with the route's
`expected_fields`. Missing required fields produce `schema_drift`, mark the source degraded, and trigger
an independent fallback. Silently accepting a shifted field map is prohibited.

## Acceptance gates

- No critical/high issue from `run_source_route_quality_gate.py`.
- Every material-fact route contains an enabled official source.
- Required independent fallback count is met.
- A `403` test proves no immediate retry.
- A schema-drift test proves fallback to a second source.
- Raw archive and manifest/candidate gates continue to run after acquisition.
