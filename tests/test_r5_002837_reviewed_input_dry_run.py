from __future__ import annotations

from typing import Any

import yaml
import pytest

DRY_RUN_SOURCE = (
    "reports/workflow_runs/wf_20260703_stock_first_002837_invic/"
    "R5_reviewed_input_dry_run_result.yaml"
)


def has_reviewed_market(snapshot: dict[str, Any]) -> bool:
    return (
        snapshot.get("status") in {"reviewed", "ready"}
        and bool(snapshot.get("as_of_date"))
        and bool(snapshot.get("source_evidence_ids"))
    )


def has_reviewed_peer(snapshot: dict[str, Any]) -> bool:
    return (
        snapshot.get("status") in {"reviewed", "ready"}
        and len(snapshot.get("peer_set") or []) >= 3
        and bool(snapshot.get("peer_metrics"))
    )


def has_reviewed_forecast_assumptions(registry: dict[str, Any]) -> bool:
    assumptions = registry.get("assumptions") or []
    return any(
        isinstance(row, dict)
        and row.get("review_status") == "reviewed"
        and (row.get("supporting_evidence_ids") or row.get("supporting_metric_ids"))
        for row in assumptions
    )


def has_reviewed_valuation_inputs(registry: dict[str, Any]) -> bool:
    return (
        (registry.get("market_snapshot") or {}).get("review_status") in {"reviewed", "ready"}
        and (registry.get("peer_snapshot") or {}).get("review_status") in {"reviewed", "ready"}
        and (registry.get("forecast_model") or {}).get("review_status") in {"reviewed", "ready"}
    )


def test_unreviewed_fixture_inputs_do_not_exceed_source_gapped_level(tmp_path):
    fixture_path = tmp_path / "unreviewed_inputs.yaml"
    fixture_path.write_text(
        yaml.safe_dump(
            {
                "market": {
                    "status": "TODO",
                    "as_of_date": None,
                    "source_evidence_ids": [],
                },
                "peer": {
                    "status": "TODO",
                    "peer_set": [],
                    "peer_metrics": [],
                },
                "assumptions": {
                    "assumptions": [
                        {
                            "review_status": "TODO",
                            "supporting_evidence_ids": [],
                            "supporting_metric_ids": [],
                        }
                    ]
                },
                "valuation": {
                    "market_snapshot": {"review_status": "TODO"},
                    "peer_snapshot": {"review_status": "TODO"},
                    "forecast_model": {"review_status": "TODO"},
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    inputs = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))

    assert has_reviewed_market(inputs["market"]) is False
    assert has_reviewed_peer(inputs["peer"]) is False
    assert has_reviewed_forecast_assumptions(inputs["assumptions"]) is False
    assert has_reviewed_valuation_inputs(inputs["valuation"]) is False


@pytest.mark.legacy_compatibility
def test_dry_run_result_reflects_promoted_physical_registries(
    historical_blob_bytes,
):
    result = yaml.safe_load(historical_blob_bytes(DRY_RUN_SOURCE).decode("utf-8"))

    assert result["derivation_source"] == "validated_physical_registries"
    assert result["allowed_report_level"] == "reviewed_input_research_draft"
    assert result["reviewed_market_inputs_available"] is True
    assert result["reviewed_peer_inputs_available"] is True
    assert result["reviewed_forecast_assumptions_available"] is True
    assert result["reviewed_business_disclosure_available"] is True
    assert result["reviewed_valuation_inputs_available"] is True
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False
    assert result["remaining_todos"] == []
    resolved = {row["token"] for row in result["todo_trace"] if row["status"] == "resolved"}
    assert {"TODO_MARKET_DATA", "TODO_PEER_DATA", "TODO_MODEL_INPUT"} <= resolved
