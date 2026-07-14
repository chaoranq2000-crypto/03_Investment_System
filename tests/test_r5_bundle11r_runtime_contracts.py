from pathlib import Path

from src.research.economic_archetypes import load_registry, load_yaml, validate_segment_plan
from src.research.research_question_planner import build_research_question_matrix

ROOT = Path(__file__).resolve().parents[1]


def test_registry_and_example_segment_plan_validate() -> None:
    registry = load_registry(ROOT / "config/economic_archetype_registry.yaml")
    plan = load_yaml(ROOT / "templates/r5_segment_driver_plan.example.yaml")
    issues = validate_segment_plan(plan, registry, periods=["2026E", "2027E", "2028E"], scenarios=["bear", "base", "bull"])
    assert not [issue for issue in issues if issue["severity"] == "critical"]
    assert len(registry.archetypes) >= 7


def test_question_matrix_exposes_missing_critical_evidence() -> None:
    registry = load_registry(ROOT / "config/economic_archetype_registry.yaml")
    plan = load_yaml(ROOT / "templates/r5_segment_driver_plan.example.yaml")
    evidence = load_yaml(ROOT / "templates/r5_evidence_status.example.yaml")
    matrix = build_research_question_matrix(plan, registry, evidence["evidence_status"])
    assert matrix["decision"] == "research_backflow_required"
    assert matrix["summary"]["critical_open"] >= 1
    assert any(q["status"] == "missing" and q["owner_skill"] == "evidence-ingest" for q in matrix["questions"])
