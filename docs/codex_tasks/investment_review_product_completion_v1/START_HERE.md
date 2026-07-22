---
schema_version: "1"
task_id: "investment_review_product_completion_v1"
contract_path: "docs/codex_tasks/investment_review_product_completion_v1/CONTRACT.md"
contract_sha256: "86d6ba6f4f4365fac03c5ed8797f381d1b888563d84239e3a933be2473e130c6"
state: "ready"
execution_branch: "codex/investment-review-product-completion"
source_baseline: "b40ef7488bc41d624294a3f6ef5475d5bbefdb0e"
last_completed_phase: "none"
next_phase: "P1"
last_validation: "pass"
updated_at: "2026-07-22T18:42:28+00:00"
---
# Start or resume this stage in a new Codex chat

Open `C:\Projects\03_Investment_System_investment_review_completion` as the repository in a new Codex chat, verify the branch is `codex/investment-review-product-completion`, and paste this block exactly:

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/investment_review_product_completion_v1
Frozen contract: docs/codex_tasks/investment_review_product_completion_v1/CONTRACT.md
Expected contract SHA-256: 86d6ba6f4f4365fac03c5ed8797f381d1b888563d84239e3a933be2473e130c6
Execution worktree: C:\Projects\03_Investment_System_investment_review_completion
Execution branch: codex/investment-review-product-completion
Source baseline: b40ef7488bc41d624294a3f6ef5475d5bbefdb0e

Read the complete applicable AGENTS.md instruction chain, .agents/skills/investment-review/SKILL.md, CONTRACT.md, and START_HERE.md before acting. Treat the frozen contract as the objective, constraints, authority, phases, and definition of done. No prior conversation, memory, another task package, or unstated decision is authoritative.

Validate package integrity and repository preflight, confirm the setup commit contains only the two package files, record the formal portfolio source database SHA-256 before any execution, then resume from the earliest phase whose postconditions are not proven. After each phase, run its validators, inspect scope, update START_HERE.md, and create the specified Git checkpoint. Continue unattended until every completion criterion passes or a contract hard stop occurs. Never modify the frozen contract, enlarge scope, weaken validation, fabricate external facts or human decisions, write the formal portfolio database or the user's existing review sidecar, or publish beyond the contract authority.
```

## Current checkpoint

- **State:** `ready`
- **Last completed phase:** `none`
- **Next phase:** `P1`
- **Latest validation:** `pass`
- **Current blocker:** none
- **Next safe action:** Open a new Codex chat in the execution worktree and paste the launch block.

The Git commit containing this file is the checkpoint commit. Do not write that commit's own hash into this file.

The preparation-time observations `portfolio ledger=983`, `existing review trade_events=961`, `decisions=0`, and `portfolio_snapshots=0` are only an as-of snapshot from 2026-07-23. Execution must remeasure current values and use `unsynced=0` at a stable cutoff as the data criterion. The existing review sidecar under `C:\Projects\03_Investment_System_portfolio` is read-only evidence and is not the candidate execution database.

## Checkpoint history

- 2026-07-23T02:35:42+08:00 — Package finalized and validated; ready for unattended launch.
