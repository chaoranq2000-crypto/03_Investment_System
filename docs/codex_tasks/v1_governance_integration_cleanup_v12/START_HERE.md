---
schema_version: "1"
task_id: "v1_governance_integration_cleanup_v12"
contract_path: "docs/codex_tasks/v1_governance_integration_cleanup_v12/CONTRACT.md"
contract_sha256: "d1eb2910de17dddd3e065ef500461f3ea22d7c434c5a94d0a7c5b90d9e041460"
state: "running"
execution_branch: "codex/v1-governance-integration-cleanup"
source_baseline: "ec1e98c6c9320c135324631ca67dca97dac11619"
last_completed_phase: "P5"
next_phase: "final_validation"
last_validation: "pass"
updated_at: "2026-07-27T16:00:02+00:00"
---
# Start or resume final v12 stabilization

本包是冻结 v11 的最终稳定化修订。P1–P5、C-001–C-014、研究事实语义、完成标准、既有三波删除事实和发布模式 A 均不变。v12 允许在专用工作树内持续修复阻止既定 validator、CI、PR 或 merge 完成的工程缺陷，并允许多个失败 candidate、多个普通 fast-forward 后继 seal；不再为普通工程失败创建新 task package。

最终 ready 后，在专用工作树 `C:\Projects\03_Investment_System_v1_governance_cleanup` 启动并使用：

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/v1_governance_integration_cleanup_v12
Frozen contract: docs/codex_tasks/v1_governance_integration_cleanup_v12/CONTRACT.md
Expected contract SHA-256: PENDING
Execution branch: codex/v1-governance-integration-cleanup
Source baseline: ec1e98c6c9320c135324631ca67dca97dac11619
Historical cleanup snapshot: 312adc73821706b0b7ca6aa00e80ee608bd10b32
Engineering source candidate: f60f220ae252262a537c612ce193fc779901984b
Dedicated worktree: C:\Projects\03_Investment_System_v1_governance_cleanup

Read the complete applicable AGENTS.md instruction chain, CONTRACT.md, START_HERE.md, and every phase-required skill file before acting. Treat the frozen contract as the complete objective, constraints, authority, and definition of done. Do not rely on any previous chat, memory, project journal, Night queue, or unstated decision.

Validate package integrity and repository preflight, then resume P5 stabilization from the earliest unproven postcondition. After every repair cycle, run relevant validators, inspect scope, update START_HERE.md before the provisional seal, and create an explicit Git checkpoint. Continue within v12 through exact-head push CI, exact-head PR CI, guarded merge, and final main CI until every completion criterion passes or a contract hard stop occurs.

Never edit the frozen contract, add phases, weaken a criterion, fabricate data or reviewer decisions, touch the user's dirty main worktree, restore or replay any completed deletion wave, direct-push main, force-push, rebase, squash, delete remote branches, or publish outside mode A. Preserve all historical manifests, receipts, vectors and completed deletion paths. New deletion is allowed only through the root AGENTS.md exact-manifest protocol.
```

## Current checkpoint

- **State:** `running`
- **Last completed phase:** `P5`（历史工程交付完成；publication stabilization 尚未闭合）
- **Next phase:** `final_validation`
- **Latest validation:** `pass`。v11 candidate `ec1e98c6c9320c135324631ca67dca97dac11619` 的 push CI run `30269811587` 已通过 Linux V-006，但 full pytest collection 因 CI 未安装 `jsonschema` 失败。
- **Current blocker:** 无合同 blocker；这是 v12 A.12 内的普通工程稳定化缺陷。
- **Next safe action:** finalize/validate v12，创建 package-only setup commit；随后在 `.github/workflows/ci.yml` 的 conda test dependency install 中补充 `jsonschema`，运行验证并创建普通后继 candidate。

## Frozen external and historical anchors

- Remote main: `a345fafb522300831ed4206d35fa17f44570cb1f`
- Night05: `a96c1b717bf15905d72fd142efd946fa01bce666`
- V1 source: `f60f220ae252262a537c612ce193fc779901984b`
- v10 failed candidate: `bcb535618367024eb85f8bee7abb8419c56d75eb`; CI `30257647025`
- v11 failed candidate / v12 source baseline: `ec1e98c6c9320c135324631ca67dca97dac11619`; CI `30269811587`
- Night deletion: `be42857bf88223e01c71e4a4dfbac8e3a47080aa`
- Bundle deletion: `274d47ec299a42946bc3b83f7908257e80f0f99b`
- old002837 deletion: `b5ebdbfe6ddce7698a438bc8afa69cf5a1c8fbd2`
- Immutable file vector: 1386 files / 9,787,412 content bytes / 121,264 path-vector bytes / SHA-256 `974d45610144d616f69c3c368d9ea1a0a27d66601a24f748aa8148e2ee702f33`
- Immutable directory vectors: 29 relative / 2208 bytes / SHA-256 `1e987f07ab4aa9b7c54a7444b053949b5c5d377655903d9715d8948e42446cd3`; 29 absolute / 3803 bytes / SHA-256 `31669a8f873c2510709a7f9828b27dad4eab9fe49a159071d40345693e770b75`
- 所有 1386 files、29 directories 和 old run root 均 absent，禁止恢复或重放。
- 用户主工作树冻结只读快照：HEAD `a345fafb522300831ed4206d35fa17f44570cb1f`；full 130 rows / 9156 bytes / SHA-256 `1b21ac246cb2ad4b055f5a264503fb1fad8fe9edae153e25c9cd6d19d4a719c0`；tracked 20 rows / 1025 bytes / SHA-256 `3ab441f68037823866029eb2136149a807f6382755966daf96d33a85b965609b`。

## v12 stabilization loop

1. 精确确认 failing SHA、event、step 和日志。
2. 在 A.12 内做最小修复；断言只能保持或增强。
3. 运行针对性、合同矩阵、full pytest、clean checkout 与 scope/absence/main-vector 检查。
4. 在 provisional seal 前更新本文件；显式 stage 和 commit，保持普通 ancestry。
5. 普通 fast-forward push，等待 exact-head push CI。
6. 失败则保留 candidate 并回到步骤 1；无需新 package/version/approval。
7. push CI 成功后创建或复用唯一 PR，等待同 SHA PR CI；失败仍按步骤 1–6 修复并更新同一 PR。
8. 同一 SHA 的 push/PR CI 都成功后锁定 final sealed head，不再写 tracked 文件；执行 exact-head guarded merge commit并等待 final main CI。

## Checkpoint history

- 2026-07-27T22:50:01+08:00 — state=draft; completed=P5; next=none; validation=failed; user authorized final v12 continuous engineering stabilization; `ec1e98c...` retained as failed candidate; immediate proven defect is missing CI `jsonschema`.
- 2026-07-27T14:53:56+00:00 — state=running; completed=P5; next=final_validation; validation=partial; v12 setup fb89525 verified package-only; begin A.12 repair for CI missing jsonschema at run 30269811587
- 2026-07-27T15:17:49+00:00 — state=running; completed=P5; next=final_validation; validation=partial; A.12 jsonschema CI install repair passed focused 80, V-002, V-003 194, V-004 16 with identical digests, V-005 18, V-006 30, V-008 17 capabilities, and full 978 passed with 2 baseline skips; clean clone smoke pending
- 2026-07-27T15:30:02+00:00 — state=running; completed=P5; next=final_validation; validation=pass; A.12 repair validated: dedicated full 978 passed 2 baseline skips; independent clone C:\Projects\v12_clean_checkout_a395325 at a395325 passed 978 with 2 baseline skips and remained clean; V-002/V-003/V-004/V-005/V-006/V-008 and package validation pass; next create provisional seal and ordinary fast-forward push
- 2026-07-27T15:36:04+00:00 — state=running; completed=P5; next=final_validation; validation=fail; provisional candidate 282412c push CI run 30280331693 failed after dependency/V-006 success: Linux checkout materialized two frozen 002837 processed text blobs as LF, so CRLF file-byte receipt mismatch caused 1 failed and 10 errors; preserve facts/hashes and enforce exact eol=crlf checkout paths
- 2026-07-27T15:48:03+00:00 — state=running; completed=P5; next=final_validation; validation=partial; A.12 cross-platform receipt repair: exact two processed text paths enforce eol=crlf; new config assertion and policy-refresh 17 passed; dedicated full 979 passed with 2 baseline skips; fresh clean-clone checkout/hash/full smoke pending
- 2026-07-27T16:00:02+00:00 — state=running; completed=P5; next=final_validation; validation=pass; A.12 receipt repair validated: exact clean-checkout CRLF hashes 0218a5ce and 1c26dcc2; policy-refresh 17 passed; dedicated full 979 passed 2 baseline skips; independent clone C:\Projects\v12_clean_checkout_9edc91b at 9edc91b passed 979 with 2 baseline skips and remained clean; next provisional seal and fast-forward push
