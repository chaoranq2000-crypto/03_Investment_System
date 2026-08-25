from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/build_r5_bundle5_benchmark_coverage_precheck.py"
RUBRIC_PATH = REPO_ROOT / "benchmarks/r5_report_quality_rubric.yaml"
SAMPLE_POLICY_PATH = REPO_ROOT / "docs/workflows/R5_SAMPLE_QUALITY_STOCK_REPORT_SPEC.md"


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


def build_current_profile(path: Path) -> dict:
    rubric = load_yaml(RUBRIC_PATH)
    policy_text = SAMPLE_POLICY_PATH.read_text(encoding="utf-8")
    coverage_dimensions = list(rubric["required_sections"])
    assert len(coverage_dimensions) == 10
    for marker in (
        "R5 只学习其“研究结构和信息密度”",
        "直接交易指令",
        "个人化仓位安排",
        "保证收益表达",
    ):
        assert marker in policy_text

    profile = {
        "schema_version": "current_r5_sample_benchmark_fixture_v1",
        "profile_id": "current_r5_sample_benchmark_policy_fixture",
        "source_origin": "current_repository_authority",
        "source_files": [],
        "use_as_research_evidence": False,
        "use_as_workflow_fact_source": False,
        "use_as_gate_definition": False,
        "allowed_uses": ["section_coverage_reference", "information_density_reference"],
        "prohibited_uses": [
            "importing_factual_claims",
            "importing_forecasts_or_prices",
            "importing_investment_ratings",
            "importing_position_sizing",
            "importing_trade_timing",
        ],
        "coverage_dimensions": coverage_dimensions,
        "forbidden_output_patterns": [
            "直接交易指令",
            "个人化仓位安排",
            "保证收益",
            "买入",
            "卖出",
            "仓位",
        ],
        "quality_flags_fixed": {
            "sample_quality_report_allowed": False,
            "p2_allowed": False,
        },
    }
    path.write_text(
        yaml.safe_dump(profile, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return profile


@pytest.fixture
def precheck_fixture(tmp_path: Path) -> dict:
    profile_path = tmp_path / "sample_report_benchmark_profile.yaml"
    profile = build_current_profile(profile_path)
    report_path = tmp_path / "research_draft.md"
    pack_path = tmp_path / "research_pack.yaml"
    quality_path = tmp_path / "quality_gate.yaml"
    manifest_root = tmp_path / "manifests"
    reviewed_input_root = tmp_path / "reviewed_inputs"
    registry_dir = tmp_path / "registries"
    manifest_root.mkdir()
    reviewed_input_root.mkdir()
    registry_dir.mkdir()
    registration_path = manifest_root / "reviewed_registry.yaml"
    sections = []
    report_lines = ["# Fixture research draft"]
    for index, dimension in enumerate(profile["coverage_dimensions"], 1):
        title = f"Fixture section {index}"
        evidence_id = f"ev_fixture_{index:02d}"
        sections.append(
            {
                "section_id": dimension,
                "title": title,
                "readiness": "covered",
                "evidence_ids": [evidence_id],
                "visible_gaps": [],
            }
        )
        report_lines.extend([f"## {title}", evidence_id])
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    pack_path.write_text(
        yaml.safe_dump({"report_sections": sections}, sort_keys=False),
        encoding="utf-8",
    )
    quality_path.write_text(
        yaml.safe_dump({"critical_quality_blockers": 0}, sort_keys=False),
        encoding="utf-8",
    )
    registration_path.write_text(
        "artifact_type: reviewed_fixture_registry\n",
        encoding="utf-8",
    )
    result = PRECHECK.build_precheck(
        REPO_ROOT,
        workflow_id="wf_fixture_benchmark",
        stock_code="300001",
        profile_path=profile_path,
        report_path=report_path,
        pack_path=pack_path,
        quality_path=quality_path,
        manifest_root=manifest_root,
        reviewed_input_root=reviewed_input_root,
        registry_dir=registry_dir,
    )
    return {
        "profile": profile,
        "result": result,
        "report_path": report_path,
        "profile_path": profile_path,
    }


def test_recorded_precheck_covers_exact_profile_dimensions(
    precheck_fixture: dict,
) -> None:
    profile = precheck_fixture["profile"]
    result = precheck_fixture["result"]

    expected = profile["coverage_dimensions"]
    actual = [row["dimension"] for row in result["coverage"]]
    assert actual == expected
    assert result["coverage_dimensions_expected"] == expected
    assert result["coverage_summary"]["total"] == 10
    assert sum(result["coverage_summary"][state] for state in PRECHECK.VALID_COVERAGE_STATES) == 10
    assert {row["status"] for row in result["coverage"]} <= PRECHECK.VALID_COVERAGE_STATES
    assert result["unsupported_populated_sections"] == []


def test_every_dimension_has_repository_support_or_visible_gap(
    precheck_fixture: dict,
) -> None:
    result = precheck_fixture["result"]

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


def test_prohibited_language_injection_fails_the_filter(
    precheck_fixture: dict,
) -> None:
    profile = precheck_fixture["profile"]
    clean_report = precheck_fixture["report_path"].read_text(encoding="utf-8")

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


def test_sample_material_is_not_registered_as_evidence(
    precheck_fixture: dict,
) -> None:
    profile = precheck_fixture["profile"]
    result = precheck_fixture["result"]

    assert profile["use_as_research_evidence"] is False
    assert profile["use_as_workflow_fact_source"] is False
    assert profile["use_as_gate_definition"] is False
    assert result["sample_evidence_registered_count"] == 0
    assert result["sample_registration_scan"]["matches"] == []
    assert result["sample_registration_scan"]["checked"] > 0
    assert result["forbidden_language_check"] == {"status": "pass", "match_count": 0, "matches": []}


def test_precheck_never_changes_report_or_p2_boundaries(
    precheck_fixture: dict,
) -> None:
    result = precheck_fixture["result"]

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
