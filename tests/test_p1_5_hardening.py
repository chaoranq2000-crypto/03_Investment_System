from __future__ import annotations

import csv
import py_compile
import re
import tomllib
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SEGMENT_ID = "ai_server_liquid_cooling"
STOCK_REPORTS = [
    ROOT / "reports/stocks/002837_invic/2026-07-01_stock_deep_dive.md",
    ROOT / "reports/stocks/300731_cotran/2026-07-01_stock_deep_dive.md",
]
EXCLUDED_PARTS = {".git", ".conda", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def repo_files(pattern: str) -> list[Path]:
    return [
        path
        for path in ROOT.rglob(pattern)
        if not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
    ]


def read_csv(relative_path: str) -> list[dict[str, str]]:
    with (ROOT / relative_path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def csv_header(relative_path: str) -> list[str]:
    with (ROOT / relative_path).open(encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle))


def load_yaml(relative_path: str) -> Any:
    return yaml.safe_load((ROOT / relative_path).read_text(encoding="utf-8"))


def as_iso_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value)
    return None


def project_as_of_date() -> date:
    config = load_yaml("config/research_config.yaml")
    value = config["project"]["as_of_date"]
    parsed = as_iso_date(value)
    assert parsed is not None
    return parsed


def split_ids(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def test_configs_parse_and_existing_acceptance_tests_compile() -> None:
    for path in [ROOT / "pyproject.toml", ROOT / ".codex/config.toml"]:
        tomllib.loads(path.read_text(encoding="utf-8"))

    for path in repo_files("*.yaml") + repo_files("*.yml"):
        yaml.safe_load(path.read_text(encoding="utf-8"))

    for path in [ROOT / "tests/test_p0_acceptance.py", ROOT / "tests/test_p1_acceptance.py"]:
        py_compile.compile(str(path), doraise=True)


def test_skill_frontmatter_is_valid_yaml() -> None:
    for skill_dir in sorted((ROOT / ".agents/skills").iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        text = skill_file.read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{skill_file.relative_to(ROOT)} missing YAML front matter"
        parts = text.split("---", 2)
        assert len(parts) == 3, f"{skill_file.relative_to(ROOT)} malformed YAML front matter"
        metadata = yaml.safe_load(parts[1])
        assert metadata["name"] == skill_dir.name
        assert isinstance(metadata.get("description"), str) and metadata["description"].strip()


def test_stage_metadata_is_consistent() -> None:
    config = load_yaml("config/research_config.yaml")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    p2_checklist = (ROOT / "reports/p1/p2_entry_checklist.md").read_text(encoding="utf-8")

    assert config["project"]["stage"] == "P1.5"
    assert config["project"]["previous_stage"]["P0"] == "conditional_pass"
    assert config["project"]["previous_stage"]["P1"] == "conditional_pass_with_medium_todos"
    assert config["project"]["current_focus"] == "pre_p2_hardening"
    assert "P1.5：pre-P2 hardening" in readme
    assert "READY_FOR_LIMITED_P2" in p2_checklist
    assert "不允许直接批量扩展细分或公司池" in p2_checklist


def test_no_swallowed_placeholder_paths() -> None:
    bad_patterns = [
        "reports/segments/" + "/",
        "reports/stocks/" + "_/",
        "reports/segments/" + "/_segment_report.md",
        "reports/stocks/" + "_/_stock_deep_dive.md",
    ]
    violations: list[str] = []
    for pattern in ["*.md", "*.py", "*.toml", "*.yaml", "*.yml"]:
        for path in repo_files(pattern):
            text = path.read_text(encoding="utf-8", errors="replace")
            for bad in bad_patterns:
                if bad in text:
                    violations.append(f"{path.relative_to(ROOT)} contains {bad}")
    assert not violations, "\n".join(violations)


def test_structured_csvs_have_required_fields_and_rows() -> None:
    config = load_yaml("config/research_config.yaml")
    required = {
        "data/manifests/evidence_manifest.csv": config["evidence"]["required_manifest_fields"],
        "data/manifests/claims_registry.csv": config["claims"]["required_registry_fields"],
        "data/manifests/metrics_registry.csv": config["metrics"]["required_registry_fields"],
        "data/processed/normalized/segment_company_exposure.csv": (
            config["segment_company_exposure"]["required_fields"]
        ),
    }
    for relative_path, fields in required.items():
        header = csv_header(relative_path)
        missing = [field for field in fields if field not in header]
        assert not missing, f"{relative_path} missing fields: {missing}"
        assert read_csv(relative_path), f"{relative_path} has no data rows"

    assert len(read_csv("data/manifests/evidence_manifest.csv")) >= 15
    assert len(read_csv("data/manifests/claims_registry.csv")) >= 22
    assert len(read_csv("data/manifests/metrics_registry.csv")) >= 44
    assert len(read_csv("reports/segments/ai_server_liquid_cooling/company_universe.csv")) == 5
    assert len(read_csv("data/processed/normalized/segment_company_exposure.csv")) == 5


def test_evidence_manifest_separates_source_url_and_local_paths() -> None:
    evidence = read_csv("data/manifests/evidence_manifest.csv")
    for row in evidence:
        assert row["source_url"] or row["raw_file_path"], row["evidence_id"]
        if row["source_url"]:
            assert row["source_url"].startswith(("http://", "https://")), row["evidence_id"]
        assert row["processed_text_path"] or row["processed_table_path"], row["evidence_id"]
        if row["raw_file_path"]:
            assert not row["raw_file_path"].startswith(("http://", "https://")), row["evidence_id"]
            assert (ROOT / row["raw_file_path"]).exists(), row["raw_file_path"]
        for processed_field in ["processed_text_path", "processed_table_path"]:
            if row[processed_field]:
                assert not row[processed_field].startswith(("http://", "https://")), row["evidence_id"]
                assert (ROOT / row[processed_field]).exists(), row[processed_field]
        if row["reliability_rank"] == "D":
            assert row["material_claim_allowed"] == "false"
            assert row["candidate_status"] in {"not_allowed", "blocked", "not_generated"}
            assert row["review_status"] in {"blocked", "rejected", "reviewed"}


def test_claims_and_metrics_registry_have_no_dangling_evidence() -> None:
    evidence = read_csv("data/manifests/evidence_manifest.csv")
    evidence_ids = {row["evidence_id"] for row in evidence}
    evidence_rank = {row["evidence_id"]: row["reliability_rank"] for row in evidence}

    for row in read_csv("data/manifests/claims_registry.csv"):
        assert row["evidence_id"] in evidence_ids, row["claim_id"]
        assert row["review_status"]
        if evidence_rank[row["evidence_id"]] == "D":
            assert row["entity_type"] == "other"

    for row in read_csv("data/manifests/metrics_registry.csv"):
        assert row["source_evidence_id"] in evidence_ids, row["metric_id"]
        assert row["review_status"]
        assert row["is_estimate"] in {"true", "false"}


def test_no_future_generated_or_review_dates() -> None:
    as_of = project_as_of_date()
    checked_fields = {
        "generated_at",
        "ingested_at",
        "created_at",
        "updated_at",
        "reviewed_at",
        "score_date",
        "report_date",
        "valid_from",
        "last_reviewed_at",
        "closed_at",
    }
    violations: list[str] = []

    for path in [
        "data/manifests/evidence_manifest.csv",
        "data/manifests/metrics_registry.csv",
        "data/processed/normalized/segment_company_exposure.csv",
        "reports/segments/ai_server_liquid_cooling/company_universe.csv",
        "reports/p1/quality_issues.csv",
    ]:
        for row_number, row in enumerate(read_csv(path), start=2):
            for key, value in row.items():
                if key not in checked_fields:
                    continue
                parsed = as_iso_date(value)
                if parsed and parsed > as_of:
                    violations.append(f"{path}:{row_number} {key}={value}")

    for path in [
        "config/research_config.yaml",
        "config/segment_taxonomy.yaml",
        "reports/segments/ai_server_liquid_cooling/segment_definition.yaml",
        "reports/segments/ai_server_liquid_cooling/scorecard.yaml",
        "reports/stocks/002837_invic/stock_scorecard.yaml",
        "reports/stocks/300731_cotran/stock_scorecard.yaml",
    ]:
        data = load_yaml(path)

        def walk(node: Any, trail: str = "") -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    child = f"{trail}.{key}" if trail else str(key)
                    if str(key) in checked_fields:
                        parsed = as_iso_date(value)
                        if parsed and parsed > as_of:
                            violations.append(f"{path}:{child}={value}")
                    walk(value, child)
            elif isinstance(node, list):
                for index, item in enumerate(node):
                    walk(item, f"{trail}[{index}]")

        walk(data)

    assert not violations, "\n".join(violations)


def test_company_universe_matches_segment_company_exposure() -> None:
    universe = read_csv("reports/segments/ai_server_liquid_cooling/company_universe.csv")
    exposure = read_csv("data/processed/normalized/segment_company_exposure.csv")
    universe_by_company = {row["company_id"]: row for row in universe}
    exposure_by_company = {row["company_id"]: row for row in exposure}

    assert set(universe_by_company) == set(exposure_by_company)
    for company_id, universe_row in universe_by_company.items():
        exposure_row = exposure_by_company[company_id]
        for field in ["segment_id", "stock_code", "stock_name", "exposure_type", "exposure_score", "confidence"]:
            assert exposure_row[field] == universe_row[field], f"{company_id} differs on {field}"
        assert exposure_row["verification_status"]
        assert exposure_row["next_evidence_needed"]
        assert exposure_row["last_reviewed_at"]
        assert exposure_row["reviewer_note"]
        assert split_ids(exposure_row["evidence_ids"])
        if exposure_row["exposure_type"] == "technology":
            assert int(exposure_row["exposure_score"]) <= 2
        if exposure_row["revenue_pct"].startswith("MISSING"):
            assert int(exposure_row["exposure_score"]) <= 4


def test_exposure_scoring_rules_are_complete() -> None:
    rules = load_yaml("config/exposure_scoring_rules.yaml")
    score_rules = rules["exposure_score_rules"]
    assert set(score_rules) == {0, 1, 2, 3, 4, 5}
    assert rules["guardrails"]["revenue_or_profit_exposure_requires_direct_disclosure"] is True
    assert (
        rules["guardrails"][
            "technology_exposure_cannot_receive_score_above_2_without_customer_order_or_revenue_evidence"
        ]
        is True
    )


def test_scorecards_match_scoring_framework_dimensions() -> None:
    frameworks = load_yaml("config/scoring_frameworks.yaml")["frameworks"]
    evidence_ids = {row["evidence_id"] for row in read_csv("data/manifests/evidence_manifest.csv")}

    segment_framework = set(frameworks["segment_scorecard"]["dimensions"])
    segment_scores = load_yaml("reports/segments/ai_server_liquid_cooling/scorecard.yaml")[
        "segment_scorecard"
    ]["scores"]
    assert set(segment_scores) == segment_framework

    stock_framework = set(frameworks["stock_scorecard"]["dimensions"])
    for path in [
        "reports/stocks/002837_invic/stock_scorecard.yaml",
        "reports/stocks/300731_cotran/stock_scorecard.yaml",
    ]:
        stock_scores = load_yaml(path)["stock_scorecard"]["scores"]
        assert set(stock_scores) == stock_framework
        for dimension, payload in stock_scores.items():
            ids = payload["evidence_ids"]
            assert ids, f"{path} {dimension} missing evidence_ids"
            assert all(evidence_id == "TODO" or evidence_id in evidence_ids for evidence_id in ids)

    for dimension, payload in segment_scores.items():
        ids = payload["evidence_ids"]
        assert ids, f"segment score {dimension} missing evidence_ids"
        assert all(evidence_id == "TODO" or evidence_id in evidence_ids for evidence_id in ids)


def test_quality_issues_have_gate_fields() -> None:
    rows = read_csv("reports/p1/quality_issues.csv")
    open_high = [
        row
        for row in rows
        if row["severity"].lower() == "high" and row["status"].lower() not in {"fixed", "closed"}
    ]
    assert not open_high
    for row in rows:
        assert row["file_path"]
        assert row["issue_type"]
        assert row["owner"]
        if row["status"].lower() in {"todo", "open"}:
            assert row["due_date"]
            assert row["blocking_for_stage"]


def test_reports_have_required_sections_and_evidence_markers() -> None:
    segment_report = ROOT / "reports/segments/ai_server_liquid_cooling/2026-07-01_segment_report.md"
    segment_text = segment_report.read_text(encoding="utf-8")
    for section in [
        "## 0. Metadata",
        "## 1. 一句话结论",
        "## 2. 细分定义与边界",
        "## 7. A股公司池",
        "## 10. 风险与反证",
        "## 11. 评分卡",
        "## 14. Refresh Status",
    ]:
        assert section in segment_text
    for dimension in load_yaml("config/scoring_frameworks.yaml")["frameworks"]["segment_scorecard"][
        "dimensions"
    ]:
        assert f"| {dimension} |" in segment_text

    stock_sections = [
        "## 0. Metadata",
        "## 1. 一页研究假设",
        "## 2. 财务质量：增长、利润率、现金流、资产负债",
        "## 3. 业务拆分：利润从哪里来",
        "## 4. 细分方向暴露：行业逻辑如何落到公司",
        "## 7. 盈利假设与敏感性",
        "## 8. 估值场景",
        "## 9. 催化剂与跟踪日历",
        "## 10. 风险、反证和可证伪条件",
        "## 13. Evidence Map",
        "## 14. Refresh Status",
    ]
    for path in STOCK_REPORTS:
        text = path.read_text(encoding="utf-8")
        for section in stock_sections:
            assert section in text, f"{path.relative_to(ROOT)} missing {section}"
        assert "evidence_id=" in text
        assert "MISSING: 暂无直接披露" in text


def test_no_direct_trading_instruction_phrases() -> None:
    forbidden = ["建议买入", "建议卖出", "强烈推荐", "买入评级", "卖出评级", "持有评级"]
    paths = [
        *Path(ROOT / "reports/p1").glob("*.md"),
        *Path(ROOT / "reports/segments" / SEGMENT_ID).glob("*.md"),
        *Path(ROOT / "reports/stocks").glob("*/*.md"),
        ROOT / "decisions/thesis_log.md",
        ROOT / "decisions/watchlist_changes.md",
    ]

    violations = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for phrase in forbidden:
            if phrase in text:
                violations.append(f"{path.relative_to(ROOT)} contains {phrase}")

    assert not violations, "\n".join(violations)
