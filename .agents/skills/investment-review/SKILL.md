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

## Product-completion system-integration boundary

The product-completion stage is a separately authorized local systems-integration
overlay. It is not a new canonical P2 stage and is specifically **not P2H Stage 2
Slice B**. It does not weaken any Phase 1, P2A, P2C, P2E-3, P2F, P2G or P2H
boundary below. Its permissions are released only by its own verified phase gates:

- P1 may refresh mapping provenance through SQLite `mode=ro`, preserve the
  separately reviewed mapping, and add only the fee-state, append-only correction
  and run-metadata contracts to a new candidate sidecar schema. P1 must not run a
  real sidecar sync or add runner, Web/API/UI or automatic-execution behavior.
- P2 may add idempotent, full-table read-only source sync, sync-health CLI and the
  fee projection/correction workflow after the P1 checkpoint and strict mapping
  validator pass. A review failure must not roll back a committed portfolio import.
- P3 may add a stable single/weekly/monthly facts-only runner after P2 reconciliation
  proves `unsynced=0`; it must preserve canonical P2E-3/P2F source-replay gates.
- P4 may add the local review API and UI after the runner service contract is stable.
  Those surfaces may expose only validated review objects and append-only human
  inputs in the candidate review sidecar; they do not authorize a P2H UI path.
- P5 may add disableable in-process catch-up and periodic automatic runs after P4
  validation. It must use idempotent run keys, expose lag/failure health, and must
  not install an OS scheduler or service.

For BUY/SELL fee presentation, exactly one state must remain visible:

- `actual`: a source fee is explicitly present and greater than zero;
- `estimated`: `historical_median_rate_v1` produced a value from an eligible,
  traceable sample set and records method version and sample count;
- `unknown`: the source fee is not actual and the estimation gate cannot be proven.

Zero or missing source fees must never be relabeled as actual. A human correction
must append a new immutable correction record with provenance and supersession
lineage; it must not update the source event, source fee or prior correction. A
current projection may be derived only from a validated, non-forking correction
chain.

The portfolio SQLite database remains read-only throughout product completion.
All new state belongs in the explicitly selected candidate review sidecar; a legacy
or user sidecar must not be silently upgraded or modified. Effective/knowledge-time
cutoffs still apply to every snapshot, event and revision. Future-known data must
not enter historical context, and `unknown`, `missing`, `partial`, `ambiguous`,
`stale`, `unpriced`, `blocked` and `failed` states must remain visible rather than
being converted to zero, success or canonical readiness.

If no model is configured, unavailable, or rejected by validation, the product must
return the exact validated facts-only artifact and an explicit attempt/failure state.
It must not synthesize missing interpretations, human decisions or readiness.

Product completion must not create or update a profile or PersonalPlaybook, create
an intervention/experiment or attempt/outcome, diagnose psychology/personality,
score behavior, emit numeric confidence, produce trade or position advice, execute
orders, write to a broker, use broker credentials, or write the portfolio source
database. Its API/UI/automation authority applies only to the product-completion
review workflow described in
`docs/playbooks/INVESTMENT_REVIEW_PRODUCT_COMPLETION.md`.

## Product-completion v3 reviewability boundary

The reviewability-corrections overlay is additive and explicitly opt-in. It uses
`reviewability_schema_version=1` and
`investment_review.operation_checkpoint.v1` only in a newly selected candidate
sidecar. Core initialization and the v2 product-completion feature must not create
or repair this overlay. A legacy, user, current-v2 or prior candidate sidecar without
the exact marker and complete schema is read-only evidence and must be refused before
opening any writable SQLite connection.

A new candidate path must be owned through `O_CREAT | O_EXCL`; the exclusive file
descriptor stays open while `fstat/stat + samestat` proves that every initialization
step still targets the same file. An existing path passes only through an immutable
`mode=ro` gate before any possible writable use. That immutable gate rejects a
nonempty `-wal` or an unpaired `-shm`. It may accept the stable zero-byte WAL plus
paired SHM left by ordinary read-only status on Windows, but snapshots and rechecks
each auxiliary file's identity, size, nanosecond mtime and SHA-256; any auxiliary
state/content change or nonempty WAL rejects the candidate. It separately snapshots
the main file's identity, size, nanosecond mtime and SHA-256 before opening it, then
requires the same main-file identity, size, mtime and hash before accepting it.
Because immutable SQLite may report
`journal_mode=delete`, the persistent main-file header must independently prove WAL.
The candidate must keep
`journal_mode=WAL`, return exactly `ok` from `PRAGMA quick_check`, and match the full
core + product-completion + reviewability foundation manifest. That manifest covers
every non-internal table/index/trigger/view plus `table_xinfo`, foreign keys,
`index_list` and `index_xinfo`, including implicit indexes, and has the fixed SHA-256
`e1241c55fe615a0389b9f7ee2c8d0e7071d7c45487800d67b00d29f53dcceab0`.
Every save revalidates the marker, WAL/quick-check result and full manifest inside the
same `BEGIN IMMEDIATE` writable transaction; an earlier read-only check is not enough.

The overlay is released only through its seven verified gates:

- P1 may define this boundary, the closed checkpoint contract and the empty additive
  schema. It must not sync real data, run reviews, reconstruct snapshots, acquire
  market data, automate work or expose API/UI behavior.
- P2 may classify account operations from quantity-before/quantity-after and explicit
  event facts. A missing Decision or reason projects `not_recorded` or
  `not_applicable`; it never blocks an otherwise provable operation review.
- P3 may project effective, user-known, system-observed and recorded/ingested times
  with explicit bases and bind a `user` or `system` perspective into run identity and
  replay. It must preserve existing event identities and reviewed mapping semantics.
- P4 may reconstruct pre/post/cutoff holdings from a completely synchronized,
  read-only ledger. Quantity, cost, cash, price, NAV, weight and industry availability
  are independent; a missing component must not hide an available position or become
  zero.
- P5 may append episode-scoped entry, adjustment, active, exit and postmortem
  checkpoints. `open` plus `outcome=interim` is a normal active-checkpoint
  state, not a gap and not a reason to downgrade operation readiness.
- P6 may freeze market context under `local_first_controlled_fallback_v1`. It checks
  local coverage first. Only `missing`, `stale` or `insufficient` coverage may invoke
  an existing allowlisted provider in the pre-bundle cache step, with timeout <=20s,
  retries <=2, concurrency <=2 and requests/run <=20. The result and a redacted receipt
  are written only to the new v3 cache/sidecar. Renderer, source replay, API and UI are
  always offline.
- P7 may expose the six validated axes and append-only human inputs through the local
  service/UI and disableable in-process automation. It does not authorize production
  publication, an OS scheduler/service or any P2H UI path.

The P6 allowlist is code-owned and closed. Every checkpoint must carry
`allowlist_version=market_provider_allowlist.v1`,
`allowlist_sha256=sha256:1e612c7bf6090fcbfd32aaaef9ca7c73db8441ba939726b9d610238b29b3790a`
and exactly these ten `provider:endpoint` values:

- `baostock:history_k_data_plus_5m`;
- `tushare:adj_factor`;
- `tushare:cb_daily`;
- `tushare:daily`;
- `tushare:etf_basic`;
- `tushare:etf_mins`;
- `tushare:fund_adj`;
- `tushare:fund_daily`;
- `tushare:stk_mins`;
- `tushare:stock_basic`.

Receipt parameter keys are endpoint-specific and closed:

- `baostock:history_k_data_plus_5m`: `code`, `fields`, `start_date`,
  `end_date`, `frequency`, `adjustflag`;
- `tushare:adj_factor`, `tushare:cb_daily`, `tushare:daily`,
  `tushare:fund_adj`, `tushare:fund_daily`: `ts_code`, `trade_date`,
  `start_date`, `end_date`, `fields`;
- `tushare:etf_basic`: `ts_code`, `fields`;
- `tushare:etf_mins`, `tushare:stk_mins`: `ts_code`, `freq`,
  `start_date`, `end_date`, `fields`;
- `tushare:stock_basic`: `exchange`, `list_status`, `fields`.

Parameter values are also closed strings. They are trimmed, limited to 512
characters, and only `exchange` may be empty:

- `code`: lowercase `sh|sz|bj`, a dot and six digits;
- `ts_code`: six digits and uppercase `.SH|.SZ|.BJ`;
- `start_date`/`end_date`: `YYYYMMDD`, or `YYYY-MM-DD` optionally followed by
  ` HH:MM:SS`; `trade_date`: `YYYYMMDD` or `YYYY-MM-DD`;
- `fields`: one or more comma-separated ASCII identifiers;
- `exchange`: empty or exactly `SSE|SZSE|BSE`; `list_status`: exactly `L|D|P`;
- the baostock 5-minute endpoint requires exactly `frequency="5"` and
  `adjustflag="3"`; Tushare minute endpoints require exactly `freq="1min"`.

All non-listed keys and out-of-grammar values are rejected. The sensitive token,
secret, password, API-key, credential, authorization/auth, header, cookie, session,
bearer, proxy, access/private-key and signature pattern is applied case-insensitively
to values as well as keys, so a safe key cannot persist secret-looking content. Each
receipt carries
`request_fingerprint_version=market_request_fingerprint.v1`; its fingerprint is
derived, not trusted from the caller, from that version, provider, endpoint, provider
version and the key-sorted safe parameter projection.

The limits are exact, not defaults that a caller may raise:
`timeout_seconds=20`, `max_retries=2`, `max_concurrency=2` and
`max_requests_per_run=20`. `request_count` is the sum of every embedded receipt's
`attempt_count`. A successful fallback requires at least one successful receipt,
non-empty cache references, response hashes, fetched time, cache-entry references
and cache lineage; the aggregate cache references cover every successful receipt's
cache entry. Success may fully satisfy coverage or honestly remain missing, stale or
insufficient. When local coverage is `satisfied`, the fallback is `not_needed`,
the request count is zero, frozen local `cache_refs` are non-empty and no external
fetch receipt may be present. Every embedded receipt, including failed, rejected,
timeout and zero-attempt provider-unavailable receipts, must have non-empty
`cache_lineage` binding the local cache requirement that triggered it.

Fallback status is exactly one of `not_needed`, `succeeded`, `failed` or
`provider_unavailable`; `attempted` and `not_attempted` are not states. Post-fallback
coverage and the market axis are coupled exactly:
`satisfied -> available`, `missing -> missing|failed`,
`stale -> stale|failed`, and
`insufficient -> insufficient|partial|failed`. Every fallback cache ref must be
frozen into the market source refs, and every successful receipt cache entry must be
present in both sets. Receipt start, completion and fetch times cannot exceed the
checkpoint knowledge cutoff. Any successful external receipt forces
`reconstructed_public_context`, and market `fetched_at` must equal the latest
successful receipt fetch time.

Every v3 checkpoint keeps these axes separate:

- `operation`: `ready`, `partial` or `blocked`;
- `decision`: `complete`, `partial`, `not_recorded`, `not_applicable` or `blocked`;
- `snapshot_cash_valuation`: field-level availability for position quantity, cost,
  cash, price, NAV, weight and industry;
- `market`: availability plus temporal role;
- `lifecycle`: `open`, `closed`, `ambiguous` or `unknown`;
- `outcome`: `interim`, `final`, `not_applicable` or `missing`.

Every gap has an axis, stable code, severity, owner, next step and source references.
The raw code is evidence detail, not the primary user-facing conclusion.

Material states require their own evidence. Root `source_refs` are always non-empty;
operation `ready|partial`, decision `complete|partial`, snapshot aggregate
`available|partial`, each snapshot field `available|partial`, market
`available|partial|stale|insufficient`, lifecycle `open|closed` and outcome
`interim|final` all require non-empty source refs. Snapshot aggregate state is
derived from the seven field states: `available` contains only
available/not-applicable fields and at least one available field; `missing` contains
only missing/not-applicable fields and at least one explicitly missing field;
`partial` contains at least one available and at least one partial/missing field. An
available field also requires a value; missing/not-applicable values remain null.
`market=available` additionally requires an effective time. An axis-blocking gap must be
`severity=blocker`, carry non-empty source references and place only that axis in
its defined blocked state.

For account actions, `owner_action_default` may place `user_known_at` at effective
time when the fact is unconflicted. It never proves `system_observed_at` and is
forbidden for market data. Later ingestion retains its true recorded/system
observation time. Later-acquired public data is
`reconstructed_public_context` (or an equally explicit retrospective state), never
proof that the user or system observed it at the decision time.

The four checkpoint times are `effective_at`, `user_known_at`,
`system_observed_at` and `recorded_at`; every one carries an explicit basis and
source references. Available bases are field-specific:

- effective: `source_occurred_at` or `source_effective_at`;
- user-known: `owner_action_default`, `explicit_user_record`,
  `source_occurred_at` or `source_effective_at`;
- system-observed: `system_observation`, `recorded_later` or
  `ingest_observation`;
- recorded: `recorded_later`, `ingest_observation` or `system_observation`.

`not_observed` and `unknown` are only for an actually null nullable time;
effective and recorded time are non-null. The semantic boundary is
`effective_at <= as_of <= knowledge_cutoff`; every non-null user/system/recorded
time must also be no later than `knowledge_cutoff`. Market context separately
preserves effective, public, fetched and system-observed time. The checkpoint is a
closed Draft 2020-12 object,
and `checkpoint_key` is exactly `review_checkpoint_key_` followed by 64 lowercase
hexadecimal characters.

Checkpoint kind/type/lifecycle/outcome combinations are closed. Active review kind
and active checkpoint type imply each other and require `open + interim`;
postmortem kind and type imply each other and require `closed + final`; an exit
requires `closed + final`. `open + final` and `closed + interim` are invalid, and
every final outcome requires a closed lifecycle.

Semantic identity is episode-rooted and hashes only `episode_id`, `review_kind`,
`checkpoint_type`, `perspective`, `as_of` and `knowledge_cutoff`.
`position_case_id` remains payload/projection evidence but cannot fork the same
semantic cutoff: changing it under the same tuple is a content conflict. The
canonical payload/content hash excludes wall-clock `inserted_at`; the separate
`investment_review.operation_checkpoint_row.v1` row-integrity hash binds the full
projection, payload SHA-256 and actual `inserted_at` and is recomputed on read.

This overlay must not change canonical event identity, make Decision fields optional
inside an actual Decision object, rewrite reviewed mapping semantics, modify old
artifacts, create motives/theses, diagnose psychology, score behavior, emit advice,
write the portfolio database, copy/upgrade an old sidecar, call a model/broker, add a
provider/dependency/credential, or publish.

See `docs/playbooks/INVESTMENT_REVIEW_REVIEWABILITY.md` and
`docs/contracts/INVESTMENT_REVIEW_OPERATION_CHECKPOINT.schema.json`.

## Product-completion v4 public-information amendment boundary

The separately authorized v4 amendment is additive. It must not reinterpret or
modify any v1 checkpoint, fallback receipt, schema file, identity, golden or
source replay. It adds exactly
`investment_review.operation_checkpoint.v2`,
`local_first_controlled_fallback_v2` and
`public_availability_user_knowledge_v1`.

Every v2 checkpoint binds a recomputed material operation anchor: event ID,
effective time and the four-field canonical P2C ordering key. Entry,
adjustment, exit and postmortem checkpoints use their corresponding operation;
an active checkpoint uses the last selected, validated material operation no
later than `as_of`. The invariant is
`operation_anchor_at <= as_of <= knowledge_cutoff`; callers cannot self-assert
the anchor.

For market or information evidence, the user perspective may project
`user_known_at_operation_by_verified_publication` only when the exact content
revision has verified publication bounds and
`upper_bound < operation_anchor_at`. Equality is ambiguous and ineligible.
Date-only evidence uses the source-timezone closed-day interval and the same
strict upper-bound test. Unknown/conflicted publication time, unknown timezone,
post-operation publication, content-hash/ref drift and an unproven later
revision remain unknown, ambiguous or ineligible.

This projection means policy-available, not actually read. It must keep
`actual_user_observation_proven=false` and must not infer attention,
understanding, motive, thesis or causality. System eligibility is separate and
requires a real `system_observed_at <= operation_anchor_at`; publication time
cannot prove system observation.

The v2 pre-bundle cache step may acquire an allowlisted historical version at
the real current time when perspective-eligible local coverage is missing,
stale or insufficient. Actual started/fetched/completed/system-observed audit
times may be later than the operation or historical cutoff and must never be
backdated or used as publication time. A user request must not be withheld only
because acquisition is late. A system request that cannot improve historical
system eligibility is canonical `withheld_by_cutoff` with zero attempts,
requests, response hashes, fetch time and cache entry. Shared-budget exhaustion
is a separate `budget_exhausted` limitation. Every such limitation still
produces a frozen manifest and any otherwise provable operation-ready active
checkpoint.

Every v2 receipt separately closes `attempt_count_status=verified|unknown` and
`budget_charged_attempts`. A bare provider exception must not fabricate an exact
attempt count: it is `failed`, count zero, status `unknown`, conservatively charges
the reserved bound, and aggregates as `request_count_status=bounded_unknown` plus
`unverified_attempt_upper_bound` and `provider_attempt_count_unknown`. Zero-request
guard receipts remain verified/zero and bind real `guard_audit_at=started_at=completed_at`
without fetch, system-observation, response-hash or cache-entry evidence.

The checkpoint market axis must bind one representative source's canonical envelope
content ID, closed information-time proof, version provenance and perspective
eligibility, plus the component-row-only `market_evidence_manifest_content_id` and
`market_evidence_manifest:<content_id>` source ref. The outer axis uses the simplified
closed temporal-role vocabulary; detailed eligibility roles remain nested. A source-less
axis has null representative proof, null market times, `not_applicable` public basis and
an explicit `missing` role while still binding the empty evidence manifest.

Every local v2 component source also embeds the bounded canonical origin database row;
every external source embeds the complete canonical immutable cache entry. Offline source
replay must rebuild the projected values, effective/public times, version and revision
proof, eligibility, receipt lineage and row identity from that origin proof. Projected
fields, hashes or references must never validate one another without the origin proof,
and revision conflicts must be derived from the competing origin proofs. Canonically
byte-identical provider rows may be deduplicated; different bytes remain distinct revision
candidates and must not be silently collapsed.

If a provider has already produced a verified successful receipt and a later provider
attempt has an unknown attempt count, the bounded fallback aggregate remains `succeeded`
and retains that success. It additionally records the bounded-unknown attempt limitation;
the later uncertainty must neither erase the successful evidence nor fabricate an exact
request total.

v2 inherits the exact v1 provider allowlist, safe parameters, redaction,
timeout/retry/concurrency/request caps, cache lineage and offline renderer,
source-replay, API and UI boundary. Raw bytes may cross perspectives only when
their revision and information-time provenance are identical; requirements,
resolutions, projections, manifests and task/run identities remain
perspective/policy/anchor-specific.

The existing authorized reviewability candidate may be upgraded once through
an explicit exact-v1-gated `BEGIN IMMEDIATE` marker transaction. The upgrade
must preserve WAL/quick-check, every DDL object and every immutable v1 row; it
adds no table, column, index or sidecar. Afterward, v1 rows remain readable and
replayable (and exact replays may be skipped), but no new v1 row may be created.
Before and after opening the writable handle and again under the immediate lock,
the upgrade must rebind the original main/WAL/SHM filesystem identity and the
SQLite `main` path. Path replacement or metadata/content drift fails before any
marker write.
New v2 checkpoints use a new explicit `knowledge_cutoff` and must fail before
SQLite insertion when the unchanged storage unique tuple would collide. See
`docs/contracts/INVESTMENT_REVIEW_OPERATION_CHECKPOINT_V2.schema.json`.

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

## P2H Stage 1 candidate and human-review-ledger boundary

After explicit P2G/P2F source artifacts are accepted and replayable, the
implementation may also:

- canonicalize one explicitly submitted `p2h.behavior_hypothesis_candidate.v1`
  with stable candidate ID/hash, dual time, exact evidence refs, alternatives,
  disconfirming observations and an observation-only plan;
- require counterevidence or an explicit source gap and replay every referenced
  artifact ID/hash before create-only sidecar ingest;
- append immutable `p2h.behavior_hypothesis_review_event.v1` human events;
- project candidate status deterministically at explicit `as_of` and
  `knowledge_cutoff` values, rejecting invalid transitions and concurrent state
  events rather than hiding them with an ID tie-break;
- query, show and source-replay candidates without modifying their P2G/P2F sources.

P2H Stage 1 must not infer or generate a candidate automatically, diagnose
psychology, emit advice or numeric scores/confidence, treat
`accepted_for_observation` as proven truth, update a profile or PersonalPlaybook,
create an intervention/experiment, open a UI path, or read/write the portfolio
database. See `docs/playbooks/INVESTMENT_REVIEW_P2H_STAGE1.md`.

## P2H Stage 2 Slice A observation-protocol boundary

After one canonical P2H Stage 1 candidate is explicitly
`accepted_for_observation`, the implementation may also:

- build one explicit, human-confirmed `p2h.observation_protocol.v1` bound to
  the exact candidate/hash, source artifacts, complete Stage 1 review-event set
  and an accepted historical projection at explicit dual-time cutoffs;
- preserve stable required-fact keys, an observation window and checkpoints,
  applicability, disconfirming and stop conditions, expiry, missing-evidence
  policy and privacy scope without collecting new facts automatically;
- create-only ingest protocols and immutable human
  `p2h.observation_protocol_review_event.v1` lifecycle events into additive v2
  sidecar tables;
- project `draft`, `submitted`, `approved_for_observation`, `active`, `paused`,
  `completed`, `abandoned` and `superseded` deterministically at explicit
  `as_of` and `knowledge_cutoff` values;
- source-replay the stored protocol through the formal Stage 1 candidate/event
  interfaces without modifying any Stage 1 row or source artifact.

Slice A must not auto-create or auto-activate a protocol from candidate status,
treat completion or expiry as proof, generate an intervention/experiment action,
record an attempt/outcome, update a profile or PersonalPlaybook, emit advice,
scores or numeric confidence, access portfolio SQLite/broker data/credentials, or
add UI/Web/API/order-execution paths. See
`docs/playbooks/INVESTMENT_REVIEW_P2H_STAGE2_OBSERVATION_PROTOCOL.md`.

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

For an approved P2H Stage 1 candidate/review-ledger run:

47. Build a candidate only from an explicit draft; require exact evidence IDs/hashes,
    alternatives, disconfirming observations and counterevidence or a source gap.
48. Validate deterministic identity, UTC whole-second dual time, semantic list order,
    no-diagnosis/no-advice/no-score rules and exact source replay before sidecar ingest.
49. Save candidates and human events create-only; identical replay is `SKIPPED`, while
    same-ID content drift, orphan events and missing supersession refs fail explicitly.
50. Project only from the explicit immutable event ledger at `as_of` and
    `knowledge_cutoff`; preserve out-of-order ingest determinism and historical states.
51. Treat `accepted_for_observation` as continued observation only, never proof, and
    stop before profile/playbook writes, intervention, experiment, UI or model generation.

For an approved P2H Stage 2 Slice A observation-protocol run:

52. Require an explicit human-confirmed protocol draft plus the exact Stage 1
    candidate, source artifacts and complete human-review event set; never build
    from candidate ID, latest status or a free-text summary alone.
53. Recompute the Stage 1 projection at the draft's explicit `as_of` and
    `knowledge_cutoff`, require `accepted_for_observation`, and bind the candidate,
    source, event-set and projection hashes into the protocol identity.
54. Validate UTC whole-second dual time, observation window/checkpoints/expiry,
    stable fact keys, missing-state preservation, privacy scope and the
    no-advice/no-score/no-profile/no-intervention boundary before ingest.
55. Save protocols and human lifecycle events create-only in the existing v2
    sidecar; exact replay is `SKIPPED`, while same-ID drift, orphan refs and
    supersession errors fail explicitly. Do not modify Stage 1 rows.
56. Project lifecycle only from the complete immutable event set at explicit
    cutoffs; preserve input-order determinism, reject concurrent semantic-time
    state events, and keep `note_added` state-neutral.
57. Project expiry separately from human state and keep `completed` governance-only;
    neither value proves or disproves the underlying hypothesis.
58. Source-replay through the formal Stage 1 store interfaces, then stop before
    Slice B, attempt/outcome, profile/playbook, UI/Web/API or any real-data run.

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
