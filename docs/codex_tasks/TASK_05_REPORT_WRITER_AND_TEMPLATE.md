# TASK 05 — Implement Report Writer and Template Filling

## Goal

Generate `stock_report_sample_quality_draft.md` from `stock_analysis_pack.yaml` and related component files.

## Files to create or modify

```text
src/report/stock_report_writer.py
src/report/render_stock_report.py
tests/test_stock_report_writer.py
```

## Required behavior

1. Load `templates/stock_report_sample_quality.md`.
2. Load stock_analysis_pack and component files.
3. Render report sections.
4. Insert evidence map and open questions.
5. Write writer_gap_requests.yaml when required data is missing.
6. Never invent facts not present in analysis pack.

## Acceptance criteria

```text
- Report contains all standard sections.
- Major sections are non-empty or explicitly TODO.
- Evidence map exists.
- No buy/sell/hold or position sizing.
```
