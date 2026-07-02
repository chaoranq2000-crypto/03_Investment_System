from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Mapping, Sequence

EVIDENCE_FIELDNAMES: list[str] = [
    "evidence_id",
    "source_type",
    "source_name",
    "source_group",
    "title",
    "publisher",
    "publish_date",
    "retrieved_at",
    "ingested_at",
    "as_of_date",
    "entity_type",
    "entity_id",
    "segment_id",
    "company_id",
    "stock_code",
    "source_url",
    "raw_file_path",
    "raw_archive_policy",
    "file_hash",
    "content_hash",
    "api_params_hash",
    "processed_text_path",
    "processed_table_path",
    "page_map_path",
    "page_count",
    "language",
    "file_format",
    "ingest_mode",
    "reliability_rank",
    "material_claim_allowed",
    "allowed_claim_types",
    "license_note",
    "stale_after",
    "status",
    "parse_status",
    "candidate_status",
    "review_status",
    "previous_evidence_id",
    "superseded_by",
    "notes",
]

METRIC_CANDIDATE_FIELDNAMES: list[str] = [
    "metric_candidate_id",
    "source_evidence_id",
    "source_name",
    "source_type",
    "entity_type",
    "entity_id",
    "segment_id",
    "company_id",
    "stock_code",
    "metric_name",
    "metric_category",
    "period",
    "period_type",
    "value",
    "unit",
    "currency",
    "original_value_text",
    "original_unit_text",
    "table_id",
    "page_no_or_section",
    "calculation_method",
    "is_estimate",
    "is_reported",
    "confidence",
    "review_status",
    "promote_to_metric_id",
    "created_at",
    "notes",
]

INGEST_RUN_FIELDNAMES: list[str] = [
    "run_id",
    "ingest_mode",
    "started_at",
    "finished_at",
    "result",
    "stock_code",
    "source_name",
    "source_type",
    "api_name",
    "manifest_rows_created",
    "manifest_rows_updated",
    "metric_candidates",
    "claim_candidates",
    "issues",
    "notes",
]

NUMERIC_SKIP_COLUMNS = {
    "ts_code",
    "symbol",
    "name",
    "stock_code",
    "ann_date",
    "f_ann_date",
    "end_date",
    "trade_date",
    "report_type",
    "comp_type",
    "currency",
}


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def repo_rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def hash_json(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return sha256_bytes(payload)


def short_hash(value: str, length: int = 8) -> str:
    cleaned = re.sub(r"[^0-9a-fA-F]", "", value)
    if len(cleaned) >= length:
        return cleaned[:length].lower()
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def safe_slug(value: str, fallback: str = "unknown") -> str:
    slug = re.sub(r"[^A-Za-z0-9_\-]+", "_", value.strip()).strip("_").lower()
    return slug or fallback


def normalize_stock_code(stock_code: str) -> str:
    digits = re.sub(r"\D", "", stock_code)
    if len(digits) != 6:
        raise ValueError(f"stock_code must contain six digits: {stock_code!r}")
    return digits


def stock_to_ts_code(stock_code: str) -> str:
    code = normalize_stock_code(stock_code)
    suffix = "SH" if code.startswith(("6", "9")) else "SZ"
    return f"{code}.{suffix}"


def evidence_id(
    *,
    source_type: str,
    entity: str,
    date_value: str,
    hash_value: str,
) -> str:
    entity_slug = safe_slug(entity)
    date_slug = re.sub(r"[^0-9]", "", date_value) or datetime.now(UTC).strftime("%Y%m%d")
    return f"ev_{safe_slug(source_type)}_{entity_slug}_{date_slug}_{short_hash(hash_value, 6)}"


def write_csv_rows(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, object]]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    ensure_parent(path)
    file_exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    return len(rows)


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def immutable_copy_or_write_bytes(target: Path, data: bytes) -> tuple[str, str]:
    ensure_parent(target)
    digest = sha256_bytes(data)
    if target.exists():
        existing_hash = sha256_file(target)
        if existing_hash == digest:
            return "unchanged", existing_hash
        raise FileExistsError(f"Refusing to overwrite immutable raw evidence: {target}")
    target.write_bytes(data)
    return "created", digest


def immutable_copy_file(source: Path, target: Path) -> tuple[str, str]:
    ensure_parent(target)
    source_hash = sha256_file(source)
    if target.exists():
        target_hash = sha256_file(target)
        if target_hash == source_hash:
            return "unchanged", target_hash
        raise FileExistsError(f"Refusing to overwrite immutable raw evidence: {target}")
    shutil.copy2(source, target)
    return "created", source_hash


def write_json(path: Path, payload: Mapping[str, object]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_number(value: str) -> bool:
    if value is None:
        return False
    text = str(value).strip().replace(",", "")
    if text == "":
        return False
    try:
        float(text)
    except ValueError:
        return False
    return True


def detect_period(row: Mapping[str, str]) -> str:
    for key in ("end_date", "trade_date", "ann_date", "f_ann_date", "period", "date"):
        value = str(row.get(key, "")).strip()
        if value:
            return value
    return "UNKNOWN"
