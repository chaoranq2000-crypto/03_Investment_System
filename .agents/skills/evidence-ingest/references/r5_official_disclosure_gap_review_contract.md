# R5 Official Disclosure Gap Review Contract

This contract handles business-line disclosure gaps such as liquid-cooling revenue, margin, profit contribution, and segment exposure. It does not fabricate a business split when official disclosure is absent.

Each review row must include:

- `gap_id`
- `requested_disclosure`
- `official_source_candidates`
- `reviewed_source_ids`
- `finding_status`: `found`, `not_found`, `partial`, or `needs_manual_review`
- `extracted_metric_candidates`
- `limitations`
- `allowed_usage`

If the disclosure is not found, `MISSING_DISCLOSURE` must remain visible in `limitations`. If partial disclosure is found, usage is limited to the exact extracted scope.

Any promoted reviewed source must include `evidence_id`, `source_rank`, and either `as_of_date` or `filing_date`.
