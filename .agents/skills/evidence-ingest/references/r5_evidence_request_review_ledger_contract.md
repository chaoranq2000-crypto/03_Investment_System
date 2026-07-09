# R5 Evidence Request Review Ledger Contract

The review ledger records the review decision for each row in `R5_evidence_request_queue.yaml`. It does not download evidence, mutate the queue, or promote null-evidence requests.

## Artifact

- `artifact_type`: `R5_evidence_request_review_ledger`
- `schema_version`: `r5_evidence_request_review_ledger_v0.1`
- `workflow_id`
- `source_queue_path`
- `review_status`
- `items`
- `promotion_rules`

Each item must include:

- `request_id`
- `source_gap_id`
- `pack_section`
- `review_decision`: `pending`, `rejected`, `accepted`, or `needs_manual_collection`
- `evidence_id`
- `source_rank`
- `reason`
- `next_action`

`accepted` rows require `evidence_id` and `source_rank`. `pending` and `needs_manual_collection` rows require visible `reason` and `next_action`, and cannot unblock a source-gapped pilot.
