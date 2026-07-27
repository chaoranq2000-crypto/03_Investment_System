---
schema_version: "1"
task_id: "v1_governance_integration_cleanup"
contract_path: "docs/codex_tasks/v1_governance_integration_cleanup/CONTRACT.md"
contract_sha256: "a681812f9e91993d4a009ebcd972df1b06fc3f808323574387b84afa2ca3353e"
state: "blocked"
execution_branch: "codex/v1-governance-integration-cleanup"
source_baseline: "f60f220ae252262a537c612ce193fc779901984b"
last_completed_phase: "none"
next_phase: "P1"
last_validation: "fail"
updated_at: "2026-07-25T11:57:27+08:00"
---
# Start or resume this stage in a new Codex chat

本任务包已固定为发布模式 A，并已获得 Night → Bundle11R–17R → old 002837 三个有序手动删除检查点授权。只有 front matter 为 `state: ready`、启动块包含真实 contract hash 且 `--require-ready` 校验通过时才可启动。

最终 ready 后，在专用工作树 `C:\Projects\03_Investment_System_v1_governance_cleanup` 打开一个全新 Codex 聊天，并原样粘贴：

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/v1_governance_integration_cleanup
Frozen contract: docs/codex_tasks/v1_governance_integration_cleanup/CONTRACT.md
Expected contract SHA-256: a681812f9e91993d4a009ebcd972df1b06fc3f808323574387b84afa2ca3353e
Execution branch: codex/v1-governance-integration-cleanup
Source baseline: f60f220ae252262a537c612ce193fc779901984b
Dedicated worktree: C:\Projects\03_Investment_System_v1_governance_cleanup

Read the complete applicable AGENTS.md instruction chain, CONTRACT.md, START_HERE.md, and every phase-required skill file before acting. Treat the frozen contract as the complete objective, constraints, authority, and definition of done. Do not rely on any previous chat, memory, project journal, Night queue, or unstated decision.

Validate package integrity and repository preflight, then resume from the earliest phase whose postconditions are not proven. After each phase, run its validators, inspect scope, update START_HERE.md, and create the specified Git checkpoint. Continue through P1-P5 until every completion criterion passes or a contract hard stop occurs.

Never edit the frozen contract, add phases, weaken a criterion, fabricate data or reviewer decisions, touch the user's dirty main worktree, perform recursive/bulk deletion, direct-push main, or publish beyond the authorization envelope. In P5, stop in order at the Night, Bundle, and old-002837 deletion waves with the exact per-file manifest; wait for the user to delete only that wave manually, then verify the complete Git status vector before continuing.
```

## Current checkpoint

- **State:** `blocked`
- **Last completed phase:** `none`
- **Next phase:** `P1`
- **Latest validation:** package integrity 与 preflight 通过；V-003 精确命令非零退出并报告
  `tests/test_r5_final_report_review_semantics.py` 不存在、`no tests ran`。该文件虽可在 P1 新增，
  但同一命令还要求当前不存在且只在 P3 明确授权新增的
  `tests/test_r5_v1_policy_refresh_002837.py`。
- **Current blocker:** 冻结合同的 P1 mutation allowlist 只允许 7 个既有治理测试和新增
  final-review 测试；P1 又必须通过包含 P3 policy-refresh 测试的完整 V-003。P3 以前置
  P1/P2 checkpoint 通过为条件，因此无法在不越过阶段 allowlist、弱化 validator 或修改冻结
  合同的前提下证明 P1 postconditions。受影响阶段为 P1，受影响标准为 C-001/C-002，
  stop class 为 conflicting instructions / unverifiable completion criterion。专用 worktree
  在失败命令后仍 clean；用户主工作树仅做了只读状态快照。
- **Next safe action:** 保留本 v1 冻结包，创建并冻结 amended v2：把 V-003 拆成逐阶段累加的
  validator（P1 为 7 个既有测试，P2 加 final-review 测试，P3/final 再加 policy-refresh
  测试），然后从新的 ready 包启动。精确 unblock 问题：用户是否提供或授权准备上述 amended
  v2 task package？

The Git commit containing this file is the checkpoint commit. Do not write that commit's own hash into this file.

## Checkpoint history

- 2026-07-25T03:23:36+08:00 — 根据 V1/main、质量规则、002837 正式披露和历史目录引用审计创建草案；未 finalize，未授权执行或发布。
- 2026-07-25T03:47:03+08:00 — 修正 method 状态推导、三波 clean arm-wave checkpoint、durable ref 与发布前后远端状态；草案验证通过，唯一剩余 blocker 为 D-012 用户授权。
- 2026-07-25T04:02:00+08:00 — 用户选择发布模式 A，并批准 Night→Bundle11R–17R→old002837 三个手动删除检查点；删除全部 B 路径，准备冻结。
- 2026-07-25T11:57:27+08:00 — execute preflight 通过后在 P1 前硬停止：V-003 要求 P1
  读取仅由 P3 mutation allowlist 授权新增的 policy-refresh 测试，形成不可满足的阶段依赖；
  未修改冻结合同、实现、测试、研究数据或用户主工作树。
