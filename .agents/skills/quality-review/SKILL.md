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

## Issue schema

Every issue must use:

```csv
issue_id,severity,impact_scope,active_disposition,affected_capabilities,blocks_current_goal,gate_id,local_check_id,mapped_global_gate_ids,stage,target_artifact,section,description,fix_owner_skill,blocking_decision,next_action,status
```

For active R5 issue-list validation, use the same scoped CSV contract in
`references/issue_schema.md`:

```csv
issue_id,severity,impact_scope,active_disposition,affected_capabilities,blocks_current_goal,gate_id,local_check_id,mapped_global_gate_ids,stage,target_artifact,section,description,fix_owner_skill,blocking_decision,next_action,status
```

For active rows, `blocking_decision` is a derived readout projection that must
match the four scoped fields; it is not an independent decision input.
Historical compact CSV rows that have `blocking_decision` but lack the scoped
fields are compatibility inputs only. An adapter must classify them against the
current goal and must not copy the historical decision into active state.

Allowed scoped values:

```text
impact_scope:
  workflow | report | section | claim | method | none

active_disposition:
  active_defect | unknown | method_unavailable | report_limitation |
  historical_backlog | policy_retired | not_required_for_active_v1
```

Severity:

| severity | Meaning |
|---|---|
| critical | Highest risk or urgency; often identity, no-advice or material truthfulness risk. |
| high | Material evidence, calculation, exposure, claim or report risk. |
| medium | Completeness, comparability, confidence or important TODO risk. |
| low | Formatting, naming, minor clarity or non-blocking improvements. |

Severity is descriptive only. It never sets `blocks_current_goal` by itself.

Status:

```text
open
resolved
accepted_todo
waived_with_reason
```

## Machine qualification and final-report human review

Active V1 intermediate validation is automated. `reviewed evidence`,
`reviewed_claims`, `reviewed_metrics`, promoted candidates and similar names
mean that the objects passed applicable provenance, schema, claim-type,
metric, citation, hash and no-advice checks. They do not mean human approval
and do not require reviewer authority, signatures, independent receipts or
per-candidate decisions.

The only active human boundary is the final report. New or updated active
states use:

```text
final_report_review_semantics_version: final_report_review_v1
automated_report_quality_passed
final_report_review_status:
  not_requested | pending | approved | changes_requested
final_report_review:
  report_path
  report_sha256
  reviewer
  reviewed_at
  decision
  notes
  change_scope
```

This skill owns the automated report-quality checks and machine hash
verification, not the human decision. `not_requested` leaves all binding,
person, note and `change_scope` fields empty. `pending` binds the repo-relative
final report path and current machine SHA-256 while reviewer, time, notes and
`change_scope` remain empty. `approved|changes_requested` require a real
non-machine reviewer, ISO time and non-empty notes; `decision` equals the
top-level status. `change_scope` is
`automated_quality_defect|report_revision` only for `changes_requested`.

Any report-byte change invalidates the prior decision. `not_requested|pending`
does not change the automatic workflow outcome or block
`system_v1_complete`, but `sample_quality_ready=false`.
`sample_quality_ready=true` requires all necessary automated quality
conditions, a valid `approved` decision for current report bytes and all other
applicable sample-quality conditions; these are necessary conditions and are
not automatically sufficient.

An `approved` review cannot override an automatic failure. A
`changes_requested` review routes to `needs_fix` only when
`change_scope=automated_quality_defect`; `report_revision` affects only the
final report revision. Historical Bundle/Night/Reader reviewer authority,
independent receipts, candidate decisions and exact-hash reviews are read-only
and never satisfy the active final-report review.

Only the final report hash binds human review. All other hashes, including
generation locks, remain machine-integrity and reproducibility evidence.

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
- Metric candidates from structured API are draft unless machine-qualified
  and promoted.

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

### QR-R5 Legacy sample-quality capability evaluators

R5-G1–R5-G11 are not default checks for ordinary workflow completion. Use
`references/r5_quality_gate.md` only when the handoff explicitly requests an
R5 report capability evaluation. The retained local evaluators are:

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
checks never appear in active `workflow_state.quality_gates[].gate_id`, never
write canonical status directly, and only affect their declared
`affected_capabilities`.

Validate issue lists with:

```bash
python .agents/skills/quality-review/scripts/validate_quality_issues.py --issues .agents/skills/quality-review/assets/r5_quality_issues.example.csv
```

## Outcome rules

The canonical truth table is owned by `RESEARCH_WORKFLOW.md`. This skill applies
it row by row:

| outcome | Conditions |
|---|---|
| `accepted` | Automated quality passes and no active limitation or TODO remains. |
| `accepted_with_todos` | Visible unknown, unavailable non-required method or report limitation remains, but the current output does not use it without support. |
| `needs_fix` | Current output contains an unsupported-used number, calculation error, true double-count, broken citation, hidden TODO, no-advice violation, or uses an unknown field. |
| `blocked` | Identity, path, parse, source identity or an irreplaceable required input fails so that no honest target output can be generated. |

`unknown` that is visible and unused sets `blocks_current_goal=false` even if
its severity is high. `method_unavailable` is blocking only when the frozen
current goal requires that method and no approved fallback exists.

Apply missing information through this degradation ladder:

```text
direct issuer disclosure
→ audited aggregate
→ bounded estimate / scenario with explicit assumptions
→ unknown or omit the dependent conclusion
```

Lower tiers must not be presented as higher tiers. Closing one capability does
not close unrelated report sections or the whole workflow.

## Outputs

```text
quality_gate_report.md
quality_issues.csv
evidence_gap_list.csv
stale_or_contradicted_claims.csv
required_fixes.md
```

When a final report exists, the automated report-quality result and
machine-computed report hash may also be recorded in `workflow_state.yaml`.
This skill must not populate human-only fields.

## Guardrails

- Quality review should surface problems, not hide gaps.
- Unsupported conclusions must become TODO / MISSING / LOW_CONFIDENCE / UNVERIFIED.
- Management comments, analyst predictions and media narratives must be labeled.
- Scores, memos and watchlists are not trading signals.
- Local Bundle/R5 results and historical `blocking_decision` values cannot
  override the scoped current-goal derivation.

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
14. Does `sample_quality_ready` remain false for `not_requested|pending`,
    stale approval, or failed automated quality?

## Explicit legacy semantic evaluators

Bundle11R–16R semantic checks may be retained only as explicitly invoked
capability-local evaluators mapped to G0–G10. They may flag missing
issuer-specific metrics, model links, peer eligibility, falsifiability,
duplication, proxy use or no-advice failures, but each finding must carry the
scoped fields above.

An unavailable optional model becomes a visible capability limitation. An
unsupported model result actually used in the report, a true double-count or a
direct trading instruction is an active defect and `needs_fix`. Extra length,
citations or unrelated passing sections cannot offset an active defect.

Legacy evaluator human-review, authority, receipt and candidate-decision
artifacts remain read-only. Explicit capability evaluation is automatic and
does not create another human boundary.
