from pathlib import Path

import re
import yaml


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def historical_yaml(historical_blob_bytes, name: str):
    return yaml.safe_load(historical_blob_bytes(f"{HISTORICAL_RUN}/{name}").decode("utf-8"))


def artifact_exists(path: str, historical_blob_bytes) -> bool:
    if path.startswith(f"{HISTORICAL_RUN}/"):
        return bool(historical_blob_bytes(path))
    return (ROOT / path).exists()


def test_all_declared_bundle6_artifacts_exist(historical_blob_bytes):
    expected = yaml.safe_load((ROOT / "codex_tasks/r5_after_bundle5/R5_BUNDLE6_EXPECTED_ARTIFACTS.yaml").read_text(encoding="utf-8"))
    missing = [
        x["path"]
        for x in expected["required_artifacts"]
        if not artifact_exists(x["path"], historical_blob_bytes)
    ]
    assert missing == []


def test_reader_report_citations_resolve_once_and_sources_exist(historical_blob_bytes):
    report = historical_blob_bytes(
        f"{HISTORICAL_RUN}/R5_stock_research_report_reader_v2.md"
    ).decode("utf-8")
    appendix = historical_yaml(
        historical_blob_bytes, "R5_stock_research_report_traceability_v2.yaml"
    )
    used = set(re.findall(r"\[(E[1-9][0-9]*)\]", report))
    refs = [x["display_reference_id"] for x in appendix["records"]]
    assert used == set(refs)
    assert all(refs.count(ref) == 1 for ref in used)
    assert all(
        artifact_exists(x["source_path"], historical_blob_bytes)
        for x in appendix["records"]
    )


def test_close_state_keeps_human_review_and_promotion_boundaries(historical_blob_bytes):
    close = (ROOT / "reports/p1_6/R5_BUNDLE_6_READER_REPORT_QUALITY_REMEDIATION_CLOSE_READOUT.md").read_text(encoding="utf-8")
    score = historical_yaml(
        historical_blob_bytes, "R5_stock_research_report_reader_v2_quality_scorecard.yaml"
    )
    review = historical_yaml(
        historical_blob_bytes, "R5_stock_research_report_reader_v2_human_review.yaml"
    )
    assert "R5_002837_READER_FACING_REPORT_V2_CANDIDATE_READY" in close
    assert score["schema_version"] == "v0.2"
    assert score["decision"] == "rejected" and score["quality_band"] == "research_draft"
    assert score["truthfulness_status"] == "pass" and score["critical_blocker_count"] == 12
    assert score["human_review_status"] == "not_ready"
    assert review["status"] == "pending" and review["reviewer"] is None
    assert not review["sample_quality_report_allowed"] and not review["p2_allowed"]
