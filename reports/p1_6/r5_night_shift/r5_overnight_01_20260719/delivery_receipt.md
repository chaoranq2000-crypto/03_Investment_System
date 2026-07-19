# R5 Overnight Mission 01 Delivery Receipt

## Delivery identity

- Run ID: `r5_overnight_01_20260719`
- Mission package: `R5_Overnight_Mission_01_20260718.zip`
- Package SHA-256: `D19AB2C9BCB811C63523B057F0E503BE448E81568D0098917FEF2D6E6918CD8`
- Immutable source branch: `codex/r5-bundle17r-bf2-execution-receipts`
- Immutable source SHA: `36a801efc2bf0af10ad9702b8c6266ebf1935d6f`
- Target branch: `codex/r5-night01-autonomous-harness`

## Published checkpoint

| Layer | Commit SHA | Remote state |
|---|---|---|
| Runtime, queue, lock, recovery and tests | `3234370782ca8295af8eba746fd597eea9a515e3` | ancestor of target branch |
| Mission contracts, BF2 seed and evidence | `90172520bb437014240443a34505bc38a7a69c06` | local and `origin/codex/r5-night01-autonomous-harness` byte-identical at the T90 checkpoint |

The final report-layer commit is intentionally identified by the target branch HEAD after this
receipt is committed; its exact local/remote parity is verified after the final push. This avoids
placing a self-referential commit SHA inside the commit it identifies.

## Acceptance evidence

| Gate | Result | Evidence |
|---|---|---|
| BF2 specialised tests | `9 passed` | `.local/night_shift/receipts/full_regression.json`; stable receipt `14ab9fd25bebc3cd20f1312cffd571b6f1eaa17f97614c87dc3fe36340e2b6b0` |
| BF2 EX1 tests | `12 passed` | same full-regression receipt |
| Source-route quality | `pass`; 17 capabilities; 0 blocking | `reports/p1_6/r5_night_shift/r5_overnight_01_20260719/validation.md` |
| Night-shift tests | `26 passed` | same full-regression receipt |
| Full repository suite | `959 passed, 2 skipped` | same full-regression receipt |
| Seed A/B determinism | 3 comparisons equal | `.local/night_shift/receipts/determinism.json`; stable receipt `3ff40edaa2e4fd2d011e85327085de8b96949a34da213c2695210f6ab09479db` |
| Readout A/B determinism | readout, JSON and next queue equal | `.local/night_shift/receipts/readout_determinism.json`; stable receipt `c16e2f5a95abf314fadfaa8ef1db0ef40ce2cb15783cad735566ea5b9fc324f5` |
| T90 trusted delivery chain | passed; full suite `959 passed, 2 skipped`; local/remote checkpoint equal | `.local/night_shift/receipts/ns01_t90_commit_push.json`; stable receipt `0e21f4ce39aa54c7e0c70b9c2c939959623cb7535bb9064e3cbf73f5d5aa2b6b` |
| Scope guard | pass; 0 forbidden; 0 tracked `.local`; 0 tracked BF2 outputs | `.local/night_shift/scope_audit.json`; audit SHA-256 `ec990a9579848d788dd7be54b76760275b6f5d2342d9e16a29f02ff0ff1f202c` |

## Research truth preserved

- 6 work orders remain pending.
- 63 blocker occurrences remain unresolved; resolved count is 0.
- Failed, orphan and rejected counts are all 0.
- The deterministic seed contains 69 tasks: 63 occurrence tasks and 6 parent work orders.
- The 8 engineering-local occurrences do not contain both explicit allowed paths and executable
  acceptance commands, so the mission recorded `no_safe_pilot` instead of guessing authority.
- Evidence, analysis, human and dependency gates remain explicit; canonical state, sample quality
  and P2 were not changed.

Sources: `.local/night_shift/bf2_inventory.json`, `.local/night_shift/bf2_seed_receipt.json`,
`.local/night_shift/receipts/no_safe_pilot.json`, and
`reports/p1_6/r5_night_shift/r5_overnight_01_20260719/no_safe_pilot_backflow.md`.

## Publication boundaries

- No PR was created.
- `main` was not merged or modified by this mission.
- No force push was used.
- `.local/**`, BF2 run outputs and `reports/quality/ci_source_route_quality_report.yaml` were not
  added to the delivery commits.
- Remaining owner: human reviewer. Next step: provide exact allowed paths and executable
  acceptance commands for the 8 engineering-local occurrences before any later pilot claim.
