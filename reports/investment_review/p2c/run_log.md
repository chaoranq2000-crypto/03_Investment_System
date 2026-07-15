# P2C run log

## 2026-07-15 Patch 00

- Rediscovered `portfolio_tracker_p2c_patch_package.zip` as the newest matching root archive.
- Package SHA-256: `230fb8035a62c79bedc603a6e077b4ee6b21fef27be016aac0ddff74e76263d2`.
- Preserved the dirty `codex/portfolio-tracker` worktree and used the clean P2B worktree at the declared base.
- Verified local and remote `codex/portfolio-tracker-p2b` at `1d5084526e5b9d0905480e954b09c00c7343fd9a`.
- Focused inherited baseline: `74 passed in 7.86s`.
- Full-suite inherited baseline: `5 failed, 699 passed, 2 skipped in 33.08s`.
- Recorded the exact five Bundle 10R node IDs and signatures in `P2C_BASELINE_MANIFEST.yaml`.
- Froze the P2C allowlist and Bundle 10R/canonical research denylist.
- Created `codex/portfolio-tracker-p2c` from the exact P2B SHA only after Patch 00 gates passed.

## 2026-07-15 Patches 01-04

- Added versioned `TradeEpisode`, collection and validation contracts without changing the v2 sidecar schema.
- Added deterministic episode construction, explicit ambiguity/data-gap handling, snapshot linkage, Decision linkage and complete consumption coverage.
- Added build/query/validate CLI commands and a read-only P2B snapshot adapter.
- Added a 36-case fixture manifest and focused contract, property, storage, CLI and tamper tests.
- P2C-only result: `21 passed`; inherited plus P2C focused result: `95 passed`.

## 2026-07-15 Patch 05

- Live read-only build consumed 961 event identities into 286 episodes with zero rejected, blocked, unassigned or duplicate-consumed events.
- Live P2B tables were absent; the adapter stopped rather than fabricating snapshot links. A degraded build preserved all links as `missing`.
- Repeated live builds produced collection digest `70a24f755943a5299c6e3776a1e601cc16ddcf733a4b4092722f2bc4800b24d9` and byte-identical artifact SHA-256 `29960ceaf8a0e0b9957b705dbc9a57a917038cc424cf328ac6850be6af9f994e`.
- Review and portfolio SQLite SHA-256 values were unchanged before/after the run.
- Candidate full suite: `5 failed, 720 passed, 2 skipped`; exact inherited five failures unchanged; new failures `0`.
- Protected Bundle 10R and canonical research path changes: `0`.
