from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_r5_bundle8b_close import validate_bundle8b  # noqa: E402


def test_bundle8b_close_inputs_reconcile_to_evidence() -> None:
    result = validate_bundle8b(ROOT)
    assert result["decision"] == "pass", result["errors"]
    assert result["checks"]["evidence_delta"]["rows"] == 46
    assert result["checks"]["peer_metrics"]["metrics_checked"] == 45
    assert result["checks"]["liquid_cooling_boundary"]["visible_missing_items"] == 5
    assert result["checks"]["market_event"]["planned_date"] == "2026-08-25"
