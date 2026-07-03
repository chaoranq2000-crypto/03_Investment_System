---
name: stock-deep-dive
description: Use when analyzing one listed company across business lines, segment exposure, financial quality, customers, supply chain, governance, scenarios, risks, and evidence map. In P1.6, prioritize the B5-lite stock-led evidence-to-report MVP. Do not use for multi-segment ranking or direct buy/sell/hold advice.
---

# Stock Deep Dive

## Goal

Produce an evidence-backed stock research package that can stand alone as a company analysis and also feed the segment-company exposure state layer.

In P1.6, the immediate target is **B5-lite**: consume evidence-ingest outputs and run one stock-led MVP, not a final fully automated valuation system.

## When to use

- The user asks to research a single A-share company or stock code.
- A stock-first workflow needs business, financial and linked segment skeletons.
- A segment sample needs a stock deep dive.
- `segment_exposure.yaml` and evidence map are required.

## Inputs

Required:

```yaml
stock_code:
stock_name:
company_id:
exchange:
evidence_snapshot:
```

Optional:

```yaml
linked_segments:
claim_ids:
metric_ids:
evidence_ids:
stock_evidence_plan:
data_layer_packs:
  valuation_snapshot:
  technical_snapshot:
  financial_metric_pack:
  business_segment_metric_pack:
  peer_market_snapshot:
  source_gap_report:
existing_stock_report:
existing_segment_exposure:
```

## Responsibilities

- Confirm company identity and security code.
- Consume evidence registered by `evidence-ingest`; do not bypass manifest.
- Build a business and financial skeleton.
- Consume data-layer packs only after they pass the data-layer quality gate.
- Separate facts, management comments, estimates, inferences and opinions.
- Discover linked segments from products, customers, projects, orders, technology and business lines.
- Output `segment_exposure.yaml` for `segment-company-mapping`.
- Produce a stock report draft with evidence snapshot, risks, counter-evidence and TODOs.
- Produce a backflow decision.

## Out of scope

- Do not perform multi-stock ranking.
- Do not replace `evidence-ingest` for downloading or registering evidence.
- Do not replace full `segment-research`.
- Do not turn valuation scenarios into target-price instructions.
- Do not output buy/sell/hold recommendations.
- Do not support key financial or business claims with a single D-level clue.
- Do not silently overwrite old reports.

## B5-lite workflow

### 0. Company identity gate

Confirm:

```yaml
stock_code:
ts_code:
stock_name:
company_id:
exchange:
identity_confidence: high | medium | low
identity_evidence_ids: []
blocking_issues: []
```

If identity is ambiguous, stop and return `blocked`.

### 1. Stock evidence plan

Check for:

```text
- annual report / latest official filing;
- interim or quarterly report if available;
- material announcements in the selected date range;
- structured financial data snapshots;
- optional IR/company website/news clues.
```

If evidence is missing, create TODOs. Do not invent.

### 2. Evidence package consumption

Read only registered evidence/candidates:

```text
data/manifests/evidence_manifest.csv
data/manifests/claims_draft.csv or claims_registry.csv
data/manifests/metrics_draft.csv or metrics_registry.csv
reports/workflow_runs/<workflow_id>/stock_evidence_plan.yaml
reports/workflow_runs/<workflow_id>/valuation_snapshot.yaml
reports/workflow_runs/<workflow_id>/technical_snapshot.yaml
reports/workflow_runs/<workflow_id>/financial_metric_pack.csv
reports/workflow_runs/<workflow_id>/source_gap_report.md
```

For data-layer pack rules, read `references/data_layer_pack_consumption.md`.

For R4 readiness and publishable report boundaries, read `references/publishable_stock_report_gate.md`.

### 3. Business breakdown contract

For each business line, record:

```yaml
business_line:
description:
revenue:
gross_margin:
growth:
products:
customers:
capacity:
orders:
related_segments:
evidence_ids:
claim_ids:
confidence:
missing_fields:
notes:
```

Allowed missing value: `MISSING:<reason>`. Do not infer revenue_pct unless directly disclosed.

### 4. Financial metric contract

Each metric must include:

```yaml
metric_name:
period:
value:
unit:
currency:
source_evidence_id:
metric_id_or_candidate_id:
calculation_method:
is_estimate:
review_status:
```

### 4.1 Data-layer pack consumption gate

Before using market or structured data packs:

```text
- `data_layer_quality_report.md` must exist and have high_issues: 0.
- Missing `valuation_snapshot.yaml` means valuation context must stay `TODO_MARKET_DATA`.
- Missing `technical_snapshot.yaml` means technical context must stay `TODO_MARKET_DATA`.
- Missing `financial_metric_pack.csv` means structured financial data must stay `TODO_STRUCTURED_FINANCIAL_DATA`.
- Missing `peer_market_snapshot.csv` means peer comparison must stay `TODO_PEER_DATA`.
- Missing official disclosure means business exposure remains `MISSING_DISCLOSURE`.
```

### 5. Linked segments discovery

Each material business line must attempt segment mapping:

```yaml
segment_id:
segment_name:
link_status: confirmed_existing | candidate | excluded | todo_insufficient_evidence
exposure_type: revenue | product | technology | customer | project | narrative
supporting_evidence_ids:
confidence:
notes:
```

If a segment does not exist, create a mini segment context TODO instead of full industry research.

### 6. `segment_exposure.yaml` contract

Write:

```text
reports/stocks/<stock_code>_<company_name>/segment_exposure.yaml
```

Minimum fields:

```yaml
company_id:
stock_code:
stock_name:
as_of_date:
linked_segments:
  - segment_id:
    segment_name:
    exposure_type:
    exposure_score:
    revenue_pct:
    profit_pct:
    evidence_ids:
    claim_ids:
    metric_ids:
    confidence:
    valid_from:
    valid_to:
    backflow_decision:
    notes:
```

### 7. Stock report contract

Write:

```text
reports/stocks/<stock_code>_<company_name>/<date>_stock_deep_dive.md
reports/stocks/<stock_code>_<company_name>/evidence_map.md
reports/stocks/<stock_code>_<company_name>/open_questions.md
```

Required sections:

```text
0. Metadata and evidence snapshot
1. One-page conclusion split into fact / inference / assumption / uncertainty
2. Company identity and business structure
3. Business breakdown
4. Financial quality and metric table
5. Linked segments and exposure
6. Customers, suppliers, capacity, orders, projects
7. Governance and management comments
8. Scenario assumptions, not trading instructions
9. Risks and counter-evidence
10. TODO / MISSING
11. Evidence map
```

### 8. Backflow decision

Every stock run must end with one of:

```text
update_exposure
create_segment_candidate
update_company_universe
update_segment_taxonomy
no_backflow_needed
blocked
```

No backflow decision means the workflow cannot close.

### 9. Quality review handoff

Send stock package to `quality-review` with gates:

```text
G1 Evidence Gate
G2 Claim Gate
G3 Metric Gate
G6 Exposure Gate
G7 Stock Report Gate
G8 Backflow Gate
G9 No Advice Gate
```

## Outputs

```text
reports/stocks/<stock_code>_<company_name>/<date>_stock_deep_dive.md
reports/stocks/<stock_code>_<company_name>/segment_exposure.yaml
reports/stocks/<stock_code>_<company_name>/evidence_map.md
reports/stocks/<stock_code>_<company_name>/open_questions.md
reports/workflow_runs/<workflow_id>/handoffs/*
```

## Guardrails

- Stock report must include evidence snapshot and evidence map.
- Management outlook is `management_comment`, not fact.
- Valuation scenarios express assumptions and sensitivity only.
- Data-layer market context cannot prove business exposure, customer orders or segment revenue.
- Scorecard/scenario cannot become trading advice.
- Segment exposure must use many-to-many mapping.
- Missing data must be marked TODO/MISSING rather than filled by guess.

## Quality checklist

- [ ] company_id, stock_code, stock_name and exchange are correct.
- [ ] evidence_snapshot is present.
- [ ] key business and financial claims have evidence_id / claim_id / metric_id / TODO.
- [ ] metric period, unit, source and calculation method are explicit.
- [ ] data-layer packs either exist with `high_issues: 0` or are represented as TODO/MISSING.
- [ ] linked_segments use segment exposure mapping.
- [ ] revenue_pct/profit_pct are disclosed or MISSING.
- [ ] risk, counter-evidence and uncertainty are listed.
- [ ] backflow decision is explicit.
- [ ] no buy/sell/hold recommendation appears.
