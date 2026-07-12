import re

from src.report.r5_reader_report_writer import build_traceability_appendix, validate_citations


def test_appendix_display_references_are_unique():
    appendix = build_traceability_appendix()
    refs = [x["display_reference_id"] for x in appendix["records"]]
    assert refs == [f"E{i}" for i in range(1, 10)]
    assert len(refs) == len(set(refs))


def test_citation_resolution_detects_unknown_reference():
    appendix = build_traceability_appendix()
    assert validate_citations("事实。[E1]", appendix) == []
    assert "E10" in validate_citations("事实。[E10]", appendix)


def test_appendix_keeps_audit_metadata_outside_report():
    appendix = build_traceability_appendix()
    assert all(x["raw_evidence_ids"] and x["source_path"] and x["method"] for x in appendix["records"])
    assert appendix["human_review_status"] == "pending"
    assert not appendix["sample_quality_report_allowed"] and not appendix["p2_allowed"]
