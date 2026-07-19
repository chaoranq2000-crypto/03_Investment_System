# Safety Boundaries

## Branch and workspace

- Use only the isolated Night02 worktree and `codex/r5-night02-contract-recovery`.
- Treat worktree root and branch as separate typed values.
- Never modify a dirty `main` checkout.
- No PR, no merge to main, no force push.

## Research truth

- Start truth: 6 pending work orders; 0/63 resolved blockers.
- Classification and proposal generation do not change resolution counts.
- Historical Bundle17R and four Bundle16R generated artifacts are read-only.
- Do not rewrite expected assertions to make old artifacts pass.
- Do not convert `decision: pass` into `candidate_ready_for_exact_hash_review: true` without the new quality contract and its gates.
- Do not invent a `generation_id` for an old generation lock.

## Human and evidence authority

- Automated packets must keep reviewer, reviewed_at, decision and decision_notes empty.
- Evidence can be requested and routed, not automatically accepted.
- Analyst workbooks can organize questions, not supply human judgment as fact.
- A proposed path/command contract is not executable until an exact-hash approval is present.

## Files

Never track `.local/**`, `__pycache__`, `.pyc`, temporary BF2 runs or generated CI source-route reports unless the task explicitly names a stable report path. Enforce per-task diff scope.

## Completion language

- `delivered`: all Night02 delivery-required engineering work passed and was published.
- `partial`: useful work published but queue remains.
- `blocked`: external authority/evidence prevents delivery.
- `failed`: unresolved acceptance or safety failure.
- The long-term Goal remains open in every Night02 outcome.
