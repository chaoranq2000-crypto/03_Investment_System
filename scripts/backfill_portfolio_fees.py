"""Explicit portfolio-ledger fee maintenance; dry-run unless ``--apply`` is given.

This command belongs to the portfolio accounting surface.  The investment-review
workflow must not invoke it to mutate its formal source ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.portfolio.importer import (  # noqa: E402
    PRIMARY_BOND_SUBSCRIPTION_FEE_RULE_VERSION,
    calculate_historical_trade_fee,
    formal_fee_rule_version,
    infer_asset_type,
)
from src.portfolio.models import decimal_to_text  # noqa: E402
from src.portfolio.store import PortfolioStore  # noqa: E402


@dataclass(frozen=True)
class FeeUpdate:
    entry_id: int
    account_id: str
    old_dedupe_key: str
    new_dedupe_key: str
    ts_code: str
    asset_type: str
    event_type: str
    gross_amount: Decimal
    fees: Decimal
    note: str
    rule_version: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dedupe_key(row: sqlite3.Row, fees: Decimal) -> str:
    payload = {
        "account_id": row["account_id"],
        "event_date": row["event_date"],
        "event_time": row["event_time"],
        "event_type": row["event_type"],
        "ts_code": row["ts_code"],
        "quantity": decimal_to_text(Decimal(row["quantity"])),
        "price": decimal_to_text(Decimal(row["price"])),
        "gross_amount": decimal_to_text(Decimal(row["gross_amount"])),
        "fees": decimal_to_text(fees),
        "cash_amount": decimal_to_text(Decimal(row["cash_amount"])),
        "external_id": row["external_id"],
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _clean_note(
    note: str,
    rule_version: str,
    *,
    fee_source: str = "rule_derived",
    backfilled: bool = True,
) -> str:
    value = re.sub(
        r"broker=user_screenshot_fee_pending",
        "broker=user_screenshot",
        str(note or ""),
        flags=re.IGNORECASE,
    )
    parts = []
    for raw in value.split(";"):
        part = raw.strip()
        lowered = part.lower()
        if not part or lowered in {
            "fees_missing=true",
            "fee_pending",
            "missing_source_column",
        }:
            continue
        if lowered.startswith(("fee_rule=", "fee_source=")):
            continue
        if lowered == "fee_backfilled_rule=true":
            continue
        parts.append(part)
    parts.extend((f"fee_rule={rule_version}", f"fee_source={fee_source}"))
    if backfilled:
        parts.append("fee_backfilled_rule=true")
    return "; ".join(parts)


def _is_primary_bond_subscription(note: str) -> bool:
    return "raw_event=新债入账" in str(note or "")


def build_plan(database: Path) -> tuple[list[FeeUpdate], list[int], dict[str, str]]:
    uri = f"{database.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT l.*, i.name, i.asset_type AS stored_asset_type
            FROM ledger_entries AS l
            LEFT JOIN instruments AS i ON i.ts_code = l.ts_code
            WHERE l.event_type IN ('BUY', 'SELL')
              AND CAST(l.fees AS REAL) = 0
            ORDER BY l.entry_id
            """
        ).fetchall()
        existing_keys = {
            str(row["dedupe_key"]): int(row["entry_id"])
            for row in connection.execute(
                "SELECT entry_id, dedupe_key FROM ledger_entries"
            ).fetchall()
        }
    finally:
        connection.close()

    updates: list[FeeUpdate] = []
    exempt_entry_ids: list[int] = []
    instrument_corrections: dict[str, str] = {}
    for row in rows:
        if _is_primary_bond_subscription(row["note"]):
            exempt_entry_ids.append(int(row["entry_id"]))
            continue
        asset_type = infer_asset_type(str(row["ts_code"]), str(row["name"] or ""))
        gross_amount = Decimal(row["gross_amount"])
        fees = calculate_historical_trade_fee(
            gross_amount,
            asset_type=asset_type,
            event_type=str(row["event_type"]),
            ts_code=str(row["ts_code"]),
        )
        rule_version = formal_fee_rule_version(
            asset_type=asset_type,
            ts_code=str(row["ts_code"]),
        )
        update = FeeUpdate(
            entry_id=int(row["entry_id"]),
            account_id=str(row["account_id"]),
            old_dedupe_key=str(row["dedupe_key"]),
            new_dedupe_key=_dedupe_key(row, fees),
            ts_code=str(row["ts_code"]),
            asset_type=asset_type,
            event_type=str(row["event_type"]),
            gross_amount=gross_amount,
            fees=fees,
            note=_clean_note(str(row["note"]), rule_version),
            rule_version=rule_version,
        )
        updates.append(update)
        if str(row["stored_asset_type"] or "unknown") != asset_type:
            instrument_corrections[update.ts_code] = asset_type

    final_keys = Counter(item.new_dedupe_key for item in updates)
    duplicate_final_keys = [key for key, count in final_keys.items() if count > 1]
    if duplicate_final_keys:
        raise RuntimeError(
            f"fee backfill would create duplicate dedupe keys: {duplicate_final_keys}"
        )
    changing_entry_ids = {item.entry_id for item in updates}
    for item in updates:
        owner = existing_keys.get(item.new_dedupe_key)
        if owner is not None and owner != item.entry_id and owner not in changing_entry_ids:
            raise RuntimeError(
                f"fee backfill dedupe collision: entry_id={item.entry_id}, owner={owner}"
            )
    return updates, exempt_entry_ids, instrument_corrections


def _summary(
    updates: list[FeeUpdate],
    exempt_entry_ids: list[int],
    instrument_corrections: dict[str, str],
) -> dict[str, Any]:
    counts = Counter(
        (item.asset_type, item.event_type, item.rule_version) for item in updates
    )
    return {
        "fee_updates": len(updates),
        "fee_total": decimal_to_text(sum((item.fees for item in updates), Decimal(0))),
        "affected_accounts": sorted({item.account_id for item in updates}),
        "formal_zero_fee_exemptions": len(exempt_entry_ids),
        "exempt_entry_ids": exempt_entry_ids,
        "instrument_corrections": instrument_corrections,
        "groups": [
            {
                "asset_type": key[0],
                "event_type": key[1],
                "rule_version": key[2],
                "entries": count,
                "fee_total": decimal_to_text(
                    sum(
                        (
                            item.fees
                            for item in updates
                            if (item.asset_type, item.event_type, item.rule_version)
                            == key
                        ),
                        Decimal(0),
                    )
                ),
            }
            for key, count in sorted(counts.items())
        ],
    }


def _backup_database(database: Path, backup: Path) -> None:
    if backup.exists():
        raise FileExistsError(f"backup already exists: {backup}")
    source = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
    destination = sqlite3.connect(backup)
    try:
        source.backup(destination)
        check = destination.execute("PRAGMA quick_check").fetchone()[0]
        if check != "ok":
            raise RuntimeError(f"backup quick_check failed: {check}")
    finally:
        destination.close()
        source.close()


def apply_plan(
    database: Path,
    backup: Path,
    updates: list[FeeUpdate],
    exempt_entry_ids: list[int],
    instrument_corrections: dict[str, str],
) -> dict[str, Any]:
    _backup_database(database, backup)
    before_sha256 = _sha256(database)
    backup_sha256 = _sha256(backup)
    connection = sqlite3.connect(database, timeout=30)
    try:
        connection.execute("BEGIN IMMEDIATE")
        for ts_code, asset_type in instrument_corrections.items():
            connection.execute(
                "UPDATE instruments SET asset_type = ? WHERE ts_code = ?",
                (asset_type, ts_code),
            )
        for item in updates:
            cursor = connection.execute(
                """
                UPDATE ledger_entries
                SET fees = ?, dedupe_key = ?, note = ?
                WHERE entry_id = ? AND CAST(fees AS REAL) = 0 AND dedupe_key = ?
                """,
                (
                    decimal_to_text(item.fees),
                    item.new_dedupe_key,
                    item.note,
                    item.entry_id,
                    item.old_dedupe_key,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"ledger changed during fee backfill: entry_id={item.entry_id}"
                )
        for entry_id in exempt_entry_ids:
            row = connection.execute(
                "SELECT note FROM ledger_entries WHERE entry_id = ?",
                (entry_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError(
                    f"ledger changed during fee exemption update: entry_id={entry_id}"
                )
            cursor = connection.execute(
                """
                UPDATE ledger_entries SET note = ?
                WHERE entry_id = ? AND CAST(fees AS REAL) = 0
                """,
                (
                    _clean_note(
                        str(row["note"]),
                        PRIMARY_BOND_SUBSCRIPTION_FEE_RULE_VERSION,
                        fee_source="formal_exemption",
                        backfilled=False,
                    ),
                    entry_id,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"ledger changed during fee exemption update: entry_id={entry_id}"
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    store = PortfolioStore(database)
    cash_updates = {
        account_id: store.recalculate_cash_from_ledger(account_id)
        for account_id in sorted({item.account_id for item in updates})
    }
    validation = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
    try:
        quick_check = validation.execute("PRAGMA quick_check").fetchone()[0]
        remaining_zero_rows = validation.execute(
            """
            SELECT COUNT(*) FROM ledger_entries
            WHERE event_type IN ('BUY', 'SELL') AND CAST(fees AS REAL) = 0
            """
        ).fetchone()[0]
        remaining_pending_rows = validation.execute(
            """
            SELECT COUNT(*) FROM ledger_entries
            WHERE event_type IN ('BUY', 'SELL')
              AND (
                  lower(note) LIKE '%fees_missing=true%'
                  OR lower(note) LIKE '%fee_pending%'
                  OR lower(note) LIKE '%missing_source_column%'
              )
            """
        ).fetchone()[0]
    finally:
        validation.close()
    if quick_check != "ok":
        raise RuntimeError(f"formal database quick_check failed: {quick_check}")
    return {
        "database": str(database),
        "backup": str(backup),
        "database_sha256_before": before_sha256,
        "database_sha256_after": _sha256(database),
        "backup_sha256": backup_sha256,
        "quick_check": quick_check,
        "remaining_zero_fee_trades": int(remaining_zero_rows),
        "remaining_pending_markers": int(remaining_pending_rows),
        "cash_updates": cash_updates,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    database = args.db.resolve()
    updates, exemptions, corrections = build_plan(database)
    result: dict[str, Any] = {
        "mode": "apply" if args.apply else "dry_run",
        **_summary(updates, exemptions, corrections),
    }
    if args.apply:
        if args.backup is None:
            parser.error("--backup is required with --apply")
        result.update(
            apply_plan(
                database,
                args.backup.resolve(),
                updates,
                exemptions,
                corrections,
            )
        )
    output = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if args.receipt is not None:
        args.receipt.resolve().write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
