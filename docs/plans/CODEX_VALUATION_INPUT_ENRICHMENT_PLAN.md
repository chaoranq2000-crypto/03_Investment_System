# Codex Plan — P1.6 Valuation Input Enrichment

## Task name

P1.6 `company-valuation` input enrichment pass for `stock-deep-dive` report quality.

## Goal

Improve the valuation section quality by creating and validating the upstream input artifacts that `company-valuation` is allowed to consume:

1. `market_snapshot.csv`
2. `peer_market_snapshot.csv`
3. `financial_metric_pack.csv`
4. enriched `forecast_model.yaml` with net profit / EPS / margin anchors where supported
5. `valuation_input_readiness.yaml` or equivalent readiness section

This task should reduce visible valuation TODOs only when reviewed sources already support the data. Missing data must stay visible as `TODO_*`, `MISSING_*`, `LOW_CONFIDENCE_*`, or `not_assessable`.

## Current context

The previous hardening pass completed the `company-valuation` subagent integration. The remaining valuation quality gaps are input-side gaps, not subagent integration defects:

- `TODO_MARKET_DATA`
- `TODO_PEER_DATA`
- `TODO_FINANCIAL_METRIC_PACK`
- `TODO_FORECAST_MODEL_NET_PROFIT`
- `MISSING_DISCLOSURE`

`company-valuation` must remain a sub-skill of `stock-deep-dive`; it must not fetch live data or create new evidence. It only consumes reviewed inputs and emits valuation artifacts under `reports/workflow_runs/<workflow_id>/valuation/`.

## Hard boundaries

Do not do any of the following:

1. Do not enter P2.
2. Do not run live APIs unless a separate manual approval file already exists in the repo.
3. Do not call yfinance, AkShare, Tushare, Baostock, Wind, Choice, Eastmoney, or other live data services inside `company-valuation`.
4. Do not invent price, market cap, PE, PB, PS, EV/EBITDA, EPS, net profit, or peer multiples.
5. Do not convert valuation ranges into buy/sell/hold, target-price instruction, position sizing, stop-loss, take-profit, or trading timing language.
6. Do not use market valuation, technical snapshot, or peer multiples as business exposure proof.
7. Do not hide unresolved TODOs.
8. Do not overwrite existing accepted artifacts without preserving versioned outputs or a clear change log.

## Primary workflow run for dry-run

Use the existing stock-first workflow run as the primary dry-run target:

```text
reports/workflow_runs/wf_20260703_stock_first_002837_invic/
```

If this path is not present in the local checkout, discover the latest stock-first workflow run under `reports/workflow_runs/` and document the selected run in the readout.

## Files to inspect first

Read these before modifying anything:

```text
AGENTS.md
.codex/config.toml
docs/workflows/RESEARCH_WORKFLOW.md
docs/policies/EVIDENCE_AND_CITATION_POLICY.md
docs/policies/QUALITY_GUARDRAILS.md
.agents/skills/company-valuation/SKILL.md
.agents/skills/company-valuation/references/valuation_model_contract.md
.agents/skills/company-valuation/references/method_selection.md
.agents/skills/company-valuation/references/output_writing_rules.md
.agents/skills/stock-deep-dive/SKILL.md
.agents/skills/stock-deep-dive/references/valuation_subagent_handoff.md
.agents/skills/stock-deep-dive/references/forecast_valuation_contract.md
.agents/skills/quality-review/SKILL.md
reports/p1_6/COMPANY_VALUATION_SUBAGENT_HARDENING_READOUT.md
reports/workflow_runs/<workflow_id>/valuation/valuation_gap_requests.yaml
reports/workflow_runs/<workflow_id>/stock_analysis_pack.yaml
reports/workflow_runs/<workflow_id>/artifact_manifest.csv
reports/workflow_runs/<workflow_id>/R4_stock_deep_dive_v0_2.md
reports/workflow_runs/<workflow_id>/R4_quality_gate_report_v0_2.md
reports/workflow_runs/<workflow_id>/R4_source_gap_report_v0_2.md
```

## Phase 0 — Inventory and gap map

Create:

```text
reports/p1_6/VALUATION_INPUT_ENRICHMENT_INVENTORY.md
```

It must include:

1. selected workflow_id;
2. current valuation gap IDs;
3. existing candidate input artifacts;
4. whether each artifact is parseable;
5. whether each artifact has source fields;
6. whether it is acceptable as reviewed input;
7. exact decision for each gap:
   - `ready_to_resolve`
   - `partial_ready`
   - `keep_todo`
   - `blocked_missing_source`

Suggested table:

```md
| gap_id | target_input | existing_candidate | parse_status | source_support | decision | notes |
|---|---|---|---|---|---|---|
```

Do not resolve any TODO in this phase.

## Phase 1 — Add valuation input contract and templates

Add or update these contract files:

```text
.agents/skills/stock-deep-dive/references/valuation_input_enrichment_contract.md
.agents/skills/stock-deep-dive/assets/market_snapshot_template.csv
.agents/skills/stock-deep-dive/assets/peer_market_snapshot_template.csv
.agents/skills/stock-deep-dive/assets/financial_metric_pack_template.csv
.agents/skills/stock-deep-dive/assets/valuation_input_readiness_template.yaml
```

Optionally add a short cross-reference in:

```text
.agents/skills/stock-deep-dive/references/valuation_subagent_handoff.md
.agents/skills/stock-deep-dive/references/forecast_valuation_contract.md
.agents/skills/company-valuation/references/valuation_model_contract.md
```

Do not redefine the global workflow or quality gate IDs.

### Required `market_snapshot.csv` columns

```csv
stock_code,company_id,stock_name,exchange,as_of_date,currency,close_price,market_cap,free_float_market_cap,shares_outstanding,float_shares,pe_ttm,pe_lyr,pe_forward_2026e,pb_lf,ps_ttm,ev,ev_ebitda_ttm,dividend_yield,turnover_rate,pct_chg_20d,pct_chg_60d,source_name,source_type,source_path,source_evidence_id,source_metric_id,reliability_rank,capture_method,snapshot_status,limitations
```

Rules:

- `as_of_date`, `currency`, `source_name`, `source_type`, `source_path`, and `snapshot_status` are mandatory.
- Numeric fields may be blank only if `snapshot_status` is `TODO_MARKET_DATA`, `MISSING_SOURCE`, or `LOW_CONFIDENCE`.
- Market context is not evidence of business exposure.

### Required `peer_market_snapshot.csv` columns

```csv
subject_stock_code,subject_company_id,peer_company,peer_stock_code,exchange,peer_selection_reason,business_similarity,segment_overlap,as_of_date,currency,market_cap,pe_ttm,pe_forward_2026e,pe_forward_2027e,pb_lf,ps_ttm,ev_ebitda_ttm,revenue_growth_2026e,net_profit_growth_2026e,roe,gross_margin,source_name,source_type,source_path,source_evidence_id,reliability_rank,confidence,limitations
```

Rules:

- Peer rows must have selection reasons and limitations.
- If peer comparability is weak, label `LOW_CONFIDENCE_PEER_SET`.
- If peer data is unavailable, keep a TODO row rather than ranking peers.

### Required `financial_metric_pack.csv` columns

```csv
metric_id,company_id,stock_code,metric_name,period,value,unit,currency,source_evidence_id,source_path,calculation_method,claim_type,confidence,review_status,limitations
```

Rules:

- `metric_id`, `metric_name`, `period`, `unit`, `source_evidence_id` or `source_path`, `calculation_method`, and `review_status` are mandatory.
- Use `review_status=reviewed` only if the metric passed existing metric/quality checks.
- If metrics are only candidates, use `review_status=candidate` and do not promote them to deterministic valuation facts.

### Required `valuation_input_readiness.yaml` schema

```yaml
valuation_input_readiness:
  workflow_id:
  company_id:
  stock_code:
  as_of_date:
  generated_by: stock-deep-dive
  consumed_by: company-valuation
  inputs:
    market_snapshot:
      path:
      status: ready | partial | todo_market_data | stale_market_data | low_confidence
      unresolved_gaps: []
    peer_market_snapshot:
      path:
      status: ready | partial | todo_peer_data | low_confidence_peer_set
      unresolved_gaps: []
    financial_metric_pack:
      path:
      status: ready | partial | todo_financial_metric_pack
      unresolved_gaps: []
    forecast_model:
      path:
      status: ready | partial | todo_forecast_model_net_profit
      unresolved_gaps: []
  quality_constraints:
    no_advice_boundary: true
    market_context_not_exposure_proof: true
    missing_data_visible: true
```

## Phase 2 — Add valuation input validator

Add script:

```text
.agents/skills/stock-deep-dive/scripts/validate_valuation_inputs.py
```

The script should accept:

```bash
python .agents/skills/stock-deep-dive/scripts/validate_valuation_inputs.py \
  --workflow-run reports/workflow_runs/<workflow_id>
```

Minimum checks:

1. parse `market_snapshot.csv`, `peer_market_snapshot.csv`, `financial_metric_pack.csv`, `forecast_model.yaml`, and `valuation_input_readiness.yaml` if present;
2. check required columns;
3. check required YAML fields;
4. check `stock_code` / `company_id` consistency with `stock_analysis_pack.yaml`;
5. check `as_of_date` is present and not clearly future-dated relative to the run context;
6. check market and peer fields have source fields before status is `ready`;
7. check numeric valuation fields are not present with missing source;
8. check no prohibited advice language appears in valuation input comments or output drafts;
9. emit machine-readable JSON and a Markdown summary.

Suggested outputs:

```text
reports/workflow_runs/<workflow_id>/valuation_input_validation.json
reports/workflow_runs/<workflow_id>/valuation_input_validation.md
```

Add tests:

```text
tests/test_valuation_input_contract.py
```

Tests should cover:

1. valid template files parse;
2. missing required columns fail;
3. ready status without source fields fails;
4. TODO status with blank numeric fields passes;
5. prohibited advice language fails;
6. mismatched stock_code/company_id fails.

## Phase 3 — Materialize inputs for the selected workflow run

For the selected workflow run, attempt to create or update:

```text
reports/workflow_runs/<workflow_id>/market_snapshot.csv
reports/workflow_runs/<workflow_id>/peer_market_snapshot.csv
reports/workflow_runs/<workflow_id>/financial_metric_pack.csv
reports/workflow_runs/<workflow_id>/valuation_input_readiness.yaml
```

### Market snapshot handling

Only fill numeric market fields if a reviewed or at least explicitly traceable source already exists in the repo.

Acceptable sources, in order:

1. reviewed market snapshot already stored under the workflow run;
2. reviewed structured data snapshot with source path and date;
3. fixture data clearly labeled as fixture, only for contract testing, not for report claims;
4. otherwise `TODO_MARKET_DATA`.

If using fixture data, mark:

```text
snapshot_status=LOW_CONFIDENCE_FIXTURE
limitations=fixture_only_not_for_publishable_claim
```

Do not use fixture values to upgrade R4 report valuation conclusions.

### Peer snapshot handling

Create a peer set only if there is a documented peer selection rationale.

For `002837` / 英维克, potential peer categories may include thermal management / data center cooling / equipment peers, but Codex must not guess final peers without checking current repo evidence. If no reviewed peer list exists, create TODO rows and document `TODO_PEER_DATA`.

Required peer decision fields:

```text
peer_selection_reason
business_similarity
segment_overlap
limitations
confidence
```

### Financial metric pack handling

If `metrics_registry.csv`, `reviewed_metrics.csv`, `metric_candidates.csv`, or equivalent exists, derive `financial_metric_pack.csv` by mapping only reviewed or explicitly candidate metrics.

At minimum, attempt to include:

```text
revenue
gross_profit
gross_margin
operating_profit
net_profit_attributable
eps
operating_cash_flow
capex
roe
```

If a metric is absent, do not invent it. Keep a row with TODO only if the contract allows it, or document it in `valuation_input_readiness.yaml`.

### Forecast model handling

Update or create:

```text
reports/workflow_runs/<workflow_id>/forecast_model.yaml
```

Only add net profit / EPS / net margin forecasts if supporting metrics, claims, or explicit assumptions exist.

If only revenue forecast exists, keep:

```text
net_profit_attributable: TODO_MODEL_INPUT
eps: TODO_MODEL_INPUT
net_margin: TODO_MODEL_INPUT
```

If profit forecast is supportable, make sure each forecast item includes:

```yaml
claim_type: estimate
supporting_metric_ids: []
supporting_claim_ids: []
assumptions: []
confidence: high | medium | low
limitations: []
```

## Phase 4 — Refresh valuation request and company-valuation outputs

Update:

```text
reports/workflow_runs/<workflow_id>/valuation_request.yaml
```

Ensure input paths include:

```yaml
input_paths:
  market_snapshot: reports/workflow_runs/<workflow_id>/market_snapshot.csv
  peer_market_snapshot: reports/workflow_runs/<workflow_id>/peer_market_snapshot.csv
  financial_metric_pack: reports/workflow_runs/<workflow_id>/financial_metric_pack.csv
  forecast_model: reports/workflow_runs/<workflow_id>/forecast_model.yaml
  valuation_input_readiness: reports/workflow_runs/<workflow_id>/valuation_input_readiness.yaml
```

Then refresh `company-valuation` outputs under:

```text
reports/workflow_runs/<workflow_id>/valuation/
```

Expected behavior:

- If market snapshot is ready: static valuation may show dated market context.
- If peer snapshot is ready: peer comparison may show dated relative context with limitations.
- If forecast model has net profit / EPS: dynamic valuation may show scenario multiples.
- If any input remains TODO: output visible TODO and do not fill unsupported valuation prose.

## Phase 5 — Refresh report artifacts without entering P2

Create versioned outputs rather than overwriting v0.2 without trace:

```text
reports/workflow_runs/<workflow_id>/R4_stock_deep_dive_v0_3.md
reports/workflow_runs/<workflow_id>/R4_quality_gate_report_v0_3.md
reports/workflow_runs/<workflow_id>/R4_source_gap_report_v0_3.md
reports/workflow_runs/<workflow_id>/R4_open_questions_v0_3.md
```

Update:

```text
reports/workflow_runs/<workflow_id>/stock_analysis_pack.yaml
reports/workflow_runs/<workflow_id>/artifact_manifest.csv
```

Rules for R4 v0.3:

1. If valuation inputs are still TODO, keep the valuation section visibly TODO.
2. If partial inputs are ready, clearly separate:
   - fact
   - estimate
   - inference
   - analyst_view
   - unknown
3. Do not rank peers as investable / non-investable.
4. Do not use market or technical context as advice.
5. Do not remove `MISSING_DISCLOSURE` for liquid-cooling revenue/profit unless official disclosure supports it.

## Phase 6 — Quality-review and acceptance checks

Run or update quality-review for the selected workflow run.

The quality report must explicitly address:

```text
QR-DL-1 valuation_snapshot exists or TODO_MARKET_DATA visible
QR-DL-3 financial_metric_pack exists or TODO_STRUCTURED_FINANCIAL_DATA visible
QR-DL-4 peer_market_snapshot exists or TODO_PEER_DATA visible
QR-VAL-1 valuation outputs exist or TODO_VALUATION_CONTEXT visible
QR-VAL-2 every valuation metric has period/unit/source/as_of_date
QR-VAL-3 peer comparison has selection reason and limitations
QR-VAL-4 scenarios are estimate/inference and include sensitivity or TODO
QR-VAL-5 no direct trading advice
QR-VAL-6 market/peer/technical context is not exposure proof
```

Allowed final statuses:

```text
accepted
accepted_with_todos
publishable_ready_with_disclosure_todos
pass_with_todos
```

Do not force `publishable_ready` if valuation or disclosure gaps remain.

## Phase 7 — Validation commands

Run at minimum:

```bash
python -m py_compile $(find . -name '*.py' -not -path './.git/*')
pytest -q
python .agents/skills/stock-deep-dive/scripts/validate_valuation_inputs.py \
  --workflow-run reports/workflow_runs/<workflow_id>
```

Also run a parse smoke check, either via existing scripts or a small inline Python command, for:

```text
.codex/config.toml
reports/workflow_runs/<workflow_id>/stock_analysis_pack.yaml
reports/workflow_runs/<workflow_id>/forecast_model.yaml
reports/workflow_runs/<workflow_id>/valuation_input_readiness.yaml
reports/workflow_runs/<workflow_id>/valuation/valuation_model.yaml
reports/workflow_runs/<workflow_id>/valuation/valuation_snapshot.yaml
reports/workflow_runs/<workflow_id>/market_snapshot.csv
reports/workflow_runs/<workflow_id>/peer_market_snapshot.csv
reports/workflow_runs/<workflow_id>/financial_metric_pack.csv
```

## Phase 8 — Final readout

Create:

```text
reports/p1_6/VALUATION_INPUT_ENRICHMENT_READOUT.md
```

Required sections:

```md
# Valuation Input Enrichment Readout

status: accepted | accepted_with_todos | needs_fix | blocked

## Scope

## Inputs created or updated

## Gap resolution table

| gap_id | before | after | evidence/source support | status | notes |
|---|---|---|---|---|---|

## Report changes

## Quality gate result

## Validation commands and results

## Remaining TODOs

## Boundary confirmation
```

The boundary confirmation must state:

```text
- P2 not entered.
- No live API executed unless separately approved and documented.
- No buy/sell/hold/rating/position/stop/target-price instruction added.
- Market/peer/technical context not used as exposure proof.
- Missing data remains visible.
```

## Definition of done

This task is complete only if:

1. valuation input contracts and templates exist;
2. validation script and tests exist;
3. selected workflow run has explicit market / peer / financial_metric / forecast readiness artifacts;
4. `valuation_request.yaml` points to those inputs;
5. `company-valuation` outputs are refreshed or explicitly preserved with clear reason;
6. `stock_analysis_pack.yaml` references current valuation artifacts;
7. `artifact_manifest.csv` registers all new or changed artifacts;
8. R4 v0.3 or equivalent report update reflects improved valuation inputs or keeps TODOs visibly;
9. QR-DL and QR-VAL checks are addressed;
10. final readout is written;
11. tests and parse checks pass, or failures are documented with `needs_fix`.
