---
schema_version: "1"
task_id: "investment_review_product_completion_v2"
contract_path: "docs/codex_tasks/investment_review_product_completion_v2/CONTRACT.md"
contract_sha256: "96973061c04b2cdb1f86b2140efba475e35b623dd45b939d609a0914d1ea922f"
state: "running"
execution_branch: "codex/investment-review-product-completion"
source_baseline: "5a5f02a71ddbdfe8c3327c49ab45ee67e777b79b"
last_completed_phase: "P1"
next_phase: "P2"
last_validation: "pass"
updated_at: "2026-07-23T16:22:05+08:00"
---
# Start or resume this stage in a new Codex chat

Open `C:\Projects\03_Investment_System_investment_review_completion` as the repository in a new Codex chat, verify the branch is `codex/investment-review-product-completion`, and paste this block exactly:

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/investment_review_product_completion_v2
Frozen contract: docs/codex_tasks/investment_review_product_completion_v2/CONTRACT.md
Expected contract SHA-256: 96973061c04b2cdb1f86b2140efba475e35b623dd45b939d609a0914d1ea922f
Execution worktree: C:\Projects\03_Investment_System_investment_review_completion
Execution branch: codex/investment-review-product-completion
Source baseline: 5a5f02a71ddbdfe8c3327c49ab45ee67e777b79b

Read the complete applicable AGENTS.md instruction chain, .agents/skills/investment-review/SKILL.md, CONTRACT.md, and START_HERE.md before acting. Treat the frozen contract as the objective, constraints, authority, phases, and definition of done. No prior conversation, memory, another task package, or unstated decision is authoritative.

Validate package integrity and repository preflight, confirm the v2 setup commit relative to `5a5f02a71ddbdfe8c3327c49ab45ee67e777b79b` contains only the two v2 package files, and record the formal portfolio source database SHA-256 before execution. In P1, resolve only the documented v1 generated-mapping provenance mismatch by regenerating the machine mapping from the formal read-only schema and registering the user-confirmed D-010 semantics and new hashes. Then resume the five phases, running validators, inspecting scope, updating START_HERE.md and creating each specified Git checkpoint. Continue unattended until every completion criterion passes or a contract hard stop occurs. Never modify the frozen contract, enlarge scope, weaken validation, fabricate external facts or human decisions, write the formal portfolio database or the user's existing review sidecar, or publish beyond the contract authority.
```

## Current checkpoint

- **State:** `running`
- **Last completed phase:** `P1`
- **Next phase:** `P2`
- **Latest validation:** `pass`
- **Current blocker:** none.
- **Next safe action:** From a clean P1 checkpoint, implement P2 read-only full-table sync, explicit candidate-sidecar resolution, fee projection/correction CLI, post-commit failure-isolated trigger, and V-201/V-202 evidence. Do not add runner, Web/UI or periodic scheduling in P2.

The Git commit containing this file is the checkpoint commit. Do not write that commit's own hash into this file.

The v1 source proof recorded portfolio SHA-256 `752e3b87966f23d2e6f3db89cd3a8d5df0ab893504ee4e7e83de793e4aa52f53`, `quick_check=ok` and `ledger_entries=983` on 2026-07-23, but v2 execution must remeasure current values. The existing review sidecar under `C:\Projects\03_Investment_System_portfolio` is read-only evidence and is not the candidate execution database.

## Checkpoint history

- 2026-07-23T16:22:05+08:00 — P1 completed. The formal source was opened read-only, `quick_check=ok`, `ledger_entries=983`, and its SHA-256 remained `752e3b87966f23d2e6f3db89cd3a8d5df0ab893504ee4e7e83de793e4aa52f53`. Doctor regeneration reproduced generated-mapping SHA-256 `bbe59f0dd126933e89c8580a2281893078e3b76baa5c61cac98355da0986d4f3`; the reviewed lock was amended from registered `a707064ba00cc8795e7e6164b5b7240b4c86a55f7a9aaa4433af3b26cd498b9e` to that raw hash, reviewer `workspace_user`, actual review time, schema-manifest SHA-256 `a4e23bf8d6bfe8b0cd15d2241e65fca1fe0305b7ffb3495fd57abaee9c4b34f0`, and canonical content SHA-256 `2eddc1c2aafe221fcd94c2c51d84c646174df5489b73bfcf1c171f55988c1c8a`. D-010 semantic assertions and `_require_reviewed_sqlite_mapping` passed; evidence is under `.codex_tmp/investment_review_product_completion_v2/mapping_refresh_*.json`. Product-completion boundaries, the fixed fee method, explicit opt-in additive schema, append-only corrections and deterministic run metadata were added without real sidecar execution. V-101 passed `30`; the additional full investment-review compatibility run passed `724` with `695` deselected. `git diff --check`, package validation and P1 scope review passed; unknown historical decisions remain intentionally unknown, with no P1 blocker.
- 2026-07-23T15:50:00+08:00 — Package finalized and validated with contract SHA-256 `96973061c04b2cdb1f86b2140efba475e35b623dd45b939d609a0914d1ea922f`; package-only setup commit is `0b98806`. The mutable launch block was corrected to carry the frozen hash before execution.
- 2026-07-23T15:37:46+08:00 — v2 amendment drafted from source baseline `5a5f02a71ddbdfe8c3327c49ab45ee67e777b79b`. It preserves the v1 objective and five phases while adding one bounded P1 mapping-provenance regeneration based on explicit user-confirmed semantics. Not safe to execute until finalized and validated.
