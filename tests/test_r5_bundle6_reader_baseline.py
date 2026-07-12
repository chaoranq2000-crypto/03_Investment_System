from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = REPO_ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"
BASELINE_PATH = RUN_DIR / "R5_bundle6_reader_surface_baseline.yaml"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_text_sha256(path: Path) -> str:
    normalized = path.read_text(encoding="utf-8").encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def test_bundle6_baseline_freezes_current_bundle5_artifacts() -> None:
    baseline = load_yaml(BASELINE_PATH)
    report = REPO_ROOT / baseline["input_artifacts"]["bundle5_draft"]["path"]
    quality = REPO_ROOT / baseline["input_artifacts"]["bundle5_quality_gate"]["path"]

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

    assert canonical_text_sha256(crlf) == expected


def test_reader_surface_inventory_records_known_failures() -> None:
    baseline = load_yaml(BASELINE_PATH)
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


def test_coverage_and_fixed_boundaries_are_preserved() -> None:
    baseline = load_yaml(BASELINE_PATH)
    coverage = baseline["coverage_baseline"]

    assert coverage["total"] == 10
    assert coverage["covered"] == 4
    assert coverage["partial"] == 4
    assert coverage["missing"] == 2
    assert baseline["reader_quality_diagnostic"]["reader_candidate_accepted"] is False
    assert baseline["canonical_state_changed"] is False
    assert baseline["sample_quality_report_allowed"] is False
    assert baseline["p2_allowed"] is False
