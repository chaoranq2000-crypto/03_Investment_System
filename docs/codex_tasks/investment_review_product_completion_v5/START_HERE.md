---
schema_version: "1"
task_id: "investment_review_product_completion_v5"
contract_path: "docs/codex_tasks/investment_review_product_completion_v5/CONTRACT.md"
contract_sha256: "b94d0d260fd5db0d7de822d1bfd3acd3b5f319d1c81a2deb695a5b818aae9638"
state: "blocked"
execution_branch: "codex/investment-review-reviewability-corrections"
source_baseline: "ee689f6a96e74033bf7ed48365bc3f75daa92e4b"
last_completed_phase: "P6"
next_phase: "P7"
last_validation: "failed"
updated_at: "2026-07-27T08:05:14+00:00"
---
# Start or resume this stage in a new Codex chat

Open `C:\Projects\03_Investment_System_investment_review_reviewability` as the repository in a new Codex chat, verify branch `codex/investment-review-reviewability-corrections`, and paste this block exactly after the package is finalized:

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/investment_review_product_completion_v5
Frozen contract: docs/codex_tasks/investment_review_product_completion_v5/CONTRACT.md
Expected contract SHA-256: b94d0d260fd5db0d7de822d1bfd3acd3b5f319d1c81a2deb695a5b818aae9638
Execution worktree: C:\Projects\03_Investment_System_investment_review_reviewability
Execution branch: codex/investment-review-reviewability-corrections
Source baseline: ee689f6a96e74033bf7ed48365bc3f75daa92e4b

Read the complete applicable AGENTS.md instruction chain, .agents/skills/investment-review/SKILL.md, v5 CONTRACT.md, and v5 START_HERE.md before acting. Read the frozen v3/v4 packages only to verify the exact predecessor files, hashes, commits and hard-stop evidence serialized in v5. Treat the frozen v5 contract as the objective, constraints, authority, phases and definition of done. No prior conversation, memory, unstated decision or another package may enlarge or replace v5 authority.

Validate package integrity and repository preflight. Confirm the v5 package-only setup commit relative to ee689f6a96e74033bf7ed48365bc3f75daa92e4b adds only the two v5 package files, then verify the P6 checkpoint ancestry and changed paths recorded below. The pre-mutation 18-path carry manifest is setup/P6-entry evidence and is not the expected post-P6 content hash. Record SHA-256, size, quick_check and WAL/SHM state for the formal portfolio database, the user's review sidecar, the v2 candidate and the authorized exact-v2 candidate.

Resume at P7. P6 is proven by its checkpoint plus `.codex_tmp/investment_review_product_completion_v5/`: Windows recovery tests passed, the real marker was not rerun, and post-marker acceptance completed `2→3→3→4→4`. The candidate main is 4,874,240 bytes/SHA-256 `52c7f2d238046ca95c52a6718eab3c2223ee85f2eccdc70d7fcc937728d650aa`, with zero-byte WAL + paired 32,768-byte SHM, exact v2 markers/manifest/DDL, two unchanged v1 checkpoints and two new authorized v2 tuples. Do not rerun the P6 one-shot or modify its create-only evidence.

P7 is now at a contract hard stop after a partially completed V-801. V-701 passed `127` tests, V-702 passed `19` Vitest tests plus Vite build, and V-703 passed `18` hostile tests. V-801 doctor, sync dry/apply/repeat and `single:user/system` apply/repeat completed; do not rerun those operations. The sync apply/repeat each reported `inserted=0`, `skipped=983`, and added only the authorized SKIPPED ingest audit rows plus run metadata. The current candidate main is 5,627,904 bytes/SHA-256 `ffb7e377eb1e78e4bb72ff9df71d5f9b45021d6d666d835faf07baba630bd5cd`, with absent WAL/SHM, exact marker/DDL, four unchanged checkpoint payloads and target tuple count `2`; all three protected databases remain exact. `weekly:user` then failed at the snapshot stage for open episode `te_232e61991189477cacf7ce8dea4f5723` / `002997.SZ`. Preserve `.codex_tmp/investment_review_product_completion_v5/p7_real/acceptance_failure.json` and all partial evidence; do not delete, overwrite or conceal the failed receipt.

The read-only diagnosis proved the root cause is the core closed-model aggregate rule in `src/investment_review/models.py`: the snapshot axis has `position_quantity=partial`, `cost_basis=partial`, and the remaining components explicitly `missing`, but `_canonical_status_axes` rejects the truthful aggregate `partial` because it incorrectly requires at least one component with status `available`. A minimal implementation correction and regression test require paths outside v5 P7 authority. Do not reinterpret or enlarge v5. Await an explicit user decision authorizing a successor amendment before any further source or candidate write; the successor must resume from this create-only state, preserve the failed evidence, and retry only the unproven weekly/monthly/API/browser/final postconditions without rerunning marker, sync apply/repeat or the accepted single runs.

Preserve v4 public_availability_user_knowledge_v1 and local_first_controlled_fallback_v2 exactly. Verified exact-version publication upper bound strictly before the operation anchor may qualify only the user policy perspective; system eligibility still requires real observation by the anchor. Actual fetch/audit times are never backdated, actual user reading is never claimed, limitations remain explicit and all renderer/replay/API/UI consumers stay offline. Continue unattended through P7 and final validators until every v5 criterion passes or a contract hard stop occurs.

Never modify a frozen contract, predecessor package, protected database or old checkpoint; never rerun the real marker, enlarge scope, weaken validation, fabricate external facts or human decisions, infer investment motives, add dependencies/providers, or publish beyond v5 authority.
```

## Current checkpoint

- **State:** `blocked`
- **Last completed phase:** `P6` — Windows paired auxiliary terminal transition, v2 compatibility/market gates and real post-marker `588200.SH` paired acceptance are proven; the real marker invocation count remained zero in v5.
- **Next phase:** `P7`
- **Latest validation:** `failed` — V-701 `127 passed`, V-702 `19 passed` plus build, and V-703 `18 passed`; V-801 doctor/sync/single gates passed, then `weekly:user` failed in snapshot checkpoint construction with `ModelValidationError: snapshot partial requires both available and limited components`.
- **Current blocker:** The truthful `002997.SZ` snapshot has partial quantity/cost plus explicitly missing cash/valuation fields. Correcting the aggregate `partial` validator requires `src/investment_review/models.py` and a regression test, but those paths are outside frozen v5 P7 authority. Failure evidence SHA-256 is `050daf53c97849dbce7688140d44e755e0cc0f698f2965b2ace2d17a2704a8ed`; failed weekly receipt SHA-256 is `6144c167505b91d7dd1191544a2259cb44232100c43b05d3ec3f17837070f07b`.
- **Next safe action:** Ask exactly: “是否授权建立 v6 后继修正包，将实现权限最小扩展到 `src/investment_review/models.py` 与 `tests/test_investment_review_reviewability_contract.py`（只有证明必要时才增加 `tests/test_investment_review_ledger_snapshot_reconstruction.py`），保留本次失败和已完成的 create-only 写入，从 `weekly:user` 后验收继续，不重跑 marker、sync apply/repeat 或已通过的 single runs？” Until answered, perform read-only inspection only.

The Git commit containing this file is the checkpoint commit. Do not write that commit's own hash into this file.

## Checkpoint history

- 2026-07-27T16:05:14+08:00 — P7 reached an authorization-boundary hard stop during V-801. V-701/V-702/V-703 passed; doctor, sync dry/apply/repeat and both single perspectives completed with zero external network. The two sync runs each inserted `0`, skipped `983`, and their 1,966 new ingest events are all `SKIPPED`. `weekly:user` then failed on open `002997.SZ` episode `te_232e61991189477cacf7ce8dea4f5723`; read-only instrumentation identified the exact core validator defect: a snapshot with partial quantity/cost and explicitly missing remaining components is rejected because `models.py` requires an `available` component for aggregate `partial`. The candidate remains exact-v2 with unchanged marker/DDL/four checkpoint payloads/target tuple count `2`; current main is 5,627,904 bytes/SHA-256 `ffb7e377eb1e78e4bb72ff9df71d5f9b45021d6d666d835faf07baba630bd5cd`, WAL/SHM absent. Formal DB, user sidecar and v2 candidate are exact. Fixing the core validator is outside v5 P7 allowed paths, so no retry or further write is authorized without a successor amendment.
- 2026-07-27T15:11:28+08:00 — Completed P6 without rerunning the real marker. Tightened the Windows guard so only committed + exact `(0,0,0)` checkpoint + closed writer permits the held zero-WAL/paired-SHM terminal transition; V-104/V-101/V-501/V-610/V-601 all passed. Three independent V-612 static audits returned GO on post-marker script SHA `9ed05481bfa63d0f1811321c07086429887455350233a9e53b16329df321086c`. V-801P6 produced byte-identical apply/repeat receipts, user known-by-policy/system retrospective truth, `already_reconciled`, zero network, six create-only cache files and checkpoint counts `2→3→3→4→4`. Summary SHA is `9338e7813c59bad1f0aae7a35ee4b0001fcdfb5b1133aafbe482e9872d68beec`; final candidate SHA is `52c7f2d238046ca95c52a6718eab3c2223ee85f2eccdc70d7fcc937728d650aa`. P6-exit V-002 passed; only `operation_checkpoint_gaps`, `operation_review_checkpoints`, `review_run_status_events` and `review_runs` changed among candidate tables.
- 2026-07-27T14:54:49+08:00 — Classified and recovered an executor-created read-only auxiliary side effect under the updated autonomous-stage-runner rules without changing the frozen v5 contract or rerunning marker. Before recovery the candidate main remained exact while WAL was 0 bytes and SHM was the known 32,768-byte object, both with no open handle; each explicit auxiliary file was removed separately under the user's continue authority. `P6_PRE_REAL_RECOVERED` V-002 then passed with absent/absent, two unchanged v1 checkpoints and target tuple count 0. Durable evidence is `.codex_tmp/investment_review_product_completion_v5/p6_real/auxiliary_recovery.json`.
- 2026-07-27T13:19:02+08:00 — Finalized v5 after independent contract-design and preflight audits returned GO on draft SHA `4092d80d39f35f2fe38be0c92374e0064afd285664dc1cdddf6e9a61d0fb2987`. Frozen SHA is `b94d0d260fd5db0d7de822d1bfd3acd3b5f319d1c81a2deb695a5b818aae9638`. Preserved the v4 P7 sync apply/repeat gate but limited its writes to the contract-enumerated audit/provenance set; P6 remains no-direct-sync-apply. No P6 code or database write occurred.
- 2026-07-27T12:50:47+08:00 — Drafted v5 from source baseline `ee689f6a96e74033bf7ed48365bc3f75daa92e4b` after the user's explicit successor authorization. Serialized the exact-v2 candidate entrance, no-retry marker provenance, strict Windows paired terminal transition, 18-path carry manifest, post-marker real acceptance and unchanged v4/P7 completion boundaries. Draft only; no P6 code or database write occurred.
