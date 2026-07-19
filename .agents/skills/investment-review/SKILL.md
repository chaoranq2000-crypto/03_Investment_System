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
- preserve canonical `decision_links` evidence (event, relation, effective and
  knowledge times, identity, status and registry source) alongside the
  backward-compatible Decision ID projection;
- write a versioned local JSON projection and query it without migrating the
  sidecar schema.

P2C must not write the portfolio database, infer Decision links, use snapshots
without point-in-time-safe knowledge cutoffs as historical decision facts, split
one reversal event across two episodes, or add P&L attribution, behavioral
interpretation, advice, UI or execution. See
`docs/playbooks/INVESTMENT_REVIEW_P2C.md`.

## P2E-3 episode portfolio-context boundary

After P2C and the P2E-2 metric registry are accepted, the implementation may also:

- bind every material Trade Episode event to deterministic `pre` and `post` anchors;
- read P2B snapshot tables through SQLite `mode=ro` plus `query_only`;
- reuse the versioned P2E-2 metric registry and preserve Decimal strings,
  method versions, source references and warning codes;
- calculate compatible pre/post metric deltas;
- save, validate and query a canonical
  `p2e3.trade_episode_portfolio_context.v1` local artifact atomically.
- bind the visible material-event set, snapshot state, cursor scope and metric
  availability ceiling into the artifact, then source-replay it before P2F use.

P2E-3 must not treat a stable ID tie-break as proof of business order, use a
future price/classification/revision, replace missing values with zero, copy
P2E-2 formulas, modify either source database, or emit behavior diagnoses,
scores, narratives or advice. Same-time events or snapshots without an explicit
business sequence/revision must remain `ambiguous`. See
`docs/playbooks/INVESTMENT_REVIEW_P2E_3.md`.

## P2F-1/P2F-4 frozen-input, interpretation and revision boundary

After P2C and P2E-3 pass source replay, the implementation may also:

- freeze one episode, its P2E-3 slice, explicit Decisions and cutoff-safe
  supplemental sources into a canonical `p2f.review_input_bundle.v1`;
- build a deterministic `p2f.episode_review.v1` facts-only revision from that
  bundle without querying any database, network service or model;
- preserve six fact sections, stable fact IDs, dual-time roles, availability,
  explicit gaps and exact five-field references to the frozen source inventory;
- compare only explicitly structured plan fields with linked execution facts,
  using neutral `matches`/`deviates` results;
- render facts-only JSON/Markdown and source-replay the review against the exact
  input bundle before downstream use.
- explicitly inject a model provider or recorded provider response to draft
  bounded interpretations over fact IDs only;
- preserve assumptions, uncertainty, alternative explanations,
  counterevidence status/refs, temporal perspective, prompt/model/input/output
  hashes and a separate interpretation-attempt receipt;
- return the exact facts-only artifact when the provider is unavailable or its
  output fails schema, temporal or policy validation.
- apply a closed human accept/reject/correct request only to existing finding
  or option IDs, then revalidate the complete artifact;
- create a new human-authored revision with one appended review event, a
  sequential revision number and an exact supersedes content ID;
- keep the prior artifact and all source databases unchanged, derive
  `superseded` only when listing a validated chain, and refuse output overwrite;
- render validated JSON as escaped Markdown and expose deterministic diff and
  revision-list commands without reopening any source database.

P2F facts must not promote free source text into objective claims, infer missing
investment logic, backfill outcomes as entry reasons, diagnose psychology,
score decisions, or emit buy/sell/hold guidance. Missing, ambiguous, stale,
partial and unpriced states remain explicit.

The current P2C snapshot cursor is partition-scoped. Unless a catalog record
explicitly proves a complete account-wide cursor, same-business-day P2E-3
metrics must be `partial` with `PORTFOLIO_CURSOR_SCOPE_LIMITED`; they must not
be promoted to `exact`, and partial endpoints must not publish numeric deltas.
Incomplete valuation coverage must leave NAV-dependent context metrics absent,
not derive NAV from only the priced subset.

## P2G-1 deterministic cross-episode fact-cohort boundary

After canonical P2F review inputs and review revision chains are accepted, the
implementation may also:

- select one unique P2F current leaf per logical review chain under an explicit
  effective window and knowledge cutoff;
- freeze the selected leaf's complete P2F `facts_only_projection`, section refs,
  source refs and cutoff-visible revision lineage into
  `p2g.behavior_cohort.v1`;
- preserve missing, partial, ambiguous, stale and unpriced states, warnings,
  gaps and exact source references without converting them to defaults;
- save, validate, query and source-replay the cohort through create-only local
  JSON artifacts.

P2G-1 must not consume interpretation text, infer psychology or motives,
calculate cross-episode behavior signals, query a database/network/model,
silently resolve multiple revision leaves, or use cutoff-later revisions.  A
P2F finding-level `reject` does not reject the immutable facts projection; an
artifact-level rejection would require a separate explicit contract.  See
`docs/playbooks/INVESTMENT_REVIEW_P2G_1.md`.

## P2G-2/P2G-3 observation and candidate-hypothesis boundary

After a P2G-1 cohort is accepted, the implementation may also:

- build the deterministic `p2g.behavior_observation_set.v1` evaluation ledger;
- consume one valid, ready and verified P2G-2 artifact plus one explicitly
  recorded local JSON response;
- compile only `proposed` candidate hypotheses with closed `evaluation_id`
  references, alternatives, assumptions, uncertainty and falsification conditions;
- preserve an independent attempt receipt and exact P2G-2 copy-through on failure;
- validate the candidate internally and replay its exact P2G-2 evaluation bindings.

P2G-3 must not call a live provider, read a database or network, infer a motive
from one episode, diagnose psychology or personality, emit a numeric confidence
or behavior score, produce trade/position advice, use outcome hindsight, or enter
P2G-4 accept/reject/correct/revision. See
`docs/playbooks/INVESTMENT_REVIEW_P2G_3.md`.

## P2G-4 review and behavior-hypothesis-ledger boundary

After a P2G-3 candidate set and its exact P2G-2 source replay are accepted, the
implementation may also:

- apply one closed, content-derived human review request atomically as a new
  `p2g.behavior_hypothesis_revision.v1` artifact;
- accept or reject only `proposed` candidates, or correct a proposed/accepted/
  rejected candidate by superseding it and creating a new `proposed` identity;
- validate and source-replay every revision, render escaped Markdown, compare
  revisions and list one complete non-forking chain;
- build one deterministic, artifact-only behavior hypothesis ledger from explicit
  complete revision chains and their exact P2G-2 observation artifacts;
- expose only accepted occurrences in the active ledger view while preserving
  proposed, rejected and superseded occurrences in the audit view.

P2G-4 and the ledger must not overwrite prior artifacts, infer new explanations,
use a live model, database, network or current time, perform semantic merging,
ranking, scoring or profiling, or emit trade/position advice. `accepted` means a
human-confirmed working hypothesis, not a proven fact. The ledger is a functional
artifact after P2G-4, not a new canonical stage number. See
`docs/playbooks/INVESTMENT_REVIEW_P2G_4.md` and
`docs/playbooks/INVESTMENT_REVIEW_BEHAVIOR_HYPOTHESIS_LEDGER.md`.

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

For an approved P2E-3 context run:

16. Validate the P2C source artifact and require explicit timezone-aware
    `as_of` and `knowledge_cutoff` values.
17. Build each material event's `pre`/`post` context only from source rows whose
    effective and knowledge times satisfy the anchor boundary.
18. Preserve `missing`, `ambiguous`, `stale`, `unpriced` and `invalid` states;
    compute deltas only when method version and unit are compatible.
19. Rebuild after input/SQLite insertion reordering and require the same bytes
    and `content_id`; verify the source database hash is unchanged.
20. Treat offline validation as internal-consistency checking only. Before any
    downstream P2F use, run source-aware replay with the identified P2C artifact
    and read-only P2B database and require `source_verification.status=verified`.

For an approved P2F facts-only run:

21. Build a release-ready P2F-1 bundle and preserve its exact `content_id` and
    source inventory; do not reopen the databases during the facts step.
22. Build the six-section facts-only review, then validate fixed templates,
    dual-time roles, fact/source IDs, explicit gaps and no-advice/no-score flags.
23. Source-replay the review from the exact input bundle and require a byte-for-byte
    rebuild before interpretations or publication.
24. Build the fixed P2F-3 prompt from the validated facts projection only; do not
    include raw Decision/note/source payload text or query a database/network source.
25. Validate every proposed finding/counterfactual against known fact IDs, temporal
    roles, alternative-explanation, counterevidence and no-advice/no-score gates.
26. Save the interpretation attempt receipt separately. On provider/output failure,
    require the result review content ID and bytes to remain the facts-only artifact.
27. Validate a `p2f.human_review_request.v1`; accept/reject findings only, and
    restrict corrections to explicit fact-link replacement on a finding or option.
28. Recompute affected interpretation IDs, append one content-derived human review
    event, set `generation_mode=human_authored`, and bind the new revision to the
    immediately prior content ID without changing the immutable fact layer.
29. Validate the whole revision chain: sequential numbers, no cycles, exact event
    prefix growth, unchanged input/facts/warnings and no undeclared interpretation edits.
30. Save the new JSON at a non-existing path, render escaped Markdown, and verify
    diff/revision-list output. Never pass or write a source database in this step.

For an approved P2G-1 cohort run:

31. Supply every cutoff-visible predecessor revision and each review's exact P2F
    input bundle; never resolve a chain from only a leaf path or `latest` alias.
32. Normalize the explicit effective window, knowledge cutoff and account/instrument
    filters, then require one validated current leaf per logical review chain.
33. Project the selected leaf through the canonical P2F facts-only projection and
    preserve all facts, states, gaps, warnings and source refs byte-deterministically.
34. Require the selected review's P2F source replay plus input-bundle
    `release_readiness=ready` and `source_verification=verified` before cohort release.
35. Rebuild after input permutation and after adding cutoff-later corrections; require
    identical bytes/content ID for the same cutoff-visible logical inputs.
36. Save create-only, query without derivation, and replay from explicit P2F sources;
    blocked/not-ready/unverified states must return a non-zero CLI exit code.

For an approved P2G-2/P2G-3 run:

37. Build and validate P2G-2 only from one ready/verified P2G-1 cohort, preserving
    every observed, not-observed, insufficient, incomparable and inapplicable state.
38. Supply the exact ready/verified P2G-2 artifact and one strict recorded JSON
    response; do not call a provider or reopen any source database.
39. Require support refs to resolve to `observed` evaluations, counterevidence to
    resolve or have an explicit search note, and scope episodes to match the refs.
40. Generate content-derived IDs, save the artifact and attempt as a create-only
    pair, and source-replay every frozen evaluation projection.
41. On unavailable, invalid or unsafe responses, preserve the P2G-2 object exactly
    and emit only the attempt receipt; do not publish partial hypotheses or enter P2G-4.

For an approved P2G-4 and behavior-hypothesis-ledger run:

42. Supply the current P2G-3/P2G-4 artifact, one canonical review request with an
    exact expected parent, and the exact ready/verified P2G-2 observation artifact.
43. Preflight every action, then apply the request all-or-nothing; corrections must
    rerun P2G-3 scope/ref and safety gates and return the new item to `proposed`.
44. Save create-only, source-replay each revision, and validate the complete chain
    before rendering, diffing or listing it; reject missing predecessors or forks.
45. Build a ledger only from explicit complete chains and all referenced P2G-2
    artifacts; exact canonical fingerprints may deduplicate payloads but never lineage.
46. Rebuild the ledger after input permutation, require identical canonical bytes and
    content ID, and keep active/audit status semantics explicit in every query/readout.

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
