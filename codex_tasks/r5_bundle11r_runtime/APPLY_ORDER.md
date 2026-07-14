# Bundle 11R runtime implementation order

1. Run strict target audit on `codex/r5-bundle10r-reader-rebuild`.
2. Apply the runtime-foundation patch.
3. Run focused tests and compile checks.
4. Preview workflow/skill integration.
5. Apply the idempotent integration with backups.
6. Populate a real 002837 segment plan and evidence-status matrix; do not copy sample-report facts.
7. Run operating-driver, peer-eligibility and semantic gates.
8. Route issues to the owning stage until no high/critical research blocker remains.
9. Regenerate the Reader using the existing generic Writer only after inputs are qualified.
10. Bind human review to the exact new report hash; keep sample quality and P2 false unless separately approved.
