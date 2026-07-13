from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

from .accounting import AccountingError, build_closed_position_cycles, build_position_states
from .models import (
    ClosePrice,
    IndustryClassification,
    Instrument,
    LedgerEntry,
    PositionState,
    ZERO,
    decimal_to_text,
)


SCHEMA_VERSION = "2"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_currency TEXT NOT NULL DEFAULT 'CNY',
    baseline_date TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS instruments (
    ts_code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    asset_type TEXT NOT NULL CHECK (asset_type IN ('equity', 'etf', 'unknown')),
    exchange TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'CNY',
    industry_name TEXT NOT NULL DEFAULT '',
    industry_source TEXT NOT NULL DEFAULT '',
    industry_updated_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_batches (
    batch_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    import_kind TEXT NOT NULL,
    broker TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    total_rows INTEGER NOT NULL,
    accepted_rows INTEGER NOT NULL,
    duplicate_rows INTEGER NOT NULL,
    skipped_rows INTEGER NOT NULL,
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ledger_entries (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    event_date TEXT NOT NULL,
    event_time TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL CHECK (
        event_type IN ('OPENING', 'BUY', 'SELL', 'DIVIDEND', 'CASH_FEE')
    ),
    ts_code TEXT NOT NULL REFERENCES instruments(ts_code),
    quantity TEXT NOT NULL DEFAULT '0',
    price TEXT NOT NULL DEFAULT '0',
    gross_amount TEXT NOT NULL DEFAULT '0',
    fees TEXT NOT NULL DEFAULT '0',
    total_cost TEXT NOT NULL DEFAULT '0',
    cash_amount TEXT NOT NULL DEFAULT '0',
    external_id TEXT NOT NULL DEFAULT '',
    dedupe_key TEXT NOT NULL,
    import_batch_id TEXT REFERENCES import_batches(batch_id),
    source_row INTEGER,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(account_id, dedupe_key)
);

CREATE INDEX IF NOT EXISTS idx_ledger_account_date
ON ledger_entries(account_id, event_date, event_time, entry_id);

CREATE TABLE IF NOT EXISTS statement_observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    event_date TEXT NOT NULL,
    event_time TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    ts_code TEXT NOT NULL REFERENCES instruments(ts_code),
    quantity TEXT NOT NULL DEFAULT '0',
    price TEXT NOT NULL DEFAULT '0',
    gross_amount TEXT NOT NULL DEFAULT '0',
    fees TEXT NOT NULL DEFAULT '0',
    cash_amount TEXT NOT NULL DEFAULT '0',
    external_id TEXT NOT NULL DEFAULT '',
    dedupe_key TEXT NOT NULL,
    disposition TEXT NOT NULL CHECK (disposition IN ('included_in_opening')),
    baseline_date TEXT NOT NULL,
    import_batch_id TEXT NOT NULL REFERENCES import_batches(batch_id),
    source_row INTEGER,
    note TEXT NOT NULL DEFAULT '',
    recorded_at TEXT NOT NULL,
    UNIQUE(account_id, dedupe_key, disposition)
);

CREATE INDEX IF NOT EXISTS idx_statement_observations_account_date
ON statement_observations(account_id, event_date, event_time, observation_id);

CREATE TABLE IF NOT EXISTS close_prices (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL REFERENCES instruments(ts_code),
    trade_date TEXT NOT NULL,
    close TEXT NOT NULL,
    pre_close TEXT NOT NULL DEFAULT '',
    pct_chg TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    UNIQUE(ts_code, trade_date, close, pre_close, pct_chg, source)
);

CREATE INDEX IF NOT EXISTS idx_close_prices_code_date
ON close_prices(ts_code, trade_date DESC, fetched_at DESC, observation_id DESC);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PortfolioStore:
    def __init__(self, path: str | Path = "data/db/portfolio.sqlite3") -> None:
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self, account_id: str = "default", account_name: str = "默认账户") -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)
            connection.execute(
                "INSERT OR IGNORE INTO metadata(key, value) VALUES ('schema_version', ?)",
                (SCHEMA_VERSION,),
            )
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()
            if row is not None and row["value"] == "1":
                columns = {
                    item["name"]
                    for item in connection.execute("PRAGMA table_info(instruments)")
                }
                migrations = {
                    "industry_name": "TEXT NOT NULL DEFAULT ''",
                    "industry_source": "TEXT NOT NULL DEFAULT ''",
                    "industry_updated_at": "TEXT NOT NULL DEFAULT ''",
                }
                for column_name, column_definition in migrations.items():
                    if column_name not in columns:
                        connection.execute(
                            f"ALTER TABLE instruments ADD COLUMN {column_name} {column_definition}"
                        )
                connection.execute(
                    "UPDATE metadata SET value = ? WHERE key = 'schema_version'",
                    (SCHEMA_VERSION,),
                )
                row = connection.execute(
                    "SELECT value FROM metadata WHERE key = 'schema_version'"
                ).fetchone()
            if row is None or row["value"] != SCHEMA_VERSION:
                raise RuntimeError(
                    f"不支持的持仓数据库版本: {None if row is None else row['value']}"
                )
            connection.execute(
                """
                INSERT OR IGNORE INTO accounts(account_id, name, base_currency, created_at)
                VALUES (?, ?, 'CNY', ?)
                """,
                (account_id, account_name, now),
            )
            connection.commit()

    def account(self, account_id: str) -> sqlite3.Row:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM accounts WHERE account_id = ?", (account_id,)
            ).fetchone()
        if row is None:
            raise ValueError(f"账户不存在: {account_id}")
        return row

    def baseline_date(self, account_id: str) -> date | None:
        value = self.account(account_id)["baseline_date"]
        return date.fromisoformat(value) if value else None

    @staticmethod
    def _upsert_instruments(
        connection: sqlite3.Connection, instruments: Iterable[Instrument]
    ) -> None:
        now = utc_now()
        for item in instruments:
            connection.execute(
                """
                INSERT INTO instruments(ts_code, name, asset_type, exchange, currency, updated_at)
                VALUES (?, ?, ?, ?, 'CNY', ?)
                ON CONFLICT(ts_code) DO UPDATE SET
                    name = CASE
                        WHEN excluded.name <> '' AND excluded.name <> excluded.ts_code THEN excluded.name
                        ELSE instruments.name
                    END,
                    asset_type = CASE
                        WHEN instruments.asset_type = 'unknown' THEN excluded.asset_type
                        ELSE instruments.asset_type
                    END,
                    updated_at = excluded.updated_at
                """,
                (item.ts_code, item.name, item.asset_type, item.exchange, now),
            )

    @staticmethod
    def _insert_entries(
        connection: sqlite3.Connection,
        entries: Iterable[LedgerEntry],
        batch_id: str,
    ) -> tuple[int, int]:
        inserted = 0
        duplicates = 0
        now = utc_now()
        for item in entries:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO ledger_entries(
                    account_id, event_date, event_time, event_type, ts_code,
                    quantity, price, gross_amount, fees, total_cost, cash_amount,
                    external_id, dedupe_key, import_batch_id, source_row, note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.account_id,
                    item.event_date.isoformat(),
                    item.event_time,
                    item.event_type,
                    item.ts_code,
                    decimal_to_text(item.quantity),
                    decimal_to_text(item.price),
                    decimal_to_text(item.gross_amount),
                    decimal_to_text(item.fees),
                    decimal_to_text(item.total_cost),
                    decimal_to_text(item.cash_amount),
                    item.external_id,
                    item.dedupe_key,
                    batch_id,
                    item.source_row,
                    item.note,
                    now,
                ),
            )
            if cursor.rowcount == 1:
                inserted += 1
            else:
                duplicates += 1
        return inserted, duplicates

    @staticmethod
    def _insert_prices(
        connection: sqlite3.Connection, prices: Iterable[ClosePrice]
    ) -> int:
        inserted = 0
        now = utc_now()
        for item in prices:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO close_prices(
                    ts_code, trade_date, close, pre_close, pct_chg, source, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.ts_code,
                    item.trade_date.isoformat(),
                    decimal_to_text(item.close),
                    decimal_to_text(item.pre_close) or "",
                    decimal_to_text(item.pct_chg) or "",
                    item.source,
                    item.fetched_at or now,
                ),
            )
            inserted += int(cursor.rowcount == 1)
        return inserted

    @staticmethod
    def _ordered_ledger(
        connection: sqlite3.Connection, account_id: str, as_of: date | None = None
    ) -> list[sqlite3.Row]:
        params: list[Any] = [account_id]
        date_filter = ""
        if as_of is not None:
            date_filter = "AND event_date <= ?"
            params.append(as_of.isoformat())
        return list(
            connection.execute(
                f"""
                SELECT * FROM ledger_entries
                WHERE account_id = ? {date_filter}
                ORDER BY event_date,
                    CASE WHEN event_time = '' THEN '99:99:99' ELSE event_time END,
                    entry_id
                """,
                params,
            )
        )

    @staticmethod
    def _insert_batch(
        connection: sqlite3.Connection,
        *,
        batch_id: str,
        account_id: str,
        import_kind: str,
        broker: str,
        source_name: str,
        source_sha256: str,
        total_rows: int,
        accepted_rows: int,
        duplicate_rows: int,
        skipped_rows: int,
    ) -> None:
        connection.execute(
            """
            INSERT INTO import_batches(
                batch_id, account_id, import_kind, broker, source_name, source_sha256,
                total_rows, accepted_rows, duplicate_rows, skipped_rows, imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch_id,
                account_id,
                import_kind,
                broker,
                source_name,
                source_sha256,
                total_rows,
                accepted_rows,
                duplicate_rows,
                skipped_rows,
                utc_now(),
            ),
        )

    def apply_opening_snapshot(
        self,
        *,
        account_id: str,
        instruments: Iterable[Instrument],
        entries: list[LedgerEntry],
        prices: list[ClosePrice],
        source_name: str,
        source_sha256: str,
        total_rows: int,
    ) -> dict[str, Any]:
        if not entries:
            raise ValueError("期初快照没有可导入的持仓")
        dates = {item.event_date for item in entries}
        if len(dates) != 1 or any(item.event_type != "OPENING" for item in entries):
            raise ValueError("一次期初快照只能包含同一日期的 OPENING 记录")
        baseline = next(iter(dates))
        batch_id = f"opening_{uuid.uuid4().hex}"

        with self.connect() as connection:
            account = connection.execute(
                "SELECT * FROM accounts WHERE account_id = ?", (account_id,)
            ).fetchone()
            if account is None:
                raise ValueError(f"账户不存在: {account_id}")
            existing_baseline = account["baseline_date"]
            if existing_baseline and existing_baseline != baseline.isoformat():
                raise ValueError(
                    f"账户期初基准日已是 {existing_baseline}，不能再导入 {baseline.isoformat()}"
                )
            non_opening = connection.execute(
                """
                SELECT COUNT(*) AS count FROM ledger_entries
                WHERE account_id = ? AND event_type <> 'OPENING'
                """,
                (account_id,),
            ).fetchone()["count"]
            if non_opening:
                raise ValueError("账户已有基准日后流水，不能追加期初快照")

            self._upsert_instruments(connection, instruments)
            self._insert_batch(
                connection,
                batch_id=batch_id,
                account_id=account_id,
                import_kind="opening_snapshot",
                broker="manual_snapshot",
                source_name=source_name,
                source_sha256=source_sha256,
                total_rows=total_rows,
                accepted_rows=0,
                duplicate_rows=0,
                skipped_rows=0,
            )
            inserted, duplicates = self._insert_entries(connection, entries, batch_id)
            price_rows = self._insert_prices(connection, prices)
            build_position_states(self._ordered_ledger(connection, account_id))
            connection.execute(
                "UPDATE accounts SET baseline_date = ? WHERE account_id = ?",
                (baseline.isoformat(), account_id),
            )
            connection.execute(
                """
                UPDATE import_batches
                SET accepted_rows = ?, duplicate_rows = ?
                WHERE batch_id = ?
                """,
                (inserted, duplicates, batch_id),
            )
            connection.commit()
        return {
            "batch_id": batch_id,
            "baseline_date": baseline.isoformat(),
            "inserted_entries": inserted,
            "duplicate_entries": duplicates,
            "inserted_prices": price_rows,
        }

    def preview_statement(
        self, account_id: str, entries: list[LedgerEntry]
    ) -> dict[str, Any]:
        baseline = self.baseline_date(account_id)
        if baseline is not None:
            invalid = [item for item in entries if item.event_date <= baseline]
            if invalid:
                first = invalid[0]
                raise ValueError(
                    f"第 {first.source_row or '?'} 行日期 {first.event_date.isoformat()} 不晚于期初基准日 "
                    f"{baseline.isoformat()}；导入会重复计算"
                )

        with self.connect() as connection:
            existing_keys = {
                row["dedupe_key"]
                for row in connection.execute(
                    "SELECT dedupe_key FROM ledger_entries WHERE account_id = ?",
                    (account_id,),
                )
            }
            seen_keys = set(existing_keys)
            unique_entries: list[LedgerEntry] = []
            for item in entries:
                if item.dedupe_key not in seen_keys:
                    unique_entries.append(item)
                    seen_keys.add(item.dedupe_key)
            rows: list[Mapping[str, Any]] = list(self._ordered_ledger(connection, account_id))
            rows.extend(
                {
                    "event_date": item.event_date.isoformat(),
                    "event_time": item.event_time,
                    "event_type": item.event_type,
                    "ts_code": item.ts_code,
                    "quantity": decimal_to_text(item.quantity),
                    "price": decimal_to_text(item.price),
                    "gross_amount": decimal_to_text(item.gross_amount),
                    "fees": decimal_to_text(item.fees),
                    "total_cost": decimal_to_text(item.total_cost),
                    "cash_amount": decimal_to_text(item.cash_amount),
                    "source_row": item.source_row or 0,
                }
                for item in unique_entries
            )
        rows.sort(
            key=lambda row: (
                str(row["event_date"]),
                str(row.get("event_time", "") if isinstance(row, dict) else row["event_time"])
                or "99:99:99",
                int(row.get("source_row", 0) if isinstance(row, dict) else row["entry_id"]),
            )
        )
        build_position_states(rows)
        return {
            "accepted_entries": len(unique_entries),
            "duplicate_entries": len(entries) - len(unique_entries),
        }

    def apply_statement(
        self,
        *,
        account_id: str,
        instruments: Iterable[Instrument],
        entries: list[LedgerEntry],
        broker: str,
        source_name: str,
        source_sha256: str,
        total_rows: int,
        skipped_rows: int,
    ) -> dict[str, Any]:
        preview = self.preview_statement(account_id, entries)
        batch_id = f"statement_{uuid.uuid4().hex}"
        with self.connect() as connection:
            self._upsert_instruments(connection, instruments)
            self._insert_batch(
                connection,
                batch_id=batch_id,
                account_id=account_id,
                import_kind="broker_statement",
                broker=broker,
                source_name=source_name,
                source_sha256=source_sha256,
                total_rows=total_rows,
                accepted_rows=0,
                duplicate_rows=0,
                skipped_rows=skipped_rows,
            )
            inserted, duplicates = self._insert_entries(connection, entries, batch_id)
            build_position_states(self._ordered_ledger(connection, account_id))
            connection.execute(
                """
                UPDATE import_batches
                SET accepted_rows = ?, duplicate_rows = ?
                WHERE batch_id = ?
                """,
                (inserted, duplicates, batch_id),
            )
            connection.commit()
        return {
            "batch_id": batch_id,
            "inserted_entries": inserted,
            "duplicate_entries": duplicates,
            "preview": preview,
        }

    def preview_included_statement(
        self, account_id: str, entries: list[LedgerEntry]
    ) -> dict[str, Any]:
        baseline = self.baseline_date(account_id)
        if baseline is None:
            raise ValueError("账户还没有期初快照，不能标记为已包含")
        later = [item for item in entries if item.event_date > baseline]
        if later:
            first = later[0]
            raise ValueError(
                f"第 {first.source_row or '?'} 行日期 {first.event_date.isoformat()} 晚于期初基准日 "
                f"{baseline.isoformat()}，应作为真实台账流水导入"
            )
        with self.connect() as connection:
            existing = {
                row["dedupe_key"]
                for row in connection.execute(
                    """
                    SELECT dedupe_key FROM statement_observations
                    WHERE account_id = ? AND disposition = 'included_in_opening'
                    """,
                    (account_id,),
                )
            }
        seen = set(existing)
        accepted = 0
        duplicates = 0
        for item in entries:
            if item.dedupe_key in seen:
                duplicates += 1
            else:
                accepted += 1
                seen.add(item.dedupe_key)
        return {
            "baseline_date": baseline.isoformat(),
            "accepted_entries": accepted,
            "duplicate_entries": duplicates,
        }

    def record_included_statement(
        self,
        *,
        account_id: str,
        instruments: Iterable[Instrument],
        entries: list[LedgerEntry],
        broker: str,
        source_name: str,
        source_sha256: str,
        total_rows: int,
        skipped_rows: int,
    ) -> dict[str, Any]:
        preview = self.preview_included_statement(account_id, entries)
        baseline = preview["baseline_date"]
        batch_id = f"reconciliation_{uuid.uuid4().hex}"
        now = utc_now()
        with self.connect() as connection:
            self._upsert_instruments(connection, instruments)
            self._insert_batch(
                connection,
                batch_id=batch_id,
                account_id=account_id,
                import_kind="statement_reconciliation",
                broker=broker,
                source_name=source_name,
                source_sha256=source_sha256,
                total_rows=total_rows,
                accepted_rows=0,
                duplicate_rows=0,
                skipped_rows=skipped_rows,
            )
            inserted = 0
            duplicates = 0
            for item in entries:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO statement_observations(
                        account_id, event_date, event_time, event_type, ts_code,
                        quantity, price, gross_amount, fees, cash_amount, external_id,
                        dedupe_key, disposition, baseline_date, import_batch_id,
                        source_row, note, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        'included_in_opening', ?, ?, ?, ?, ?)
                    """,
                    (
                        item.account_id,
                        item.event_date.isoformat(),
                        item.event_time,
                        item.event_type,
                        item.ts_code,
                        decimal_to_text(item.quantity),
                        decimal_to_text(item.price),
                        decimal_to_text(item.gross_amount),
                        decimal_to_text(item.fees),
                        decimal_to_text(item.cash_amount),
                        item.external_id,
                        item.dedupe_key,
                        baseline,
                        batch_id,
                        item.source_row,
                        item.note + "; disposition=included_in_opening",
                        now,
                    ),
                )
                if cursor.rowcount == 1:
                    inserted += 1
                else:
                    duplicates += 1
            connection.execute(
                """
                UPDATE import_batches SET accepted_rows = ?, duplicate_rows = ?
                WHERE batch_id = ?
                """,
                (inserted, duplicates, batch_id),
            )
            connection.commit()
        return {
            "batch_id": batch_id,
            "disposition": "included_in_opening",
            "baseline_date": baseline,
            "recorded_entries": inserted,
            "duplicate_entries": duplicates,
        }

    def add_close_prices(self, prices: Iterable[ClosePrice]) -> int:
        price_list = list(prices)
        with self.connect() as connection:
            missing = []
            for item in price_list:
                exists = connection.execute(
                    "SELECT 1 FROM instruments WHERE ts_code = ?", (item.ts_code,)
                ).fetchone()
                if exists is None:
                    missing.append(item.ts_code)
            if missing:
                raise ValueError(f"行情包含未登记证券: {', '.join(sorted(set(missing)))}")
            inserted = self._insert_prices(connection, price_list)
            connection.commit()
        return inserted

    def set_industries(
        self, classifications: Iterable[IndustryClassification]
    ) -> int:
        items = list(classifications)
        with self.connect() as connection:
            known_codes = {
                row["ts_code"]
                for row in connection.execute("SELECT ts_code FROM instruments")
            }
            missing = sorted({item.ts_code for item in items if item.ts_code not in known_codes})
            if missing:
                raise ValueError(f"行业分类包含未登记证券: {', '.join(missing)}")
            updated = 0
            for item in items:
                classified_at = item.classified_at or utc_now()
                cursor = connection.execute(
                    """
                    UPDATE instruments
                    SET industry_name = ?, industry_source = ?, industry_updated_at = ?
                    WHERE ts_code = ? AND (
                        industry_name <> ? OR industry_source <> ?
                    )
                    """,
                    (
                        item.industry_name,
                        item.source,
                        classified_at,
                        item.ts_code,
                        item.industry_name,
                        item.source,
                    ),
                )
                updated += cursor.rowcount
            connection.commit()
        return updated

    def ledger(self, account_id: str, as_of: date | None = None) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return self._ordered_ledger(connection, account_id, as_of)

    def instruments_for_open_positions(
        self, account_id: str, as_of: date | None = None
    ) -> list[Instrument]:
        rows = self.ledger(account_id, as_of)
        states = build_position_states(rows)
        open_codes = [code for code, state in states.items() if state.quantity > ZERO]
        if not open_codes:
            return []
        placeholders = ",".join("?" for _ in open_codes)
        with self.connect() as connection:
            instrument_rows = {
                row["ts_code"]: row
                for row in connection.execute(
                    f"SELECT * FROM instruments WHERE ts_code IN ({placeholders})", open_codes
                )
            }
        return [
            Instrument(
                ts_code=code,
                name=instrument_rows[code]["name"],
                asset_type=instrument_rows[code]["asset_type"],
            )
            for code in open_codes
        ]

    @staticmethod
    def _latest_price(
        connection: sqlite3.Connection, ts_code: str, as_of: date | None
    ) -> sqlite3.Row | None:
        if as_of is None:
            return connection.execute(
                """
                SELECT * FROM close_prices WHERE ts_code = ?
                ORDER BY trade_date DESC, fetched_at DESC, observation_id DESC LIMIT 1
                """,
                (ts_code,),
            ).fetchone()
        return connection.execute(
            """
            SELECT * FROM close_prices WHERE ts_code = ? AND trade_date <= ?
            ORDER BY trade_date DESC, fetched_at DESC, observation_id DESC LIMIT 1
            """,
            (ts_code, as_of.isoformat()),
        ).fetchone()

    def position_report(
        self, account_id: str, as_of: date | None = None
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        ledger = self.ledger(account_id, as_of)
        states = build_position_states(ledger)
        result: list[dict[str, Any]] = []
        with self.connect() as connection:
            for ts_code, state in states.items():
                if state.quantity <= ZERO:
                    continue
                instrument = connection.execute(
                    "SELECT * FROM instruments WHERE ts_code = ?", (ts_code,)
                ).fetchone()
                quote = self._latest_price(connection, ts_code, as_of)
                close = Decimal(quote["close"]) if quote is not None else None
                market_value = close * state.quantity if close is not None else None
                unrealized = (
                    market_value - state.remaining_cost if market_value is not None else None
                )
                return_pct = (
                    unrealized / state.remaining_cost * Decimal("100")
                    if unrealized is not None and state.remaining_cost != ZERO
                    else None
                )
                result.append(
                    {
                        "ts_code": ts_code,
                        "name": instrument["name"] if instrument else ts_code,
                        "asset_type": instrument["asset_type"] if instrument else "unknown",
                        "industry_name": (
                            instrument["industry_name"]
                            if instrument and instrument["industry_name"]
                            else (
                                "未分类（ETF）"
                                if instrument and instrument["asset_type"] == "etf"
                                else "未分类"
                            )
                        ),
                        "industry_source": (
                            instrument["industry_source"] if instrument else ""
                        ),
                        "industry_updated_at": (
                            instrument["industry_updated_at"] if instrument else ""
                        ),
                        "industry_classified": bool(
                            instrument and instrument["industry_name"]
                        ),
                        "quantity": state.quantity,
                        "average_cost": state.average_cost,
                        "remaining_cost": state.remaining_cost,
                        "close": close,
                        "price_date": quote["trade_date"] if quote is not None else None,
                        "price_source": quote["source"] if quote is not None else None,
                        "pct_chg": (
                            Decimal(quote["pct_chg"])
                            if quote is not None and quote["pct_chg"] != ""
                            else None
                        ),
                        "market_value": market_value,
                        "unrealized_pnl": unrealized,
                        "return_pct": return_pct,
                        "realized_pnl": state.realized_pnl,
                    }
                )

        remaining_cost = sum((row["remaining_cost"] for row in result), ZERO)
        priced_rows = [row for row in result if row["market_value"] is not None]
        market_value = sum((row["market_value"] for row in priced_rows), ZERO)
        unrealized = sum((row["unrealized_pnl"] for row in priced_rows), ZERO)
        realized = sum((state.realized_pnl for state in states.values()), ZERO)
        missing_prices = [row["ts_code"] for row in result if row["close"] is None]
        fully_priced = not missing_prices
        summary = {
            "account_id": account_id,
            "as_of": as_of.isoformat() if as_of else None,
            "position_count": len(result),
            "remaining_cost": remaining_cost,
            "market_value": market_value if fully_priced else None,
            "unrealized_pnl": unrealized if fully_priced else None,
            "unrealized_return_pct": (
                unrealized / remaining_cost * Decimal("100")
                if fully_priced and remaining_cost != ZERO
                else None
            ),
            "realized_pnl_since_baseline": realized,
            "total_pnl_since_baseline": unrealized + realized if fully_priced else None,
            "missing_prices": missing_prices,
            "latest_price_date": max(
                (row["price_date"] for row in result if row["price_date"]),
                default=None,
            ),
        }
        return result, summary

    def closed_position_report(
        self, account_id: str, as_of: date | None = None
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        ledger = self.ledger(account_id, as_of)
        cycles = build_closed_position_cycles(ledger)
        states = build_position_states(ledger)
        with self.connect() as connection:
            instruments = {
                row["ts_code"]: row
                for row in connection.execute("SELECT * FROM instruments")
            }

        result: list[dict[str, Any]] = []
        for cycle in cycles:
            instrument = instruments.get(cycle.ts_code)
            result.append(
                {
                    "cycle_id": f"{cycle.ts_code}:{cycle.cycle_number}",
                    "ts_code": cycle.ts_code,
                    "name": instrument["name"] if instrument else cycle.ts_code,
                    "asset_type": instrument["asset_type"] if instrument else "unknown",
                    "industry_name": (
                        instrument["industry_name"]
                        if instrument and instrument["industry_name"]
                        else (
                            "未分类（ETF）"
                            if instrument and instrument["asset_type"] == "etf"
                            else "未分类"
                        )
                    ),
                    "industry_source": (
                        instrument["industry_source"] if instrument else ""
                    ),
                    "cycle_number": cycle.cycle_number,
                    "opened_on": cycle.opened_on,
                    "closed_on": cycle.closed_on,
                    "opening_event_type": cycle.opening_event_type,
                    "holding_days": cycle.holding_days,
                    "acquired_quantity": cycle.acquired_quantity,
                    "sold_quantity": cycle.sold_quantity,
                    "cost_basis": cycle.cost_basis,
                    "net_sale_proceeds": cycle.net_sale_proceeds,
                    "trading_pnl": cycle.trading_pnl,
                    "cash_income": cycle.cash_income,
                    "cash_fees": cycle.cash_fees,
                    "realized_pnl": cycle.realized_pnl,
                    "return_pct": cycle.return_pct,
                    "close_price": cycle.close_price,
                    "buy_count": cycle.buy_count,
                    "sell_count": cycle.sell_count,
                    "calculation_source": "ledger_entries.moving_average_cost",
                }
            )

        total_cost_basis = sum((item["cost_basis"] for item in result), ZERO)
        total_net_sale_proceeds = sum(
            (item["net_sale_proceeds"] for item in result), ZERO
        )
        total_trading_pnl = sum((item["trading_pnl"] for item in result), ZERO)
        total_cash_income = sum((item["cash_income"] for item in result), ZERO)
        total_cash_fees = sum((item["cash_fees"] for item in result), ZERO)
        total_realized_pnl = sum((item["realized_pnl"] for item in result), ZERO)
        all_realized_pnl = sum((state.realized_pnl for state in states.values()), ZERO)
        gain_count = sum(item["realized_pnl"] > ZERO for item in result)
        loss_count = sum(item["realized_pnl"] < ZERO for item in result)
        flat_count = len(result) - gain_count - loss_count
        summary = {
            "account_id": account_id,
            "as_of": as_of.isoformat() if as_of else None,
            "cycle_count": len(result),
            "security_count": len({item["ts_code"] for item in result}),
            "gain_count": gain_count,
            "loss_count": loss_count,
            "flat_count": flat_count,
            "win_rate_pct": (
                Decimal(gain_count) / Decimal(len(result)) * Decimal("100")
                if result
                else None
            ),
            "total_cost_basis": total_cost_basis,
            "total_net_sale_proceeds": total_net_sale_proceeds,
            "total_trading_pnl": total_trading_pnl,
            "total_cash_income": total_cash_income,
            "total_cash_fees": total_cash_fees,
            "total_realized_pnl": total_realized_pnl,
            "return_pct": (
                total_realized_pnl / total_cost_basis * Decimal("100")
                if total_cost_basis != ZERO
                else None
            ),
            "realized_pnl_outside_closed_cycles": (
                all_realized_pnl - total_realized_pnl
            ),
            "latest_close_date": (
                max((item["closed_on"] for item in result), default=None)
            ),
            "calculation_note": (
                "仅统计持仓数量由正数归零的完整周期；移动加权平均成本、卖出费用、"
                "周期内现金红利和现金税费均计入。部分卖出但尚未归零的已实现盈亏不计入本视图。"
            ),
        }
        return result, summary

    def recent_ledger(self, account_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT entry_id, event_date, event_time, event_type, ts_code, quantity,
                    price, gross_amount, fees, total_cost, cash_amount, external_id,
                    source_row, note
                FROM ledger_entries WHERE account_id = ?
                ORDER BY event_date DESC, event_time DESC, entry_id DESC LIMIT ?
                """,
                (account_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def recent_reconciliations(self, account_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT observation_id, event_date, event_time, event_type, ts_code,
                    quantity, price, gross_amount, fees, cash_amount, disposition,
                    baseline_date, external_id, source_row, note
                FROM statement_observations WHERE account_id = ?
                ORDER BY event_date DESC, event_time DESC, observation_id DESC LIMIT ?
                """,
                (account_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def dashboard_metadata(self, account_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            account = connection.execute(
                "SELECT name, base_currency, baseline_date, created_at FROM accounts WHERE account_id = ?",
                (account_id,),
            ).fetchone()
            if account is None:
                raise ValueError(f"账户不存在: {account_id}")
            ledger_count = connection.execute(
                "SELECT COUNT(*) AS count FROM ledger_entries WHERE account_id = ?",
                (account_id,),
            ).fetchone()["count"]
            reconciliation_count = connection.execute(
                "SELECT COUNT(*) AS count FROM statement_observations WHERE account_id = ?",
                (account_id,),
            ).fetchone()["count"]
            batch_count = connection.execute(
                "SELECT COUNT(*) AS count FROM import_batches WHERE account_id = ?",
                (account_id,),
            ).fetchone()["count"]
            latest_fetch = connection.execute(
                """
                SELECT MAX(fetched_at) AS fetched_at FROM close_prices
                WHERE source LIKE 'tushare.%'
                """
            ).fetchone()["fetched_at"]
            latest_industry_update = connection.execute(
                "SELECT MAX(industry_updated_at) AS updated_at FROM instruments"
            ).fetchone()["updated_at"]
        return {
            "account_name": account["name"],
            "base_currency": account["base_currency"],
            "baseline_date": account["baseline_date"],
            "account_created_at": account["created_at"],
            "ledger_count": ledger_count,
            "reconciliation_count": reconciliation_count,
            "import_batch_count": batch_count,
            "last_tushare_fetch_at": latest_fetch,
            "last_industry_update_at": latest_industry_update,
        }

    def debug_summary(self, account_id: str) -> str:
        positions, summary = self.position_report(account_id)
        payload = {
            "database": str(self.path.resolve()),
            "positions": positions,
            "summary": summary,
        }
        return json.dumps(payload, ensure_ascii=False, default=str, indent=2)
