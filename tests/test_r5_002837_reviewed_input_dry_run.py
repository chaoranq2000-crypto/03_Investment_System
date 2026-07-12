from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = REPO_ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
RESULT_PATH = RUN_DIR / "R5_reviewed_input_dry_run_result.yaml"


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


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


def test_current_002837_stubs_do_not_exceed_source_gapped_level():
    market = load_yaml(RUN_DIR / "R5_market_snapshot_stub.yaml")
    peer = load_yaml(RUN_DIR / "R5_peer_snapshot_stub.yaml")
    assumptions = load_yaml(REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_forecast_assumption_registry.example.yaml")
    valuation = load_yaml(REPO_ROOT / ".agents/skills/stock-deep-dive/assets/r5_valuation_input_registry.example.yaml")

    assert has_reviewed_market(market) is False
    assert has_reviewed_peer(peer) is False
    assert has_reviewed_forecast_assumptions(assumptions) is False
    assert has_reviewed_valuation_inputs(valuation) is False


def test_dry_run_result_reflects_promoted_physical_registries():
    result = load_yaml(RESULT_PATH)

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
