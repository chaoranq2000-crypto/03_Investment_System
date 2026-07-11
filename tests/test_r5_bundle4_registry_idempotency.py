from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/promote_r5_reviewed_inputs_to_registries.py"
FIXTURE_ROOT = REPO_ROOT / "tests/fixtures/r5_reviewed_inputs"
FIXTURE_WORKFLOW = "wf_fixture_r5_bundle4"
FIXTURE_STOCK = "000000"
REGISTRY_FILES = {
    "market_peer": "R5_market_peer_input_registry.yaml",
    "forecast_assumptions": "R5_forecast_assumption_registry.yaml",
    "valuation_inputs": "R5_valuation_input_registry.yaml",
    "evidence_ledger": "R5_evidence_request_review_ledger.yaml",
}


def load_promoter():
    spec = importlib.util.spec_from_file_location("r5_bundle4_idempotency_promoter", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def promote(promoter, *, output_run_dir: Path, dry_run: bool = False) -> dict[str, Any]:
    return promoter.promote_reviewed_inputs(
        repo_root=REPO_ROOT,
        workflow_id=FIXTURE_WORKFLOW,
        stock_code=FIXTURE_STOCK,
        dropzone_root=FIXTURE_ROOT / "accepted_core_complete",
        output_run_dir=output_run_dir,
        fixture_mode=True,
        dry_run=dry_run,
    )


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def target_bytes(run_dir: Path) -> dict[str, bytes]:
    return {key: (run_dir / name).read_bytes() for key, name in REGISTRY_FILES.items()}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def test_second_identical_promotion_is_byte_stable_and_all_unchanged(
    tmp_path: Path,
) -> None:
    promoter = load_promoter()
    output_run_dir = tmp_path / "idempotent_run"

    first = promote(promoter, output_run_dir=output_run_dir)
    first_bytes = target_bytes(output_run_dir)
    first_hashes = {
        key: sha256_path(output_run_dir / filename)
        for key, filename in REGISTRY_FILES.items()
    }
    second = promote(promoter, output_run_dir=output_run_dir)

    assert first["validation_status"] == "pass"
    assert first["registries_changed"] is True
    assert all(item["action"] == "created" for item in first["registry_results"].values())
    assert second["validation_status"] == "pass"
    assert second["registries_changed"] is False
    assert second["fixture_mode"] is True
    assert second["sample_quality_report_allowed"] is False
    assert second["p2_allowed"] is False
    assert target_bytes(output_run_dir) == first_bytes
    for key, registry_result in second["registry_results"].items():
        assert registry_result["action"] == "unchanged"
        assert registry_result["planned_action"] == "unchanged"
        assert registry_result["before_hash"] == first_hashes[key]
        assert registry_result["after_hash"] == first_hashes[key]
        assert registry_result["promoted_input_ids"] == first["registry_results"][key][
            "promoted_input_ids"
        ]
        assert registry_result["validation"]["decision"] != "blocked"


def test_dry_run_plans_creation_without_writing_then_matches_real_hashes(
    tmp_path: Path,
) -> None:
    promoter = load_promoter()
    output_run_dir = tmp_path / "dry_run"

    planned = promote(promoter, output_run_dir=output_run_dir, dry_run=True)

    assert planned["validation_status"] == "pass"
    assert planned["registries_changed"] is False
    assert planned["fixture_mode"] is True
    assert planned["sample_quality_report_allowed"] is False
    assert planned["p2_allowed"] is False
    assert not output_run_dir.exists() or not any(output_run_dir.iterdir())
    planned_hashes: dict[str, str] = {}
    for key, registry_result in planned["registry_results"].items():
        assert registry_result["action"] == "unchanged"
        assert registry_result["planned_action"] == "created"
        assert registry_result["before_hash"] is None
        assert isinstance(registry_result["after_hash"], str)
        assert len(registry_result["after_hash"]) == 64
        assert registry_result["validation"]["decision"] != "blocked"
        planned_hashes[key] = registry_result["after_hash"]

    materialized = promote(promoter, output_run_dir=output_run_dir)

    assert materialized["registries_changed"] is True
    for key, filename in REGISTRY_FILES.items():
        assert materialized["registry_results"][key]["action"] == "created"
        assert materialized["registry_results"][key]["after_hash"] == planned_hashes[key]
        assert sha256_path(output_run_dir / filename) == planned_hashes[key]


def test_merge_preserves_unrelated_valid_market_field_and_ledger_item(
    tmp_path: Path,
) -> None:
    promoter = load_promoter()
    output_run_dir = tmp_path / "preserve_run"
    first = promote(promoter, output_run_dir=output_run_dir)
    assert first["registries_changed"] is True

    market_path = output_run_dir / REGISTRY_FILES["market_peer"]
    market = load_yaml(market_path)
    unrelated_market_field = {
        "value": 77.0,
        "unit": "synthetic_unit",
        "evidence_id": "ev_fixture_unrelated_market",
        "source_type": "market_snapshot",
        "input_id": "fixture_unrelated_existing_market",
        "source_rank": "B",
        "as_of_date": "2026-06-29",
        "reviewer": "fixture_reviewer",
        "reviewed_at": "2026-07-10T08:00:00+08:00",
        "limitations": ["synthetic test data", "not research evidence"],
    }
    market["market_inputs"]["unrelated_existing_field"] = unrelated_market_field
    write_yaml(market_path, market)

    ledger_path = output_run_dir / REGISTRY_FILES["evidence_ledger"]
    ledger = load_yaml(ledger_path)
    unrelated_ledger_item = {
        "request_id": "fixture_unrelated_request_001",
        "source_gap_id": "FIXTURE_UNRELATED_GAP_001",
        "pack_section": "fixture_unrelated_section",
        "review_decision": "accepted",
        "evidence_id": "ev_fixture_unrelated_ledger",
        "source_rank": "B",
        "reason": "preserve unrelated reviewed item",
        "next_action": "retain existing reviewed evidence",
        "input_id": "fixture_unrelated_existing_ledger",
        "no_live_api": True,
        "limitations": ["synthetic test data", "not research evidence"],
    }
    ledger["items"].append(unrelated_ledger_item)
    write_yaml(ledger_path, ledger)

    merged = promote(promoter, output_run_dir=output_run_dir)

    assert merged["validation_status"] == "pass"
    assert merged["registry_results"]["market_peer"]["validation"]["decision"] != "blocked"
    assert merged["registry_results"]["evidence_ledger"]["validation"]["decision"] != "blocked"
    merged_market = load_yaml(market_path)
    assert merged_market["market_inputs"]["unrelated_existing_field"] == unrelated_market_field
    merged_ledger = load_yaml(ledger_path)
    retained = [
        item
        for item in merged_ledger["items"]
        if item.get("request_id") == unrelated_ledger_item["request_id"]
    ]
    assert retained == [unrelated_ledger_item]

    stable_bytes = target_bytes(output_run_dir)
    repeated = promote(promoter, output_run_dir=output_run_dir)
    assert repeated["registries_changed"] is False
    assert all(item["action"] == "unchanged" for item in repeated["registry_results"].values())
    assert target_bytes(output_run_dir) == stable_bytes


def test_commit_failure_rolls_back_all_registry_bytes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    promoter = load_promoter()
    output_run_dir = tmp_path / "rollback_run"
    first = promote(promoter, output_run_dir=output_run_dir)
    assert first["registries_changed"] is True
    before = target_bytes(output_run_dir)

    changed_fixture = tmp_path / "changed_fixture"
    shutil.copytree(FIXTURE_ROOT / "accepted_core_complete", changed_fixture)
    market_path = changed_fixture / "market_snapshot/market.yaml"
    market = load_yaml(market_path)
    market["records"][0]["close_price"] = 10.5
    write_yaml(market_path, market)
    forecast_path = changed_fixture / "forecast_assumptions/forecast.yaml"
    forecast = load_yaml(forecast_path)
    forecast["records"][0]["value"] = 5.5
    write_yaml(forecast_path, forecast)

    original_replace = promoter.registry_io.os.replace
    calls = {"count": 0}

    def fail_second_replace(source, target):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("injected second replace failure")
        return original_replace(source, target)

    monkeypatch.setattr(promoter.registry_io.os, "replace", fail_second_replace)
    result = promoter.promote_reviewed_inputs(
        repo_root=REPO_ROOT,
        workflow_id=FIXTURE_WORKFLOW,
        stock_code=FIXTURE_STOCK,
        dropzone_root=changed_fixture,
        output_run_dir=output_run_dir,
        fixture_mode=True,
        dry_run=False,
    )

    assert result["validation_status"] == "fail"
    assert result["promotion_status"] == "blocked_atomic_commit"
    assert result["registries_changed"] is False
    assert target_bytes(output_run_dir) == before
    assert not list(output_run_dir.glob(".*.tmp"))
