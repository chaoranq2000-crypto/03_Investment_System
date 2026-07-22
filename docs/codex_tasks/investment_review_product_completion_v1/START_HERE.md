---
schema_version: "1"
task_id: "investment_review_product_completion_v1"
contract_path: "docs/codex_tasks/investment_review_product_completion_v1/CONTRACT.md"
contract_sha256: "86d6ba6f4f4365fac03c5ed8797f381d1b888563d84239e3a933be2473e130c6"
state: "blocked"
execution_branch: "codex/investment-review-product-completion"
source_baseline: "b40ef7488bc41d624294a3f6ef5475d5bbefdb0e"
last_completed_phase: "none"
next_phase: "P1"
last_validation: "fail"
updated_at: "2026-07-23T03:03:00+08:00"
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

- **State:** `blocked`
- **Last completed phase:** `none`
- **Next phase:** `P1`
- **Latest validation:** package/branch/baseline/setup/source-DB checks passed, but the project mapping validator failed because `config/investment_review.portfolio.generated.json` does not match its reviewed provenance SHA-256 lock.
- **Current blocker:** before P1, `review.generated_mapping_sha256` expected `a707064ba00cc8795e7e6164b5b7240b4c86a55f7a9aaa4433af3b26cd498b9e`; the worktree file is `bbe59f0dd126933e89c8580a2281893078e3b76baa5c61cac98355da0986d4f3`, and the Git blob is `d79a9e26e426ed6ad4d330b2ec08d0b3aa30fa83acebf0a00551a1bba890065f`. The existing validator raises `MappingError`, so C-DATA-002 cannot be proven without a new human-reviewed mapping provenance decision outside this frozen contract.
- **Next safe action / unblock question:** Will the user authorize an amended `investment_review_product_completion_v2` package that explicitly regenerates and human-reviews the mapping provenance before product-completion execution resumes?

The Git commit containing this file is the checkpoint commit. Do not write that commit's own hash into this file.

The preparation-time observations `portfolio ledger=983`, `existing review trade_events=961`, `decisions=0`, and `portfolio_snapshots=0` are only an as-of snapshot from 2026-07-23. Execution must remeasure current values and use `unsynced=0` at a stable cutoff as the data criterion. The existing review sidecar under `C:\Projects\03_Investment_System_portfolio` is read-only evidence and is not the candidate execution database.

## Checkpoint history

- 2026-07-23T03:03:00+08:00 — Preflight hard stop before P1. V-001 passed; branch, source-baseline ancestry, clean worktree and package-only setup commit were verified. Formal source DB proof was recorded at `.codex_tmp/investment_review_product_completion/source_db_proof.json`: SHA-256 `752e3b87966f23d2e6f3db89cd3a8d5df0ab893504ee4e7e83de793e4aa52f53`, `quick_check=ok`, `ledger_entries=983`, no missing/duplicate source identities, schema hash matched, and the candidate sidecar remained absent. Mapping content and schema-manifest hashes matched, but the generated-mapping provenance hash did not; the project validator reproduced the exact `MappingError`. No phase implementation, real sidecar write, source DB write, UI/API change, or publication was attempted.
- 2026-07-23T02:35:42+08:00 — Package finalized and validated; ready for unattended launch.
