---
schema_version: "1"
task_id: "r5_v1_convergence"
contract_path: "docs/codex_tasks/r5_v1_convergence/CONTRACT.md"
contract_sha256: "5e4a52f8eff0792810a8b0255089a01359a47bafc549edb0bffacb1f4335d163"
state: "ready"
execution_branch: "codex/r5-v1-convergence"
source_baseline: "a96c1b717bf15905d72fd142efd946fa01bce666"
last_completed_phase: "none"
next_phase: "P1"
last_validation: "pass"
updated_at: "2026-07-22T18:46:41+00:00"
---
# Start or resume this stage in a new Codex chat

Open `C:\Projects\03_Investment_System_v1_convergence` as the repository workspace, start a new Codex chat, and paste this block exactly:

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/r5_v1_convergence
Frozen contract: docs/codex_tasks/r5_v1_convergence/CONTRACT.md
Expected contract SHA-256: 5e4a52f8eff0792810a8b0255089a01359a47bafc549edb0bffacb1f4335d163
Execution branch: codex/r5-v1-convergence
Source baseline: a96c1b717bf15905d72fd142efd946fa01bce666
Execution worktree: C:\Projects\03_Investment_System_v1_convergence

Read the complete applicable AGENTS.md instruction chain, CONTRACT.md, and START_HERE.md before acting. Treat the frozen contract as the objective, constraints, and definition of done. Do not rely on any previous chat, memory, old plan, Night queue, or unstated decision.

Validate package integrity and repository preflight, then resume from the earliest phase whose postconditions are not proven. After each phase, run its validators, inspect scope, update START_HERE.md, and create the specified Git checkpoint. Continue without waiting between phases until every completion criterion passes or a contract hard stop occurs. Never modify the frozen contract, add phases, enlarge scope, weaken validation, fabricate external facts or human decisions, or publish beyond its authority.
```

## Current checkpoint

- **State:** `ready`
- **Last completed phase:** `none`
- **Next phase:** `P1`
- **Latest validation:** `pass`
- **Current blocker:** none
- **Next safe action:** Open a new Codex chat in the execution worktree and paste the launch block.

The Git commit containing this file is the checkpoint commit. Do not write that commit's own hash into this file.

## Checkpoint history

- 2026-07-23T02:34:56+08:00 — Package drafted from Night05 exact baseline after read-only ancestry, workflow-authority, validation-path, dirty-worktree, and historical-boundary audits; not yet safe for unattended execution.
- 2026-07-22T18:46:41+00:00 — Package finalized; contract frozen at SHA-256 `5e4a52f8eff0792810a8b0255089a01359a47bafc549edb0bffacb1f4335d163`; ready-package validation and context-independence audit passed with no warnings or blockers.
