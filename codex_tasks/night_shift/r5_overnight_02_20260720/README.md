# R5_Overnight_Mission_02_20260719

This is the next executable night-shift work package for `03_Investment_System`.

## What it changes

Unlike a five-line gate queue, this package contains **40 dependency-aware tasks** with explicit paths, acceptance commands, required artifacts, retry rules and truth boundaries. It targets the real night-shift runtime, schema, tests, CI and backflow packet generation.

## Starting point

- Source: `codex/r5-night01-autonomous-harness`
- Exact SHA: `4340945457d661ed62967e949f862ccf2214aff2`
- Target: `codex/r5-night02-contract-recovery`
- Night01 truth: 6 pending work orders; 0/63 blockers resolved.

## Key design changes

- `no_safe_pilot` can no longer pass a delivery task.
- Nightly Mission completion is separated from long-term Goal closure.
- Partial/blocked/cutoff runs remain resumable across nights.
- Windows worktree path and Git branch are separate typed values.
- Tracked receipts use implementation identity; post-push receipts bind final remote HEAD.
- Contract proposals are not approvals.
- Missing upstream fields are not “fixed” by pointing assertions at unrelated legacy fields.
- 63 blockers become occurrence-level tasks, not four gates plus one aggregate task.
- A bounded fallback engineering backlog keeps the runner productive when research gates are external.
- Completing the 34 required tasks does not stop the run: ready strategic tasks continue until cutoff unless all 40 tasks and the next queue are complete.

## Files

- `COMPLETION_AUDIT.md` — checked Night01 result and root cause.
- `OVERNIGHT_MISSION.md` — mission contract and truth table.
- `EXECPLAN.md` — living execution plan.
- `task_queue.yaml` — 40 executable tasks.
- `pointer_occurrences.yaml` — exact seed for the eight pointer occurrences.
- `AGENT_PROMPT.md` / `scheduled_task_prompt.txt` — Codex prompt.
- `WINDOWS_RUNBOOK.md` / `bootstrap_worktree.ps1` — safe Windows bootstrap.
- `tools/verify_package.py` — package and queue validator.

## Validate before use

```powershell
python .\tools\verify_package.py
```

Then follow `WINDOWS_RUNBOOK.md`.
