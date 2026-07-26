from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
BUILD_SCRIPT = ROOT / "scripts/build_r5_bundle10_human_review_handoff.py"


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_builder():
    spec = importlib.util.spec_from_file_location("build_r5_bundle10_human_review_handoff", BUILD_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def historical_yaml(historical_blob_bytes, name: str):
    return yaml.safe_load(historical_blob_bytes(f"{HISTORICAL_RUN}/{name}").decode("utf-8"))


def archived_windows_bytes(payload: bytes) -> bytes:
    assert b"\r\n" not in payload
    return payload.replace(b"\n", b"\r\n")


def materialize_handoff_run(tmp_path: Path, historical_blob_bytes) -> Path:
    run = tmp_path / "bundle10_handoff_run"
    for name in (
        "R5_stock_research_report_reader_v3.md",
        "R5_stock_research_report_traceability_v3.yaml",
        "R5_stock_research_report_reader_v3_quality_scorecard.yaml",
        "R5_bundle10_reader_pack.yaml",
    ):
        target = run / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(historical_blob_bytes(f"{HISTORICAL_RUN}/{name}"))
    return run


def test_bundle10_finalized_human_review_handoff_is_hash_bound(
    historical_blob_bytes,
) -> None:
    handoff = historical_yaml(
        historical_blob_bytes, "R5_stock_research_report_reader_v3_human_review.yaml"
    )
    assert handoff["reader_report_sha256"] == sha(
        archived_windows_bytes(
            historical_blob_bytes(
                f"{HISTORICAL_RUN}/R5_stock_research_report_reader_v3.md"
            )
        )
    )
    assert handoff["traceability_appendix_sha256"] == sha(
        archived_windows_bytes(
            historical_blob_bytes(
                f"{HISTORICAL_RUN}/R5_stock_research_report_traceability_v3.yaml"
            )
        )
    )
    assert handoff["quality_scorecard_sha256"] == sha(
        archived_windows_bytes(
            historical_blob_bytes(
                f"{HISTORICAL_RUN}/R5_stock_research_report_reader_v3_quality_scorecard.yaml"
            )
        )
    )
    assert handoff["status"] == "passed_external_human_review"
    assert Path(handoff["review_form_path"]).name == "R5_stock_research_report_reader_v3_human_review_form.md"
    assert handoff["external_reviewer"] == "Q" and handoff["reviewed_at"]
    assert all(row["status"] == "pass" for row in handoff["required_checklist"])
    assert handoff["sample_quality_report_allowed"] is True
    assert handoff["p2_allowed"] is False
    review_form = historical_blob_bytes(
        f"{HISTORICAL_RUN}/R5_stock_research_report_reader_v3_human_review_form.md"
    ).decode("utf-8")
    assert handoff["reader_report_sha256"] in review_form
    assert handoff["traceability_appendix_sha256"] in review_form
    assert review_form.count("| `pending` |") == 6
    assert all(f"| HR-{number} |" in review_form for number in range(1, 7))
    assert "form_status: `pending_external_human_review`" in review_form
    submission_template = historical_yaml(
        historical_blob_bytes,
        "R5_stock_research_report_reader_v3_human_review_submission_template.yaml",
    )
    assert submission_template["external_reviewer"] is None
    assert submission_template["decision"] is None
    assert all(row["status"] == "pending" for row in submission_template["required_checklist"])
    assert submission_template["attestation"]["external_human_review_confirmed"] is False
    assert submission_template["attestation"]["automated_agent_generated"] is None


def test_handoff_builder_still_defaults_to_fail_closed_pending(
    tmp_path: Path,
    historical_blob_bytes,
) -> None:
    handoff, precheck = load_builder().build_handoff(
        materialize_handoff_run(tmp_path, historical_blob_bytes)
    )
    assert handoff["status"] == "pending_external_human_review"
    assert handoff["external_reviewer"] is None and handoff["reviewed_at"] is None
    assert all(row["status"] == "pending" for row in handoff["required_checklist"])
    assert handoff["sample_quality_report_allowed"] is False
    assert handoff["p2_allowed"] is False
    assert precheck["external_human_review_status"] == "pending"
    assert precheck["sample_quality_report_allowed"] is False
    assert precheck["p2_allowed"] is False


def test_ai_semantic_precheck_does_not_claim_external_signoff(
    historical_blob_bytes,
) -> None:
    precheck = historical_yaml(
        historical_blob_bytes, "R5_bundle10_ai_assisted_semantic_precheck.yaml"
    )
    assert precheck["status"] == "pass_for_external_human_handoff"
    assert precheck["external_human_review_status"] == "pending"
    assert all(precheck["checks"].values())
    assert precheck["sample_quality_report_allowed"] is False
    assert precheck["p2_allowed"] is False
