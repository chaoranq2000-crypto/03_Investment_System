# Legacy Stock Skill Rules Migrated Into Stock Deep Dive

## Purpose

This file carries forward the useful rules from the retired
`stock-research-analyst` and `stock-report-writer` split workflow.

It is a `stock-deep-dive` reference, not a routing entry. Do not call or revive
the old skills as defaults. The active stock path remains:

```text
research-orchestrator
-> evidence-ingest
-> stock-deep-dive
-> segment-company-mapping
-> quality-review
-> research-orchestrator close readout
```

## Migrated Analysis Rules

The former analyst layer is now SDD-2 Analysis pack build.

- Use reviewed claims, reviewed metrics, accepted estimates, and registered
  data-layer packs as inputs.
- Treat claim or metric candidates as candidates until quality-review promotes
  them.
- Do not download evidence, parse PDFs, register evidence, or run source
  adapters from `stock-deep-dive`.
- Build `stock_analysis_pack.yaml` as the single structured upstream for
  report drafting.
- Keep `facts`, `inferences`, `key_assumptions`, and
  `largest_uncertainties` separate.
- Preserve component outputs when useful:
  `financial_quality.yaml`, `business_breakdown.yaml`,
  `industry_context_card.yaml`, `forecast_model.yaml`,
  `valuation_model.yaml`, `peer_comparison.csv`,
  `technical_snapshot.yaml`, `market_sentiment_pack.yaml`,
  `catalyst_calendar.yaml`, `risk_counter_evidence.yaml`, and
  `evidence_gap_requests.yaml`.
- If a business line, customer, order, project, capacity, revenue, margin,
  forecast, valuation, technical, sentiment, or event field lacks support,
  write an explicit gap such as `MISSING_DISCLOSURE`,
  `TODO_SOURCE_REQUIRED`, `TODO_PARSE_REQUIRED`, or
  `LOW_CONFIDENCE_CLUE_ONLY`.

## Migrated Report Writing Rules

The former writer layer is now SDD-3 Report drafting.

- Report drafting translates `stock_analysis_pack.yaml` and component files
  into narrative. It must not discover new facts.
- Do not use hidden inputs. A material paragraph should trace back to a
  `claim_id`, `metric_id`, `evidence_id`, source path, or explicit TODO.
- Each major section should start with a section-level research observation,
  then show the evidence or metric, name the key variable, and state the risk
  or counter-evidence.
- Sample-level expression is allowed only when evidence gaps remain visible.
  A polished paragraph must not hide TODOs.
- When evidence is incomplete, use weaker wording:

```text
目前证据只能支持“<weaker_statement>”，尚不足以证明“<stronger_statement>”。
```

- Use `Evidence Map`, `Open Questions`, and `writer_gap_requests` or equivalent
  source-gap artifacts as part of the report output.
- Use `research_status` or watch-state language only as research workflow
  status. Do not use buy/sell/hold, rating, target-price instruction, position
  sizing, add/reduce-position wording, or guaranteed-return language.

## Not Needed After Merge

Mark duplicated old rules as `not_needed_duplicate` in cleanup readouts rather
than copying the same rule into multiple references.

These old split-workflow ideas are intentionally not retained:

- Separate active routing to `stock-research-analyst`.
- Separate active routing to `stock-report-writer`.
- A handoff that lets a writer consume raw evidence or unreviewed sources.
- Any `.codex` snippet that enables old stock skills by default.
- Any rule that lets report polish override evidence gaps, claim type labels,
  missing disclosure, risk, counter-evidence, or no-advice gates.

## Quality Review Hooks

Send the merged outputs to `quality-review` for:

- evidence traceability;
- fact / estimate / inference / management_comment / analyst_view separation;
- metric period, unit, source, and calculation method;
- business exposure and `segment_exposure.yaml`;
- report evidence map and source gaps;
- no-advice boundary;
- backflow decision.
