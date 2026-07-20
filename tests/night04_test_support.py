from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.maintenance.night_shift.night04 import EXPECTED_QUEUE_SHA256, OUTPUT_ROOT
from src.maintenance.night_shift.night04_review import DECISION_SCHEMA_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_REVIEWER = "external_test_fixture_reviewer"
FIXTURE_REVIEW_TIME = "2026-07-20T12:00:00+00:00"
FIXTURE_NOW = datetime(2026, 7, 21, tzinfo=timezone.utc)


def registry() -> dict[str, Any]:
    return yaml.safe_load((REPO_ROOT / OUTPUT_ROOT / "review_control/candidate_registry.yaml").read_text(encoding="utf-8"))


def valid_manifest(index: int = 0, *, decision: str = "approve") -> tuple[dict[str, Any], set[tuple[str, str]]]:
    entry = deepcopy(registry()["candidates"][index])
    authority = str(entry["required_reviewer_authority"])
    record = {
        "occurrence_id": entry["occurrence_id"],
        "candidate_sha256": entry["candidate_sha256"],
        "review_packet_sha256": entry["review_packet_sha256"],
        "reviewer": FIXTURE_REVIEWER,
        "reviewer_authority": authority,
        "reviewed_at": FIXTURE_REVIEW_TIME,
        "decision": decision,
        "notes": ["synthetic test fixture; not an external production decision"],
    }
    return {
        "schema_version": DECISION_SCHEMA_VERSION,
        "source_queue_sha256": EXPECTED_QUEUE_SHA256,
        "records": [record],
    }, {(FIXTURE_REVIEWER, authority)}
