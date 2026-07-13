from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import yaml

from src.report.r5_reader_report_writer import (
    SECTION_HEADINGS,
    build_reader_report,
    build_traceability_appendix,
    validate_citations,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_bundle10_pack_renders_without_identity_hardcoding() -> None:
    pack = yaml.safe_load((RUN / "R5_bundle10_reader_pack.yaml").read_text(encoding="utf-8"))
    report = build_reader_report(pack)
    appendix = build_traceability_appendix(pack)
    assert validate_citations(report, appendix) == []
    assert pack["metadata"]["company_name"] in report
    assert str(pack["metadata"]["stock_code"]) in report
    assert all(report.count(heading) == 1 for heading in SECTION_HEADINGS.values())
    writer_source = (ROOT / "src/report/r5_reader_report_writer.py").read_text(encoding="utf-8")
    for token in (pack["metadata"]["company_name"], str(pack["metadata"]["stock_code"]), pack["metadata"]["workflow_id"]):
        assert token not in writer_source


def test_reader_pack_contract_accepts_real_bundle10_pack() -> None:
    validator = load_script("validate_r5_reader_report_pack", ROOT / "scripts/validate_r5_reader_report_pack.py")
    pack = yaml.safe_load((RUN / "R5_bundle10_reader_pack.yaml").read_text(encoding="utf-8"))
    assert validator.validate_pack(pack, ROOT) == []


def test_real_bundle10_pack_has_unique_prose_and_exact_value_sources() -> None:
    pack = yaml.safe_load((RUN / "R5_bundle10_reader_pack.yaml").read_text(encoding="utf-8"))
    report = build_reader_report(pack)
    prose = []
    for line in report.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "|", "-", ">")):
            continue
        normalized = re.sub(r"(?:\s*\[E\d+\])+\s*$", "", stripped)
        if normalized != "---":
            prose.append(normalized)
    assert len(prose) == len(set(prose))

    records = {
        row["display_reference_id"]: row for row in pack["traceability_records"]
    }
    assert records["E15"]["source_path"].endswith("R5_bundle9_valuation_pack.yaml")
    assert len(records["E15"]["raw_evidence_ids"]) == 4
    assert all(
        evidence_id.startswith("ev_structured_market_data_")
        for evidence_id in records["E15"]["raw_evidence_ids"]
    )
    assert records["E16"]["claim_type"] == "metric_statement"
    assert records["E17"]["source_path"].endswith("forecast_sensitivity.csv")
    assert records["E18"]["source_path"].endswith("R5_bundle9_valuation_pack.yaml")
    assert "[E9][E15]" in report
    assert "[E18][E14]" in report

    sentiment = yaml.safe_load(
        (RUN / "R5_bundle10_sentiment_event_pack.yaml").read_text(encoding="utf-8")
    )
    assert sentiment["as_of_date"] == pack["metadata"]["cutoff_date"]
    assert sentiment["information_cutoff_date"] == pack["metadata"]["cutoff_date"]
    assert sentiment["retrieved_at"] >= sentiment["information_cutoff_date"]


def test_two_cross_industry_cases_render_without_leakage(tmp_path: Path) -> None:
    regression = load_script(
        "run_r5_bundle10_cross_industry_writer_regression",
        ROOT / "scripts/run_r5_bundle10_cross_industry_writer_regression.py",
    )
    result = regression.run_regression(
        ROOT / "tests/fixtures/r5_reader_writer/cross_industry_cases.yaml",
        tmp_path,
    )
    assert result["decision"] == "pass"
    assert result["case_count"] == 2
    assert result["distinct_industries"] == 2
    assert result["writer_identity_hardcoding"] is False
    assert result["cross_sample_identity_leakage"] is False
    assert result["fixture_boundary"] == "synthetic_layout_and_schema_regression_only"
    assert result["narrative_quality"]["status"] == "pass"
    assert result["narrative_quality"]["total_duplicate_paragraph_count"] == 0
    assert result["narrative_quality"]["malformed_pattern_hits"] == []
    assert result["narrative_quality"]["prohibited_advice_hits"] == []
    assert result["narrative_quality"]["minimum_unique_section_judgment_count"] == 10
    assert result["narrative_quality"]["total_judgment_restatement_count"] == 0
    for row in result["results"]:
        assert row["narrative_quality"]["status"] == "pass"
        assert row["narrative_quality"]["paragraph_count"] == 10
        assert row["narrative_quality"]["duplicate_paragraph_count"] == 0
        assert row["narrative_quality"]["judgment_restatement_count"] == 0
        report = (tmp_path / f"{row['sample_id']}_reader.md").read_text(encoding="utf-8")
        assert "若若" not in report
        assert "该段仅用于" not in report
