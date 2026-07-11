from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/promote_r5_reviewed_inputs_to_registries.py"
FIXTURE_ROOT = REPO_ROOT / "tests/fixtures/r5_reviewed_inputs"
FIXTURE_WORKFLOW = "wf_fixture_r5_bundle4"
FIXTURE_STOCK = "000000"
REAL_WORKFLOW = "wf_20260703_stock_first_002837_invic"
REAL_RUN_DIR = REPO_ROOT / "reports/workflow_runs" / REAL_WORKFLOW
REGISTRY_FILES = {
    "market_peer": "R5_market_peer_input_registry.yaml",
    "forecast_assumptions": "R5_forecast_assumption_registry.yaml",
    "valuation_inputs": "R5_valuation_input_registry.yaml",
    "evidence_ledger": "R5_evidence_request_review_ledger.yaml",
}
VALIDATOR_SCRIPTS = {
    "market_peer": REPO_ROOT
    / ".agents/skills/stock-deep-dive/scripts/validate_r5_market_peer_input_registry.py",
    "forecast_assumptions": REPO_ROOT
    / ".agents/skills/stock-deep-dive/scripts/validate_r5_forecast_assumption_registry.py",
    "valuation_inputs": REPO_ROOT
    / ".agents/skills/stock-deep-dive/scripts/validate_r5_valuation_inputs.py",
    "evidence_ledger": REPO_ROOT
    / ".agents/skills/evidence-ingest/scripts/validate_r5_evidence_request_review_ledger.py",
}
REGISTRY_RESULT_FIELDS = {
    "target_path",
    "action",
    "planned_action",
    "before_hash",
    "after_hash",
    "promoted_input_ids",
    "validation",
}


def load_promoter():
    spec = importlib.util.spec_from_file_location("r5_bundle4_registry_promoter", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_validator(key: str):
    name = f"r5_bundle4_physical_validator_{key}"
    spec = importlib.util.spec_from_file_location(name, VALIDATOR_SCRIPTS[key])
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def promote(
    promoter,
    *,
    scenario: str,
    output_run_dir: Path,
    workflow_id: str = FIXTURE_WORKFLOW,
    stock_code: str | None = FIXTURE_STOCK,
    dry_run: bool = False,
) -> dict[str, Any]:
    return promoter.promote_reviewed_inputs(
        repo_root=REPO_ROOT,
        workflow_id=workflow_id,
        stock_code=stock_code,
        dropzone_root=FIXTURE_ROOT / scenario,
        output_run_dir=output_run_dir,
        fixture_mode=True,
        dry_run=dry_run,
    )


def sha256_path(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def target_hashes(run_dir: Path) -> dict[str, str | None]:
    return {key: sha256_path(run_dir / name) for key, name in REGISTRY_FILES.items()}


def target_bytes(run_dir: Path) -> dict[str, bytes | None]:
    return {
        key: path.read_bytes() if path.is_file() else None
        for key, name in REGISTRY_FILES.items()
        for path in [run_dir / name]
    }


def scalar_values(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {scalar for item in value.values() for scalar in scalar_values(item)}
    if isinstance(value, list):
        return {scalar for item in value for scalar in scalar_values(item)}
    if value is None:
        return set()
    return {str(value)}


def load_registry(run_dir: Path, key: str) -> dict[str, Any]:
    data = yaml.safe_load((run_dir / REGISTRY_FILES[key]).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def physical_validation_decision(key: str, data: dict[str, Any]) -> str:
    validator = load_validator(key)
    if key == "valuation_inputs":
        issues = validator.validate_valuation_inputs(data)
        return validator.derive_decision(data, issues)
    if key == "evidence_ledger":
        issues = validator.validate_ledger(data)
        return validator.derive_decision(data, issues)
    issues = validator.validate_registry(data)
    return validator.derive_decision(data, issues)


def assert_common_result(result: dict[str, Any]) -> None:
    required = {
        "validation_status",
        "promotion_status",
        "registries_changed",
        "fixture_mode",
        "sample_quality_report_allowed",
        "p2_allowed",
        "registry_results",
    }
    assert required <= result.keys()
    assert result["fixture_mode"] is True
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False
    assert set(result["registry_results"]) == set(REGISTRY_FILES)


def assert_created_valid_registries(result: dict[str, Any], run_dir: Path) -> None:
    assert_common_result(result)
    assert result["validation_status"] == "pass"
    assert "blocked" not in str(result["promotion_status"]).lower()
    assert result["registries_changed"] is True

    for key, filename in REGISTRY_FILES.items():
        registry_result = result["registry_results"][key]
        assert REGISTRY_RESULT_FIELDS <= registry_result.keys()
        target = run_dir / filename
        assert Path(registry_result["target_path"]).resolve() == target.resolve()
        assert target.is_file()
        assert registry_result["action"] == "created"
        assert registry_result["planned_action"] == "created"
        assert registry_result["before_hash"] is None
        assert registry_result["after_hash"] == sha256_path(target)
        assert isinstance(registry_result["promoted_input_ids"], list)
        validation = registry_result["validation"]
        assert isinstance(validation, dict)
        assert validation.get("decision") != "blocked"
        physical_registry = load_registry(run_dir, key)
        assert physical_validation_decision(key, physical_registry) != "blocked"


def assert_blocked_result(result: dict[str, Any]) -> None:
    assert_common_result(result)
    assert result["validation_status"] != "pass"
    assert "blocked" in str(result["promotion_status"]).lower()
    assert result["registries_changed"] is False


def ledger_item_for_input_id(ledger: dict[str, Any], input_id: str) -> dict[str, Any]:
    items = ledger.get("items")
    assert isinstance(items, list)
    matches = [item for item in items if isinstance(item, dict) and input_id in scalar_values(item)]
    assert len(matches) == 1
    return matches[0]


def test_core_fixture_materializes_four_valid_registries(tmp_path: Path) -> None:
    promoter = load_promoter()
    output_run_dir = tmp_path / "core_run"

    result = promote(
        promoter,
        scenario="accepted_core_complete",
        output_run_dir=output_run_dir,
    )

    assert_created_valid_registries(result, output_run_dir)
    expected_by_registry = {
        "market_peer": {"fixture_core_market_001", "fixture_core_peer_001"},
        "forecast_assumptions": {
            "fixture_core_forecast_001",
            "fixture_core_forecast_002",
            "fixture_core_forecast_003",
            "fixture_core_forecast_004",
            "fixture_core_forecast_005",
        },
        "valuation_inputs": {
            "fixture_core_market_001",
            "fixture_core_peer_001",
            "fixture_core_forecast_001",
            "fixture_core_valuation_001",
        },
        "evidence_ledger": {
            "fixture_core_market_001",
            "fixture_core_peer_001",
            "fixture_core_forecast_001",
            "fixture_core_forecast_002",
            "fixture_core_forecast_003",
            "fixture_core_forecast_004",
            "fixture_core_forecast_005",
            "fixture_core_valuation_001",
        },
    }
    for key, expected_ids in expected_by_registry.items():
        assert expected_ids <= scalar_values(load_registry(output_run_dir, key))


def test_all_complete_fixture_stays_capped_below_sample_quality_and_p2(
    tmp_path: Path,
) -> None:
    promoter = load_promoter()
    output_run_dir = tmp_path / "all_complete_run"

    result = promote(
        promoter,
        scenario="accepted_all_complete",
        output_run_dir=output_run_dir,
    )

    assert_created_valid_registries(result, output_run_dir)
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False
    business_input_id = "fixture_all_business_001"
    assert business_input_id in scalar_values(load_registry(output_run_dir, "valuation_inputs"))
    business_item = ledger_item_for_input_id(
        load_registry(output_run_dir, "evidence_ledger"),
        business_input_id,
    )
    assert business_item["review_decision"] == "accepted"


def test_mixed_status_promotes_only_accepted_fact_and_ledgers_every_decision(
    tmp_path: Path,
) -> None:
    promoter = load_promoter()
    output_run_dir = tmp_path / "mixed_run"

    result = promote(promoter, scenario="mixed_status", output_run_dir=output_run_dir)

    assert_created_valid_registries(result, output_run_dir)
    accepted_id = "fixture_mixed_market_accepted"
    non_fact_ids = {
        "fixture_mixed_peer_degraded",
        "fixture_mixed_forecast_pending",
        "fixture_mixed_valuation_rejected",
    }
    fact_registry_keys = [key for key in REGISTRY_FILES if key != "evidence_ledger"]
    fact_values = set().union(
        *(scalar_values(load_registry(output_run_dir, key)) for key in fact_registry_keys)
    )
    assert accepted_id in fact_values
    assert fact_values.isdisjoint(non_fact_ids)

    ledger = load_registry(output_run_dir, "evidence_ledger")
    accepted_item = ledger_item_for_input_id(ledger, accepted_id)
    assert accepted_item["review_decision"] == "accepted"
    for input_id in non_fact_ids:
        item = ledger_item_for_input_id(ledger, input_id)
        assert item["review_decision"] != "accepted"


def test_invalid_input_keeps_existing_registry_bytes_and_hashes_unchanged(
    tmp_path: Path,
) -> None:
    promoter = load_promoter()
    output_run_dir = tmp_path / "atomic_run"
    first = promote(
        promoter,
        scenario="accepted_core_complete",
        output_run_dir=output_run_dir,
    )
    assert_created_valid_registries(first, output_run_dir)
    before_bytes = target_bytes(output_run_dir)
    before_hashes = target_hashes(output_run_dir)

    blocked = promote(
        promoter,
        scenario="invalid_cross_stock",
        output_run_dir=output_run_dir,
    )

    assert_blocked_result(blocked)
    assert target_bytes(output_run_dir) == before_bytes
    assert target_hashes(output_run_dir) == before_hashes
    for key, registry_result in blocked["registry_results"].items():
        assert REGISTRY_RESULT_FIELDS <= registry_result.keys()
        assert registry_result["action"] == "blocked"
        assert registry_result["before_hash"] == before_hashes[key]
        assert registry_result["after_hash"] == before_hashes[key]


def test_fixture_mode_rejects_real_workflow_and_real_committed_run(
    tmp_path: Path,
) -> None:
    promoter = load_promoter()
    disposable_run = tmp_path / "must_remain_empty"

    real_workflow_result = promote(
        promoter,
        scenario="accepted_core_complete",
        output_run_dir=disposable_run,
        workflow_id=REAL_WORKFLOW,
        stock_code="002837",
    )

    assert_blocked_result(real_workflow_result)
    assert all(value is None for value in target_hashes(disposable_run).values())

    real_before = target_bytes(REAL_RUN_DIR)
    real_run_result = promote(
        promoter,
        scenario="accepted_core_complete",
        output_run_dir=REAL_RUN_DIR,
        dry_run=True,
    )

    assert_blocked_result(real_run_result)
    assert target_bytes(REAL_RUN_DIR) == real_before


@pytest.mark.parametrize(
    ("workflow_id", "stock_code"),
    [
        ("wf_fixture_r5_bundle4_wrong", FIXTURE_STOCK),
        (FIXTURE_WORKFLOW, "999999"),
    ],
)
def test_cli_identity_mismatch_is_blocked_without_registry_writes(
    tmp_path: Path,
    workflow_id: str,
    stock_code: str,
) -> None:
    output_run_dir = tmp_path / f"cli_{stock_code}"
    result_path = tmp_path / f"cli_result_{stock_code}.json"
    command = [
        sys.executable,
        str(SCRIPT),
        "--repo-root",
        str(REPO_ROOT),
        "--workflow-id",
        workflow_id,
        "--stock-code",
        stock_code,
        "--dropzone-root",
        str(FIXTURE_ROOT / "accepted_core_complete"),
        "--output-run-dir",
        str(output_run_dir),
        "--fixture-mode",
        "--json",
        str(result_path),
    ]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert result_path.is_file(), completed.stderr
    result = yaml.safe_load(result_path.read_text(encoding="utf-8"))
    assert isinstance(result, dict)
    assert_blocked_result(result)
    assert all(value is None for value in target_hashes(output_run_dir).values())
