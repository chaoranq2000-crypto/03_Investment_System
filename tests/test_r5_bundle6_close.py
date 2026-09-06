import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
HISTORICAL_EXPECTED_ARTIFACTS = (
    "codex_tasks/r5_after_bundle5/R5_BUNDLE6_EXPECTED_ARTIFACTS.yaml"
)
HISTORICAL_CLOSE_READOUT = (
    "reports/p1_6/R5_BUNDLE_6_READER_REPORT_QUALITY_REMEDIATION_CLOSE_READOUT.md"
)
BUILDER_PATH = ROOT / "scripts/build_r5_bundle6_close_readout.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("r5_bundle6_close_builder_test", BUILDER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def historical_yaml(historical_blob_bytes, name: str):
    return yaml.safe_load(historical_blob_bytes(f"{HISTORICAL_RUN}/{name}").decode("utf-8"))


def artifact_exists(path: str, historical_blob_bytes) -> bool:
    try:
        return bool(historical_blob_bytes(path))
    except (AssertionError, subprocess.CalledProcessError):
        return False


@pytest.mark.legacy_compatibility
def test_all_declared_bundle6_artifacts_exist(historical_blob_bytes):
    expected = yaml.safe_load(
        historical_blob_bytes(HISTORICAL_EXPECTED_ARTIFACTS).decode("utf-8")
    )
    missing = [
        x["path"]
        for x in expected["required_artifacts"]
        if not artifact_exists(x["path"], historical_blob_bytes)
    ]
    assert missing == []


@pytest.mark.legacy_compatibility
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


@pytest.mark.legacy_compatibility
def test_close_state_keeps_human_review_and_promotion_boundaries(historical_blob_bytes):
    close = historical_blob_bytes(HISTORICAL_CLOSE_READOUT).decode("utf-8")
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


def test_bundle6_builder_uses_explicit_contract_and_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    builder = load_builder()
    root = tmp_path / "repo"
    run_rel = Path("reports/workflow_runs/wf_fixture_bundle6")
    run = root / run_rel
    run.mkdir(parents=True)

    report = run / "R5_stock_research_report_reader_v2.md"
    appendix = run / "R5_stock_research_report_traceability_v2.yaml"
    scorecard = run / "R5_stock_research_report_reader_v2_quality_scorecard.yaml"
    human = run / "R5_stock_research_report_reader_v2_human_review.yaml"
    comparison = run / "R5_bundle6_before_after_comparison.yaml"
    report.write_text("# Fixture reader\n", encoding="utf-8")
    appendix.write_text("records: []\n", encoding="utf-8")
    scorecard.write_text(
        yaml.safe_dump({"score": 100, "critical_blocker_count": 0}),
        encoding="utf-8",
    )
    human.write_text(
        yaml.safe_dump(
            {
                "status": "pending",
                "report_path": report.relative_to(root).as_posix(),
                "report_sha256": builder.sha(report),
            }
        ),
        encoding="utf-8",
    )
    before = {
        "raw_internal_ids": 3,
        "internal_paths": 2,
        "raw_gap_tokens": 1,
        "numeric_format_violations": 1,
        "covered_dimensions": 4,
        "partial_dimensions": 3,
        "missing_dimensions": 3,
        "reader_quality_score": 60,
    }
    after = {
        "raw_internal_ids": 0,
        "internal_paths": 0,
        "raw_gap_tokens": 0,
        "numeric_format_violations": 0,
        "covered_dimensions": 10,
        "partial_dimensions": 0,
        "missing_dimensions": 0,
        "reader_quality_score": 100,
    }
    comparison.write_text(
        yaml.safe_dump({"bundle5_draft": before, "bundle6_candidate": after}),
        encoding="utf-8",
    )

    expected_path = root / "fixtures/bundle6_expected_artifacts.yaml"
    expected_path.parent.mkdir(parents=True)
    expected_path.write_text(
        yaml.safe_dump(
            {
                "required_artifacts": [
                    {
                        "path": (
                            "reports/workflow_runs/wf_historical/" + artifact.name
                        ),
                        "owner_card": "fixture",
                    }
                    for artifact in (report, appendix, scorecard, human, comparison)
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    output_rel = Path("outputs/bundle6_close.md")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(BUILDER_PATH),
            "--repo-root",
            str(root),
            "--run-root",
            run_rel.as_posix(),
            "--expected-artifacts",
            expected_path.relative_to(root).as_posix(),
            "--output",
            output_rel.as_posix(),
            "--full-pytest-summary",
            "fixture pass",
        ],
    )

    assert builder.main() == 0
    rendered = (root / output_rel).read_text(encoding="utf-8")
    assert "expected artifacts hashed=5" in rendered
    assert "sample_quality_report_allowed: `false`" in rendered
    assert "p2_allowed: `false`" in rendered
    assert not (
        root
        / "reports/p1_6/R5_BUNDLE_6_READER_REPORT_QUALITY_REMEDIATION_CLOSE_READOUT.md"
    ).exists()
