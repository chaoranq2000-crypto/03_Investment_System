from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.maintenance.night_shift.night03 import Night03Error
from src.maintenance.night_shift.night03_decisions import validate_decision_manifest


def test_analysis_adapter_requires_evidence_counterevidence_confidence_and_model_link(
    night03_decision_factory,
) -> None:
    valid = {
        "conclusion": "The operating assertion remains unqualified.",
        "evidence_ids": ["ev_001"],
        "counter_evidence": ["The comparison period is incomplete."],
        "confidence": "low",
        "model_link": "analysis_model_001",
    }
    root, manifest, _, _ = night03_decision_factory("analysis_acceptance", valid)
    now = datetime(2026, 7, 20, tzinfo=timezone.utc)
    assert validate_decision_manifest(root, manifest, now=now)["valid"] is True
    invalid = dict(valid, evidence_ids=[])
    root, manifest, _, _ = night03_decision_factory("analysis_acceptance", invalid)
    with pytest.raises(Night03Error, match="evidence_ids"):
        validate_decision_manifest(root, manifest, now=now)
