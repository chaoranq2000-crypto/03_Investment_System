from __future__ import annotations

import json
from pathlib import Path

from src.maintenance.night_shift.night03 import OUTPUT_ROOT
from src.maintenance.night_shift.night03_execution import (
    build_resolution_receipt,
    generation_lock,
    resolution_receipt_schema,
)
from src.maintenance.night_shift.receipts import canonical_json_bytes, sha256_bytes


def test_resolution_receipt_is_deterministic_nonselfreferential_and_generation_locked() -> None:
    kwargs = {
        "occurrence_id": "occ_001",
        "decision_digest_sha256": "a" * 64,
        "implementation_tree_sha": "b" * 40,
        "commands": [{"command": "pytest", "exit_code": 0}],
        "outputs": [{"path": "report.json", "sha256": "c" * 64}],
        "terminal_status": "passed",
        "lineage_match": True,
        "resolution_claim_allowed": True,
    }
    first = build_resolution_receipt(**kwargs)
    second = build_resolution_receipt(**kwargs)
    assert first == second
    assert first["publication_head"] is None
    supplied = first.pop("stable_receipt_sha256")
    assert supplied == sha256_bytes(canonical_json_bytes(first))
    first["stable_receipt_sha256"] = supplied
    lock = generation_lock([first, second])
    assert lock["receipt_count"] == 2
    repo_root = Path(__file__).resolve().parents[1]
    artifact = json.loads(
        (repo_root / OUTPUT_ROOT / "execution/resolution_receipt_schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifact == resolution_receipt_schema()
