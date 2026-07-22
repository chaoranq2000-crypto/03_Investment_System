"""Separate SQLite store for normalized review data."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from .artifact_io import canonical_json_bytes
from .behavior_hypothesis_candidates import (
    _canonical_timestamp,
    project_behavior_hypothesis_state,
    replay_validate_behavior_hypothesis_candidate,
    validate_behavior_hypothesis_review_event,
)
from .behavior_observation_protocols import (
    project_observation_protocol_state,
    replay_validate_observation_protocol,
    validate_observation_protocol_review_event,
)
from .models import CanonicalTradeEvent, DecisionRecord, SourceDefinition, canonical_json
from .portfolio_context import PortfolioContext, PortfolioSnapshot, calculate_portfolio_metrics


SCHEMA_VERSION = 2
APPLICATION_ID = 0x49525657  # ASCII "IRVW"
P2H_STAGE1_SCHEMA_VERSION = 1
P2H_STAGE2_SLICE_A_SCHEMA_VERSION = 1

class ReviewStoreError(RuntimeError):
    """Base error for the review store."""


class DataConflictError(ReviewStoreError):
    """Same source record ID was observed with different content."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS data_sources (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    uri TEXT NOT NULL,
    timezone TEXT NOT NULL,
    read_only INTEGER NOT NULL CHECK (read_only IN (0, 1)),
    config_json TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_config_versions (
    source_id TEXT NOT NULL REFERENCES data_sources(source_id),
    fingerprint TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (source_id, fingerprint)
);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    market TEXT,
    occurred_at TEXT NOT NULL,
    known_at TEXT NOT NULL,
    status TEXT NOT NULL,
    thesis TEXT NOT NULL,
    trigger_text TEXT,
    invalidation_text TEXT,
    expected_horizon TEXT,
    portfolio_role TEXT,
    direct_reason TEXT,
    risk_notes TEXT,
    raw_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES data_sources(source_id),
    source_fingerprint TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    seen_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    error_text TEXT,
    manifest_json TEXT NOT NULL,
    FOREIGN KEY (source_id, source_fingerprint)
        REFERENCES source_config_versions(source_id, fingerprint)
);

CREATE TABLE IF NOT EXISTS trade_events (
    event_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES data_sources(source_id),
    source_record_id TEXT,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    known_at TEXT NOT NULL,
    account TEXT,
    market TEXT,
    symbol TEXT NOT NULL,
    side TEXT,
    quantity TEXT,
    price TEXT,
    gross_amount TEXT,
    cash_amount TEXT,
    fees TEXT,
    currency TEXT NOT NULL,
    raw_payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    first_ingest_run_id TEXT REFERENCES ingest_runs(run_id),
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_run_events (
    run_id TEXT NOT NULL REFERENCES ingest_runs(run_id) ON DELETE CASCADE,
    event_id TEXT NOT NULL REFERENCES trade_events(event_id),
    outcome TEXT NOT NULL CHECK (outcome IN ('INSERTED', 'SKIPPED')),
    payload_sha256 TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    PRIMARY KEY (run_id, event_id)
);

CREATE TABLE IF NOT EXISTS decision_event_links (
    decision_id TEXT NOT NULL REFERENCES decisions(decision_id) ON DELETE CASCADE,
    event_id TEXT NOT NULL REFERENCES trade_events(event_id) ON DELETE CASCADE,
    relation TEXT NOT NULL DEFAULT 'execution',
    created_at TEXT NOT NULL,
    PRIMARY KEY (decision_id, event_id, relation)
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    source_id TEXT REFERENCES data_sources(source_id),
    source_record_id TEXT,
    observed_at TEXT NOT NULL,
    known_at TEXT NOT NULL,
    account TEXT,
    nav TEXT,
    cash TEXT,
    gross_exposure TEXT,
    net_exposure TEXT,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS position_snapshot_items (
    snapshot_id TEXT NOT NULL REFERENCES portfolio_snapshots(snapshot_id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    market TEXT,
    quantity TEXT NOT NULL,
    cost_basis TEXT,
    market_price TEXT,
    market_value TEXT,
    currency TEXT NOT NULL DEFAULT 'CNY',
    payload_json TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, symbol, market)
);

CREATE TABLE IF NOT EXISTS behavior_hypothesis_candidates (
    candidate_id TEXT PRIMARY KEY,
    canonical_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    knowledge_at TEXT NOT NULL,
    subject_scope_kind TEXT NOT NULL,
    subject_scope_refs_json TEXT NOT NULL,
    pattern_family TEXT NOT NULL,
    source_verification_status TEXT NOT NULL CHECK (
        source_verification_status = 'verified'
    ),
    payload_json TEXT NOT NULL,
    inserted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS behavior_hypothesis_review_events (
    review_event_id TEXT PRIMARY KEY,
    canonical_hash TEXT NOT NULL UNIQUE,
    candidate_id TEXT NOT NULL REFERENCES behavior_hypothesis_candidates(candidate_id),
    event_type TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    knowledge_at TEXT NOT NULL,
    evidence_cutoff TEXT NOT NULL,
    reviewer_ref TEXT NOT NULL,
    supersedes_event_id TEXT REFERENCES behavior_hypothesis_review_events(review_event_id),
    supersedes_candidate_id TEXT REFERENCES behavior_hypothesis_candidates(candidate_id),
    payload_json TEXT NOT NULL,
    inserted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS behavior_observation_protocols (
    protocol_id TEXT PRIMARY KEY,
    canonical_hash TEXT NOT NULL UNIQUE,
    candidate_id TEXT NOT NULL REFERENCES behavior_hypothesis_candidates(candidate_id),
    created_at TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    knowledge_at TEXT NOT NULL,
    expiry_at TEXT NOT NULL,
    stage1_event_set_hash TEXT NOT NULL,
    stage1_projection_hash TEXT NOT NULL,
    source_verification_status TEXT NOT NULL CHECK (
        source_verification_status = 'verified'
    ),
    payload_json TEXT NOT NULL,
    inserted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS behavior_observation_protocol_review_events (
    protocol_review_event_id TEXT PRIMARY KEY,
    canonical_hash TEXT NOT NULL UNIQUE,
    protocol_id TEXT NOT NULL REFERENCES behavior_observation_protocols(protocol_id),
    event_type TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    knowledge_at TEXT NOT NULL,
    evidence_cutoff TEXT NOT NULL,
    reviewer_ref TEXT NOT NULL,
    supersedes_event_id TEXT REFERENCES behavior_observation_protocol_review_events(
        protocol_review_event_id
    ),
    superseded_by_protocol_id TEXT REFERENCES behavior_observation_protocols(protocol_id),
    payload_json TEXT NOT NULL,
    inserted_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trade_events_symbol_time
    ON trade_events(symbol, occurred_at);
CREATE INDEX IF NOT EXISTS idx_trade_events_known_at
    ON trade_events(known_at);
CREATE INDEX IF NOT EXISTS idx_trade_events_source_record
    ON trade_events(source_id, source_record_id);
CREATE INDEX IF NOT EXISTS idx_ingest_run_events_event
    ON ingest_run_events(event_id, run_id);
CREATE INDEX IF NOT EXISTS idx_decisions_symbol_time
    ON decisions(symbol, occurred_at);
CREATE INDEX IF NOT EXISTS idx_snapshots_observed_at
    ON portfolio_snapshots(observed_at);
CREATE INDEX IF NOT EXISTS idx_behavior_candidates_scope
    ON behavior_hypothesis_candidates(subject_scope_kind, pattern_family);
CREATE INDEX IF NOT EXISTS idx_behavior_candidates_dual_time
    ON behavior_hypothesis_candidates(effective_at, knowledge_at, created_at);
CREATE INDEX IF NOT EXISTS idx_behavior_review_events_candidate_time
    ON behavior_hypothesis_review_events(
        candidate_id, effective_at, knowledge_at, reviewed_at, review_event_id
    );
CREATE INDEX IF NOT EXISTS idx_observation_protocols_candidate_time
    ON behavior_observation_protocols(
        candidate_id, effective_at, knowledge_at, created_at, protocol_id
    );
CREATE INDEX IF NOT EXISTS idx_observation_protocol_events_protocol_time
    ON behavior_observation_protocol_review_events(
        protocol_id, effective_at, knowledge_at, reviewed_at,
        protocol_review_event_id
    );
"""


class ReviewStore:
    def __init__(self, path: str | Path = "data/db/investment_review.sqlite3") -> None:
        self.path = Path(path)

    def _connect(self, *, read_only: bool = False) -> sqlite3.Connection:
        if read_only:
            if not self.path.exists():
                raise FileNotFoundError(self.path)
            uri = f"{self.path.resolve().as_uri()}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    @contextmanager
    def connection(self, *, read_only: bool = False) -> Iterator[sqlite3.Connection]:
        conn = self._connect(read_only=read_only)
        try:
            yield conn
        finally:
            conn.close()

    def initialize(self) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            application_id = conn.execute("PRAGMA application_id").fetchone()[0]
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            }
            if tables and application_id != APPLICATION_ID:
                raise ReviewStoreError(
                    "Refusing to initialize an unmarked or legacy SQLite database: "
                    f"{self.path}. Create a new v{SCHEMA_VERSION} sidecar and reimport; "
                    "automatic legacy migration cannot reconstruct event-run lineage."
                )
            if not tables and application_id not in (0, APPLICATION_ID):
                raise ReviewStoreError(
                    f"Unexpected SQLite application_id for review database: {application_id}"
                )
            if tables:
                version_row = conn.execute(
                    "SELECT value FROM schema_meta WHERE key='schema_version'"
                ).fetchone() if "schema_meta" in tables else None
                schema_version = int(version_row[0]) if version_row else None
                user_version = conn.execute("PRAGMA user_version").fetchone()[0]
                if schema_version != SCHEMA_VERSION or user_version != SCHEMA_VERSION:
                    raise ReviewStoreError(
                        f"Review database is legacy or inconsistent "
                        f"(schema_version={schema_version}, user_version={user_version}). "
                        f"Create a new v{SCHEMA_VERSION} sidecar and reimport."
                    )
                feature_row = conn.execute(
                    "SELECT value FROM schema_meta "
                    "WHERE key='p2h_stage1_schema_version'"
                ).fetchone()
                if (
                    feature_row is not None
                    and int(feature_row[0]) != P2H_STAGE1_SCHEMA_VERSION
                ):
                    raise ReviewStoreError(
                        "Unsupported P2H Stage 1 feature schema: "
                        f"{feature_row[0]}"
                    )
                stage2_row = conn.execute(
                    "SELECT value FROM schema_meta "
                    "WHERE key='p2h_stage2_slice_a_schema_version'"
                ).fetchone()
                if (
                    stage2_row is not None
                    and int(stage2_row[0]) != P2H_STAGE2_SLICE_A_SCHEMA_VERSION
                ):
                    raise ReviewStoreError(
                        "Unsupported P2H Stage 2 Slice A feature schema: "
                        f"{stage2_row[0]}"
                    )

            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(_SCHEMA_SQL)

            now = _now()
            conn.execute(f"PRAGMA application_id = {APPLICATION_ID}")
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            conn.execute(
                "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(SCHEMA_VERSION),),
            )
            conn.execute(
                "INSERT INTO schema_meta(key, value) VALUES('initialized_at', ?) "
                "ON CONFLICT(key) DO NOTHING",
                (now,),
            )
            conn.execute(
                "INSERT INTO schema_meta(key, value) "
                "VALUES('p2h_stage1_schema_version', ?) "
                "ON CONFLICT(key) DO NOTHING",
                (str(P2H_STAGE1_SCHEMA_VERSION),),
            )
            conn.execute(
                "INSERT INTO schema_meta(key, value) "
                "VALUES('p2h_stage2_slice_a_schema_version', ?) "
                "ON CONFLICT(key) DO NOTHING",
                (str(P2H_STAGE2_SLICE_A_SCHEMA_VERSION),),
            )
            conn.commit()
        finally:
            conn.close()
        return {"database": str(self.path), "schema_version": SCHEMA_VERSION}

    def _ensure_initialized(self) -> None:
        if not self.path.is_file():
            raise ReviewStoreError(
                f"Review database is not initialized: {self.path}. Run the init command first."
            )
        with self.connection(read_only=True) as conn:
            application_id = conn.execute("PRAGMA application_id").fetchone()[0]
            if application_id != APPLICATION_ID:
                raise ReviewStoreError(
                    f"Not an investment-review database: {self.path}. "
                    "Refusing to create or modify schema implicitly."
                )
            version_row = conn.execute(
                "SELECT value FROM schema_meta WHERE key='schema_version'"
            ).fetchone()
            version = int(version_row[0]) if version_row else None
            if version != SCHEMA_VERSION:
                raise ReviewStoreError(
                    f"Review database schema_version={version}; create a new v{SCHEMA_VERSION} "
                    "sidecar and reimport."
                )

    def _ensure_p2h_stage1_initialized(self) -> None:
        self._ensure_initialized()
        with self.connection(read_only=True) as conn:
            feature_row = conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key='p2h_stage1_schema_version'"
            ).fetchone()
            tables = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        required = {
            "behavior_hypothesis_candidates",
            "behavior_hypothesis_review_events",
        }
        if (
            feature_row is None
            or int(feature_row[0]) != P2H_STAGE1_SCHEMA_VERSION
            or not required.issubset(tables)
        ):
            raise ReviewStoreError(
                "P2H Stage 1 tables are not initialized; run the init command first."
            )

    def _ensure_p2h_stage2_slice_a_initialized(self) -> None:
        self._ensure_p2h_stage1_initialized()
        with self.connection(read_only=True) as conn:
            feature_row = conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key='p2h_stage2_slice_a_schema_version'"
            ).fetchone()
            tables = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        required = {
            "behavior_observation_protocols",
            "behavior_observation_protocol_review_events",
        }
        if (
            feature_row is None
            or int(feature_row[0]) != P2H_STAGE2_SLICE_A_SCHEMA_VERSION
            or not required.issubset(tables)
        ):
            raise ReviewStoreError(
                "P2H Stage 2 Slice A tables are not initialized; run the init "
                "command first."
            )

    @staticmethod
    def _upsert_source(conn: sqlite3.Connection, source: SourceDefinition) -> None:
        source.validate()
        now = _now()
        conn.execute(
            """
            INSERT INTO data_sources(
                source_id, name, kind, uri, timezone, read_only,
                config_json, fingerprint, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                name=excluded.name,
                kind=excluded.kind,
                uri=excluded.uri,
                timezone=excluded.timezone,
                read_only=excluded.read_only,
                config_json=excluded.config_json,
                fingerprint=excluded.fingerprint,
                updated_at=excluded.updated_at
            """,
            (
                source.source_id,
                source.name,
                source.kind,
                source.uri,
                source.timezone,
                1 if source.read_only else 0,
                canonical_json(dict(source.config)),
                source.fingerprint,
                now,
                now,
            ),
        )

    @staticmethod
    def _register_source_version(conn: sqlite3.Connection, source: SourceDefinition) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO source_config_versions(
                source_id, fingerprint, config_json, created_at
            ) VALUES (?, ?, ?, ?)
            """,
            (
                source.source_id,
                source.fingerprint,
                canonical_json(dict(source.config)),
                _now(),
            ),
        )

    @classmethod
    def _register_failed_source_attempt(
        cls, conn: sqlite3.Connection, source: SourceDefinition
    ) -> None:
        exists = conn.execute(
            "SELECT 1 FROM data_sources WHERE source_id = ?", (source.source_id,)
        ).fetchone()
        if exists is None:
            cls._upsert_source(conn, source)
        cls._register_source_version(conn, source)

    def import_events(
        self,
        source: SourceDefinition,
        events: Sequence[CanonicalTradeEvent],
        *,
        manifest: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Atomically import canonical events and detect source-record drift."""

        self._ensure_initialized()
        for event in events:
            event.validate()
            if event.source_id != source.source_id:
                raise ReviewStoreError(
                    f"Event {event.event_id} belongs to {event.source_id}, expected {source.source_id}"
                )

        event_ids = [event.event_id for event in events]
        if len(set(event_ids)) != len(event_ids):
            raise ReviewStoreError("Input contains duplicate canonical event IDs")

        run_id = f"run_{uuid.uuid4().hex}"
        started = _now()
        inserted = 0
        skipped = 0

        try:
            with self.connection() as conn:
                with conn:
                    self._upsert_source(conn, source)
                    self._register_source_version(conn, source)
                    conn.execute(
                        """
                        INSERT INTO ingest_runs(
                            run_id, source_id, source_fingerprint,
                            started_at, status, manifest_json
                        ) VALUES (?, ?, ?, ?, 'RUNNING', ?)
                        """,
                        (
                            run_id,
                            source.source_id,
                            source.fingerprint,
                            started,
                            canonical_json(manifest or {}),
                        ),
                    )

                    previous_run = conn.execute(
                        """
                        SELECT r.run_id
                        FROM ingest_runs r
                        WHERE r.source_id = ? AND r.status = 'COMPLETED'
                          AND EXISTS (
                              SELECT 1 FROM ingest_run_events l WHERE l.run_id = r.run_id
                          )
                        ORDER BY r.finished_at DESC, r.run_id DESC
                        LIMIT 1
                        """,
                        (source.source_id,),
                    ).fetchone()
                    if previous_run is not None:
                        previous_ids = {
                            row[0]
                            for row in conn.execute(
                                "SELECT event_id FROM ingest_run_events WHERE run_id = ?",
                                (previous_run[0],),
                            ).fetchall()
                        }
                        missing_ids = previous_ids.difference(event_ids)
                        if missing_ids:
                            raise DataConflictError(
                                "Source snapshot removed or replaced previously observed records: "
                                f"previous_run={previous_run[0]}, missing_count={len(missing_ids)}"
                            )

                    for event in events:
                        existing = conn.execute(
                            """
                            SELECT payload_sha256, source_id, source_record_id,
                                   event_type, occurred_at, known_at, account, market,
                                   symbol, side, quantity, price, gross_amount,
                                   cash_amount, fees, currency
                            FROM trade_events WHERE event_id = ?
                            """,
                            (event.event_id,),
                        ).fetchone()
                        if existing is not None:
                            expected = {
                                "payload_sha256": event.payload_sha256,
                                "source_id": event.source_id,
                                "source_record_id": event.source_record_id,
                                "event_type": event.event_type,
                                "occurred_at": event.occurred_at,
                                "known_at": event.known_at,
                                "account": event.account,
                                "market": event.market,
                                "symbol": event.symbol,
                                "side": event.side,
                                "quantity": str(event.quantity) if event.quantity is not None else None,
                                "price": str(event.price) if event.price is not None else None,
                                "gross_amount": str(event.gross_amount) if event.gross_amount is not None else None,
                                "cash_amount": str(event.cash_amount) if event.cash_amount is not None else None,
                                "fees": str(event.fees) if event.fees is not None else None,
                                "currency": event.currency,
                            }
                            actual = dict(existing)
                            if actual != expected:
                                raise DataConflictError(
                                    "Source record changed after an earlier import: "
                                    f"event_id={event.event_id}, source_record_id={event.source_record_id!r}"
                                )
                            conn.execute(
                                """
                                INSERT INTO ingest_run_events(
                                    run_id, event_id, outcome, payload_sha256, observed_at
                                ) VALUES (?, ?, 'SKIPPED', ?, ?)
                                """,
                                (run_id, event.event_id, event.payload_sha256, _now()),
                            )
                            skipped += 1
                            continue

                        conn.execute(
                            """
                            INSERT INTO trade_events(
                                event_id, source_id, source_record_id, event_type,
                                occurred_at, known_at, account, market, symbol, side,
                                quantity, price, gross_amount, cash_amount, fees, currency,
                                raw_payload_json, payload_sha256,
                                first_ingest_run_id, ingested_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                event.event_id,
                                event.source_id,
                                event.source_record_id,
                                event.event_type,
                                event.occurred_at,
                                event.known_at,
                                event.account,
                                event.market,
                                event.symbol,
                                event.side,
                                str(event.quantity) if event.quantity is not None else None,
                                str(event.price) if event.price is not None else None,
                                str(event.gross_amount) if event.gross_amount is not None else None,
                                str(event.cash_amount) if event.cash_amount is not None else None,
                                str(event.fees) if event.fees is not None else None,
                                event.currency,
                                canonical_json(dict(event.raw_payload)),
                                event.payload_sha256,
                                run_id,
                                _now(),
                            ),
                        )
                        conn.execute(
                            """
                            INSERT INTO ingest_run_events(
                                run_id, event_id, outcome, payload_sha256, observed_at
                            ) VALUES (?, ?, 'INSERTED', ?, ?)
                            """,
                            (run_id, event.event_id, event.payload_sha256, _now()),
                        )
                        inserted += 1

                    conn.execute(
                        """
                        UPDATE ingest_runs
                        SET finished_at=?, status='COMPLETED', seen_count=?,
                            inserted_count=?, skipped_count=?
                        WHERE run_id=?
                        """,
                        (_now(), len(events), inserted, skipped, run_id),
                    )
        except Exception as exc:
            # Record the failed attempt without retaining any partial event rows.
            with self.connection() as conn:
                with conn:
                    self._register_failed_source_attempt(conn, source)
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO ingest_runs(
                            run_id, source_id, source_fingerprint,
                            started_at, finished_at, status,
                            seen_count, inserted_count, skipped_count,
                            error_text, manifest_json
                        ) VALUES (?, ?, ?, ?, ?, 'FAILED', ?, 0, 0, ?, ?)
                        """,
                        (
                            run_id,
                            source.source_id,
                            source.fingerprint,
                            started,
                            _now(),
                            len(events),
                            str(exc),
                            canonical_json(manifest or {}),
                        ),
                    )
            raise

        return {
            "run_id": run_id,
            "source_id": source.source_id,
            "seen": len(events),
            "inserted": inserted,
            "skipped": skipped,
            "status": "COMPLETED",
        }

    def add_decision(self, decision: DecisionRecord) -> str:
        self._ensure_initialized()
        decision.validate()
        now = _now()
        with self.connection() as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO decisions(
                        decision_id, symbol, market, occurred_at, known_at, status,
                        thesis, trigger_text, invalidation_text, expected_horizon,
                        portfolio_role, direct_reason, risk_notes, raw_note,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        decision.decision_id,
                        decision.symbol,
                        decision.market,
                        decision.occurred_at,
                        decision.known_at,
                        decision.status,
                        decision.thesis,
                        decision.trigger_text,
                        decision.invalidation_text,
                        decision.expected_horizon,
                        decision.portfolio_role,
                        decision.direct_reason,
                        decision.risk_notes,
                        decision.raw_note,
                        now,
                        now,
                    ),
                )
        return decision.decision_id

    def link_decision_event(
        self, decision_id: str, event_id: str, relation: str = "execution"
    ) -> None:
        self._ensure_initialized()
        with self.connection() as conn:
            with conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO decision_event_links(
                        decision_id, event_id, relation, created_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (decision_id, event_id, relation, _now()),
                )

    def save_portfolio_snapshot(
        self, source: SourceDefinition, snapshot: PortfolioSnapshot
    ) -> dict[str, Any]:
        """Persist one immutable portfolio snapshot in the sidecar review DB."""

        self._ensure_initialized()
        source.validate()
        snapshot.validate()
        if not source.read_only:
            raise ReviewStoreError("Portfolio snapshot source must be read-only")
        if snapshot.source_id != source.source_id:
            raise ReviewStoreError("Snapshot source_id does not match source definition")
        snapshot_id = snapshot.resolved_snapshot_id
        payload = snapshot.to_dict()
        payload_sha256 = snapshot.payload_sha256
        metrics = calculate_portfolio_metrics(snapshot)
        now = _now()
        with self.connection() as conn:
            with conn:
                self._upsert_source(conn, source)
                self._register_source_version(conn, source)
                existing = conn.execute(
                    "SELECT payload_sha256 FROM portfolio_snapshots WHERE snapshot_id = ?",
                    (snapshot_id,),
                ).fetchone()
                if existing is not None:
                    if existing["payload_sha256"] != payload_sha256:
                        raise DataConflictError(
                            f"Portfolio snapshot {snapshot_id} was observed with different content"
                        )
                    return {"snapshot_id": snapshot_id, "status": "SKIPPED"}
                conn.execute(
                    """
                    INSERT INTO portfolio_snapshots(
                        snapshot_id, source_id, source_record_id, observed_at, known_at,
                        account, nav, cash, gross_exposure, net_exposure,
                        payload_json, payload_sha256, ingested_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        source.source_id,
                        snapshot.source_record_id,
                        snapshot.observed_at,
                        snapshot.known_at,
                        snapshot.account,
                        str(snapshot.net_asset_value),
                        str(snapshot.cash),
                        metrics["gross_exposure"],
                        metrics["net_exposure"],
                        canonical_json(payload),
                        payload_sha256,
                        now,
                    ),
                )
                for position in snapshot.positions:
                    conn.execute(
                        """
                        INSERT INTO position_snapshot_items(
                            snapshot_id, symbol, market, quantity, cost_basis,
                            market_price, market_value, currency, payload_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            snapshot_id,
                            position.symbol,
                            position.market or "",
                            str(position.quantity),
                            str(position.cost_basis) if position.cost_basis is not None else None,
                            str(position.price) if position.price is not None else None,
                            str(position.market_value) if position.market_value is not None else None,
                            position.currency,
                            canonical_json(position.to_dict()),
                        ),
                    )
        return {"snapshot_id": snapshot_id, "status": "INSERTED"}

    def load_portfolio_snapshot(self, snapshot_id: str) -> PortfolioSnapshot:
        self._ensure_initialized()
        with self.connection(read_only=True) as conn:
            row = conn.execute(
                "SELECT payload_json FROM portfolio_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            raise ReviewStoreError(f"Portfolio snapshot not found: {snapshot_id}")
        payload = json.loads(row["payload_json"])
        return PortfolioSnapshot.from_dict(payload, default_source_id=payload.get("source_id"), timezone="UTC")

    def get_decision(self, decision_id: str) -> dict[str, Any]:
        self._ensure_initialized()
        with self.connection(read_only=True) as conn:
            row = conn.execute(
                "SELECT * FROM decisions WHERE decision_id = ?", (decision_id,)
            ).fetchone()
        if row is None:
            raise ReviewStoreError(f"Decision not found: {decision_id}")
        return dict(row)

    def build_decision_portfolio_context(
        self,
        *,
        decision_id: str,
        before_snapshot_id: str,
        after_snapshot_id: str | None = None,
    ) -> PortfolioContext:
        decision = self.get_decision(decision_id)
        return PortfolioContext(
            reference_type="decision",
            reference_id=decision_id,
            reference_symbol=decision["symbol"],
            reference_occurred_at=decision["occurred_at"],
            before_snapshot=self.load_portfolio_snapshot(before_snapshot_id),
            after_snapshot=(
                self.load_portfolio_snapshot(after_snapshot_id) if after_snapshot_id else None
            ),
        )

    def list_events(
        self,
        *,
        limit: int = 50,
        symbol: str | None = None,
        include_raw: bool = False,
    ) -> list[dict[str, Any]]:
        self._ensure_initialized()
        columns = "*" if include_raw else (
            "event_id, source_id, source_record_id, event_type, occurred_at, known_at, "
            "account, market, symbol, side, quantity, price, gross_amount, cash_amount, "
            "fees, currency, payload_sha256, first_ingest_run_id, ingested_at"
        )
        query = f"SELECT {columns} FROM trade_events"
        params: list[Any] = []
        if symbol:
            query += " WHERE symbol = ?"
            params.append(symbol.strip().upper())
        query += " ORDER BY occurred_at DESC, event_id DESC LIMIT ?"
        params.append(max(1, min(int(limit), 1000)))
        with self.connection(read_only=True) as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def list_episode_projection_inputs(
        self,
        *,
        account: str | None = None,
        symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return all canonical event inputs plus explicit Decision links for P2C."""

        self._ensure_initialized()
        filters: list[str] = []
        params: list[Any] = []
        if account:
            filters.append("account = ?")
            params.append(account.strip())
        if symbol:
            filters.append("symbol = ?")
            params.append(symbol.strip().upper())
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        with self.connection(read_only=True) as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM trade_events
                {where}
                ORDER BY account, market, symbol, occurred_at, source_record_id, event_id
                """,
                params,
            ).fetchall()
            event_ids = [str(row["event_id"]) for row in rows]
            links: dict[str, list[dict[str, Any]]] = {event_id: [] for event_id in event_ids}
            if event_ids:
                placeholders = ",".join("?" for _ in event_ids)
                for link in conn.execute(
                    f"""
                    SELECT l.event_id, l.relation,
                           d.decision_id, d.symbol, d.market,
                           d.occurred_at, d.known_at, d.status
                    FROM decision_event_links l
                    JOIN decisions d ON d.decision_id = l.decision_id
                    WHERE l.event_id IN ({placeholders})
                    ORDER BY l.event_id, d.decision_id, l.relation
                    """,
                    event_ids,
                ):
                    links[str(link["event_id"])].append(
                        {
                            "decision_id": link["decision_id"],
                            "event_id": link["event_id"],
                            "relation": link["relation"],
                            "symbol": link["symbol"],
                            "market": link["market"],
                            "occurred_at": link["occurred_at"],
                            "known_at": link["known_at"],
                            "status": link["status"],
                            "link_source": "decision_event_links",
                        }
                    )
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["raw_payload"] = json.loads(item.pop("raw_payload_json"))
            item["decision_refs"] = links[str(item["event_id"])]
            result.append(item)
        return result

    @staticmethod
    def _p2h_payload_json(value: Mapping[str, Any]) -> str:
        return canonical_json_bytes(value).decode("utf-8")

    def save_behavior_hypothesis_candidate(
        self,
        candidate: Mapping[str, Any],
        *,
        source_artifacts: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Create one source-verified candidate or idempotently replay it."""

        self._ensure_p2h_stage1_initialized()
        candidate_id = str(candidate.get("candidate_id") or "")
        canonical_hash = str(candidate.get("canonical_hash") or "")
        payload_json = self._p2h_payload_json(candidate)
        with self.connection() as conn:
            with conn:
                existing = conn.execute(
                    "SELECT canonical_hash, payload_json "
                    "FROM behavior_hypothesis_candidates WHERE candidate_id = ?",
                    (candidate_id,),
                ).fetchone()
                if existing is not None:
                    if (
                        existing["canonical_hash"] == canonical_hash
                        and existing["payload_json"] == payload_json
                    ):
                        return {
                            "candidate_id": candidate_id,
                            "canonical_hash": canonical_hash,
                            "status": "SKIPPED",
                            "source_verification": "verified",
                        }
                    raise DataConflictError(
                        "Behavior hypothesis candidate changed after creation: "
                        f"candidate_id={candidate_id}"
                    )

                validation = replay_validate_behavior_hypothesis_candidate(
                    candidate,
                    source_artifacts=source_artifacts,
                )
                if (
                    validation["validation_status"] != "accepted"
                    or validation["source_verification"]["status"] != "verified"
                ):
                    raise ReviewStoreError(
                        "Behavior hypothesis candidate failed source replay: "
                        + ", ".join(validation["finding_codes"])
                    )
                hash_owner = conn.execute(
                    "SELECT candidate_id FROM behavior_hypothesis_candidates "
                    "WHERE canonical_hash = ?",
                    (canonical_hash,),
                ).fetchone()
                if hash_owner is not None:
                    raise DataConflictError(
                        "Behavior hypothesis canonical hash already belongs to "
                        f"candidate_id={hash_owner['candidate_id']}"
                    )
                scope = candidate["subject_scope"]
                conn.execute(
                    """
                    INSERT INTO behavior_hypothesis_candidates(
                        candidate_id, canonical_hash, created_at, effective_at,
                        knowledge_at, subject_scope_kind, subject_scope_refs_json,
                        pattern_family, source_verification_status, payload_json,
                        inserted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'verified', ?, ?)
                    """,
                    (
                        candidate_id,
                        canonical_hash,
                        candidate["created_at"],
                        candidate["effective_at"],
                        candidate["knowledge_at"],
                        scope["kind"],
                        canonical_json(scope["refs"]),
                        candidate["pattern_family"],
                        payload_json,
                        _now(),
                    ),
                )
        return {
            "candidate_id": candidate_id,
            "canonical_hash": canonical_hash,
            "status": "INSERTED",
            "source_verification": "verified",
        }

    def save_behavior_hypothesis_review_event(
        self, event: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Create one immutable review event or idempotently replay it."""

        self._ensure_p2h_stage1_initialized()
        event_id = str(event.get("review_event_id") or "")
        canonical_hash = str(event.get("canonical_hash") or "")
        candidate_id = str(event.get("candidate_id") or "")
        payload_json = self._p2h_payload_json(event)
        with self.connection() as conn:
            with conn:
                existing = conn.execute(
                    "SELECT canonical_hash, payload_json "
                    "FROM behavior_hypothesis_review_events "
                    "WHERE review_event_id = ?",
                    (event_id,),
                ).fetchone()
                if existing is not None:
                    if (
                        existing["canonical_hash"] == canonical_hash
                        and existing["payload_json"] == payload_json
                    ):
                        return {
                            "review_event_id": event_id,
                            "candidate_id": candidate_id,
                            "canonical_hash": canonical_hash,
                            "status": "SKIPPED",
                        }
                    raise DataConflictError(
                        "Behavior hypothesis review event changed after creation: "
                        f"review_event_id={event_id}"
                    )

                validation = validate_behavior_hypothesis_review_event(event)
                if validation["validation_status"] != "accepted":
                    raise ReviewStoreError(
                        "Behavior hypothesis review event failed validation: "
                        + ", ".join(validation["finding_codes"])
                    )
                candidate_row = conn.execute(
                    "SELECT knowledge_at FROM behavior_hypothesis_candidates "
                    "WHERE candidate_id = ?",
                    (candidate_id,),
                ).fetchone()
                if candidate_row is None:
                    raise ReviewStoreError(
                        f"Behavior hypothesis candidate not found: {candidate_id}"
                    )
                if event["evidence_cutoff"] < candidate_row["knowledge_at"]:
                    raise ReviewStoreError(
                        "Review evidence_cutoff cannot precede candidate knowledge_at"
                    )
                supersedes_event_id = event.get("supersedes_event_id")
                if supersedes_event_id is not None:
                    parent_event = conn.execute(
                        "SELECT candidate_id FROM behavior_hypothesis_review_events "
                        "WHERE review_event_id = ?",
                        (supersedes_event_id,),
                    ).fetchone()
                    if parent_event is None:
                        raise ReviewStoreError(
                            "Superseded review event not found: "
                            f"{supersedes_event_id}"
                        )
                supersedes_candidate_id = event.get("supersedes_candidate_id")
                if supersedes_candidate_id is not None:
                    parent_candidate = conn.execute(
                        "SELECT 1 FROM behavior_hypothesis_candidates "
                        "WHERE candidate_id = ?",
                        (supersedes_candidate_id,),
                    ).fetchone()
                    if parent_candidate is None:
                        raise ReviewStoreError(
                            "Superseded candidate not found: "
                            f"{supersedes_candidate_id}"
                        )
                hash_owner = conn.execute(
                    "SELECT review_event_id "
                    "FROM behavior_hypothesis_review_events "
                    "WHERE canonical_hash = ?",
                    (canonical_hash,),
                ).fetchone()
                if hash_owner is not None:
                    raise DataConflictError(
                        "Behavior hypothesis event canonical hash already belongs to "
                        f"review_event_id={hash_owner['review_event_id']}"
                    )
                conn.execute(
                    """
                    INSERT INTO behavior_hypothesis_review_events(
                        review_event_id, canonical_hash, candidate_id, event_type,
                        reviewed_at, effective_at, knowledge_at, evidence_cutoff,
                        reviewer_ref, supersedes_event_id, supersedes_candidate_id,
                        payload_json, inserted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        canonical_hash,
                        candidate_id,
                        event["event_type"],
                        event["reviewed_at"],
                        event["effective_at"],
                        event["knowledge_at"],
                        event["evidence_cutoff"],
                        event["reviewer_ref"],
                        supersedes_event_id,
                        supersedes_candidate_id,
                        payload_json,
                        _now(),
                    ),
                )
        return {
            "review_event_id": event_id,
            "candidate_id": candidate_id,
            "canonical_hash": canonical_hash,
            "status": "INSERTED",
        }

    def get_behavior_hypothesis_candidate(
        self, candidate_id: str
    ) -> dict[str, Any]:
        self._ensure_p2h_stage1_initialized()
        with self.connection(read_only=True) as conn:
            row = conn.execute(
                "SELECT payload_json FROM behavior_hypothesis_candidates "
                "WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
        if row is None:
            raise ReviewStoreError(
                f"Behavior hypothesis candidate not found: {candidate_id}"
            )
        return json.loads(row["payload_json"])

    def list_behavior_hypothesis_review_events(
        self,
        *,
        candidate_id: str | None = None,
        event_type: str | None = None,
        as_of: str | None = None,
        knowledge_cutoff: str | None = None,
        reviewed_from: str | None = None,
        reviewed_to: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_p2h_stage1_initialized()
        filters: list[str] = []
        params: list[Any] = []
        values = {
            "effective_at": (
                _canonical_timestamp(as_of, "as_of") if as_of is not None else None
            ),
            "knowledge_at": (
                _canonical_timestamp(knowledge_cutoff, "knowledge_cutoff")
                if knowledge_cutoff is not None
                else None
            ),
            "reviewed_from": (
                _canonical_timestamp(reviewed_from, "reviewed_from")
                if reviewed_from is not None
                else None
            ),
            "reviewed_to": (
                _canonical_timestamp(reviewed_to, "reviewed_to")
                if reviewed_to is not None
                else None
            ),
        }
        if candidate_id is not None:
            filters.append("candidate_id = ?")
            params.append(candidate_id)
        if event_type is not None:
            filters.append("event_type = ?")
            params.append(event_type)
        if values["effective_at"] is not None:
            filters.append("effective_at <= ?")
            params.append(values["effective_at"])
        if values["knowledge_at"] is not None:
            filters.append("knowledge_at <= ?")
            params.append(values["knowledge_at"])
        if values["reviewed_from"] is not None:
            filters.append("reviewed_at >= ?")
            params.append(values["reviewed_from"])
        if values["reviewed_to"] is not None:
            filters.append("reviewed_at <= ?")
            params.append(values["reviewed_to"])
        where = " WHERE " + " AND ".join(filters) if filters else ""
        with self.connection(read_only=True) as conn:
            rows = conn.execute(
                "SELECT payload_json FROM behavior_hypothesis_review_events"
                + where
                + " ORDER BY effective_at, knowledge_at, reviewed_at, review_event_id",
                params,
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def list_behavior_hypothesis_candidates(
        self,
        *,
        candidate_id: str | None = None,
        status: str | None = None,
        pattern_family: str | None = None,
        scope_kind: str | None = None,
        scope_ref: str | None = None,
        as_of: str | None = None,
        knowledge_cutoff: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query candidates with strict deterministic event-ledger projection."""

        self._ensure_p2h_stage1_initialized()
        filters: list[str] = []
        params: list[Any] = []
        temporal = {
            "effective_at": (
                _canonical_timestamp(as_of, "as_of") if as_of is not None else None
            ),
            "knowledge_at": (
                _canonical_timestamp(knowledge_cutoff, "knowledge_cutoff")
                if knowledge_cutoff is not None
                else None
            ),
            "created_from": (
                _canonical_timestamp(created_from, "created_from")
                if created_from is not None
                else None
            ),
            "created_to": (
                _canonical_timestamp(created_to, "created_to")
                if created_to is not None
                else None
            ),
        }
        for column, value in (
            ("candidate_id", candidate_id),
            ("pattern_family", pattern_family),
            ("subject_scope_kind", scope_kind),
        ):
            if value is not None:
                filters.append(f"{column} = ?")
                params.append(value)
        if temporal["effective_at"] is not None:
            filters.append("effective_at <= ?")
            params.append(temporal["effective_at"])
        if temporal["knowledge_at"] is not None:
            filters.append("knowledge_at <= ?")
            params.append(temporal["knowledge_at"])
        if temporal["created_from"] is not None:
            filters.append("created_at >= ?")
            params.append(temporal["created_from"])
        if temporal["created_to"] is not None:
            filters.append("created_at <= ?")
            params.append(temporal["created_to"])
        where = " WHERE " + " AND ".join(filters) if filters else ""
        with self.connection(read_only=True) as conn:
            rows = conn.execute(
                "SELECT payload_json FROM behavior_hypothesis_candidates"
                + where
                + " ORDER BY created_at, candidate_id",
                params,
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            candidate = json.loads(row["payload_json"])
            if scope_ref is not None and scope_ref not in candidate["subject_scope"]["refs"]:
                continue
            events = self.list_behavior_hypothesis_review_events(
                candidate_id=candidate["candidate_id"],
                as_of=temporal["effective_at"],
                knowledge_cutoff=temporal["knowledge_at"],
            )
            projection = project_behavior_hypothesis_state(
                candidate,
                events,
                as_of=temporal["effective_at"] or "9999-12-31T23:59:59Z",
                knowledge_cutoff=(
                    temporal["knowledge_at"] or "9999-12-31T23:59:59Z"
                ),
            )
            projected_status = projection["status"]
            if status is not None and status != projected_status:
                continue
            result.append(
                {
                    "candidate": candidate,
                    "projected_status": projected_status,
                    "projection": projection,
                    "visible_review_event_ids": [
                        event["review_event_id"] for event in events
                    ],
                }
            )
        return result

    def project_behavior_hypothesis_candidate(
        self,
        candidate_id: str,
        *,
        as_of: str,
        knowledge_cutoff: str,
    ) -> dict[str, Any]:
        candidate = self.get_behavior_hypothesis_candidate(candidate_id)
        events = self.list_behavior_hypothesis_review_events(
            candidate_id=candidate_id,
            as_of=as_of,
            knowledge_cutoff=knowledge_cutoff,
        )
        return project_behavior_hypothesis_state(
            candidate,
            events,
            as_of=as_of,
            knowledge_cutoff=knowledge_cutoff,
        )

    def replay_behavior_hypothesis_candidate(
        self,
        candidate_id: str,
        *,
        source_artifacts: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        return replay_validate_behavior_hypothesis_candidate(
            self.get_behavior_hypothesis_candidate(candidate_id),
            source_artifacts=source_artifacts,
        )

    def save_observation_protocol(
        self,
        protocol: Mapping[str, Any],
        *,
        candidate_source_artifacts: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Create one source-replayed protocol or idempotently replay it."""

        self._ensure_p2h_stage2_slice_a_initialized()
        protocol_id = str(protocol.get("protocol_id") or "")
        canonical_hash = str(protocol.get("canonical_hash") or "")
        binding = protocol.get("candidate_binding")
        if not isinstance(binding, Mapping):
            raise ReviewStoreError("Observation protocol candidate_binding is required")
        candidate_id = str(binding.get("candidate_id") or "")
        payload_json = self._p2h_payload_json(protocol)
        with self.connection(read_only=True) as conn:
            existing_before_replay = conn.execute(
                "SELECT canonical_hash, payload_json "
                "FROM behavior_observation_protocols WHERE protocol_id = ?",
                (protocol_id,),
            ).fetchone()
        if existing_before_replay is not None and (
            existing_before_replay["canonical_hash"] != canonical_hash
            or existing_before_replay["payload_json"] != payload_json
        ):
            raise DataConflictError(
                "Observation protocol changed after creation: "
                f"protocol_id={protocol_id}"
            )
        candidate = self.get_behavior_hypothesis_candidate(candidate_id)
        complete_events = self.list_behavior_hypothesis_review_events(
            candidate_id=candidate_id
        )
        validation = replay_validate_observation_protocol(
            protocol,
            candidate=candidate,
            review_events=complete_events,
            candidate_source_artifacts=candidate_source_artifacts,
        )
        if (
            validation["validation_status"] != "accepted"
            or validation["source_verification"]["status"] != "verified"
        ):
            raise ReviewStoreError(
                "Observation protocol failed Stage 1 source replay: "
                + ", ".join(validation["finding_codes"])
            )

        accepted_projection = binding["accepted_projection"]
        with self.connection() as conn:
            with conn:
                existing = conn.execute(
                    "SELECT canonical_hash, payload_json "
                    "FROM behavior_observation_protocols WHERE protocol_id = ?",
                    (protocol_id,),
                ).fetchone()
                if existing is not None:
                    if (
                        existing["canonical_hash"] == canonical_hash
                        and existing["payload_json"] == payload_json
                    ):
                        return {
                            "protocol_id": protocol_id,
                            "candidate_id": candidate_id,
                            "canonical_hash": canonical_hash,
                            "status": "SKIPPED",
                            "source_verification": "verified",
                        }
                    raise DataConflictError(
                        "Observation protocol changed after creation: "
                        f"protocol_id={protocol_id}"
                    )
                hash_owner = conn.execute(
                    "SELECT protocol_id FROM behavior_observation_protocols "
                    "WHERE canonical_hash = ?",
                    (canonical_hash,),
                ).fetchone()
                if hash_owner is not None:
                    raise DataConflictError(
                        "Observation protocol canonical hash already belongs to "
                        f"protocol_id={hash_owner['protocol_id']}"
                    )
                conn.execute(
                    """
                    INSERT INTO behavior_observation_protocols(
                        protocol_id, canonical_hash, candidate_id, created_at,
                        effective_at, knowledge_at, expiry_at,
                        stage1_event_set_hash, stage1_projection_hash,
                        source_verification_status, payload_json, inserted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'verified', ?, ?)
                    """,
                    (
                        protocol_id,
                        canonical_hash,
                        candidate_id,
                        protocol["created_at"],
                        protocol["effective_at"],
                        protocol["knowledge_at"],
                        protocol["expiry_at"],
                        binding["review_event_set_hash"],
                        accepted_projection["projection_hash"],
                        payload_json,
                        _now(),
                    ),
                )
        return {
            "protocol_id": protocol_id,
            "candidate_id": candidate_id,
            "canonical_hash": canonical_hash,
            "status": "INSERTED",
            "source_verification": "verified",
        }

    def get_observation_protocol(self, protocol_id: str) -> dict[str, Any]:
        self._ensure_p2h_stage2_slice_a_initialized()
        with self.connection(read_only=True) as conn:
            row = conn.execute(
                "SELECT payload_json FROM behavior_observation_protocols "
                "WHERE protocol_id = ?",
                (protocol_id,),
            ).fetchone()
        if row is None:
            raise ReviewStoreError(f"Observation protocol not found: {protocol_id}")
        return json.loads(row["payload_json"])

    def list_observation_protocols(
        self,
        *,
        protocol_id: str | None = None,
        candidate_id: str | None = None,
        status: str | None = None,
        as_of: str | None = None,
        knowledge_cutoff: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_p2h_stage2_slice_a_initialized()
        filters: list[str] = []
        params: list[Any] = []
        for column, value in (
            ("protocol_id", protocol_id),
            ("candidate_id", candidate_id),
        ):
            if value is not None:
                filters.append(f"{column} = ?")
                params.append(value)
        normalized_as_of = (
            _canonical_timestamp(as_of, "as_of") if as_of is not None else None
        )
        normalized_cutoff = (
            _canonical_timestamp(knowledge_cutoff, "knowledge_cutoff")
            if knowledge_cutoff is not None
            else None
        )
        if normalized_as_of is not None:
            filters.append("effective_at <= ?")
            params.append(normalized_as_of)
        if normalized_cutoff is not None:
            filters.append("knowledge_at <= ?")
            params.append(normalized_cutoff)
        if created_from is not None:
            filters.append("created_at >= ?")
            params.append(_canonical_timestamp(created_from, "created_from"))
        if created_to is not None:
            filters.append("created_at <= ?")
            params.append(_canonical_timestamp(created_to, "created_to"))
        where = " WHERE " + " AND ".join(filters) if filters else ""
        with self.connection(read_only=True) as conn:
            rows = conn.execute(
                "SELECT payload_json FROM behavior_observation_protocols"
                + where
                + " ORDER BY created_at, protocol_id",
                params,
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            protocol = json.loads(row["payload_json"])
            events = self.list_observation_protocol_review_events(
                protocol_id=protocol["protocol_id"],
                as_of=normalized_as_of,
                knowledge_cutoff=normalized_cutoff,
            )
            projection = project_observation_protocol_state(
                protocol,
                events,
                as_of=normalized_as_of or "9999-12-31T23:59:59Z",
                knowledge_cutoff=normalized_cutoff or "9999-12-31T23:59:59Z",
            )
            if status is not None and projection["status"] != status:
                continue
            result.append(
                {
                    "protocol": protocol,
                    "projected_status": projection["status"],
                    "projection": projection,
                    "visible_review_event_ids": [
                        event["protocol_review_event_id"] for event in events
                    ],
                }
            )
        return result

    def save_observation_protocol_review_event(
        self, event: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Create one immutable human protocol-lifecycle event."""

        self._ensure_p2h_stage2_slice_a_initialized()
        event_id = str(event.get("protocol_review_event_id") or "")
        canonical_hash = str(event.get("canonical_hash") or "")
        protocol_id = str(event.get("protocol_id") or "")
        payload_json = self._p2h_payload_json(event)
        with self.connection(read_only=True) as conn:
            existing_before_validation = conn.execute(
                "SELECT canonical_hash, payload_json "
                "FROM behavior_observation_protocol_review_events "
                "WHERE protocol_review_event_id = ?",
                (event_id,),
            ).fetchone()
        if existing_before_validation is not None and (
            existing_before_validation["canonical_hash"] != canonical_hash
            or existing_before_validation["payload_json"] != payload_json
        ):
            raise DataConflictError(
                "Observation protocol review event changed after creation: "
                f"protocol_review_event_id={event_id}"
            )
        validation = validate_observation_protocol_review_event(event)
        if validation["validation_status"] != "accepted":
            raise ReviewStoreError(
                "Observation protocol review event failed validation: "
                + ", ".join(validation["finding_codes"])
            )
        with self.connection() as conn:
            with conn:
                existing = conn.execute(
                    "SELECT canonical_hash, payload_json "
                    "FROM behavior_observation_protocol_review_events "
                    "WHERE protocol_review_event_id = ?",
                    (event_id,),
                ).fetchone()
                if existing is not None:
                    if (
                        existing["canonical_hash"] == canonical_hash
                        and existing["payload_json"] == payload_json
                    ):
                        return {
                            "protocol_review_event_id": event_id,
                            "protocol_id": protocol_id,
                            "canonical_hash": canonical_hash,
                            "status": "SKIPPED",
                        }
                    raise DataConflictError(
                        "Observation protocol review event changed after creation: "
                        f"protocol_review_event_id={event_id}"
                    )
                protocol_row = conn.execute(
                    "SELECT effective_at, knowledge_at "
                    "FROM behavior_observation_protocols WHERE protocol_id = ?",
                    (protocol_id,),
                ).fetchone()
                if protocol_row is None:
                    raise ReviewStoreError(
                        f"Observation protocol not found: {protocol_id}"
                    )
                if event["effective_at"] < protocol_row["effective_at"]:
                    raise ReviewStoreError(
                        "Protocol event effective_at cannot precede the protocol"
                    )
                if event["knowledge_at"] < protocol_row["knowledge_at"]:
                    raise ReviewStoreError(
                        "Protocol event knowledge_at cannot precede the protocol"
                    )
                if event["event_type"] != "note_added":
                    concurrent = conn.execute(
                        "SELECT protocol_review_event_id "
                        "FROM behavior_observation_protocol_review_events "
                        "WHERE protocol_id = ? AND event_type != 'note_added' "
                        "AND effective_at = ? AND knowledge_at = ? AND reviewed_at = ?",
                        (
                            protocol_id,
                            event["effective_at"],
                            event["knowledge_at"],
                            event["reviewed_at"],
                        ),
                    ).fetchone()
                    if concurrent is not None:
                        raise ReviewStoreError(
                            "CONCURRENT_PROTOCOL_STATE_EVENTS: another state event "
                            "already uses the same semantic time"
                        )
                supersedes_event_id = event.get("supersedes_event_id")
                if supersedes_event_id is not None:
                    prior = conn.execute(
                        "SELECT protocol_id "
                        "FROM behavior_observation_protocol_review_events "
                        "WHERE protocol_review_event_id = ?",
                        (supersedes_event_id,),
                    ).fetchone()
                    if prior is None or prior["protocol_id"] != protocol_id:
                        raise ReviewStoreError(
                            "Superseded protocol event is missing or belongs to "
                            "another protocol"
                        )
                replacement_id = event.get("superseded_by_protocol_id")
                if replacement_id is not None:
                    replacement = conn.execute(
                        "SELECT 1 FROM behavior_observation_protocols "
                        "WHERE protocol_id = ?",
                        (replacement_id,),
                    ).fetchone()
                    if replacement is None:
                        raise ReviewStoreError(
                            "Replacement observation protocol not found: "
                            f"{replacement_id}"
                        )
                hash_owner = conn.execute(
                    "SELECT protocol_review_event_id "
                    "FROM behavior_observation_protocol_review_events "
                    "WHERE canonical_hash = ?",
                    (canonical_hash,),
                ).fetchone()
                if hash_owner is not None:
                    raise DataConflictError(
                        "Observation protocol event canonical hash already belongs to "
                        f"protocol_review_event_id={hash_owner['protocol_review_event_id']}"
                    )
                conn.execute(
                    """
                    INSERT INTO behavior_observation_protocol_review_events(
                        protocol_review_event_id, canonical_hash, protocol_id,
                        event_type, reviewed_at, effective_at, knowledge_at,
                        evidence_cutoff, reviewer_ref, supersedes_event_id,
                        superseded_by_protocol_id, payload_json, inserted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        canonical_hash,
                        protocol_id,
                        event["event_type"],
                        event["reviewed_at"],
                        event["effective_at"],
                        event["knowledge_at"],
                        event["evidence_cutoff"],
                        event["reviewer_ref"],
                        supersedes_event_id,
                        replacement_id,
                        payload_json,
                        _now(),
                    ),
                )
        return {
            "protocol_review_event_id": event_id,
            "protocol_id": protocol_id,
            "canonical_hash": canonical_hash,
            "status": "INSERTED",
        }

    def list_observation_protocol_review_events(
        self,
        *,
        protocol_id: str | None = None,
        event_type: str | None = None,
        as_of: str | None = None,
        knowledge_cutoff: str | None = None,
        reviewed_from: str | None = None,
        reviewed_to: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_p2h_stage2_slice_a_initialized()
        filters: list[str] = []
        params: list[Any] = []
        values = {
            "effective_at": (
                _canonical_timestamp(as_of, "as_of") if as_of is not None else None
            ),
            "knowledge_at": (
                _canonical_timestamp(knowledge_cutoff, "knowledge_cutoff")
                if knowledge_cutoff is not None
                else None
            ),
            "reviewed_from": (
                _canonical_timestamp(reviewed_from, "reviewed_from")
                if reviewed_from is not None
                else None
            ),
            "reviewed_to": (
                _canonical_timestamp(reviewed_to, "reviewed_to")
                if reviewed_to is not None
                else None
            ),
        }
        if protocol_id is not None:
            filters.append("protocol_id = ?")
            params.append(protocol_id)
        if event_type is not None:
            filters.append("event_type = ?")
            params.append(event_type)
        if values["effective_at"] is not None:
            filters.append("effective_at <= ?")
            params.append(values["effective_at"])
        if values["knowledge_at"] is not None:
            filters.append("knowledge_at <= ?")
            params.append(values["knowledge_at"])
        if values["reviewed_from"] is not None:
            filters.append("reviewed_at >= ?")
            params.append(values["reviewed_from"])
        if values["reviewed_to"] is not None:
            filters.append("reviewed_at <= ?")
            params.append(values["reviewed_to"])
        where = " WHERE " + " AND ".join(filters) if filters else ""
        with self.connection(read_only=True) as conn:
            rows = conn.execute(
                "SELECT payload_json "
                "FROM behavior_observation_protocol_review_events"
                + where
                + " ORDER BY effective_at, knowledge_at, reviewed_at, "
                "protocol_review_event_id",
                params,
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def project_observation_protocol(
        self,
        protocol_id: str,
        *,
        as_of: str,
        knowledge_cutoff: str,
    ) -> dict[str, Any]:
        protocol = self.get_observation_protocol(protocol_id)
        events = self.list_observation_protocol_review_events(
            protocol_id=protocol_id,
            as_of=as_of,
            knowledge_cutoff=knowledge_cutoff,
        )
        return project_observation_protocol_state(
            protocol,
            events,
            as_of=as_of,
            knowledge_cutoff=knowledge_cutoff,
        )

    def replay_observation_protocol(
        self,
        protocol_id: str,
        *,
        candidate_source_artifacts: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        protocol = self.get_observation_protocol(protocol_id)
        candidate_id = protocol["candidate_binding"]["candidate_id"]
        return replay_validate_observation_protocol(
            protocol,
            candidate=self.get_behavior_hypothesis_candidate(candidate_id),
            review_events=self.list_behavior_hypothesis_review_events(
                candidate_id=candidate_id
            ),
            candidate_source_artifacts=candidate_source_artifacts,
        )

    def status(self) -> dict[str, Any]:
        self._ensure_initialized()
        with self.connection(read_only=True) as conn:
            counts = {
                table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "data_sources",
                    "source_config_versions",
                    "ingest_runs",
                    "ingest_run_events",
                    "trade_events",
                    "decisions",
                    "decision_event_links",
                    "portfolio_snapshots",
                    "position_snapshot_items",
                    "behavior_hypothesis_candidates",
                    "behavior_hypothesis_review_events",
                    "behavior_observation_protocols",
                    "behavior_observation_protocol_review_events",
                )
            }
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            version_row = conn.execute(
                "SELECT value FROM schema_meta WHERE key='schema_version'"
            ).fetchone()
            p2h_row = conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key='p2h_stage1_schema_version'"
            ).fetchone()
            p2h_stage2_row = conn.execute(
                "SELECT value FROM schema_meta "
                "WHERE key='p2h_stage2_slice_a_schema_version'"
            ).fetchone()
        return {
            "database": str(self.path),
            "schema_version": int(version_row[0]) if version_row else None,
            "p2h_stage1_schema_version": int(p2h_row[0]) if p2h_row else None,
            "p2h_stage2_slice_a_schema_version": (
                int(p2h_stage2_row[0]) if p2h_stage2_row else None
            ),
            "integrity_check": integrity,
            "counts": counts,
        }
