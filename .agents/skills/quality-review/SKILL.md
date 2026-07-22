---
name: quality-review
description: Use when checking evidence traceability, claim types, stale evidence, metric definitions, counter-evidence, missing data, update logs, exposure mapping, stock-led backflow, and investment-safety boundaries. Do not use to generate new unreviewed claims or trade instructions.
---

# Quality Review

## Purpose

Check that research artifacts are traceable, correctly typed, comparable, uncertainty-aware, counter-evidence-aware, updateable and free of direct trading instructions.

This skill owns issue detection and severity assignment. It does not own global workflow gate IDs.

## Canonical boundary

Global gate IDs are defined only in:

```text
docs/workflows/RESEARCH_WORKFLOW.md
```

This skill may refer to G0-G10 but must not create new global G numbers.

Skill-local checks must use `QR-*` IDs.
R5 sample-quality checks use local `R5-G1` to `R5-G11` IDs from
`references/r5_quality_gate.md`; they do not extend the global workflow gate
table.

In active issue records, `gate_id` is always a canonical `G0`–`G10` owner gate.
Put the R5/QR/compatibility identifier in `local_check_id` and record every owner
gate in `mapped_global_gate_ids`. Historical compact CSV files without those
columns remain compatibility inputs only.

## When to use

- Before delivering segment report, stock report, comparison, memo or refresh log.
- Before / after modifying scorecard, watchlist, thesis or exposure records.
- When evidence conflicts, data is missing, or source reliability is unclear.
- At quality stages of stock-first, segment-first and interlock runs.

## Inputs

```text
artifact paths
evidence_manifest.csv
claims_draft.csv / claims_registry.csv
metrics_draft.csv / metrics_registry.csv
segment_exposure.yaml
segment_company_exposure.csv
workflow_state.yaml
run_log.md
data_layer_quality_report.md
valuation_snapshot.yaml
technical_snapshot.yaml
financial_metric_pack.csv
source_gap_report.md
```

## Responsibilities

- Check material claims have evidence / claim / metric / TODO support.
- Check claim_type separation.
- Check metric period, unit, source and calculation method.
- Check risk, counter-evidence and missing data.
- Check exposure mapping and backflow decisions.
- Check report path and output boundary.
- Output issue list, severity and fix owner.

## Out of scope

- Do not generate new unreviewed conclusions.
- Do not replace `evidence-ingest`.
- Do not replace segment or stock research.
- Do not output buy/sell/hold instructions.
- Do not silently modify reports; list required fixes.

## Issue schema

Every issue must use:

```csv
issue_id,severity,gate_id,local_check_id,stage,target_artifact,description,fix_owner_skill,status,created_at,resolved_at,notes
```

For R5 issue-list validation, use the active compact CSV schema in
`references/issue_schema.md`:

```csv
issue_id,severity,gate_id,local_check_id,mapped_global_gate_ids,stage,target_artifact,section,description,fix_owner_skill,blocking_decision,next_action,status
```

Severity:

| severity | Meaning |
|---|---|
| critical | Blocks accepted status; indicates no-advice failure, identity failure, or impossible review state. |
| high | Blocks accepted status; affects evidence traceability, identity, exposure, material claims, or no-advice boundary. |
| medium | Does not block limited pilot if disclosed; affects completeness, comparability, confidence or important TODOs. |
| low | Formatting, naming, minor clarity or non-blocking improvements. |

Status:

```text
open
resolved
accepted_todo
waived_with_reason
```

## Global gate checks consumed by this skill

### G1 Evidence Gate

Pass conditions:

- Evidence manifest exists.
- Required official filings are registered or explicit TODOs exist.
- `source_url` and `raw_file_path` are separated.
- Structured API snapshots are marked metric-only.

### G2 Claim Gate

Pass conditions:

- `fact` / `estimate` / `inference` / `management_comment` / `analyst_view` / `opinion` are separated.
- D-level clues do not support material claims.
- Management comments are not written as facts.

### G3 Metric Gate

Pass conditions:

- Each metric has period, value, unit / currency, source evidence id and calculation method.
- Metric candidates from structured API are draft unless promoted.

### G6 Exposure Gate

Pass conditions:

- `exposure_type`, `exposure_score`, `evidence_ids` and `confidence` are present.
- `revenue_pct` / `profit_pct` are disclosed or `MISSING`.
- Narrative exposure is not upgraded to revenue / product exposure without evidence.

### G7 Stock Report Gate

Pass conditions:

- Stock report has metadata, evidence snapshot, business skeleton, financial metrics, linked segments, risk / counter-evidence and TODO.
- Material statements cite `evidence_id` / `claim_id` / `metric_id` or TODO / MISSING.
- Data-layer packs are used only when `data_layer_quality_report.md` has `high_issues: 0`.
- Missing valuation, technical, peer or structured financial packs remain TODO / MISSING.

### G8 Backflow Gate

Pass conditions:

- Backflow decision is explicit.
- Update / no-update / blocked reason is recorded.
- Stock findings are not isolated from segment-company state.

### G9 No Advice Gate

Pass conditions:

- No buy/sell/hold language.
- No target-price instruction.
- Score, memo or scenario is not framed as a trading signal.

## Skill-local subchecks

### QR-DL Data Layer Pack Subchecks

Use these subchecks when a report uses data-layer packs:

| local_check_id | Pass condition |
|---|---|
| `QR-DL-1` | `valuation_snapshot.yaml` exists before valuation context is written; otherwise `TODO_MARKET_DATA` is visible. |
| `QR-DL-2` | `technical_snapshot.yaml` exists before technical context is written; otherwise `TODO_MARKET_DATA` is visible. |
| `QR-DL-3` | `financial_metric_pack.csv` exists before structured financial data is used; otherwise `TODO_STRUCTURED_FINANCIAL_DATA` is visible. |
| `QR-DL-4` | `peer_market_snapshot.csv` exists before peer valuation comparison is written; otherwise `TODO_PEER_DATA` is visible. |
| `QR-DL-5` | Official disclosure evidence exists before business exposure is written as fact; otherwise `MISSING_DISCLOSURE` is visible. |
| `QR-DL-6` | Tushare / Baostock / market context snapshots do not support customer order, capacity or segment revenue facts by themselves. |

The data-layer quality adapter uses implementation-local `DLQ-*` checks. They
remain supporting checks and map as follows:

| local_check_id | mapped_global_gate_ids | applicable_boundary | failure_backflow |
|---|---|---|---|
| `DLQ-1` | `G1` | source permission | `evidence-ingest` |
| `DLQ-2` | `G1` | raw archive and hash presence | `evidence-ingest` |
| `DLQ-3` | `G1\|G3` | structured snapshot reproducibility | `evidence-ingest` |
| `DLQ-4` | `G3` | normalized field schema | `evidence-ingest` |
| `DLQ-5` | `G2\|G3\|G9` | metric-only and no-advice boundary | source or text owner |
| `DLQ-6` | `G3\|G7` | dated market snapshot | `evidence-ingest` |
| `DLQ-7` | `G1\|G10` | source-license and secret hygiene | `evidence-ingest` |
| `DLQ-8` | `G7\|G10` | supporting-pack and visible-TODO completeness | artifact owner |

`data_layer_quality_report.md` is a supporting quality artifact. The active
run's single current decision remains `quality_gate_report.md`.

### QR-VAL Valuation Sub-skill Subchecks

Use these checks when a stock report consumes `company-valuation` outputs.

| local_check_id | Pass condition |
|---|---|
| `QR-VAL-1` | `valuation_model.yaml` and `valuation_section_draft.md` exist, or visible `TODO_VALUATION_CONTEXT` is present. |
| `QR-VAL-2` | Every valuation metric has period, unit / currency, source path or metric id, calculation method and `as_of_date`. |
| `QR-VAL-3` | Peer comparison includes peer selection reasons, same-period multiple dates, and limitations. |
| `QR-VAL-4` | Bear/base/bull scenarios are labeled `estimate` / `inference` / `analyst_view` and include sensitivity or explicit TODO. |
| `QR-VAL-5` | No buy/sell/hold language, target-price instruction, position sizing or guaranteed return appears in valuation outputs. |
| `QR-VAL-6` | Market valuation, technical or peer context is not used as business exposure proof. |

### QR-R4 Publishable Stock Report Subchecks

Use these subchecks for R4 readiness or publishable-candidate stock reports:

| local_check_id | Pass condition |
|---|---|
| `QR-R4-1` | `official_financial_reconciliation.csv` exists before company-level financial metrics are treated as reported facts. |
| `QR-R4-2` | `business_segment_metric_pack.csv` exists before business-segment discussion is upgraded beyond explicit TODO / MISSING. |
| `QR-R4-3` | `MISSING_DISCLOSURE`, `official_missing` and `mismatch` rows stay visible. |
| `QR-R4-4` | `bridge_only` is distinct from `publishable_ready`. |
| `QR-R4-5` | No-advice boundary still passes. |

Reference:

```text
.agents/skills/stock-deep-dive/references/publishable_stock_report_gate.md
```

### QR-R5 Sample-Quality Gate Subchecks

Use `references/r5_quality_gate.md` when reviewing R5 research packs or R5
report notes. The R5 local gates are:

```text
R5-G1 Evidence Completeness Gate
R5-G2 Financial Model Gate
R5-G3 Business Breakdown Gate
R5-G4 Industry Context Gate
R5-G5 Forecast Model Gate
R5-G6 Valuation Gate
R5-G7 Market / Technical Gate
R5-G8 Sentiment / Event Gate
R5-G9 Narrative Coherence Gate
R5-G10 No-Advice Gate
R5-G11 Sample Benchmark Gate
```

The same reference contains the mandatory local-to-global mapping. R5 local
checks never appear in active `workflow_state.quality_gates[].gate_id`.

Validate issue lists with:

```bash
python .agents/skills/quality-review/scripts/validate_quality_issues.py --issues .agents/skills/quality-review/assets/r5_quality_issues.example.csv
```

## Outcome rules

| outcome | Conditions |
|---|---|
| `accepted` | No high / medium blocking issue. |
| `accepted_with_todos` | No high issue; medium / low TODOs documented. |
| `needs_fix` | At least one fixable high issue. |
| `blocked` | Identity / evidence / path / source problem prevents review. |

## Outputs

```text
quality_gate_report.md
quality_issues.csv
evidence_gap_list.csv
stale_or_contradicted_claims.csv
required_fixes.md
```

## Guardrails

- Quality review should surface problems, not hide gaps.
- Unsupported conclusions must become TODO / MISSING / LOW_CONFIDENCE / UNVERIFIED.
- Management comments, analyst predictions and media narratives must be labeled.
- Scores, memos and watchlists are not trading signals.

## Quality checklist

1. Do all key conclusions have `evidence_id`, `claim_id`, `metric_id` or TODO?
2. Are facts, estimates, inferences and opinions separated?
3. Are management comments tagged as management comments?
4. Are analyst predictions tagged as analyst views?
5. Is missing data explicitly marked?
6. Are counter-evidence and uncertainty visible?
7. Are metric period, unit and source clear?
8. Is stale evidence marked?
9. Is update / backflow logging required?
10. Is direct trading advice avoided?
11. Are missing data-layer packs represented as TODO / MISSING rather than unsupported conclusions?

<!-- BEGIN R5_BUNDLE11R_RUNTIME_INTEGRATION -->
## Bundle 11R semantic research gate

Review both truthfulness and decision usefulness. Fail a candidate when a core section lacks issuer-specific metrics, an economic section lacks a model link, peer multiples use an ineligible peer set, watchpoints are not falsifiable, the same insight is repeated across sections, proxy share exceeds the contract, or direct trading/target-price language appears. Extra length, citations, technical indicators, or unrelated passing sections cannot compensate for these failures.
<!-- END R5_BUNDLE11R_RUNTIME_INTEGRATION -->
