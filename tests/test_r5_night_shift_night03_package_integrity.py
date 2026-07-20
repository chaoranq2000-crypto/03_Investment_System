from __future__ import annotations

import json
from pathlib import Path

from src.maintenance.night_shift.night04 import (
    EXPECTED_NIGHT03_ZIP_BYTES,
    EXPECTED_NIGHT03_ZIP_SHA256,
    OUTPUT_ROOT,
)


def test_original_night03_package_integrity_was_runtime_verified() -> None:
    root = Path(__file__).resolve().parents[1]
    receipt = json.loads((root / OUTPUT_ROOT / "preflight/night03_package_integrity.json").read_text(encoding="utf-8"))
    assert receipt["sha256"] == EXPECTED_NIGHT03_ZIP_SHA256
    assert receipt["bytes"] == EXPECTED_NIGHT03_ZIP_BYTES
    assert receipt["verification_mode"] == "runtime_original_archive_sha256"
    assert receipt["passed"] is True
