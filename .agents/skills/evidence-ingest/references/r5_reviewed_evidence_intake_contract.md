# R5 Reviewed Evidence Intake Contract

This contract turns planned `R5_evidence_request_queue.yaml` rows into reviewed local inputs. It does not authorize live API calls or unreviewed downloads.

## Artifact

- `artifact_type`: `R5_reviewed_evidence_registry`
- `registry_id`: stable registry identifier
- `workflow_id`: workflow run id
- `stock_code`: A-share stock code
- `no_live_api`: must be `true`
- `records`: reviewed or TODO intake rows

Each row must include:

- `source_gap_id`
- `request_id`
- `evidence_id`
- `source_type`
- `source_rank`
- `as_of_date`
- `review_status`: `planned`, `needs_review`, or `reviewed`
- `reviewer`
- `allowed_usage`
- `claim_scope`
- `metric_scope`
- `limitations`

## Promotion Rules

`planned` and `needs_review` rows may keep `evidence_id: null` only when the row remains a visible TODO. `reviewed` rows require a concrete `evidence_id`, a reviewer, allowed usage, and no unresolved `TODO_SOURCE_REQUIRED`.

Rows used for market, peer, event, or sentiment context require `as_of_date` before they can be marked `reviewed`.

Allowed usage must never contain direct trading instructions, position sizing, guaranteed return language, or buy/sell/hold recommendations.
