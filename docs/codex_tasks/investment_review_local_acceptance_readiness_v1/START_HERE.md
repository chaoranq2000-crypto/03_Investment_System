---
schema_version: "1"
task_id: "investment_review_local_acceptance_readiness_v1"
contract_path: "docs/codex_tasks/investment_review_local_acceptance_readiness_v1/CONTRACT.md"
contract_sha256: "0f7b37a382bbba0fa3faaace63621664aede2529842b52905ae7677f516c89ac"
state: "running"
execution_branch: "codex/investment-review-reviewability-corrections"
source_baseline: "07fe3a14dc5b4b770bad1dd1e30966672b74bce5"
last_completed_phase: "P1"
next_phase: "P2"
last_validation: "pass"
updated_at: "2026-07-27T15:24:34+00:00"
---
# 在新的 Codex 任务中启动或续跑本阶段

在专用执行 worktree `C:\Projects\03_Investment_System_investment_review_reviewability` 中打开新任务并原样粘贴：

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/investment_review_local_acceptance_readiness_v1
Frozen contract: docs/codex_tasks/investment_review_local_acceptance_readiness_v1/CONTRACT.md
Expected contract SHA-256: 0f7b37a382bbba0fa3faaace63621664aede2529842b52905ae7677f516c89ac
Execution worktree: C:\Projects\03_Investment_System_investment_review_reviewability
Execution branch: codex/investment-review-reviewability-corrections
Source baseline: 07fe3a14dc5b4b770bad1dd1e30966672b74bce5

Read the complete applicable AGENTS.md instruction chain, C:\Users\Q\.codex\skills\autonomous-stage-runner\SKILL.md, .agents/skills/investment-review/SKILL.md, CONTRACT.md, and START_HERE.md before acting. Treat the frozen contract as the objective, constraints, authority, phases, and definition of done. No prior conversation, memory, another task package, or unstated decision is authoritative.

Validate package integrity and repository preflight. Record entry SHA-256, size, immutable quick_check and WAL/SHM state for all four databases, plus tree manifests for the reviewed artifact root and v3 market cache. Resume from the earliest phase whose postconditions are not proven. After each phase, run its validators and protected-source checks, inspect scope, update START_HERE.md, and create the specified Git checkpoint. Continue unattended until every engineering-readiness completion criterion passes or a contract hard stop occurs.

Acceptance runtime is loopback-only, immutable/query-only, automation/provider/network off, review-read-only, and must reject portfolio/realtime/refresh and all review mutation routes. Never rerun marker/sync/doctor/review apply, modify the frozen contract, write any protected database/canonical candidate/cache/predecessor artifact, enlarge scope, weaken validation, fabricate external facts, user motives, actual observation or human acceptance, or publish. The endpoint is human_product_acceptance=pending and production_released=false.
```

## Current checkpoint

- **State:** `running`
- **Last completed phase:** `P1`
- **Next phase:** `P2`
- **Latest validation:** `pass`
- **Runtime authorizations:** bounded local engineering, loopback rehearsal, exact-owned process start/stop and audited per-file cleanup defined by the frozen contract; no external network, protected-data mutation, human acceptance or publication.
- **Current blocker:** none
- **Next safe action:** Execute P2 against the exact real candidate: start the owned localhost service, capture API/browser evidence, stop it, recheck protected state, run the full suite, and close the readiness report.

The Git commit containing this file is the checkpoint commit. Do not write that commit's own hash into this file.

## Checkpoint history

- 2026-07-27T23:01:17+08:00 — Package drafted from clean v7 compatibility checkpoint `07fe3a1...`. Live audit found the ordinary dashboard unsafe for strict acceptance because it initializes the formal DB, does not select the exact candidate/artifact root, starts automation by default, loads realtime/performance routes and exposes review mutation forms. This successor is therefore bounded to a dedicated immutable, loopback-only, review-read-only acceptance surface. Human acceptance and release remain pending/false.
- 2026-07-27T15:24:34+00:00 — state=running; completed=P1; next=P2; validation=pass; P1 complete: dedicated immutable/query-only acceptance mode, explicit candidate/artifact identity, server-side route and mutation isolation, frontend review-only branch, verified-PID start/stop scripts and playbook added. Backend targeted regression 87 passed; frontend 21 passed plus build; PowerShell parser and unknown-process refusal passed. Protected four-DB state, 760-file artifact manifest and 153-file cache manifest remain exact; no external network, dependency, protected write or publication.
