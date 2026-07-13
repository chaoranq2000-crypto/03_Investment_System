from copy import deepcopy

from src.quality.r5_bundle10r_reader_gate import evaluate_reader_candidate
from src.report.r5_reader_writer_v4 import render_reader_report
from src.report.r5_traceability_v4 import build_traceability_appendix
from tests.r5_bundle10r_test_fixtures import binding, payload, quality_contract, reader_contract


def run(p):
    report = render_reader_report(p)
    appendix = build_traceability_appendix(p, report)
    return evaluate_reader_candidate(p, report, appendix, binding(), reader_contract(), quality_contract())


def test_positive_candidate_passes():
    result = run(payload())
    assert result["decision"] == "candidate_ready_for_human_review"
    assert result["core_section_blockers"] == []


def test_forecast_core_failure_cannot_be_offset():
    p = payload()
    section = next(x for x in p["sections"] if x["section_id"] == "forecast_and_scenarios")
    section["causal_mechanism"] = []
    result = run(p)
    assert result["decision"] == "rejected"
    assert any(x["message"] == "forecast_and_scenarios" for x in result["core_section_blockers"])
    assert result["score"] > 70


def test_stale_payload_generation_blocks():
    p = payload()
    p["input_model_generation_id"] = "model_gen_stale"
    result = run(p)
    assert result["decision"] == "rejected"
    assert any(x["code"] == "stale_or_wrong_model_generation" for x in result["truthfulness_blockers"])
