# Night05 execution plan

## N5-00 isolated bootstrap

Resolve the final Night04 source from the snapshotted remote delivery receipt.
Verify the exact source commit, successful CI, 228 tracked Night04 artifacts,
the 69-item queue, candidate hashes, review packet hashes, review waves, and
lineage. Historical Night04 and earlier outputs are read-only.

## N5-01 external decision intake

Read only externally supplied authority and decision files. Validate schema,
candidate hash, review packet hash, reviewer-authority binding, time,
conflicts, and replay. Automation must not populate human fields.

If no valid external decisions exist, close this phase as
closed_review_intake_ready and continue to the zero-input close.

## N5-02 to N5-04 review waves

- Wave A: seven highest-leverage candidates.
- Wave B: six remaining candidates for the first copper parent.
- Wave C: the remaining thirty candidates.

These phases remain blocked_external until real reviewers provide valid
decisions. Membership coverage does not unlock a dependency.

## N5-05 recompute and close

Without independent passed receipts, preserve all starting states:

- 0 / 63 blocker occurrences resolved
- 0 / 20 dependencies unlocked
- 0 / 6 parents resolved
- 69 unresolved queue entries carried forward

Generate a change log, blocker ledger, mission state, validation receipts,
tracked delivery receipt, morning readout, and post-push remote receipt. The
engineering outcome is review_intake_ready; the research program remains open.

