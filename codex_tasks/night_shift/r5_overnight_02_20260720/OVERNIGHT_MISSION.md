# R5 Overnight Mission 02 — Contract Recovery, Outcome Semantics and Backflow Expansion

## Mission identity

- Package: `R5_Overnight_Mission_02_20260719`
- Run ID: `r5_overnight_02_20260720`
- Immutable source branch: `codex/r5-night01-autonomous-harness`
- Immutable source SHA: `4340945457d661ed62967e949f862ccf2214aff2`
- Target branch: `codex/r5-night02-contract-recovery`
- Expected worktree: `C:\Projects\03_Investment_System_night02`
- Timezone: `Europe/London`

## Long-term Goal

推进 Bundle17R targeted backflow，最终让四个真实 golden case 形成受审 evidence/materialization/qualification/regression/exact-hash 链。

**本夜不得关闭长期 Goal。** 本夜即使完成全部 runner 工程任务，也只能关闭 Night02 mission；长期 Goal 继续保持 open，直到真实研究门禁和人工门禁被关闭。

## Why this mission exists

Night01 工程闭环通过，但 `no_safe_pilot` 被当作 pilot 任务满足，之后队列只剩四个大门禁和一个汇总项，所以很快结束。Night02 把工作拆成 40 个有路径、有命令、有产物的工作单，并增加 fallback backlog。

## Non-negotiable truth

- Start: 6 work orders pending; 0/63 blockers resolved.
- Classification: 24 analysis, 20 dependency, 8 engineering-local, 8 evidence, 3 human.
- Historical Bundle17R and four Bundle16R case artifacts are read-only.
- A proposal is not an approval; a classification is not a resolution.
- `no_safe_pilot`, `blocked`, `partial`, and `cutoff` are not delivery success.
- No PR, no merge to main, no force push.
- No canonical state, sample quality or P2 mutation.

## Required delivery outcomes

1. Mission outcome state machine and Goal close policy are implemented and tested.
2. Windows path/branch separation, stale baseline detection, two-phase publication and digest validation are implemented.
3. Executable contract authority, lint, command safety, per-task scope guard and review hash lock are implemented.
4. 63 blocker occurrences are restored as an occurrence-level queue with dependency graph and owner packets.
5. Eight pointer issues receive semantically correct **proposals**; historical artifacts are not edited and no false resolution is claimed.
6. Fallback backlog, bounded retry, metrics, crash/cutoff resume and adversarial tests are implemented.
7. Night-specific, source-route and full regression pass; branch is pushed and remote SHA is verified.
8. Morning readout truthfully separates Night02 mission status from the still-open long-term Goal.
9. The next queue contains at least 12 executable or occurrence-sized tasks; it must not collapse into four gates plus one aggregate task.

## Mission outcome truth table

| Outcome | Meaning | Long-term Goal |
|---|---|---|
| `delivered` | All delivery-required Night02 engineering tasks passed, pushed and CI verified | remains open |
| `partial` | Some useful work passed, but delivery tasks remain or cutoff reached | remains open |
| `blocked` | No delivery task can proceed because of external authority/evidence | remains open |
| `failed` | Safety/acceptance failure unresolved | remains open |
| `cutoff` | Claiming stopped at cutoff; in-flight work was finalized | remains open |

`no_safe_pilot` is evidence attached to `blocked` or `partial`; it is never `passed`.

## Commit plan

Use coherent workstream commits, not one giant final commit and not one commit per trivial file:

1. `feat(night-shift): harden mission outcome and publication`
2. `feat(night-shift): enforce executable contract authority`
3. `feat(night-shift): expand backflow queue and fallback work`
4. `test(night-shift): add adversarial recovery coverage`
5. `docs(night-shift): publish mission 02 evidence and next queue`

Push after each coherent workstream. Never merge main and never create a PR.

## Execution rule

Read `task_queue.yaml`, continuously claim the highest-priority dependency-ready task, update receipts, and immediately claim the next task. When research gates are blocked, use the approved fallback engineering backlog. After every delivery-required task passes, continue with ready strategic-fallback tasks until cutoff. Stop early only when all 40 packaged tasks are terminal and the next queue (at least 12 tasks) has been generated.
