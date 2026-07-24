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
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from .episodes import EpisodeProjectionError, load_p2b_snapshot_references
from .models import canonical_json, sha256_text


SNAPSHOT_INVENTORY_SCHEMA = "investment_review.portfolio_snapshot_inventory.v1"
SNAPSHOT_ADAPTER_VERSION = "portfolio_snapshot_adapter_v1"
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


def inspect_portfolio_snapshots(
    portfolio_db: str | Path,
    *,
    as_of: date | str,
    knowledge_cutoff: datetime | str,
    account: str | None = None,
) -> dict[str, Any]:
    """Stable runner-facing alias for the read-only inventory operation."""

    return load_portfolio_snapshot_inventory(
        portfolio_db,
        account_id=account,
        as_of_date=as_of,
        knowledge_cutoff_at=knowledge_cutoff,
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
    ) -> dict[str, Any]:
        return load_portfolio_snapshot_inventory(
            self.database,
            account_id=account_id,
            as_of_date=as_of_date,
            knowledge_cutoff_at=knowledge_cutoff_at,
        )
