# 002837 V1 replay close readout

## Outcome

The isolated offline stock-first chain completed its automatable T0-T10 scope and closed honestly at `needs_fix`. The pure Bundle13R recomputation exactly matched the archived result: queue 21, resolved 6, unresolved 11, validation blockers 0.

## Input and research boundary

- Real archived evidence objects: 4; every raw hash matches `data/manifests/evidence_manifest.csv`.
- Structured metric candidates: 136; all remain draft and unpromoted.
- Historical source workflow: `wf_20260703_stock_first_002837_invic` (read-only lineage only).
- Current workflow: `wf_20260723_stock_first_002837_v1_replay`.
- No live network, raw copy, historical mutation, new Reader, or inherited human decision.

## Quality and next step

G3 and G6 fail because four high research gaps remain. The next route is `evidence-ingest` at T1; the required trigger is same-period, locator-backed official operating evidence. The exposure mapping remains blocked from global update.

## Four independent facts

- `system_v1_complete=false` during P4.
- `sample_quality_ready=false`.
- `p2_ready=false`.
- `release_ready=false`.

## Repeatability

Exact command:

```powershell
C:\Projects\03_Investment_System\.conda\investment-system\python.exe -B scripts\run_r5_v1_replay_002837.py --repo-root . --source-run reports\workflow_runs\wf_20260703_stock_first_002837_invic --output-run reports\workflow_runs\wf_20260723_stock_first_002837_v1_replay
```

The command performs two materializations and records zero byte drift in `validation/idempotence_report.yaml`.
