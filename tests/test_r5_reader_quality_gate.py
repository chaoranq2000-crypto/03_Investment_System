from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from scripts.run_r5_reader_quality_gate import evaluate


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def load(name):
    return yaml.safe_load((RUN / name).read_text(encoding="utf-8"))


@pytest.fixture
def supported():
    return (
        (RUN / "R5_stock_research_report_reader_v2.md").read_text(encoding="utf-8"),
        load("R5_stock_research_report_traceability_v2.yaml"),
        load("R5_bundle6_forecast_bridge.yaml"),
        load("R5_bundle6_valuation_reasoning_pack.yaml"),
        yaml.safe_load((ROOT / "config/r5_reader_quality_rubric.yaml").read_text(encoding="utf-8")),
    )


def test_real_candidate_passes_with_pending_human_review(supported):
    result = evaluate(*supported)
    assert result["decision"] == "candidate_ready_for_human_review"
    assert result["score"] >= 82 and result["critical_blocker_count"] == 0
    assert result["human_review_status"] == "pending"
    assert not result["sample_quality_report_allowed"] and not result["p2_allowed"]


def test_frozen_bundle5_draft_fails_reader_surface_gate(supported):
    _, appendix, bridge, valuation, rubric = supported
    old = (RUN / "R5_stock_research_note_reviewed_input_draft.md").read_text(encoding="utf-8")
    result = evaluate(old, appendix, bridge, valuation, rubric)
    assert result["decision"] == "rejected"
    assert result["critical_blocker_count"] > 0


def test_source_gapped_but_honest_report_fails_candidate_coverage(supported):
    report, appendix, bridge, valuation, rubric = supported
    start = report.index("## 五、行业结构与竞争")
    end = report.index("## 六、预测与情景")
    source_gapped = report[:start] + report[end:]
    result = evaluate(source_gapped, appendix, bridge, valuation, rubric)
    assert result["decision"] == "rejected"
    assert "missing_mandatory_section" in {x["code"] for x in result["critical_blockers"]}


MUTATIONS = [
    ("unknown_reference", lambda r, a, b, v: (r + "\n未经支持。[E99]", a, b, v), "unresolved_traceability_reference"),
    ("raw_evidence_id", lambda r, a, b, v: (r + "\nev_bad_123", a, b, v), "raw_internal_evidence_id_in_main_report"),
    ("raw_claim_id", lambda r, a, b, v: (r + "\nclaim_id_bad", a, b, v), "raw_internal_evidence_id_in_main_report"),
    ("raw_path", lambda r, a, b, v: (r + "\nreports/workflow_runs/x/file.yaml", a, b, v), "raw_registry_or_workflow_path_in_main_report"),
    ("readiness_label", lambda r, a, b, v: (r + "\nreadiness: ready", a, b, v), "readiness_or_visible_gap_token_in_main_report"),
    ("todo_token", lambda r, a, b, v: (r + "\nTODO_SOURCE_REQUIRED", a, b, v), "raw_todo_missing_or_unreviewed_token_in_main_report"),
    ("duplicate_section", lambda r, a, b, v: (r + "\n## 一、核心研究观点", a, b, v), "duplicate_machine_readiness_sections"),
    ("raw_currency", lambda r, a, b, v: (r + "\n收入123456789.123元", a, b, v), "unrounded_raw_cny_dump"),
    ("missing_bridge", lambda r, a, b, v: (r, a, {**b, "base_case_bridge": []}, v), "forecast_without_driver_bridge"),
    ("forecast_mismatch", lambda r, a, b, v: (r, a, {**b, "base_case_bridge": [{**b["base_case_bridge"][0], "reconciliation_difference": 0.1}]}, v), "forecast_arithmetic_mismatch"),
    ("valuation_date", lambda r, a, b, v: (r, a, b, {**v, "as_of_date": None}), "valuation_without_date_or_denominator_control"),
    ("direct_advice", lambda r, a, b, v: (r + "\n建议仓位五成", a, b, v), "direct_buy_sell_hold_or_position_instruction"),
    ("sample_fact", lambda r, a, b, v: (r + "\nSAMPLE_FACT", a, b, v), "sample_fact_used_as_evidence"),
    ("fake_human_review", lambda r, a, b, v: (r + "\nhuman_review_status: accepted", a, b, v), "fabricated_human_review_acceptance"),
    ("duplicate_appendix_ref", lambda r, a, b, v: (r, {**a, "records": a["records"] + [deepcopy(a["records"][0])]}, b, v), "unresolved_traceability_reference"),
]


@pytest.mark.parametrize("name,mutate,expected", MUTATIONS, ids=[x[0] for x in MUTATIONS])
def test_negative_cases_fail_closed(supported, name, mutate, expected):
    report, appendix, bridge, valuation, rubric = supported
    result = evaluate(*mutate(report, appendix, bridge, valuation), rubric)
    assert result["decision"] == "rejected", name
    assert expected in {x["code"] for x in result["critical_blockers"]}
