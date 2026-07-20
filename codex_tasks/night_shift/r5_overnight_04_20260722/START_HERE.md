# Start Here — Night04

This package uses Night03 final commit `758ab7557d9de9eea42a5aeb5df95e3d68c26f0c` as an exact source baseline.

## Validate package

```powershell
python .\tools\verify_package.py .
```

## Bootstrap isolated worktree

```powershell
.\bootstrap_worktree.ps1 `
  -RepoRoot "C:\Projects\03_Investment_System" `
  -WorktreeRoot "C:\Projects\03_Investment_System_night04"
```

Default source branch: `codex/r5-night03-targeted-backflow-intake`

Default target branch: `codex/r5-night04-review-acceleration-and-unlock`

The bootstrap must independently verify:

- remote source branch SHA equals `758ab7557d9de9eea42a5aeb5df95e3d68c26f0c`;
- GitHub Actions run `29693876604` succeeded and binds the same SHA;
- no PR exists for the source branch;
- Night03 tracked morning readout says 40/40 and `delivered_candidate_ready`;
- Night03 queue carries exactly 69 IDs: 63 occurrences + 6 parents;
- research truth remains 0/63 resolved, 43 candidate-ready, 20 dependency-blocked;
- Bundle17R, Night02 and Night03 historical paths are not modified.

## Scheduled task

Use `scheduled_task_prompt.txt` as the prompt and `C:\Projects\03_Investment_System_night04` as the working directory.

The mission window is 2026-07-21 23:00 to 2026-07-22 06:30 Europe/London.
