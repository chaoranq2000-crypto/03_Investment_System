# Windows Runbook

## 1. Extract the package

Extract `R5_Overnight_Mission_02_20260719.zip` to a local folder.

## 2. Bootstrap the worktree

Run PowerShell from the extracted package folder:

```powershell
.\bootstrap_worktree.ps1 `
  -RepoRoot "C:\Projects\03_Investment_System" `
  -WorktreeRoot "C:\Projects\03_Investment_System_night02"
```

The script verifies `origin/codex/r5-night01-autonomous-harness` equals `4340945457d661ed62967e949f862ccf2214aff2`, creates `codex/r5-night02-contract-recovery`, and copies this package into `codex_tasks/night_shift/r5_overnight_02_20260720`. It never concatenates the path and branch into a single argument.

## 3. Scheduled task prompt

Use the contents of `scheduled_task_prompt.txt` as the Codex scheduled-task prompt. Set the working directory to:

```text
C:\Projects\03_Investment_System_night02
```

## 4. Morning inspection

Check:

- `reports/p1_6/r5_night_shift/r5_overnight_02_20260720/morning_readout.md`
- `reports/p1_6/r5_night_shift/r5_overnight_02_20260720/next_night_queue.yaml`
- `reports/p1_6/r5_night_shift/r5_overnight_02_20260720/publication/remote_delivery_receipt.json`
- target branch remote SHA and GitHub Actions status

The long-term Goal must still be open. A `partial` or `blocked` run is not a failure to be hidden; it must carry the queue forward.
