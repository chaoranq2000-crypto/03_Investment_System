# R5 Quality Scorecard V2

R5 quality review uses section readiness rather than a single pass/fail flag. The scorecard explains why an output is limited to source-gapped draft, reviewed-input draft, or sample-quality candidate.

Section readiness values:

- `ready`
- `ready_with_limitations`
- `source_gapped`
- `blocked`

Each section row must include:

- `section_id`
- `readiness`
- `evidence_ids`
- `issues`
- `limitations`
- `fix_owner_skill`

The overall artifact must include `allowed_report_level`, `sample_quality_blockers`, `next_actions`, and reviewed-input flags. Forecast and valuation sections cannot be marked ready unless their reviewed input flags are present.
