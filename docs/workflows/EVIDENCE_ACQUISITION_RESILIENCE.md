# Evidence Acquisition Resilience Workflow

## Scope

This workflow is an operational extension of `evidence-ingest`. It completes the missing layer between
`data_request_plan.yaml` and source-specific adapters. It is intentionally separate from analysis,
forecast, valuation and reader-report generation.

## Why this layer is needed

The repository already distinguishes official disclosures, structured databases, market context and
clues. The remaining operational risks are:

- a request has no deterministic source route;
- several fallbacks share the same failure domain;
- a public endpoint is retried too aggressively;
- `403` and field drift are mistaken for empty data;
- a broken source is called again in every run;
- downstream code cannot tell whether a gap is a disclosure gap or an acquisition failure.

## Workflow

### ER0 — Request

Input:

```yaml
request_id: REQ_002837_REFRESH
required_capabilities:
  - official_disclosures
  - financial_statements
  - financial_indicators
  - valuation_snapshot
  - technical_history
  - investor_relations
  - industry_policy
```

### ER1 — Route validation

```bash
python scripts/run_source_route_quality_gate.py
```

The gate checks source existence, claim permission, official-source requirements, independent fallback
coverage, retry-policy references and enabled routes.

### ER2 — Health-aware queue

```bash
python scripts/build_evidence_acquisition_plan.py \
  --request reports/workflow_runs/<workflow_id>/data_request_plan.yaml \
  --output reports/workflow_runs/<workflow_id>/adapter_run_queue.yaml
```

Queue generation is dry-run by default. Add `--live` only when source-specific adapters, credentials,
network terms and raw-archive paths have been verified.

### ER3 — Adapter execution

Source-specific adapters consume queue rows. They must return:

```yaml
success:
source_name:
capability:
fields:
http_status:
raw_snapshot_path:
error_class:
message:
```

The acquisition orchestrator applies fallback and schema checks. It does not parse findings into a
reader conclusion.

### ER4 — Health ledger

Write operational state to:

```text
data/manifests/source_health_ledger.yaml
```

The ledger is mutable operational metadata. Raw evidence remains immutable.

### ER5 — Existing evidence pipeline

Successful raw snapshots continue through the existing chain:

```text
hash/dedup
→ raw archive
→ parse/normalize
→ evidence_manifest
→ claim_candidates / metric_candidates / clue_log
→ review/promotion
```

## Initial capability map

| Capability | Preferred route | Independent fallback | Claim boundary |
|---|---|---|---|
| Official disclosures | CNINFO | SSE/SZSE/BSE | Material fact after review |
| Financial statements | Tushare | Baostock | Metric only |
| Daily price/history | mootdx | Tencent/Tushare/Baostock | Metric only |
| Valuation snapshot | Tencent | Tushare | Metric only |
| Fund flow | Planned Sina | Eastmoney/THS | Context or clue only |
| Investor relations | Planned CNINFO IR | CNINFO activity records | Management comment only |
| Industry policy | Official policy/statistics | Independent industry report | Contextual fact |
| Research metadata | Eastmoney metadata | Broker inventory | Analyst view only |
| News | Planned CLS | News/Eastmoney/THS | Clue only |

Planned sources remain disabled until their fixture tests and live-smoke gates pass.

## Bundle integration

This workflow should be treated as **R5 Bundle 8A**, an operational completion of M3. It does not close
Bundle 8's research gap by itself. After installation, run an evidence refresh for the unresolved
liquid-cooling segment disclosure gap, then close Bundle 8 before starting Bundle 9 forecasting and
valuation.
