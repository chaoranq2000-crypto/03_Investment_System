# 002837 V1 replay run log

## Exact command

```powershell
C:\Projects\03_Investment_System\.conda\investment-system\python.exe -B scripts\run_r5_v1_replay_002837.py --repo-root . --source-run reports\workflow_runs\wf_20260703_stock_first_002837_invic --output-run reports\workflow_runs\wf_20260723_stock_first_002837_v1_replay
```

## T0-T10 execution

- T0: fixed 002837 scope, old source run and new target run verified.
- T1: two official and two structured archived inputs verified by path and SHA-256; no network used.
- T2: Bundle12R/13R context validated; structured candidates retained as draft and unpromoted.
- T3-T6: linked segment and run-scoped exposure projected; missing allocation remains visible.
- T7: gap-visible report produced without a new Reader or inherited human decision.
- T8: four high issues routed without updating global segment state.
- T9: G0-G10 evaluated; G3/G6 failed non-compensating checks.
- T10: singleton state, TODOs, quality report and readout materialized.

## Recomputed result

- decision: `backflow_execution_in_progress`
- resolved T1/T2 items: `6`
- unresolved T1/T2 items: `11`
- validation issues: `0`
- validation blockers: `0`

The command performs two internal materialization passes and fails if any compared output byte changes.
