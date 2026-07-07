# Backflow Decision Rules

## Purpose

`backflow_decision` records what a stock finding should do to segment-company state. It is a workflow action label, not an investment recommendation.

## Allowed values

```text
update_exposure
create_segment_candidate
update_company_universe
update_segment_taxonomy
update_scorecard
no_backflow_needed
blocked
```

## Decision guide

| decision | Use when |
|---|---|
| `update_exposure` | Existing exposure type, score, confidence, or evidence support should change. |
| `create_segment_candidate` | The stock evidence points to a possible segment that is not yet in taxonomy. |
| `update_company_universe` | The company pool entry needs a note, status, or evidence update. |
| `update_segment_taxonomy` | Segment boundary, alias, parent, or adjacent segment definition needs review. |
| `update_scorecard` | A reviewed stock finding should update a segment scorecard TODO or factor. |
| `no_backflow_needed` | The stock finding does not change segment state; reason must be visible. |
| `blocked` | Evidence or identity is insufficient to decide. |

## Guardrails

- A valuation or market snapshot cannot trigger exposure backflow by itself.
- Product clues do not become revenue exposure without official disclosure or reviewed claim support.
- `blocked` requires a next action, owner, or missing reason.
- `no_backflow_needed` must explain why no state update is needed.
