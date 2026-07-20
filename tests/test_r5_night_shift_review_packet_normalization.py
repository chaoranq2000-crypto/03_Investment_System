from __future__ import annotations

import yaml

from src.maintenance.night_shift.night04_review import MACHINE_EMPTY_FIELDS, REVIEW_PACKET_SCHEMA_VERSION

from tests.night04_test_support import REPO_ROOT, registry


def test_all_review_packets_share_one_auditable_envelope() -> None:
    for item in registry()["candidates"]:
        packet = yaml.safe_load((REPO_ROOT / item["review_packet_path"]).read_text(encoding="utf-8"))
        assert packet["schema_version"] == REVIEW_PACKET_SCHEMA_VERSION
        assert packet["occurrence_id"] == item["occurrence_id"]
        assert packet["candidate_sha256"] == item["candidate_sha256"]
        assert packet["source_lineage"]
        assert packet["counterevidence"]
        assert packet["uncertainties"]
        assert all(packet[field] is None for field in MACHINE_EMPTY_FIELDS)
