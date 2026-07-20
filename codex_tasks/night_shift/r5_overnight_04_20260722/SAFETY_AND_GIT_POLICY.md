# Safety and Git Policy — Night04

## Git boundaries

- Exact source: `codex/r5-night03-targeted-backflow-intake` at `758ab7557d9de9eea42a5aeb5df95e3d68c26f0c`.
- Target: `codex/r5-night04-review-acceleration-and-unlock`.
- Isolated worktree: `C:\Projects\03_Investment_System_night04`.
- Seed commit may add only `codex_tasks/night_shift/r5_overnight_04_20260722/**`.
- Require at least 6 meaningful workstream commits after the seed.
- No PR, no merge to `main`, no force push, no cleanup of the user's main worktree.

## Immutable history

Read-only and zero-diff relative to the source commit:

- `reports/p1_6/r5_bundle17r/**`
- `reports/p1_6/r5_night_shift/r5_overnight_02_20260720/**`
- `reports/p1_6/r5_night_shift/r5_overnight_03_20260721/**`

## Human authority

Automation must never create reviewer identity, reviewer authority, `reviewed_at`, approval,
or an exact-hash human decision. It may generate blank decision forms and validate externally
supplied decisions. Candidate-ready is not resolved.

## Research truth

- Start at 0/63 resolved unless independent receipts prove otherwise at bootstrap.
- Only an accepted decision plus a successful resolution receipt can increase resolved.
- Parent completion and dependency unlocks are derived from atomic occurrence receipts.
- Do not auto-open sample quality, P2, canonical state, or Bundle18 human acceptance.
- Do not modify `data/raw/**` or promote user samples into evidence.
