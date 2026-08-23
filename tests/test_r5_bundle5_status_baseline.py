from __future__ import annotations

from pathlib import Path, PurePosixPath
import subprocess
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SOURCE = "config/r5_bundle5_expected_artifacts.yaml"
BASELINE_READOUT = REPO_ROOT / "reports/p1_6/R5_AFTER_BUNDLE4_STATUS_BASELINE_READOUT.md"
README_PATH = REPO_ROOT / "README.md"
CI_PATH = REPO_ROOT / ".github/workflows/ci.yml"

EXPECTED_CORE_INPUT_TYPES = {
    "business_disclosure",
    "market_snapshot",
    "peer_snapshot",
    "forecast_assumptions",
    "valuation_inputs",
}


def load_manifest(historical_blob_bytes) -> dict[str, Any]:
    data = yaml.safe_load(historical_blob_bytes(MANIFEST_SOURCE).decode("utf-8"))
    assert isinstance(data, dict)
    return data


def test_bundle5_manifest_freezes_scope_and_fail_closed_states(historical_blob_bytes) -> None:
    manifest = load_manifest(historical_blob_bytes)

    assert manifest["bundle"] == "R5_BUNDLE_5_REAL_002837_REVIEWED_INPUT_ONBOARDING"
    assert manifest["base_state"] == "R5_REVIEWED_INPUT_FIXTURE_PROMOTION_SMOKE_PASSED"
    assert manifest["real_workflow"] == "wf_20260703_stock_first_002837_invic"
    assert manifest["stock_code"] == "002837"
    assert set(manifest["required_core_input_types"]) == EXPECTED_CORE_INPUT_TYPES
    assert manifest["optional_input_types"] == ["sentiment_event_sources"]
    assert manifest["fixed_boundaries"]["sample_quality_report_allowed"] is False
    assert manifest["fixed_boundaries"]["p2_allowed"] is False
    assert manifest["fixed_boundaries"]["sample_reports_are_research_evidence"] is False
    assert manifest["fixed_boundaries"]["fixtures_are_research_evidence"] is False


def test_baseline_required_paths_are_physical(historical_blob_bytes) -> None:
    manifest = load_manifest(historical_blob_bytes)
    required = manifest["baseline_required_paths"]

    assert len(required) == len(set(required))
    missing = []
    for path in required:
        if (REPO_ROOT / path).exists():
            continue
        try:
            historical_blob_bytes(path)
        except (AssertionError, subprocess.CalledProcessError):
            missing.append(path)
    assert missing == []


def test_owned_artifact_producers_are_unique_and_repo_relative(historical_blob_bytes) -> None:
    manifest = load_manifest(historical_blob_bytes)
    producers: dict[str, str] = {}

    for card_id, card in manifest["cards"].items():
        for artifact in card["owned_artifacts"]:
            path = artifact["path"]
            assert artifact["required_by_card"] == card_id
            assert path not in producers, (
                f"duplicate producer ownership for {path}: "
                f"{producers.get(path)} and {card_id}"
            )
            producers[path] = card_id
            pure_path = PurePosixPath(path)
            assert not pure_path.is_absolute()
            assert ".." not in pure_path.parts

    assert producers
    assert not any(path.lower().endswith(".zip") for path in producers)
    missing_reused_checks = []
    for path in manifest["reused_checks"]:
        if (REPO_ROOT / path).exists():
            continue
        try:
            historical_blob_bytes(path)
        except (AssertionError, subprocess.CalledProcessError):
            missing_reused_checks.append(path)
    assert missing_reused_checks == []


def test_registry_write_boundary_starts_at_card_5_5_only(historical_blob_bytes) -> None:
    manifest = load_manifest(historical_blob_bytes)
    cards = manifest["cards"]
    first_write_card = manifest["real_workflow_write_boundary"][
        "first_card_allowed_to_write_canonical_registries"
    ]
    first_write_order = cards[first_write_card]["order"]

    assert manifest["real_workflow_write_boundary"][
        "canonical_registry_write_allowed_before_card_5_5"
    ] is False
    for card_id, card in cards.items():
        if card["order"] < first_write_order:
            assert card["canonical_registry_write_allowed"] is False
            assert "canonical_registries" not in card["declared_write_scopes"]

    assert cards[first_write_card]["canonical_registry_write_allowed"] is True
    assert "canonical_registries" in cards[first_write_card]["declared_write_scopes"]


def test_ci_keeps_compile_and_full_pytest_semantics() -> None:
    ci_text = CI_PATH.read_text(encoding="utf-8")
    baseline_text = BASELINE_READOUT.read_text(encoding="utf-8")

    assert "python -m py_compile $(git ls-files '*.py')" in ci_text
    assert "python -m pytest -q" in ci_text
    assert "node20_action_runtime_migration" in baseline_text
    assert "conda_defaults_channel_implicit" in baseline_text
    assert "sample_quality_report_allowed: `false`" in baseline_text
    assert "p2_allowed: `false`" in baseline_text
