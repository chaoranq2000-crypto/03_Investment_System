"""Read-only adapter for the existing P2B portfolio snapshot contract.

The adapter inventories snapshots that already exist in the portfolio SQLite
database and selects only rows visible under explicit effective- and
knowledge-time cutoffs.  It deliberately does not reconstruct historical
snapshots from ``ledger_entries``: the portfolio ledger's ``created_at`` is not
historical decision-time knowledge provenance.

No decision, price, classification, or account-wide cursor is inferred here.
Missing evidence remains ``missing`` or ``partial`` for the canonical P2C /
P2E-3 builders to handle under their existing source-replay gates.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from copy import deepcopy
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from .episodes import EpisodeProjectionError, load_p2b_snapshot_references
from .episode_portfolio_context import (
    ledger_snapshot_reconstruction_availability,
)
from .ledger_snapshot_reconstruction import (
    LEDGER_SNAPSHOT_BASELINE_SCHEMA_VERSION,
    LEDGER_SNAPSHOT_RECONSTRUCTION_SCHEMA_VERSION,
)
from .models import canonical_json, sha256_text


SNAPSHOT_INVENTORY_SCHEMA = "investment_review.portfolio_snapshot_inventory.v1"
SNAPSHOT_ADAPTER_VERSION = "portfolio_snapshot_adapter_v1"
CASH_BASELINE_PROOF_SCHEMA = "investment_review.cash_baseline_proof.v1"
CASH_BASELINE_ADAPTER_VERSION = "cash_baseline_adapter_v1"
_BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_REQUIRED_COLUMNS = {
    "accounts": {"account_id"},
    "portfolio_snapshots": {
        "snapshot_id",
        "account_id",
        "as_of_date",
        "knowledge_cutoff_at",
        "revision",
        "engine_version",
        "source_state_hash",
        "cash_status",
        "valuation_complete",
        "position_count",
    },
    "position_snapshots": {
        "snapshot_id",
        "ts_code",
        "price",
        "price_date",
        "price_source",
        "valuation_status",
        "market_value",
        "industry_name",
        "industry_source",
        "lineage_json",
    },
}
_CASH_REQUIRED_COLUMNS = {
    "snapshot_id",
    "account_id",
    "as_of_date",
    "amount",
    "source",
    "note",
    "recorded_at",
}


class PortfolioSnapshotAdapterError(RuntimeError):
    """Raised when a stable, read-only snapshot inventory cannot be proven."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _as_of_date(value: date | str) -> date:
    if isinstance(value, datetime):
        raise PortfolioSnapshotAdapterError("as_of_date must be a date, not a datetime")
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise PortfolioSnapshotAdapterError(
            "as_of_date must be an ISO 8601 date"
        ) from exc


def _aware_utc(value: datetime | str, *, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value).strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise PortfolioSnapshotAdapterError(
                f"{field} must be a timezone-aware ISO 8601 timestamp"
            ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PortfolioSnapshotAdapterError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _effective_day_end(value: date) -> datetime:
    local = datetime.combine(value, time(23, 59, 59), tzinfo=_BUSINESS_TIMEZONE)
    return local.astimezone(timezone.utc)


def _open_read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"{path.resolve().as_uri()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    if int(connection.execute("PRAGMA query_only").fetchone()[0]) != 1:
        connection.close()
        raise PortfolioSnapshotAdapterError(
            "SQLite query_only could not be enabled"
        )
    return connection


def _schema_manifest(connection: sqlite3.Connection) -> tuple[dict[str, Any], str]:
    tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    missing_tables = sorted(set(_REQUIRED_COLUMNS) - tables)
    if missing_tables:
        raise PortfolioSnapshotAdapterError(
            f"portfolio database lacks required snapshot tables: {missing_tables}"
        )

    manifest: dict[str, Any] = {}
    for table_name, required in sorted(_REQUIRED_COLUMNS.items()):
        rows = [
            {
                "cid": int(row["cid"]),
                "name": str(row["name"]),
                "type": str(row["type"]),
                "notnull": int(row["notnull"]),
                "pk": int(row["pk"]),
            }
            for row in connection.execute(f'PRAGMA table_info("{table_name}")')
        ]
        columns = {row["name"] for row in rows}
        missing_columns = sorted(required - columns)
        if missing_columns:
            raise PortfolioSnapshotAdapterError(
                f"{table_name} lacks required columns: {missing_columns}"
            )
        manifest[table_name] = rows
    return manifest, sha256_text(canonical_json(manifest))


def _cash_schema_manifest(
    connection: sqlite3.Connection,
) -> tuple[list[dict[str, Any]], str]:
    tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    if "cash_balance_snapshots" not in tables:
        raise PortfolioSnapshotAdapterError(
            "portfolio database lacks cash_balance_snapshots"
        )
    rows = [
        {
            "cid": int(row["cid"]),
            "name": str(row["name"]),
            "type": str(row["type"]),
            "notnull": int(row["notnull"]),
            "pk": int(row["pk"]),
        }
        for row in connection.execute(
            'PRAGMA table_info("cash_balance_snapshots")'
        )
    ]
    missing = sorted(
        _CASH_REQUIRED_COLUMNS - {str(row["name"]) for row in rows}
    )
    if missing:
        raise PortfolioSnapshotAdapterError(
            f"cash_balance_snapshots lacks required columns: {missing}"
        )
    return rows, sha256_text(canonical_json(rows))


def _safe_lineage(value: object) -> Mapping[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, Mapping) else {}


def _parse_optional_known(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return _aware_utc(str(value), field="snapshot.knowledge_cutoff_at")
    except PortfolioSnapshotAdapterError:
        return None


def _position_quality(
    row: Mapping[str, Any],
    *,
    snapshot_as_of: date,
    snapshot_known_at: datetime,
    requested_knowledge_cutoff: datetime,
) -> dict[str, Any]:
    symbol = str(row.get("ts_code") or "").upper()
    lineage = _safe_lineage(row.get("lineage_json"))

    raw_price_lineage = lineage.get("price")
    price_lineage = (
        raw_price_lineage if isinstance(raw_price_lineage, Mapping) else {}
    )
    price_date: date | None = None
    if row.get("price_date"):
        try:
            price_date = date.fromisoformat(str(row["price_date"]))
        except ValueError:
            price_date = None
    price_known_at: datetime | None = None
    if price_lineage.get("known_at"):
        try:
            price_known_at = _aware_utc(
                str(price_lineage["known_at"]),
                field="position.price.known_at",
            )
        except PortfolioSnapshotAdapterError:
            price_known_at = None
    price_status = "available"
    price_reason: str | None = None
    if str(row.get("valuation_status") or "") == "unpriced":
        price_status = "missing"
        price_reason = "source_position_is_unpriced"
    elif row.get("price") in (None, "") or row.get("market_value") in (None, ""):
        price_status = "missing"
        price_reason = "price_or_market_value_missing"
    elif (
        price_date is None
        or price_date > snapshot_as_of
        or price_known_at is None
        or price_known_at > snapshot_known_at
        or price_known_at > requested_knowledge_cutoff
        or str(price_lineage.get("trade_date") or "")
        != str(row.get("price_date") or "")
        or str(price_lineage.get("source") or "")
        != str(row.get("price_source") or "")
    ):
        price_status = "missing"
        price_reason = "dual_time_price_lineage_unproven"

    raw_industry_lineage = lineage.get("industry")
    industry_lineage = (
        raw_industry_lineage
        if isinstance(raw_industry_lineage, Mapping)
        else {}
    )
    classification_status = "missing"
    classification_reason = "point_in_time_classification_unavailable"
    if industry_lineage.get("point_in_time") is True:
        candidate_name = str(row.get("industry_name") or "").strip()
        candidate_source = str(row.get("industry_source") or "").strip()
        lineage_name = str(industry_lineage.get("name") or "").strip()
        lineage_source = str(industry_lineage.get("source") or "").strip()
        updated_at: datetime | None = None
        if industry_lineage.get("updated_at"):
            try:
                updated_at = _aware_utc(
                    str(industry_lineage["updated_at"]),
                    field="position.industry.updated_at",
                )
            except PortfolioSnapshotAdapterError:
                updated_at = None
        if (
            candidate_name
            and candidate_name == lineage_name
            and candidate_source
            and candidate_source == lineage_source
            and updated_at is not None
            and updated_at
            <= min(
                _effective_day_end(snapshot_as_of),
                snapshot_known_at,
                requested_knowledge_cutoff,
            )
        ):
            classification_status = "available"
            classification_reason = None

    return {
        "symbol": symbol,
        "price_status": price_status,
        "price_reason": price_reason,
        "classification_status": classification_status,
        "classification_reason": classification_reason,
    }


def _snapshot_quality(
    connection: sqlite3.Connection,
    reference: Mapping[str, Any],
    *,
    requested_knowledge_cutoff: datetime,
) -> dict[str, Any]:
    snapshot_id = str(reference["snapshot_id"])
    row = connection.execute(
        "SELECT * FROM portfolio_snapshots WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchone()
    if row is None:
        raise PortfolioSnapshotAdapterError(
            f"snapshot reference disappeared during read: {snapshot_id}"
        )
    snapshot = dict(row)
    try:
        snapshot_as_of = date.fromisoformat(str(snapshot["as_of_date"]))
    except ValueError as exc:
        raise PortfolioSnapshotAdapterError(
            f"snapshot {snapshot_id} has invalid as_of_date"
        ) from exc
    snapshot_known_at = _parse_optional_known(snapshot["knowledge_cutoff_at"])
    if snapshot_known_at is None:
        raise PortfolioSnapshotAdapterError(
            f"snapshot {snapshot_id} lacks valid knowledge_cutoff_at"
        )

    position_rows = [
        dict(item)
        for item in connection.execute(
            """
            SELECT * FROM position_snapshots
            WHERE snapshot_id = ?
            ORDER BY ts_code
            """,
            (snapshot_id,),
        )
    ]
    position_quality = [
        _position_quality(
            item,
            snapshot_as_of=snapshot_as_of,
            snapshot_known_at=snapshot_known_at,
            requested_knowledge_cutoff=requested_knowledge_cutoff,
        )
        for item in position_rows
    ]
    missing_prices = sum(
        item["price_status"] == "missing" for item in position_quality
    )
    missing_classifications = sum(
        item["classification_status"] == "missing"
        for item in position_quality
    )
    cash_status = (
        "available"
        if str(snapshot.get("cash_status") or "") == "available"
        else "missing"
    )
    valuation_status = (
        "complete"
        if bool(snapshot.get("valuation_complete"))
        and missing_prices == 0
        and int(snapshot.get("position_count") or 0) == len(position_rows)
        else "partial"
    )
    classification_status = (
        "complete" if missing_classifications == 0 else "partial"
    )
    warnings: list[dict[str, Any]] = [
        {
            "code": "PORTFOLIO_CURSOR_SCOPE_LIMITED",
            "severity": "warning",
            "snapshot_id": snapshot_id,
            "message": (
                "No explicit account-wide cursor proof exists; the snapshot "
                "remains partition-scoped."
            ),
        }
    ]
    if cash_status == "missing":
        warnings.append(
            {
                "code": "CASH_UNAVAILABLE",
                "severity": "warning",
                "snapshot_id": snapshot_id,
                "message": "Snapshot cash is unavailable.",
            }
        )
    for item in position_quality:
        if item["price_status"] == "missing":
            warnings.append(
                {
                    "code": "MISSING_PRICE",
                    "severity": "warning",
                    "snapshot_id": snapshot_id,
                    "symbol": item["symbol"],
                    "message": (
                        "No cutoff-safe price with complete lineage is available."
                    ),
                }
            )
        if item["classification_status"] == "missing":
            warnings.append(
                {
                    "code": "MISSING_CLASSIFICATION",
                    "severity": "warning",
                    "snapshot_id": snapshot_id,
                    "symbol": item["symbol"],
                    "message": (
                        "No point-in-time classification with complete lineage "
                        "is available."
                    ),
                }
            )
    return {
        "snapshot_id": snapshot_id,
        "status": "partial",
        "cash_status": cash_status,
        "valuation_status": valuation_status,
        "classification_status": classification_status,
        "cursor_scope": "partition",
        "account_global_cursor_status": "missing",
        "position_count": len(position_rows),
        "missing_price_count": missing_prices,
        "missing_classification_count": missing_classifications,
        "positions": position_quality,
        "warnings": sorted(
            warnings,
            key=lambda item: (
                str(item.get("code") or ""),
                str(item.get("snapshot_id") or ""),
                str(item.get("symbol") or ""),
            ),
        ),
    }


def load_portfolio_snapshot_inventory(
    database: str | Path,
    *,
    account_id: str | None = None,
    as_of_date: date | str,
    knowledge_cutoff_at: datetime | str,
) -> dict[str, Any]:
    """Return cutoff-visible P2B snapshot references and explicit quality.

    The returned ``snapshot_references`` are ready to pass to the existing P2C
    episode builder.  They intentionally retain ``cursor_scope=partition`` and
    ``included_event_set_complete=false`` because the P2B source schema carries
    no account-wide cursor proof.
    """

    path = Path(database).resolve()
    account = str(account_id).strip() if account_id is not None else None
    if account_id is not None and not account:
        raise PortfolioSnapshotAdapterError(
            "account_id must be non-empty when provided"
        )
    effective_cutoff = _as_of_date(as_of_date)
    knowledge_cutoff = _aware_utc(
        knowledge_cutoff_at,
        field="knowledge_cutoff_at",
    )
    if not path.is_file():
        raise FileNotFoundError(path)

    source_hash_before = _sha256_file(path)
    connection = _open_read_only(path)
    data_version_before = int(
        connection.execute("PRAGMA data_version").fetchone()[0]
    )
    try:
        connection.execute("BEGIN")
        try:
            raw_references = load_p2b_snapshot_references(
                path,
                account=account,
            )
        except (
            EpisodeProjectionError,
            sqlite3.Error,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise PortfolioSnapshotAdapterError(
                f"could not load P2B snapshot references: {exc}"
            ) from exc
        quick_check_rows = [
            str(row[0]) for row in connection.execute("PRAGMA quick_check")
        ]
        if quick_check_rows != ["ok"]:
            raise PortfolioSnapshotAdapterError(
                f"portfolio database quick_check failed: {quick_check_rows}"
            )
        schema_manifest, schema_sha256 = _schema_manifest(connection)
        account_exists = (
            True
            if account is None
            else connection.execute(
                "SELECT 1 FROM accounts WHERE account_id = ?",
                (account,),
            ).fetchone()
            is not None
        )

        selected: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        for raw in raw_references:
            reference = dict(raw)
            reasons: list[str] = []
            try:
                snapshot_as_of = date.fromisoformat(
                    str(reference.get("as_of_date") or "")
                )
            except ValueError:
                reasons.append("invalid_effective_time")
                snapshot_as_of = None
            snapshot_known_at = _parse_optional_known(
                reference.get("knowledge_cutoff_at")
            )
            if snapshot_known_at is None:
                reasons.append("missing_or_invalid_knowledge_time")
            if snapshot_as_of is not None and snapshot_as_of > effective_cutoff:
                reasons.append("future_effective")
            if (
                snapshot_known_at is not None
                and snapshot_known_at > knowledge_cutoff
            ):
                reasons.append("future_known")
            if reasons:
                excluded.append(
                    {
                        "snapshot_id": str(reference.get("snapshot_id") or ""),
                        "reasons": sorted(set(reasons)),
                    }
                )
                continue
            reference["cursor_scope"] = "partition"
            reference["included_event_set_complete"] = False
            selected.append(reference)

        qualities = [
            _snapshot_quality(
                connection,
                reference,
                requested_knowledge_cutoff=knowledge_cutoff,
            )
            for reference in selected
        ]
        connection.execute("ROLLBACK")
        data_version_after = int(
            connection.execute("PRAGMA data_version").fetchone()[0]
        )
    finally:
        connection.close()

    source_hash_after = _sha256_file(path)
    if (
        source_hash_after != source_hash_before
        or data_version_after != data_version_before
    ):
        raise PortfolioSnapshotAdapterError(
            "portfolio database changed while the read-only inventory was being built"
        )

    warnings: list[dict[str, Any]] = []
    if not account_exists:
        warnings.append(
            {
                "code": "ACCOUNT_MISSING",
                "severity": "warning",
                "message": "The requested account is not present in the source database.",
            }
        )
    if not selected:
        warnings.append(
            {
                "code": "SNAPSHOT_MISSING",
                "severity": "warning",
                "message": (
                    "No existing P2B snapshot is visible under both requested "
                    "cutoffs; no historical snapshot was synthesized."
                ),
            }
        )
    if excluded:
        warnings.append(
            {
                "code": "SNAPSHOT_CUTOFF_EXCLUDED",
                "severity": "info",
                "message": (
                    f"{len(excluded)} existing snapshot(s) were excluded by "
                    "effective/knowledge-time rules."
                ),
            }
        )
    warnings.extend(
        warning
        for quality in qualities
        for warning in quality["warnings"]
    )
    warnings = sorted(
        warnings,
        key=lambda item: (
            str(item.get("code") or ""),
            str(item.get("snapshot_id") or ""),
            str(item.get("symbol") or ""),
        ),
    )

    cursor = {
        "cursor_scope": "partition",
        "included_event_set_complete": False,
        "account_global_cursor_status": "missing",
        "reason": (
            "The existing P2B reference contract contains no explicit "
            "account-wide cursor proof."
        ),
    }
    selection = {
        "account_id": account,
        "as_of_date": effective_cutoff.isoformat(),
        "knowledge_cutoff_at": _utc_text(knowledge_cutoff),
        "effective_rule": "snapshot.as_of_date<=as_of_date",
        "knowledge_rule": (
            "snapshot.knowledge_cutoff_at is present and "
            "<=knowledge_cutoff_at"
        ),
        "inventory_count": len(raw_references),
        "selected_count": len(selected),
        "excluded": sorted(
            excluded,
            key=lambda item: str(item.get("snapshot_id") or ""),
        ),
    }
    lineage = {
        "adapter_version": SNAPSHOT_ADAPTER_VERSION,
        "reference_loader": (
            "src.investment_review.episodes.load_p2b_snapshot_references"
        ),
        "source_path": str(path),
        "source_sha256_before": source_hash_before,
        "source_sha256_after": source_hash_after,
        "sqlite_data_version_before": data_version_before,
        "sqlite_data_version_after": data_version_after,
        "source_schema_sha256": schema_sha256,
        "source_schema": schema_manifest,
        "sqlite_mode": "ro",
        "query_only": True,
        "quick_check": "ok",
        "selection": selection,
        "selection_sha256": sha256_text(canonical_json(selected)),
    }
    payload: dict[str, Any] = {
        "schema_version": SNAPSHOT_INVENTORY_SCHEMA,
        "status": "missing" if not selected else "partial",
        "account_id": account,
        "snapshot_references": selected,
        "snapshot_quality": qualities,
        "cursor": cursor,
        "quality": {
            "status": "missing" if not selected else "partial",
            "warnings": warnings,
        },
        "lineage": lineage,
    }
    content_sha256 = sha256_text(canonical_json(payload))
    payload["content_sha256"] = content_sha256
    payload["content_id"] = f"snapshot_inventory_{content_sha256[:32]}"
    return payload


def _canonical_cash_row(row: Mapping[str, Any]) -> dict[str, Any]:
    try:
        amount = Decimal(str(row.get("amount") or ""))
    except InvalidOperation as exc:
        raise PortfolioSnapshotAdapterError(
            "cash snapshot amount must be a Decimal string"
        ) from exc
    if not amount.is_finite():
        raise PortfolioSnapshotAdapterError(
            "cash snapshot amount must be finite"
        )
    amount_text = format(amount, "f")
    if "." in amount_text:
        amount_text = amount_text.rstrip("0").rstrip(".")
    if amount_text in {"", "-0"}:
        amount_text = "0"
    try:
        as_of = date.fromisoformat(str(row.get("as_of_date") or ""))
    except ValueError as exc:
        raise PortfolioSnapshotAdapterError(
            "cash snapshot as_of_date must be an ISO date"
        ) from exc
    recorded = _aware_utc(
        row.get("recorded_at"),
        field="cash snapshot recorded_at",
    )
    note = str(row.get("note") or "")
    note_lower = note.casefold()
    pending_counts = [
        int(value)
        for value in re.findall(
            r"(?:^|[;\s])fee_pending_entries\s*=\s*([0-9]+)(?:$|[;\s])",
            note_lower,
        )
    ]
    fee_pending = (
        any(value > 0 for value in pending_counts)
        if pending_counts
        else (
            "fees_missing=true" in note_lower
            or "missing_source_column" in note_lower
            or "calculation_status=fee_pending" in note_lower
            or re.search(
                r"(?:^|[;\s])fee_pending(?:$|[;\s])",
                note_lower,
            )
            is not None
        )
    )
    payload = {
        "snapshot_id": str(row.get("snapshot_id") or ""),
        "account_id": str(row.get("account_id") or ""),
        "as_of_date": as_of.isoformat(),
        "effective_precision": "date",
        "amount": amount_text,
        "currency": "CNY",
        "source": str(row.get("source") or ""),
        "note": note,
        "recorded_at": _utc_text(recorded),
        "fee_pending": fee_pending,
    }
    if (
        not payload["snapshot_id"]
        or not payload["account_id"]
        or not payload["source"]
    ):
        raise PortfolioSnapshotAdapterError(
            "cash snapshot identity/source must be non-empty"
        )
    row_sha256 = sha256_text(canonical_json(payload))
    payload["row_content_id"] = f"sha256:{row_sha256}"
    payload["source_refs"] = [
        {
            "source_type": "cash_balance_snapshot",
            "source_id": payload["snapshot_id"],
            "effective_date": payload["as_of_date"],
            "effective_precision": "date",
            "recorded_at": payload["recorded_at"],
            "content_id": payload["row_content_id"],
        }
    ]
    return payload


def _select_cash_evidence(
    rows: list[dict[str, Any]],
    *,
    date_predicate: Any,
    missing_reason: str,
) -> dict[str, Any]:
    eligible = [
        row
        for row in rows
        if date_predicate(date.fromisoformat(str(row["as_of_date"])))
    ]
    if not eligible:
        return {
            "status": "missing",
            "reason": missing_reason,
            "row": None,
            "source_refs": [],
        }
    eligible.sort(
        key=lambda row: (
            date.fromisoformat(str(row["as_of_date"])),
            _aware_utc(row["recorded_at"], field="cash snapshot recorded_at"),
        ),
        reverse=True,
    )
    best_rank = (
        str(eligible[0]["as_of_date"]),
        str(eligible[0]["recorded_at"]),
    )
    tied = [
        row
        for row in eligible
        if (str(row["as_of_date"]), str(row["recorded_at"])) == best_rank
    ]
    distinct = {
        canonical_json(
            {
                key: row[key]
                for key in (
                    "snapshot_id",
                    "account_id",
                    "as_of_date",
                    "amount",
                    "source",
                    "note",
                    "recorded_at",
                )
            }
        )
        for row in tied
    }
    if len(distinct) > 1:
        refs = [
            ref
            for row in tied
            for ref in _canonical_cash_row(row)["source_refs"]
        ]
        return {
            "status": "ambiguous",
            "reason": "same-rank cash snapshots have conflicting content",
            "row": None,
            "source_refs": sorted(
                refs,
                key=lambda item: (
                    str(item.get("source_id") or ""),
                    str(item.get("content_id") or ""),
                ),
            ),
        }
    selected = _canonical_cash_row(tied[0])
    return {
        "status": "available",
        "reason": (
            "selected by effective date and cutoff-visible recorded time; "
            "snapshot UUID was not used as a business-order tie-break"
        ),
        "row": selected,
        "source_refs": deepcopy(selected["source_refs"]),
    }


def load_cash_baseline_proof(
    database: str | Path,
    *,
    account_id: str,
    as_of: datetime | str,
    knowledge_cutoff_at: datetime | str,
    pre_event_at: datetime | str,
) -> dict[str, Any]:
    """Read formal cash evidence without treating a same-day row as pre-event.

    A date-only cash row can prove a pre-event baseline only when its business
    date is strictly earlier than the first event's business date.  The latest
    cutoff-visible row through ``as_of`` is retained separately as checkpoint
    reconciliation evidence and is never promoted into the pre-event baseline.
    """

    path = Path(database).resolve()
    account = str(account_id).strip()
    if not account:
        raise PortfolioSnapshotAdapterError("account_id must be non-empty")
    if not path.is_file():
        raise FileNotFoundError(path)
    as_of_time = _aware_utc(as_of, field="as_of")
    knowledge_cutoff = _aware_utc(
        knowledge_cutoff_at, field="knowledge_cutoff_at"
    )
    pre_event_time = _aware_utc(pre_event_at, field="pre_event_at")
    if pre_event_time > as_of_time or as_of_time > knowledge_cutoff:
        raise PortfolioSnapshotAdapterError(
            "cash proof requires pre_event_at <= as_of <= knowledge_cutoff_at"
        )
    as_of_date = as_of_time.astimezone(_BUSINESS_TIMEZONE).date()
    pre_event_date = pre_event_time.astimezone(_BUSINESS_TIMEZONE).date()

    source_hash_before = _sha256_file(path)
    connection = _open_read_only(path)
    data_version_before = int(
        connection.execute("PRAGMA data_version").fetchone()[0]
    )
    invalid_rows: list[dict[str, str]] = []
    schema_error: str | None = None
    try:
        connection.execute("BEGIN")
        quick_check_rows = [
            str(row[0]) for row in connection.execute("PRAGMA quick_check")
        ]
        if quick_check_rows != ["ok"]:
            raise PortfolioSnapshotAdapterError(
                f"portfolio database quick_check failed: {quick_check_rows}"
            )
        try:
            schema, schema_sha256 = _cash_schema_manifest(connection)
        except PortfolioSnapshotAdapterError as exc:
            schema_error = str(exc)
            schema = []
            schema_sha256 = sha256_text(
                canonical_json(
                    {
                        "status": "missing",
                        "reason": schema_error,
                    }
                )
            )
            raw_rows = []
        else:
            raw_rows = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT snapshot_id, account_id, as_of_date, amount,
                           source, note, recorded_at
                    FROM cash_balance_snapshots
                    WHERE account_id = ?
                    ORDER BY as_of_date, recorded_at
                    """,
                    (account,),
                )
            ]
        visible: list[dict[str, Any]] = []
        for row in raw_rows:
            try:
                _canonical_cash_row(row)
                row_date = date.fromisoformat(str(row["as_of_date"]))
                recorded_at = _aware_utc(
                    row["recorded_at"], field="cash snapshot recorded_at"
                )
            except (PortfolioSnapshotAdapterError, ValueError) as exc:
                invalid_rows.append(
                    {
                        "snapshot_id": str(row.get("snapshot_id") or ""),
                        "reason": str(exc),
                    }
                )
                continue
            if row_date <= as_of_date and recorded_at <= knowledge_cutoff:
                normalized = dict(row)
                normalized["recorded_at"] = _utc_text(recorded_at)
                visible.append(normalized)
        baseline = _select_cash_evidence(
            visible,
            date_predicate=lambda value: value < pre_event_date,
            missing_reason=(
                "no cutoff-visible date-precision cash snapshot exists strictly "
                "before the first event business date"
            ),
        )
        checkpoint = _select_cash_evidence(
            visible,
            date_predicate=lambda value: value <= as_of_date,
            missing_reason=(
                "no cutoff-visible cash snapshot exists through checkpoint as_of"
            ),
        )
        connection.execute("ROLLBACK")
        data_version_after = int(
            connection.execute("PRAGMA data_version").fetchone()[0]
        )
    finally:
        connection.close()

    source_hash_after = _sha256_file(path)
    if (
        source_hash_after != source_hash_before
        or data_version_after != data_version_before
    ):
        raise PortfolioSnapshotAdapterError(
            "portfolio database changed while cash baseline proof was built"
        )
    source_ref = {
        "source_type": "portfolio_sqlite",
        "source_id": f"sha256:{source_hash_before}",
        "content_id": f"sha256:{source_hash_before}",
    }
    gaps: list[dict[str, Any]] = []
    if baseline["status"] != "available":
        gaps.append(
            {
                "axis": "snapshot_cash_valuation",
                "code": (
                    "CASH_BASELINE_AMBIGUOUS"
                    if baseline["status"] == "ambiguous"
                    else "CASH_BASELINE_MISSING"
                ),
                "severity": "warning",
                "owner": "data",
                "next_step": "record or reconcile an earlier explicit cash balance",
                "source_refs": baseline["source_refs"] or [source_ref],
            }
        )
    if invalid_rows:
        gaps.append(
            {
                "axis": "snapshot_cash_valuation",
                "code": "CASH_EVIDENCE_ROW_INVALID",
                "severity": "warning",
                "owner": "data",
                "next_step": "repair the invalid cash evidence row in its source workflow",
                "source_refs": [source_ref],
            }
        )
    if schema_error is not None:
        gaps.append(
            {
                "axis": "snapshot_cash_valuation",
                "code": "CASH_SOURCE_SCHEMA_MISSING",
                "severity": "warning",
                "owner": "data",
                "next_step": "provide the versioned cash evidence table in the source workflow",
                "source_refs": [source_ref],
            }
        )
    payload: dict[str, Any] = {
        "schema_version": CASH_BASELINE_PROOF_SCHEMA,
        "method_version": CASH_BASELINE_ADAPTER_VERSION,
        "content_id": "",
        "account_id": account,
        "as_of": _utc_text(as_of_time),
        "knowledge_cutoff": _utc_text(knowledge_cutoff),
        "pre_event_at": _utc_text(pre_event_time),
        "pre_event_baseline": baseline,
        "checkpoint_reconciliation": checkpoint,
        "invalid_rows": sorted(
            invalid_rows,
            key=lambda item: (
                item["snapshot_id"],
                item["reason"],
            ),
        ),
        "source_binding": {
            "source_path": str(path),
            "source_sha256_before": source_hash_before,
            "source_sha256_after": source_hash_after,
            "sqlite_data_version_before": data_version_before,
            "sqlite_data_version_after": data_version_after,
            "source_schema": schema,
            "source_schema_sha256": schema_sha256,
            "source_schema_status": (
                "missing" if schema_error is not None else "available"
            ),
            "source_schema_reason": schema_error,
            "sqlite_mode": "ro",
            "query_only": True,
            "quick_check": "ok",
            "visible_row_count": len(visible),
            "raw_row_count": len(raw_rows),
            "same_day_checkpoint_not_pre_baseline": True,
        },
        "gaps": sorted(
            gaps,
            key=lambda item: (
                str(item.get("axis") or ""),
                str(item.get("code") or ""),
            ),
        ),
        "source_refs": sorted(
            {
                canonical_json(ref): ref
                for ref in [
                    source_ref,
                    *baseline["source_refs"],
                    *checkpoint["source_refs"],
                ]
            }.values(),
            key=lambda item: (
                str(item.get("source_type") or ""),
                str(item.get("source_id") or ""),
                str(item.get("content_id") or ""),
            ),
        ),
    }
    baseline_row = (
        baseline.get("row")
        if isinstance(baseline.get("row"), Mapping)
        else None
    )
    if baseline["status"] == "available" and baseline_row is not None:
        row_recorded = _aware_utc(
            baseline_row["recorded_at"],
            field="cash baseline recorded_at",
        )
        row_refs = [
            str(item.get("content_id") or item.get("source_id") or "")
            for item in baseline.get("source_refs", [])
            if isinstance(item, Mapping)
            and str(item.get("content_id") or item.get("source_id") or "")
        ]
        fee_pending = bool(baseline_row.get("fee_pending"))
        cash_baseline = {
            "status": "partial" if fee_pending else "available",
            "value": str(baseline_row["amount"]),
            "currency": str(baseline_row.get("currency") or "CNY"),
            # The source proves only a business date.  Use the actual recorded
            # instant for the scalar timestamp instead of fabricating an
            # intraday effective time; the rich row retains date precision.
            "effective_at": _utc_text(row_recorded),
            "known_at": _utc_text(row_recorded),
            "recorded_at": _utc_text(row_recorded),
            "fee_pending": fee_pending,
            "method": "cash_balance_snapshot",
            "source_refs": sorted(set(row_refs)),
        }
    else:
        cash_baseline = {
            "status": "missing",
            "value": None,
            "currency": "CNY",
            "effective_at": None,
            "known_at": None,
            "recorded_at": None,
            "fee_pending": False,
            "method": "missing",
            "source_refs": [],
        }
    payload["baseline_proof"] = {
        "schema_version": LEDGER_SNAPSHOT_BASELINE_SCHEMA_VERSION,
        "position": {
            "status": "missing",
            "quantity": None,
            "cost_basis": None,
            "effective_at": None,
            "known_at": None,
            "method": "missing",
            "source_refs": [],
        },
        "cash": cash_baseline,
    }
    material = deepcopy(payload)
    material.pop("content_id", None)
    payload["content_id"] = (
        "sha256:" + sha256_text(canonical_json(material))
    )
    return payload


def attach_ledger_snapshot_reconstruction(
    inventory: Mapping[str, Any],
    reconstruction: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach one validated v3 ledger reconstruction without changing P2B refs.

    The existing P2B inventory and its partition cursor remain evidence in
    their original form.  The reconstruction is an additive, immutable
    projection with an independent status; it never masquerades as a persisted
    P2B snapshot or account-global cursor.
    """

    if not isinstance(inventory, Mapping):
        raise PortfolioSnapshotAdapterError("snapshot inventory must be an object")
    if inventory.get("schema_version") != SNAPSHOT_INVENTORY_SCHEMA:
        raise PortfolioSnapshotAdapterError("unsupported snapshot inventory schema")
    frozen = deepcopy(dict(inventory))
    supplied_content_id = frozen.pop("content_id", None)
    supplied_content_sha256 = frozen.pop("content_sha256", None)
    expected_sha256 = sha256_text(canonical_json(frozen))
    if (
        supplied_content_sha256 != expected_sha256
        or supplied_content_id != f"snapshot_inventory_{expected_sha256[:32]}"
    ):
        raise PortfolioSnapshotAdapterError(
            "snapshot inventory content identity is invalid"
        )
    if (
        not isinstance(reconstruction, Mapping)
        or reconstruction.get("schema_version")
        != LEDGER_SNAPSHOT_RECONSTRUCTION_SCHEMA_VERSION
    ):
        raise PortfolioSnapshotAdapterError(
            "unsupported ledger snapshot reconstruction schema"
        )
    try:
        envelope_availability = ledger_snapshot_reconstruction_availability(
            reconstruction
        )
        reconstruction_as_of = _aware_utc(
            reconstruction.get("as_of"),
            field="ledger_snapshot_reconstruction.as_of",
        )
        reconstruction_cutoff = _aware_utc(
            reconstruction.get("knowledge_cutoff"),
            field="ledger_snapshot_reconstruction.knowledge_cutoff",
        )
    except (EpisodeProjectionError, ValueError) as exc:
        raise PortfolioSnapshotAdapterError(str(exc)) from exc

    lineage = (
        inventory.get("lineage")
        if isinstance(inventory.get("lineage"), Mapping)
        else {}
    )
    selection = (
        lineage.get("selection")
        if isinstance(lineage.get("selection"), Mapping)
        else {}
    )
    inventory_as_of = _as_of_date(selection.get("as_of_date"))
    inventory_cutoff = _aware_utc(
        selection.get("knowledge_cutoff_at"),
        field="snapshot inventory knowledge_cutoff_at",
    )
    if reconstruction_as_of.astimezone(_BUSINESS_TIMEZONE).date() != inventory_as_of:
        raise PortfolioSnapshotAdapterError(
            "ledger reconstruction as_of does not match snapshot inventory"
        )
    if reconstruction_cutoff != inventory_cutoff:
        raise PortfolioSnapshotAdapterError(
            "ledger reconstruction knowledge_cutoff does not match snapshot inventory"
        )
    inventory_account = inventory.get("account_id")
    scope = (
        reconstruction.get("scope")
        if isinstance(reconstruction.get("scope"), Mapping)
        else {}
    )
    reconstruction_account = scope.get("account_id")
    if (
        inventory_account not in (None, "")
        and str(inventory_account) != str(reconstruction_account or "")
    ):
        raise PortfolioSnapshotAdapterError(
            "ledger reconstruction account does not match snapshot inventory"
        )

    result = deepcopy(dict(inventory))
    result["ledger_snapshot_reconstruction"] = deepcopy(dict(reconstruction))
    result["reconstruction_status"] = {
        "available": "available",
        "ambiguous": "partial",
        "missing": "missing",
        "invalid": "blocked",
    }[envelope_availability]
    result["reconstruction_binding"] = {
        "schema_version": LEDGER_SNAPSHOT_RECONSTRUCTION_SCHEMA_VERSION,
        "content_id": str(reconstruction.get("content_id") or ""),
        "episode_id": str(reconstruction.get("episode_id") or ""),
        "perspective": str(reconstruction.get("perspective") or ""),
        "as_of": _utc_text(reconstruction_as_of),
        "knowledge_cutoff": _utc_text(reconstruction_cutoff),
        "p2b_snapshot_references_unchanged": True,
        "p2b_cursor_not_promoted": True,
    }
    material = deepcopy(result)
    material.pop("content_id", None)
    material.pop("content_sha256", None)
    content_sha256 = sha256_text(canonical_json(material))
    result["content_sha256"] = content_sha256
    result["content_id"] = f"snapshot_inventory_{content_sha256[:32]}"
    return result


def inspect_portfolio_snapshots(
    portfolio_db: str | Path,
    *,
    as_of: date | str,
    knowledge_cutoff: datetime | str,
    account: str | None = None,
    ledger_reconstruction: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Stable runner-facing alias for the read-only inventory operation."""

    inventory = load_portfolio_snapshot_inventory(
        portfolio_db,
        account_id=account,
        as_of_date=as_of,
        knowledge_cutoff_at=knowledge_cutoff,
    )
    if ledger_reconstruction is None:
        return inventory
    return attach_ledger_snapshot_reconstruction(
        inventory, ledger_reconstruction
    )


class PortfolioSnapshotAdapter:
    """Small stable service wrapper used by the P3 facts-only runner."""

    def __init__(self, database: str | Path) -> None:
        self.database = Path(database).resolve()

    def load(
        self,
        *,
        account_id: str | None = None,
        as_of_date: date | str,
        knowledge_cutoff_at: datetime | str,
        ledger_reconstruction: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        inventory = load_portfolio_snapshot_inventory(
            self.database,
            account_id=account_id,
            as_of_date=as_of_date,
            knowledge_cutoff_at=knowledge_cutoff_at,
        )
        if ledger_reconstruction is None:
            return inventory
        return attach_ledger_snapshot_reconstruction(
            inventory, ledger_reconstruction
        )
