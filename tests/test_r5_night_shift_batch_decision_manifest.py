from __future__ import annotations

import json

from src.maintenance.night_shift.night04 import OUTPUT_ROOT
from src.maintenance.night_shift.night04_review import ALLOWED_DECISIONS, batch_decision_schema, validate_decision_batch

from tests.night04_test_support import FIXTURE_NOW, REPO_ROOT, valid_manifest


def test_batch_schema_and_exact_hash_record_validate() -> None:
    path = REPO_ROOT / OUTPUT_ROOT / "review_control/batch_decision_schema.json"
    assert json.loads(path.read_text(encoding="utf-8")) == batch_decision_schema()
    manifest, authorities = valid_manifest()
    result = validate_decision_batch(REPO_ROOT, manifest, authority_registry=authorities, now=FIXTURE_NOW)
    assert result["accepted_count"] == 1
    assert result["invalid_count"] == 0
    assert set(ALLOWED_DECISIONS) == {"approve", "reject", "defer", "request_changes"}
