from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "benchmarks/sample_reports/README.md"
SCHEMA = REPO_ROOT / "benchmarks/sample_reports/sample_report_metadata.schema.yaml"
MAPPING = REPO_ROOT / "benchmarks/sample_reports/section_expectation_mapping.yaml"


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_readme_limits_samples_to_structure_density_and_evidence_requirements():
    text = README.read_text(encoding="utf-8")
    for needle in ["structure", "density", "section capability", "evidence-requirement"]:
        assert needle in text
    assert "Do not paste full external" in text
    assert "trading advice" in text


def test_metadata_schema_has_required_fields():
    schema = load_yaml(SCHEMA)
    required = schema["required_fields"]
    for field in [
        "sample_id",
        "company_name",
        "sections_present",
        "forecast_present",
        "valuation_present",
        "technical_present",
        "sentiment_present",
        "catalyst_present",
        "copyright_status",
        "local_user_provided",
    ]:
        assert field in required
    assert schema["rules"]["no_full_text_storage"] is True
    assert schema["rules"]["no_rating_or_position_guidance_copy"] is True


def test_section_mapping_links_samples_to_r5_rubric_sections():
    mapping = load_yaml(MAPPING)
    targets = set(mapping["mapping"].values())
    for section in ["preface", "financial_overview", "business_breakdown", "industry_analysis", "forecast", "valuation", "technical_analysis", "sentiment_analysis", "catalyst_events", "research_conclusion"]:
        assert section in targets
    assert mapping["rules"]["facts_from_sample_are_not_evidence"] is True


def test_no_external_report_body_files_are_present():
    disallowed_suffixes = {".txt", ".docx", ".pdf"}
    files = [path for path in README.parent.iterdir() if path.is_file()]
    assert not [path for path in files if path.suffix.lower() in disallowed_suffixes]
