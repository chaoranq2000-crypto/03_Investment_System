---
schema_version: "1"
task_id: "investment_review_product_completion_v2"
contract_path: "docs/codex_tasks/investment_review_product_completion_v2/CONTRACT.md"
contract_sha256: "96973061c04b2cdb1f86b2140efba475e35b623dd45b939d609a0914d1ea922f"
state: "ready"
execution_branch: "codex/investment-review-product-completion"
source_baseline: "5a5f02a71ddbdfe8c3327c49ab45ee67e777b79b"
last_completed_phase: "none"
next_phase: "P1"
last_validation: "pass"
updated_at: "2026-07-23T07:44:05+00:00"
---
# Start or resume this stage in a new Codex chat

Open `C:\Projects\03_Investment_System_investment_review_completion` as the repository in a new Codex chat, verify the branch is `codex/investment-review-product-completion`, and paste this block exactly:

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/investment_review_product_completion_v2
Frozen contract: docs/codex_tasks/investment_review_product_completion_v2/CONTRACT.md
Expected contract SHA-256: PENDING
Execution worktree: C:\Projects\03_Investment_System_investment_review_completion
Execution branch: codex/investment-review-product-completion
Source baseline: 5a5f02a71ddbdfe8c3327c49ab45ee67e777b79b

Read the complete applicable AGENTS.md instruction chain, .agents/skills/investment-review/SKILL.md, CONTRACT.md, and START_HERE.md before acting. Treat the frozen contract as the objective, constraints, authority, phases, and definition of done. No prior conversation, memory, another task package, or unstated decision is authoritative.

Validate package integrity and repository preflight, confirm the v2 setup commit relative to `5a5f02a71ddbdfe8c3327c49ab45ee67e777b79b` contains only the two v2 package files, and record the formal portfolio source database SHA-256 before execution. In P1, resolve only the documented v1 generated-mapping provenance mismatch by regenerating the machine mapping from the formal read-only schema and registering the user-confirmed D-010 semantics and new hashes. Then resume the five phases, running validators, inspecting scope, updating START_HERE.md and creating each specified Git checkpoint. Continue unattended until every completion criterion passes or a contract hard stop occurs. Never modify the frozen contract, enlarge scope, weaken validation, fabricate external facts or human decisions, write the formal portfolio database or the user's existing review sidecar, or publish beyond the contract authority.
```

## Current checkpoint

- **State:** `ready`
- **Last completed phase:** `none`
- **Next phase:** `P1`
- **Latest validation:** `pass`
- **Current blocker:** none; the v1 provenance mismatch is an explicit P1 amendment target, not a waived validator.
- **Next safe action:** Finalize and validate this v2 package, create a package-only setup commit, then execute P1.

The Git commit containing this file is the checkpoint commit. Do not write that commit's own hash into this file.

The v1 source proof recorded portfolio SHA-256 `752e3b87966f23d2e6f3db89cd3a8d5df0ab893504ee4e7e83de793e4aa52f53`, `quick_check=ok` and `ledger_entries=983` on 2026-07-23, but v2 execution must remeasure current values. The existing review sidecar under `C:\Projects\03_Investment_System_portfolio` is read-only evidence and is not the candidate execution database.

## Checkpoint history

- 2026-07-23T15:37:46+08:00 — v2 amendment drafted from source baseline `5a5f02a71ddbdfe8c3327c49ab45ee67e777b79b`. It preserves the v1 objective and five phases while adding one bounded P1 mapping-provenance regeneration based on explicit user-confirmed semantics. Not safe to execute until finalized and validated.
