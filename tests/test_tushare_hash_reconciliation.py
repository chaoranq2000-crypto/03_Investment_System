"""Protect the narrow byte-metadata repair without freezing future manifest additions."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

from conftest import GIT_HISTORY


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_REL = "data/manifests/evidence_manifest.csv"
RECEIPT_REL = "data/processed/logs/2026-09-09_tushare_hash_reconciliation.json"
TARGET_IDS = (
    "market_data_tushare_stock_basic_20260701_a6d9f2",
    "market_data_tushare_income_selected_stocks_20260701_f1c8b2",
    "market_data_tushare_fina_indicator_selected_stocks_20260701_c3e4a9",
    "market_data_tushare_cashflow_selected_stocks_20260701_d5b6c1",
    "market_data_tushare_balancesheet_selected_stocks_20260701_a8f0d7",
)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def csv_rows(payload: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(payload.decode("utf-8-sig"), newline="")))


def manifest_rows(payload: bytes) -> dict[str, dict[str, str]]:
    return {
        row["evidence_id"]: row
        for row in csv.DictReader(io.StringIO(payload.decode("utf-8-sig"), newline=""))
    }


@pytest.fixture(scope="module")
def reconciliation():
    receipt = json.loads((ROOT / RECEIPT_REL).read_text(encoding="utf-8"))
    assert tuple(row["evidence_id"] for row in receipt["records"]) == TARGET_IDS
    return receipt


def test_reconciliation_changes_only_ten_hash_cells(reconciliation) -> None:
    receipt = reconciliation
    archived = GIT_HISTORY.blob(receipt["base_commit"], MANIFEST_REL).payload
    assert sha256(archived) == receipt["manifest_sha256_before"]
    before = manifest_rows(archived)
    reconstructed = archived
    for record in receipt["records"]:
        evidence_id = record["evidence_id"]
        old = before[evidence_id]
        old_pair = f"{old['file_hash']},{old['content_hash']}".encode("ascii")
        new_pair = f"{record['file_hash']},{record['content_hash']}".encode("ascii")
        assert reconstructed.count(old_pair) == 1
        reconstructed = reconstructed.replace(old_pair, new_pair)
    assert sha256(reconstructed) == receipt["manifest_sha256_after"]
    after = manifest_rows(reconstructed)
    changed_cells = {
        (evidence_id, field)
        for evidence_id, row in before.items()
        for field, value in row.items()
        if value != after[evidence_id][field]
    }
    assert changed_cells == {
        (evidence_id, field)
        for evidence_id in TARGET_IDS
        for field in ("file_hash", "content_hash")
    }
    assert receipt["changed_row_count"] == 5
    assert receipt["changed_field_count"] == 10
    # Only the dated repair snapshot is exact; current review metadata may evolve.


@pytest.mark.parametrize("evidence_id", TARGET_IDS)
def test_snapshot_hashes_and_original_crlf_receipts_are_reproducible(
    reconciliation, evidence_id: str,
) -> None:
    receipt = reconciliation
    record = next(row for row in receipt["records"] if row["evidence_id"] == evidence_id)
    current = manifest_rows((ROOT / MANIFEST_REL).read_bytes())[evidence_id]
    raw = (ROOT / record["raw_file_path"]).read_bytes()
    processed = (ROOT / record["processed_text_path"]).read_bytes()
    table = (ROOT / record["processed_table_path"]).read_bytes()
    assert sha256(raw) == record["file_hash"] == current["file_hash"]
    assert sha256(processed) == record["content_hash"] == current["content_hash"]
    assert b"\r" not in raw and b"\r" not in processed
    assert len(raw) == record["raw_bytes"]
    assert len(processed) == record["processed_text_bytes"]
    assert raw == table
    original = GIT_HISTORY.blob(
        receipt["history"]["first_snapshot_commit"], record["raw_file_path"],
    )
    assert original.oid == record["original_git_blob_oid"]
    assert original.payload == raw
    assert GIT_HISTORY.blob(receipt["base_commit"], record["processed_text_path"]).payload == processed

    crlf_raw = raw.replace(b"\n", b"\r\n")
    crlf_processed = processed.replace(b"\n", b"\r\n")
    assert sha256(crlf_raw) == record["previous_file_hash"]
    assert sha256(crlf_processed) == record["previous_content_hash"]
    values = csv_rows(raw)
    assert values == csv_rows(crlf_raw)
    assert len(values) == record["csv_row_count_including_header"]
    encoded_values = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert sha256(encoded_values) == record["csv_values_sha256"]

    registered = manifest_rows(GIT_HISTORY.blob(
        receipt["history"]["full_hash_registration_commit"], MANIFEST_REL,
    ).payload)[evidence_id]
    assert registered["file_hash"] == record["previous_file_hash"]
    assert registered["content_hash"] == record["previous_content_hash"]
