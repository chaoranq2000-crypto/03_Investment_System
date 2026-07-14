from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

from .accounting import (
    AccountingError,
    build_closed_position_cycles,
    build_ledger_cycles,
    build_position_states,
)
from .models import (
    AdjustmentFactorObservation,
    ClosePrice,
    DailyBarObservation,
    IndustryClassification,
    Instrument,
    LedgerEntry,
    MinuteBarObservation,
    PositionState,
    ZERO,
    decimal_to_text,
)


SCHEMA_VERSION = "6"

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

CREATE TABLE IF NOT EXISTS cash_balance_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    as_of_date TEXT NOT NULL,
    amount TEXT NOT NULL,
    source TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    recorded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cash_balance_account_date
ON cash_balance_snapshots(account_id, as_of_date DESC, recorded_at DESC);

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

CREATE TABLE IF NOT EXISTS internal_transfer_reconciliations (
    transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    ts_code TEXT NOT NULL REFERENCES instruments(ts_code),
    quantity TEXT NOT NULL,
    transfer_out_date TEXT NOT NULL,
    transfer_in_date TEXT NOT NULL,
    from_broker TEXT NOT NULL,
    to_broker TEXT NOT NULL,
    reference_price TEXT NOT NULL DEFAULT '0',
    out_source_name TEXT NOT NULL DEFAULT '',
    in_source_name TEXT NOT NULL DEFAULT '',
    out_reference TEXT NOT NULL DEFAULT '',
    in_reference TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK (status IN ('reconciled_internal')),
    note TEXT NOT NULL DEFAULT '',
    dedupe_key TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE(account_id, dedupe_key)
);

CREATE INDEX IF NOT EXISTS idx_internal_transfers_account_date
ON internal_transfer_reconciliations(
    account_id, transfer_in_date DESC, transfer_out_date DESC, transfer_id DESC
);

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

CREATE TABLE IF NOT EXISTS daily_bar_observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL REFERENCES instruments(ts_code),
    trade_date TEXT NOT NULL,
    open_price TEXT NOT NULL,
    high_price TEXT NOT NULL,
    low_price TEXT NOT NULL,
    close_price TEXT NOT NULL,
    volume_lots TEXT NOT NULL,
    amount_k_cny TEXT NOT NULL,
    source TEXT NOT NULL,
    refresh_batch_id TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE,
    fetched_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_daily_bars_code_date
ON daily_bar_observations(
    ts_code, trade_date DESC, fetched_at DESC, observation_id DESC
);

CREATE TABLE IF NOT EXISTS adjustment_factor_observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL REFERENCES instruments(ts_code),
    trade_date TEXT NOT NULL,
    adj_factor TEXT NOT NULL,
    source TEXT NOT NULL,
    refresh_batch_id TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE,
    fetched_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_adjustment_factors_code_date
ON adjustment_factor_observations(
    ts_code, trade_date DESC, fetched_at DESC, observation_id DESC
);

CREATE TABLE IF NOT EXISTS minute_refresh_batches (
    refresh_batch_id TEXT PRIMARY KEY,
    ts_code TEXT NOT NULL REFERENCES instruments(ts_code),
    trade_date TEXT NOT NULL,
    frequency_minutes INTEGER NOT NULL CHECK (frequency_minutes IN (1, 5)),
    source TEXT NOT NULL,
    provider_attempts_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_minute_batches_code_date
ON minute_refresh_batches(
    ts_code, trade_date DESC, frequency_minutes, fetched_at DESC
);

CREATE TABLE IF NOT EXISTS minute_bar_observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL REFERENCES instruments(ts_code),
    bar_time TEXT NOT NULL,
    frequency_minutes INTEGER NOT NULL CHECK (frequency_minutes IN (1, 5)),
    open_price TEXT NOT NULL,
    high_price TEXT NOT NULL,
    low_price TEXT NOT NULL,
    close_price TEXT NOT NULL,
    volume_shares TEXT NOT NULL,
    amount_cny TEXT NOT NULL,
    source TEXT NOT NULL,
    refresh_batch_id TEXT NOT NULL REFERENCES minute_refresh_batches(refresh_batch_id),
    dedupe_key TEXT NOT NULL UNIQUE,
    fetched_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_minute_bars_code_time
ON minute_bar_observations(
    ts_code, bar_time DESC, frequency_minutes, fetched_at DESC, observation_id DESC
);
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

    def _schema_version_on_disk(self) -> str | None:
        if not self.path.is_file():
            return None
        connection = sqlite3.connect(self.path)
        try:
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'metadata'"
            ).fetchone()
            if table is None:
                return None
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()
            return str(row[0]) if row is not None else None
        finally:
            connection.close()

    def _backup_before_migration(self, current_version: str | None) -> Path | None:
        if current_version not in {"1", "2", "3", "4", "5"} or not self.path.is_file():
            return None
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup_path = self.path.with_name(
            f"{self.path.name}-v{current_version}-backup-{stamp}"
        )
        source = sqlite3.connect(self.path)
        target = sqlite3.connect(backup_path)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        return backup_path

    def initialize(self, account_id: str = "default", account_name: str = "默认账户") -> None:
        current_version = self._schema_version_on_disk()
        self._backup_before_migration(current_version)
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
                    ("2",),
                )
                row = connection.execute(
                    "SELECT value FROM metadata WHERE key = 'schema_version'"
                ).fetchone()
            if row is not None and row["value"] == "2":
                connection.execute(
                    "UPDATE metadata SET value = ? WHERE key = 'schema_version'",
                    ("3",),
                )
                row = connection.execute(
                    "SELECT value FROM metadata WHERE key = 'schema_version'"
                ).fetchone()
            if row is not None and row["value"] == "3":
                connection.execute(
                    "UPDATE metadata SET value = ? WHERE key = 'schema_version'",
                    ("4",),
                )
                row = connection.execute(
                    "SELECT value FROM metadata WHERE key = 'schema_version'"
                ).fetchone()
            if row is not None and row["value"] == "4":
                connection.execute(
                    "UPDATE metadata SET value = ? WHERE key = 'schema_version'",
                    ("5",),
                )
                row = connection.execute(
                    "SELECT value FROM metadata WHERE key = 'schema_version'"
                ).fetchone()
            if row is not None and row["value"] == "5":
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

    def set_cash_balance(
        self,
        account_id: str,
        amount: Decimal,
        as_of: date,
        *,
        source: str = "user_provided",
        note: str = "",
    ) -> dict[str, Any]:
        if not amount.is_finite() or amount < ZERO:
            raise ValueError("现金余额必须是大于或等于 0 的有限数值")
        normalized_source = source.strip()
        if not normalized_source:
            raise ValueError("现金余额来源不能为空")
        snapshot_id = str(uuid.uuid4())
        recorded_at = utc_now()
        with self.connect() as connection:
            if connection.execute(
                "SELECT 1 FROM accounts WHERE account_id = ?", (account_id,)
            ).fetchone() is None:
                raise ValueError(f"账户不存在: {account_id}")
            connection.execute(
                """
                INSERT INTO cash_balance_snapshots(
                    snapshot_id, account_id, as_of_date, amount, source, note, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    account_id,
                    as_of.isoformat(),
                    decimal_to_text(amount),
                    normalized_source,
                    note.strip(),
                    recorded_at,
                ),
            )
            connection.commit()
        return {
            "snapshot_id": snapshot_id,
            "account_id": account_id,
            "as_of_date": as_of.isoformat(),
            "amount": amount,
            "source": normalized_source,
            "note": note.strip(),
            "recorded_at": recorded_at,
        }

    def cash_balance(
        self, account_id: str, as_of: date | None = None
    ) -> dict[str, Any] | None:
        date_filter = "AND as_of_date <= ?" if as_of is not None else ""
        params: tuple[str, ...] = (
            (account_id, as_of.isoformat()) if as_of is not None else (account_id,)
        )
        with self.connect() as connection:
            row = connection.execute(
                f"""
                SELECT snapshot_id, account_id, as_of_date, amount, source, note, recorded_at
                FROM cash_balance_snapshots
                WHERE account_id = ? {date_filter}
                ORDER BY as_of_date DESC, recorded_at DESC, snapshot_id DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["amount"] = Decimal(result["amount"])
        return result

    def cash_history(self, account_id: str, limit: int = 100) -> list[dict[str, Any]]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit 必须在 1 到 1000 之间")
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT snapshot_id, account_id, as_of_date, amount, source, note, recorded_at
                FROM cash_balance_snapshots
                WHERE account_id = ?
                ORDER BY as_of_date DESC, recorded_at DESC, snapshot_id DESC
                LIMIT ?
                """,
                (account_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

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

    def preview_historical_closed_statement(
        self, account_id: str, entries: list[LedgerEntry]
    ) -> dict[str, Any]:
        """校验基准日前、从零开始且最终完全清仓的一组历史流水。"""

        baseline = self.baseline_date(account_id)
        if baseline is None:
            raise ValueError("账户还没有期初快照，不能导入历史已清仓流水")
        later = [item for item in entries if item.event_date > baseline]
        if later:
            first = later[0]
            raise ValueError(
                f"第 {first.source_row or '?'} 行日期 {first.event_date.isoformat()} 晚于期初基准日 "
                f"{baseline.isoformat()}，不能作为历史已清仓流水导入"
            )

        ordered_entries = sorted(
            entries,
            key=lambda item: (
                item.event_date.isoformat(),
                item.event_time or "99:99:99",
                item.source_row or 0,
            ),
        )
        candidate_rows = [
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
            for item in ordered_entries
        ]
        candidate_states = build_position_states(candidate_rows)
        incomplete = sorted(
            code for code, state in candidate_states.items() if state.quantity != ZERO
        )
        if incomplete:
            raise ValueError(
                "历史已清仓流水必须从零建仓并最终归零；以下证券仍有数量: "
                + ", ".join(incomplete)
            )
        event_types: dict[str, set[str]] = {}
        for item in ordered_entries:
            event_types.setdefault(item.ts_code, set()).add(item.event_type)
        missing_sides = sorted(
            code
            for code, types in event_types.items()
            if not {"BUY", "SELL"}.issubset(types)
        )
        if missing_sides:
            raise ValueError(
                "历史已清仓流水必须同时包含建仓和清仓成交: "
                + ", ".join(missing_sides)
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
            rows: list[Any] = list(self._ordered_ledger(connection, account_id))
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
                str(row["event_time"]) or "99:99:99",
                int(row["source_row"] if isinstance(row, dict) else row["entry_id"]),
            )
        )
        build_position_states(rows)
        return {
            "baseline_date": baseline.isoformat(),
            "accepted_entries": len(unique_entries),
            "duplicate_entries": len(entries) - len(unique_entries),
            "closed_codes": sorted(candidate_states),
        }

    def apply_historical_closed_statement(
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
        preview = self.preview_historical_closed_statement(account_id, entries)
        batch_id = f"historical_closed_{uuid.uuid4().hex}"
        with self.connect() as connection:
            self._upsert_instruments(connection, instruments)
            self._insert_batch(
                connection,
                batch_id=batch_id,
                account_id=account_id,
                import_kind="historical_closed_statement",
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
                "UPDATE import_batches SET accepted_rows = ?, duplicate_rows = ? WHERE batch_id = ?",
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

    def instrument(self, ts_code: str) -> Instrument | None:
        normalized = ts_code.strip().upper()
        with self.connect() as connection:
            row = connection.execute(
                "SELECT ts_code, name, asset_type FROM instruments WHERE ts_code = ?",
                (normalized,),
            ).fetchone()
        if row is None:
            return None
        return Instrument(
            ts_code=row["ts_code"],
            name=row["name"],
            asset_type=row["asset_type"],
        )

    def add_kline_batch(
        self,
        bars: Iterable[DailyBarObservation],
        factors: Iterable[AdjustmentFactorObservation],
    ) -> dict[str, int]:
        bar_list = list(bars)
        factor_list = list(factors)
        codes = {item.ts_code for item in [*bar_list, *factor_list]}
        with self.connect() as connection:
            known_codes = {
                row["ts_code"]
                for row in connection.execute("SELECT ts_code FROM instruments")
            }
            missing = sorted(codes - known_codes)
            if missing:
                raise ValueError(f"K 线包含未登记证券: {', '.join(missing)}")

            inserted_bars = 0
            for item in bar_list:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO daily_bar_observations(
                        ts_code, trade_date, open_price, high_price, low_price,
                        close_price, volume_lots, amount_k_cny, source,
                        refresh_batch_id, dedupe_key, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.ts_code,
                        item.trade_date.isoformat(),
                        decimal_to_text(item.open),
                        decimal_to_text(item.high),
                        decimal_to_text(item.low),
                        decimal_to_text(item.close),
                        decimal_to_text(item.volume_lots),
                        decimal_to_text(item.amount_k_cny),
                        item.source,
                        item.refresh_batch_id,
                        item.dedupe_key,
                        item.fetched_at or utc_now(),
                    ),
                )
                inserted_bars += int(cursor.rowcount == 1)

            inserted_factors = 0
            for item in factor_list:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO adjustment_factor_observations(
                        ts_code, trade_date, adj_factor, source,
                        refresh_batch_id, dedupe_key, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.ts_code,
                        item.trade_date.isoformat(),
                        decimal_to_text(item.adj_factor),
                        item.source,
                        item.refresh_batch_id,
                        item.dedupe_key,
                        item.fetched_at or utc_now(),
                    ),
                )
                inserted_factors += int(cursor.rowcount == 1)
            connection.commit()
        return {
            "new_bar_observations": inserted_bars,
            "new_factor_observations": inserted_factors,
        }

    def latest_daily_bars(
        self, ts_code: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM (
                    SELECT daily_bar_observations.*,
                        ROW_NUMBER() OVER (
                            PARTITION BY trade_date
                            ORDER BY fetched_at DESC, observation_id DESC
                        ) AS observation_rank
                    FROM daily_bar_observations
                    WHERE ts_code = ? AND trade_date BETWEEN ? AND ?
                ) WHERE observation_rank = 1
                ORDER BY trade_date, observation_id
                """,
                (ts_code, start_date.isoformat(), end_date.isoformat()),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["trade_date"] = date.fromisoformat(item["trade_date"])
            for key in (
                "open_price",
                "high_price",
                "low_price",
                "close_price",
                "volume_lots",
                "amount_k_cny",
            ):
                item[key] = Decimal(item[key])
            result.append(item)
        return result

    def latest_adjustment_factors(
        self, ts_code: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM (
                    SELECT adjustment_factor_observations.*,
                        ROW_NUMBER() OVER (
                            PARTITION BY trade_date
                            ORDER BY fetched_at DESC, observation_id DESC
                        ) AS observation_rank
                    FROM adjustment_factor_observations
                    WHERE ts_code = ? AND trade_date BETWEEN ? AND ?
                ) WHERE observation_rank = 1
                ORDER BY trade_date, observation_id
                """,
                (ts_code, start_date.isoformat(), end_date.isoformat()),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["trade_date"] = date.fromisoformat(item["trade_date"])
            item["adj_factor"] = Decimal(item["adj_factor"])
            result.append(item)
        return result

    def add_minute_batch(
        self,
        bars: Iterable[MinuteBarObservation],
        *,
        trade_date: date,
        frequency_minutes: int,
        source: str,
        refresh_batch_id: str,
        provider_attempts: list[dict[str, str]],
        fetched_at: str,
    ) -> dict[str, int]:
        bar_list = list(bars)
        if frequency_minutes not in {1, 5}:
            raise ValueError("分钟行情频率只支持 1 或 5 分钟")
        if any(item.ts_code != bar_list[0].ts_code for item in bar_list[1:]):
            raise ValueError("同一刷新批次不能包含多只证券")
        if any(item.frequency_minutes != frequency_minutes for item in bar_list):
            raise ValueError("分钟行情批次频率不一致")
        if not bar_list:
            return {"new_refresh_batches": 0, "new_minute_observations": 0}

        ts_code = bar_list[0].ts_code
        with self.connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM instruments WHERE ts_code = ?", (ts_code,)
            ).fetchone()
            if exists is None:
                raise ValueError(f"分钟行情包含未登记证券: {ts_code}")
            batch_cursor = connection.execute(
                """
                INSERT OR IGNORE INTO minute_refresh_batches(
                    refresh_batch_id, ts_code, trade_date, frequency_minutes,
                    source, provider_attempts_json, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    refresh_batch_id,
                    ts_code,
                    trade_date.isoformat(),
                    frequency_minutes,
                    source,
                    json.dumps(provider_attempts, ensure_ascii=False, sort_keys=True),
                    fetched_at,
                ),
            )
            inserted_bars = 0
            for item in bar_list:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO minute_bar_observations(
                        ts_code, bar_time, frequency_minutes, open_price, high_price,
                        low_price, close_price, volume_shares, amount_cny, source,
                        refresh_batch_id, dedupe_key, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.ts_code,
                        item.bar_time.isoformat(),
                        item.frequency_minutes,
                        decimal_to_text(item.open),
                        decimal_to_text(item.high),
                        decimal_to_text(item.low),
                        decimal_to_text(item.close),
                        decimal_to_text(item.volume_shares),
                        decimal_to_text(item.amount_cny),
                        item.source,
                        item.refresh_batch_id,
                        item.dedupe_key,
                        item.fetched_at or fetched_at,
                    ),
                )
                inserted_bars += int(cursor.rowcount == 1)
            connection.commit()
        return {
            "new_refresh_batches": int(batch_cursor.rowcount == 1),
            "new_minute_observations": inserted_bars,
        }

    def latest_minute_bars(
        self, ts_code: str, trade_date: date
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        with self.connect() as connection:
            batch = connection.execute(
                """
                SELECT * FROM minute_refresh_batches
                WHERE ts_code = ? AND trade_date = ?
                ORDER BY frequency_minutes ASC, fetched_at DESC, rowid DESC
                LIMIT 1
                """,
                (ts_code, trade_date.isoformat()),
            ).fetchone()
            if batch is None:
                return [], None
            rows = connection.execute(
                """
                SELECT * FROM (
                    SELECT minute_bar_observations.*,
                        ROW_NUMBER() OVER (
                            PARTITION BY bar_time
                            ORDER BY fetched_at DESC, observation_id DESC
                        ) AS observation_rank
                    FROM minute_bar_observations
                    WHERE ts_code = ?
                        AND frequency_minutes = ?
                        AND substr(bar_time, 1, 10) = ?
                ) WHERE observation_rank = 1
                ORDER BY bar_time, observation_id
                """,
                (ts_code, batch["frequency_minutes"], trade_date.isoformat()),
            ).fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["bar_time"] = datetime.fromisoformat(item["bar_time"])
            for key in (
                "open_price",
                "high_price",
                "low_price",
                "close_price",
                "volume_shares",
                "amount_cny",
            ):
                item[key] = Decimal(item[key])
            result.append(item)
        metadata = dict(batch)
        metadata["trade_date"] = date.fromisoformat(metadata["trade_date"])
        metadata["provider_attempts"] = json.loads(
            metadata.pop("provider_attempts_json")
        )
        return result, metadata

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
        baseline = self.baseline_date(account_id)
        baseline_ledger = (
            [row for row in ledger if date.fromisoformat(row["event_date"]) >= baseline]
            if baseline is not None
            else ledger
        )
        baseline_states = build_position_states(baseline_ledger)
        active_cycles = {
            cycle.ts_code: cycle
            for cycle in build_ledger_cycles(ledger)
            if not cycle.is_closed
        }
        result: list[dict[str, Any]] = []
        with self.connect() as connection:
            for ts_code, state in states.items():
                if state.quantity <= ZERO:
                    continue
                active_cycle = active_cycles.get(ts_code)
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
                        "cycle_id": (
                            active_cycle.cycle_id if active_cycle is not None else None
                        ),
                        "cycle_number": (
                            active_cycle.cycle_number if active_cycle is not None else None
                        ),
                        "opened_on": (
                            active_cycle.opened_on if active_cycle is not None else None
                        ),
                        "opening_event_type": (
                            active_cycle.opening_event_type
                            if active_cycle is not None
                            else None
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
                        "realized_pnl": baseline_states.get(
                            ts_code, PositionState(ts_code=ts_code)
                        ).realized_pnl,
                    }
                )

        remaining_cost = sum((row["remaining_cost"] for row in result), ZERO)
        priced_rows = [row for row in result if row["market_value"] is not None]
        market_value = sum((row["market_value"] for row in priced_rows), ZERO)
        unrealized = sum((row["unrealized_pnl"] for row in priced_rows), ZERO)
        realized = sum((state.realized_pnl for state in baseline_states.values()), ZERO)
        missing_prices = [row["ts_code"] for row in result if row["close"] is None]
        fully_priced = not missing_prices
        cash_snapshot = self.cash_balance(account_id, as_of)
        cash_balance = cash_snapshot["amount"] if cash_snapshot is not None else ZERO
        summary = {
            "account_id": account_id,
            "as_of": as_of.isoformat() if as_of else None,
            "position_count": len(result),
            "remaining_cost": remaining_cost,
            "market_value": market_value if fully_priced else None,
            "cash_balance": cash_balance,
            "cash_as_of": (
                cash_snapshot["as_of_date"] if cash_snapshot is not None else None
            ),
            "cash_source": cash_snapshot["source"] if cash_snapshot is not None else None,
            "total_assets": market_value + cash_balance if fully_priced else None,
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

    def record_internal_transfers(
        self, account_id: str, transfers: Iterable[Mapping[str, Any]]
    ) -> dict[str, int]:
        """登记组合内部的券商托管迁移，不写入买卖台账。"""

        normalized: list[dict[str, Any]] = []
        for row in transfers:
            ts_code = str(row.get("ts_code", "")).strip()
            quantity = Decimal(str(row.get("quantity", "0")))
            out_date = date.fromisoformat(str(row.get("transfer_out_date", "")).strip())
            in_date = date.fromisoformat(str(row.get("transfer_in_date", "")).strip())
            from_broker = str(row.get("from_broker", "")).strip()
            to_broker = str(row.get("to_broker", "")).strip()
            reference_price = Decimal(str(row.get("reference_price", "0") or "0"))
            if not ts_code or quantity <= ZERO:
                raise ValueError("内部托管迁移必须包含证券代码和正数量")
            if in_date < out_date:
                raise ValueError(f"{ts_code}: 托管转入日不能早于转出日")
            if not from_broker or not to_broker or from_broker == to_broker:
                raise ValueError(f"{ts_code}: 转出/转入券商必须明确且不同")
            if reference_price < ZERO:
                raise ValueError(f"{ts_code}: 参考价格不能为负")
            payload = {
                "account_id": account_id,
                "ts_code": ts_code,
                "quantity": decimal_to_text(quantity),
                "transfer_out_date": out_date.isoformat(),
                "transfer_in_date": in_date.isoformat(),
                "from_broker": from_broker,
                "to_broker": to_broker,
            }
            dedupe_key = hashlib.sha256(
                json.dumps(
                    payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest()
            normalized.append(
                {
                    **payload,
                    "reference_price": decimal_to_text(reference_price),
                    "out_source_name": str(row.get("out_source_name", "")).strip(),
                    "in_source_name": str(row.get("in_source_name", "")).strip(),
                    "out_reference": str(row.get("out_reference", "")).strip(),
                    "in_reference": str(row.get("in_reference", "")).strip(),
                    "note": str(row.get("note", "")).strip(),
                    "dedupe_key": dedupe_key,
                }
            )

        inserted = 0
        duplicates = 0
        now = utc_now()
        with self.connect() as connection:
            if connection.execute(
                "SELECT 1 FROM accounts WHERE account_id = ?", (account_id,)
            ).fetchone() is None:
                raise ValueError(f"账户不存在: {account_id}")
            known_codes = {
                item["ts_code"]
                for item in connection.execute("SELECT ts_code FROM instruments")
            }
            missing = sorted({item["ts_code"] for item in normalized} - known_codes)
            if missing:
                raise ValueError("托管迁移证券尚未登记: " + ", ".join(missing))
            for item in normalized:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO internal_transfer_reconciliations(
                        account_id, ts_code, quantity, transfer_out_date, transfer_in_date,
                        from_broker, to_broker, reference_price, out_source_name,
                        in_source_name, out_reference, in_reference, status, note,
                        dedupe_key, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        'reconciled_internal', ?, ?, ?)
                    """,
                    (
                        account_id,
                        item["ts_code"],
                        item["quantity"],
                        item["transfer_out_date"],
                        item["transfer_in_date"],
                        item["from_broker"],
                        item["to_broker"],
                        item["reference_price"],
                        item["out_source_name"],
                        item["in_source_name"],
                        item["out_reference"],
                        item["in_reference"],
                        item["note"],
                        item["dedupe_key"],
                        now,
                    ),
                )
                if cursor.rowcount == 1:
                    inserted += 1
                else:
                    duplicates += 1
            connection.commit()
        return {"inserted_transfers": inserted, "duplicate_transfers": duplicates}

    def recent_internal_transfers(
        self, account_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT transfer_id, ts_code, quantity, transfer_out_date, transfer_in_date,
                    from_broker, to_broker, reference_price, out_source_name,
                    in_source_name, out_reference, in_reference, status, note, recorded_at
                FROM internal_transfer_reconciliations
                WHERE account_id = ?
                ORDER BY transfer_in_date DESC, transfer_out_date DESC, transfer_id DESC
                LIMIT ?
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
            internal_transfer_count = connection.execute(
                "SELECT COUNT(*) AS count FROM internal_transfer_reconciliations WHERE account_id = ?",
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
            latest_kline_fetch = connection.execute(
                """
                SELECT MAX(fetched_at) AS fetched_at FROM (
                    SELECT fetched_at FROM daily_bar_observations
                    UNION ALL
                    SELECT fetched_at FROM adjustment_factor_observations
                )
                """
            ).fetchone()["fetched_at"]
            latest_intraday_fetch = connection.execute(
                "SELECT MAX(fetched_at) AS fetched_at FROM minute_refresh_batches"
            ).fetchone()["fetched_at"]
        return {
            "account_name": account["name"],
            "base_currency": account["base_currency"],
            "baseline_date": account["baseline_date"],
            "account_created_at": account["created_at"],
            "ledger_count": ledger_count,
            "reconciliation_count": reconciliation_count,
            "internal_transfer_count": internal_transfer_count,
            "import_batch_count": batch_count,
            "last_tushare_fetch_at": latest_fetch,
            "last_kline_fetch_at": latest_kline_fetch,
            "last_intraday_fetch_at": latest_intraday_fetch,
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
