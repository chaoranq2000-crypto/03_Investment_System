from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
RUN_DIR = REPO_ROOT / "reports/workflow_runs" / WORKFLOW_ID
DROPZONE = REPO_ROOT / "data/reviewed_inputs" / WORKFLOW_ID
MANIFEST_PATH = REPO_ROOT / "config/r5_bundle5_expected_artifacts.yaml"
TRUTHFULNESS_PATH = REPO_ROOT / "reports/p1_6/r5_bundle5_readout_truthfulness_result.json"
CLOSE_READOUT = REPO_ROOT / "reports/p1_6/R5_BUNDLE_5_REAL_REVIEWED_INPUT_ONBOARDING_CLOSE_READOUT.md"
CANONICAL_INDEX = REPO_ROOT / "reports/p1_6/R5_READOUT_CANONICAL_INDEX.md"
PRECHECK_SCRIPT = REPO_ROOT / "scripts/build_r5_bundle5_benchmark_coverage_precheck.py"


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def load_precheck_module():
    spec = importlib.util.spec_from_file_location("r5_bundle5_close_precheck", PRECHECK_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PRECHECK = load_precheck_module()


def manifest_owned_paths(manifest: dict[str, Any]) -> list[str]:
    paths = list(manifest.get("baseline_required_paths") or [])
    for card in (manifest.get("cards") or {}).values():
        if not isinstance(card, dict):
            continue
        for row in card.get("owned_artifacts") or []:
            if isinstance(row, dict) and row.get("path"):
                paths.append(str(row["path"]))
    return sorted(set(paths))


def accepted_dropzone_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(DROPZONE.rglob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        rows = data.get("records") if isinstance(data, dict) else None
        if isinstance(rows, list):
            records.extend(row for row in rows if isinstance(row, dict) and row.get("review_status") == "accepted")
    return records


def test_manifest_declared_bundle5_artifacts_are_physical_and_boundaries_closed() -> None:
    manifest = load_yaml(MANIFEST_PATH)

    assert manifest["bundle"] == "R5_BUNDLE_5_REAL_002837_REVIEWED_INPUT_ONBOARDING"
    assert manifest["fixed_boundaries"]["sample_quality_report_allowed"] is False
    assert manifest["fixed_boundaries"]["p2_allowed"] is False
    paths = manifest_owned_paths(manifest)
    assert paths
    assert [path for path in paths if not (REPO_ROOT / path).exists()] == []


def test_all_22_accepted_real_inputs_have_review_and_evidence_provenance() -> None:
    records = accepted_dropzone_records()
    assert len(records) == 22
    assert len({row["input_id"] for row in records}) == 22

    with (REPO_ROOT / "data/manifests/evidence_manifest.csv").open("r", encoding="utf-8", newline="") as handle:
        evidence_rows = {row["evidence_id"]: row for row in csv.DictReader(handle)}
    for row in records:
        assert row["workflow_id"] == WORKFLOW_ID
        assert str(row["stock_code"]) == "002837"
        assert row.get("reviewer")
        assert row.get("reviewed_at")
        assert row.get("source_rank") in {"A", "B"}
        evidence_id = row.get("source_evidence_id")
        assert evidence_id in evidence_rows
        raw_path = evidence_rows[evidence_id].get("raw_file_path")
        assert raw_path and (REPO_ROOT / raw_path).is_file()
        text = yaml.safe_dump(row, allow_unicode=True).lower()
        assert "fixture" not in text
        assert "sample_report" not in text
        assert "template" not in text


def test_staging_promotion_and_registry_readiness_reconcile() -> None:
    staging = load_yaml(RUN_DIR / "R5_bundle5_reviewed_input_staging.yaml")
    promotion = load_yaml(RUN_DIR / "R5_bundle5_registry_promotion_result.yaml")
    dry_run = load_yaml(RUN_DIR / "R5_reviewed_input_dry_run_result.yaml")

    assert staging["validation_status"] == "pass"
    assert promotion["validation_status"] == "pass"
    assert staging["accepted_count"] == promotion["accepted_count"] == 22
    assert set(staging["accepted_input_ids"]) == set(promotion["accepted_input_ids"])
    assert promotion["accepted_degraded_count"] == 0
    assert promotion["promotion_status"] == "accepted_inputs_promoted"
    assert dry_run["derivation_source"] == "validated_physical_registries"
    assert dry_run["validation_status"] == "pass"
    for flag in [
        "reviewed_market_inputs_available",
        "reviewed_peer_inputs_available",
        "reviewed_forecast_assumptions_available",
        "reviewed_business_disclosure_available",
        "reviewed_valuation_inputs_available",
    ]:
        assert dry_run[flag] is True
    assert dry_run["remaining_todos"] == []
    assert promotion["sample_quality_report_allowed"] is False
    assert promotion["p2_allowed"] is False


def test_registry_promotion_is_backup_protected_and_idempotent() -> None:
    inventory = load_yaml(RUN_DIR / "R5_bundle5_prepromotion_inventory.yaml")
    backup = load_yaml(RUN_DIR / "R5_bundle5_registry_backup_manifest.yaml")
    idempotency = load_json(RUN_DIR / "R5_bundle5_registry_idempotency_result.json")

    assert inventory["dropzone_validation_status"] == "pass"
    assert inventory["accepted_count"] == 22
    assert inventory["inventory_signature"] == backup["inventory_signature"]
    assert backup["backup_verified"] is True
    assert len(backup["items"]) == 4
    for row in backup["items"]:
        if row["pre_exists"]:
            assert row["pre_hash"] == row["backup_hash"]
            assert (REPO_ROOT / row["backup_path"]).is_file()
        else:
            assert row["action"] == "recorded_missing_target"
            assert row["backup_path"] is None
    assert "restore" in backup["restore_strategy"]
    assert idempotency["status"] == "pass"
    assert idempotency["byte_level_idempotent"] is True
    assert idempotency["semantic_idempotent"] is True
    assert idempotency["first_hashes"] == idempotency["second_hashes"]
    assert set(idempotency["second_actions"].values()) == {"unchanged"}


def test_core_pack_pilot_render_and_quality_gates_agree() -> None:
    core = load_yaml(RUN_DIR / "R5_bundle5_core_asset_preflight.yaml")
    gate = load_json(RUN_DIR / "R5_bundle5_real_pilot_gate_result.json")
    render = load_yaml(RUN_DIR / "R5_reviewed_input_render_result.yaml")
    quality = load_yaml(RUN_DIR / "R5_bundle5_quality_gate_result.yaml")

    assert core["blockers"] == []
    assert {core[key] for key in ["financial_history_status", "business_breakdown_status", "forecast_model_status", "valuation_status"]} <= {"accepted", "accepted_with_todos"}
    assert gate["current_r5_state"] == "R5_REVIEWED_INPUT_PILOT_ALLOWED"
    assert gate["reviewed_input_pilot_allowed"] is True
    assert gate["blockers"] == []
    assert gate["input_summary"]["pack_promotion_level"] == "reviewed_input_research_draft"
    assert render["input_gate_state"] == gate["current_r5_state"]
    assert render["rendered_output_type"] == "reviewed_input_research_draft"
    assert quality["quality_decision"] == "accepted_with_todos"
    assert quality["critical_quality_blockers"] == 0
    for artifact in [core, gate, render, quality]:
        assert artifact["sample_quality_report_allowed"] is False
        assert artifact["p2_allowed"] is False


def test_benchmark_is_nonpromoting_and_sample_content_is_not_evidence() -> None:
    benchmark = load_yaml(RUN_DIR / "R5_bundle5_benchmark_coverage_precheck.yaml")

    assert benchmark["precheck_status"] == "pass"
    assert benchmark["coverage_summary"]["total"] == 10
    assert benchmark["sample_evidence_registered_count"] == 0
    assert benchmark["forbidden_language_check"]["match_count"] == 0
    assert benchmark["precheck_only"] is True
    assert benchmark["promotion_decision"] is False
    assert benchmark["canonical_registry_write_performed"] is False
    assert benchmark["sample_quality_report_allowed"] is False
    assert benchmark["p2_allowed"] is False


def test_real_draft_keeps_traceability_risk_counterevidence_and_source_gaps() -> None:
    profile = load_yaml(REPO_ROOT / "codex_tasks/r5_after_bundle4/SAMPLE_REPORT_BENCHMARK_PROFILE.yaml")
    report = (RUN_DIR / "R5_stock_research_note_reviewed_input_draft.md").read_text(encoding="utf-8")

    assert PRECHECK.find_forbidden_language(report, profile) == []
    for marker in [
        "Source Gap Appendix",
        "Open Questions",
        "MISSING_DISCLOSURE",
        "风险、反证与开放问题",
        "fact",
        "estimate",
        "inference",
        "ev_annual_report_002837_20260421_2cbfc5",
        "ev_quarterly_report_002837_20260421_2f00c7",
        "ev_structured_market_data_002837_20260710_eb0c08",
    ]:
        assert marker in report
    for token in ["TODO_MARKET_DATA", "TODO_PEER_DATA", "TODO_MODEL_INPUT"]:
        assert token not in report


def test_bundle5_truthfulness_and_canonical_index_are_complete() -> None:
    truthfulness = load_json(TRUTHFULNESS_PATH)
    index_text = CANONICAL_INDEX.read_text(encoding="utf-8")

    assert truthfulness["truthfulness_status"] == "pass"
    assert truthfulness["checked"] == 8
    assert truthfulness["failed"] == 0
    assert len(truthfulness["results"]) == 8
    assert all(row["status"] == "pass" for row in truthfulness["results"])
    expected_readouts = [
        "R5_BUNDLE_5_1_REAL_INPUT_INVENTORY_READOUT.md",
        "R5_BUNDLE_5_2_OFFICIAL_DISCLOSURE_FINANCIAL_READOUT.md",
        "R5_BUNDLE_5_3_MARKET_PEER_INPUT_READOUT.md",
        "R5_BUNDLE_5_4_FORECAST_VALUATION_INPUT_READOUT.md",
        "R5_BUNDLE_5_5_REAL_REGISTRY_PROMOTION_READOUT.md",
        "R5_BUNDLE_5_6_RESEARCH_DRAFT_RENDER_QUALITY_READOUT.md",
        "R5_BUNDLE_5_7_BENCHMARK_COVERAGE_PRECHECK_READOUT.md",
        "R5_BUNDLE_5_REAL_REVIEWED_INPUT_ONBOARDING_CLOSE_READOUT.md",
    ]
    assert all(name in index_text for name in expected_readouts)


def test_close_readout_preserves_target_mapping_and_hard_boundaries() -> None:
    text = CLOSE_READOUT.read_text(encoding="utf-8")

    assert "R5_REVIEWED_INPUT_PILOT_ALLOWED" in text
    assert "R5_REAL_002837_REVIEWED_INPUT_RESEARCH_DRAFT_READY" in text
    assert "real_reviewed_inputs_supplied: `true`" in text
    assert "real_registry_promotion_completed: `true`" in text
    assert "reviewed_input_research_draft_rendered: `true`" in text
    assert "sample_quality_report_allowed: `false`" in text
    assert "p2_allowed: `false`" in text
