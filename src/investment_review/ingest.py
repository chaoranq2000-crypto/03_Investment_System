"""Mapping-driven, idempotent ingestion from CSV or read-only SQLite."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from .introspection import quote_identifier, table_schema_sha256
from .models import CanonicalTradeEvent, ModelValidationError, SourceDefinition, parse_decimal
from .store import ReviewStore


class MappingError(ValueError):
    """Raised when an ingest mapping is incomplete or references missing fields."""


SIDE_ALIASES = {
    "买入": "BUY",
    "证券买入": "BUY",
    "申购": "BUY",
    "BUY": "BUY",
    "B": "BUY",
    "卖出": "SELL",
    "证券卖出": "SELL",
    "赎回": "SELL",
    "SELL": "SELL",
    "S": "SELL",
    "转入": "TRANSFER_IN",
    "TRANSFER_IN": "TRANSFER_IN",
    "转出": "TRANSFER_OUT",
    "TRANSFER_OUT": "TRANSFER_OUT",
}


def _validate_mapping_payload(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise MappingError("Mapping root must be a JSON object")
    if not isinstance(payload.get("source"), dict):
        raise MappingError("Mapping must contain a source object")
    if not isinstance(payload.get("mapping"), dict):
        raise MappingError("Mapping must contain a mapping object")
    return payload


def _load_mapping_with_snapshot(path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse and fingerprint the exact same bytes from one open file handle."""

    target = Path(path)
    with target.open("rb") as handle:
        raw = handle.read()
        stat = os.fstat(handle.fileno())
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MappingError(f"Invalid UTF-8 JSON mapping {target}: {exc}") from exc
    return _validate_mapping_payload(payload), {
        "path": str(target.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "mtime_ns": stat.st_mtime_ns,
    }


def load_mapping(path: str | Path) -> dict[str, Any]:
    payload, _ = _load_mapping_with_snapshot(path)
    return payload


def _file_snapshot(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        stat = os.fstat(handle.fileno())
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return {
        "path": str(target.resolve()),
        "sha256": digest.hexdigest(),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _assert_same_snapshot(before: dict[str, Any], after: dict[str, Any], *, label: str) -> None:
    fields = ("sha256", "size_bytes", "mtime_ns")
    if any(before[field] != after[field] for field in fields):
        raise MappingError(f"{label} changed while it was being read")


def _resolve_review_artifact(path_value: object) -> Path:
    candidate = Path(str(path_value or ""))
    if not str(candidate):
        raise MappingError("Reviewed mapping provenance path is missing")
    return candidate if candidate.is_absolute() else Path.cwd() / candidate


def reviewed_mapping_content_sha256(config: Mapping[str, Any]) -> str:
    """Hash the reviewed document while excluding only its self-referential hash."""

    canonical = dict(config)
    review = canonical.get("review")
    if isinstance(review, Mapping):
        canonical_review = dict(review)
        canonical_review.pop("mapping_content_sha256", None)
        canonical["review"] = canonical_review
    try:
        payload = json.dumps(
            canonical,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MappingError(f"Reviewed mapping cannot be canonicalized: {exc}") from exc
    return hashlib.sha256(payload).hexdigest()


def _same_file(left: Path, right_value: object) -> bool:
    right = Path(str(right_value or ""))
    if not str(right):
        return False
    right = right if right.is_absolute() else Path.cwd() / right
    try:
        return os.path.samefile(left, right)
    except OSError:
        return left.resolve() == right.resolve()


def _require_reviewed_sqlite_mapping(
    config: dict[str, Any], *, source_db: Path, table: str
) -> str:
    review = config.get("review")
    if not isinstance(review, dict) or str(review.get("status", "")).lower() != "reviewed":
        raise MappingError(
            "Real SQLite import requires review.status='reviewed'; generated mappings are dry-run only"
        )
    for field in ("reviewed_at", "reviewed_by"):
        if not str(review.get(field, "")).strip():
            raise MappingError(f"Reviewed mapping is missing review.{field}")
    expected_content = str(review.get("mapping_content_sha256", "")).lower()
    if len(expected_content) != 64:
        raise MappingError("Reviewed mapping is missing review.mapping_content_sha256")
    actual_content = reviewed_mapping_content_sha256(config)
    if actual_content != expected_content:
        raise MappingError(
            "Reviewed mapping content hash mismatch: "
            f"expected={expected_content}, actual={actual_content}"
        )
    for prefix in ("schema_manifest", "generated_mapping"):
        artifact = _resolve_review_artifact(review.get(f"{prefix}_path"))
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
    if not isinstance(source_config, dict) or not _same_file(
        source_db, source_config.get("uri")
    ):
        raise MappingError(
            "Real SQLite import source does not match the reviewed source.uri; "
            "rerun doctor and review before changing databases"
        )
    if source_config.get("read_only") is not True:
        raise MappingError("Reviewed SQLite source must set source.read_only=true")

    generated_from = config.get("generated_from")
    if not isinstance(generated_from, dict):
        raise MappingError("Reviewed SQLite mapping is missing generated_from provenance")
    if not _same_file(source_db, generated_from.get("database")):
        raise MappingError(
            "Real SQLite import source does not match generated_from.database"
        )
    if str(generated_from.get("table", "")) != table:
        raise MappingError("sqlite.table does not match the reviewed generated_from.table")
    expected_schema = str(generated_from.get("table_schema_sha256", "")).lower()
    if len(expected_schema) != 64:
        raise MappingError(
            "Reviewed SQLite mapping is missing generated_from.table_schema_sha256"
        )
    return expected_schema


def _resolve(row: Mapping[str, Any], spec: Any, *, field_name: str) -> Any:
    if spec is None:
        return None
    if isinstance(spec, str):
        if spec not in row:
            raise MappingError(f"Field {field_name!r} references missing column {spec!r}")
        return row[spec]
    if isinstance(spec, list):
        total = None
        for child in spec:
            value = _resolve(row, child, field_name=field_name)
            number = parse_decimal(value, field_name=field_name)
            if number is not None:
                total = number if total is None else total + number
        return total
    if isinstance(spec, dict):
        if "constant" in spec:
            return spec["constant"]
        if "column" in spec:
            return _resolve(row, spec["column"], field_name=field_name)
        if "coalesce" in spec:
            for child in spec["coalesce"]:
                value = _resolve(row, child, field_name=field_name)
                if value not in (None, ""):
                    return value
            return None
        if "join" in spec:
            separator = str(spec.get("separator", " "))
            parts = [
                str(_resolve(row, child, field_name=field_name)).strip()
                for child in spec["join"]
            ]
            return separator.join(part for part in parts if part)
    raise MappingError(f"Unsupported mapping for {field_name!r}: {spec!r}")


def _map_value(config: dict[str, Any], field: str, value: Any) -> Any:
    if value in (None, ""):
        return value
    configured = config.get("values", {}).get(field, {})
    text = str(value).strip()
    for key, mapped in configured.items():
        if text == str(key).strip():
            return mapped
    if field == "side":
        return SIDE_ALIASES.get(text.upper(), SIDE_ALIASES.get(text, text.upper()))
    return value


def source_from_config(config: dict[str, Any], *, source_uri: str | None = None) -> SourceDefinition:
    raw = config["source"]
    uri = source_uri or raw.get("uri")
    if not uri:
        raise MappingError("source.uri is required")
    return SourceDefinition(
        name=str(raw.get("name") or Path(uri).name),
        kind=str(raw.get("kind") or "generic"),
        uri=str(uri),
        timezone=str(raw.get("timezone") or "Asia/Shanghai"),
        read_only=bool(raw.get("read_only", True)),
        identity_key=(str(raw.get("identity_key")).strip() if raw.get("identity_key") else None),
        config=config,
    )


def _event_preview(event: CanonicalTradeEvent) -> dict[str, Any]:
    """Return reviewable fields without exposing the complete raw source row."""

    return {
        "source_id": event.source_id,
        "source_record_id": event.source_record_id,
        "event_type": event.event_type,
        "occurred_at": event.occurred_at,
        "known_at": event.known_at,
        "known_at_fallback": bool(event.raw_payload.get("known_at_fallback")),
        "symbol": event.symbol,
        "account": event.account,
        "market": event.market,
        "side": event.side,
        "quantity": str(event.quantity) if event.quantity is not None else None,
        "price": str(event.price) if event.price is not None else None,
        "gross_amount": str(event.gross_amount) if event.gross_amount is not None else None,
        "cash_amount": str(event.cash_amount) if event.cash_amount is not None else None,
        "fees": str(event.fees) if event.fees is not None else None,
        "currency": event.currency,
        "payload_sha256": event.payload_sha256,
    }


def _dry_run_details(events: list[CanonicalTradeEvent]) -> dict[str, Any]:
    counts = Counter((event.event_type, event.side) for event in events)
    representatives: list[CanonicalTradeEvent] = []
    selected_ids: set[str] = set()
    seen_types: set[str] = set()
    for event in events:
        if event.event_type not in seen_types:
            representatives.append(event)
            selected_ids.add(event.event_id)
            seen_types.add(event.event_type)
    for event in events:
        if len(representatives) >= max(5, len(seen_types)):
            break
        if event.event_id not in selected_ids:
            representatives.append(event)
            selected_ids.add(event.event_id)
    return {
        "event_type_side_counts": [
            {"event_type": event_type, "side": side, "count": count}
            for (event_type, side), count in sorted(counts.items())
        ],
        "preview": [_event_preview(event) for event in representatives],
    }


def rows_to_events(
    rows: Iterable[Mapping[str, Any]],
    *,
    config: dict[str, Any],
    source: SourceDefinition,
) -> list[CanonicalTradeEvent]:
    mapping = config["mapping"]
    required = ("record_id", "occurred_at", "symbol", "side", "quantity", "price")
    missing = [field for field in required if mapping.get(field) in (None, "")]
    if missing:
        raise MappingError(
            "Mapping is not ready; fill these canonical fields: " + ", ".join(missing)
        )

    events: list[CanonicalTradeEvent] = []
    for row_number, raw_row in enumerate(rows, start=1):
        row = dict(raw_row)
        try:
            values = {
                field: _resolve(row, spec, field_name=field)
                for field, spec in mapping.items()
            }
            for field in ("side", "event_type", "currency", "market"):
                values[field] = _map_value(config, field, values.get(field))

            gross_amount = values.get("gross_amount")
            if gross_amount in (None, ""):
                quantity = parse_decimal(values.get("quantity"), field_name="quantity")
                price = parse_decimal(values.get("price"), field_name="price")
                gross_amount = quantity * price if quantity is not None and price is not None else None

            raw_payload = {
                "source_row_number": row_number,
                "source_row": row,
                "mapping_version": config.get("mapping_version", 1),
                "known_at_fallback": values.get("known_at") in (None, ""),
            }
            event = CanonicalTradeEvent.build(
                source_id=source.source_id,
                source_record_id=values.get("record_id"),
                event_type=values.get("event_type") or "fill",
                occurred_at=values.get("occurred_at"),
                known_at=values.get("known_at"),
                symbol=values.get("symbol"),
                timezone=source.timezone,
                account=values.get("account"),
                market=values.get("market"),
                side=values.get("side"),
                quantity=values.get("quantity"),
                price=values.get("price"),
                gross_amount=gross_amount,
                cash_amount=values.get("cash_amount"),
                fees=values.get("fees"),
                currency=values.get("currency") or "CNY",
                raw_payload=raw_payload,
            )
        except (MappingError, ModelValidationError, ValueError) as exc:
            raise MappingError(f"Row {row_number}: {exc}") from exc
        events.append(event)
    return events


def _read_csv(path: Path, config: dict[str, Any]) -> list[dict[str, str]]:
    source_options = config.get("csv", {})
    requested_encoding = source_options.get("encoding")
    encodings = [requested_encoding] if requested_encoding else ["utf-8-sig", "gb18030", "utf-8"]
    last_error: Exception | None = None
    text = None
    used_encoding = None
    for encoding in encodings:
        try:
            text = path.read_text(encoding=encoding)
            used_encoding = encoding
            break
        except UnicodeDecodeError as exc:
            last_error = exc
    if text is None:
        raise MappingError(f"Could not decode CSV {path}: {last_error}")

    delimiter = source_options.get("delimiter")
    if not delimiter:
        try:
            delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",	;|").delimiter
        except csv.Error:
            delimiter = ","
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    if not reader.fieldnames:
        raise MappingError(f"CSV has no header: {path}")
    rows = [dict(row) for row in reader]
    config.setdefault("runtime", {})["csv_encoding"] = used_encoding
    config.setdefault("runtime", {})["csv_delimiter"] = delimiter
    return rows


def ingest_csv(
    csv_path: str | Path,
    mapping_path: str | Path,
    store: ReviewStore,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    config, mapping_snapshot = _load_mapping_with_snapshot(mapping_path)
    if not str(config["source"].get("identity_key", "")).strip():
        raise MappingError(
            "CSV import requires a stable source.identity_key so copied or renamed "
            "exports cannot create duplicate events"
        )
    source = source_from_config(config, source_uri=str(path.resolve()))
    source_snapshot = _file_snapshot(path)
    rows = _read_csv(path, config)
    events = rows_to_events(rows, config=config, source=source)
    _assert_same_snapshot(source_snapshot, _file_snapshot(path), label="CSV source")
    if dry_run:
        return {
            "status": "DRY_RUN",
            "source_id": source.source_id,
            "seen": len(events),
            **_dry_run_details(events),
        }
    return store.import_events(
        source,
        events,
        manifest={
            "adapter": "csv",
            "source_path": str(path.resolve()),
            "mapping_path": str(Path(mapping_path).resolve()),
            "mapping_sha256": mapping_snapshot["sha256"],
            "mapping_snapshot": config,
            "row_count": len(rows),
            "source_sha256": source_snapshot["sha256"],
            "source_size_bytes": source_snapshot["size_bytes"],
            "source_mtime_ns": source_snapshot["mtime_ns"],
            "runtime": config.get("runtime", {}),
        },
    )


def ingest_sqlite(
    source_db: str | Path,
    mapping_path: str | Path,
    store: ReviewStore,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    path = Path(source_db)
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        same_file = store.path.exists() and os.path.samefile(path, store.path)
    except OSError:
        same_file = path.resolve() == store.path.resolve()
    if same_file:
        raise MappingError("Source portfolio database and review database must be different files")

    config, mapping_snapshot = _load_mapping_with_snapshot(mapping_path)
    sqlite_config = config.get("sqlite")
    if not isinstance(sqlite_config, dict) or not sqlite_config.get("table"):
        raise MappingError("SQLite mapping must contain sqlite.table")
    table = str(sqlite_config["table"])
    expected_schema = None
    if not dry_run:
        expected_schema = _require_reviewed_sqlite_mapping(
            config, source_db=path, table=table
        )
    source = source_from_config(config, source_uri=str(path.resolve()))
    source_snapshot = _file_snapshot(path)

    uri = f"{path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        available = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        if table not in available:
            raise MappingError(f"Table {table!r} does not exist in {path}")
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
        if expected_schema is not None and actual_schema != expected_schema:
            raise MappingError(
                "Reviewed SQLite table schema hash mismatch: "
                f"expected={expected_schema}, actual={actual_schema}; "
                "rerun doctor and review"
            )
        rows = [
            dict(row)
            for row in conn.execute(f"SELECT * FROM {quote_identifier(table)}").fetchall()
        ]
    finally:
        conn.close()

    _assert_same_snapshot(source_snapshot, _file_snapshot(path), label="SQLite source")

    events = rows_to_events(rows, config=config, source=source)
    if dry_run:
        return {
            "status": "DRY_RUN",
            "source_id": source.source_id,
            "seen": len(events),
            "table": table,
            "mapping_review_status": str(config.get("review", {}).get("status", "unreviewed")),
            "table_schema_sha256": actual_schema,
            **_dry_run_details(events),
        }
    return store.import_events(
        source,
        events,
        manifest={
            "adapter": "sqlite",
            "source_path": str(path.resolve()),
            "table": table,
            "mapping_path": str(Path(mapping_path).resolve()),
            "mapping_sha256": mapping_snapshot["sha256"],
            "mapping_snapshot": config,
            "row_count": len(rows),
            "read_only": True,
            "source_sha256": source_snapshot["sha256"],
            "source_size_bytes": source_snapshot["size_bytes"],
            "source_mtime_ns": source_snapshot["mtime_ns"],
        },
    )
