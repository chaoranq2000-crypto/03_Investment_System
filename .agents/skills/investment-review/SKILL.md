---
name: investment-review
description: >-
  Evidence-first personal investment review workflow. Use for importing personal
  trade records, capturing decision notes, reconstructing trade episodes, and
  producing traceable reviews that separate facts, interpretations, alternative
  explanations, and uncertainty. Never route to order execution or direct advice.
---

# Investment Review

## Phase 1 operating boundary

The current implementation is a data-foundation skill. It may:

- inspect the existing portfolio SQLite database in read-only mode;
- normalize fills into a separate review database;
- preserve non-fill cash events with an explicit `cash_amount` field;
- preserve both `occurred_at` and `known_at`;
- capture decision notes and link them to execution events;
- report missing mappings, conflicts, and provenance.

It must not:

- modify the existing portfolio ledger;
- infer motives from a single trade;
- generate direct buy/sell/position instructions;
- collapse evidence into one mechanical score;
- use information whose `known_at` is later than the decision being reviewed.

## P2A portfolio-context boundary

After the Phase 1 evidence layer is accepted, the implementation may also:

- store reviewed `PositionSnapshot` and `PortfolioSnapshot` objects in the
  existing v2 sidecar snapshot tables;
- calculate deterministic single-snapshot cash, gross/net exposure,
  concentration, industry and label metrics;
- link a pre-reference snapshot and optional post-event snapshot to a Decision
  or externally identified Trade Episode;
- render a separate portfolio-analysis block with provenance, uncertainty and
  alternative explanations.

P2A must keep post-event observations outside facts available at the decision
time. It does not authorize full episode reconstruction, historical portfolio
replay, complex risk models, AI behavioral claims, UI changes or brokerage
writes. See `docs/playbooks/INVESTMENT_REVIEW_P2A.md` for formulas and commands.

## P2C trade-episode boundary

After the P2B point-in-time snapshot contract is accepted, the implementation
may also:

- build deterministic `TradeEpisode` v1 projections from the reviewed v2
  sidecar `trade_events`;
- consume P2B portfolio/position snapshot references through a read-only SQLite
  connection;
- preserve an event-consumption ledger, stable identities, canonical digests,
  explicit data-gap/ambiguity statuses and blocker/warning/info findings;
- link Decisions only through `decision_event_links` and retain `unlinked` when
  no explicit relation exists;
- write a versioned local JSON projection and query it without migrating the
  sidecar schema.

P2C must not write the portfolio database, infer Decision links, use snapshots
without point-in-time-safe knowledge cutoffs as historical decision facts, split
one reversal event across two episodes, or add P&L attribution, behavioral
interpretation, advice, UI or execution. See
`docs/playbooks/INVESTMENT_REVIEW_P2C.md`.

## Required workflow

1. Run `python -m src.investment_review --db data/db/investment_review.sqlite3 init`.
2. Run `doctor` against the portfolio database and preserve the generated manifest.
3. Preserve the generated mapping, create a separately reviewed mapping, and bind its
   reviewer, review time, canonical reviewed-content SHA-256, generated-mapping SHA-256
   and schema-manifest SHA-256.
4. Run `ingest-sqlite --dry-run`; inspect the per-event-type preview and counts.
5. Run the actual import. Repeated imports must be idempotent.
6. Capture missing decision context with `note-add`.
7. Only after the evidence layer is complete, proceed to episode reconstruction or analysis.

For an approved P2A context run:

8. Review a snapshot JSON document and verify `source.read_only=true`,
   `source_path`, `observed_at`, `known_at`, cash/NAV, positions and currencies.
9. Run `snapshot-add`; repeated identical snapshots must return `SKIPPED`, while
   same-ID content drift must fail.
10. Run `portfolio-context` with a Decision or Trade Episode reference. The
    before-snapshot `observed_at` and `known_at` must not exceed the reference
    time; any after-snapshot stays in `post_event_observation`.
11. Preserve metric definitions, data-quality flags, snapshot IDs, source IDs,
    source paths and payload SHA-256 in the output.

For an approved P2C episode run:

12. Build only from reviewed sidecar events whose `occurred_at` and `known_at`
    are no later than the explicit cutoff.
13. Read P2B snapshot references in SQLite read-only mode; use exact after links
    only when event inclusion is proven, otherwise retain `missing`.
14. Preserve every input in the consumption ledger as consumed, classified,
    rejected, blocked or cutoff-excluded; never drop it silently.
15. Rebuild after shuffled input and require identical episode/collection
    digests before promotion.

Generated SQLite mappings are dry-run only. A real import must use
`review.status=reviewed`, and any post-review mapping edit must invalidate
`review.mapping_content_sha256`. Its source path, selected table and live table-schema
SHA-256 must still match the reviewed provenance. CSV sources require a stable semantic
`source.identity_key`; a filename is not a source identity. The review database has its
own SQLite application ID; never use the portfolio database as `--db`. Legacy v1 stores
must be preserved and reimported into a new v2 sidecar, not silently upgraded. Each seen
event must link to its ingest run with an `INSERTED` or `SKIPPED` outcome.

## Output contract

Every review output must keep these sections distinct:

- facts and source references;
- interpretation;
- alternative explanations;
- uncertainty or missing evidence;
- realistic alternative actions considered at that time;
- links to related historical episodes.
