---
schema_version: "1"
task_id: "v1_governance_integration_cleanup_v2"
contract_path: "docs/codex_tasks/v1_governance_integration_cleanup_v2/CONTRACT.md"
contract_sha256: "c160ea2d676d5ba9a9893070be1a6e4418193cc508db07e71dd48cd0394a642f"
state: "running"
execution_branch: "codex/v1-governance-integration-cleanup"
source_baseline: "23fcd3b6b5ce3574661c4cfd306dadd782ad0717"
last_completed_phase: "P1"
next_phase: "P2"
last_validation: "pass"
updated_at: "2026-07-25T13:25:09+08:00"
---
# Start or resume this stage in a new Codex chat

本任务包是旧 v1 冻结包的 authorized amended v2。它只把 V-003 修正为 P1 七项、P2 八项、P3/final 九项的累加验证；发布模式 A、P1–P5、Night → Bundle11R–17R → old 002837 三个有序手动删除检查点和全部完成标准保持不变。只有 front matter 为 `state: ready`、启动块包含真实 contract hash 且 `--require-ready` 校验通过时才可启动。

最终 ready 后，在专用工作树 `C:\Projects\03_Investment_System_v1_governance_cleanup` 打开一个全新 Codex 聊天，并原样粘贴：

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/v1_governance_integration_cleanup_v2
Frozen contract: docs/codex_tasks/v1_governance_integration_cleanup_v2/CONTRACT.md
Expected contract SHA-256: c160ea2d676d5ba9a9893070be1a6e4418193cc508db07e71dd48cd0394a642f
Execution branch: codex/v1-governance-integration-cleanup
Source baseline: 23fcd3b6b5ce3574661c4cfd306dadd782ad0717
Engineering source candidate: f60f220ae252262a537c612ce193fc779901984b
Dedicated worktree: C:\Projects\03_Investment_System_v1_governance_cleanup

Read the complete applicable AGENTS.md instruction chain, CONTRACT.md, START_HERE.md, and every phase-required skill file before acting. Treat the frozen contract as the complete objective, constraints, authority, and definition of done. Do not rely on any previous chat, memory, project journal, Night queue, or unstated decision.

Validate package integrity and repository preflight, then resume from the earliest phase whose postconditions are not proven. After each phase, run its validators, inspect scope, update START_HERE.md, and create the specified Git checkpoint. Continue through P1-P5 until every completion criterion passes or a contract hard stop occurs.

Never edit the frozen contract, add phases, weaken a criterion, fabricate data or reviewer decisions, touch the user's dirty main worktree, perform recursive/bulk deletion, direct-push main, or publish beyond the authorization envelope. In P5, stop in order at the Night, Bundle, and old-002837 deletion waves with the exact per-file manifest; wait for the user to delete only that wave manually, then verify the complete Git status vector before continuing.
```

## Current checkpoint

- **State:** `running`
- **Last completed phase:** `P1`
- **Next phase:** `P2`
- **Latest validation:** `pass`（V-002、V-003 P1 90 passed、V-009）
- **Current blocker:** none。旧 v1 的 V-003 阶段依赖冲突已由本 amendment 明确解除；旧包及其 blocker checkpoint 保持只读。
- **Next safe action:** 创建 P1 checkpoint `refactor(v1): scope blockers to current research outputs`；确认 clean 后读取 P2 点名的人审契约与 tests，记录 P2 精确 mutation paths。

### P1 completion evidence

- Canonical fields and outcome derivation: `decision_semantics_version: current_goal_v1`, `impact_scope`, `active_disposition`, `affected_capabilities`, `blocks_current_goal`.
- Degradation ladder: direct disclosure → audited aggregate → bounded estimate/scenario → unknown/omit.
- Bundle11R–16R and R5-G1–R5-G11: removed from ordinary routing; retained evaluators require explicit inputs and cannot write canonical state.
- V-002: `reports/p1_6/r5_v1_governance_cleanup/validation/doc_drift.txt`.
- V-003 P1: `reports/p1_6/r5_v1_governance_cleanup/validation/governance_targeted.txt`.
- Active routing: `reports/p1_6/r5_v1_governance_cleanup/validation/active_routing_audit.yaml`.
- V-009: `reports/p1_6/r5_v1_governance_cleanup/validation/scope_audit.yaml`.

The Git commit containing this file is the checkpoint commit. Do not write that commit's own hash into this file.

## Checkpoint history

- 2026-07-25T11:57:27+08:00 — prior package `docs/codex_tasks/v1_governance_integration_cleanup/` 在 P1 前因 V-003 阶段依赖冲突硬停止；其 frozen hash 为 `a681812f9e91993d4a009ebcd972df1b06fc3f808323574387b84afa2ca3353e`，blocker checkpoint 为 `23fcd3b6b5ce3574661c4cfd306dadd782ad0717`。
- 2026-07-25T12:55:36+08:00 — 用户授权 amended v2；新包只拆分 V-003 为 P1 七项、P2 八项、P3/final 九项，并把 package baseline 固定为 amendment 前 checkpoint。旧包、工程目标、P1–P5、完成标准、发布与删除授权保持不变；尚未 finalize。
- 2026-07-25T13:10:43+08:00 — amended v2 已冻结并通过 `--require-ready`；contract SHA-256 为 `c160ea2d676d5ba9a9893070be1a6e4418193cc508db07e71dd48cd0394a642f`，setup checkpoint 为 `f41d99dc3685da6b1317da58b73beb23fc95135c`。V-001、用户主工作树只读快照与 P1 baseline 七项测试（61 passed）通过，开始 P1。
- 2026-07-25T13:25:09+08:00 — P1 scope-aware blocker/outcome、降级阶梯和 explicit capability-evaluator routing 已实现；V-002、V-003 P1（90 passed）、额外兼容测试（63 passed）、V-009 和 task-package integrity 通过，等待指定 P1 checkpoint。
