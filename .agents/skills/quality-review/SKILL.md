---
name: quality-review
description: Use when checking evidence traceability, claim types, stale evidence, metric definitions, counter-evidence, missing data, update logs, exposure mapping, stock-led backflow, and investment-safety boundaries. Do not use to generate new machine-unvalidated claims or trade instructions.
---

# Quality Review

## Purpose

Machine-check that research artifacts are traceable, correctly typed,
comparable, uncertainty-aware, counter-evidence-aware, updateable and free of
direct trading instructions.

This skill owns issue detection, severity assignment and scoped issue
classification. It does not own global workflow gate IDs or canonical outcome
semantics.

## Canonical boundary

Global gate IDs are defined only in:

```text
docs/workflows/RESEARCH_WORKFLOW.md
```

This skill may refer to G0-G10 but must not create new global G numbers.

Skill-local checks must use `QR-*` IDs.
For an explicitly requested local/legacy evaluator, read its existing reference
for the local IDs and mapping. In active issue records, `gate_id` remains a
canonical `G0`–`G10` owner gate; keep any local identifier in `local_check_id`.

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
- Check scorecard dimensions supported only by placeholder states from
  `config/scoring_frameworks.yaml` remain `score: null` /
  `score_type: unscored`, while every numeric score has non-placeholder
  evidence and is labelled `analyst_judgment`.
- Check missing disclosure triggers evidence refresh rather than an automatic
  score change or thesis invalidation.
- Check report path and output boundary.
- Output issue list, severity and fix owner.
- Compute or recompute final-report SHA-256 and validate the review record
  without creating reviewer identity or a human decision.

## Out of scope

- Do not generate new machine-unvalidated conclusions.
- Do not replace `evidence-ingest`.
- Do not replace segment or stock research.
- Do not output buy/sell/hold instructions.
- Do not silently modify reports; list required fixes.
- Do not approve evidence, claims, metrics, fields, candidates, calculations,
  generation locks or intermediate receipts on behalf of a human.
- Do not synthesize a final-report reviewer, timestamp, approval or change request.

## Issue records

Use `references/issue_schema.md` as the only field-level issue contract and
validate active issue lists with this skill's validator. For each finding:

- cite the affected artifact and evidence;
- select the applicable canonical owner gate and any local check ID;
- classify the issue and identify the affected capability and fix owner;
- preserve visible non-blocking limitations and legacy provenance.

Severity is descriptive only. Derive no run outcome in this skill; return the
validated issue list to `research-orchestrator`, which consumes the canonical
semantics from `RESEARCH_WORKFLOW.md`. Historical compact rows remain inputs
only through the compatibility behavior defined in `references/issue_schema.md`.

## Machine qualification and final-report human review

Active V1 intermediate validation is automated. `reviewed evidence`,
`reviewed_claims`, `reviewed_metrics`, promoted candidates and similar names
mean that the objects passed applicable provenance, schema, claim-type,
metric, citation, hash and no-advice checks. They do not mean human approval
and do not require reviewer authority, signatures, independent receipts or
per-candidate decisions.

The only active human boundary is the final report. New or updated active
states follow
`.agents/skills/research-orchestrator/references/workflow_state_schema.md` and
`schemas/r5_final_report_review.schema.json`; this skill does not restate
their fields or transition table.

This skill owns automated report-quality checks and machine hash verification,
not the human decision. Recompute the current report hash, report stale or
invalid bindings as issues, and return the validated result to the
orchestrator. Never synthesize human-only data or let a human review override
an automatic failure. Historical local reviewer authority, receipts, candidate
decisions and exact-hash reviews are read-only and never satisfy the active
final-report review.

Only the final report hash binds human review. All other hashes, including
generation locks, remain machine-integrity and reproducibility evidence.

## Global gate checks consumed by this skill

Consume global gate IDs and pass conditions only from
`docs/workflows/RESEARCH_WORKFLOW.md`. Select and execute the applicable owner
gate for evidence, claims, metrics, exposure, reports, backflow or no-advice;
record the observed evidence and issue rows without restating the global gate
contract here.

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

`data_layer_quality_report.md` is a supporting quality artifact. Applicable
G0-G10 evidence is rendered in `quality_gate_report.md`; the current workflow
outcome remains owned by `workflow_state.yaml`.

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

### Conditional legacy sample-quality evaluation

Only when the handoff explicitly requests the retained legacy sample-quality
capability, read `references/r5_quality_gate.md` for its local checks, mapping
and validation example. Return scoped issues through the ordinary issue
contract; the evaluator cannot write canonical status and affects only the
declared capability.

## Outcome routing

Do not maintain a local outcome truth table. Validate findings, preserve the
evidence and affected scope, and return them to `research-orchestrator` for
canonical status derivation under `RESEARCH_WORKFLOW.md`. Apply missing-data
degradation from that kernel and `QUALITY_GUARDRAILS.md`; do not turn an
optional capability gap into a new global rule.

## Outputs

```text
quality_gate_report.md
quality_issues.csv
evidence_gap_list.csv
stale_or_contradicted_claims.csv
required_fixes.md
```

When a final report exists, return the automated checks and machine-computed
report hash to `research-orchestrator` for schema-governed state update. This
skill must not write legacy derived booleans or populate human-only fields.

## Guardrails

- Quality review should surface problems, not hide gaps.
- Unsupported conclusions must become TODO / MISSING / LOW_CONFIDENCE / UNVERIFIED.
- Management comments, analyst predictions and media narratives must be labeled.
- Scores, memos and watchlists are not trading signals.
- Local evaluator results and historical decision projections cannot override
  the scoped current-goal derivation.

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
12. Are intermediate `reviewed` objects machine-qualified without human-authority fields?
13. If a final report review is bound, do its current bytes match the recorded SHA-256?
14. Does final-report review state pass the canonical state validator without
    bypassing automated quality or sample-quality ownership?
