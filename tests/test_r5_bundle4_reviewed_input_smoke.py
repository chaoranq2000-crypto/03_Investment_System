from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/run_r5_bundle4_reviewed_input_smoke.py"
FIXTURE_ROOT = REPO_ROOT / "tests/fixtures/r5_reviewed_inputs"
REAL_WORKFLOW = "wf_20260703_stock_first_002837_invic"
REAL_RUN_DIR = REPO_ROOT / "reports/workflow_runs" / REAL_WORKFLOW

SCENARIO_KEYS = {
    "empty_or_pending",
    "accepted_core_complete",
    "accepted_all_complete",
    "mixed_status",
    "invalid_input",
    "idempotent_rerun",
}
REVIEWED_FLAG_KEYS = {
    "reviewed_market_inputs_available",
    "reviewed_peer_inputs_available",
    "reviewed_forecast_assumptions_available",
    "reviewed_valuation_inputs_available",
    "reviewed_business_disclosure_available",
}
REGISTRY_FILES = {
    "market_peer": "R5_market_peer_input_registry.yaml",
    "forecast_assumptions": "R5_forecast_assumption_registry.yaml",
    "valuation_inputs": "R5_valuation_input_registry.yaml",
    "evidence_ledger": "R5_evidence_request_review_ledger.yaml",
}
ALL_TODOS = {
    "TODO_MARKET_DATA",
    "TODO_PEER_DATA",
    "TODO_MODEL_INPUT",
    "TODO_SOURCE_REQUIRED",
    "MISSING_DISCLOSURE",
}


def load_runner():
    assert SCRIPT.is_file(), f"missing Bundle 4.5 smoke runner: {SCRIPT}"
    spec = importlib.util.spec_from_file_location("r5_bundle4_reviewed_input_smoke", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_smoke(tmp_path: Path) -> dict[str, Any]:
    runner = load_runner()
    result = runner.run_smoke(
        repo_root=REPO_ROOT,
        fixture_root=FIXTURE_ROOT,
        work_root=tmp_path,
    )
    assert isinstance(result, dict)
    return result


def sha256_or_none(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def real_registry_hashes() -> dict[str, str | None]:
    return {
        key: sha256_or_none(REAL_RUN_DIR / filename)
        for key, filename in REGISTRY_FILES.items()
    }


def assert_reviewed_flags(
    scenario: dict[str, Any],
    *,
    market: bool,
    peer: bool,
    forecast: bool,
    valuation: bool,
    business: bool,
) -> None:
    expected = {
        "reviewed_market_inputs_available": market,
        "reviewed_peer_inputs_available": peer,
        "reviewed_forecast_assumptions_available": forecast,
        "reviewed_valuation_inputs_available": valuation,
        "reviewed_business_disclosure_available": business,
    }
    assert scenario["reviewed_flags"] == expected


def assert_registry_action_shape(scenario: dict[str, Any]) -> dict[str, dict[str, Any]]:
    actions = scenario["registry_actions"]
    assert isinstance(actions, dict)
    assert set(actions) == set(REGISTRY_FILES)
    for action in actions.values():
        assert isinstance(action, dict)
        assert {"action", "before_hash", "after_hash"} <= action.keys()
    return actions


def normalize_paths(value: Any, *paths: Path) -> Any:
    if isinstance(value, dict):
        return {key: normalize_paths(item, *paths) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_paths(item, *paths) for item in value]
    if isinstance(value, str):
        normalized = value
        for path in paths:
            resolved = path.resolve()
            normalized = normalized.replace(str(resolved), "<transient_path>")
            normalized = normalized.replace(resolved.as_posix(), "<transient_path>")
        return normalized
    return value


def test_smoke_contract_and_all_scenarios_pass(tmp_path: Path) -> None:
    result = run_smoke(tmp_path / "all_scenarios")

    assert isinstance(result["artifact_type"], str) and "smoke" in result["artifact_type"].lower()
    assert isinstance(result["schema_version"], str) and result["schema_version"]
    assert result["fixture_mode"] is True
    assert result["overall_status"] == "pass"
    assert result["real_workflow_unchanged"] is True
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False
    assert set(result["scenarios"]) == SCENARIO_KEYS

    for scenario in result["scenarios"].values():
        assert scenario["status"] == "pass"
        assert scenario["expectation_met"] is True
        assert scenario["sample_quality_report_allowed"] is False
        assert scenario["p2_allowed"] is False
        assert isinstance(scenario["steps"], (list, dict)) and scenario["steps"]
        assert set(scenario["reviewed_flags"]) == REVIEWED_FLAG_KEYS
        assert isinstance(scenario["remaining_todos"], list)
        assert isinstance(scenario["blockers"], list)
        assert_registry_action_shape(scenario)


def test_empty_pending_and_positive_flags_are_accepted_only(tmp_path: Path) -> None:
    scenarios = run_smoke(tmp_path / "flags")["scenarios"]

    empty = scenarios["empty_or_pending"]
    assert_reviewed_flags(
        empty,
        market=False,
        peer=False,
        forecast=False,
        valuation=False,
        business=False,
    )
    assert set(empty["remaining_todos"]) == ALL_TODOS
    assert empty["allowed_report_level"] == "source_gapped_research_draft"
    assert all(
        item["action"] == "unchanged"
        for item in assert_registry_action_shape(empty).values()
    )

    core = scenarios["accepted_core_complete"]
    assert_reviewed_flags(
        core,
        market=True,
        peer=True,
        forecast=True,
        valuation=True,
        business=False,
    )
    assert core["remaining_todos"] == ["MISSING_DISCLOSURE"]
    assert core["allowed_report_level"] == "reviewed_input_research_draft"

    complete = scenarios["accepted_all_complete"]
    assert_reviewed_flags(
        complete,
        market=True,
        peer=True,
        forecast=True,
        valuation=True,
        business=True,
    )
    assert complete["remaining_todos"] == []
    assert complete["allowed_report_level"] == "reviewed_input_research_draft"
    assert complete["sample_quality_report_allowed"] is False
    assert complete["p2_allowed"] is False


def test_mixed_status_activates_only_accepted_rows(tmp_path: Path) -> None:
    mixed = run_smoke(tmp_path / "mixed")["scenarios"]["mixed_status"]

    assert_reviewed_flags(
        mixed,
        market=True,
        peer=False,
        forecast=False,
        valuation=False,
        business=False,
    )
    assert set(mixed["remaining_todos"]) == ALL_TODOS - {"TODO_MARKET_DATA"}
    assert mixed["accepted_count"] == 1
    assert mixed["accepted_degraded_count"] == 1
    assert mixed["accepted_input_ids"] == ["fixture_mixed_market_accepted"]
    assert mixed["accepted_degraded_input_ids"] == ["fixture_mixed_peer_degraded"]
    assert mixed["allowed_report_level"] == "source_gapped_research_draft"


def test_invalid_input_has_no_partial_registry_write(tmp_path: Path) -> None:
    invalid = run_smoke(tmp_path / "invalid")["scenarios"]["invalid_input"]

    assert invalid["expectation_met"] is True
    assert invalid["blockers"]
    assert invalid["registries_changed"] is False
    for action in assert_registry_action_shape(invalid).values():
        assert action["action"] in {"blocked", "unchanged"}
        assert action["before_hash"] == action["after_hash"]
        target = action.get("target_path")
        if target:
            assert not Path(target).is_file()


def test_idempotent_rerun_reports_every_registry_unchanged(tmp_path: Path) -> None:
    rerun = run_smoke(tmp_path / "idempotent")["scenarios"]["idempotent_rerun"]

    assert rerun["expectation_met"] is True
    assert rerun["registries_changed"] is False
    for action in assert_registry_action_shape(rerun).values():
        assert action["action"] == "unchanged"
        assert action["before_hash"]
        assert action["before_hash"] == action["after_hash"]


def test_smoke_does_not_attempt_network_access(tmp_path: Path, monkeypatch) -> None:
    def reject_network(*_args, **_kwargs):
        raise AssertionError("Bundle 4 fixture smoke must not access the network")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)

    result = run_smoke(tmp_path / "offline")

    assert result["overall_status"] == "pass"


def test_real_002837_registry_hashes_remain_unchanged(tmp_path: Path) -> None:
    before = real_registry_hashes()

    result = run_smoke(tmp_path / "real_boundary")

    assert result["real_workflow_unchanged"] is True
    assert real_registry_hashes() == before


def test_cli_writes_json_and_repeated_runs_are_semantically_stable(tmp_path: Path) -> None:
    outputs: list[dict[str, Any]] = []
    transient_paths: list[Path] = []

    for index in (1, 2):
        work_root = tmp_path / f"cli_work_{index}"
        result_path = tmp_path / f"result_{index}.json"
        command = [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(REPO_ROOT),
            "--fixture-root",
            str(FIXTURE_ROOT),
            "--work-root",
            str(work_root),
            "--json",
            str(result_path),
        ]
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            check=False,
        )

        assert completed.returncode == 0, completed.stderr
        assert result_path.is_file()
        parsed = json.loads(result_path.read_text(encoding="utf-8"))
        assert parsed["overall_status"] == "pass"
        outputs.append(parsed)
        transient_paths.extend([work_root, result_path])

    assert normalize_paths(outputs[0], *transient_paths) == normalize_paths(
        outputs[1], *transient_paths
    )
