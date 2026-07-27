---
schema_version: "1"
task_id: "v1_governance_integration_cleanup_v9"
contract_path: "docs/codex_tasks/v1_governance_integration_cleanup_v9/CONTRACT.md"
contract_sha256: "990e582e36c18f93a4e594eb1c0dc1b043f182e1a45eeb0cd7c83fd61a7d2b82"
state: "blocked"
execution_branch: "codex/v1-governance-integration-cleanup"
source_baseline: "1e38e1f3704f9eff0328f80053d4da254f4b80b6"
last_completed_phase: "P4"
next_phase: "P5"
last_validation: "fail"
updated_at: "2026-07-27T08:38:56+00:00"
---
# Start or resume this stage in a new Codex chat

本任务包是冻结 v8 的最小 authorized amended v9。新增权限严格只有 Appendix A.8 的 14 个路径，用于关闭最终 full pytest 暴露的十项历史路径间接读取，并加强 V-006 scanner。三波删除已经完成；1386 个文件、29 个目录和旧 run root 均不得恢复、重放或改变清单/收据。A.1–A.7、P1–P5 数量、研究/治理语义、发布模式 A 与全部完成标准保持不变。只有 front matter 为 `state: ready`、启动块包含真实 contract hash 且 `--require-ready` 校验通过时才可启动。

最终 ready 后，在专用工作树 `C:\Projects\03_Investment_System_v1_governance_cleanup` 打开一个全新 Codex 聊天，并原样粘贴：

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/v1_governance_integration_cleanup_v9
Frozen contract: docs/codex_tasks/v1_governance_integration_cleanup_v9/CONTRACT.md
Expected contract SHA-256: 990e582e36c18f93a4e594eb1c0dc1b043f182e1a45eeb0cd7c83fd61a7d2b82
Execution branch: codex/v1-governance-integration-cleanup
Source baseline: 1e38e1f3704f9eff0328f80053d4da254f4b80b6
Historical cleanup snapshot: 312adc73821706b0b7ca6aa00e80ee608bd10b32
Engineering source candidate: f60f220ae252262a537c612ce193fc779901984b
Dedicated worktree: C:\Projects\03_Investment_System_v1_governance_cleanup

Read the complete applicable AGENTS.md instruction chain, CONTRACT.md, START_HERE.md, and every phase-required skill file before acting. Treat the frozen contract as the complete objective, constraints, authority, and definition of done. Do not rely on any previous chat, memory, project journal, Night queue, or unstated decision.

Validate package integrity and repository preflight, then resume from the earliest phase whose postconditions are not proven. After each phase, run its validators, inspect scope, update START_HERE.md, and create the specified Git checkpoint. Continue through P1-P5 until every completion criterion passes or a contract hard stop occurs.

Never edit the frozen contract, add phases, weaken a criterion, fabricate data or reviewer decisions, touch the user's dirty main worktree, restore or replay any completed deletion wave, direct-push main, or publish beyond the authorization envelope. In P5, modify only Appendix A.8 plus the exact checkpoint evidence paths. Use manifest-bound Git blobs or explicit temporary inputs whose paths do not contain the old workflow ID; preserve all business verdicts and assertion strength. Verify all 1386 deleted files, 29 directories, and the old run root remain absent before and after tests.
```

## Current checkpoint

- **State:** `blocked`
- **Last completed phase:** `P4`
- **Next phase:** `P5`
- **Latest validation:** `fail`。v9 A.8 focused regression 为 `13 passed in 8.06s`；V-006 scanner 正反例为 `5 passed`，但 active-root scan 仍为 `1 failed`，精化后的真实剩余量为 27 references / 12 个 A.8 外路径。1386 files、29 directories 与 old root 测试后继续全 absent；用户主树完整/跟踪状态向量与冻结快照逐字节一致；`git diff --check` 通过。
- **Current blocker:** V-006 证明 7 个保留生产实现仍使用旧 workflow run 作为 CLI 默认值、构建输入/输出或 rerun 命令，5 个保留测试仍把旧 workflow ID/path 送入活动 builder/registry/composer。精确路径为 `scripts/build_r5_bundle10_reader_pack.py`、`scripts/build_r5_bundle9_forecast.py`、`scripts/build_r5_bundle9_valuation.py`、`scripts/build_r5_reader_section_payloads.py`、`src/ingest/business_segment_extraction.py`、`src/qa/r4_disclosure_backflow_review.py`、`src/research/r5_bundle13r_evidence_backflow.py`、`tests/test_r5_bundle4_post_promotion_dry_run.py`、`tests/test_r5_bundle4_registry_promotion.py`、`tests/test_r5_bundle5_real_registry_promotion.py`、`tests/test_r5_composer_research_draft_plus.py`、`tests/test_r5_reviewed_input_registry_promotion.py`。这些路径均不在冻结 v9 Appendix A.8；修改任何一个都会越权，不能靠豁免 scanner、删除断言或接受非零引用完成 C-008/V-006。
- **Next safe action:** 用户明确批准最小 v10：只新增上述 12-path active-route retirement authority；允许把生产 CLI default 改为 required/显式参数、把旧 run 输入/输出改为显式 generic/temp/blob-bound 输入，并把 5 个测试改为等强 generic/temp/blob-bound 正反例；其余 v9 标准、A.1–A.8、三波边界/commits/receipts、无删除/无恢复和发布模式 A 全部不变。

### Immutable completed deletion evidence

- Night deletion commit: `be42857bf88223e01c71e4a4dfbac8e3a47080aa`
- Bundle deletion commit: `274d47ec299a42946bc3b83f7908257e80f0f99b`
- old002837 deletion commit: `b5ebdbfe6ddce7698a438bc8afa69cf5a1c8fbd2`
- File manifest aggregate: 1386 files / 9,787,412 content bytes / 121,264 path-vector bytes / SHA-256 `974d45610144d616f69c3c368d9ea1a0a27d66601a24f748aa8148e2ee702f33`
- Directory manifest: 29 repo-relative paths / 2208 bytes / SHA-256 `1e987f07ab4aa9b7c54a7444b053949b5c5d377655903d9715d8948e42446cd3`; 29 absolute paths / 3803 bytes / SHA-256 `31669a8f873c2510709a7f9828b27dad4eab9fe49a159071d40345693e770b75`
- All manifest files, all 29 directories, and old run root are absent. Never restore or replay.

### A.8 exact planned mutation paths

- `scripts/validate_r5_bundle10_close.py`
- `scripts/validate_r5_reader_report_pack.py`
- `scripts/validate_r5_bundle10r_human_review.py`
- `scripts/validate_r5_bundle8b_close.py`
- `scripts/manage_r5_v1_historical_cleanup.py`
- `tests/test_r5_002837_reviewed_input_staging.py`
- `tests/test_r5_bundle10_close.py`
- `tests/test_r5_bundle10r_v5_human_review.py`
- `tests/test_r5_bundle13r_evidence_backflow.py`
- `tests/test_r5_bundle5_real_input_inventory.py`
- `tests/test_r5_bundle8b_close.py`
- `tests/test_r5_pilot_gate_recheck_and_render.py`
- `tests/test_r5_report_composer_degradation.py`
- `tests/test_r5_v1_active_routing_retirement.py`

## Checkpoint history

| Timestamp | Phase | Commit | Validation | Scope |
|---|---|---|---|---|
| 2026-07-27T15:44:44+08:00 | P5 blocker | `1e38e1f3704f9eff0328f80053d4da254f4b80b6` | 10 failed, 966 passed, 2 skipped | v8 final-regression authority blocker evidence |
| 2026-07-27T16:38:56+08:00 | P5 blocker | current checkpoint commit | A.8 focused 13 passed; V-006 active scan 27 references / 12 unauthorized paths | v9 A.8 repairs close all original regressions and strengthen the scanner; continuation requires exact v10 authority |

## Resume rules

1. Read root `AGENTS.md`, frozen v9 `CONTRACT.md`, this file, `$autonomous-stage-runner`, and all P5-required files completely.
2. Validate package hash/status/branch/baseline before any task mutation.
3. Prove setup commit is package-only and a direct child of `1e38e1f3704f9eff0328f80053d4da254f4b80b6`.
4. Verify three deletion commits/receipts and complete absence before and after every test group.
5. Modify only A.8 plus exact checkpoint evidence paths; any additional implementation/test path requires a new amendment.
6. Run focused ten tests, V-006, all contract validators, full pytest, clean-checkout smoke, scope audit and package validation.
7. After seal, do not write tracked files; publication evidence remains external.
- 2026-07-27T08:08:24+00:00 — state=running; completed=P4; next=P5; validation=pass; v9 frozen and package-only setup checkpoint 49c9cc9 verified; begin A.8 final-regression repair
