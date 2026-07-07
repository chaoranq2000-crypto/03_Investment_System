---
name: segment-company-mapping
description: "Use when maintaining many-to-many exposure records between segments and companies. In P1.6, prioritize B4-lite: consume stock segment_exposure.yaml and produce exposure state updates or change notes. Do not use for writing full narrative reports, valuation, or direct trading instructions."
---

# Segment Company Mapping

## Goal

Maintain `segment_company_exposure`, so one company can map to multiple segments and one segment can contain multiple companies.

In P1.6, the immediate goal is **B4-lite**: accept `segment_exposure.yaml` from stock-led MVP and create/update exposure state or write a blocked/TODO change note.

## When to use

- Need to add, update or review segment-company exposure.
- Need to consume `reports/stocks/<stock_code>_<company_name>/segment_exposure.yaml`.
- Need to distinguish revenue, product, technology, customer, project and narrative exposure.
- Need to produce a backflow decision after stock research.

## Inputs

```yaml
segment_exposure_path:
segment_id:
company_id:
stock_code:
stock_name:
evidence_ids:
claim_ids:
metric_ids:
revenue_pct:
profit_pct:
```

## Responsibilities

- Validate segment and company identifiers.
- Validate exposure_type, exposure_score and confidence.
- Ensure revenue_pct and profit_pct are disclosed or explicitly MISSING.
- Ensure exposure_score is backed by evidence/claim/TODO.
- Maintain evidence_ids, valid_from, valid_to and notes.
- Write exposure change notes and backflow decisions.
- Validate B4-lite `segment_exposure.yaml` with `scripts/validate_segment_exposure.py` before promoting updates.

## Out of scope

- Do not write full segment reports.
- Do not write full stock deep dives.
- Do not make valuation conclusions.
- Do not treat exposure scores as trading signals.
- Do not silently rewrite history; material changes need a change note or refresh log.

## Exposure type enum

```text
revenue
product
technology
customer
project
capacity
order
narrative
excluded
todo_insufficient_evidence
```

## Exposure score guide

| score | Meaning | Minimum support |
|---:|---|---|
| 0 | excluded / not material | evidence or exclusion reason |
| 1 | narrative/clue only | clue or TODO, no material claim |
| 2 | product/technology/customer clue | company evidence, low confidence |
| 3 | confirmed product/project/customer exposure | official/company evidence, revenue share MISSING allowed |
| 4 | meaningful business exposure | official evidence or multiple reviewed claims |
| 5 | high-purity/revenue-confirmed exposure | disclosed revenue/profit share or very strong official evidence |

Narrative-only exposure cannot score above 1. Technology-only exposure cannot score above 2 unless there is product/project/customer evidence.

## B4-lite workflow

1. Read `segment_exposure.yaml`.
2. Validate identifiers.
3. Validate each linked segment row.
4. Compare with existing `data/processed/normalized/segment_company_exposure.csv` if present.
5. Decide action:

```text
update_exposure
create_segment_candidate
update_company_universe
update_segment_taxonomy
update_scorecard
no_backflow_needed
blocked
```

6. Write either:

```text
data/processed/normalized/segment_company_exposure.csv
```

or:

```text
reports/stocks/<stock_code>_<company_name>/exposure_change_note.md
```

7. Handoff to `quality-review` for G6/G8 gates.

## Output row contract

```csv
segment_id,company_id,stock_code,stock_name,exposure_type,exposure_score,revenue_pct,profit_pct,evidence_ids,claim_ids,metric_ids,confidence,valid_from,valid_to,status,backflow_decision,notes
```

## References and validators

```text
references/exposure_schema.md
references/backflow_decision_rules.md
assets/segment_exposure.example.yaml
assets/segment_company_exposure.example.csv
scripts/validate_segment_exposure.py
```

## Guardrails

- revenue_pct and profit_pct cannot be guessed; if absent, write `MISSING:<reason>`.
- D-level clues cannot support high exposure_score.
- Technology reserve, capacity, orders and revenue must remain separate.
- Conflicting evidence must be shown side by side.
- No accepted mapping without evidence_ids, claim_ids, or explicit TODO.

## Quality checklist

- [ ] segment_id, company_id, stock_code and stock_name are present.
- [ ] exposure_type is in the allowed enum.
- [ ] exposure_score has evidence, claim, metric or TODO support.
- [ ] evidence_ids are filled or explicitly missing.
- [ ] confidence is high/medium/low.
- [ ] revenue_pct / profit_pct are disclosed or MISSING.
- [ ] backflow decision is explicit.
- [ ] change note exists for material updates.
