from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDER_SCRIPT = REPO_ROOT / "scripts/build_r5_reviewed_input_dry_run_from_registries.py"
PROMOTER_SCRIPT = REPO_ROOT / "scripts/promote_r5_reviewed_inputs_to_registries.py"
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
REVIEWED_FLAGS = (
    "reviewed_market_inputs_available",
    "reviewed_peer_inputs_available",
    "reviewed_forecast_assumptions_available",
    "reviewed_valuation_inputs_available",
    "reviewed_business_disclosure_available",
)
CRITICAL_TODOS = (
    "TODO_MARKET_DATA",
    "TODO_PEER_DATA",
    "TODO_MODEL_INPUT",
    "MISSING_DISCLOSURE",
    "TODO_SOURCE_REQUIRED",
)
REAL_READ_TARGETS = (
    *REGISTRY_FILES.values(),
    "R5_reviewed_input_registry_promotion_result.yaml",
    "R5_reviewed_input_dry_run_result.yaml",
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def promoter():
    return load_module("r5_bundle4_post_promotion_promoter", PROMOTER_SCRIPT)


@pytest.fixture(scope="module")
def builder():
    return load_module("r5_bundle4_post_promotion_builder", BUILDER_SCRIPT)


def promote_fixture(promoter, tmp_path: Path, scenario: str):
    run_dir = tmp_path / scenario / "run"
    result_path = tmp_path / scenario / "promotion_result.yaml"
    result = promoter.promote_reviewed_inputs(
        repo_root=REPO_ROOT,
        workflow_id=FIXTURE_WORKFLOW,
        stock_code=FIXTURE_STOCK,
        dropzone_root=FIXTURE_ROOT / scenario,
        output_run_dir=run_dir,
        fixture_mode=True,
        dry_run=False,
    )
    assert result["validation_status"] == "pass"
    assert "blocked" not in result["promotion_status"]
    result_path.write_bytes(promoter.registry_io.dump_yaml_bytes(result))
    return run_dir, result_path, result


def build(builder, run_dir: Path, promotion_result_path: Path | None = None):
    return builder.build_dry_run_from_registries(
        run_dir,
        True,
        promotion_result_path=promotion_result_path,
        repo_root=REPO_ROOT,
    )


def trace_by_token(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    trace = result["todo_trace"]
    assert [row["token"] for row in trace] == list(CRITICAL_TODOS)
    required = {
        "token",
        "status",
        "resolving_input_ids",
        "registry_path",
        "field",
        "evidence_ids",
        "reason",
    }
    assert all(required <= row.keys() for row in trace)
    return {row["token"]: row for row in trace}


def sha256_path(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def target_hashes(run_dir: Path, names: tuple[str, ...]) -> dict[str, str | None]:
    return {name: sha256_path(run_dir / name) for name in names}


@pytest.mark.parametrize("create_empty_dir", [False, True], ids=["missing", "empty"])
def test_missing_or_empty_registries_keep_every_flag_false(
    builder,
    tmp_path: Path,
    create_empty_dir: bool,
) -> None:
    run_dir = tmp_path / "empty_or_missing"
    if create_empty_dir:
        run_dir.mkdir()

    result = build(builder, run_dir)

    assert result["validation_status"] == "fail"
    assert all(result[flag] is False for flag in REVIEWED_FLAGS)
    assert result["remaining_todos"] == list(CRITICAL_TODOS)
    assert result["blockers"]
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False


def test_core_complete_derives_four_flags_and_only_independent_gap(
    builder,
    promoter,
    tmp_path: Path,
) -> None:
    run_dir, promotion_path, _promotion = promote_fixture(
        promoter, tmp_path, "accepted_core_complete"
    )

    result = build(builder, run_dir, promotion_path)
    trace = trace_by_token(result)

    assert result["validation_status"] == "pass"
    assert result["reviewed_market_inputs_available"] is True
    assert result["reviewed_peer_inputs_available"] is True
    assert result["reviewed_forecast_assumptions_available"] is True
    assert result["reviewed_valuation_inputs_available"] is True
    assert result["reviewed_business_disclosure_available"] is False
    assert result["remaining_todos"] == ["MISSING_DISCLOSURE"]
    assert trace["MISSING_DISCLOSURE"]["status"] == "remaining"
    assert trace["MISSING_DISCLOSURE"]["resolving_input_ids"] == []
    for token in set(CRITICAL_TODOS) - {"MISSING_DISCLOSURE"}:
        assert trace[token]["status"] == "resolved"
        assert trace[token]["resolving_input_ids"]
        assert trace[token]["evidence_ids"]


def test_all_complete_sets_five_flags_but_fixture_caps_sample_quality_and_p2(
    builder,
    promoter,
    tmp_path: Path,
) -> None:
    run_dir, promotion_path, _promotion = promote_fixture(
        promoter, tmp_path, "accepted_all_complete"
    )

    result = build(builder, run_dir, promotion_path)

    assert result["validation_status"] == "pass"
    assert all(result[flag] is True for flag in REVIEWED_FLAGS)
    assert result["remaining_todos"] == []
    assert result["fixture_mode"] is True
    assert result["allowed_report_level"] == "reviewed_input_research_draft"
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False


def test_valuation_flag_requires_evidence_anchored_valuation_input_refs(
    builder,
    promoter,
    tmp_path: Path,
) -> None:
    run_dir, _promotion_path, _promotion = promote_fixture(
        promoter, tmp_path, "accepted_core_complete"
    )
    registry_io = promoter.registry_io
    valuation_path = run_dir / REGISTRY_FILES["valuation_inputs"]
    valuation = registry_io.load_yaml(valuation_path)
    valuation["valuation_input_refs"] = []
    valuation_path.write_bytes(registry_io.dump_yaml_bytes(valuation))

    result = build(builder, run_dir)

    assert result["reviewed_market_inputs_available"] is True
    assert result["reviewed_peer_inputs_available"] is True
    assert result["reviewed_forecast_assumptions_available"] is True
    assert result["reviewed_valuation_inputs_available"] is False
    assert "TODO_SOURCE_REQUIRED" in result["remaining_todos"]
    assert any(
        blocker.get("registry") == "valuation_inputs"
        and "valuation_input_refs" in blocker.get("reason", "")
        for blocker in result["blockers"]
    )


def test_tampered_market_evidence_and_promotion_hash_fail_closed(
    builder,
    promoter,
    tmp_path: Path,
) -> None:
    run_dir, promotion_path, promotion = promote_fixture(
        promoter, tmp_path, "accepted_core_complete"
    )
    registry_io = promoter.registry_io
    market_path = run_dir / REGISTRY_FILES["market_peer"]
    market = registry_io.load_yaml(market_path)
    market["market_inputs"]["current_price"]["evidence_id"] = None
    market_path.write_bytes(registry_io.dump_yaml_bytes(market))

    result = build(builder, run_dir, promotion_path)

    expected_hash = promotion["registry_results"]["market_peer"]["after_hash"]
    assert result["validation_status"] == "fail"
    assert result["reviewed_market_inputs_available"] is False
    assert result["registry_sources"]["market_peer"]["sha256"] != expected_hash
    assert any(
        blocker.get("registry") == "market_peer"
        and "hash" in blocker.get("reason", "").lower()
        for blocker in result["blockers"]
    )


@pytest.mark.parametrize(
    ("identity_field", "wrong_value"),
    [
        ("workflow_id", "wf_fixture_r5_bundle4_wrong"),
        ("stock_code", "999999"),
    ],
)
def test_cross_registry_identity_mismatch_blocks_all_flags(
    builder,
    promoter,
    tmp_path: Path,
    identity_field: str,
    wrong_value: str,
) -> None:
    run_dir, _promotion_path, _promotion = promote_fixture(
        promoter, tmp_path, "accepted_core_complete"
    )
    registry_io = promoter.registry_io
    forecast_path = run_dir / REGISTRY_FILES["forecast_assumptions"]
    forecast = registry_io.load_yaml(forecast_path)
    forecast[identity_field] = wrong_value
    forecast_path.write_bytes(registry_io.dump_yaml_bytes(forecast))

    result = build(builder, run_dir)

    assert result["validation_status"] == "fail"
    assert all(result[flag] is False for flag in REVIEWED_FLAGS)
    assert any(identity_field in blocker.get("reason", "") for blocker in result["blockers"])


def test_repeated_result_is_byte_stable_through_registry_serializer(
    builder,
    promoter,
    tmp_path: Path,
) -> None:
    run_dir, promotion_path, _promotion = promote_fixture(
        promoter, tmp_path, "accepted_core_complete"
    )

    first = build(builder, run_dir, promotion_path)
    second = build(builder, run_dir, promotion_path)

    first_bytes = promoter.registry_io.dump_yaml_bytes(first)
    second_bytes = promoter.registry_io.dump_yaml_bytes(second)
    assert first_bytes == second_bytes


def test_reading_real_002837_run_does_not_change_any_target_hash(builder) -> None:
    promotion_path = REAL_RUN_DIR / "R5_reviewed_input_registry_promotion_result.yaml"
    before = target_hashes(REAL_RUN_DIR, REAL_READ_TARGETS)

    builder.build_dry_run_from_registries(
        REAL_RUN_DIR,
        False,
        promotion_result_path=promotion_path,
        repo_root=REPO_ROOT,
    )

    assert target_hashes(REAL_RUN_DIR, REAL_READ_TARGETS) == before
