"""Separate SQLite store for normalized review data."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

from .models import CanonicalTradeEvent, DecisionRecord, SourceDefinition, canonical_json


SCHEMA_VERSION = 2
APPLICATION_ID = 0x49525657  # ASCII "IRVW"

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
                )
            }
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            version_row = conn.execute(
                "SELECT value FROM schema_meta WHERE key='schema_version'"
            ).fetchone()
        return {
            "database": str(self.path),
            "schema_version": int(version_row[0]) if version_row else None,
            "integrity_check": integrity,
            "counts": counts,
        }
