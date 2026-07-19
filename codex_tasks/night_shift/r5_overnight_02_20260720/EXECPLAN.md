# ExecPlan — r5_overnight_02_20260720

This file is a living execution plan. Update the Progress, Discoveries, Decisions and Remaining Work sections after each workstream. Do not replace it with a retrospective-only document.

## Purpose

Repair the Night01 early-close semantics and turn Bundle17R backflow into a durable, occurrence-level, truth-preserving queue. The code change is in the real night-shift runtime, schema, tests and CI—not only in task documentation.

## Progress

- [x] A. Exact baseline and Night01 audit
- [x] B. Mission outcome / Goal-close separation
- [x] C. Executable contract authority and safety
- [ ] D. Occurrence-level backflow and fallback queue
- [ ] E. Adversarial tests, deterministic dry run, full regression and publication
- [ ] F. Optional strategic fallback artifacts

## Workstream A — baseline and publication defects

Implement T00–T03. In particular, treat worktree path and branch as separate typed values and detect the stale `f89a3ab` baseline against final `4340945457d661ed62967e949f862ccf2214aff2`.

## Workstream B — outcome semantics

Implement T10–T15. A run may finish while the long-term Goal stays open. A tracked receipt cannot contain the SHA of its own commit; use implementation identity plus post-push publication identity.

## Workstream C — contract authority

Implement T20–T26. Generate proposals without approval. A missing upstream field is not fixed by pointing an assertion at a different legacy field.

## Workstream D — targeted backflow

Implement T30–T39. Expand the 63 occurrences, preserve 6 parent work orders, generate evidence/analysis/human packets, and create the eight pointer proposals. Do not increment resolved counts without independent implementation receipts.

## Workstream E — validation and publication

Implement T40–T47. Run all targeted tests, source-route, full pytest, deterministic double run and scope audit. Push `codex/r5-night02-contract-recovery` only. Verify remote equality and CI, then generate a readout and a non-trivial next queue.

## Workstream F — optional fallback

T50–T54 are valid engineering/analysis-automation work when the required work is waiting on external gates. They must not be used to claim Bundle17R activation.

## Discoveries

- 2026-07-19: bootstrap 在复制任务包前验证了 clean worktree；复制后的包与
  preflight 产物属于首个 Night02 workstream，因此 T00 的 clean 断言必须以
  bootstrap 前置检查为证据，不能在首个提交之后伪造重跑。
- 2026-07-19: Night01 tracked next queue 的 `f89a3ab...` 确实落后最终远端
  `4340945...` 一笔提交；Night02 使用 final remote HEAD 作为下一次基线解析源。
- 2026-07-19: 原始 Night02 queue 是 `v2_proposed`，不含逐任务 authority 字段；
  verified package digest 可为这 40 个包内任务生成独立 `v2` runtime queue，
  但不能替代后续自动生成 proposal 的 exact-hash 人审。

## Decisions

- Mission outcome 使用 `delivered / partial / blocked / failed / cutoff`，长期 Goal
  另由 `ProgramGoalPolicy` 管理；覆盖
  `test_r5_night_shift_outcome.py`、`test_r5_night_shift_goal_policy.py`。
- Git worktree path 与 branch 使用 `GitTarget` 两个字段并生成 argv；覆盖
  `test_r5_night_shift_git_targets.py`。
- tracked receipt 绑定 implementation commit/tree，post-push receipt 才绑定
  final remote HEAD；覆盖 `test_r5_night_shift_publication.py`、
  `test_r5_night_shift_digest.py`、`test_r5_night_shift_receipts.py`。
- v2 executable contract 采用 `contract_origin / path_authority /
  acceptance_authority / review_state / review_sha / resolution_claims` 并 fail
  closed；覆盖 `test_r5_night_shift_authority.py`、
  `test_r5_night_shift_contract_lint.py`。
- 命令不经 shell 执行，parser 允许引号内 Python 语句分号，但拒绝 shell chain、
  下载/网络能力和 mutating Git；覆盖 `test_r5_night_shift_command_safety.py`。
- proposal hash 只绑定候选合同正文，审批字段独立；内容变化立即使审批失效；覆盖
  `test_r5_night_shift_contract_proposals.py`、
  `test_r5_night_shift_review_handoff.py`。

## Remaining Work

- Workstream D: `ns02_t30`–`ns02_t39`。
- Workstream E/F: `ns02_t40`–`ns02_t54`。
- Research truth remains 6 pending work orders and 0/63 resolved blockers.

## Acceptance summary

The final mission cannot be `delivered` unless all `delivery_required: true` tasks in `task_queue.yaml` passed, the full regression and scope audit passed, the branch was pushed, remote SHA matched local SHA, and the readout preserved 0/63 unless real receipts prove otherwise.
