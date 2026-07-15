# P2C inherited interface inventory

- Review sidecar owner: `src/investment_review/store.py`, schema v2, SQLite application ID `IRVW`.
- Canonical event: `CanonicalTradeEvent`; stable `event_id` derives from source identity or canonical event content.
- Event partition fields: explicit `account`, `market`, `symbol`; no strategy partition exists upstream.
- Event time fields: UTC `occurred_at` and `known_at`; the reviewed portfolio mapping visibly records `known_at_fallback=true` when source history lacks a trustworthy knowledge time.
- Explicit decisions: `decisions` plus `decision_event_links`; P2C may consume links but must not infer them.
- Existing review snapshot contract: P2A sidecar `PortfolioSnapshot`; it remains unchanged.
- P2B snapshot owner: `src/portfolio/store.py`, portfolio schema v7, engine `portfolio-snapshot-v1`.
- P2B public interfaces: `build_snapshot`, `get_snapshot`, and `list_snapshots` plus CLI `snapshot`, `snapshot-show`, and `snapshot-list`.
- P2B identity: account, as-of date, knowledge cutoff, engine version, and source-state hash; revisions are immutable.
- P2B time policy: ledger effective date and optional ledger/price/cash recorded-time cutoff; missing cutoff means current database knowledge and is unsafe for historical decision linkage.
- P2B lineage: portfolio source-state hash plus per-open-position transaction, price, and industry references.
- Canonical serialization: sorted compact JSON with stable Decimal/date strings; generation time is excluded from source-state identity.
- Extension point: a pure P2C projection in `src/investment_review/episodes.py`, consuming sidecar events and read-only P2B snapshot references.
- Persistence decision: keep sidecar schema v2 unchanged; emit a versioned canonical projection artifact and query it read-only.
- Focused inherited tests: Phase 1, P2A context, P2B snapshot service/CLI, and portfolio tracker tests.
- Protected baseline: the five recorded Bundle 10R hash-binding failures are not part of P2C.
