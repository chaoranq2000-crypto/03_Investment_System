from src.quality.r5_bundle10r_reader_gate import evaluate_reader_candidate
from src.report.r5_reader_writer_v4 import render_reader_report
from src.report.r5_traceability_v4 import build_traceability_appendix
from tests.r5_bundle10r_test_fixtures import binding, payload, quality_contract, reader_contract


def run(p, mutate_report=None):
    report = render_reader_report(p)
    if mutate_report:
        report = mutate_report(report)
    appendix = build_traceability_appendix(p, report)
    return evaluate_reader_candidate(p, report, appendix, binding(), reader_contract(), quality_contract())


def test_liquid_cooling_fact_inflation_fails():
    p = payload()
    p["claims"][1]["claim_type"] = "issuer_fact"
    result = run(p)
    assert any(x["code"] == "liquid_cooling_claim_inflated_to_fact" for x in result["truthfulness_blockers"])


def test_low_confidence_peer_ranking_fails():
    p = payload()
    p["claims"][2]["ranking_performed"] = True
    result = run(p)
    assert any(x["code"] == "low_confidence_peer_ranking_performed" for x in result["truthfulness_blockers"])


def test_consensus_relabelled_as_fact_fails():
    p = payload()
    p["claims"][0]["claim_type"] = "fact"
    result = run(p)
    assert any(x["code"] == "consensus_claim_type_inflated" for x in result["truthfulness_blockers"])


def test_action_language_fails():
    result = run(payload(), lambda report: report + "\n建议买入并加仓，目标价100元。\n")
    assert any(x["code"] == "direct_action_language_in_main_report" for x in result["truthfulness_blockers"])
