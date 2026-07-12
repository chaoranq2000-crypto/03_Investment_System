from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
RUN_DIR = REPO_ROOT / "reports/workflow_runs" / WORKFLOW_ID
SCRIPT = REPO_ROOT / "scripts/build_r5_bundle5_benchmark_coverage_precheck.py"
PROFILE_PATH = REPO_ROOT / "codex_tasks/r5_after_bundle4/SAMPLE_REPORT_BENCHMARK_PROFILE.yaml"
RESULT_PATH = RUN_DIR / "R5_bundle5_benchmark_coverage_precheck.yaml"


def load_module():
    spec = importlib.util.spec_from_file_location("r5_bundle5_benchmark_precheck_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PRECHECK = load_module()


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_recorded_precheck_covers_exact_profile_dimensions() -> None:
    profile = load_yaml(PROFILE_PATH)
    result = load_yaml(RESULT_PATH)

    expected = profile["coverage_dimensions"]
    actual = [row["dimension"] for row in result["coverage"]]
    assert actual == expected
    assert result["coverage_dimensions_expected"] == expected
    assert result["coverage_summary"]["total"] == 10
    assert sum(result["coverage_summary"][state] for state in PRECHECK.VALID_COVERAGE_STATES) == 10
    assert {row["status"] for row in result["coverage"]} <= PRECHECK.VALID_COVERAGE_STATES
    assert result["unsupported_populated_sections"] == []


def test_every_dimension_has_repository_support_or_visible_gap() -> None:
    result = load_yaml(RESULT_PATH)

    for row in result["coverage"]:
        assert row["rendered"] is True
        assert row["support_check"] == "pass"
        assert row["issues"] == []
        if row["status"] in {"covered", "partial"}:
            assert row["evidence_ids"] or row["explicit_todo_or_missing"]
        if row["status"] in {"partial", "missing"}:
            assert row["explicit_todo_or_missing"]
            assert row["visible_gaps_in_report"]


def test_profile_alias_does_not_create_an_eleventh_dimension() -> None:
    section = {
        "section_id": "research_conclusion_and_watch_conditions_without_action_instruction",
        "title": "结论",
        "readiness": "partial",
        "evidence_ids": ["ev_test"],
        "visible_gaps": ["MISSING_TEST"],
    }
    row = PRECHECK.evaluate_dimension(section, "## 结论\nev_test\nMISSING_TEST\n")

    assert row["dimension"] == "research_conclusion_and_watch_conditions"
    assert row["support_check"] == "pass"


def test_prohibited_language_injection_fails_the_filter() -> None:
    profile = load_yaml(PROFILE_PATH)
    clean_report = (RUN_DIR / "R5_stock_research_note_reviewed_input_draft.md").read_text(encoding="utf-8")

    assert PRECHECK.find_forbidden_language(clean_report, profile) == []
    assert PRECHECK.find_forbidden_language(clean_report + "\n建议买入\n", profile)
    assert PRECHECK.find_forbidden_language(clean_report + "\nposition sizing\n", profile)


def test_populated_section_without_anchor_or_gap_fails_support_check() -> None:
    section = {
        "section_id": "company_context",
        "title": "公司背景",
        "readiness": "covered",
        "evidence_ids": [],
        "visible_gaps": [],
    }
    row = PRECHECK.evaluate_dimension(section, "## 公司背景\n只有无锚点文本\n")

    assert row["support_check"] == "fail"
    assert any("no repository evidence anchor" in issue for issue in row["issues"])


def test_not_applicable_cannot_hide_a_known_gap() -> None:
    section = {
        "section_id": "dated_sentiment_and_events_when_supported",
        "title": "事件",
        "readiness": "not_applicable",
        "evidence_ids": [],
        "visible_gaps": ["TODO_SOURCE_REQUIRED"],
    }
    row = PRECHECK.evaluate_dimension(section, "## 事件\nTODO_SOURCE_REQUIRED\n")

    assert row["support_check"] == "fail"
    assert any("cannot hide" in issue for issue in row["issues"])


def test_sample_material_is_not_registered_as_evidence() -> None:
    result = load_yaml(RESULT_PATH)

    assert result["sample_evidence_registered_count"] == 0
    assert result["sample_registration_scan"]["matches"] == []
    assert result["sample_registration_scan"]["checked"] > 0
    assert result["forbidden_language_check"] == {"status": "pass", "match_count": 0, "matches": []}


def test_precheck_never_changes_report_or_p2_boundaries() -> None:
    result = load_yaml(RESULT_PATH)

    assert result["precheck_status"] == "pass"
    assert result["blockers"] == []
    assert result["precheck_only"] is True
    assert result["promotion_decision"] is False
    assert result["canonical_registry_write_performed"] is False
    assert result["sample_quality_report_allowed"] is False
    assert result["p2_allowed"] is False
    assert all(len(row["sha256"]) == 64 for row in result["input_artifacts"].values())


def test_benchmark_directory_contains_no_external_report_bodies() -> None:
    benchmark_dir = REPO_ROOT / "benchmarks/sample_reports"
    disallowed_suffixes = {".txt", ".docx", ".pdf"}

    assert not [path for path in benchmark_dir.iterdir() if path.is_file() and path.suffix.lower() in disallowed_suffixes]
