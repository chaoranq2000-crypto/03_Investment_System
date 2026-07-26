---
schema_version: "1"
task_id: "v1_governance_integration_cleanup_v6"
contract_path: "docs/codex_tasks/v1_governance_integration_cleanup_v6/CONTRACT.md"
contract_sha256: "f5326c3c322fa3e0a319e36c032be4e169ede44acf57cce19bf63cf97b7ce3ec"
state: "blocked"
execution_branch: "codex/v1-governance-integration-cleanup"
source_baseline: "46a55d17f120496b6114c55e1d79e96adaef8378"
last_completed_phase: "P4"
next_phase: "P5"
last_validation: "fail"
updated_at: "2026-07-27T00:09:50+08:00"
---
# Start or resume this stage in a new Codex chat

本任务包是冻结 v5 的最小 authorized amended v6。它只改变 Night 删除 actor：Night=`codex_exact_manifest_one_file_at_a_time`，Bundle 与 old002837 仍=`user_manual_only`；A.1–A.7 权限、历史 snapshot `312adc...`、1386 与 `680/205/501` 精确路径集合/bytes/hash、P1–P4 结论、P1–P5 数量、完成标准、发布模式 A、Night → Bundle11R–17R → old 002837 顺序和全部验证强度保持不变。v6 还要求 A.2 tool/manifests/tests/receipts 重绑 wave-specific actor，并在验证后重新 arm Night；旧 `82f7d37...` 只作历史 arm。只有 front matter 为 `state: ready`、启动块包含真实 contract hash 且 `--require-ready` 校验通过时才可启动。

最终 ready 后，在专用工作树 `C:\Projects\03_Investment_System_v1_governance_cleanup` 打开一个全新 Codex 聊天，并原样粘贴：

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/v1_governance_integration_cleanup_v6
Frozen contract: docs/codex_tasks/v1_governance_integration_cleanup_v6/CONTRACT.md
Expected contract SHA-256: f5326c3c322fa3e0a319e36c032be4e169ede44acf57cce19bf63cf97b7ce3ec
Execution branch: codex/v1-governance-integration-cleanup
Source baseline: 46a55d17f120496b6114c55e1d79e96adaef8378
Historical cleanup snapshot: 312adc73821706b0b7ca6aa00e80ee608bd10b32
Engineering source candidate: f60f220ae252262a537c612ce193fc779901984b
Dedicated worktree: C:\Projects\03_Investment_System_v1_governance_cleanup

Read the complete applicable AGENTS.md instruction chain, CONTRACT.md, START_HERE.md, and every phase-required skill file before acting. Treat the frozen contract as the complete objective, constraints, authority, and definition of done. Do not rely on any previous chat, memory, project journal, Night queue, or unstated decision.

Validate package integrity and repository preflight, then resume from the earliest phase whose postconditions are not proven. After each phase, run its validators, inspect scope, update START_HERE.md, and create the specified Git checkpoint. Continue through P1-P5 until every completion criterion passes or a contract hard stop occurs.

Never edit the frozen contract, add phases, weaken a criterion, fabricate data or reviewer decisions, touch the user's dirty main worktree, use recursive/wildcard/directory/collection/out-of-manifest deletion, direct-push main, or publish beyond the authorization envelope. In P5, keep Night → Bundle → old-002837 order: only Night may be deleted by Codex after a new v6 clean arm and exact preflight, one literal file at a time; stop at Bundle and old-002837 for the user to delete only that wave manually, then verify the complete raw NUL Git status/name-status vectors before continuing.
```

## Current checkpoint

- **State:** `blocked`
- **Last completed phase:** `P4`
- **Next phase:** `P5`
- **Latest validation:** `fail`。v6 contract 与 package integrity、A.2 actor/tool/manifest 静态审计、Night 680 项存在性/普通文件/非 reparse 校验、全量 1,386-file byte-for-byte restore 和 V-006 `26 passed in 638.56s` 均通过；但随后完整 pytest 为 `1 failed, 1353 passed, 2 skipped in 800.63s`。唯一失败是 `tests/test_r5_v1_root_policy_migration.py::test_receipt_is_deterministic_aggregate_only_and_checked_in`：`805b8e3...` 曾把 checked-in `blocker_root_reconciliation.yaml` 改成 `P5_pre_delete`/2026-07-26 并追加非派生 `final_revalidation`，却未同步仍确定性渲染 `P4`/2026-07-25 的 validator。此前 `1349 passed, 2 skipped` 发生在该回执写入之前，不能证明当前 checkpoint。没有 wave 被删除。
- **Current blocker:** frozen v6 的 exact amendment 和 D-017 只允许 A.2 identity/actor rebinding，以及 A.1 `governance_cleanup_readout.md` 的 actor/checkpoint metadata；不授权修复 `validation/blocker_root_reconciliation.yaml`。所需修复超出 v6 mutation semantics，按 P5/required-validator stop 条款 hard stop；不得创建 actor migration checkpoint 或新 Night arm。
- **Prior hard-stop evidence:** v4 checkpoints `0f582599...` 与 `f1dafeb...` 保留历史冲突证据；v5 已修复三项 A.7 冲突以及 A.2 retained-dependency/unknown-classification 缺陷。旧 `82f7d37...` arm 因其后存在 policy/v6 commits 已失去 current-wave-parent 资格。
- **User-main protection snapshot:** HEAD `a345fafb522300831ed4206d35fa17f44570cb1f`；批准的新完整 `porcelain=v1 -z -uall` 向量为 130 records、9156 bytes、SHA-256 `1b21ac246cb2ad4b055f5a264503fb1fad8fe9edae153e25c9cd6d19d4a719c0`，tracked-only 为 20 records、1025 bytes、SHA-256 `3ab441f68037823866029eb2136149a807f6382755966daf96d33a85b965609b`。v6 准备时补丁工具的两份未跟踪草稿曾误落该树，已按两个明确文件路径逐一撤销；HEAD 与两组 raw NUL 向量随后精确恢复。不得再写入、清理、修复、吸收或提交其中内容。
- **Next safe action:** 用户已于 2026-07-27 明确批准最小 v7 修订包；先把本 v6 blocked 状态与 A.2 actor 重绑工作保存为干净 checkpoint，再以该 commit 为 v7 source baseline。v7 只授权把 `reports/p1_6/r5_v1_governance_cleanup/validation/blocker_root_reconciliation.yaml` 重渲染为现有 validator 的精确确定性输出（`phase=P4`、`checked_at=2026-07-25`、移除非派生 `final_revalidation`），不修改 validator/test、不降低断言；随后重跑 V-005、V-006、full restore 和 full pytest。新 v7 验证与 clean arm 前不得删除 Night。

### P5 pre-delete completion evidence

- A.7 exact paths: `tests/test_r5_night_shift_ci_contract.py`, `tests/test_r5_night_shift_night03_ci_contract.py`, `tests/test_r5_night_shift_night04_ci_contract.py`; each now contains equal-strength CI retirement assertions and remains in the Night manifest.
- Historical cleanup inventory: 1,386 files / 9,787,412 content bytes / 121,264 path-vector bytes / SHA-256 `974d45610144d616f69c3c368d9ea1a0a27d66601a24f748aa8148e2ee702f33`.
- Wave aggregates: Night 680 / 4,480,614 / `1ec2f42b84c1078f6b26caa377e9c1fb3efff9221196bc2e02bd819588a59c59`; Bundle 205 / 1,770,109 / `fc8912dfe6d20d92bd8fe907d4400ae90b724826a7c468ba5286232dc3b3363a`; old002837 501 / 3,536,689 / `73d0a405b928fa3fa615d5b0d527f16f7c1182bb16239fb9ef89266d9868862f`.
- Reference graph: `reference_count=0`, `unknown_classification_count=0`, A.7 overlap exact and all Night, retained/protected overlap 0.
- Restore proof: all 1,386 Git blobs recovered byte-for-byte; final root `C:\Users\Q\AppData\Local\Temp\r5_v1_historical_restore_final_a5b1d2db3a3b4eb78631eba15a2ef2a8`; `cat_file_e_verified`, `content_hash_verified`, `full_restore_verified` and `byte_for_byte_match` all true.
- Focused validators: V-003 194 passed; V-004 16 passed with equal digests; V-005 18 passed; V-006 21 passed; A.7 4 passed; source route `decision=pass`, blocking 0.
- Full repository pytest: `1349 passed, 2 skipped in 650.20s`; no failures/errors and no new skip/xfail/mock/collection-ignore.
- Scope: only A.1/A.2/A.7 paths changed; no deletion, untracked path, frozen-contract change, raw-data change or user-main write.

### P5 Night exact-manifest candidate (not armed under v6)

- Wave: `night`（顺序 1/3）
- Deletion actor: `codex_exact_manifest_one_file_at_a_time`
- Codex deletion authorization: `true` for Night only; Bundle/old002837 remain `false`
- `wave_parent_commit`: `PENDING_NEW_V6_ARM`；旧 `82f7d37a10a9677af631c1a5863661a64df3270b` 不得复用。新 v6 actor migration 全部验证通过后，创建本文件所在 clean arm commit，再由 `git rev-parse HEAD` 取得并写入 deletion receipt，不把提交自身 SHA 写回本文件。
- Expected deletion count: 680
- Expected content bytes: 4,480,614
- Expected ordinal UTF-8 NUL path-vector bytes: 55,881
- Expected ordinal UTF-8 NUL path-vector SHA-256: `1ec2f42b84c1078f6b26caa377e9c1fb3efff9221196bc2e02bd819588a59c59`
- Manifest source: `reports/p1_6/r5_v1_governance_cleanup/historical_cleanup_manifest.yaml`
- Restore source: each manifest row's exact `baseline_commit:path`, `blob_oid`, byte count and content SHA-256; final full-restore receipt is `reports/p1_6/r5_v1_governance_cleanup/validation/historical_decoupling.yaml`.
- Codex rule: 仅在新 v6 arm、contract/AGENTS/manifest/recovery/status 全部预检通过后，按下列 ordinal manifest 每次删除一个已经解析的 literal regular file；任何错误或漂移立即停止。禁止 wildcard、recursive、directory、symlink/reparse、collection、Git clean/reset/checkout 或清单外删除。
- Readiness rule: actor migration 与新 arm 完成后先向协调任务报告；真正删除时不得提前 stage/commit，680 项全部缺失且完整 raw NUL status/name-status vectors 精确等于 manifest 后才可显式 stage。

#### Night exact absolute per-file manifest

1. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\BF2_INPUT_HANDOFF.md`
2. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\CODEX_SCHEDULED_TASK_PROMPT.md`
3. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\EXECPLAN.md`
4. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\OVERNIGHT_MISSION.md`
5. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\PACKAGE_MANIFEST.yaml`
6. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\SAFETY_AND_GIT_POLICY.md`
7. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\START_HERE.md`
8. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\acceptance_matrix.yaml`
9. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\contracts\morning_readout.schema.json`
10. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\contracts\night_shift_task_queue.schema.json`
11. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\task_cards\T00_PREFLIGHT.md`
12. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\task_cards\T10_BF2_INVENTORY.md`
13. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\task_cards\T20_CONTRACT_LOADER.md`
14. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\task_cards\T30_STATE_LOCK_RESUME.md`
15. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\task_cards\T40_ACCEPTANCE_RECEIPTS.md`
16. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\task_cards\T50_BF2_SEED_ADAPTER.md`
17. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\task_cards\T60_SAFE_PILOT.md`
18. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\task_cards\T70_REGRESSION_DETERMINISM.md`
19. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\task_cards\T80_READOUT_NEXT_QUEUE.md`
20. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\task_cards\T90_COMMIT_PUSH.md`
21. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\task_queue.yaml`
22. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\templates\failure_packet.md`
23. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\templates\morning_readout.md`
24. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\templates\next_night_queue.yaml`
25. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\tools\build_input_handoff.py`
26. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\tools\preflight_source_worktree.ps1`
27. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_01\tools\verify_package.py`
28. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_02_20260720\ACCEPTANCE_MATRIX.md`
29. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_02_20260720\AGENT_PROMPT.md`
30. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_02_20260720\COMPLETION_AUDIT.md`
31. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_02_20260720\CONTRACT_AUTHORITY_POLICY.md`
32. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_02_20260720\EXECPLAN.md`
33. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_02_20260720\OVERNIGHT_MISSION.md`
34. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_02_20260720\README.md`
35. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_02_20260720\REVIEW_HANDOFF_TEMPLATE.yaml`
36. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_02_20260720\SAFETY_BOUNDARIES.md`
37. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_02_20260720\SOURCE_STATE.yaml`
38. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_02_20260720\WINDOWS_RUNBOOK.md`
39. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_02_20260720\bootstrap_worktree.ps1`
40. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_02_20260720\pointer_occurrences.yaml`
41. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_02_20260720\scheduled_task_prompt.txt`
42. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_02_20260720\task_queue.yaml`
43. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_02_20260720\tools\verify_package.py`
44. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\AGENT_PROMPT.md`
45. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\CHECK_REPORT.md`
46. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\EXECPLAN.md`
47. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\OVERNIGHT_MISSION.md`
48. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\PACKAGE_MANIFEST.yaml`
49. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\README.md`
50. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\SAFETY_AND_GIT_POLICY.md`
51. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\START_HERE.md`
52. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\WINDOWS_RUNBOOK.md`
53. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\acceptance_matrix.yaml`
54. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\bootstrap_worktree.ps1`
55. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\contracts\outcome_contract.yaml`
56. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\contracts\research_queue_contract.yaml`
57. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\scheduled_task_prompt.txt`
58. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\source_contract.yaml`
59. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\task_cards\T00_T07_BASELINE.md`
60. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\task_cards\T10_T17_DECISION_INTAKE.md`
61. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\task_cards\T20_T27_RESOLUTION_ENGINE.md`
62. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\task_cards\T30_T37_TARGETED_BACKFLOW.md`
63. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\task_cards\T40_T47_VALIDATION_PUBLICATION.md`
64. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\task_queue.yaml`
65. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\templates\blank_decision_manifest.yaml`
66. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\tools\inspect_night02_outputs.py`
67. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_03_20260721\tools\verify_package.py`
68. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\EXECPLAN.md`
69. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\OVERNIGHT_MISSION.md`
70. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\PACKAGE_MANIFEST.yaml`
71. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\README.md`
72. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\SAFETY_AND_GIT_POLICY.md`
73. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\START_HERE.md`
74. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\WINDOWS_RUNBOOK.md`
75. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\bootstrap_worktree.ps1`
76. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\contracts\outcome_contract.yaml`
77. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\contracts\pointer_prevalidation_contract.yaml`
78. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\contracts\review_bundle_contract.yaml`
79. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\scheduled_task_prompt.txt`
80. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\source_contract.yaml`
81. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\task_cards\T00_T09_BASELINE.md`
82. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\task_cards\T10_T19_REVIEW_CONTROL.md`
83. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\task_cards\T20_T31_REVIEW_ACCELERATION.md`
84. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\task_cards\T32_T43_POINTER_PREVALIDATION.md`
85. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\task_cards\T44_T51_CONDITIONAL_EXECUTION.md`
86. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\task_cards\T52_T59_VALIDATION_PUBLICATION.md`
87. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\task_queue.yaml`
88. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\templates\blank_batch_decision_manifest.yaml`
89. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\templates\reviewer_decision_sheet.md`
90. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\tools\inspect_night03_outputs.py`
91. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_04_20260722\tools\verify_package.py`
92. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_05_20260723\EXECPLAN.md`
93. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_05_20260723\PACKAGE_MANIFEST.yaml`
94. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_05_20260723\README.md`
95. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_05_20260723\inputs\night04_remote_delivery_receipt.json`
96. `C:\Projects\03_Investment_System_v1_governance_cleanup\codex_tasks\night_shift\r5_overnight_05_20260723\task_queue.yaml`
97. `C:\Projects\03_Investment_System_v1_governance_cleanup\config\r5_night_shift.yaml`
98. `C:\Projects\03_Investment_System_v1_governance_cleanup\config\r5_night_shift_task_schema.json`
99. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_01_20260719\bf2_compatibility_map.md`
100. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_01_20260719\bf2_seed_summary.md`
101. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_01_20260719\delivery_receipt.md`
102. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_01_20260719\morning_readout.md`
103. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_01_20260719\next_night_queue.yaml`
104. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_01_20260719\no_safe_pilot_backflow.md`
105. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_01_20260719\pilot_result.md`
106. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_01_20260719\preflight.md`
107. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_01_20260719\validation.md`
108. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\backflow\analysis_workbooks.md`
109. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\backflow\analysis_workbooks.yaml`
110. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\backflow\dependency_dag.json`
111. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\backflow\evidence_requests.md`
112. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\backflow\evidence_requests.yaml`
113. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\backflow\expanded_queue.yaml`
114. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\backflow\expansion_receipt.json`
115. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\backflow\fallback_backlog.yaml`
116. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\backflow\human_gate_handoffs.yaml`
117. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\backflow\occurrence_inventory.json`
118. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\backflow\pointer_contract_proposals.md`
119. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\backflow\pointer_contract_proposals.yaml`
120. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\backflow\queue_metrics.json`
121. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\completion_audit.json`
122. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\completion_audit.md`
123. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\contract\authority_readout.md`
124. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\contract\authorized_task_queue.yaml`
125. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\contract\contract_lint.json`
126. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\mission_completion_receipt.json`
127. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\mission_state.yaml`
128. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\morning_readout.json`
129. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\morning_readout.md`
130. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\next_night_queue.yaml`
131. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\preflight\preflight.md`
132. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\preflight\source_state.json`
133. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\publication\implementation_delivery_receipt.json`
134. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t00_exact_baseline_preflight.json`
135. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t01_night01_completion_audit.json`
136. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t02_windows_path_branch_guard.json`
137. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t03_stale_baseline_detector.json`
138. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t10_mission_outcome_model.json`
139. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t11_no_safe_pilot_not_success.json`
140. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t12_program_goal_close_policy.json`
141. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t13_open_mission_resume.json`
142. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t14_two_phase_publication.json`
143. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t15_digest_integrity.json`
144. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t20_contract_authority_schema.json`
145. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t21_contract_lint.json`
146. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t22_acceptance_command_safety.json`
147. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t23_task_diff_scope_guard.json`
148. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t24_contract_proposal_generator.json`
149. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t25_review_packet_hash_lock.json`
150. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t26_semantic_contract_router.json`
151. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t30_occurrence_queue_expander.json`
152. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t31_dependency_dag.json`
153. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t32_evidence_request_packets.json`
154. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t33_analysis_workbooks.json`
155. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t34_human_gate_handoffs.json`
156. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t35_pointer_contract_proposals.json`
157. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t36_fallback_engineering_backlog.json`
158. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t37_failure_spawn_retry.json`
159. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t38_queue_metrics_and_capacity.json`
160. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t39_pilot_eligibility_gate.json`
161. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t40_adversarial_test_matrix.json`
162. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t41_crash_cutoff_resume_tests.json`
163. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t42_ci_integration.json`
164. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t43_bf2_dry_run_truth_preservation.json`
165. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t44_determinism_double_run.json`
166. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t45_full_regression_scope_audit.json`
167. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t46_commit_push_remote_ci.json`
168. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t47_morning_readout_next_queue.json`
169. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t50_golden_case_inventory.json`
170. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t51_semantic_quality_negative_fixtures.json`
171. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t52_driver_contract_gap_matrix.json`
172. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t53_bundle18_readiness_precheck.json`
173. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\ns02_t54_next_mission_seed.json`
174. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\receipts\task_acceptance_summary.json`
175. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\strategic\bundle18_precheck.yaml`
176. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\strategic\driver_contract_gap_matrix.md`
177. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\strategic\driver_contract_gap_matrix.yaml`
178. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\strategic\golden_case_inventory.md`
179. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\strategic\golden_case_inventory.yaml`
180. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\strategic\night03_seed.yaml`
181. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\validation\bf2_dry_run_receipt.json`
182. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\validation\determinism_receipt.json`
183. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\validation\full_regression.json`
184. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\validation\readout_baseline.json`
185. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_02_20260720\validation\scope_audit.json`
186. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\candidates\analysis_candidates.md`
187. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\candidates\analysis_candidates.yaml`
188. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\candidates\dependency_unlock_matrix.md`
189. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\candidates\dependency_unlock_matrix.yaml`
190. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\candidates\evidence_candidates.md`
191. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\candidates\evidence_candidates.yaml`
192. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\candidates\human_gate_handoffs.md`
193. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\candidates\human_gate_handoffs.yaml`
194. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\candidates\pointer_review_index.md`
195. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\candidates\pointer_review_index.yaml`
196. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\decisions\analysis_adapter_contract.yaml`
197. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\decisions\authority_matrix.yaml`
198. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\decisions\blank_decision_manifest.yaml`
199. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\decisions\decision_manifest_schema.json`
200. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\decisions\decision_validation_contract.md`
201. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\decisions\evidence_adapter_contract.yaml`
202. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\decisions\human_gate_adapter_contract.yaml`
203. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\decisions\pointer_approval_adapter_contract.yaml`
204. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\decisions\resolution_policy.yaml`
205. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\execution\approved_input_consumption.json`
206. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\execution\command_safety_contract.yaml`
207. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\execution\dependency_unblock_contract.yaml`
208. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\execution\occurrence_state_contract.yaml`
209. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\execution\parent_aggregation_contract.yaml`
210. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\execution\pointer_executor_contract.yaml`
211. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\execution\replay_contract.yaml`
212. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\execution\resolution_receipt_schema.json`
213. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\execution\sandbox_contract.yaml`
214. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\mission_state.yaml`
215. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\morning_readout.json`
216. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\morning_readout.md`
217. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\next_night_queue.yaml`
218. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\preflight\night02_input_manifest.json`
219. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\preflight\night02_receipt_audit.json`
220. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\preflight\night02_receipt_audit.md`
221. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\preflight\preflight.md`
222. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\preflight\remote_ci_reconciliation.json`
223. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\preflight\remote_ci_reconciliation.md`
224. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\preflight\source_state.json`
225. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\preflight\source_state.md`
226. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\progress\blocker_ledger.json`
227. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\progress\blocker_ledger.md`
228. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\progress\four_case_dashboard.md`
229. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\progress\four_case_dashboard.yaml`
230. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\publication\tracked_delivery_receipt.json`
231. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\queue\authoritative_queue_lock.json`
232. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\queue\authoritative_queue_snapshot.yaml`
233. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\queue\lineage_audit.json`
234. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\queue\taxonomy_audit.json`
235. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\queue\taxonomy_audit.md`
236. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\queue\truth_snapshot.json`
237. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t00_exact_baseline_preflight.json`
238. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t01_night02_completion_receipt_audit.json`
239. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t02_remote_ci_pr_workspace_reconcile.json`
240. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t03_night02_output_hash_manifest.json`
241. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t04_import_authoritative_69_queue.json`
242. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t05_queue_taxonomy_count_audit.json`
243. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t06_lineage_and_stale_source_guard.json`
244. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t07_truth_snapshot_and_outcome_model.json`
245. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t10_decision_manifest_schema.json`
246. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t11_exact_hash_decision_validator.json`
247. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t12_authority_reviewer_identity_guard.json`
248. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t13_evidence_acceptance_adapter.json`
249. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t14_analysis_decision_adapter.json`
250. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t15_human_exact_hash_adapter.json`
251. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t16_pointer_contract_approval_adapter.json`
252. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t17_false_resolution_guard.json`
253. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t20_occurrence_state_transition_engine.json`
254. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t21_parent_aggregation_engine.json`
255. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t22_dependency_unblock_engine.json`
256. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t23_occurrence_diff_sandbox.json`
257. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t24_acceptance_command_safety.json`
258. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t25_approved_pointer_pilot_executor.json`
259. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t26_resolution_receipt_generation_lock.json`
260. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t27_idempotent_resume_and_replay.json`
261. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t30_consume_available_approved_inputs.json`
262. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t31_evidence_candidate_enrichment.json`
263. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t32_analysis_candidate_enrichment.json`
264. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t33_human_gate_packet_refresh.json`
265. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t34_pointer_proposal_review_index.json`
266. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t35_dependency_unlock_matrix.json`
267. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t36_four_case_progress_dashboard.json`
268. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t37_blocker_delta_unresolved_ledger.json`
269. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t40_adversarial_decision_and_resolution_tests.json`
270. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t41_determinism_double_run.json`
271. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t42_crash_cutoff_resume_tests.json`
272. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t43_full_regression_source_route_scope_audit.json`
273. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t44_ci_contract_and_workflow_verification.json`
274. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t45_workstream_commit_push.json`
275. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t46_final_remote_ci_receipt.json`
276. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\receipts\ns03_t47_morning_readout_and_night04_queue.json`
277. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\validation\adversarial_matrix.json`
278. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\validation\ci_contract.json`
279. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\validation\crash_resume_receipt.json`
280. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\validation\determinism_receipt.json`
281. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\validation\full_regression.json`
282. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_03_20260721\validation\scope_audit.json`
283. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\execution\analysis_execution_receipts.json`
284. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\execution\decision_replay_ledger.json`
285. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\execution\dependency_recompute.json`
286. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\execution\evidence_execution_receipts.json`
287. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\execution\human_gate_receipts.json`
288. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\execution\parent_recompute.json`
289. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\execution\pointer_execution_receipts.json`
290. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\execution\startup_decision_consumption.json`
291. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\external_decisions\README.md`
292. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\mission_state.yaml`
293. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\morning_readout.json`
294. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\morning_readout.md`
295. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\next_night_queue.yaml`
296. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\batch_simulation.yaml`
297. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\command_safety.yaml`
298. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\conditional_execution_contract.yaml`
299. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\conflict_matrix.yaml`
300. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\diff_ceiling_receipt.json`
301. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\dry_run_patch_index.yaml`
302. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\dry_run_truth_receipt.json`
303. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\generation_lock_previews.yaml`
304. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\patches\ns02_t30_occ_3caf2ad00e1b6285.patch`
305. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\patches\ns02_t30_occ_3caf2ad00e1b6285.patch.b64`
306. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\patches\ns02_t30_occ_6b198842cf80755a.patch`
307. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\patches\ns02_t30_occ_6b198842cf80755a.patch.b64`
308. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\patches\ns02_t30_occ_99e77539490b01ad.patch`
309. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\patches\ns02_t30_occ_99e77539490b01ad.patch.b64`
310. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\patches\ns02_t30_occ_c7f5c80f4b2e7a9c.patch`
311. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\patches\ns02_t30_occ_c7f5c80f4b2e7a9c.patch.b64`
312. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\patches\ns02_t30_occ_c8af30bbe2f10e8a.patch`
313. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\patches\ns02_t30_occ_c8af30bbe2f10e8a.patch.b64`
314. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\patches\ns02_t30_occ_d2ef6aeae1113c9c.patch`
315. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\patches\ns02_t30_occ_d2ef6aeae1113c9c.patch.b64`
316. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\patches\ns02_t30_occ_db819651b1640db8.patch`
317. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\patches\ns02_t30_occ_db819651b1640db8.patch.b64`
318. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\patches\ns02_t30_occ_e3fefccd3e77fd5a.patch`
319. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\patches\ns02_t30_occ_e3fefccd3e77fd5a.patch.b64`
320. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\path_resolution.yaml`
321. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\rollback_receipt.json`
322. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\sandbox_manager_contract.yaml`
323. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\pointer_prevalidation\targeted_test_receipts.json`
324. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\preflight\night03_input_manifest.json`
325. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\preflight\night03_package_integrity.json`
326. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\preflight\night03_receipt_audit.json`
327. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\preflight\non_self_reference_audit.json`
328. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\preflight\remote_ci_reconciliation.json`
329. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\preflight\source_state.json`
330. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\progress\blocker_ledger.json`
331. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\progress\blocker_ledger.md`
332. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\publication\tracked_delivery_receipt.json`
333. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\queue\authoritative_queue_snapshot.yaml`
334. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\queue\lineage_audit.json`
335. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\queue\taxonomy_audit.json`
336. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\queue\truth_snapshot.json`
337. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t00.json`
338. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t01.json`
339. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t02.json`
340. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t03.json`
341. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t04.json`
342. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t05.json`
343. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t06.json`
344. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t07.json`
345. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t08.json`
346. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t09.json`
347. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t10.json`
348. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t11.json`
349. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t12.json`
350. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t13.json`
351. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t14.json`
352. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t15.json`
353. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t16.json`
354. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t17.json`
355. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t18.json`
356. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t19.json`
357. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t20.json`
358. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t21.json`
359. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t22.json`
360. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t23.json`
361. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t24.json`
362. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t25.json`
363. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t26.json`
364. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t27.json`
365. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t28.json`
366. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t29.json`
367. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t30.json`
368. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t31.json`
369. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t32.json`
370. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t33.json`
371. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t34.json`
372. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t35.json`
373. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t36.json`
374. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t37.json`
375. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t38.json`
376. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t39.json`
377. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t40.json`
378. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t41.json`
379. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t42.json`
380. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t43.json`
381. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t44.json`
382. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t45.json`
383. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t46.json`
384. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t47.json`
385. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t48.json`
386. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t49.json`
387. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t50.json`
388. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t51.json`
389. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t52.json`
390. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t53.json`
391. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t54.json`
392. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t55.json`
393. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t56.json`
394. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\receipts\ns04_t57.json`
395. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_acceleration\analysis_review_briefs.yaml`
396. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_acceleration\counterevidence_index.yaml`
397. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_acceleration\downstream_impact.yaml`
398. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_acceleration\evidence_claim_diff_index.yaml`
399. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_acceleration\evidence_review_briefs.yaml`
400. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_acceleration\first_parent_path.yaml`
401. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_acceleration\human_review_briefs.yaml`
402. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_acceleration\max_unlock_path.yaml`
403. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_acceleration\pointer_review_briefs.yaml`
404. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_acceleration\review_groups.yaml`
405. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_acceleration\reviewer_dashboard.html`
406. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_acceleration\reviewer_dashboard.md`
407. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_acceleration\reviewer_dashboard.yaml`
408. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_acceleration\unblock_leverage.yaml`
409. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\batch_decision_schema.json`
410. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\index.yaml`
411. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_04343acd916afae4.yaml`
412. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_101f0195f0c5cf37.yaml`
413. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_1842382e6647f17d.yaml`
414. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_1977687ea7bce884.yaml`
415. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_23259d462e4ca0f3.yaml`
416. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_2c030a28f8631544.yaml`
417. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_3139481aee5c01e0.yaml`
418. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_3caf2ad00e1b6285.yaml`
419. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_3d282b4ad0ca31e2.yaml`
420. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_6491a19059d9ec6c.yaml`
421. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_6870f1ec5d1048be.yaml`
422. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_6b198842cf80755a.yaml`
423. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_6cd0e0bd57166a21.yaml`
424. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_6d2b87d81881062e.yaml`
425. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_6ff83cb834d7176d.yaml`
426. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_7213df41458cf67d.yaml`
427. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_76d9fbbac37b50a6.yaml`
428. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_7745e52b12c07f1c.yaml`
429. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_7a3640d70206502d.yaml`
430. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_86fb71b6c845c94f.yaml`
431. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_97d3e4a3c0388529.yaml`
432. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_99e77539490b01ad.yaml`
433. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_9fe0bbfe8ab9bb7d.yaml`
434. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_a88a58ab2685ee6e.yaml`
435. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_a9673677adb3ef8a.yaml`
436. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_ab0f8aac8f21f0db.yaml`
437. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_ab6b62516df0a0f1.yaml`
438. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_b52cbf88aff2c105.yaml`
439. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_be4e0eb69d196ff7.yaml`
440. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_becffa9c7cb6d886.yaml`
441. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_c7f5c80f4b2e7a9c.yaml`
442. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_c8af30bbe2f10e8a.yaml`
443. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_cdf02c368ebec0a7.yaml`
444. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_d2ef6aeae1113c9c.yaml`
445. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_db819651b1640db8.yaml`
446. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_dc67ef1afb1051ef.yaml`
447. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_e3fefccd3e77fd5a.yaml`
448. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_e48b0cd43634c242.yaml`
449. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_e855cd5fb843f9bf.yaml`
450. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_e95d9ae85fb2fba0.yaml`
451. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_eb221be0020f7038.yaml`
452. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_ee055856e18cd3f4.yaml`
453. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\blank_decision_bundles\ns02_t30_occ_f9fff3f413f6c43c.yaml`
454. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\candidate_registry.yaml`
455. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\conflict_policy.yaml`
456. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\human_field_integrity.json`
457. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\inbox_polling_contract.yaml`
458. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\partial_acceptance_contract.yaml`
459. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packet_contract.yaml`
460. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_04343acd916afae4.yaml`
461. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_101f0195f0c5cf37.yaml`
462. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_1842382e6647f17d.yaml`
463. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_1977687ea7bce884.yaml`
464. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_23259d462e4ca0f3.yaml`
465. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_2c030a28f8631544.yaml`
466. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_3139481aee5c01e0.yaml`
467. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_3caf2ad00e1b6285.yaml`
468. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_3d282b4ad0ca31e2.yaml`
469. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_6491a19059d9ec6c.yaml`
470. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_6870f1ec5d1048be.yaml`
471. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_6b198842cf80755a.yaml`
472. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_6cd0e0bd57166a21.yaml`
473. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_6d2b87d81881062e.yaml`
474. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_6ff83cb834d7176d.yaml`
475. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_7213df41458cf67d.yaml`
476. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_76d9fbbac37b50a6.yaml`
477. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_7745e52b12c07f1c.yaml`
478. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_7a3640d70206502d.yaml`
479. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_86fb71b6c845c94f.yaml`
480. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_97d3e4a3c0388529.yaml`
481. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_99e77539490b01ad.yaml`
482. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_9fe0bbfe8ab9bb7d.yaml`
483. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_a88a58ab2685ee6e.yaml`
484. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_a9673677adb3ef8a.yaml`
485. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_ab0f8aac8f21f0db.yaml`
486. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_ab6b62516df0a0f1.yaml`
487. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_b52cbf88aff2c105.yaml`
488. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_be4e0eb69d196ff7.yaml`
489. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_becffa9c7cb6d886.yaml`
490. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_c7f5c80f4b2e7a9c.yaml`
491. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_c8af30bbe2f10e8a.yaml`
492. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_cdf02c368ebec0a7.yaml`
493. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_d2ef6aeae1113c9c.yaml`
494. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_db819651b1640db8.yaml`
495. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_dc67ef1afb1051ef.yaml`
496. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_e3fefccd3e77fd5a.yaml`
497. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_e48b0cd43634c242.yaml`
498. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_e855cd5fb843f9bf.yaml`
499. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_e95d9ae85fb2fba0.yaml`
500. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_eb221be0020f7038.yaml`
501. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_ee055856e18cd3f4.yaml`
502. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\review_packets\ns02_t30_occ_f9fff3f413f6c43c.yaml`
503. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\reviewer_authority_contract.yaml`
504. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\review_control\stale_hash_policy.yaml`
505. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\validation\adversarial_matrix.json`
506. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\validation\ci_contract.json`
507. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\validation\crash_resume_receipt.json`
508. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\validation\determinism_receipt.json`
509. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\validation\full_regression.json`
510. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_04_20260722\validation\scope_audit.json`
511. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\execution\decision_intake.json`
512. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\execution\decision_replay_ledger.json`
513. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\execution\recompute_summary.json`
514. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\execution\typed_execution_summary.json`
515. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\external_decisions\README.md`
516. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\external_decisions\external_authority_registry.template.yaml`
517. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\mission_state.yaml`
518. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\morning_readout.json`
519. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\morning_readout.md`
520. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\next_night_queue.yaml`
521. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\preflight\source_git_manifest.json`
522. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\preflight\source_preflight.json`
523. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\progress\blocker_ledger.json`
524. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\progress\change_log.json`
525. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\publication\tracked_delivery_receipt.json`
526. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\review\review_wave_plan.yaml`
527. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\validation\ci_contract.json`
528. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\validation\full_regression.json`
529. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\validation\scope_audit.json`
530. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\validation\source_route_quality_report.yaml`
531. `C:\Projects\03_Investment_System_v1_governance_cleanup\reports\p1_6\r5_night_shift\r5_overnight_05_20260723\validation\structural_gate.json`
532. `C:\Projects\03_Investment_System_v1_governance_cleanup\scripts\run_r5_night_shift.ps1`
533. `C:\Projects\03_Investment_System_v1_governance_cleanup\scripts\run_r5_night_shift.py`
534. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\__init__.py`
535. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\backflow.py`
536. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\bf2_seed.py`
537. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\contracts.py`
538. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\lock.py`
539. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\models.py`
540. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\night03.py`
541. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\night03_backflow.py`
542. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\night03_decisions.py`
543. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\night03_execution.py`
544. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\night03_validation.py`
545. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\night04.py`
546. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\night04_acceleration.py`
547. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\night04_execution.py`
548. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\night04_pointer.py`
549. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\night04_review.py`
550. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\night04_validation.py`
551. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\night05.py`
552. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\outcome.py`
553. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\publication.py`
554. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\queue.py`
555. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\readout.py`
556. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\receipts.py`
557. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\runner.py`
558. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\strategic.py`
559. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\targets.py`
560. `C:\Projects\03_Investment_System_v1_governance_cleanup\src\maintenance\night_shift\validation.py`
561. `C:\Projects\03_Investment_System_v1_governance_cleanup\templates\night_shift_failure_packet.md`
562. `C:\Projects\03_Investment_System_v1_governance_cleanup\templates\night_shift_morning_readout.md`
563. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\fixtures\r5_night_shift\semantic_negative_cases.yaml`
564. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\night04_test_support.py`
565. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_adversarial.py`
566. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_analysis_candidate_packets.py`
567. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_analysis_decision_execution.py`
568. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_analysis_decisions.py`
569. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_analysis_review_briefs.py`
570. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_authority.py`
571. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_backflow_packets.py`
572. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_batch_decision_manifest.py`
573. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_bf2_dry_run.py`
574. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_bf2_seed.py`
575. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_blank_decision_bundles.py`
576. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_blocker_ledger.py`
577. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_bundle18_precheck.py`
578. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_candidate_registry.py`
579. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_carry_forward.py`
580. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_ci_contract.py`
581. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_command_safety.py`
582. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_contract.py`
583. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_contract_lint.py`
584. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_contract_proposals.py`
585. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_crash_recovery.py`
586. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_decision_adversarial.py`
587. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_decision_authority.py`
588. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_decision_conflicts.py`
589. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_decision_hash.py`
590. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_decision_inbox.py`
591. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_decision_manifest.py`
592. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_decision_replay.py`
593. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_dependency_critical_path.py`
594. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_dependency_dag.py`
595. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_dependency_matrix.py`
596. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_dependency_unblock.py`
597. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_determinism.py`
598. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_digest.py`
599. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_evidence_candidate_packets.py`
600. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_evidence_decision_execution.py`
601. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_evidence_decisions.py`
602. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_evidence_review_briefs.py`
603. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_fallback_backlog.py`
604. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_four_case_dashboard.py`
605. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_git_targets.py`
606. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_goal_policy.py`
607. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_golden_inventory.py`
608. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_historical_immutability.py`
609. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_human_decisions.py`
610. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_human_field_integrity.py`
611. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_human_gate.py`
612. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_human_gate_execution.py`
613. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_human_packet_refresh.py`
614. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_human_review_briefs.py`
615. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_lineage_guard.py`
616. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_lock.py`
617. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_metrics.py`
618. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_night02_manifest.py`
619. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_night03_ci_contract.py`
620. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_night03_crash_resume.py`
621. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_night03_determinism.py`
622. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_night03_manifest.py`
623. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_night03_package_integrity.py`
624. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_night04_ci_contract.py`
625. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_night04_crash_resume.py`
626. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_night04_determinism.py`
627. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_night04_outcome.py`
628. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_night04_publication.py`
629. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_night04_taxonomy.py`
630. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_night05_intake.py`
631. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_no_false_success.py`
632. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_non_self_referential_receipts.py`
633. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_occurrence_sandbox.py`
634. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_occurrence_transition.py`
635. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_outcome.py`
636. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_parent_aggregation.py`
637. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_parent_critical_path.py`
638. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_partial_batch_decisions.py`
639. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_pilot_eligibility.py`
640. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_pointer_approvals.py`
641. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_pointer_batch_simulation.py`
642. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_pointer_conditional_execution.py`
643. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_pointer_conflicts.py`
644. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_pointer_diff_ceiling.py`
645. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_pointer_dry_run_patches.py`
646. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_pointer_dry_run_truth.py`
647. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_pointer_execution.py`
648. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_pointer_executor.py`
649. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_pointer_path_resolution.py`
650. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_pointer_proposals.py`
651. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_pointer_receipt_preview.py`
652. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_pointer_review_briefs.py`
653. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_pointer_review_index.py`
654. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_pointer_rollback.py`
655. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_pointer_sandbox_manager.py`
656. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_pointer_targeted_tests.py`
657. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_publication.py`
658. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_queue_expansion.py`
659. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_queue_import.py`
660. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_queue_taxonomy.py`
661. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_readout.py`
662. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_receipts.py`
663. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_resolution_receipts.py`
664. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_resolution_truth.py`
665. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_resume.py`
666. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_retry_graph.py`
667. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_review_counterevidence.py`
668. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_review_diff_summaries.py`
669. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_review_downstream_impact.py`
670. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_review_groups.py`
671. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_review_handoff.py`
672. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_review_packet_normalization.py`
673. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_reviewer_authority.py`
674. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_reviewer_dashboard.py`
675. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_runner.py`
676. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_scope_guard.py`
677. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_semantic_fixture_contract.py`
678. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_semantic_router.py`
679. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_stale_decision_hashes.py`
680. `C:\Projects\03_Investment_System_v1_governance_cleanup\tests\test_r5_night_shift_unblock_leverage.py`

### P5 v6 planned mutation paths and inherited authorities

v6 当前只计划修改下列 A.2 工具、manifest、tests、validation receipts 与本文件，以完成 contract identity、wave-specific actor 和 safe Night delete surface 重绑；另只修改 A.1 `governance_cleanup_readout.md` 的 actor/checkpoint metadata。不以 wildcard 或 family 替代实际路径。其他 A.1 与全部 A.7 已在 v5 完成并验证，本包默认只读，除非 A.2 重绑造成真实回归且合同 exact authority 明确允许，否则不得再次修改。

新增或继续维护的 A.2 路径：

- `scripts/manage_r5_v1_historical_cleanup.py`
- `reports/p1_6/r5_v1_governance_cleanup/historical_baseline_manifest.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/historical_cleanup_manifest.yaml`
- `tests/test_r5_v1_historical_baseline_manifest.py`
- `tests/test_r5_v1_historical_cleanup_manifest.py`
- `tests/test_r5_v1_active_routing_retirement.py`
- `reports/p1_6/r5_v1_governance_cleanup/validation/historical_decoupling.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/validation/manual_deletion_wave_night.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/validation/manual_deletion_wave_bundle.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/validation/manual_deletion_wave_old002837.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/validation/clean_checkout_smoke.txt`
- `reports/p1_6/r5_v1_governance_cleanup/validation/full_pytest.txt`
- `docs/codex_tasks/v1_governance_integration_cleanup_v6/START_HERE.md`

A.7 `transition_modify_then_delete_exact` 三路径（v5 已完成；v6 不再修改，仍属 Night manifest）：

- `tests/test_r5_night_shift_ci_contract.py`
- `tests/test_r5_night_shift_night03_ci_contract.py`
- `tests/test_r5_night_shift_night04_ci_contract.py`

三者已是等强 CI retirement assertions，仍必须进入 Night actual manifest，并在新 v6 arm 后由 Codex 按 D-020 精确逐文件删除。

v5 已完成的高置信 A.1 物理解耦路径（v6 只读历史）：

- `.github/workflows/ci.yml`
- `.github/workflows/r5_bundle11r_runtime.yml`
- `.gitattributes`
- `config/r5_readout_canonical_index.yaml`
- `config/a_stock_data_capability_catalog.yaml`
- `config/adapter_contract_registry.yaml`
- `scripts/run_r5_v1_replay_002837.py`
- `tests/conftest.py`
- `tests/test_r5_v1_active_control_plane.py`
- `tests/test_r5_v1_blocker_root_cause_map.py`
- `tests/test_r5_v1_replay_002837.py`
- `tests/test_r5_v1_workflow_state_validator.py`
- `tests/test_valuation_input_contract.py`

P5 A.1 readout/validator metadata 路径（v6 仅首项 actor/checkpoint metadata 计划写入；其余默认只读，只有发生 D-017 exact authority 明确覆盖的真实回归时才可更新，否则 hard stop）：

- `reports/p1_6/r5_v1_governance_cleanup/governance_cleanup_readout.md`
- `reports/p1_6/r5_v1_governance_cleanup/validation/preflight.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/validation/doc_drift.txt`
- `reports/p1_6/r5_v1_governance_cleanup/validation/governance_targeted.txt`
- `reports/p1_6/r5_v1_governance_cleanup/validation/refresh_002837.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/validation/blocker_root_reconciliation.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/validation/source_route_quality_report.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/validation/scope_audit.yaml`

### P5 reference-scan expanded exact mutation paths

活动根反向扫描已证明 A.1 中全部 46 个保留代码路径都需要 D-017 最小物理解耦：41 个直接包含固定旧 workflow ID；其余 5 个通过 A.4 配置中的 `default_paths` 或 `required_inputs` 间接解析旧目录。`scripts/run_r5_v1_replay_002837.py` 已列于首轮清单；以下是其余逐路径代码 mutation set：

- `scripts/build_evidence_generation_lock.py`
- `scripts/build_r5_analysis_pack_v2.py`
- `scripts/build_r5_bundle10_reader_pack.py`
- `scripts/build_r5_bundle5_benchmark_coverage_precheck.py`
- `scripts/build_r5_bundle5_forecast_valuation_onboarding.py`
- `scripts/build_r5_bundle5_market_peer_onboarding.py`
- `scripts/build_r5_bundle5_official_disclosure_onboarding.py`
- `scripts/build_r5_bundle6_close_readout.py`
- `scripts/build_r5_bundle6_human_review_handoff.py`
- `scripts/build_r5_bundle6_reader_baseline.py`
- `scripts/build_r5_bundle6_research_remediation.py`
- `scripts/build_r5_bundle8_research_depth_plan.py`
- `scripts/build_r5_bundle8r_pilot_artifacts.py`
- `scripts/build_r5_bundle9_forecast.py`
- `scripts/build_r5_bundle9_valuation.py`
- `scripts/build_r5_bundle9r_forecast_valuation.py`
- `scripts/build_r5_evidence_coverage_matrix.py`
- `scripts/build_r5_reader_section_payloads.py`
- `scripts/build_r5_reviewed_input_staging.py`
- `scripts/close_r5_bundle8b.py`
- `scripts/close_r5_bundle9.py`
- `scripts/promote_r5_reviewed_inputs_to_registries.py`
- `scripts/r5_next_pilot_gate.py`
- `scripts/r5_pack_promotion_gate.py`
- `scripts/r5_readiness_gate.py`
- `scripts/r5_reviewed_input_pilot_gate.py`
- `scripts/render_r5_reviewed_input_output.py`
- `scripts/run_r5_bundle10_cross_industry_writer_regression.py`
- `scripts/run_r5_bundle5_real_registry_promotion.py`
- `scripts/run_r5_bundle5_research_draft_quality_gate.py`
- `scripts/run_r5_bundle8_research_depth_gate.py`
- `scripts/run_r5_reader_quality_gate.py`
- `scripts/sync_r5_bundle10_external_review_pending.py`
- `scripts/validate_r5_bundle10_close.py`
- `scripts/validate_r5_bundle10_human_review_submission.py`
- `scripts/validate_r5_bundle8b_close.py`
- `scripts/validate_r5_bundle9_close.py`
- `src/ingest/adapters/adapter_runtime.py`
- `src/ingest/adapters/eastmoney_report_pdf_adapter.py`
- `src/ingest/business_segment_extraction.py`
- `src/ingest/official_financial_reconciliation.py`
- `src/qa/r4_disclosure_backflow_review.py`
- `src/qa/r4_publishable_stock_report_gate.py`
- `src/report/r5_section_payload_builder.py`
- `src/research/r5_bundle13r_evidence_backflow.py`

同一扫描证明 A.1 的 60 个保留测试中有 58 个会物理读取候选目录或依赖旧默认输入；首轮清单已包含其中 6 个。下列其余 52 个测试路径进入 exact mutation set；`tests/test_r5_bundle4_close.py` 与 `tests/test_r5_bundle5_status_baseline.py` 仅检查 A.4 metadata，保持只读：

- `tests/test_build_r5_evidence_plan_from_gaps.py`
- `tests/test_build_r5_evidence_request_queue.py`
- `tests/test_business_segment_extraction.py`
- `tests/test_data_layer_bridge_draft.py`
- `tests/test_liquid_cooling_exposure_evidence_review.py`
- `tests/test_official_reconciliation_review_decision.py`
- `tests/test_r4_artifact_formatting.py`
- `tests/test_r4_publishable_stock_report_gate.py`
- `tests/test_r4_stock_report_v0_2_gate.py`
- `tests/test_r5_002837_reviewed_input_dry_run.py`
- `tests/test_r5_002837_reviewed_input_staging.py`
- `tests/test_r5_after_patch55_close.py`
- `tests/test_r5_bundle10_close.py`
- `tests/test_r5_bundle10_dynamic_writer.py`
- `tests/test_r5_bundle10_human_review_finalize.py`
- `tests/test_r5_bundle10_human_review_handoff.py`
- `tests/test_r5_bundle10_human_review_submission.py`
- `tests/test_r5_bundle10_state_sync.py`
- `tests/test_r5_bundle10r_v5_artifacts.py`
- `tests/test_r5_bundle10r_v5_human_review.py`
- `tests/test_r5_bundle13r_evidence_backflow.py`
- `tests/test_r5_bundle4_post_promotion_dry_run.py`
- `tests/test_r5_bundle4_registry_promotion.py`
- `tests/test_r5_bundle4_reviewed_input_smoke.py`
- `tests/test_r5_bundle5_benchmark_coverage_precheck.py`
- `tests/test_r5_bundle5_close.py`
- `tests/test_r5_bundle5_real_input_inventory.py`
- `tests/test_r5_bundle5_real_pilot_gate.py`
- `tests/test_r5_bundle5_real_registry_promotion.py`
- `tests/test_r5_bundle6_close.py`
- `tests/test_r5_bundle6_human_review_handoff.py`
- `tests/test_r5_bundle6_reader_baseline.py`
- `tests/test_r5_bundle6_research_remediation.py`
- `tests/test_r5_bundle7_close.py`
- `tests/test_r5_bundle8b_local_close.py`
- `tests/test_r5_bundle9_close.py`
- `tests/test_r5_bundle9_forecast.py`
- `tests/test_r5_bundle9_valuation.py`
- `tests/test_r5_composer_research_draft_plus.py`
- `tests/test_r5_forecast_valuation_interlock.py`
- `tests/test_r5_pilot_gate_recheck_and_render.py`
- `tests/test_r5_quality_backflow.py`
- `tests/test_r5_reader_quality_gate.py`
- `tests/test_r5_reader_report_writer.py`
- `tests/test_r5_report_composer_degradation.py`
- `tests/test_r5_reviewed_input_registry_promotion.py`
- `tests/test_r5_source_gapped_002837_pack.py`
- `tests/test_segment_exposure_gate.py`
- `tests/test_segment_stock_backflow_review.py`
- `tests/test_validate_r5_forecast_assumption_registry.py`
- `tests/test_validate_r5_market_peer_input_registry.py`
- `tests/test_validate_r5_market_peer_inputs.py`

### P4 completion scope

- `reports/p1_6/r5_v1_governance_cleanup/root_policy_migration.yaml`
- `schemas/r5_v1_root_policy_migration.schema.json`
- `scripts/validate_r5_v1_root_policy_migration.py`
- `tests/test_r5_v1_root_policy_migration.py`
- `reports/p1_6/r5_v1_governance_cleanup/validation/blocker_root_reconciliation.yaml`
- `config/r5_readout_canonical_index.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/governance_cleanup_readout.md`
- `reports/p1_6/r5_v1_governance_cleanup/validation/scope_audit.yaml`
- `docs/codex_tasks/v1_governance_integration_cleanup_v2/START_HERE.md`

### P4 completion evidence

- Seven-root migration with no occurrence/candidate overlay: `reports/p1_6/r5_v1_governance_cleanup/root_policy_migration.yaml`.
- Strict schema, dynamic validator and adversarial tests: `schemas/r5_v1_root_policy_migration.schema.json`, `scripts/validate_r5_v1_root_policy_migration.py`, `tests/test_r5_v1_root_policy_migration.py`.
- Dynamic 63/20/6/69/43/0, 532-edge, six-duplicate reconciliation and zero active defects: `reports/p1_6/r5_v1_governance_cleanup/validation/blocker_root_reconciliation.yaml`.
- Active pointer: `config/r5_readout_canonical_index.yaml` → `policy_migrations.blocker_root_policy`.
- V-009, unchanged protected root map and user-main vector: `reports/p1_6/r5_v1_governance_cleanup/validation/scope_audit.yaml`.
- Required P5 follow-up: before Night/Bundle deletion, decouple `tests/test_r5_v1_blocker_root_cause_map.py` from physical historical paths while preserving V-005 behavior through durable baseline/blob reads.

### P3 completion scope

- Runner and tests: `scripts/run_r5_v1_policy_refresh_002837.py`, `tests/test_r5_v1_policy_refresh_002837.py`.
- Canonical pointer: `config/r5_readout_canonical_index.yaml`.
- New run control plane: `reports/workflow_runs/wf_20260725_stock_first_002837_v1_policy_refresh/workflow_state.yaml`, `artifact_manifest.csv`, `open_todos.csv`, `quality_gate_report.md`, `run_log.md`, `workflow_readout.md`.
- New run evidence/research: `reports/workflow_runs/wf_20260725_stock_first_002837_v1_policy_refresh/inputs/input_provenance.csv`, `research/disclosed_facts.yaml`, `research/limitations.yaml`, `research/issue_change_log.csv`, `research/stock_research_pack.yaml`, `research/segment_exposure.yaml`, `research/stock_report_draft.md`, `research/backflow_decision.yaml`.
- New run validation: `reports/workflow_runs/wf_20260725_stock_first_002837_v1_policy_refresh/validation/artifact_hashes.csv`, `replay_receipt.yaml`, `idempotence_report.yaml`.
- Phase evidence/checkpoint: `reports/p1_6/r5_v1_governance_cleanup/governance_cleanup_readout.md`, `validation/refresh_002837.yaml`, `validation/governance_targeted.txt`, `validation/source_route_quality_report.yaml`, `validation/scope_audit.yaml`, and this `START_HERE.md`.

### P3 completion evidence

- Canonical state and six-piece control plane: `reports/workflow_runs/wf_20260725_stock_first_002837_v1_policy_refresh/`.
- Fixed official provenance, page locators, facts and visible limitations: new run `inputs/` and `research/` artifacts.
- Two-pass and two-directory replay: new run `validation/` plus `reports/p1_6/r5_v1_governance_cleanup/validation/refresh_002837.yaml`.
- V-003 P3: `reports/p1_6/r5_v1_governance_cleanup/validation/governance_targeted.txt`.
- V-008: `reports/p1_6/r5_v1_governance_cleanup/validation/source_route_quality_report.yaml`.
- V-009 and unchanged protected assets: `reports/p1_6/r5_v1_governance_cleanup/validation/scope_audit.yaml`.

### P2 completion scope

- Permanent workflow/policy/meta docs: `docs/workflows/RESEARCH_WORKFLOW.md`, `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md`, `docs/workflows/R5_SAMPLE_QUALITY_STOCK_REPORT_SPEC.md`, `docs/workflows/R5_REAL_COMPANY_REGRESSION_CONTRACT.md`, `docs/policies/QUALITY_GUARDRAILS.md`, `docs/meta/DOC_OWNERSHIP_MATRIX.md`.
- Active skills/references: `.agents/skills/research-orchestrator/SKILL.md`, `.agents/skills/research-orchestrator/references/workflow_state_schema.md`, `.agents/skills/research-orchestrator/assets/workflow_state_template.yaml`, `.agents/skills/research-orchestrator/scripts/validate_workflow_state.py`, `.agents/skills/quality-review/SKILL.md`, `.agents/skills/quality-review/references/r5_quality_gate.md`, `.agents/skills/stock-deep-dive/SKILL.md`, `.agents/skills/stock-deep-dive/references/r5_stock_research_pack_contract.md`, `.agents/skills/stock-deep-dive/references/report_production_profile.md`.
- New schema and tests: `schemas/r5_final_report_review.schema.json`, `tests/test_r5_v1_active_control_plane.py`, `tests/test_r5_v1_completion_semantics.py`, `tests/test_r5_v1_workflow_state_validator.py`, `tests/test_r5_final_report_review_semantics.py`.
- P2 evidence/checkpoint: `reports/p1_6/r5_v1_governance_cleanup/governance_cleanup_readout.md`, files under `reports/p1_6/r5_v1_governance_cleanup/validation/`, and this `START_HERE.md`.

### P2 completion evidence

- Unique final-report human boundary and current-byte binding: `schemas/r5_final_report_review.schema.json`, workflow-state template/schema/validator, and permanent workflow/policy documents.
- Machine-vs-human truth separation and `changes_requested` routing: active orchestrator, quality-review, and stock-deep-dive skills/references.
- V-002: `reports/p1_6/r5_v1_governance_cleanup/validation/doc_drift.txt`.
- V-003 P2 and compatibility regression: `reports/p1_6/r5_v1_governance_cleanup/validation/governance_targeted.txt`.
- Human-boundary and adversarial audit: `reports/p1_6/r5_v1_governance_cleanup/validation/final_report_review_audit.yaml`.
- V-009 and unchanged user-main vector: `reports/p1_6/r5_v1_governance_cleanup/validation/scope_audit.yaml`.

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
- 2026-07-25T13:31:22+08:00 — P1 指定 checkpoint `0906a5fa8c785da1a74326aa19dbf0abc58ddd2e` 已创建且工作树 clean；完整读取 P2 点名的人审、sample-quality、real-company regression、Reader 与 generation-lock 契约/测试后，按上述精确路径开始 P2。
- 2026-07-25T14:23:39+08:00 — P2 最终报告唯一人审边界、当前字节 hash 失效、truth 分离、`changes_requested` 路由与历史 review 只读兼容已实现；V-002、V-003 P2（178 passed）、兼容回归（75 passed）、对抗复核、V-009 和 task-package integrity 通过，等待指定 P2 checkpoint。
- 2026-07-25T14:33:04+08:00 — P2 指定 checkpoint `aa73859ddf8dbef2ad94b8c72dbf0ffc3931b851` 已创建且工作树 clean；P3 点名的四个 skills 及其适用必读 references、旧 replay 实现/测试和固定官方输入已完整读取，按上述精确路径开始 P3。
- 2026-07-25T15:30:31+08:00 — P3 独立 002837 policy refresh 已生成 17 件 canonical 产物；正式披露 hash/page、四 issue 动态处置、unknown 非数值使用、毛利率与未披露毛利贡献字段语义隔离、双临时目录重放、V-003 P3（194 passed）、V-004（16 passed）、V-008 和 V-009 均通过，等待指定 P3 checkpoint。
- 2026-07-25T15:37:32+08:00 — P3 指定 checkpoint `6c7fc2a35942bb04f5ef0ecfa2c6ccbd10e0a069` 已创建且工作树 clean；原 root map 与 engineering source 的 Git blob 相同（worktree SHA-256 `39aadff44cf51d1ad5607d8ec8481bbab42650723eaf5a981415df0ee3facacf`），7 roots、63 occurrence、20 dependency-blocked、6 parent、69 carry-forward、43 candidate-ready、0 historical resolved 和 532 dependency edges 已完整读取，V-005 既有基线 7 passed，按上述 9 条精确路径开始 P4。
- 2026-07-25T15:55:38+08:00 — P4 七 root 活动处置迁移已实现：1 `policy_retired`、1 `not_required_for_active_v1`、1 `report_limitation`、1 visible unused `unknown`、3 open `historical_backlog`、0 `active_defect`；动态证明 63/20/6/69/43/0、532 edges、6 duplicate references，未复制 occurrence/candidate 决定或声称历史 resolution/system completion。V-005（18 passed）、额外索引兼容回归（27 passed）、对抗复核、V-009 和 task-package integrity 通过，等待指定 P4 checkpoint。
- 2026-07-25T16:34:47+08:00 — P4 指定 checkpoint `3741c807ae1d9859e8cb72d5e587a5bb74f2082e` 已创建且 clean。P5 三种实质不同方法（retain 分类、静态引用图、filtered-tree full-pytest 诊断）均指向同一授权冲突：冻结 exact mutation set 不允许修改删除后必然失败的既有 tests/scripts/fixtures。诊断造成的 12 个本地 fixture commits、索引和共享 Git 配置副作用已完整恢复，专用树 clean，用户主工作树完整状态向量与 preflight 逐字节相同，远端未写入。P5 在任何删除 arm 前硬停止，等待 amended v3。
- 2026-07-25T21:30:00+08:00 — 用户明确授权 amended v3，并补充“允许所有操作”“继续”。专用树仍位于 clean blocker checkpoint `1c4040edced3fa0829fb68f36bc156aeac223870`，远端 refs 未漂移。用户主工作树 HEAD 未变但脏状态由用户外部更新，已连续两次采集新的完整/跟踪 NUL 向量作为只读保护快照。v3 只扩充 Appendix A 的 P5 精确路径权限和 Bundle action/test 命名边界；旧 v1/v2 合同、P1–P4、全部标准、三波人工删除和发布模式 A 不变。package 仍为 draft，等待 finalize。
- 2026-07-26T03:01:18+00:00 — state=blocked; completed=P4; next=P5; validation=fail; Post-freeze audit proved that eight existing P5 readout and validation paths were described in prose but omitted from modify_existing_exact; P5 did not start and no deletion wave was armed; prepare amended v4 without editing frozen v3.
- 2026-07-26T10:42:00+08:00 — v3 frozen package 和 blocker 状态以 package-only checkpoint `312adc73821706b0b7ca6aa00e80ee608bd10b32` 保存；该 commit 仅新增 v3 `CONTRACT.md` 与 `START_HERE.md`。工作树恢复 clean，P5 mutation 和 deletion wave 均未开始。
- 2026-07-26T11:11:15+08:00 — 用户再次回复“批准”。v4 draft 以 `312adc73821706b0b7ca6aa00e80ee608bd10b32` 为 source baseline，补齐 A.1 八个既有 readout/validation 路径，并闭合 A.1=120、A.2=13、A.3=44、A.4=35、A.5=27 与 A.6 source-baseline archive inventory 机制；P1–P4、三波用户手工删除边界与发布模式 A 不变。当时 package 仍为 draft，未冻结。
- 2026-07-26T11:23:54+08:00 — 用户主工作树完整状态向量因仅 untracked 的外部变化由 102 records 漂移到 130 records，tracked-only 和 HEAD 均未变。按合同暂停并报告后，用户明确回复“继续，以新快照为基线”；两次连续采样确认新完整向量为 130 records/9156 bytes/SHA-256 `1b21ac246cb2ad4b055f5a264503fb1fad8fe9edae153e25c9cd6d19d4a719c0`，tracked-only 仍为 20 records/1025 bytes/SHA-256 `3ab441f68037823866029eb2136149a807f6382755966daf96d33a85b965609b`。v4 同时闭合 exact amendment disclosure、A6 与两个 Bundle17R direct-child deletion targets 的保护重叠、唯一 A.1/A.5 交集和 116-path ordinal NUL inventory 指纹。
- 2026-07-26T11:27:50+08:00 — 两项独立只读审计均返回 `SAFE TO FREEZE`，并复现 A.1=120、A.2=13、A.3=44、A.4=35、A.5=27、唯一 A.1∩A.5 两路径、A.6 116 paths/8065 bytes/SHA-256 `6c667b2aa0db007d5e89baf5b7bae837fd62249be3d85613f16aba3d14d32e6a`、active old-ID/Bundle unknown=0、新用户主树状态向量及远端 refs。v4 合同已冻结，canonical SHA-256 为 `c806d4811e4f40ffb86154c6144c75173c7d13e1fc193f9add07686495217736`；`--require-ready` 通过，只产生预期的 last_completed=P4 warning。
- 2026-07-26T11:37:24+08:00 — package-only v4 setup checkpoint `63e542ddc8a7329812e8aac15ead871253b58ca6` 已创建且 clean。P1→P4 checkpoint direct ancestry 与产物逐项通过；当前 doc drift pass，V-003 final 九项 `194 passed`，V-005 `18 passed`，V-004 两次 replay semantic digest `2d8487beb46f10b6df103a9a2808998870a19556ef6879959ed15c6eb90cbcc6`、tree digest `3baefe904ef244d272f9432ea661a3e13f2704003bd8d19590232a4d9f78df5f` 且 `16 passed`，V-008 `decision=pass`/blocking=0；原 root map blob `526d9964a95ddc866fa960a1b9556e720ca80178` 与 f60f220 完全一致。最早未证明阶段为 P5，本文件切换为 running，并记录首轮逐路径 mutation set。
- 2026-07-26T12:00:00+08:00 — P5 Group A/B 的授权内解耦补丁完成首轮只读审查和 75 项针对性测试，但 pre-delete full-pytest 复现 `tests/test_r5_night_shift_ci_contract.py` 为 `1 failed, 1 passed`。该只读删除候选要求 CI 保留 Night glob，而 C-008/V-006 要求 CI physical route=0；三种可能规避分别违反 C-008 或 D-017。两项独立审查与诊断工具确认 frozen v4 无授权内解，状态切换为 blocked；未删除、arm、stage、push、PR 或发布。用户主树完整新快照再次逐字节匹配，合同 hash 不变。
- 2026-07-26T12:18:01+08:00 — blocker 后只读全仓冲突扫描把同类自依赖从 1 项纠正为 3 项：除直接 CI contract 外，Night03/Night04 CI contract 也分别经冻结 builder 要求旧 Night glob/history guards，实测另有 `2 failed`。未发现第四项同类权限/顺序冲突；Night05 `.gitattributes` 检查绑定固定 `a96c...` delivery，不依赖当前内容。最小 v5 unblock 因此改为三个 exact transition-modify-then-delete 路径，不能只授权原一项。另记录两个 A.2 诊断工具缺陷；均不扩大合同权限。
- 2026-07-26T12:47:52+08:00 — 用户精确批准 v5：三个 Night CI tests 进入 A.7 `transition_modify_then_delete_exact`，只改为等强退休断言，随后仍在 Night wave 由用户手工删除；其余 v4 标准和三波边界不变。准备预检确认 dedicated HEAD/source baseline=`f1dafeb32b08d24a6960f31d4a0f6d8820b95839`、remote main/Night05/V1 refs 未漂移、execution ref 不存在、P1–P4 与 v4 checkpoints 全部为祖先。两份机械草稿曾误落用户主树，已按明确单文件逐一撤销并复核 full/tracked NUL 向量精确恢复；v5 当前只在专用工作树新增 `CONTRACT.md` 与 `START_HERE.md` draft，等待独立审计、finalize 和 package-only setup checkpoint。
- 2026-07-26T13:05:30+08:00 — 两项独立只读审计分别返回 `SAFE TO FREEZE` 与 `SAFE TO FINALIZE`，独立复现 A.1=120、A.2=13、A.3=44、A.4=35、A.5=27、A.6 116/8065/`6c667...`、A.7 精确三路径及三项 Night manifest 登记。标准 finalize 完成，v5 contract frozen hash=`7a02675ea94dd9ef83f40df42889720998cbea0d8db26992d158bf3c78135ef4`；`--require-ready` 返回 `ok: true`，仅有继承 P4 的预期 ready warning。等待 package-only setup checkpoint。
- 2026-07-26T13:06:28+08:00 — v5 package-only setup checkpoint `ce4f9554db4fcdfa4699c70516d9a3497c565fc7` 已创建，直接父为 `f1dafeb32b08d24a6960f31d4a0f6d8820b95839`，提交只含 v5 `CONTRACT.md` 与 `START_HERE.md`；随后从最早未证明阶段 P5 恢复。
- 2026-07-26T15:12:00+08:00 — P5 删除前解耦完成：三个 A.7 tests 改为等强退休断言；活动引用/unknown 均为 0；exact manifest 1,386 files，Night/Bundle/old002837=`680/205/501`；全量 Git blob 恢复逐字节通过；V-003/V-004/V-005/V-006/V-008 和 full pytest `1349 passed, 2 skipped` 通过；独立质量审计 PASS。指定 decoupling checkpoint `805b8e3e9624e4e93057aa950cba4db1b3010cb3` 已创建且 clean，提交含 97 个 A.1/A.2/A.7 路径、0 删除。
- 2026-07-26T15:15:00+08:00 — Night wave 已准备 arm：本文件逐项列出 680 个绝对路径，aggregate 为 4,480,614 bytes、55,881 path-vector bytes、SHA-256 `1ec2f42b84c1078f6b26caa377e9c1fb3efff9221196bc2e02bd819588a59c59`。随后创建旧 manual arm checkpoint `82f7d37a10a9677af631c1a5863661a64df3270b`，但没有删除、stage、push、PR 或发布。
- 2026-07-26T22:25:00+08:00 — 用户明确授权项目根删除规则最小修订；policy checkpoint `46a55d17f120496b6114c55e1d79e96adaef8378` 直接父为旧 arm、只改 `AGENTS.md`，文件 SHA-256 `1717636c2e2dd7c92c9ac35ef66ef6231d471d398f28c681ad99e8a110174cbf`。独立审计 PASS，同时确认 v5 manifest/tests/receipt 仍禁止 Codex 删除，因此必须先建 v6、重绑 actor 并重新 arm。
- 2026-07-26T22:38:25+08:00 — v6 draft 以 `46a55d17...` 为 source baseline，只拟将 Night actor 改为 Codex exact-manifest one-file-at-a-time；Bundle/old002837 手工边界和三波全部 path sets/hashes 不变。补丁工具曾把两份未跟踪草稿误落用户主树，已逐文件撤销并复核主树 HEAD/full/tracked NUL 向量精确恢复；专用树当前只新增 v6 `CONTRACT.md` 与 `START_HERE.md`，等待 finalize/setup。
- 2026-07-26T22:54:05+08:00 — 两项独立只读审计均返回 `SAFE TO FINALIZE`。标准 finalizer 冻结 v6 contract，raw/canonical SHA-256=`f5326c3c322fa3e0a319e36c032be4e169ede44acf57cce19bf63cf97b7ce3ec`；`--require-ready` 返回 `ok: true`，仅有继承 P4 的预期 warning。等待 package-only setup checkpoint；Night 仍未授权执行，须先完成 actor rebinding 与新 arm。
- 2026-07-26T23:50:08+08:00 — v6 A.2 actor/tool/manifest 重绑静态审计、1,386-file full restore 和 V-006 `26 passed` 均通过；但完整 pytest 复现 `1 failed, 1353 passed, 2 skipped`。唯一失败证明 `805b8e3...` 在旧成功测试后把 deterministic V-005 checked-in receipt 改写为非渲染输出；独立 frozen-authority 审计确认 v6 不授权修复该 A.1 回执，故在任何 actor checkpoint、Night arm 或删除前 hard stop。已向协调任务报告；等待用户批准仅机械重渲染该回执的最小 v7。
- 2026-07-27T00:09:50+08:00 — 用户明确批准最小 v7：“仅授权重新生成 `blocker_root_reconciliation.yaml`，其他 v6 标准、Night/Bundle/旧 002837 三波边界均不变。”当前 user-main HEAD/full/tracked NUL 向量和远端 main/Night05/V1 refs 再次精确匹配，execution ref 仍不存在；先保存本 blocked checkpoint，再创建 v7 package-only amendment。
