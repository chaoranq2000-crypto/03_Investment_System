# 002837 V1 policy refresh readout

## Result

- Workflow: `wf_20260725_stock_first_002837_v1_policy_refresh`
- Derived automatic status: `accepted_with_todos`
- Automatic G0–G10: `pass` (`G5=not_applicable`)
- Semantic digest: `2d8487beb46f10b6df103a9a2808998870a19556ef6879959ed15c6eb90cbcc6`
- Final report review: `not_requested`
- `system_v1_complete=false`
- `sample_quality_ready=false`
- `p2_ready=false`
- `release_ready=false`

## Source truth

- 2025 annual official disclosure: `ev_annual_report_002837_20260421_2cbfc5`; PDF and processed text hashes verified; pages 15–16 resolved.
- 2025 interim official disclosure: `ev_interim_report_002837_20250819_47054e`; PDF and processed text hashes verified; page 9 resolved.

## Issue disposition

The four historical high issues are not recorded as resolved. They are reclassified into current nonblocking limitations because their unknown values are visible and unused. Room/liquid partial overlap is confirmed while its amount remains unknown. The cabinet/liquid relationship remains unknown in both directions.

## Replay

`C:\Projects\03_Investment_System\.conda\investment-system\python.exe -B scripts\run_r5_v1_policy_refresh_002837.py --repo-root . --output-dir reports/workflow_runs/wf_20260725_stock_first_002837_v1_policy_refresh`
