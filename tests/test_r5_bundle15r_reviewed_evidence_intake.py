from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml

from src.maintenance.reviewed_evidence_intake import (
    build_intake,
    build_proposed_workflow_state,
    canonical_sha256,
    write_intake_outputs,
)


WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
ANCHOR = "bundle12r/R5_bundle12r_operating_evidence_input.yaml"


def _trigger(index: int) -> dict:
    overlap = index >= 10
    return {
        "trigger_id": f"B14R-{index:02d}",
        "issue_id": "OVERLAP" if overlap else "DRIVER",
        "kind": "overlap_elimination" if overlap else "operating_driver",
        "owner_stage": "T2_mapping_backflow" if overlap else "T1_evidence_backflow",
        "metric_key": f"metric_{index:02d}",
        "business_scope": f"scope_{index:02d}",
        "severity": "high",
        "period_policy": "same_period_as_anchor",
        "allowed_source_classes": [
            "issuer_periodic_report",
            "issuer_announcement",
            "issuer_ir_record",
        ],
        "required_fields": (
            [
                "base_scope",
                "cross_cutting_scope",
                "deduction_value",
                "unit",
                "period",
                "allocation_rule",
                "source_evidence_id",
                "locator",
            ]
            if overlap
            else [
                "metric_value",
                "unit",
                "period",
                "business_scope",
                "source_evidence_id",
                "locator",
            ]
        ),
        "status": "unresolved",
    }


def _registry() -> dict:
    return {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "base_commit": "a" * 40,
        "source_bundle13r_generation_id": "backflow_gen_r5_bundle13r_test",
        "period_anchor_ref": ANCHOR,
        "triggers": [_trigger(index) for index in range(1, 12)],
    }


def _payload(index: int, value: float | None = None) -> dict:
    if index >= 10:
        return {
            "base_scope": "base",
            "cross_cutting_scope": "cross",
            "deduction_value": value if value is not None else float(index),
            "unit": "CNY",
            "period": "2025A",
            "allocation_rule": "reviewed_rule",
        }
    return {
        "metric_value": value if value is not None else float(index),
        "unit": "unit",
        "period": "2025A",
        "business_scope": f"scope_{index:02d}",
    }


def _record(
    index: int,
    *,
    evidence_id: str | None = None,
    value: float | None = None,
    **overrides,
) -> dict:
    record = {
        "evidence_id": evidence_id or f"EV-{index:02d}",
        "source_class": "issuer_periodic_report",
        "official_issuer_source": True,
        "review_status": "reviewed",
        "document_date": "2026-08-20",
        "period_compatible": True,
        "period_anchor_ref": ANCHOR,
        "source_hash": f"{index:064x}",
        "locator": f"p.{index}",
        "metrics": [
            {
                "metric_key": f"metric_{index:02d}",
                "payload": _payload(index, value=value),
            }
        ],
    }
    record.update(overrides)
    return record


def _input(records: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "as_of": "2026-08-20",
        "period_anchor_ref": ANCHOR,
        "records": records,
    }


def test_empty_input_stays_waiting_and_keeps_downstream_closed() -> None:
    result = build_intake(_registry(), _input([]))
    summary = result["summary"]
    assert summary["eligible_candidate_count"] == 0
    assert summary["decision"] == (
        "waiting_for_reviewed_same-period_official_operating_evidence"
    )
    assert summary["bundle12r_rerun_allowed"] is False
    assert summary["reader_regeneration_allowed"] is False
    assert summary["p2_allowed"] is False


def test_unreviewed_nonofficial_and_wrong_anchor_records_are_rejected() -> None:
    records = [
        _record(1, review_status="pending"),
        _record(2, official_issuer_source=False),
        _record(3, period_compatible=False),
        _record(4, period_anchor_ref="wrong"),
    ]
    result = build_intake(_registry(), _input(records))
    reasons = {row["reason"] for row in result["rejections"]}
    assert "review_status_not_eligible" in reasons
    assert "not_official_issuer_source" in reasons
    assert "period_not_compatible" in reasons
    assert "period_anchor_mismatch" in reasons
    assert result["summary"]["eligible_candidate_count"] == 0


def test_partial_reviewed_input_builds_only_matching_candidate() -> None:
    result = build_intake(_registry(), _input([_record(1)]))
    assert result["summary"]["eligible_candidate_count"] == 1
    assert result["summary"]["represented_trigger_count"] == 1
    assert result["summary"]["next_action"] == (
        "run_existing_bundle14r_trigger_evaluator_for_selective_backflow"
    )
    candidate = result["candidate_pack"]["candidates"][0]
    assert candidate["metric_keys"] == ["metric_01"]
    assert candidate["source_evidence_id"] == "EV-01"


def test_equal_value_duplicates_are_deterministically_suppressed() -> None:
    records = [
        _record(1, evidence_id="EV-B"),
        _record(1, evidence_id="EV-A", source_hash="f" * 64, locator="p.9"),
    ]
    result = build_intake(_registry(), _input(records))
    assert result["summary"]["eligible_candidate_count"] == 1
    assert result["summary"]["duplicate_suppressed_count"] == 1
    assert result["candidate_pack"]["candidates"][0]["evidence_id"] == "EV-A"
    assert any(
        row["reason"] == "duplicate_same_value_suppressed"
        for row in result["rejections"]
    )


def test_conflicting_reviewed_values_fail_closed() -> None:
    records = [
        _record(1, evidence_id="EV-A", value=1.0),
        _record(1, evidence_id="EV-B", value=2.0, source_hash="e" * 64, locator="p.2"),
    ]
    result = build_intake(_registry(), _input(records))
    assert result["summary"]["eligible_candidate_count"] == 0
    assert result["summary"]["conflict_group_count"] == 1
    assert result["conflict_ledger"]["conflicts"][0]["metric_key"] == "metric_01"
    assert all(
        row["reason"] == "conflicting_reviewed_values"
        for row in result["rejections"]
    )


def test_all_eleven_metrics_only_prepare_bundle14r_evaluation() -> None:
    result = build_intake(
        _registry(),
        _input([_record(index) for index in range(1, 12)]),
    )
    summary = result["summary"]
    assert summary["eligible_candidate_count"] == 11
    assert summary["represented_trigger_count"] == 11
    assert summary["decision"] == (
        "all_trigger_candidates_ready_for_bundle14r_evaluation"
    )
    assert summary["bundle12r_rerun_allowed"] is False
    assert summary["valuation_refresh_allowed"] is False
    assert summary["model_regeneration_allowed"] is False
    assert summary["reader_regeneration_allowed"] is False
    assert summary["sample_quality_allowed"] is False
    assert summary["p2_allowed"] is False


def test_build_is_deterministic_under_record_order_changes() -> None:
    records = [_record(index) for index in range(1, 5)]
    first = build_intake(_registry(), _input(records))
    second = build_intake(_registry(), _input(list(reversed(records))))
    assert canonical_sha256(first["candidate_pack"]) == canonical_sha256(
        second["candidate_pack"]
    )
    assert canonical_sha256(first["summary"]) == canonical_sha256(second["summary"])


def test_file_outputs_and_proposed_state_never_open_downstream(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.yaml"
    input_path = tmp_path / "input.yaml"
    state_path = tmp_path / "workflow_state.yaml"
    yaml.safe_dump(_registry(), registry_path.open("w", encoding="utf-8"), allow_unicode=True)
    yaml.safe_dump(_input([_record(1)]), input_path.open("w", encoding="utf-8"), allow_unicode=True)
    yaml.safe_dump(
        {"workflow_id": WORKFLOW_ID, "status": "in_progress"},
        state_path.open("w", encoding="utf-8"),
        allow_unicode=True,
    )
    result = write_intake_outputs(
        registry_path=registry_path,
        reviewed_input_path=input_path,
        output_dir=tmp_path / "generated",
        workflow_state_path=state_path,
    )
    for path in result["paths"].values():
        assert path.exists()
    proposed = yaml.safe_load(
        result["paths"]["workflow_state_copy"].read_text(encoding="utf-8")
    )
    section = proposed["bundle15r_reviewed_evidence_intake"]
    assert section["canonical_state_overwritten"] is False
    assert section["bundle12r_rerun_allowed"] is False
    assert section["reader_regeneration_allowed"] is False
    assert section["p2_allowed"] is False
