"""Safe, deterministic synchronization from the portfolio ledger.

The portfolio database is always opened through SQLite ``mode=ro`` with
``query_only`` enabled.  All mutable state belongs to an explicitly selected,
already initialized review sidecar.  A dry run validates the same reviewed
mapping as an apply run and never creates or modifies the sidecar.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .fee_estimation import (
    FeeObservation,
    build_fee_profile,
    estimate_fee,
)
from .ingest import (
    MappingError,
    _load_mapping_with_snapshot,
    reviewed_mapping_content_sha256,
    rows_to_events,
    source_from_config,
)
from .introspection import quote_identifier, table_schema_sha256
from .models import CanonicalTradeEvent, SourceDefinition, canonical_json, sha256_text
from .store import (
    PRODUCT_COMPLETION_SCHEMA_VERSION,
    ReviewStore,
    ReviewStoreError,
)


SYNC_RECEIPT_SCHEMA_VERSION = "investment_review.sync_receipt.v1"
SYNC_STATUS_SCHEMA_VERSION = "investment_review.sync_status.v1"
FEE_RECEIPT_SCHEMA_VERSION = "investment_review.fee_projection_receipt.v1"
DEFAULT_REVIEW_DB_ENV = "INVESTMENT_REVIEW_DB"


class SyncServiceError(RuntimeError):
    """Raised when the synchronization safety contract cannot be proven."""


class SyncConflictError(SyncServiceError):
    """Raised for identity, content, snapshot, or reconciliation drift."""


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_repo_root(value: str | Path | None) -> Path:
    root = Path(value) if value is not None else _default_repo_root()
    return root.expanduser().resolve()


def _resolve_under_root(value: str | Path, *, repo_root: Path) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


def resolve_review_db(
    *,
    explicit: str | Path | None = None,
    repo_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Resolve one canonical sidecar path without consulting the current cwd.

    Precedence is explicit CLI/service input, ``INVESTMENT_REVIEW_DB``, then the
    repository-local production default.  Relative values are always relative
    to the repository root.
    """

    root = _resolve_repo_root(repo_root)
    environment = os.environ if env is None else env
    configured = explicit
    if configured is None or not str(configured).strip():
        configured = environment.get(DEFAULT_REVIEW_DB_ENV)
    if configured is None or not str(configured).strip():
        configured = Path("data") / "db" / "investment_review.sqlite3"
    resolved = _resolve_under_root(configured, repo_root=root)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SyncServiceError(
            "Review sidecar must remain inside the selected repository checkout: "
            f"repo_root={root}, review_db={resolved}"
        ) from exc
    return resolved


def _resolve_mapping_path(
    value: str | Path | None, *, repo_root: Path
) -> Path:
    configured = (
        value
        if value is not None and str(value).strip()
        else Path("config") / "investment_review.portfolio.reviewed.json"
    )
    return _resolve_under_root(configured, repo_root=repo_root)


def _same_path(left: Path, right: Path) -> bool:
    try:
        if left.exists() and right.exists():
            return os.path.samefile(left, right)
    except OSError:
        pass
    return left.resolve() == right.resolve()


def _file_snapshot(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        stat = os.fstat(handle.fileno())
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return {
        "path": str(path.resolve()),
        "sha256": digest.hexdigest(),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _same_snapshot(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return all(left.get(key) == right.get(key) for key in ("sha256", "size_bytes", "mtime_ns"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _absolute_from_review(value: object, *, repo_root: Path) -> Path:
    text = str(value or "").strip()
    if not text:
        raise MappingError("Reviewed mapping provenance path is missing")
    return _resolve_under_root(text, repo_root=repo_root)


def _configured_source_path(value: object, *, repo_root: Path) -> Path:
    text = str(value or "").strip()
    if not text:
        raise MappingError("Reviewed mapping source path is missing")
    return _resolve_under_root(text, repo_root=repo_root)


def _require_strict_reviewed_mapping(
    config: dict[str, Any],
    *,
    source_db: Path,
    table: str,
    repo_root: Path,
) -> str:
    """Apply the repository's reviewed mapping lock with repo-root paths.

    ``ingest._require_reviewed_sqlite_mapping`` historically resolves relative
    provenance paths from the process cwd.  The product service must be stable
    from any cwd, so this function enforces the same lock while resolving every
    relative artifact against the repository root.
    """

    review = config.get("review")
    if not isinstance(review, dict) or str(review.get("status", "")).lower() != "reviewed":
        raise MappingError(
            "SQLite sync requires review.status='reviewed'; generated mappings are dry-run suggestions only"
        )
    for field in ("reviewed_at", "reviewed_by"):
        if not str(review.get(field, "")).strip():
            raise MappingError(f"Reviewed mapping is missing review.{field}")

    expected_content = str(review.get("mapping_content_sha256", "")).lower()
    actual_content = reviewed_mapping_content_sha256(config)
    if len(expected_content) != 64 or actual_content != expected_content:
        raise MappingError(
            "Reviewed mapping content hash mismatch: "
            f"expected={expected_content or 'missing'}, actual={actual_content}"
        )

    for prefix in ("schema_manifest", "generated_mapping"):
        artifact = _absolute_from_review(
            review.get(f"{prefix}_path"), repo_root=repo_root
        )
        expected = str(review.get(f"{prefix}_sha256", "")).lower()
        if len(expected) != 64:
            raise MappingError(f"Reviewed mapping is missing review.{prefix}_sha256")
        if not artifact.is_file():
            raise MappingError(f"Reviewed mapping provenance file does not exist: {artifact}")
        actual = _file_snapshot(artifact)["sha256"]
        if actual != expected:
            raise MappingError(
                f"Reviewed mapping provenance hash mismatch for {artifact}: "
                f"expected={expected}, actual={actual}"
            )

    source_config = config.get("source")
    if not isinstance(source_config, dict):
        raise MappingError("Reviewed mapping is missing source")
    configured_source = _configured_source_path(
        source_config.get("uri"), repo_root=repo_root
    )
    if not _same_path(source_db, configured_source):
        raise MappingError(
            "SQLite sync source does not match reviewed source.uri; rerun doctor and review"
        )
    if source_config.get("read_only") is not True:
        raise MappingError("Reviewed SQLite source must set source.read_only=true")

    generated = config.get("generated_from")
    if not isinstance(generated, dict):
        raise MappingError("Reviewed SQLite mapping is missing generated_from provenance")
    generated_source = _configured_source_path(
        generated.get("database"), repo_root=repo_root
    )
    if not _same_path(source_db, generated_source):
        raise MappingError(
            "SQLite sync source does not match generated_from.database"
        )
    if str(generated.get("table", "")) != table:
        raise MappingError("sqlite.table does not match generated_from.table")
    expected_schema = str(generated.get("table_schema_sha256", "")).lower()
    if len(expected_schema) != 64:
        raise MappingError(
            "Reviewed SQLite mapping is missing generated_from.table_schema_sha256"
        )
    return expected_schema


def _validate_composed_identities(
    rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any]
) -> None:
    mapping = config.get("mapping")
    if not isinstance(mapping, Mapping):
        raise MappingError("Reviewed mapping has no mapping object")
    record_spec = mapping.get("record_id")
    if isinstance(record_spec, Mapping) and isinstance(record_spec.get("join"), list):
        for row_number, row in enumerate(rows, start=1):
            for component in record_spec["join"]:
                if isinstance(component, str) and str(row.get(component) or "").strip() == "":
                    raise SyncConflictError(
                        "Source identity component is blank: "
                        f"row={row_number}, component={component}"
                    )


@dataclass(frozen=True)
class _SourceSnapshot:
    source: SourceDefinition
    events: tuple[CanonicalTradeEvent, ...]
    asset_types: Mapping[str, str]
    table: str
    table_schema_sha256: str
    mapping_snapshot: Mapping[str, Any]
    source_file: Mapping[str, Any]
    quick_check: str
    cutoff: Mapping[str, Any]


def _cutoff(
    events: Sequence[CanonicalTradeEvent],
    *,
    source_id: str,
    table: str,
    table_schema_sha256: str,
    mapping_sha256: str,
    asset_types: Mapping[str, str],
) -> dict[str, Any]:
    identities = [str(event.source_record_id) for event in events]
    content = [
        {
            "source_record_id": event.source_record_id,
            "event_id": event.event_id,
            "payload_sha256": event.payload_sha256,
        }
        for event in events
    ]
    identity_sha256 = sha256_text(canonical_json(identities))
    content_sha256 = sha256_text(canonical_json(content))
    relevant_asset_types = {
        symbol: str(asset_types.get(symbol) or "")
        for symbol in sorted({event.symbol for event in events})
    }
    material = {
        "source_id": source_id,
        "table": table,
        "table_schema_sha256": table_schema_sha256,
        "mapping_sha256": mapping_sha256,
        "source_seen": len(events),
        "identity_sha256": identity_sha256,
        "content_sha256": content_sha256,
        "asset_type_sha256": sha256_text(canonical_json(relevant_asset_types)),
    }
    return {
        "cutoff_id": f"sync_cutoff_{sha256_text(canonical_json(material))[:24]}",
        **material,
        "max_occurred_at": max((event.occurred_at for event in events), default=None),
        "max_known_at": max((event.known_at for event in events), default=None),
    }


def _open_read_only(path: Path) -> sqlite3.Connection:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    query_only = int(conn.execute("PRAGMA query_only").fetchone()[0])
    if query_only != 1:
        conn.close()
        raise SyncServiceError("SQLite query_only could not be enabled")
    return conn


def _read_source_snapshot(
    source_db: Path,
    mapping_path: Path,
    *,
    repo_root: Path,
) -> _SourceSnapshot:
    if not source_db.is_file():
        raise FileNotFoundError(source_db)
    if not mapping_path.is_file():
        raise FileNotFoundError(mapping_path)

    config, mapping_snapshot = _load_mapping_with_snapshot(mapping_path)
    sqlite_config = config.get("sqlite")
    if not isinstance(sqlite_config, dict) or not str(sqlite_config.get("table", "")).strip():
        raise MappingError("SQLite mapping must contain sqlite.table")
    table = str(sqlite_config["table"])
    expected_schema = _require_strict_reviewed_mapping(
        config,
        source_db=source_db,
        table=table,
        repo_root=repo_root,
    )
    source = source_from_config(config, source_uri=str(source_db.resolve()))
    before = _file_snapshot(source_db)

    conn = _open_read_only(source_db)
    try:
        conn.execute("BEGIN")
        quick_check = str(conn.execute("PRAGMA quick_check").fetchone()[0])
        if quick_check.lower() != "ok":
            raise SyncServiceError(f"Portfolio SQLite quick_check failed: {quick_check}")
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        if table not in tables:
            raise MappingError(f"Table {table!r} does not exist in {source_db}")
        schema_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        columns = [
            dict(row)
            for row in conn.execute(
                f"PRAGMA table_info({quote_identifier(table)})"
            ).fetchall()
        ]
        actual_schema = table_schema_sha256(
            columns, schema_row[0] if schema_row is not None else None
        )
        if actual_schema != expected_schema:
            raise MappingError(
                "Reviewed SQLite table schema hash mismatch: "
                f"expected={expected_schema}, actual={actual_schema}"
            )
        rows = [
            dict(row)
            for row in conn.execute(
                f"SELECT * FROM {quote_identifier(table)}"
            ).fetchall()
        ]
        asset_types: dict[str, str] = {}
        if "instruments" in tables:
            instrument_columns = {
                str(row[1])
                for row in conn.execute("PRAGMA table_info(instruments)").fetchall()
            }
            if {"ts_code", "asset_type"}.issubset(instrument_columns):
                asset_types = {
                    str(row["ts_code"]).strip().upper(): str(row["asset_type"] or "").strip().lower()
                    for row in conn.execute(
                        "SELECT ts_code, asset_type FROM instruments"
                    ).fetchall()
                }
        conn.rollback()
    finally:
        conn.close()

    after = _file_snapshot(source_db)
    if not _same_snapshot(before, after):
        raise SyncConflictError("Portfolio SQLite changed while one sync snapshot was being read")
    mapping_after = _file_snapshot(mapping_path)
    if not _same_snapshot(mapping_snapshot, mapping_after):
        raise SyncConflictError("Reviewed mapping changed while one sync snapshot was being read")

    _validate_composed_identities(rows, config)
    events = tuple(sorted(rows_to_events(rows, config=config, source=source), key=lambda item: item.event_id))
    record_ids = [str(event.source_record_id or "").strip() for event in events]
    if any(not record_id for record_id in record_ids):
        raise SyncConflictError("Source contains a blank canonical record identity")
    if len(set(record_ids)) != len(record_ids):
        raise SyncConflictError("Source contains duplicate canonical record identities")
    event_ids = [event.event_id for event in events]
    if len(set(event_ids)) != len(event_ids):
        raise SyncConflictError("Source contains duplicate canonical event identities")

    return _SourceSnapshot(
        source=source,
        events=events,
        asset_types=asset_types,
        table=table,
        table_schema_sha256=actual_schema,
        mapping_snapshot=mapping_snapshot,
        source_file=before,
        quick_check=quick_check,
        cutoff=_cutoff(
            events,
            source_id=source.source_id,
            table=table,
            table_schema_sha256=actual_schema,
            mapping_sha256=str(mapping_snapshot["sha256"]),
            asset_types=asset_types,
        ),
    )


def _sidecar_rows(path: Path, source_id: str) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    conn = _open_read_only(path)
    try:
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "trade_events" not in tables:
            return {}
        rows = conn.execute(
            "SELECT event_id, source_record_id, payload_sha256 "
            "FROM trade_events WHERE source_id = ? ORDER BY event_id",
            (source_id,),
        ).fetchall()
        return {str(row["event_id"]): dict(row) for row in rows}
    finally:
        conn.close()


def _reconcile(snapshot: _SourceSnapshot, sidecar: Path) -> dict[str, Any]:
    expected = {
        event.event_id: {
            "event_id": event.event_id,
            "source_record_id": event.source_record_id,
            "payload_sha256": event.payload_sha256,
        }
        for event in snapshot.events
    }
    actual = _sidecar_rows(sidecar, snapshot.source.source_id)
    missing = sorted(set(expected).difference(actual))
    unexpected = sorted(set(actual).difference(expected))
    divergent = sorted(
        event_id
        for event_id in set(expected).intersection(actual)
        if expected[event_id] != actual[event_id]
    )
    unsynced = len(missing) + len(unexpected) + len(divergent)
    return {
        "source_seen": len(expected),
        "sidecar_seen": len(actual),
        "matched": len(expected) - len(missing) - len(divergent),
        "unsynced": unsynced,
        "missing_count": len(missing),
        "unexpected_count": len(unexpected),
        "divergent_count": len(divergent),
        "missing_sample": missing[:10],
        "unexpected_sample": unexpected[:10],
        "divergent_sample": divergent[:10],
    }


def _fee_source_details(event: CanonicalTradeEvent) -> tuple[str, str | None]:
    source_row = event.raw_payload.get("source_row")
    note = str(source_row.get("note") or "") if isinstance(source_row, Mapping) else ""
    fields: dict[str, str] = {}
    for part in note.split(";"):
        key, separator, value = part.strip().partition("=")
        if separator and key.strip():
            fields[key.strip().lower()] = value.strip()
    fee_source = fields.get("fee_source", "").lower()
    fee_rule = fields.get("fee_rule")
    if fee_source in {"broker_actual", "rule_derived", "formal_exemption"}:
        return fee_source, fee_rule
    if fields.get("fees_inferred_from_net_amount", "").lower() == "true":
        return "broker_actual", fee_rule
    if "fee_backfilled_exact" in fields:
        return "broker_actual", fee_rule
    if fields.get("fee_backfilled_rule", "").lower() == "true":
        return "rule_derived", fee_rule
    if fee_rule:
        return (
            "formal_exemption" if "exempt" in fee_rule.lower() else "rule_derived",
            fee_rule,
        )
    return "unknown", None


def _fee_observations(
    snapshot: _SourceSnapshot,
) -> tuple[tuple[FeeObservation, ...], dict[str, CanonicalTradeEvent]]:
    events_by_id = {event.event_id: event for event in snapshot.events}
    observations = []
    for event in snapshot.events:
        if event.side not in {"BUY", "SELL"}:
            continue
        fee_source, fee_rule = _fee_source_details(event)
        source_fee_actual = fee_source == "broker_actual"
        observations.append(
            FeeObservation.build(
                event_id=event.event_id,
                account_id=event.account,
                asset_type=snapshot.asset_types.get(event.symbol),
                side=event.side,
                gross_amount=event.gross_amount,
                source_fees=event.fees,
                source_fee_actual=source_fee_actual,
                currency=event.currency,
                source_fee_provenance={
                    "source_id": snapshot.source.source_id,
                    "source_record_id": event.source_record_id,
                    "source_table": snapshot.table,
                    "source_field": "fees",
                    "explicit_positive": bool(event.fees is not None and event.fees > 0),
                    "fee_source": fee_source,
                    "fee_rule": fee_rule,
                },
            )
        )
    return tuple(sorted(observations, key=lambda item: item.event_id)), events_by_id


@dataclass(frozen=True)
class _FeePlan:
    profiles: tuple[Mapping[str, Any], ...]
    projections: tuple[Mapping[str, Any], ...]
    status_counts: Mapping[str, int]


def _build_fee_plan(snapshot: _SourceSnapshot) -> _FeePlan:
    observations, events_by_id = _fee_observations(snapshot)
    profiles: dict[str, Mapping[str, Any]] = {}
    projections: list[Mapping[str, Any]] = []

    for target in observations:
        target_event = events_by_id[target.event_id]
        historical = tuple(
            sample
            for sample in observations
            if events_by_id[sample.event_id].occurred_at <= target_event.occurred_at
            and events_by_id[sample.event_id].known_at <= target_event.known_at
        )
        projection = estimate_fee(target, historical)
        projection_payload = projection.to_dict()
        projection_payload["projected_at"] = target_event.known_at
        projections.append(projection_payload)

        if projection.profile_id is not None:
            profile = build_fee_profile(
                historical,
                account_id=target.account_id,
                asset_type=target.asset_type,
                side=target.side,
            )
            if profile is None or profile.profile_id != projection.profile_id:
                raise SyncConflictError(
                    f"Fee profile replay mismatch for event_id={target.event_id}"
                )
            sample_known_at = [
                events_by_id[event_id].known_at for event_id in profile.sample_event_ids
            ]
            profile_payload = profile.to_dict()
            profile_payload["computed_at"] = max(sample_known_at)
            prior = profiles.get(profile.profile_id)
            if prior is not None and canonical_json(prior) != canonical_json(profile_payload):
                raise SyncConflictError(
                    f"Fee profile content drift for profile_id={profile.profile_id}"
                )
            profiles[profile.profile_id] = profile_payload

    counts = Counter(str(item["status"]) for item in projections)
    return _FeePlan(
        profiles=tuple(profiles[key] for key in sorted(profiles)),
        projections=tuple(sorted(projections, key=lambda item: str(item["event_id"]))),
        status_counts={status: int(counts.get(status, 0)) for status in ("actual", "estimated", "unknown")},
    )


def _persist_fee_plan(store: ReviewStore, plan: _FeePlan) -> dict[str, Any]:
    saved = store.save_fee_plan(plan.profiles, plan.projections)
    profile_outcomes = Counter(
        str(result["status"]).lower() for result in saved["profiles"]
    )
    projection_outcomes = Counter(
        str(result["status"]).lower() for result in saved["projections"]
    )
    return {
        "status_counts": dict(plan.status_counts),
        "profile_count": len(plan.profiles),
        "projection_count": len(plan.projections),
        "profiles_inserted": int(profile_outcomes["inserted"]),
        "profiles_skipped": int(profile_outcomes["skipped"]),
        "projections_inserted": int(projection_outcomes["inserted"]),
        "projections_skipped": int(projection_outcomes["skipped"]),
    }


def _fee_preview(plan: _FeePlan) -> dict[str, Any]:
    return {
        "status_counts": dict(plan.status_counts),
        "profile_count": len(plan.profiles),
        "projection_count": len(plan.projections),
        "profiles_inserted": 0,
        "profiles_skipped": 0,
        "projections_inserted": 0,
        "projections_skipped": 0,
    }


class ReviewSyncService:
    """Read-only portfolio sync plus deterministic fee projection."""

    def __init__(
        self,
        portfolio_db: str | Path,
        *,
        review_db: str | Path | None = None,
        mapping_path: str | Path | None = None,
        repo_root: str | Path | None = None,
    ) -> None:
        self.repo_root = _resolve_repo_root(repo_root)
        self.portfolio_db = _resolve_under_root(portfolio_db, repo_root=self.repo_root)
        self.review_db = resolve_review_db(
            explicit=review_db, repo_root=self.repo_root
        )
        self.mapping_path = _resolve_mapping_path(
            mapping_path, repo_root=self.repo_root
        )
        if _same_path(self.portfolio_db, self.review_db):
            raise SyncServiceError(
                "Source portfolio database and review sidecar must be different files"
            )

    def _snapshot(self) -> _SourceSnapshot:
        return _read_source_snapshot(
            self.portfolio_db, self.mapping_path, repo_root=self.repo_root
        )

    def _require_apply_store(self) -> ReviewStore:
        if not self.review_db.is_file():
            raise ReviewStoreError(
                "Review sidecar does not exist; explicitly initialize the candidate sidecar first"
            )
        store = ReviewStore(self.review_db)
        status = store.status()
        if status.get("product_completion_schema_version") != PRODUCT_COMPLETION_SCHEMA_VERSION:
            raise ReviewStoreError(
                "Product-completion schema is not initialized; explicitly run product-init first"
            )
        return store

    @staticmethod
    def _source_section(snapshot: _SourceSnapshot) -> dict[str, Any]:
        return {
            "path": snapshot.source_file["path"],
            "mode": "ro",
            "query_only": True,
            "quick_check": snapshot.quick_check,
            "table": snapshot.table,
            "table_schema_sha256": snapshot.table_schema_sha256,
            "sha256": snapshot.source_file["sha256"],
            "mapping_path": snapshot.mapping_snapshot["path"],
            "mapping_sha256": snapshot.mapping_snapshot["sha256"],
            "source_id": snapshot.source.source_id,
            "cutoff": dict(snapshot.cutoff),
        }

    def _save_run(self, store: ReviewStore, snapshot: _SourceSnapshot, *, trigger: str) -> str:
        run_id = f"reviewrun_{uuid.uuid4().hex}"
        requested_at = _utc_now()
        store.save_review_run(
            {
                "run_id": run_id,
                "run_key": f"sync:{snapshot.cutoff['cutoff_id']}:{run_id}",
                "scope": "sync",
                "requested_at": requested_at,
                "source_cutoff": snapshot.cutoff.get("max_known_at"),
                "trigger": str(trigger or "manual"),
                "parameters": {
                    "portfolio_db": str(self.portfolio_db),
                    "review_db": str(self.review_db),
                    "mapping_path": str(self.mapping_path),
                    "cutoff": dict(snapshot.cutoff),
                },
            }
        )
        return run_id

    @staticmethod
    def _save_run_status(
        store: ReviewStore,
        run_id: str,
        status: str,
        details: Mapping[str, Any],
    ) -> None:
        timestamp = _utc_now()
        store.append_review_run_status(
            {
                "run_event_id": f"runstatus_{uuid.uuid4().hex}",
                "run_id": run_id,
                "status": status,
                "occurred_at": timestamp,
                "known_at": timestamp,
                "details": dict(details),
            }
        )

    def sync(self, *, dry_run: bool = False, trigger: str = "manual") -> dict[str, Any]:
        snapshot = self._snapshot()
        before = _reconcile(snapshot, self.review_db)
        plan = _build_fee_plan(snapshot)
        if dry_run:
            return {
                "schema_version": SYNC_RECEIPT_SCHEMA_VERSION,
                "status": "dry_run",
                "mode": "dry_run",
                "source": self._source_section(snapshot),
                "sidecar": {
                    "path": str(self.review_db),
                    "exists": self.review_db.is_file(),
                    "mutated": False,
                },
                "counts": {
                    **before,
                    "inserted": 0,
                    "skipped": 0,
                },
                "fees": _fee_preview(plan),
                "run": None,
            }

        store = self._require_apply_store()
        attempts: list[dict[str, Any]] = []
        event_totals = Counter()
        fee_totals = Counter()

        # A portfolio commit may land after the first read-only snapshot but
        # before review-side reconciliation finishes.  One bounded retry is
        # allowed by the frozen contract; a second moving cutoff is a visible
        # data blocker rather than an unbounded loop.
        for attempt_number in (1, 2):
            if attempt_number > 1:
                before = _reconcile(snapshot, self.review_db)
                plan = _build_fee_plan(snapshot)
            run_id = self._save_run(store, snapshot, trigger=trigger)
            terminal_status_recorded = False
            try:
                imported = store.import_events(
                    snapshot.source,
                    snapshot.events,
                    manifest={
                        "adapter": "investment_review_sync_service",
                        "source_path": str(self.portfolio_db),
                        "table": snapshot.table,
                        "mapping_path": str(self.mapping_path),
                        "mapping_sha256": snapshot.mapping_snapshot["sha256"],
                        "row_count": len(snapshot.events),
                        "read_only": True,
                        "query_only": True,
                        "source_sha256": snapshot.source_file["sha256"],
                        "cutoff": dict(snapshot.cutoff),
                        "attempt_number": attempt_number,
                    },
                )
                after = _reconcile(snapshot, self.review_db)
                if after["unsynced"] != 0 or after["source_seen"] != after["sidecar_seen"]:
                    raise SyncConflictError(
                        "Sidecar reconciliation failed after import: "
                        f"source_seen={after['source_seen']}, "
                        f"sidecar_seen={after['sidecar_seen']}, unsynced={after['unsynced']}"
                    )
                fees = _persist_fee_plan(store, plan)
                event_totals.update(
                    inserted=int(imported.get("inserted", 0)),
                    skipped=int(imported.get("skipped", 0)),
                )
                fee_totals.update(
                    profiles_inserted=int(fees.get("profiles_inserted", 0)),
                    profiles_skipped=int(fees.get("profiles_skipped", 0)),
                    projections_inserted=int(fees.get("projections_inserted", 0)),
                    projections_skipped=int(fees.get("projections_skipped", 0)),
                )

                latest = self._snapshot()
                attempt_details = {
                    "attempt_number": attempt_number,
                    "cutoff": dict(snapshot.cutoff),
                    "reconciliation": after,
                    "inserted": int(imported.get("inserted", 0)),
                    "skipped": int(imported.get("skipped", 0)),
                    "fee_status_counts": fees["status_counts"],
                }
                if latest.cutoff["cutoff_id"] != snapshot.cutoff["cutoff_id"]:
                    attempt_details["next_cutoff"] = dict(latest.cutoff)
                    if attempt_number == 1:
                        attempt_details["retry_required"] = True
                        self._save_run_status(store, run_id, "partial", attempt_details)
                        attempts.append({**attempt_details, "status": "partial"})
                        snapshot = latest
                        continue

                    attempt_details.update(
                        {
                            "data_blocker": "SOURCE_CONTINUED_CHANGING_DURING_SYNC",
                            "retry_required": False,
                        }
                    )
                    self._save_run_status(store, run_id, "blocked", attempt_details)
                    terminal_status_recorded = True
                    raise SyncConflictError(
                        "Portfolio source continued to change across two sync attempts; "
                        "recorded data blocker SOURCE_CONTINUED_CHANGING_DURING_SYNC"
                    )

                self._save_run_status(store, run_id, "succeeded", attempt_details)
                attempts.append({**attempt_details, "status": "succeeded"})
            except Exception as exc:
                if not terminal_status_recorded:
                    try:
                        self._save_run_status(
                            store,
                            run_id,
                            "failed",
                            {
                                "attempt_number": attempt_number,
                                "cutoff": dict(snapshot.cutoff),
                                "error_type": type(exc).__name__,
                                "error": str(exc),
                            },
                        )
                    except Exception:
                        pass
                raise

            fee_result = {
                **fees,
                **{key: int(value) for key, value in fee_totals.items()},
            }
            return {
                "schema_version": SYNC_RECEIPT_SCHEMA_VERSION,
                "status": "succeeded",
                "mode": "apply",
                "source": self._source_section(snapshot),
                "sidecar": {
                    "path": str(self.review_db),
                    "exists": True,
                    "mutated": True,
                    "product_completion_schema_version": PRODUCT_COMPLETION_SCHEMA_VERSION,
                },
                "counts": {
                    **after,
                    "inserted": int(event_totals["inserted"]),
                    "skipped": int(event_totals["skipped"]),
                },
                "fees": fee_result,
                "run": {
                    "run_id": run_id,
                    "status": "succeeded",
                    "attempt_count": len(attempts),
                    "attempts": attempts,
                },
            }

        raise AssertionError("bounded sync retry loop exited without a terminal result")

    def project_fees(self, *, dry_run: bool = False) -> dict[str, Any]:
        snapshot = self._snapshot()
        reconciliation = _reconcile(snapshot, self.review_db)
        plan = _build_fee_plan(snapshot)
        if dry_run:
            fees = _fee_preview(plan)
        else:
            store = self._require_apply_store()
            if reconciliation["unsynced"] != 0:
                raise SyncConflictError(
                    "Fee projection requires an exactly reconciled sidecar; "
                    f"unsynced={reconciliation['unsynced']}"
                )
            fees = _persist_fee_plan(store, plan)
        return {
            "schema_version": FEE_RECEIPT_SCHEMA_VERSION,
            "status": "dry_run" if dry_run else "succeeded",
            "mode": "dry_run" if dry_run else "apply",
            "source": self._source_section(snapshot),
            "sidecar": {"path": str(self.review_db), "exists": self.review_db.is_file()},
            "counts": reconciliation,
            "fees": fees,
        }

    def status(self) -> dict[str, Any]:
        snapshot = self._snapshot()
        reconciliation = _reconcile(snapshot, self.review_db)
        result: dict[str, Any] = {
            "schema_version": SYNC_STATUS_SCHEMA_VERSION,
            "status": "missing_sidecar" if not self.review_db.is_file() else "unknown",
            "source": self._source_section(snapshot),
            "sidecar": {"path": str(self.review_db), "exists": self.review_db.is_file()},
            "counts": reconciliation,
            "lag": {
                "unsynced": reconciliation["unsynced"],
                "source_cutoff_id": snapshot.cutoff["cutoff_id"],
            },
            "fees": {"actual": 0, "estimated": 0, "unknown": 0},
            "fee_details": {
                "base_projection_counts": {"actual": 0, "estimated": 0, "unknown": 0},
                "effective_counts": {"actual": 0, "estimated": 0, "unknown": 0},
                "correction_count": 0,
            },
            "last_success": None,
            "last_failure": None,
        }
        if not self.review_db.is_file():
            return result

        store = ReviewStore(self.review_db)
        try:
            store_status = store.status()
        except ReviewStoreError as exc:
            result["status"] = "invalid_sidecar"
            result["sidecar"]["error"] = str(exc)
            return result
        product_version = store_status.get("product_completion_schema_version")
        result["sidecar"]["product_completion_schema_version"] = product_version
        result["sidecar"]["integrity_check"] = store_status.get("integrity_check")
        if product_version != PRODUCT_COMPLETION_SCHEMA_VERSION:
            result["status"] = "schema_not_initialized"
            return result

        with store.connection(read_only=True) as conn:
            fee_rows = conn.execute(
                "SELECT status, COUNT(*) AS count FROM fee_projections GROUP BY status"
            ).fetchall()
            effective_fee_rows = conn.execute(
                """
                WITH latest_projection AS (
                    SELECT event_id, status,
                           ROW_NUMBER() OVER (
                               PARTITION BY event_id
                               ORDER BY projected_at DESC, projection_id DESC
                           ) AS rank
                    FROM fee_projections
                ),
                latest_correction AS (
                    SELECT event_id, status,
                           ROW_NUMBER() OVER (
                               PARTITION BY event_id
                               ORDER BY effective_at DESC, known_at DESC, correction_id DESC
                           ) AS rank
                    FROM fee_corrections
                )
                SELECT COALESCE(c.status, p.status, 'unknown') AS status,
                       COUNT(*) AS count
                FROM trade_events AS e
                LEFT JOIN latest_projection AS p
                  ON p.event_id = e.event_id AND p.rank = 1
                LEFT JOIN latest_correction AS c
                  ON c.event_id = e.event_id AND c.rank = 1
                WHERE e.side IN ('BUY', 'SELL')
                GROUP BY COALESCE(c.status, p.status, 'unknown')
                """
            ).fetchall()
            correction_count = int(
                conn.execute("SELECT COUNT(*) FROM fee_corrections").fetchone()[0]
            )
            sync_run_ids = [
                str(row["run_id"])
                for row in conn.execute(
                    "SELECT run_id FROM review_runs WHERE scope = 'sync' ORDER BY rowid"
                ).fetchall()
            ]
        base_projection_counts = {
            status: next(
                (int(row["count"]) for row in fee_rows if row["status"] == status), 0
            )
            for status in ("actual", "estimated", "unknown")
        }
        effective_counts = {
            status: next(
                (
                    int(row["count"])
                    for row in effective_fee_rows
                    if row["status"] == status
                ),
                0,
            )
            for status in ("actual", "estimated", "unknown")
        }
        result["fees"] = effective_counts
        result["fee_details"] = {
            "base_projection_counts": base_projection_counts,
            "effective_counts": effective_counts,
            "correction_count": correction_count,
        }
        # ``requested_at`` is evidence supplied by the run and can legitimately
        # tie (for example after a clock-coarsened failure/recovery).  SQLite
        # insertion order is the authoritative local ordering for health.
        runs = [store.get_review_run(run_id) for run_id in sync_run_ids]
        successes = [item for item in runs if item["status"] == "succeeded"]
        failures = [item for item in runs if item["status"] in {"failed", "blocked"}]
        result["last_success"] = successes[-1] if successes else None
        result["last_failure"] = failures[-1] if failures else None
        terminal_runs = [
            item
            for item in runs
            if item["status"] in {"succeeded", "failed", "blocked"}
        ]
        if terminal_runs and terminal_runs[-1]["status"] in {"failed", "blocked"}:
            result["status"] = "failed"
        elif reconciliation["unsynced"]:
            result["status"] = "lagging"
        else:
            result["status"] = "healthy"
        return result


def sync_review_events(
    portfolio_db: str | Path,
    *,
    review_db: str | Path | None = None,
    mapping_path: str | Path | None = None,
    dry_run: bool = False,
    trigger: str = "manual",
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    return ReviewSyncService(
        portfolio_db,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=repo_root,
    ).sync(dry_run=dry_run, trigger=trigger)


def project_review_fees(
    portfolio_db: str | Path,
    *,
    review_db: str | Path | None = None,
    mapping_path: str | Path | None = None,
    dry_run: bool = False,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    return ReviewSyncService(
        portfolio_db,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=repo_root,
    ).project_fees(dry_run=dry_run)


def review_sync_status(
    portfolio_db: str | Path,
    *,
    review_db: str | Path | None = None,
    mapping_path: str | Path | None = None,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    return ReviewSyncService(
        portfolio_db,
        review_db=review_db,
        mapping_path=mapping_path,
        repo_root=repo_root,
    ).status()


def sync_after_portfolio_commit(
    portfolio_db: str | Path,
    *,
    explicit_review_db: str | Path | None = None,
    mapping_path: str | Path | None = None,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Best-effort post-commit entry point that never re-raises review errors."""

    try:
        return sync_review_events(
            portfolio_db,
            review_db=explicit_review_db,
            mapping_path=mapping_path,
            dry_run=False,
            trigger="portfolio_post_commit",
            repo_root=repo_root,
        )
    except Exception as exc:
        return {
            "schema_version": SYNC_RECEIPT_SCHEMA_VERSION,
            "status": "failed",
            "mode": "apply",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "portfolio_db": str(portfolio_db),
            "review_db": str(explicit_review_db) if explicit_review_db is not None else None,
        }


__all__ = [
    "DEFAULT_REVIEW_DB_ENV",
    "FEE_RECEIPT_SCHEMA_VERSION",
    "SYNC_RECEIPT_SCHEMA_VERSION",
    "SYNC_STATUS_SCHEMA_VERSION",
    "ReviewSyncService",
    "SyncConflictError",
    "SyncServiceError",
    "project_review_fees",
    "resolve_review_db",
    "review_sync_status",
    "sync_after_portfolio_commit",
    "sync_review_events",
]
