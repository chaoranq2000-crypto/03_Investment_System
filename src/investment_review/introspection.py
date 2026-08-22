"""Read-only inspection of the existing portfolio SQLite database."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "record_id": (
        "trade_id", "fill_id", "transaction_id", "serial_no", "contract_no",
        "external_id", "dedupe_key", "entry_id",
        "成交编号", "合同编号", "流水号", "编号", "id",
    ),
    "occurred_at": (
        "occurred_at", "executed_at", "filled_at", "trade_time", "datetime",
        "timestamp", "成交时间", "发生时间", "时间",
    ),
    "trade_date": (
        "trade_date", "event_date", "business_date", "date",
        "成交日期", "发生日期", "日期",
    ),
    "trade_clock": ("trade_clock", "event_time", "time", "成交时刻", "成交时间", "时刻"),
    "known_at": ("known_at", "received_at", "created_at", "入库时间", "知悉时间"),
    "symbol": (
        "symbol", "ts_code", "security_code", "stock_code", "ticker", "code",
        "证券代码", "股票代码", "代码",
    ),
    "side": (
        "side", "event_type", "direction", "buy_sell", "operation",
        "业务名称", "买卖标志", "方向",
    ),
    "quantity": (
        "quantity", "qty", "volume", "shares", "business_amount",
        "成交数量", "发生数量", "股份数量", "数量",
    ),
    "price": ("price", "trade_price", "fill_price", "business_price", "成交价格", "价格"),
    "gross_amount": (
        "gross_amount", "amount", "notional", "turnover", "business_balance",
        "成交金额", "发生金额", "金额",
    ),
    "cash_amount": (
        "cash_amount", "net_cash_amount", "cash_flow", "资金发生数", "清算金额",
    ),
    "fees": ("fees", "fee", "commission", "total_fee", "手续费", "佣金", "费用"),
    "account": ("account", "account_id", "fund_account", "资金账号", "账户"),
    "market": ("market", "exchange", "交易市场", "市场"),
    "currency": ("currency", "币种"),
    "cost_basis": ("cost_basis", "avg_cost", "cost_price", "成本价", "成本"),
    "market_value": ("market_value", "position_value", "市值", "证券市值"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def table_schema_sha256(columns: list[dict[str, Any]], create_sql: str | None) -> str:
    """Return a strict signature for one SQLite table contract."""

    payload = json.dumps(
        {"columns": columns, "create_sql": create_sql},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalized(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def match_column(columns: Iterable[str], canonical_field: str) -> str | None:
    available = list(columns)
    by_normalized = {_normalized(column): column for column in available}
    for alias in FIELD_ALIASES.get(canonical_field, (canonical_field,)):
        hit = by_normalized.get(_normalized(alias))
        if hit:
            return hit
    return None


def score_table(columns: list[str]) -> dict[str, Any]:
    matched = {field: match_column(columns, field) for field in FIELD_ALIASES}
    trade_core = ("symbol", "side", "quantity", "price")
    time_ok = bool(matched["occurred_at"] or matched["trade_date"])
    trade_score = sum(bool(matched[field]) for field in trade_core) + int(time_ok)
    position_core = ("symbol", "quantity", "cost_basis", "market_value")
    position_score = sum(bool(matched[field]) for field in position_core)

    roles: list[str] = []
    if trade_score >= 4:
        roles.append("trade_event_candidate")
    if position_score >= 3:
        roles.append("position_snapshot_candidate")
    return {
        "roles": roles,
        "trade_score": trade_score,
        "position_score": position_score,
        "matched_fields": {key: value for key, value in matched.items() if value},
    }


def inspect_sqlite(path: str | Path, *, include_counts: bool = False) -> dict[str, Any]:
    database = Path(path)
    if not database.is_file():
        raise FileNotFoundError(database)

    stat_before = database.stat()
    uri = f"{database.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        tables = conn.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
        table_reports: list[dict[str, Any]] = []
        for table in tables:
            name = table["name"]
            columns = [
                dict(row)
                for row in conn.execute(f"PRAGMA table_info({quote_identifier(name)})").fetchall()
            ]
            column_names = [column["name"] for column in columns]
            report: dict[str, Any] = {
                "name": name,
                "columns": columns,
                "candidate": score_table(column_names),
                "create_sql": table["sql"],
                "table_schema_sha256": table_schema_sha256(columns, table["sql"]),
            }
            if include_counts:
                report["row_count"] = conn.execute(
                    f"SELECT COUNT(*) FROM {quote_identifier(name)}"
                ).fetchone()[0]
            table_reports.append(report)

        user_version = conn.execute("PRAGMA user_version").fetchone()[0]
        application_id = conn.execute("PRAGMA application_id").fetchone()[0]
    finally:
        conn.close()

    stat_after = database.stat()
    if (stat_before.st_size, stat_before.st_mtime_ns) != (stat_after.st_size, stat_after.st_mtime_ns):
        raise RuntimeError("Source database changed during read-only inspection")

    candidates = [
        {"table": table["name"], **table["candidate"]}
        for table in table_reports
        if table["candidate"]["roles"]
    ]
    candidates.sort(key=lambda item: (item["trade_score"], item["position_score"]), reverse=True)

    return {
        "generated_at": _now(),
        "database": str(database),
        "read_only": True,
        "size_bytes": stat_before.st_size,
        "mtime_ns": stat_before.st_mtime_ns,
        "sqlite_user_version": user_version,
        "sqlite_application_id": application_id,
        "tables": table_reports,
        "candidates": candidates,
    }


def discover_sqlite_files(root: str | Path = "data/db") -> list[Path]:
    directory = Path(root)
    if not directory.exists():
        return []
    patterns = ("*.db", "*.sqlite", "*.sqlite3")
    found: set[Path] = set()
    for pattern in patterns:
        found.update(path for path in directory.glob(pattern) if path.is_file())
    return sorted(found)


def suggest_trade_mapping(
    report: dict[str, Any], *, table_name: str | None = None
) -> dict[str, Any]:
    tables = report.get("tables", [])
    if table_name:
        selected = next((table for table in tables if table["name"] == table_name), None)
        if selected is None:
            raise ValueError(f"Table not found: {table_name}")
    else:
        ranked = sorted(
            tables,
            key=lambda table: table["candidate"]["trade_score"],
            reverse=True,
        )
        selected = ranked[0] if ranked else None
    if not selected:
        raise ValueError("No tables available for a mapping suggestion")

    matched = selected["candidate"]["matched_fields"]
    record_id: Any = matched.get("record_id")
    if (
        record_id
        and _normalized(record_id) == "external_id"
        and matched.get("account")
    ):
        record_id = {
            "join": [matched["account"], record_id],
            "separator": "::",
        }

    mapping: dict[str, Any] = {
        "record_id": record_id,
        "symbol": matched.get("symbol"),
        "side": matched.get("side"),
        "quantity": matched.get("quantity"),
        "price": matched.get("price"),
        "gross_amount": matched.get("gross_amount"),
        "cash_amount": matched.get("cash_amount"),
        "fees": matched.get("fees"),
        "known_at": matched.get("known_at"),
        "account": matched.get("account") or {"constant": "default"},
        "market": matched.get("market"),
        "currency": matched.get("currency") or {"constant": "CNY"},
        "event_type": (
            matched.get("side")
            if matched.get("side") and _normalized(matched["side"]) == "event_type"
            else {"constant": "fill"}
        ),
    }
    # Prefer an explicit date + clock pair when both exist. Broker exports
    # often call the clock-only column ``trade_time`` or ``成交时间``.
    if matched.get("trade_date") and matched.get("trade_clock"):
        mapping["occurred_at"] = {
            "join": [matched["trade_date"], matched["trade_clock"]],
            "separator": " ",
        }
    elif matched.get("occurred_at"):
        mapping["occurred_at"] = matched["occurred_at"]
    else:
        mapping["occurred_at"] = matched.get("trade_date")

    return {
        "source": {
            "name": f"portfolio-ledger:{Path(report['database']).stem}:{selected['name']}",
            "kind": "portfolio_sqlite",
            "uri": report["database"],
            "timezone": "Asia/Shanghai",
            "read_only": True,
        },
        "sqlite": {"table": selected["name"]},
        "mapping": mapping,
        "values": {
            "side": {
                "买入": "BUY",
                "证券买入": "BUY",
                "BUY": "BUY",
                "B": "BUY",
                "卖出": "SELL",
                "证券卖出": "SELL",
                "SELL": "SELL",
                "S": "SELL",
                "DIVIDEND": "OTHER",
                "CASH_FEE": "OTHER",
                "OPENING": "OTHER"
            }
        },
        "generated_from": {
            "database": report["database"],
            "table": selected["name"],
            "table_schema_sha256": selected["table_schema_sha256"],
            "trade_score": selected["candidate"]["trade_score"],
            # A generated mapping is always a suggestion. Even when the five
            # required fields are detected, their semantics still require a
            # human check before a real import.
            "review_required": True,
            "missing_required_fields": [
                field
                for field in ("occurred_at", "symbol", "side", "quantity", "price")
                if mapping.get(field) in (None, "")
            ],
        },
    }


def write_json(path: str | Path, payload: Any) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
