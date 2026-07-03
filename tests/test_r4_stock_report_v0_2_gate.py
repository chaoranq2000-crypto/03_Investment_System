from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK_RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def test_r4_v0_2_references_required_reviews() -> None:
    report = (STOCK_RUN / "R4_stock_deep_dive_v0_2.md").read_text(encoding="utf-8")

    assert "Official Reconciliation Review" in report
    assert "Liquid-cooling Exposure Evidence Review" in report
    assert "Segment Exposure And Backflow" in report
    assert "MISSING_DISCLOSURE" in report
    assert "R4_source_gap_report_v0_2.md" in report


def test_r4_v0_2_gate_status_is_allowed_enum() -> None:
    gate = (STOCK_RUN / "R4_quality_gate_report_v0_2.md").read_text(encoding="utf-8")
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


def test_r4_v0_2_does_not_write_liquid_cooling_revenue_pct() -> None:
    report = (STOCK_RUN / "R4_stock_deep_dive_v0_2.md").read_text(encoding="utf-8")

    assert "liquid-cooling revenue_pct | MISSING_DISCLOSURE" in report
    assert "liquid-cooling profit_pct | MISSING_DISCLOSURE" in report
    assert "revenue_pct | 17" not in report


def test_r4_v0_2_no_advice_boundary() -> None:
    forbidden = ["买入", "卖出", "持有", "仓位", "止盈", "止损", "交易建议", "强烈推荐", "目标价"]
    for name in [
        "R4_stock_deep_dive_v0_2.md",
        "R4_quality_gate_report_v0_2.md",
        "R4_source_gap_report_v0_2.md",
        "R4_open_questions_v0_2.md",
    ]:
        text = (STOCK_RUN / name).read_text(encoding="utf-8")
        assert not [term for term in forbidden if term in text]


def test_p2_readiness_check_does_not_start_p2() -> None:
    text = (ROOT / "reports/p1_6/P2_READINESS_CHECK_AFTER_R4_V0_2.md").read_text(encoding="utf-8")

    assert "decision: ready_for_limited_p2_pilot" in text
    assert "does not start P2" in text
    assert "does not create comparison reports" in text
