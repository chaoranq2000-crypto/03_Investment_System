# R5 Overnight Mission 05

This execution package was materialized from the Night04 Night05 seed plan.
The source seed explicitly said that it was not yet a runnable patch package,
so this package implements only the safe, currently executable path:
exact-source bootstrap, external-decision intake, zero-input recompute, quality
gates, isolated-branch publication, and a truthful review_intake_ready close.

The package must not create reviewer identity, reviewer authority, reviewed_at,
or decision values. A candidate, review packet, approval, or dry run is not a
research resolution. Resolution still requires a valid external exact-hash
decision and an independent passed execution receipt.

## Locked source

- Night04 source commit: d0fc0fb735f0f581619e330b3fa6f1ef1914a276
- Night04 source branch: codex/r5-night04-review-acceleration-and-unlock
- Night04 exact-head CI: 29764207418, success
- Night04 carry-forward queue: 69 items
- Candidate-ready items: 43
- Research resolution at start: 0 / 63

The post-push Night04 receipt is snapshotted at
inputs/night04_remote_delivery_receipt.json. The runtime validates its stable
receipt, source commit, branch, CI head, and CI conclusion.

## Current valid outcome

No external authority registry or decision manifests were supplied. The valid
Night05 close is review_intake_ready. All 69 unresolved IDs and their source
hashes must remain unchanged, the program goal remains
open_needs_targeted_backflow, and sample quality / P2 remain false.

## Run order

1. Run the Night05 module in bootstrap mode.
2. Run the explicit Night Shift test list through Conda.
3. Run the source-route gate and the full pytest suite through Conda.
4. Record regression, scope, and CI-contract receipts.
5. Commit and push only codex/r5-night05-external-review-intake.
6. Wait for exact-head CI and write the post-push receipt outside the commit.

Do not create a PR, merge main, or force-push without a separate user
instruction.
