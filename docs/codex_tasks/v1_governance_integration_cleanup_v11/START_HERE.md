---
schema_version: "1"
task_id: "v1_governance_integration_cleanup_v11"
contract_path: "docs/codex_tasks/v1_governance_integration_cleanup_v11/CONTRACT.md"
contract_sha256: "68028d41f366d535daf7647faa8aae408e167f5442a96ed2ff7a3c3aeca18aae"
state: "running"
execution_branch: "codex/v1-governance-integration-cleanup"
source_baseline: "bcb535618367024eb85f8bee7abb8419c56d75eb"
last_completed_phase: "P5"
next_phase: "none"
last_validation: "pass"
updated_at: "2026-07-27T13:18:41+00:00"
---
# Start or resume this stage in a new Codex chat

本任务包是冻结 v10 的最小 amended v11。唯一新增权限是修复 V-006 在 Linux checkout 中对冻结 Windows absolute directory receipt 的 mixed-separator 重建，并把已失败候选 `bcb5356...` 普通 fast-forward supersede 为一个新 sealed candidate。固定目标、P1–P5、C-001–C-014、研究/治理事实、既有 relative/absolute vectors、1386 文件、29 目录、三波边界、用户主树保护和发布模式 A 均不变；不执行任何删除。只有 front matter 为 `state: ready`、启动块包含真实 contract hash 且 `--require-ready` 校验通过时才可启动。

最终 ready 后，在专用工作树 `C:\Projects\03_Investment_System_v1_governance_cleanup` 打开一个全新 Codex 聊天，并原样粘贴：

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/v1_governance_integration_cleanup_v11
Frozen contract: docs/codex_tasks/v1_governance_integration_cleanup_v11/CONTRACT.md
Expected contract SHA-256: PENDING
Execution branch: codex/v1-governance-integration-cleanup
Source baseline: bcb535618367024eb85f8bee7abb8419c56d75eb
Historical cleanup snapshot: 312adc73821706b0b7ca6aa00e80ee608bd10b32
Engineering source candidate: f60f220ae252262a537c612ce193fc779901984b
Dedicated worktree: C:\Projects\03_Investment_System_v1_governance_cleanup

Read the complete applicable AGENTS.md instruction chain, CONTRACT.md, START_HERE.md, and every phase-required skill file before acting. Treat the frozen contract as the complete objective, constraints, authority, and definition of done. Do not rely on any previous chat, memory, project journal, Night queue, or unstated decision.

Validate package integrity and repository preflight, then resume from the earliest phase whose postconditions are not proven. After each phase, run its validators, inspect scope, update START_HERE.md, and create the specified Git checkpoint. Continue through P1-P5 until every completion criterion passes or a contract hard stop occurs.

Never edit the frozen contract, add phases, weaken a criterion, fabricate data or reviewer decisions, touch the user's dirty main worktree, restore or replay any completed deletion wave, direct-push main, or publish beyond the authorization envelope. In P5, use only Appendix A.11 exact paths and behavior; A.9/A.10 are historical and no deletion is authorized. Preserve the fixed Windows receipt, all manifests/vectors and runtime dedicated-root enforcement. Verify all completed-wave targets remain absent before and after tests.
```

## Current checkpoint

- **State:** `running`
- **Last completed phase:** `P5`
- **Next phase:** `none`（tracked stage complete；new sealed publication pending）
- **Latest validation:** `pass`。POSIX path-flavour regression 在修复前精确复现 `old002837 absolute directory-vector SHA-256 drift`；修复后 focused 3、V-006 30、V-003 194、V-004 16、V-005 18、V-008 通过；专用工作树和同父目录 independent clone 均为 `978 passed, 2 skipped`。既有 29/2208/relative SHA 与 29/3803/absolute SHA 均不变。
- **Current blocker:** 无。v11 已冻结并通过 package-only setup；A.11 portable receipt repair 正在执行。
- **Active authorization:** 用户原文：“批准创建最小 v11 修订包：仅授权修复 V-006 的跨平台绝对目录向量校验，使普通 Linux checkout 验证冻结的专用 Windows 路径收据，而不以当前 checkout 路径重算该固定哈希；授权将 bcb5356 标记为失败候选并生成新的 sealed candidate。既有相对/绝对向量、1386 文件、29 目录、三波边界、事实语义、完成标准、主工作树保护和发布模式 A 均不变。”
- **Next safe action:** 创建新的 `chore(v1): seal governance cleanup candidate`；此后不再写 tracked 文件，按 V-014 将远端 execution ref 从失败候选 `bcb5356...` 普通 fast-forward 到新 seal，再等待 exact-head push CI。

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

1. Read root `AGENTS.md`, frozen v11 `CONTRACT.md`, this file, `$autonomous-stage-runner`, and all P5-required files completely.
2. Validate package hash/status/branch/baseline before any task mutation.
3. Prove setup commit is package-only and a direct child of `bcb535618367024eb85f8bee7abb8419c56d75eb`.
4. Verify three deletion commits/receipts and complete absence before and after every test group.
5. Use only A.11 exact paths; do not execute deletion or modify any fixed manifest/vector/runtime containment.
6. Run focused portable-receipt tests, V-006, all contract validators, full pytest, same-parent clean-checkout smoke, scope audit and package validation.
7. Preserve `bcb5356...` as failed ancestry; after the new seal, do not write tracked files; publication evidence remains external.
- 2026-07-27T08:48:46+00:00 — state=draft; completed=P4; next=P5; validation=not_run; v10 broad authority approved; finalize package before execution
- 2026-07-27T08:55:33+00:00 — state=running; completed=P4; next=P5; validation=partial; v10 setup 1b0298d verified; begin A.9 closure of 27 references across 12 paths; A.10 extended waves only if retirement-only candidates are proven
- 2026-07-27T09:07:17+00:00 — state=running; completed=P4; next=P5; validation=partial; A.9 route closure complete: active references 27 to 0; focused original regressions 13 passed; route/behavior suites 62 passed and explicit-root subset 36 passed; A.10 extended_wave_count=0 because no retirement-only file candidate was proven; next run full contract validation
- 2026-07-27T09:36:49+00:00 — state=running; completed=P4; next=P5; validation=partial with only independent clean-checkout smoke pending; V-002/V-003/V-004/V-005/V-006/V-008 and full repository pytest passed; 977 passed and 2 unchanged baseline skips; all completed-wave targets remained absent; next create validation checkpoint and run independent local clone smoke
- 2026-07-27T10:18:54+00:00 — state=running; completed=P5; next=none; validation=pass; exact CRLF historical snapshots are preserved by 16 path-specific attributes; independent same-parent clone at 8957416 passed 977 with 2 unchanged skips and remained clean; remote preflight matches frozen refs and no matching PR exists; seal and publication mode A are next
- 2026-07-27T10:20:04+00:00 — state=blocked; completed=P4; next=P5; validation=failed; v10 seal bcb5356 push CI run 30257647025 failed 2 of 29 V-006 tests because Linux pathlib.Path rebuilt a fixed Windows receipt with mixed separators; no PR or merge was created
- 2026-07-27T10:31:00+00:00 — state=draft; completed=P4; next=P5; validation=failed; user approved minimal v11 portable Windows absolute receipt repair and one new sealed candidate; bcb5356 remains failed candidate ancestry; no deletion or vector change authorized
- 2026-07-27T10:38:00+00:00 — state=running; completed=P4; next=P5; validation=partial; v11 setup 718d663 verified package-only with direct parent bcb5356; exact A.11 paths are test, cleanup tool, v11 START and six validation/readout files; first reproduce POSIX path-flavour failure
- 2026-07-27T12:51:32+00:00 — state=running; completed=P4; next=P5; validation=partial; pre-fix POSIX flavour regression reproduced the exact CI drift; PureWindowsPath repair passed focused 3 and full V-006 30; fixed manifests, vectors and deletion containment unchanged; next create portable-receipt fix checkpoint
- 2026-07-27T13:18:41+00:00 — state=running; completed=P5; next=none; validation=pass; dedicated and independent same-parent clone both passed 978 with 2 unchanged skips; all local validators, immutable manifest checks, deletion absence, main status vectors and remote preflight passed; next create new sealed candidate
