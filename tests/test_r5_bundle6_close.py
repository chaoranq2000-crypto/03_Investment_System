from pathlib import Path

import re
import yaml


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def test_all_declared_bundle6_artifacts_exist():
    expected = yaml.safe_load((ROOT / "codex_tasks/r5_after_bundle5/R5_BUNDLE6_EXPECTED_ARTIFACTS.yaml").read_text(encoding="utf-8"))
    missing = [x["path"] for x in expected["required_artifacts"] if not (ROOT / x["path"]).exists()]
    assert missing == []


def test_reader_report_citations_resolve_once_and_sources_exist():
    report = (RUN / "R5_stock_research_report_reader_v2.md").read_text(encoding="utf-8")
    appendix = yaml.safe_load((RUN / "R5_stock_research_report_traceability_v2.yaml").read_text(encoding="utf-8"))
    used = set(re.findall(r"\[(E[1-9][0-9]*)\]", report))
    refs = [x["display_reference_id"] for x in appendix["records"]]
    assert used == set(refs)
    assert all(refs.count(ref) == 1 for ref in used)
    assert all((ROOT / x["source_path"]).exists() for x in appendix["records"])


def test_close_state_keeps_human_review_and_promotion_boundaries():
    close = (ROOT / "reports/p1_6/R5_BUNDLE_6_READER_REPORT_QUALITY_REMEDIATION_CLOSE_READOUT.md").read_text(encoding="utf-8")
    score = yaml.safe_load((RUN / "R5_stock_research_report_reader_v2_quality_scorecard.yaml").read_text(encoding="utf-8"))
    review = yaml.safe_load((RUN / "R5_stock_research_report_reader_v2_human_review.yaml").read_text(encoding="utf-8"))
    assert "R5_002837_READER_FACING_REPORT_V2_CANDIDATE_READY" in close
    assert score["decision"] == "candidate_ready_for_human_review" and score["critical_blocker_count"] == 0
    assert review["status"] == "pending" and review["reviewer"] is None
    assert not review["sample_quality_report_allowed"] and not review["p2_allowed"]
