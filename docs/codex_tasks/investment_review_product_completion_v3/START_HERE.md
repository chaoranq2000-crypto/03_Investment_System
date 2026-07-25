---
schema_version: "1"
task_id: "investment_review_product_completion_v3"
contract_path: "docs/codex_tasks/investment_review_product_completion_v3/CONTRACT.md"
contract_sha256: "1f566582eec30ec4d3efc9e0c2349912468642edae32ba79997bb76de6f35033"
state: "ready"
execution_branch: "codex/investment-review-reviewability-corrections"
source_baseline: "c3e296661c04b9de35795e2311674b507846d19a"
last_completed_phase: "none"
next_phase: "P1"
last_validation: "pass"
updated_at: "2026-07-25T13:03:16+08:00"
---
# Start or resume this stage in a new Codex chat

Open `C:\Projects\03_Investment_System_investment_review_reviewability` as the repository in a new Codex chat, verify the branch is `codex/investment-review-reviewability-corrections`, and paste this block exactly when the frontmatter state is `ready`:

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/investment_review_product_completion_v3
Frozen contract: docs/codex_tasks/investment_review_product_completion_v3/CONTRACT.md
Expected contract SHA-256: 1f566582eec30ec4d3efc9e0c2349912468642edae32ba79997bb76de6f35033
Execution worktree: C:\Projects\03_Investment_System_investment_review_reviewability
Execution branch: codex/investment-review-reviewability-corrections
Source baseline: c3e296661c04b9de35795e2311674b507846d19a

Read the complete applicable AGENTS.md instruction chain, .agents/skills/investment-review/SKILL.md, CONTRACT.md, and START_HERE.md before acting. Treat the frozen contract as the objective, constraints, authority, phases, and definition of done. No prior conversation, memory, another task package, or unstated decision is authoritative.

Validate package integrity and repository preflight. Confirm the package-only setup commit relative to c3e296661c04b9de35795e2311674b507846d19a contains only the two v3 package files. Before any execution, record SHA-256, size, quick_check and WAL/SHM state for the formal portfolio database, the user's existing review sidecar, and the v2 candidate sidecar. Create and write only the new v3 candidate sidecar named by the contract.

Resume from the earliest phase whose postconditions are not proven. After each phase, run its validators and protected-source checks, inspect scope, update START_HERE.md, and create the specified Git checkpoint. Continue unattended until every completion criterion passes or a contract hard stop occurs. For market context, use the contract's `local_first_controlled_fallback_v1`: call an existing allowlisted provider only from the pre-bundle cache step and only after a versioned check proves local data `missing`, `stale`, or `insufficient`; obey all request caps, provenance and cache-write limits, and never let renderer, source replay, API or UI access the network. Never modify the frozen contract, enlarge scope, weaken validation, fabricate external facts or human decisions, write any protected database or old sidecar, infer investment motives, or publish beyond the contract authority.
```

## Current checkpoint

- **State:** `ready`
- **Last completed phase:** `none`
- **Next phase:** `P1`
- **Latest validation:** `pass` — finalizer and `--require-ready` validation accepted frozen contract `1f566582eec30ec4d3efc9e0c2349912468642edae32ba79997bb76de6f35033`, 7 consecutive phases, 0 errors and 0 warnings.
- **Current blocker:** none
- **Next safe action:** Open a new Codex chat in the execution worktree and paste the launch block.

The Git commit containing this file is the checkpoint commit. Do not write that commit's own hash into this file.

## Checkpoint history

- 2026-07-25T13:03:16+08:00 — Finalized package version 3 after explicit user approval. Frozen contract SHA-256 is `1f566582eec30ec4d3efc9e0c2349912468642edae32ba79997bb76de6f35033`; task state is `ready`; finalizer validation returned 0 errors and 0 warnings. The next safe action is P1 execution from the package-only setup checkpoint.
- 2026-07-25T12:57:24+08:00 — Workspace user confirmed the final v3 objective and acceptance criteria with `local_first_controlled_fallback_v1`: local cache first; only `missing`, `stale` or `insufficient` coverage may trigger a bounded existing allowlisted provider before bundle freeze; writes stay in the new v3 cache/sidecar; renderer, source replay, API and UI remain offline. Draft validation must be rerun before finalization.
- 2026-07-25T03:25:18+08:00 — Added explicit v3 source reconciliation and protected-file criteria, replaced abbreviated evidence paths with exact paths, and revalidated the draft with 0 errors and 0 warnings. Current draft hash is `e4243ca18586dcdc647c0c047f2eced0184e8fd0c46232dae470b5f819770f75`.
- 2026-07-25T03:23:26+08:00 — Draft package validation passed with 0 errors and 0 warnings. The draft hash is informational only and will change during finalization; the launch block remains `PENDING`.
- 2026-07-25T03:12:10+08:00 — v3 amendment drafted from source baseline `c3e296661c04b9de35795e2311674b507846d19a`. It defines seven reviewability corrections, a new isolated candidate sidecar, protected-source hashes, real 588200 acceptance, local-cache-only automatic market context, and a local-only publication boundary. It is not safe to execute until explicitly approved, finalized, validated, and committed as a package-only setup checkpoint.
