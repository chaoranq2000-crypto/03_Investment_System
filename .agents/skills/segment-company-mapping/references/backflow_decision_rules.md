# Backflow Decision Rules

## Purpose

`backflow_decision` records what a stock finding should do to segment-company state. It is a workflow action label, not an investment recommendation.

## Allowed values

```text
update_exposure
create_segment_candidate
no_backflow_needed
needs_review
blocked
```

## Decision guide

| decision | Use when |
|---|---|
| `update_exposure` | Existing exposure type, score, confidence, or evidence support should change. |
| `create_segment_candidate` | The stock evidence points to a possible segment that is not yet in taxonomy. |
| `no_backflow_needed` | The stock finding does not change segment state; reason must be visible. |
| `needs_review` | The mapping may matter but needs quality-review or source review first. |
| `blocked` | Evidence or identity is insufficient to decide. |

## Guardrails

- A valuation or market snapshot cannot trigger exposure backflow by itself.
- Product-line clues do not become revenue or profit exposure without official disclosure or reviewed claim support.
- `blocked` requires a next action, owner, or missing reason.
- `no_backflow_needed` must explain why no state update is needed.
