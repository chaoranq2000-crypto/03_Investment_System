from __future__ import annotations

import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SOURCE = "config/r5_bundle4_expected_artifacts.yaml"
SMOKE_SOURCE = "reports/p1_6/r5_bundle4_reviewed_input_smoke_result.json"
TRUTHFULNESS_SOURCE = "reports/p1_6/r5_bundle4_readout_truthfulness_result.json"
CLOSE_READOUT_SOURCE = (
    "reports/p1_6/R5_BUNDLE_4_REVIEWED_INPUT_FIXTURE_PROMOTION_CLOSE_READOUT.md"
)
REAL_DECISION_SOURCE = "reports/p1_6/r5_after_patch55_decision.json"
EXPECTED_SCENARIOS = {
    "empty_or_pending",
    "accepted_core_complete",
    "accepted_all_complete",
    "mixed_status",
    "invalid_input",
    "idempotent_rerun",
}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def artifact_paths(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [path for child in value.values() for path in artifact_paths(child)]
    if isinstance(value, list):
        return [path for child in value for path in artifact_paths(child)]
    if isinstance(value, str):
        return [value]
    return []


def test_expected_artifact_manifest_is_complete_and_physical(
    historical_blob_bytes,
) -> None:
    manifest = yaml.safe_load(historical_blob_bytes(MANIFEST_SOURCE).decode("utf-8"))

    assert manifest["bundle"] == "R5_BUNDLE_4_REVIEWED_INPUT_FIXTURE_PROMOTION_SMOKE"
    assert manifest["expected_close_state"] == "R5_REVIEWED_INPUT_FIXTURE_PROMOTION_SMOKE_PASSED"
    assert manifest["fixture_mode_sample_quality_allowed"] is False
    assert manifest["p2_allowed"] is False
    paths = artifact_paths(manifest["artifacts"])
    assert paths
    missing = []
    for path in sorted(set(paths)):
        if not PurePosixPath(path).suffix:
            if not (REPO_ROOT / path).is_dir():
                missing.append(path)
            continue
        try:
            historical_blob_bytes(path)
        except (AssertionError, subprocess.CalledProcessError):
            missing.append(path)
    assert missing == []


def test_smoke_result_has_exact_scenarios_and_fail_closed_caps(
    historical_blob_bytes,
) -> None:
    smoke = json.loads(historical_blob_bytes(SMOKE_SOURCE).decode("utf-8"))

    assert smoke["overall_status"] == "pass"
    assert smoke["fixture_mode"] is True
    assert smoke["real_workflow_unchanged"] is True
    assert smoke["sample_quality_report_allowed"] is False
    assert smoke["p2_allowed"] is False
    assert set(smoke["scenarios"]) == EXPECTED_SCENARIOS
    for scenario in smoke["scenarios"].values():
        assert scenario["status"] == "pass"
        assert scenario["expectation_met"] is True
        assert scenario["sample_quality_report_allowed"] is False
        assert scenario["p2_allowed"] is False


def test_invalid_and_idempotent_smoke_evidence_is_physical(
    historical_blob_bytes,
) -> None:
    smoke = json.loads(historical_blob_bytes(SMOKE_SOURCE).decode("utf-8"))
    invalid = smoke["scenarios"]["invalid_input"]
    rerun = smoke["scenarios"]["idempotent_rerun"]

    assert invalid["registries_changed"] is False
    assert all(
        item["action"] == "blocked" and item["before_hash"] == item["after_hash"]
        for item in invalid["registry_actions"].values()
    )
    assert rerun["registries_changed"] is False
    assert all(
        item["action"] == "unchanged"
        and item["before_hash"]
        and item["before_hash"] == item["after_hash"]
        for item in rerun["registry_actions"].values()
    )


def test_real_002837_gate_remains_source_gapped_and_closed(
    historical_blob_bytes,
) -> None:
    decision = json.loads(
        historical_blob_bytes(REAL_DECISION_SOURCE).decode("utf-8")
    )

    assert decision["current_r5_state"] == "R5_REVIEWED_INPUT_PILOT_BLOCKED_SOURCE_GAPPED"
    assert decision["reviewed_input_pilot_allowed"] is False
    assert decision["sample_quality_report_allowed"] is False
    assert decision["p2_allowed"] is False
    assert decision["registries_changed"] is False


def test_bundle4_truthfulness_result_checks_exact_readout_count(
    historical_blob_bytes,
) -> None:
    truthfulness = json.loads(
        historical_blob_bytes(TRUTHFULNESS_SOURCE).decode("utf-8")
    )

    assert truthfulness["truthfulness_status"] == "pass"
    assert truthfulness["checked"] == 6
    assert truthfulness["failed"] == 0
    assert len(truthfulness["results"]) == 6
    assert all(result["status"] == "pass" for result in truthfulness["results"])


def test_close_readout_separates_fixture_and_real_decisions(
    historical_blob_bytes,
) -> None:
    text = historical_blob_bytes(CLOSE_READOUT_SOURCE).decode("utf-8")

    assert "current_r5_state: `R5_REVIEWED_INPUT_FIXTURE_PROMOTION_SMOKE_PASSED`" in text
    assert "fixture_pipeline_executable: `true`" in text
    assert "real_002837_reviewed_inputs_supplied: `false`" in text
    assert "real_002837_reviewed_input_pilot_allowed: `false`" in text
    assert "sample_quality_report_allowed: `false`" in text
    assert "p2_allowed: `false`" in text
    assert "R5_REVIEWED_INPUT_PILOT_ALLOWED" not in text
