# Investment Review Phase 1 Run Log

## 2026-07-15

1. Rediscovered `investment_review_phase1_patch_a12cbb8.zip` as the latest trading-review patch.
2. Verified archive SHA-256, all 23 internal checksums, base commit and 14 add-only target paths.
3. Preserved the dirty portfolio worktree and applied the package patch only after `git apply --check` passed.
4. Resolved the canonical portfolio database to the primary worktree and ran doctor through SQLite `mode=ro`.
5. Found the post-package schema mismatch and adapted `event_date + event_time`, `event_type`, `cash_amount`, account identity and representative preview handling without changing `src/portfolio`.
6. Preserved the generated mapping as a dry-run-only suggestion and created a separate reviewed mapping. Stable source identity is `account_id::external_id`; `dedupe_key` remains raw content evidence rather than identity.
7. Bound the reviewed mapping to reviewer metadata, schema manifest SHA-256, generated mapping SHA-256 and `review.mapping_content_sha256`. The content hash covers the complete reviewed document except that self-referential field.
8. Rejected rebuild `created_at` as historical `known_at`; all 961 imported events explicitly record fallback and `note-add` now requires `--known-at`.
9. Reran doctor: `ledger_entries`, score 5 / 5, 961 rows and no missing required mapping fields.
10. Confirmed generated mapping formal import is rejected. Ran reviewed-mapping dry-run with representative BUY / SELL / DIVIDEND / CASH_FEE rows and visible `cash_amount`.
11. Initialized the schema v2 sidecar with `application_id=0x49525657`; a wrong `--db` path is rejected before review schema or WAL creation.
12. Imported 961 events in `run_17f51358aee04c2388e204c7cf39d69d`, then reran idempotently in `run_343100a5b35e415bb2bbe3292fb122e4` with `inserted=0` and `skipped=961`.
13. Added the full reviewed-document content lock and reran in `run_e781fadf03714777a870cfdca1a73990`; it also produced `inserted=0` and `skipped=961`.
14. Bound formal SQLite import to the same source path, reviewed table and live `table_schema_sha256`; required stable CSV `source.identity_key` and a non-missing `record_id` for every mapping.
15. Refused automatic legacy v1 migration because it cannot reconstruct event-run lineage; the safe path is a new v2 sidecar plus read-only reimport.
16. Reran the fully bound reviewed mapping in `run_d4aeac0e8c82487ebc5fcac6d312deca`; it produced `inserted=0` and `skipped=961`.
17. Preserved all three source config fingerprints: `source_config_versions=3`; failed or changed attempts do not silently overwrite the active source configuration.
18. Verified `trade_events=961`, `ingest_runs=4`, `ingest_run_events=3844`, integrity, foreign keys, unique stable IDs, raw payload SHA-256, explicit first-run links, dual-time ordering and removed-snapshot detection.
19. Reconciled event counts and cash sums: BUY 489, SELL 404, DIVIDEND 39 / 6465.15, CASH_FEE 29 / 369.49.
20. Verified the portfolio source SHA-256, size and mtime remained unchanged across doctor, dry-run and all four formal runs.
21. Expanded the conda test suite to 14 tests and passed compileall, all 14 tests, `git diff --check`, and launcher `status`.
22. Updated the linked-worktree launcher to reuse the primary worktree conda environment and resolved the root `AGENTS.md` routing conflict by explicitly enabling the isolated investment-review utility.
23. Independent final review confirmed Gate 1 as `accepted_with_todos` with open critical/high = 0 and 16 resolved high issues. Gate 2–5 and P2 remain out of scope.

No file or directory was deleted. No `src/portfolio` user change was overwritten or reverted.
