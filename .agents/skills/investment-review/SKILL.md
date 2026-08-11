---
name: investment-review
description: >-
  Personal investment review workflow for importing trade records, reconstructing
  trade episodes, generating portfolio and instrument daily/weekly/monthly reports,
  inferring trading motives when decision notes are absent, and, only when explicitly
  requested with user-confirmed strategy and risk inputs, producing evidence-grounded
  personalized recommendations. Use for personal trade review and periodic reporting.
  Never route to order execution or guaranteed-return claims. When advice inputs are
  absent, produce observations rather than trading actions or position targets.
---

# Investment Review

## Product goal

Build a simple reader-facing review product. Let the user open one report center and
directly read:

- portfolio daily, weekly and monthly reviews;
- instrument daily, weekly and monthly reviews;
- operation reviews embedded as one section of each periodic report;
- inferred trading motives when no decision record exists;
- personalized actions and position guidance when the user has explicitly requested
  advice and supplied the required personal strategy and risk context;
- observation-only review when that context is absent.

Do not let a missing Decision block report generation.

## Working boundary

- Read the formal portfolio SQLite database in read-only mode.
- Store derived review state only in the existing review sidecar.
- Keep facts, inferred motives, retrospective outcomes and recommendations visibly
  separate.
- Preserve missing or uncertain inputs instead of inventing facts.
- Do not use information learned after an operation as evidence for what motivated
  that operation.
- Do not diagnose personality or mental health from trading records.
- Do not place orders, write to a broker, use broker credentials, guarantee returns,
  or present uncertain conclusions as certain.
- Do not add a new canonical P2 stage, behavior profile, complex risk model,
  provenance layer, approval workflow or revision system solely for this product.

This skill consumes Portfolio accounting facts but does not alter them. Research
artifacts remain no-advice inputs; importing them into Investment Review does not turn
their research conclusions into trading instructions.

Treat existing P2A-P2H artifacts, replay checks and playbooks as optional internal or
historical implementation references. Reuse what is already useful, but do not make
those stages prerequisites for ordinary periodic reports.

## Infer motives when no Decision exists

When no explicit decision note is linked, automatically infer one or more
`motive_hypothesis` objects from information available at the operation time.
Use, when available:

- operation type and sequence: open, add, reduce, exit or re-entry;
- price trend, volatility, volume and relative market/industry movement;
- position size, concentration, cash and portfolio exposure before the operation;
- unrealized or realized profit/loss state visible at that time;
- nearby operations in the same Trade Episode;
- public information already available before the operation.

For each inferred motive, provide:

- the most likely motive in plain language;
- supporting observations;
- at least one alternative explanation;
- qualitative confidence: `high`, `medium` or `low`;
- important missing information;
- the label `system_inference`.

If only one isolated trade and limited context are available, still provide a
best-effort low-confidence hypothesis and alternatives. Never present the inferred
motive as a recorded user statement. Use later price and outcome data only in the
retrospective review section.

## Advice boundary

An ordinary request to generate or refresh a periodic report produces an
observation-only review. Provide personalized trading actions only when the user, in
the current request or an explicitly advice-capable review, asks for advice and has
confirmed the strategy and risk inputs needed to interpret it. These inputs must at
least establish the user's time horizon and risk budget; preserve any relevant
liquidity, concentration or other portfolio constraints the user supplies. Never
substitute system defaults, historical experimental thresholds or inferred preferences
for user confirmation.

An observation-only review may describe accounting facts, changes in exposure,
retrospective outcomes, labeled motive hypotheses, risks, scenarios and questions for
the user. It must not recommend `buy`, `sell`, `hold`, `add`, `reduce` or `exit`, and
must not state an exact target position or position range.

When the user has explicitly requested advice and the necessary user-confirmed inputs
are present, use only information available at the report cutoff to provide a direct,
evidence-grounded recommendation.

A recommendation may include:

- `buy`, `sell`, `hold`, `add`, `reduce` or `exit`;
- an exact target position or a position range;
- time horizon;
- main supporting facts and inferences;
- price, valuation, portfolio or risk conditions behind the recommendation;
- invalidation conditions and major downside risks;
- data timestamp and important missing inputs.

Keep the recommendation separate from facts and motive inference. If data quality is
too weak to support the requested action or position size, return to observation-only
analysis for the unsupported part and state which evidence or user input is missing.

Do not claim guaranteed outcomes. Do not execute the recommendation.

## Minimal report contract

Keep the main report concise and reader-first. The items below are semantic
requirements, not mandatory headings or a checklist that must be printed in order:

1. 本期结论摘要；
2. 收益、持仓、现金和风险变化；
3. 操作与交易动机复盘；
4. 哪些判断或执行合理，哪些需要改进；
5. 观察、风险、场景与待确认问题；仅在满足 advice boundary 时给出个性化交易建议与建议仓位；
6. 主要依据、风险、失效条件和数据缺失。

Use fundamental/valuation, market/sector, technical/trend and
position/execution context as an evidence pool. Include a dimension in the main
text only when it changes the central judgment, explains an operation or outcome,
affects the recommendation, or constitutes a material risk. Put remaining facts,
operation details and source references in a collapsed appendix.

Organize the main text around one central judgment, a small number of material
findings, and the causal link to the operation or portfolio state. Include a next
action only when the advice boundary is satisfied.
Do not repeat the same fact in multiple sections merely to satisfy the report
contract.

Hide technical IDs, hashes, receipts and replay details from the main report. Put
only the minimum source and time references needed to understand the conclusion in a
collapsed appendix or internal log.

When a development-time reviewer is used to improve a real sample, treat it as a
principle-based critical reader rather than a template enforcer. It should identify
at most three material problems, state what should be preserved, not rewrite the
report, and allow at most one revision round. Ordinary report generation must not
depend on a new soft-review approval chain.

## Minimal workflow

1. Read and idempotently synchronize the portfolio ledger into the existing sidecar.
2. Select one natural trading day, week or month and one portfolio/instrument subject.
3. Calculate period facts and reconstruct the relevant Trade Episodes.
4. Infer missing motives and produce retrospective operation reviews.
5. Generate observation-only analysis from information available at the report
   cutoff; add personalized recommendations only when the advice boundary is satisfied.
6. Render and save one readable report.
7. After one real daily sample is accepted, reuse the same pipeline for all six report
   types and enable scheduled generation.

Do not require manual mapping review, byte-exact rebuild, multi-stage approval or a
new revision chain for every ordinary report. Run deeper validation only when the
source schema changes, reconciliation fails, time boundaries are materially
ambiguous, or a write could affect protected data.

## Completion criteria

The product is complete when:
- all six portfolio/instrument daily/weekly/monthly report types are directly
  accessible;
- reports are generated even when there was no trade or no Decision record;
- every relevant operation has a recorded motive or a labeled motive hypothesis;
- every report contains useful review judgments; personalized actions or position
  targets appear only when the user explicitly requested advice and supplied the
  required inputs;
- repeated runs do not duplicate reports or change source accounting data;
- failures and important missing data are visible without exposing a large audit
  interface to the user.
