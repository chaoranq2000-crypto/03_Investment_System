from pathlib import Path

from src.research.r5_bundle11r_runtime import run_runtime

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_generates_targeted_backflow_from_example() -> None:
    result = run_runtime(
        registry_path=ROOT / "config/economic_archetype_registry.yaml",
        runtime_contract_path=ROOT / "config/r5_bundle11r_runtime_contract.yaml",
        segment_plan_path=ROOT / "templates/r5_segment_driver_plan.example.yaml",
        evidence_status_path=ROOT / "templates/r5_evidence_status.example.yaml",
        peer_pack_path=ROOT / "templates/r5_peer_pack.example.yaml",
        semantic_payload_path=ROOT / "templates/r5_semantic_payload.example.yaml",
        semantic_config_path=ROOT / "config/r5_bundle11r_semantic_gate.yaml",
    )
    assert result["decision"] == "needs_research_backflow"
    assert result["backflow_plan"]["tasks"]
    assert result["fixed_boundaries"] == {"sample_quality_allowed": False, "p2_allowed": False}
