from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_reader_and_gate_contracts_are_separate_and_fixed():
    reader = (ROOT / ".agents/skills/stock-deep-dive/references/r5_reader_facing_report_contract.md").read_text(encoding="utf-8")
    gate = (ROOT / ".agents/skills/quality-review/references/r5_reader_quality_gate_contract.md").read_text(encoding="utf-8")
    assert "traceability_appendix" in reader
    assert "candidate_ready_for_human_review" in gate
    assert "sample_quality_report_allowed=false" in reader
    assert "p2_allowed=false" in reader


def test_rubric_is_executable_and_totals_100():
    rubric = yaml.safe_load((ROOT / "config/r5_reader_quality_rubric.yaml").read_text(encoding="utf-8"))
    assert sum(rubric["dimensions"].values()) == 100
    assert rubric["candidate_threshold"] == 82
    assert rubric["human_review_status"] == "pending"
    assert not rubric["sample_quality_report_allowed"]
    assert not rubric["p2_allowed"]
    assert len(rubric["required_sections"]) == 9
