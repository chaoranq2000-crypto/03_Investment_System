# Windows Runbook — Night04

## 1. Extract and verify

```powershell
Expand-Archive .\R5_Overnight_Mission_04_20260721.zip -DestinationPath .\R5_Overnight_Mission_04_20260721
cd .\R5_Overnight_Mission_04_20260721
python .\tools\verify_package.py .
```

## 2. Bootstrap

```powershell
.\bootstrap_worktree.ps1 `
  -RepoRoot "C:\Projects\03_Investment_System" `
  -WorktreeRoot "C:\Projects\03_Investment_System_night04"
```

The script verifies the exact source branch/SHA and creates `codex/r5-night04-review-acceleration-and-unlock` in an isolated worktree.

## 3. Schedule

- Working directory: `C:\Projects\03_Investment_System_night04`
- Prompt: `codex_tasks/night_shift/r5_overnight_04_20260722\scheduled_task_prompt.txt`
- Start: 2026-07-21 23:00 Europe/London
- Stop claiming: 2026-07-22 06:15
- Final readout: 2026-07-22 06:30

## 4. Optional human decisions

Place externally completed manifests under:

```text
reports/p1_6/r5_night_shift/r5_overnight_04_20260722\external_decisions\
```

Use `templates\blank_batch_decision_manifest.yaml`. Do not edit candidate states directly.

## 5. Morning outputs

- `reports/p1_6/r5_night_shift/r5_overnight_04_20260722\morning_readout.md`
- `reports/p1_6/r5_night_shift/r5_overnight_04_20260722\review_acceleration\reviewer_dashboard.html`
- `reports/p1_6/r5_night_shift/r5_overnight_04_20260722\progress\blocker_ledger.md`
- `reports/p1_6/r5_night_shift/r5_overnight_04_20260722\publication\remote_delivery_receipt.json`
- `reports/p1_6/r5_night_shift/r5_overnight_04_20260722\next_night_queue.yaml`
