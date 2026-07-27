# R5 Quality Gate

## Purpose

The R5 quality gate is an automated capability evaluator. It checks whether a
stock research pack and its future note meet machine-verifiable prerequisites
for sample quality. It does not generate report prose, investment advice or a
human approval.

## R5 local gate set

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

## Canonical owner mapping

Each active issue row records the local id in `local_check_id`, the first owner
gate in `gate_id`, and the complete list in `mapped_global_gate_ids`.

| local_check_id | mapped_global_gate_ids | owner | applicable_boundary | failure_backflow |
|---|---|---|---|---|
| `R5-G1` | `G1` | `quality-review` | evidence completeness | `evidence-ingest` |
| `R5-G2` | `G3\|G7` | `quality-review` | financial model used by a stock report | `stock-deep-dive` |
| `R5-G3` | `G2\|G3\|G7` | `quality-review` | business breakdown and its report claims | `stock-deep-dive` |
| `R5-G4` | `G4\|G7` | `quality-review` | segment context consumed by a stock report | `segment-research` |
| `R5-G5` | `G3\|G7` | `quality-review` | forecast model | `stock-deep-dive` |
| `R5-G6` | `G3\|G7` | `quality-review` | valuation context | `company-valuation` |
| `R5-G7` | `G3\|G7` | `quality-review` | dated market and technical context | `stock-deep-dive` |
| `R5-G8` | `G1\|G2\|G7` | `quality-review` | sentiment and event evidence/claims | `evidence-ingest` |
| `R5-G9` | `G2\|G7` | `quality-review` | narrative coherence and claim typing | `stock-deep-dive` |
| `R5-G10` | `G9` | `quality-review` | no-advice review | text owner skill |
| `R5-G11` | `G7` | `quality-review` | local sample benchmark | blocking issue owner |

This mapping does not create additional global gates or change sample quality,
P2 readiness, human authority, or engineering completion.

R5-G1–R5-G11 are explicit capability-local checks. A failed or incomplete local
check records `affected_capabilities` and maps to G0–G10, but it cannot directly
set canonical workflow status. Canonical status is derived from
`impact_scope`, `active_disposition`, actual current-goal dependency, and
`blocks_current_goal`.

## Outcome rules

```text
accepted: automatic quality passes and no active limitation remains.
accepted_with_todos: visible unused unknown, unavailable optional method, or report limitation remains.
needs_fix: current output actually uses unsupported data, has a wrong calculation or real double-count, hides a TODO, breaks a citation, or violates no-advice.
blocked: identity, path, parse, source integrity, or a required unavailable method prevents any honest target output.
```

Severity remains descriptive and cannot replace this derivation.

## Sample-quality blockers

The `sample_quality_ready` capability cannot pass when any of these are active:

```text
unsupported number used by the report
hidden TODO
direct trading instruction
real double-count
forecast model required by the frozen sample target but unavailable
valuation market snapshot required by a used valuation method but missing
business breakdown used by a material conclusion but missing
technical as_of_date missing for market-state language
no-advice gate missing or failed
```

Visible missing disclosure that is not used by the current output affects only the
named claim/section/method or `sample_quality_ready` capability. It can coexist with
canonical `accepted_with_todos`, even when severity is high. A local gate never
expands that limitation to the whole workflow.

Passing these local checks is necessary but not sufficient for
`sample_quality_ready=true`. The current final report must also have
`final_report_review_status=approved`, a valid real non-machine reviewer, and
a machine-recomputed SHA-256 matching the reviewed bytes, plus every other
applicable sample-quality condition. `not_requested|pending` does not change
the automatic workflow outcome or block `system_v1_complete`, but keeps
`sample_quality_ready=false`.

Evidence, claim, metric, field, candidate, calculation, pack and
generation-lock checks are machine validation. Their hashes are integrity
evidence and do not bind human review. Only the final report hash binds the one
active human decision. Historical Bundle/Night exact-hash reviews, authorities
and independent receipts remain read-only and are not active R5 inputs.

For `changes_requested`, `change_scope=automated_quality_defect` routes the
workflow to `needs_fix`; `change_scope=report_revision` requests only final
report revision and does not overwrite the automated outcome.

## Validation

Run:

```bash
python .agents/skills/quality-review/scripts/validate_quality_issues.py .agents/skills/quality-review/assets/r5_quality_issues.example.csv --require-current-goal --expected-decision accepted_with_todos
```

The validator reports one of:

```text
accepted
accepted_with_todos
needs_fix
blocked
```
