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
