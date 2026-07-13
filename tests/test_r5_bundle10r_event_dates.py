from src.quality.r5_bundle10r_reader_gate import evaluate_reader_candidate
from src.report.r5_reader_writer_v4 import render_reader_report
from src.report.r5_traceability_v4 import build_traceability_appendix
from tests.r5_bundle10r_test_fixtures import binding, payload, quality_contract, reader_contract


def test_past_event_cannot_be_future_catalyst():
    p = payload()
    market = next(x for x in p["sections"] if x["section_id"] == "market_technical_sentiment_and_events")
    market["events"][0]["date"] = "2026-06-30"
    report = render_reader_report(p)
    appendix = build_traceability_appendix(p, report)
    result = evaluate_reader_candidate(p, report, appendix, binding(), reader_contract(), quality_contract())
    assert any(x["code"] == "past_event_presented_as_future" for x in result["candidate_blockers"])
