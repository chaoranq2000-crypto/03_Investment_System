from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKFLOW_SOURCE = ROOT / "src/qa/r4_disclosure_backflow_review.py"
HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def _historical_file(historical_blob_file, name: str) -> Path:
    return historical_blob_file(f"{HISTORICAL_RUN}/{name}", f"r4_v0_2/{name}")


def test_stage_summaries_are_scoped_to_the_explicit_workflow_run() -> None:
    source = BACKFLOW_SOURCE.read_text(encoding="utf-8")
    assert 'SUMMARY_ROOT = STOCK_RUN / "stage_summaries"' in source
    assert "reports/p1_6/" not in source


def test_r4_v0_2_references_required_reviews(historical_blob_file) -> None:
    report = _historical_file(
        historical_blob_file, "R4_stock_deep_dive_v0_2.md"
    ).read_text(encoding="utf-8")

    assert "Official Reconciliation Review" in report
    assert "Liquid-cooling Exposure Evidence Review" in report
    assert "Segment Exposure And Backflow" in report
    assert "MISSING_DISCLOSURE" in report
    assert "R4_source_gap_report_v0_2.md" in report


def test_r4_v0_2_gate_status_is_allowed_enum(historical_blob_file) -> None:
    gate = _historical_file(
        historical_blob_file, "R4_quality_gate_report_v0_2.md"
    ).read_text(encoding="utf-8")
    allowed = {
        "publishable_ready",
        "publishable_ready_with_disclosure_todos",
        "bridge_only",
        "blocked",
    }
    status_line = next(line for line in gate.splitlines() if line.startswith("r4_publishable_gate_status:"))
    status = status_line.split(":", 1)[1].strip()

    assert status in allowed
    assert status == "publishable_ready_with_disclosure_todos"
    assert "high_issues: 0" in gate
    assert "owner" in gate
    assert "next_action" in gate
    assert "blocking_decision" in gate


def test_r4_v0_2_does_not_write_liquid_cooling_revenue_pct(historical_blob_file) -> None:
    report = _historical_file(
        historical_blob_file, "R4_stock_deep_dive_v0_2.md"
    ).read_text(encoding="utf-8")

    assert "liquid-cooling revenue_pct | MISSING_DISCLOSURE" in report
    assert "liquid-cooling profit_pct | MISSING_DISCLOSURE" in report
    assert "revenue_pct | 17" not in report


def test_r4_v0_2_no_advice_boundary(historical_blob_file) -> None:
    forbidden = ["买入", "卖出", "持有", "仓位", "止盈", "止损", "交易建议", "强烈推荐", "目标价"]
    for name in [
        "R4_stock_deep_dive_v0_2.md",
        "R4_quality_gate_report_v0_2.md",
        "R4_source_gap_report_v0_2.md",
        "R4_open_questions_v0_2.md",
    ]:
        text = _historical_file(historical_blob_file, name).read_text(encoding="utf-8")
        assert not [term for term in forbidden if term in text]


def test_p2_readiness_check_does_not_start_p2(historical_blob_bytes) -> None:
    text = historical_blob_bytes(
        "reports/p1_6/P2_READINESS_CHECK_AFTER_R4_V0_2.md"
    ).decode("utf-8")

    assert "decision: ready_for_limited_p2_pilot" in text
    assert "does not start P2" in text
    assert "does not create comparison reports" in text
