---
schema_version: "1"
task_id: "investment_review_product_completion_v3"
contract_path: "docs/codex_tasks/investment_review_product_completion_v3/CONTRACT.md"
contract_sha256: "1f566582eec30ec4d3efc9e0c2349912468642edae32ba79997bb76de6f35033"
state: "running"
execution_branch: "codex/investment-review-reviewability-corrections"
source_baseline: "c3e296661c04b9de35795e2311674b507846d19a"
last_completed_phase: "P3"
next_phase: "P4"
last_validation: "pass"
updated_at: "2026-07-26T13:28:31+08:00"
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

- **State:** `running`
- **Last completed phase:** `P3`
- **Next phase:** `P4`
- **Latest validation:** `pass` — exact V-301 completed with 130 passed in 34.72s and no skip/failure/error; the latest V-201 compatibility set completed with 103 passed in 26.20s. Independent knowledge-provenance and runner/receipt hostile audits found no remaining blocker. The exact O-010 v3 candidate initialized idempotently, first sync inserted 983 events, repeat sync inserted 0/skipped 983, and final status is healthy with `unsynced=0`. Real dry-run evidence at cutoff `2026-07-18T00:00:00Z` selected the seven-operation open 588200 episode under `user` and selected no episode under pre-observation `system`; both receipts validated. Frozen contract SHA-256 remains `1f566582eec30ec4d3efc9e0c2349912468642edae32ba79997bb76de6f35033`. Final P3 V-002 found all three protected sources byte-identical to preflight with `quick_check=ok` and unchanged WAL/SHM state; the isolated v3 candidate has `quick_check=ok`, SHA-256 `27dba0200826724a300ce90fc98f7bfd0e68b921c3979f8fbc95f155bf6abb7a`, and only its expected zero-byte WAL/existing SHM state.
- **Current blocker:** none
- **Next safe action:** After this P3 checkpoint commit, begin P4 ledger snapshot reconstruction from the fully reconciled v3 candidate. Keep the formal portfolio database read-only and degrade only fields whose lineage or baseline cannot be proven.

The Git commit containing this file is the checkpoint commit. Do not write that commit's own hash into this file.

## Checkpoint history

- 2026-07-26T13:28:31+08:00 — P3 completed. Added closed `investment_review.knowledge_provenance.v1` projection with separate effective, user-known, system-observed and recorded times; an explicit account-only owner-action allowlist; null/unknown plus owned gaps for missing or cutoff-withheld recorded evidence; complete-event manifest commitments; byte-deterministic source replay; and fail-closed validation for malformed JSON, time inversion, coordinated ledger/visibility drift and perspective downgrade. Runner and CLI now default to `user`, support explicit `system`, and bind perspective, knowledge content, episode details, source replay and run identity while preserving authentic legacy v1 receipts and canonical P2C/P2F bytes. After source/mapping identity reconciliation, only `data/db/investment_review_reviewability_v3.sqlite3` was initialized; sync dry/apply/repeat produced 983 initial inserts, then 0 inserts/983 skips and `unsynced=0`. At `as_of=2026-07-17T05:55:28Z`, `knowledge_cutoff=2026-07-18T00:00:00Z`, the real user dry run selected the open 588200 episode with seven operations and `operation_review_status=ready`, while the system dry run selected none before the immutable first-ingest observation; both receipts and source replay validated. Exact V-301: 130 passed in 34.72s; latest V-201 compatibility: 103 passed in 26.20s; independent hostile audits passed. Final V-002 preserved all three protected-source hashes and WAL/SHM states; the v3 candidate is healthy with `quick_check=ok`. No network was used. Next safe phase is P4.
- 2026-07-26T12:20:17+08:00 — P2 completed. Added the versioned `investment_review.operation_review.v1` classifier as a parallel artifact without changing P2C/P2E-3/P2F schemas or bytes. Position roles derive only from the canonical quantity chain and explicit event type/side; no-Decision closed/open episodes retain `operation_review_status=ready` with `decision_context_status=not_recorded`, while standalone cash uses `not_applicable`. Reversal, flat outflow, correction, corporate action, transfer, unknown event semantics and inconsistent provenance remain explicit ambiguous/blocked facts. The closed validator/replay gate now rejects invalid P2C digests/schema, binary floats, lone surrogates, invalid/extreme timestamps or decimals, open-ended scope/reason fields, impossible self-rehashed roles, broken episode/cash ordering, missing material lineage and malformed replay inputs. Runner run keys bind classifier schema/method; the existing `episode` stage carries the additive artifact and independent readiness while authentic legacy v1 receipts still validate/replay. Exact V-201: 93 passed in 17.29s; legacy P2E-3/P2F compatibility: 208 passed; final independent compatibility and adversarial audits found no blocker. Package validation remained 0 errors/0 warnings and the frozen contract hash was unchanged. Final P2 V-002 matched all three protected-source preflight sizes, SHA-256 values, `quick_check=ok` and WAL/SHM states; the real v3 candidate sidecar remains absent. Next safe phase is P3.
- 2026-07-26T11:23:22+08:00 — P1 completed. Added the opt-in reviewability skill/playbook boundary, closed `investment_review.operation_checkpoint.v1` schema, six independent status axes, field-specific four-time provenance, episode-rooted semantic keys, create-only checkpoint storage, row-integrity verification, and a full foundation DDL manifest. Froze the code-owned provider/endpoint/parameter/value allowlist and derived request fingerprint, including exact request caps, sensitive-value rejection, frozen cache lineage, market-time ordering, and offline consumers. Existing-candidate validation rejects nonempty WAL or structural drift while preserving the stable zero-WAL Windows read-only case; replay, status, and same-transaction saves fail closed on marker, manifest, payload, projection, inserted-time, gap, or row-integrity drift. V-101: 71 passed in 6.62s with no skip/failure/error; final independent audit found no blocker. Frozen contract/package hash remained unchanged. Final P1 V-002: formal portfolio DB, user sidecar and v2 candidate retained their preflight size/SHA-256, `quick_check=ok`, and unchanged WAL/SHM state; evidence is in `.codex_tmp/investment_review_product_completion_v3/protected_sources.json`. The real v3 candidate sidecar still does not exist. Next safe phase is P2.
- 2026-07-25T13:03:16+08:00 — Finalized package version 3 after explicit user approval. Frozen contract SHA-256 is `1f566582eec30ec4d3efc9e0c2349912468642edae32ba79997bb76de6f35033`; task state is `ready`; finalizer validation returned 0 errors and 0 warnings. The next safe action is P1 execution from the package-only setup checkpoint.
- 2026-07-25T12:57:24+08:00 — Workspace user confirmed the final v3 objective and acceptance criteria with `local_first_controlled_fallback_v1`: local cache first; only `missing`, `stale` or `insufficient` coverage may trigger a bounded existing allowlisted provider before bundle freeze; writes stay in the new v3 cache/sidecar; renderer, source replay, API and UI remain offline. Draft validation must be rerun before finalization.
- 2026-07-25T03:25:18+08:00 — Added explicit v3 source reconciliation and protected-file criteria, replaced abbreviated evidence paths with exact paths, and revalidated the draft with 0 errors and 0 warnings. Current draft hash is `e4243ca18586dcdc647c0c047f2eced0184e8fd0c46232dae470b5f819770f75`.
- 2026-07-25T03:23:26+08:00 — Draft package validation passed with 0 errors and 0 warnings. The draft hash is informational only and will change during finalization; the launch block remains `PENDING`.
- 2026-07-25T03:12:10+08:00 — v3 amendment drafted from source baseline `c3e296661c04b9de35795e2311674b507846d19a`. It defines seven reviewability corrections, a new isolated candidate sidecar, protected-source hashes, real 588200 acceptance, local-cache-only automatic market context, and a local-only publication boundary. It is not safe to execute until explicitly approved, finalized, validated, and committed as a package-only setup checkpoint.
