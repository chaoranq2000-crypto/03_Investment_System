from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK_RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def test_data_layer_bridge_draft_exposes_metrics_and_todos() -> None:
    draft = STOCK_RUN / "R4_stock_report_data_layer_bridge_draft.md"
    text = draft.read_text(encoding="utf-8")

    assert "## 2. Financial Quality Table" in text
    assert "## 3. Valuation Context" in text
    assert "## 4. Technical / Market State Observation" in text
    assert "## 5. Peer Valuation Table" in text
    assert "## 6. Source Gaps Carried Forward" in text
    assert "ev_structured_financial_data_002837_20260701_1b506c" in text
    assert "ev_structured_market_data_002837_20260701_daa823" in text
    assert "ev_structured_market_data_002837_20260701_eaca20" in text
    assert "TODO_DISCLOSURE_RECONCILIATION" in text
    assert "TODO_MARKET_DATA" in text
    assert "MISSING_DISCLOSURE" in text


def test_data_layer_bridge_outputs_keep_boundaries() -> None:
    draft = (STOCK_RUN / "R4_stock_report_data_layer_bridge_draft.md").read_text(encoding="utf-8")
    readout = (STOCK_RUN / "data_layer_bridge_readout.md").read_text(encoding="utf-8")
    issue_rows = list(
        csv.DictReader((STOCK_RUN / "data_layer_bridge_issue_list.csv").open("r", encoding="utf-8", newline=""))
    )

    assert issue_rows
    assert len((STOCK_RUN / "data_layer_bridge_issue_list.csv").read_text(encoding="utf-8").splitlines()) >= 4
    assert {row["issue_id"] for row in issue_rows} == {"DLBR-001", "DLBR-002", "DLBR-003"}
    assert "Data Layer Pack Gate" in readout
    assert "structured snapshots remain metric-only | pass" in readout
    assert "No stock report was regenerated." in readout

    for forbidden in ["买入", "卖出", "持有", "目标价"]:
        assert forbidden not in draft
        assert forbidden not in readout


def test_integrated_data_layer_debug_outputs_keep_todos_visible() -> None:
    integrated = (STOCK_RUN / "integrated_data_layer_readout.md").read_text(encoding="utf-8")
    gate = (STOCK_RUN / "quality_gate_report_after_data_layer_bridge.md").read_text(encoding="utf-8")
    gaps = (STOCK_RUN / "remaining_source_gaps_after_data_layer_bridge.md").read_text(encoding="utf-8")

    assert "status: accepted_with_todos" in integrated
    assert integrated.count("## ") >= 3
    assert "Data Layer Pack Gate | accepted_with_todos" in integrated
    assert "DLBR-001" in integrated
    assert "final_status: accepted_with_todos" in gate
    assert "blocking_issues: 0" in gate
    assert "accepted_todos: 3" in gate
    assert "DISCLOSURE-SEGMENT-001" in gaps
    assert "MISSING_DISCLOSURE" in gaps
    assert "TODO_SOURCE_REQUIRED" in gaps

    for forbidden in ["买入", "卖出", "持有", "目标价"]:
        assert forbidden not in integrated
        assert forbidden not in gate
        assert forbidden not in gaps
