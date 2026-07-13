from src.quality.r5_bundle10r_reader_gate import evaluate_reader_candidate
from src.report.r5_traceability_v4 import build_traceability_appendix
from tests.r5_bundle10r_test_fixtures import binding, payload, quality_contract, reader_contract


def test_nine_sentence_style_thin_report_fails():
    p = payload()
    report = "# 极薄报告\n\n" + "\n\n".join(f"## {i}、章节\n本节只有一句结论。[E1]" for i in range(1, 10))
    appendix = build_traceability_appendix(p, report)
    result = evaluate_reader_candidate(p, report, appendix, binding(), reader_contract(), quality_contract(min_han=1200))
    assert result["decision"] == "rejected"
    assert any(x["code"] == "reader_report_below_density_floor" for x in result["candidate_blockers"])
