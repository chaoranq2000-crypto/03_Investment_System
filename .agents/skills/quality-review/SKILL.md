---
name: quality-review
description: Use when checking evidence traceability, claim types, stale evidence, metric definitions, counter-evidence, missing data, update logs, exposure mapping, stock-led backflow, and investment-safety boundaries. Do not use to generate new unreviewed claims or trade instructions.
---

# Quality Review

## Goal

Check that research artifacts are traceable, correctly typed, comparable, uncertainty-aware, counter-evidence-aware, updateable and free of direct trading instructions.

In P1.6, prioritize **B6-lite stock gates** for the stock-led evidence-to-report MVP.

## When to use

- Before delivering segment report, stock report, comparison, memo or refresh log.
- Before/after modifying scorecard, watchlist, thesis or exposure records.
- When evidence conflicts, data is missing, or source reliability is unclear.
- At T9 of `stock_first_closed_loop`.

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

## Canonical gate boundary

Global `gate_id` values are defined only in:

```text
docs/workflows/RESEARCH_WORKFLOW.md
```

This skill may define quality checklists and stock-report-specific `subcheck_id`
values, but must not add new global G-number gates.

## Out of scope

- Do not generate new unreviewed conclusions.
- Do not replace `evidence-ingest`.
- Do not replace segment or stock research.
- Do not output buy/sell/hold instructions.
- Do not silently modify reports; list required fixes.

## Issue schema

Every issue must use:

```csv
issue_id,severity,gate_id,subcheck_id,stage,target_artifact,description,fix_owner_skill,status,created_at,resolved_at,notes
```

`gate_id` must come from `docs/workflows/RESEARCH_WORKFLOW.md`. If a local
check is needed, write it as `subcheck_id` or in `notes`.

Severity:

| severity | Meaning |
|---|---|
| high | Blocks accepted status; affects evidence traceability, identity, exposure, material claims, or no-advice boundary |
| medium | Does not block limited pilot if disclosed; affects completeness, comparability, confidence or important TODOs |
| low | Formatting, naming, minor clarity or non-blocking improvements |

Status:

```text
open
fixed
accepted_todo
false_positive
blocked
```

## Stock-led gates

### G1 Evidence Gate

Pass conditions:

- Evidence manifest exists.
- Required official filings are registered or explicit TODOs exist.
- source_url and raw_file_path are separated.
- structured API snapshots are marked metric-only.

### G2 Claim Gate

Pass conditions:

- fact / estimate / inference / management_comment / analyst_view / opinion are separated.
- D-level clues do not support material claims.
- management comments are not written as facts.

### G3 Metric Gate

Pass conditions:

- each metric has period, value, unit/currency, source_evidence_id and calculation_method.
- metric candidates from structured API are draft unless promoted.

### G6 Exposure Gate

Pass conditions:

- exposure_type, exposure_score, evidence_ids and confidence are present.
- revenue_pct / profit_pct are disclosed or MISSING.
- narrative exposure is not upgraded to revenue/product exposure without evidence.

### G7 Stock Report Gate

Pass conditions:

- stock report has metadata, evidence snapshot, business skeleton, financial metrics, linked segments, risk/counter-evidence and TODO.
- material statements cite evidence_id / claim_id / metric_id or TODO/MISSING.
- data-layer packs are used only when `data_layer_quality_report.md` has high_issues: 0.
- missing valuation, technical, peer or structured financial packs remain TODO/MISSING.

### G8 Backflow Gate

Pass conditions:

- backflow decision is explicit.
- update/no-update/blocked reason is recorded.
- stock findings are not isolated from segment-company state.

### G9 No Advice Gate

Pass conditions:

- no buy/sell/hold language.
- no target-price instruction.
- score, memo or scenario is not framed as a trading signal.

### G7-DL Data Layer Pack Check

Parent gate:

```yaml
parent_gate_id: G7
name: Data Layer Pack Check
```

Pass conditions:

- `valuation_snapshot.yaml` exists before valuation context is written; otherwise `TODO_MARKET_DATA` is visible.
- `technical_snapshot.yaml` exists before technical context is written; otherwise `TODO_MARKET_DATA` is visible.
- `financial_metric_pack.csv` exists before structured financial data is used; otherwise `TODO_STRUCTURED_FINANCIAL_DATA` is visible.
- `peer_market_snapshot.csv` exists before peer valuation comparison is written; otherwise `TODO_PEER_DATA` is visible.
- official disclosure evidence exists before business exposure is written as fact; otherwise `MISSING_DISCLOSURE` is visible.
- Tushare/Baostock/market context snapshots do not support customer order, capacity or segment revenue facts by themselves.

### G7-R4 R4 Publishable Stock Report Check

Parent gate:

```yaml
parent_gate_id: G7
name: R4 Publishable Stock Report Check
```

Pass conditions:

- `official_financial_reconciliation.csv` exists before company-level financial metrics are treated as reported facts.
- `business_segment_metric_pack.csv` exists before business-segment discussion is upgraded beyond explicit TODO/MISSING.
- `MISSING_DISCLOSURE`, `official_missing` and `mismatch` rows stay visible.
- `bridge_only` is distinct from `publishable_ready`.
- No-advice gate still passes.

Reference: `.agents/skills/stock-deep-dive/references/publishable_stock_report_gate.md`.

## Outcome rules

| outcome | Conditions |
|---|---|
| accepted | no high/medium blocking issue |
| accepted_with_todos | no high issue; medium/low TODOs documented |
| needs_fix | at least one fixable high issue |
| blocked | identity/evidence/path/source problem prevents review |

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
- Unsupported conclusions must become TODO/MISSING/LOW_CONFIDENCE/UNVERIFIED.
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
9. Is update/backflow logging required?
10. Is direct trading advice avoided?
11. Are missing data-layer packs represented as TODO/MISSING rather than unsupported conclusions?

Compatibility checklist:

1. 是否所有关键结论都有 `evidence_id` 或 `claim_id`。
2. 是否混淆事实、估计、推断、观点。
3. 是否把管理层表述当成事实。
4. 是否把券商预测当成事实。
5. 是否标记缺失数据。
6. 是否列出反证和不确定性。
7. 是否说明指标口径、单位和周期。
8. 是否存在过期证据。
9. 是否有更新日志要求。
10. 是否避免买卖建议。
