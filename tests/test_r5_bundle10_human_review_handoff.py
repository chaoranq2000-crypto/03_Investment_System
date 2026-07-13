from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
BUILD_SCRIPT = ROOT / "scripts/build_r5_bundle10_human_review_handoff.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_builder():
    spec = importlib.util.spec_from_file_location("build_r5_bundle10_human_review_handoff", BUILD_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bundle10_finalized_human_review_handoff_is_hash_bound() -> None:
    handoff = yaml.safe_load(
        (RUN / "R5_stock_research_report_reader_v3_human_review.yaml").read_text(encoding="utf-8")
    )
    assert handoff["reader_report_sha256"] == sha(RUN / "R5_stock_research_report_reader_v3.md")
    assert handoff["traceability_appendix_sha256"] == sha(
        RUN / "R5_stock_research_report_traceability_v3.yaml"
    )
    assert handoff["quality_scorecard_sha256"] == sha(
        RUN / "R5_stock_research_report_reader_v3_quality_scorecard.yaml"
    )
    assert handoff["status"] == "passed_external_human_review"
    assert Path(handoff["review_form_path"]).name == "R5_stock_research_report_reader_v3_human_review_form.md"
    assert handoff["external_reviewer"] == "Q" and handoff["reviewed_at"]
    assert all(row["status"] == "pass" for row in handoff["required_checklist"])
    assert handoff["sample_quality_report_allowed"] is True
    assert handoff["p2_allowed"] is False
    review_form = (RUN / "R5_stock_research_report_reader_v3_human_review_form.md").read_text(encoding="utf-8")
    assert handoff["reader_report_sha256"] in review_form
    assert handoff["traceability_appendix_sha256"] in review_form
    assert review_form.count("| `pending` |") == 6
    assert all(f"| HR-{number} |" in review_form for number in range(1, 7))
    assert "form_status: `pending_external_human_review`" in review_form
    submission_template = yaml.safe_load(
        (RUN / "R5_stock_research_report_reader_v3_human_review_submission_template.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert submission_template["external_reviewer"] is None
    assert submission_template["decision"] is None
    assert all(row["status"] == "pending" for row in submission_template["required_checklist"])
    assert submission_template["attestation"]["external_human_review_confirmed"] is False
    assert submission_template["attestation"]["automated_agent_generated"] is None


def test_handoff_builder_still_defaults_to_fail_closed_pending() -> None:
    handoff, precheck = load_builder().build_handoff(RUN)
    assert handoff["status"] == "pending_external_human_review"
    assert handoff["external_reviewer"] is None and handoff["reviewed_at"] is None
    assert all(row["status"] == "pending" for row in handoff["required_checklist"])
    assert handoff["sample_quality_report_allowed"] is False
    assert handoff["p2_allowed"] is False
    assert precheck["external_human_review_status"] == "pending"
    assert precheck["sample_quality_report_allowed"] is False
    assert precheck["p2_allowed"] is False


def test_ai_semantic_precheck_does_not_claim_external_signoff() -> None:
    precheck = yaml.safe_load(
        (RUN / "R5_bundle10_ai_assisted_semantic_precheck.yaml").read_text(encoding="utf-8")
    )
    assert precheck["status"] == "pass_for_external_human_handoff"
    assert precheck["external_human_review_status"] == "pending"
    assert all(precheck["checks"].values())
    assert precheck["sample_quality_report_allowed"] is False
    assert precheck["p2_allowed"] is False
