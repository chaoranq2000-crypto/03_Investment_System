---
schema_version: "1"
task_id: "v1_governance_integration_cleanup_v10"
contract_path: "docs/codex_tasks/v1_governance_integration_cleanup_v10/CONTRACT.md"
contract_sha256: "f7715de5429b961a34eca9c62fa3609682f8bdd5783900f3a830d81763e568ec"
state: "running"
execution_branch: "codex/v1-governance-integration-cleanup"
source_baseline: "696ca4cdf54858f9e259bb19fdd6349cd3cf2d6d"
last_completed_phase: "P4"
next_phase: "P5"
last_validation: "partial"
updated_at: "2026-07-27T09:07:17+00:00"
---
# Start or resume this stage in a new Codex chat

本任务包是冻结 v9 的扩展授权 amended v10。固定目标、P1–P5、C-001–C-014、研究/治理事实、用户主树保护和发布模式 A 不变；新增 Appendix A.9 受控全阶段收尾权限与 A.10 扩展 exact-manifest wave 协议。既有 1386 个文件、29 个目录和旧 run root 均不得恢复或重放。只有 front matter 为 `state: ready`、启动块包含真实 contract hash 且 `--require-ready` 校验通过时才可启动。

最终 ready 后，在专用工作树 `C:\Projects\03_Investment_System_v1_governance_cleanup` 打开一个全新 Codex 聊天，并原样粘贴：

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/v1_governance_integration_cleanup_v10
Frozen contract: docs/codex_tasks/v1_governance_integration_cleanup_v10/CONTRACT.md
Expected contract SHA-256: PENDING
Execution branch: codex/v1-governance-integration-cleanup
Source baseline: 696ca4cdf54858f9e259bb19fdd6349cd3cf2d6d
Historical cleanup snapshot: 312adc73821706b0b7ca6aa00e80ee608bd10b32
Engineering source candidate: f60f220ae252262a537c612ce193fc779901984b
Dedicated worktree: C:\Projects\03_Investment_System_v1_governance_cleanup

Read the complete applicable AGENTS.md instruction chain, CONTRACT.md, START_HERE.md, and every phase-required skill file before acting. Treat the frozen contract as the complete objective, constraints, authority, and definition of done. Do not rely on any previous chat, memory, project journal, Night queue, or unstated decision.

Validate package integrity and repository preflight, then resume from the earliest phase whose postconditions are not proven. After each phase, run its validators, inspect scope, update START_HERE.md, and create the specified Git checkpoint. Continue through P1-P5 until every completion criterion passes or a contract hard stop occurs.

Never edit the frozen contract, add phases, weaken a criterion, fabricate data or reviewer decisions, touch the user's dirty main worktree, restore or replay any completed deletion wave, direct-push main, or publish beyond the authorization envelope. In P5, use Appendix A.9 for criterion-bound tracked changes and A.10 for any new exact cleanup wave. Never treat a family, glob, scanner output, prefix or dynamic discovery as a deletion manifest. Verify all existing and newly completed wave targets remain absent before and after tests.
```

## Current checkpoint

- **State:** `running`
- **Last completed phase:** `P4`
- **Next phase:** `P5`
- **Latest validation:** `partial`。source baseline `696ca4c...` 上 v9 A.8 focused regression 为 `13 passed in 8.06s`；V-006 scanner 正反例 `5 passed`，active-root scan 尚有 27 references / 12 paths。1386 files、29 directories 与 old root 全 absent；用户主树快照精确不变。
- **Current blocker:** 无。用户已明确批准 v10 受控全阶段收尾权限和扩展 exact-manifest deletion waves；仍需冻结和验证本包。
- **Next safe action:** finalize v10，验证 package-only setup diff 并提交；随后从 27 references / 12 paths 开始执行 P5。

### Immutable completed deletion evidence

- Night deletion commit: `be42857bf88223e01c71e4a4dfbac8e3a47080aa`
- Bundle deletion commit: `274d47ec299a42946bc3b83f7908257e80f0f99b`
- old002837 deletion commit: `b5ebdbfe6ddce7698a438bc8afa69cf5a1c8fbd2`
- File manifest aggregate: 1386 files / 9,787,412 content bytes / 121,264 path-vector bytes / SHA-256 `974d45610144d616f69c3c368d9ea1a0a27d66601a24f748aa8148e2ee702f33`
- Directory manifest: 29 repo-relative paths / 2208 bytes / SHA-256 `1e987f07ab4aa9b7c54a7444b053949b5c5d377655903d9715d8948e42446cd3`; 29 absolute paths / 3803 bytes / SHA-256 `31669a8f873c2510709a7f9828b27dad4eab9fe49a159071d40345693e770b75`
- All manifest files, all 29 directories, and old run root are absent. Never restore or replay.

### Initial v10 route-closure paths

- `scripts/build_r5_bundle10_reader_pack.py`
- `scripts/build_r5_bundle9_forecast.py`
- `scripts/build_r5_bundle9_valuation.py`
- `scripts/build_r5_reader_section_payloads.py`
- `src/ingest/business_segment_extraction.py`
- `src/qa/r4_disclosure_backflow_review.py`
- `src/research/r5_bundle13r_evidence_backflow.py`
- `tests/test_r5_bundle4_post_promotion_dry_run.py`
- `tests/test_r5_bundle4_registry_promotion.py`
- `tests/test_r5_bundle5_real_registry_promotion.py`
- `tests/test_r5_composer_research_draft_plus.py`
- `tests/test_r5_reviewed_input_registry_promotion.py`

## Checkpoint history

| Timestamp | Phase | Commit | Validation | Scope |
|---|---|---|---|---|
| 2026-07-27T15:44:44+08:00 | P5 blocker | `1e38e1f3704f9eff0328f80053d4da254f4b80b6` | 10 failed, 966 passed, 2 skipped | v8 final-regression authority blocker evidence |
| 2026-07-27T16:38:56+08:00 | P5 blocker | current checkpoint commit | A.8 focused 13 passed; V-006 active scan 27 references / 12 unauthorized paths | v9 A.8 repairs close all original regressions and strengthen the scanner; continuation requires exact v10 authority |

## Resume rules

1. Read root `AGENTS.md`, frozen v10 `CONTRACT.md`, this file, `$autonomous-stage-runner`, and all P5-required files completely.
2. Validate package hash/status/branch/baseline before any task mutation.
3. Prove setup commit is package-only and a direct child of `696ca4cdf54858f9e259bb19fdd6349cd3cf2d6d`.
4. Verify three deletion commits/receipts and complete absence before and after every test group.
5. Use A.9 only for changes directly bound to existing criteria/validators; use A.10 only for committed exact cleanup manifests.
6. Run focused ten tests, V-006, all contract validators, full pytest, clean-checkout smoke, scope audit and package validation.
7. After seal, do not write tracked files; publication evidence remains external.
- 2026-07-27T08:48:46+00:00 — state=draft; completed=P4; next=P5; validation=not_run; v10 broad authority approved; finalize package before execution
- 2026-07-27T08:55:33+00:00 — state=running; completed=P4; next=P5; validation=partial; v10 setup 1b0298d verified; begin A.9 closure of 27 references across 12 paths; A.10 extended waves only if retirement-only candidates are proven
- 2026-07-27T09:07:17+00:00 — state=running; completed=P4; next=P5; validation=partial; A.9 route closure complete: active references 27 to 0; focused original regressions 13 passed; route/behavior suites 62 passed and explicit-root subset 36 passed; A.10 extended_wave_count=0 because no retirement-only file candidate was proven; next run full contract validation
