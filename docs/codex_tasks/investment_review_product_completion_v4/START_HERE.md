---
schema_version: "1"
task_id: "investment_review_product_completion_v4"
contract_path: "docs/codex_tasks/investment_review_product_completion_v4/CONTRACT.md"
contract_sha256: "b74d5f00e28b7f2f9590a69ca7427384b25c7122369919803b9423d1c0715d4c"
state: "ready"
execution_branch: "codex/investment-review-reviewability-corrections"
source_baseline: "92181d0fe7b3d8bf48bd8d69977b4ba00bbad4f7"
last_completed_phase: "P5"
next_phase: "P6"
last_validation: "pass"
updated_at: "2026-07-27T00:34:20+08:00"
---
# Start or resume this stage in a new Codex chat

Open `C:\Projects\03_Investment_System_investment_review_reviewability` as the repository in a new Codex chat, verify branch `codex/investment-review-reviewability-corrections`, and paste this block exactly after the package is finalized:

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/investment_review_product_completion_v4
Frozen contract: docs/codex_tasks/investment_review_product_completion_v4/CONTRACT.md
Expected contract SHA-256: b74d5f00e28b7f2f9590a69ca7427384b25c7122369919803b9423d1c0715d4c
Execution worktree: C:\Projects\03_Investment_System_investment_review_reviewability
Execution branch: codex/investment-review-reviewability-corrections
Source baseline: 92181d0fe7b3d8bf48bd8d69977b4ba00bbad4f7

Read the complete applicable AGENTS.md instruction chain, .agents/skills/investment-review/SKILL.md, v4 CONTRACT.md, and v4 START_HERE.md before acting. Read the frozen v3 CONTRACT.md and blocked v3 START_HERE.md only to verify that the exact predecessor files/hash/hard-stop commit named by v4 are unchanged; all inherited evidence needed for execution is serialized in v4. Treat the frozen v4 contract as the objective, constraints, authority, phases, and definition of done. No prior conversation, memory, unstated decision, or another package may enlarge or replace v4 authority.

Validate package integrity and repository preflight. Confirm the v4 package-only setup commit relative to 92181d0fe7b3d8bf48bd8d69977b4ba00bbad4f7 contains only the two v4 package files, the frozen v3 files are unchanged, and the ten carried P6 paths match the v4 manifest before any P6 mutation. Record SHA-256, size, quick_check and WAL/SHM state for the formal portfolio database, the user's review sidecar, the v2 candidate, and hash/marker/manifest/DDL integrity for the existing authorized v3-path candidate. Never create or write another real sidecar. Only after synthetic compatibility validators pass, perform the contract's single exact-v1-gated, atomic no-DDL v2 marker upgrade on that existing candidate; preserve and replay every v1 row.

P1-P5 count as completed only when their named commits, ancestry, the evidence serialized in v4, and compatibility validators prove their postconditions. Resume at P6. First implement and validate public_availability_user_knowledge_v1 plus local_first_controlled_fallback_v2 with explicit operation anchors and separate user/system eligibility; then review and complete the carried P6 adapter/bundle/runner/checkpoint/automation work. For user perspective, a real late fetch may qualify only when the exact historical version and its publication interval are verified before the operation anchor; for system perspective, only the real system observation time qualifies. Unknown, conflicting, post-operation or revision-unproven information stays explicit. Every market limitation must still produce a frozen manifest and active operation checkpoint; never backdate or claim actual user reading. After every phase, run the exact validators and protected-source checks, inspect scope, update v4 START_HERE.md, and create the specified Git checkpoint. Continue unattended until every v4 completion criterion passes or a contract hard stop occurs.

Use an existing allowlisted provider only from the P6 pre-bundle cache step and only after versioned perspective-eligible local coverage returns missing, stale or insufficient. A user-policy request may occur after the historical cutoff; preserve its real receipt/fetch/system-observed times and require version-bound publication provenance. A system request that cannot improve operation-time system eligibility remains zero-network. Obey all caps, provenance and create-only cache limits. Renderer, source replay, API and UI never access the network. Never modify either frozen contract, enlarge scope, weaken v1/v2 validation, fabricate public/version time, external facts or human decisions, write a protected database or unauthorized sidecar, infer investment motives, claim actual user reading, or publish beyond v4 authority.
```

## Current checkpoint

- **State:** `ready`
- **Last completed phase:** `P5` — inherited only from exact v3 commits/evidence and subject to v4 compatibility preflight.
- **Next phase:** `P6`
- **Latest validation:** `pass` — finalizer froze the contract at SHA-256 `b74d5f00e28b7f2f9590a69ca7427384b25c7122369919803b9423d1c0715d4c`; `--require-ready` returned `ok=true`, 0 errors and the expected inherited-phase warning (`ready package normally has last_completed_phase none`).
- **Current blocker:** none. v4 is frozen and ready; user authorization, fixed publication-time policy, strict-before anchor boundary, exact P7 scope, and existing-candidate no-DDL storage decision are serialized in the contract. Frozen v3 remains blocked and unchanged.
- **Next safe action:** Create and validate the package-only setup commit, remeasure protected sources and the existing candidate, then verify the ten carried P6 paths before the first P6 code mutation.

The Git commit containing this file is the checkpoint commit. Do not write that commit's own hash into this file.

## Checkpoint history

- 2026-07-26T23:42:00+08:00 — Drafted independent v4 amendment from source baseline `92181d0fe7b3d8bf48bd8d69977b4ba00bbad4f7` after explicit user authorization. The initial draft preserved the frozen v3 package and exact ten-path P6 carry manifest but still used late-clock cutoff withholding; it remained draft and was never executed.
- 2026-07-27 — Incorporated the user's fixed publication-time rule before finalization: user knowledge eligibility is based on the verified exact-version publication interval before the operation anchor, not later search/fetch time; system eligibility remains real observation-time based; actual acquisition times remain audit facts; no actual-reading or motive inference is allowed. Added full v2 discriminator/schema/replay, hostile paired user/system criteria, and an exact-v1-gated atomic no-DDL marker upgrade for the already-authorized existing candidate, with no new sidecar. The draft remains non-executable until validation, finalization and setup-only commit checks pass.
- 2026-07-27T00:22:51+08:00 — Draft validator passed with `ok=true`, 0 errors and 0 warnings after the publication-time and existing-candidate storage amendments. Informational draft contract SHA-256 is `961f65ea2de599964c7ad4b314cb926449b617806c989a7db2570f637bac9713`; it will change during finalization.
- 2026-07-27T00:30:36+08:00 — Revalidated the complete current draft after serializing exact P7 paths, adding operation-anchor event/order identity, fixing the formal 588200 paired user/system expectation, and closing the no-DDL store scope. Result: `ok=true`, 0 errors, 0 warnings; informational draft contract SHA-256 `601d20dcf6a7abc39b60af53c3c66441ea62198b2bd32efe05ffbbef8a03538b`.
- 2026-07-27T00:32:50+08:00 — Froze the literal “before operation” boundary as strict `publication upper_bound < operation_anchor`; equality is ambiguous/ineligible for user, while real system observation retains `<= anchor`. Independent semantic/scope audit found no blocker. Draft validation returned 0 errors/0 warnings; informational SHA-256 `39e9f93a05f904c4db67f85abe4e00f2ffd93a8c703fdb0f6357f7a0fa589186`.
- 2026-07-27T00:34:20+08:00 — Finalized v4 after explicit user authorization and continuation. Frozen contract SHA-256 is `b74d5f00e28b7f2f9590a69ca7427384b25c7122369919803b9423d1c0715d4c`; `--require-ready` returned `ok=true`, 0 errors, and only the expected warning because P1-P5 are inherited rather than `none`. No P6 source was mutated during package preparation.
