# P2C Handoff / Close Readout

## 1. Identity

- Repository: `chaoranq2000-crypto/03_Investment_System`
- Base branch: `codex/portfolio-tracker-p2b`
- Base SHA: `1d5084526e5b9d0905480e954b09c00c7343fd9a`
- Working branch: `codex/portfolio-tracker-p2c`
- Suggested final commit: `feat(portfolio): reconstruct auditable trade episodes`
- Authoritative final head/remote SHA and clean-worktree proof: reported by the post-commit handoff because a tracked file cannot contain its own final commit SHA.
- PR created: no.

## 2. Scope delivered

- `TradeEpisode` v1, collection v1 and machine validation v1 contracts;
- deterministic flat/open/add/reduce/close/re-entry builder;
- explicit data-gap and unsplit-reversal blockers;
- complete event consumption ledger;
- read-only P2B snapshot references with fallback/exact/missing methods;
- explicit-only Decision linkage;
- canonical JSON build, query and validate CLI;
- 36-case package matrix mapped to focused tests;
- baseline, quality, TODO and close evidence.

The implementation changes 4 runtime package files, 2 test/fixture files and contract/operating evidence files. The total file count exceeds the package's preferred implementation-only guardrail because Patch 00 and Patch 05 evidence are intentionally tracked separately; the runtime surface remains narrow.

## 3. Contract summary

- schema: `portfolio.trade_episode.v1`;
- collection: `portfolio.trade_episode.collection.v1`;
- identity: schema + explicit account/instrument/currency + opening event ID;
- partition: `(account, market, symbol, currency)` only;
- status: `open | closed | data_gap | ambiguous`;
- time: timezone-aware `occurred_at`, `known_at`, cutoff; later-known events are excluded visibly;
- lineage: event/source refs, input/snapshot/content digests, builder version and consumption ledger;
- Decision policy: `decision_event_links` only; `unlinked` is valid;
- compatibility: v2 review sidecar remains unchanged; output is a local versioned JSON projection.

## 4. Algorithm and edge cases

- canonical order: effective timestamp, source sequence, stable source/event identity;
- flat to non-zero opens; non-zero to flat closes; adds/reductions stay within one episode;
- re-entry after flat creates a new stable ID;
- one sign-reversal event is blocked rather than assigned to two episodes;
- opening balance, transfer, correction and company-action quantity effects remain typed and visible;
- exact duplicates are deduplicated; conflicting duplicates block;
- every input is consumed, classified, rejected, blocked or cutoff-excluded.

## 5. Focused and full verification

| Check | Result | Local artifact |
|---|---|---|
| P2C only | `21 passed` | `.codex_tmp/p2c_close/focused.xml` includes combined suite |
| P2A/P2B + P2C focused | `95 passed in 8.09s` | `.codex_tmp/p2c_close/focused.log` |
| deterministic rerun | same collection digest and byte-identical artifact SHA | `.codex_tmp/p2c_live/` |
| randomized input order | pass across 8 seeds | `test_shuffle_rerun_and_equal_timestamp_order_are_deterministic` |
| full baseline | `5 failed, 699 passed, 2 skipped` | P2B `.codex_tmp/p2c_baseline/` |
| full candidate | `5 failed, 720 passed, 2 skipped` | `.codex_tmp/p2c_close/full_suite.log` |
| new failures | `0` | `P2C_FULL_SUITE_DELTA.json` |

The same five Bundle 10R node IDs and stable hash signatures remain. P2C did not resolve or alter them.

## 6. Protected-scope proof

- Bundle 10R workflow-run files changed: `0`;
- Bundle 10R expected hash/canonical index files changed: `0`;
- Bundle 10R tests/scripts changed: `0`;
- unrelated R5/data manifest/workflow files changed: `0`.

## 7. Audit traces

### Closed episode

- episode: `te_27f2e3f8c6efe05101edf8f16a1a03c2`;
- ordered normalized events: `30`, each with source lineage and connected quantity path;
- snapshot links: explicit `missing` because the live P2B tables are not initialized;
- Decision link: `unlinked` because no explicit record exists;
- validation: `accepted_with_warnings` (`KNOWN_AT_FALLBACK`, `SNAPSHOT_LINK_MISSING`, `DECISION_LINK_UNAVAILABLE`).

### Open episode

- episode: `te_bf59e1f6bf87e09df9bfdec3390966d0`;
- ordered normalized events: `1`, consumed once;
- at-cutoff state: non-zero and status `open`;
- snapshot links: `before_open`, `after_open`, and `at_cutoff` all explicitly `missing`;
- Decision link: `unlinked`;
- validation: `accepted_with_warnings` with the same visible data gaps.

No symbol, account balance, price, quantity or raw private row is copied into this tracked readout.

## 8. Limitations and next gate

- Live P2B snapshot tables need a separately approved initialization/backfill operation.
- Historical `known_at` is an explicit fallback and cannot support strong decision-time claims.
- No live Decision link exists yet.

Next gate recommendation: **P2D explicit Decision and Information Event capture/linkage with durable `occurred_at` / `known_at`**. P2D was not started.

## 9. Final status

```text
P2C focused tests: pass (95)
Full-suite new failures: 0
Known Bundle 10R failures: same exact 5
Protected-path changes: 0
Live source DB writes: 0 (SHA-256 unchanged)
Close decision: accepted_with_todos
PR: not created
```
