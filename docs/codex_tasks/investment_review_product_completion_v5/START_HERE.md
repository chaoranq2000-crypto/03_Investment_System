---
schema_version: "1"
task_id: "investment_review_product_completion_v5"
contract_path: "docs/codex_tasks/investment_review_product_completion_v5/CONTRACT.md"
contract_sha256: "b94d0d260fd5db0d7de822d1bfd3acd3b5f319d1c81a2deb695a5b818aae9638"
state: "ready"
execution_branch: "codex/investment-review-reviewability-corrections"
source_baseline: "ee689f6a96e74033bf7ed48365bc3f75daa92e4b"
last_completed_phase: "P5"
next_phase: "P6"
last_validation: "pass"
updated_at: "2026-07-27T05:19:02+00:00"
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

Validate package integrity and repository preflight. Confirm the v5 package-only setup commit relative to ee689f6a96e74033bf7ed48365bc3f75daa92e4b adds only the two v5 package files and the 18-path P6 carry manifest remains exact. Record SHA-256, size, quick_check and WAL/SHM state for the formal portfolio database, the user's review sidecar, the v2 candidate and the existing authorized exact-v2 candidate. The candidate must enter with main SHA-256 9eefa6e70e08c61841041e83ca2084e490a0124fcaa9570574922f6fbe092c8e, absent WAL/SHM, exact v2 markers/manifest, unchanged DDL and exactly the two immutable v1 checkpoints named by the contract.

Resume at P6. Fix only the Windows post-close auxiliary proof: after marker commit, successful TRUNCATE and writer close, permit the initial zero-WAL+paired-SHM to terminate as absent/absent while keeping main/path binding and all early/hostile checks strict. Validate on temporary candidates first. Never call upgrade_reviewability_candidate_v2 or execute marker SQL on the real candidate. Then run the post-marker 588200 user/system dry/apply/repeat acceptance, complete P6 and checkpoint it before any P7 mutation.

Preserve v4 public_availability_user_knowledge_v1 and local_first_controlled_fallback_v2 exactly. Verified exact-version publication upper bound strictly before the operation anchor may qualify only the user policy perspective; system eligibility still requires real observation by the anchor. Actual fetch/audit times are never backdated, actual user reading is never claimed, limitations remain explicit and all renderer/replay/API/UI consumers stay offline. Continue unattended through P7 and final validators until every v5 criterion passes or a contract hard stop occurs.

Never modify a frozen contract, predecessor package, protected database or old checkpoint; never rerun the real marker, enlarge scope, weaken validation, fabricate external facts or human decisions, infer investment motives, add dependencies/providers, or publish beyond v5 authority.
```

## Current checkpoint

- **State:** `ready`
- **Last completed phase:** `P5` — inherited from exact v3/v4 commits and evidence; within P6 the real marker subpostcondition is proven exact-v2, but P6 as a phase is incomplete.
- **Next phase:** `P6`
- **Latest validation:** `pass` — frozen contract SHA-256 `b94d0d260fd5db0d7de822d1bfd3acd3b5f319d1c81a2deb695a5b818aae9638`; `--require-ready` returned `ok=true`, 0 errors and the expected inherited-P5 warning.
- **Current blocker:** none. User authority for the exact-v2 successor, Windows terminal-transition repair and no-marker post-P6 continuation is explicit.
- **Next safe action:** Validate the frozen package and package-only diff, run V-003/V-004/V-002, then begin the narrowly authorized P6 Windows recovery mutation; do not touch the real candidate before those gates pass.

The Git commit containing this file is the checkpoint commit. Do not write that commit's own hash into this file.

## Checkpoint history

- 2026-07-27T13:19:02+08:00 — Finalized v5 after independent contract-design and preflight audits returned GO on draft SHA `4092d80d39f35f2fe38be0c92374e0064afd285664dc1cdddf6e9a61d0fb2987`. Frozen SHA is `b94d0d260fd5db0d7de822d1bfd3acd3b5f319d1c81a2deb695a5b818aae9638`. Preserved the v4 P7 sync apply/repeat gate but limited its writes to the contract-enumerated audit/provenance set; P6 remains no-direct-sync-apply. No P6 code or database write occurred.
- 2026-07-27T12:50:47+08:00 — Drafted v5 from source baseline `ee689f6a96e74033bf7ed48365bc3f75daa92e4b` after the user's explicit successor authorization. Serialized the exact-v2 candidate entrance, no-retry marker provenance, strict Windows paired terminal transition, 18-path carry manifest, post-marker real acceptance and unchanged v4/P7 completion boundaries. Draft only; no P6 code or database write occurred.
