---
schema_version: "1"
task_id: "investment_review_product_completion_v6"
contract_path: "docs/codex_tasks/investment_review_product_completion_v6/CONTRACT.md"
contract_sha256: "8b0d14a61153603bb4500d1d58803e40e207ba629014baa0b4aad8f1e11da8f4"
state: "blocked"
execution_branch: "codex/investment-review-reviewability-corrections"
source_baseline: "bd842e2f7e5960fcb570f5ea092c94ea38a7b5da"
last_completed_phase: "none"
next_phase: "P1"
last_validation: "fail"
updated_at: "2026-07-27T08:43:13+00:00"
---
# Start or resume this stage in a new Codex chat

Open `C:\Projects\03_Investment_System_investment_review_reviewability` as the repository in a new Codex chat and paste:

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/investment_review_product_completion_v6
Frozen contract: docs/codex_tasks/investment_review_product_completion_v6/CONTRACT.md
Expected contract SHA-256: 8b0d14a61153603bb4500d1d58803e40e207ba629014baa0b4aad8f1e11da8f4
Execution worktree: C:\Projects\03_Investment_System_investment_review_reviewability
Execution branch: codex/investment-review-reviewability-corrections
Source baseline: bd842e2f7e5960fcb570f5ea092c94ea38a7b5da

Read the complete applicable AGENTS.md instruction chain, .agents/skills/investment-review/SKILL.md, v6 CONTRACT.md and v6 START_HERE.md before acting. Treat v6 as the objective, constraints, authority, phases and definition of done. No prior chat, memory, unstated decision or another package enlarges v6.

Validate package integrity, setup-only scope, the exact seven-path carry manifest, v6 preflight evidence, protected sources, candidate entrance, v5 failed weekly evidence and accepted sync/single receipts. Resume at the earliest unproven postcondition. Do not rerun marker, doctor, sync dry/apply/repeat or accepted single user/system runs.

P1 may only apply the minimal truthful-partial aggregate validator fix and authorized tests plus the existing P7 carry. P2 must use a statically audited create-only recovery to continue weekly/monthly, API/browser and final validation. Preserve all failed evidence and old rows. Network is localhost-only with external count zero.

After each phase run its validators and protected-source checks, inspect scope, update START_HERE.md and create the named local Git checkpoint. Continue unattended until every completion criterion passes or a contract hard stop occurs. Never modify a frozen contract/predecessor, enlarge scope, weaken validation, fabricate facts/human decisions, infer motives, add dependencies/providers, write protected data or publish.
```

## Current checkpoint

- **State:** `blocked`
- **Last completed phase:** `none`
- **Next phase:** `P1`
- **Latest validation:** `failed` — the minimal aggregate fix and all P1 test gates pass, but a read-only real `weekly:user` probe exposed a second builder timestamp defect outside v6 authority; the first CLI dry-run also created one forbidden P1 cache triplet.
- **Current blocker:** The fixed model predicate now accepts truthful `partial+missing` snapshots and progressed beyond the v5 failing episode, but the next episode `te_279ea5cae3aab875f6fe2a14a92f91cf` fails with `TimestampError: known_at (2026-07-14T17:43:41Z) cannot be earlier than occurred_at (2026-07-17T06:00:00Z)`. Correcting the builder/time projection is outside O-002/O-003. Additionally, the initial CLI dry-run used its default adapter and created the cache-only triplet `v2/{locks,q,r}/ba8454da1eac0dd2f976.*` for `002572.SZ`; v6 forbids P1 cache writes and cache deletion, so these files are preserved rather than concealed.
- **Next safe action / precise unblock question:** Does the user authorize a v7 successor amendment that (1) adds only the proven checkpoint builder/time-projection implementation and targeted regression paths needed to correct this TimestampError, and (2) adopts the preserved three-file `ba8454da1eac0dd2f976` cache triplet as explicit v7 entrance state without deleting or rewriting it?

The Git commit containing this file is the checkpoint commit. Do not write that commit's own hash into this file.

## Checkpoint history

- 2026-07-27T16:18:45+08:00 — Drafted v6 after explicit user authorization. Source baseline is v5 hard-stop commit `bd842e2f...`. v6 only adds the core partial-aggregate model/test paths; objective/truth/data/network/publication boundaries remain unchanged. Preflight SHA-256=`d24fefb138cf7c1be7fca19f2251dec4976666768c6a49aaad9a970e2ca56872`; candidate SHA=`ffb7e377...bd5cd`; protected sources exact; seven carry paths exact; cache has 12 create-only entries; failed weekly and accepted sync/single evidence are preserved.
- 2026-07-27T16:43:13+08:00 — P1 model correction changed only the aggregate predicate to count `available` or `partial` as a truthful component. New v2 positive/negative regressions passed; V-101=`166 passed`, V-701=`127 passed`, V-702=`19 passed` plus Vite build, and V-703=`18 passed` (evidence SHA-256=`32c8929147c1068e0b04f0638a06e98e76650849b4adfe1c9ed2c61d0ad9ee45`). A real injected `weekly:user` dry probe then progressed past the v5 `te_232e...` aggregate failure and stopped at `te_279ea...` with the independent TimestampError above; diagnostic evidence SHA-256=`985d905d64534a58b336fab472089e4a4ea0e9c0f4b6dac7c496eb63995fa269`. External network calls remained zero. Candidate main/DDL/raw selected tables and all protected sources remain byte-exact with v6 entrance and quick_check=`ok`; candidate WAL/SHM are absent. The first CLI dry-run created only the three cache paths recorded above, with no existing cache path changed. P1 is not complete and P2 was not started.
