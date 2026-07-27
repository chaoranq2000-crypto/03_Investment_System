from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def historical_yaml(historical_blob_bytes, name: str):
    return yaml.safe_load(historical_blob_bytes(f"{HISTORICAL_RUN}/{name}").decode("utf-8"))


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_text_sha256(payload: bytes) -> str:
    normalized = payload.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def test_bundle6_baseline_freezes_current_bundle5_artifacts(historical_blob_bytes) -> None:
    baseline = historical_yaml(
        historical_blob_bytes, "R5_bundle6_reader_surface_baseline.yaml"
    )
    report = historical_blob_bytes(baseline["input_artifacts"]["bundle5_draft"]["path"])
    quality = historical_blob_bytes(
        baseline["input_artifacts"]["bundle5_quality_gate"]["path"]
    )

    assert baseline["classification"] == "audit_oriented_research_draft_not_reader_candidate"
    assert baseline["before_state_preserved"] is True
    assert baseline["input_artifacts"]["bundle5_draft"]["sha256"] == sha256(report)
    assert baseline["input_artifacts"]["bundle5_quality_gate"]["sha256_mode"] == "canonical_lf_utf8"
    assert baseline["input_artifacts"]["bundle5_quality_gate"]["sha256"] == canonical_text_sha256(quality)
    assert baseline["verification"]["bundle5_truthfulness"] == "pass_checked_8_failed_0"
    assert baseline["verification"]["critical_quality_blockers"] == 0


def test_canonical_text_hash_is_line_ending_independent(tmp_path: Path) -> None:
    crlf = tmp_path / "quality.yaml"
    crlf.write_bytes(b"status: pass\r\ncount: 1\r\n")
    expected = hashlib.sha256(b"status: pass\ncount: 1\n").hexdigest()

    assert canonical_text_sha256(crlf.read_bytes()) == expected


def test_reader_surface_inventory_records_known_failures(historical_blob_bytes) -> None:
    baseline = historical_yaml(
        historical_blob_bytes, "R5_bundle6_reader_surface_baseline.yaml"
    )
    surface = baseline["reader_surface"]

    assert surface["line_count"] > 0
    assert surface["heading_count"] > 0
    assert surface["raw_internal_id_count"] > 0
    assert surface["internal_path_count"] > 0
    assert surface["machine_label_count"] > 0
    assert surface["gap_token_count"] > 0
    assert surface["duplicate_machine_readiness_section_count"] > 0
    assert surface["source_gap_appendix_in_main_body"] is True
    assert surface["over_precise_numeric_count"] > 0


def test_coverage_and_fixed_boundaries_are_preserved(historical_blob_bytes) -> None:
    baseline = historical_yaml(
        historical_blob_bytes, "R5_bundle6_reader_surface_baseline.yaml"
    )
    coverage = baseline["coverage_baseline"]

    assert coverage["total"] == 10
    assert coverage["covered"] == 4
    assert coverage["partial"] == 4
    assert coverage["missing"] == 2
    assert baseline["reader_quality_diagnostic"]["reader_candidate_accepted"] is False
    assert baseline["canonical_state_changed"] is False
    assert baseline["sample_quality_report_allowed"] is False
    assert baseline["p2_allowed"] is False
