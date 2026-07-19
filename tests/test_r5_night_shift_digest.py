from __future__ import annotations

from pathlib import Path

import pytest

from src.maintenance.night_shift.models import ContractError
from src.maintenance.night_shift.publication import require_sha256, validate_stable_digest
from src.maintenance.night_shift.receipts import canonical_json_bytes, sha256_bytes, write_receipt


def receipt() -> dict:
    value = {"schema_version": "test", "payload": {"value": 1}}
    value["stable_receipt_sha256"] = sha256_bytes(canonical_json_bytes(value))
    return value


def test_sha256_must_be_exactly_64_hexadecimal_characters() -> None:
    assert require_sha256("a" * 64, field="digest") == "a" * 64
    with pytest.raises(ContractError):
        require_sha256("a" * 41, field="digest")
    with pytest.raises(ContractError):
        require_sha256("g" * 64, field="digest")


def test_digest_recalculation_detects_manual_edits(tmp_path: Path) -> None:
    value = receipt()
    validate_stable_digest(value)
    write_receipt(tmp_path / "receipt.json", value)
    value["payload"]["value"] = 2
    with pytest.raises(ContractError, match="mismatch"):
        validate_stable_digest(value)
    with pytest.raises(ContractError, match="does not match"):
        write_receipt(tmp_path / "tampered.json", value)
