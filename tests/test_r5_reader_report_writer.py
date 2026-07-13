import re
from pathlib import Path

import yaml

from src.report.r5_reader_report_writer import build_traceability_appendix, validate_citations


ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10_reader_pack.yaml"


def load_pack():
    return yaml.safe_load(PACK_PATH.read_text(encoding="utf-8"))


def test_appendix_display_references_are_unique():
    appendix = build_traceability_appendix(load_pack())
    refs = [x["display_reference_id"] for x in appendix["records"]]
    assert refs == [f"E{i}" for i in range(1, 19)]
    assert len(refs) == len(set(refs))


def test_citation_resolution_detects_unknown_reference():
    appendix = build_traceability_appendix(load_pack())
    assert validate_citations("事实。[E1]", appendix) == []
    assert "E99" in validate_citations("事实。[E99]", appendix)


def test_appendix_keeps_audit_metadata_outside_report():
    appendix = build_traceability_appendix(load_pack())
    assert all(x["raw_evidence_ids"] and x["source_path"] and x["method"] for x in appendix["records"])
    assert appendix["human_review_status"] == "pending"
    assert not appendix["sample_quality_report_allowed"] and not appendix["p2_allowed"]
