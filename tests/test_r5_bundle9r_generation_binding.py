from pathlib import Path

import yaml

from src.research.r5_bundle9r_contracts import (
    validate_evidence_generation_lock,
    validate_generation_bound_artifact,
    validate_locked_input_hashes,
)


def test_current_generation_binding_passes():
    lock = {
        "generation_id": "evidence_gen_r5_bundle8r_b82ba6f33b5044e6",
        "aggregate_sha256": "b82ba6f33b5044e686e4c7210eba77675b0527a24169c48aea41ad8e4bc1846c",
        "missing_input_count": 0,
        "downstream_consumers": ["R5_BUNDLE_9R_FORECAST_VALUATION_REBUILD"],
    }
    assert validate_evidence_generation_lock(
        lock,
        expected_generation_id="evidence_gen_r5_bundle8r_b82ba6f33b5044e6",
        expected_aggregate_sha256="b82ba6f33b5044e686e4c7210eba77675b0527a24169c48aea41ad8e4bc1846c",
        required_consumer="R5_BUNDLE_9R_FORECAST_VALUATION_REBUILD",
    ) == []


def test_stale_downstream_artifact_is_blocked():
    issues = validate_generation_bound_artifact(
        {"input_evidence_generation_id": "old_generation"},
        current_generation_id="evidence_gen_r5_bundle8r_b82ba6f33b5044e6",
        artifact_label="forecast",
    )
    assert [x.code for x in issues] == ["stale_or_unbound_artifact"]


def test_changed_locked_input_hash_is_blocked(tmp_path):
    path = tmp_path / "input.txt"
    path.write_text("current", encoding="utf-8")
    lock = {"inputs": [{"path": "input.txt", "sha256": "0" * 64}]}
    assert [x.code for x in validate_locked_input_hashes(lock, tmp_path)] == ["locked_input_hash_changed"]
