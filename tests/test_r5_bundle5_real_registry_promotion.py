from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
HISTORICAL_RUN = f"reports/workflow_runs/{WORKFLOW_ID}"
RETAINED_DROPZONE = REPO_ROOT / "data/reviewed_inputs" / WORKFLOW_ID
RUNNER_PATH = REPO_ROOT / "scripts/run_r5_bundle5_real_registry_promotion.py"
STAGING_PATH = REPO_ROOT / "scripts/build_r5_reviewed_input_staging.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load_module("r5_bundle5_real_registry_runner_test", RUNNER_PATH)
STAGING = load_module("r5_bundle5_staging_cap_test", STAGING_PATH)


@pytest.fixture
def registry_fixture(historical_blob_file) -> tuple[Path, Path]:
    registry_sources = list(RUNNER.promoter.REGISTRY_FILENAMES.values())
    first_registry = None
    for filename in registry_sources:
        path = historical_blob_file(
            f"{HISTORICAL_RUN}/{filename}",
            f"registry_case/run/{filename}",
        )
        first_registry = first_registry or path
    assert first_registry is not None
    return RETAINED_DROPZONE, first_registry.parent


def test_complete_real_dropzone_is_capped_at_research_draft(
    registry_fixture: tuple[Path, Path],
) -> None:
    dropzone_root, run_dir = registry_fixture
    staging = STAGING.build_staging_result(
        repo_root=REPO_ROOT,
        workflow_id=WORKFLOW_ID,
        dropzone_root=dropzone_root,
    )
    assert staging["validation_status"] == "pass"
    assert staging["accepted_count"] == 22
    assert staging["allowed_report_level"] == "reviewed_input_research_draft"
    assert staging["sample_quality_report_allowed"] is False
    assert staging["p2_allowed"] is False

    dry_run = RUNNER.promoter.promote_reviewed_inputs(
        repo_root=REPO_ROOT,
        workflow_id=WORKFLOW_ID,
        stock_code="002837",
        dropzone_root=dropzone_root,
        output_run_dir=run_dir,
        fixture_mode=False,
        dry_run=True,
    )
    assert dry_run["promotion_status"] == "dry_run_ready"
    assert dry_run["allowed_report_level"] == "reviewed_input_research_draft"
    assert dry_run["sample_quality_report_allowed"] is False
    assert dry_run["p2_allowed"] is False


def test_prepromotion_inventory_covers_all_inputs_and_targets(
    registry_fixture: tuple[Path, Path],
) -> None:
    dropzone_root, run_dir = registry_fixture
    dry_run = RUNNER.promoter.promote_reviewed_inputs(
        repo_root=REPO_ROOT,
        workflow_id=WORKFLOW_ID,
        stock_code="002837",
        dropzone_root=dropzone_root,
        output_run_dir=run_dir,
        fixture_mode=False,
        dry_run=True,
    )
    inventory = RUNNER.build_prepromotion_inventory(
        REPO_ROOT,
        run_dir,
        dropzone_root,
        dry_run,
        workflow_id=WORKFLOW_ID,
        stock_code="002837",
    )
    assert inventory["accepted_count"] == 22
    assert inventory["accepted_degraded_count"] == 0
    assert sum(row["record_count"] for row in inventory["input_files"]) == 22
    assert set(inventory["registry_targets"]) == set(RUNNER.promoter.REGISTRY_FILENAMES)
    assert inventory["dry_run"]["promotion_status"] == "dry_run_ready"
    assert inventory["hard_boundaries"]["sample_quality_report_allowed"] is False
    assert inventory["hard_boundaries"]["p2_allowed"] is False


def test_fully_reviewed_forecast_merge_drops_stale_todo_interlock(
    registry_fixture: tuple[Path, Path],
) -> None:
    dropzone_root, run_dir = registry_fixture
    records = [
        row
        for row in RUNNER.promoter.collect_records(dropzone_root)
        if row.get("review_status") == "accepted"
    ]
    conflicts: list[str] = []
    existing = RUNNER.registry_io.load_yaml(
        run_dir / "R5_forecast_assumption_registry.yaml"
    )
    workflow_id = existing["workflow_id"]
    candidate = RUNNER.promoter._build_forecast_registry(
        workflow_id,
        "002837",
        records,
        conflicts,
    )
    merged = RUNNER.promoter._merge_forecast(
        existing,
        candidate,
        workflow_id,
        "002837",
        conflicts,
    )
    assert conflicts == []
    assert merged["review_status"] == "reviewed"
    assert "forecast_model_interlock" not in merged
    assert merged["sample_quality_report_allowed"] is False
    assert merged["p2_allowed"] is False
    assert "TODO_MODEL_INPUT" not in yaml.safe_dump(merged, allow_unicode=True)


def test_backup_restore_round_trip_handles_existing_and_missing_targets(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    run_dir = repo / "run_fixture"
    run_dir.mkdir(parents=True)
    target_states = {
        "market_peer": b"artifact_type: old_market\n",
        "forecast_assumptions": b"artifact_type: old_forecast\n",
        "valuation_inputs": None,
        "evidence_ledger": b"artifact_type: old_ledger\n",
    }
    targets = RUNNER.registry_paths(run_dir)
    for key, data in target_states.items():
        if data is not None:
            targets[key].write_bytes(data)
    inventory = {
        "workflow_id": "wf_fixture_backup_restore",
        "inventory_signature": "a" * 64,
        "registry_targets": {
            key: {
                "path": target.relative_to(repo).as_posix(),
                "exists": target_states[key] is not None,
                "sha256": RUNNER._sha256(target),
            }
            for key, target in targets.items()
        },
    }
    manifest = RUNNER.create_backup_manifest(repo, run_dir, inventory)
    assert manifest["backup_verified"] is True
    for target in targets.values():
        target.write_text("artifact_type: changed\n", encoding="utf-8")
    restored = RUNNER.restore_from_backup(repo, manifest)
    for key, expected in target_states.items():
        target = targets[key]
        if expected is None:
            assert not target.exists()
            assert restored[key] is None
        else:
            assert target.read_bytes() == expected
            assert restored[key] == RUNNER._sha256(target)


def test_recorded_real_promotion_is_byte_and_semantic_idempotent(
    historical_blob_bytes,
) -> None:
    import json

    result_source = f"{HISTORICAL_RUN}/R5_bundle5_registry_idempotency_result.json"
    result = json.loads(historical_blob_bytes(result_source).decode("utf-8"))
    assert result["status"] == "pass"
    assert result["byte_level_idempotent"] is True
    assert result["semantic_idempotent"] is True
    assert set(result["second_actions"].values()) == {"unchanged"}
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False

    backup_source = f"{HISTORICAL_RUN}/R5_bundle5_registry_backup_manifest.yaml"
    backup = yaml.safe_load(historical_blob_bytes(backup_source).decode("utf-8"))
    assert backup["backup_verified"] is True
    assert len(backup["items"]) == 4
