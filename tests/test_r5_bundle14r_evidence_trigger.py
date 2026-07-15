from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml

from src.maintenance.evidence_trigger_backflow import (
    build_selective_backflow_plan,
    canonical_sha256,
    evaluate_from_files,
    evaluate_triggers,
    update_workflow_state_copy,
    validate_registry,
)


BASE_COMMIT = "32d2c3617c2c95d389682b5de634be9768187f46"
ANCHOR = "bundle12r/R5_bundle12r_operating_evidence_input.yaml"


def _trigger(index: int, kind: str = "operating_driver") -> dict:
    is_driver = kind == "operating_driver"
    return {
        "trigger_id": f"TR-{index:02d}",
        "issue_id": "R5B13R-DRIVER-001" if is_driver else "R5B13R-OVERLAP-001",
        "kind": kind,
        "owner_stage": "T1_evidence_backflow" if is_driver else "T2_mapping_backflow",
        "metric_key": f"metric_{index:02d}",
        "business_scope": "scope",
        "severity": "high",
        "period_policy": "same_period_as_anchor",
        "allowed_source_classes": ["issuer_periodic_report", "issuer_ir_record"],
        "required_fields": ["metric_value", "unit", "period", "business_scope"],
        "status": "unresolved",
    }


def _registry() -> dict:
    return {
        "schema_version": 1,
        "workflow_id": "wf_20260703_stock_first_002837_invic",
        "base_commit": BASE_COMMIT,
        "source_bundle13r_generation_id": "backflow_gen_r5_bundle13r_fb8cefccfaa93293",
        "period_anchor_ref": ANCHOR,
        "triggers": [_trigger(i) for i in range(1, 10)]
        + [_trigger(10, "overlap_elimination"), _trigger(11, "overlap_elimination")],
    }


def _candidate(index: int, **overrides) -> dict:
    payload = {
        "evidence_id": f"EV-{index:02d}",
        "source_class": "issuer_periodic_report",
        "official_issuer_source": True,
        "review_status": "reviewed",
        "document_date": "2026-08-20",
        "period_compatible": True,
        "period_anchor_ref": ANCHOR,
        "metric_keys": [f"metric_{index:02d}"],
        "available_fields": ["metric_value", "unit", "period", "business_scope"],
        "source_hash": f"{'a' * 62}{index:02d}",
        "locator": f"p.{index}",
    }
    payload.update(overrides)
    return payload


def _pack(candidates: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "workflow_id": "wf_20260703_stock_first_002837_invic",
        "as_of": "2026-08-20",
        "candidates": candidates,
    }


def test_registry_has_nine_driver_and_two_overlap_contracts() -> None:
    registry = _registry()
    validate_registry(registry)
    drivers = [item for item in registry["triggers"] if item["kind"] == "operating_driver"]
    overlaps = [item for item in registry["triggers"] if item["kind"] == "overlap_elimination"]
    assert len(drivers) == 9
    assert len(overlaps) == 2


def test_empty_pack_keeps_all_eleven_unresolved_and_freezes_downstream() -> None:
    evaluation = evaluate_triggers(_registry(), _pack([]))
    assert evaluation["decision"] == "R5_BUNDLE14R_WAITING_FOR_OFFICIAL_EVIDENCE"
    assert evaluation["qualified_trigger_count"] == 0
    assert evaluation["unresolved_trigger_count"] == 11
    assert evaluation["selective_backflow_stages"] == []
    assert evaluation["bundle12r_rerun_allowed"] is False
    assert evaluation["valuation_refresh_allowed"] is False
    assert evaluation["reader_regeneration_allowed"] is False
    assert evaluation["p2_allowed"] is False


def test_unreviewed_or_nonofficial_candidate_does_not_qualify() -> None:
    candidates = [
        _candidate(1, review_status="pending"),
        _candidate(2, official_issuer_source=False),
        _candidate(3, source_class="broker_research"),
    ]
    evaluation = evaluate_triggers(_registry(), _pack(candidates))
    assert evaluation["qualified_trigger_count"] == 0


def test_wrong_period_anchor_does_not_qualify() -> None:
    evaluation = evaluate_triggers(
        _registry(),
        _pack([_candidate(1, period_compatible=False, period_anchor_ref="wrong")]),
    )
    result = next(item for item in evaluation["trigger_results"] if item["trigger_id"] == "TR-01")
    reasons = result["candidate_rejections"][0]["reasons"]
    assert "period_not_compatible" in reasons
    assert "period_anchor_mismatch" in reasons


def test_partial_driver_match_schedules_only_t1_and_no_bundle12r_rerun() -> None:
    evaluation = evaluate_triggers(_registry(), _pack([_candidate(1)]))
    plan = build_selective_backflow_plan(evaluation)
    assert evaluation["decision"] == "R5_BUNDLE14R_PARTIAL_EVIDENCE_TRIGGERED"
    assert evaluation["selective_backflow_stages"] == ["T1_evidence_backflow"]
    assert [task["task_id"] for task in plan["tasks"]] == ["B14R-SELECTIVE-T1"]
    assert plan["bundle12r_rerun_allowed"] is False


def test_partial_overlap_match_schedules_only_t2() -> None:
    evaluation = evaluate_triggers(_registry(), _pack([_candidate(10)]))
    plan = build_selective_backflow_plan(evaluation)
    assert evaluation["selective_backflow_stages"] == ["T2_mapping_backflow"]
    assert [task["task_id"] for task in plan["tasks"]] == ["B14R-SELECTIVE-T2"]


def test_all_eleven_reviewed_candidates_allow_only_bundle12r_requalification() -> None:
    evaluation = evaluate_triggers(_registry(), _pack([_candidate(i) for i in range(1, 12)]))
    plan = build_selective_backflow_plan(evaluation)
    assert evaluation["qualified_trigger_count"] == 11
    assert evaluation["unresolved_trigger_count"] == 0
    assert evaluation["bundle12r_rerun_allowed"] is True
    assert evaluation["valuation_refresh_allowed"] is False
    assert evaluation["model_regeneration_allowed"] is False
    assert evaluation["reader_regeneration_allowed"] is False
    assert evaluation["p2_allowed"] is False
    assert [task["task_id"] for task in plan["tasks"]] == [
        "B14R-SELECTIVE-T1",
        "B14R-SELECTIVE-T2",
        "B14R-RERUN-B12R",
    ]


def test_candidate_order_does_not_change_generation_id() -> None:
    first = evaluate_triggers(_registry(), _pack([_candidate(2), _candidate(1)]))
    second = evaluate_triggers(_registry(), _pack([_candidate(1), _candidate(2)]))
    assert first["generation_id"] == second["generation_id"]
    assert canonical_sha256(first) == canonical_sha256(second)


def test_workflow_state_copy_preserves_unrelated_state_and_keeps_p2_closed() -> None:
    evaluation = evaluate_triggers(_registry(), _pack([_candidate(1)]))
    plan = build_selective_backflow_plan(evaluation)
    original = {"workflow_id": "wf", "custom": {"preserve": True}, "p2_allowed": False}
    updated = update_workflow_state_copy(original, evaluation, plan)
    assert original == {"workflow_id": "wf", "custom": {"preserve": True}, "p2_allowed": False}
    assert updated["custom"] == {"preserve": True}
    assert updated["bundle14r_evidence_trigger_backflow"]["p2_allowed"] is False


def test_file_runner_emits_outputs_without_overwriting_input_state(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.yaml"
    candidates_path = tmp_path / "candidates.yaml"
    state_path = tmp_path / "workflow_state.yaml"
    out = tmp_path / "out"
    registry_path.write_text(yaml.safe_dump(_registry(), sort_keys=False), encoding="utf-8")
    candidates_path.write_text(yaml.safe_dump(_pack([]), sort_keys=False), encoding="utf-8")
    original_state = {"workflow_id": "wf", "sentinel": "unchanged"}
    state_path.write_text(yaml.safe_dump(original_state, sort_keys=False), encoding="utf-8")
    paths = evaluate_from_files(
        registry_path=registry_path,
        candidate_pack_path=candidates_path,
        output_dir=out,
        workflow_state_path=state_path,
    )
    assert set(paths) == {"evaluation", "plan", "workflow_state_copy"}
    assert yaml.safe_load(state_path.read_text(encoding="utf-8")) == original_state
    assert paths["workflow_state_copy"].exists()
