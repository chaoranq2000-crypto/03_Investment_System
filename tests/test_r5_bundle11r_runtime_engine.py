from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from scripts.run_r5_bundle11r_runtime import run_runtime
from src.research.economic_archetypes import load_registry, load_yaml
from src.research.operating_driver_engine import build_operating_driver_pack
from src.research.peer_eligibility import qualify_peers

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def runtime_inputs() -> dict[str, Path]:
    return {
        "registry_path": ROOT / "config/economic_archetype_registry.yaml",
        "runtime_contract_path": ROOT / "config/r5_bundle11r_runtime_contract.yaml",
        "segment_plan_path": ROOT / "templates/r5_segment_driver_plan.example.yaml",
        "evidence_status_path": ROOT / "templates/r5_evidence_status.example.yaml",
        "peer_pack_path": ROOT / "templates/r5_peer_pack.example.yaml",
        "semantic_payload_path": ROOT / "templates/r5_semantic_payload.example.yaml",
        "semantic_config_path": ROOT / "config/r5_bundle11r_semantic_gate.yaml",
    }


def test_runtime_generates_targeted_backflow_from_example(runtime_inputs: dict[str, Path]) -> None:
    result = run_runtime(**runtime_inputs)
    assert result["decision"] == "needs_research_backflow"
    assert result["backflow_plan"]["tasks"]
    assert result["fixed_boundaries"] == {"sample_quality_allowed": False, "p2_allowed": False}


@pytest.mark.parametrize(
    ("ready", "expected_decision", "expected_exit_code"),
    [(False, "needs_research_backflow", 2), (True, "candidate_inputs_ready", 0)],
)
def test_runtime_cli_matches_engine_output_and_exit_code(
    tmp_path: Path,
    runtime_inputs: dict[str, Path],
    ready: bool,
    expected_decision: str,
    expected_exit_code: int,
) -> None:
    if ready:
        registry = load_registry(runtime_inputs["registry_path"])
        plan = load_yaml(runtime_inputs["segment_plan_path"])
        evidence = load_yaml(runtime_inputs["evidence_status_path"])
        for segment in plan["segments"]:
            for driver in registry.get(segment["archetype_id"]).drivers:
                evidence_key = f"{segment['segment_id']}.{driver.driver_id}"
                evidence["evidence_status"][evidence_key] = {
                    "status": "confirmed",
                    "evidence_ids": [f"fixture_{evidence_key}"],
                    "period": "2026E",
                    "confidence": "high",
                }
        evidence_path = tmp_path / "ready_evidence.yaml"
        evidence_path.write_text(yaml.safe_dump(evidence), encoding="utf-8")
        runtime_inputs["evidence_status_path"] = evidence_path

    expected = run_runtime(**runtime_inputs)
    assert expected["decision"] == expected_decision
    output_path = tmp_path / "output" / "runtime.yaml"
    summary_path = tmp_path / "summary.json"
    command = [sys.executable, "-B", str(ROOT / "scripts/run_r5_bundle11r_runtime.py")]
    for option, name in (
        ("--registry", "registry_path"),
        ("--contract", "runtime_contract_path"),
        ("--segment-plan", "segment_plan_path"),
        ("--evidence-status", "evidence_status_path"),
        ("--peer-pack", "peer_pack_path"),
        ("--semantic-payload", "semantic_payload_path"),
        ("--semantic-config", "semantic_config_path"),
    ):
        command.extend([option, str(runtime_inputs[name])])
    command.extend(["--output", str(output_path), "--json-summary", str(summary_path)])
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    assert completed.returncode == expected_exit_code, completed.stderr
    assert load_yaml(output_path) == expected
    assert json.loads(completed.stdout) == json.loads(summary_path.read_text(encoding="utf-8")) == {
        "decision": expected_decision,
        "issues": len(expected["all_issues"]),
        "backflow_tasks": len(expected["backflow_plan"]["tasks"]),
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }


def test_operating_driver_pack_reconciles_and_tracks_proxy_share() -> None:
    registry = load_registry(ROOT / "config/economic_archetype_registry.yaml")
    plan = load_yaml(ROOT / "templates/r5_segment_driver_plan.example.yaml")
    result = build_operating_driver_pack(
        plan,
        registry,
        periods=["2026E", "2027E", "2028E"],
        scenarios=["bear", "base", "bull"],
        maximum_proxy_revenue_share=0.45,
    )
    assert len(result["segments"]) == 27
    assert len(result["consolidated"]) == 9
    base_2026 = next(row for row in result["consolidated"] if row["scenario"] == "base" and row["period"] == "2026E")
    assert 0 < base_2026["proxy_revenue_share"] < 0.45
    assert base_2026["revenue"] > 0


def test_excessive_proxy_share_is_non_compensating_high_issue() -> None:
    registry = load_registry(ROOT / "config/economic_archetype_registry.yaml")
    plan = load_yaml(ROOT / "templates/r5_segment_driver_plan.example.yaml")
    plan = deepcopy(plan)
    proxy = plan["segments"][-1]
    for scenario in proxy["proxy_revenue"]:
        for period in proxy["proxy_revenue"][scenario]:
            proxy["proxy_revenue"][scenario][period] = 10000
    result = build_operating_driver_pack(plan, registry, periods=["2026E"], scenarios=["base"], maximum_proxy_revenue_share=0.45)
    assert result["decision"] == "needs_research_backflow"
    assert any(issue["code"] == "PROXY_REVENUE_SHARE_EXCEEDED" for issue in result["issues"])


def test_peer_eligibility_requires_three_definition_compatible_peers() -> None:
    pack = load_yaml(ROOT / "templates/r5_peer_pack.example.yaml")
    result = qualify_peers(pack)
    assert result["peer_method_eligible"] is True
    degraded = deepcopy(pack)
    degraded["peers"][0]["hard_blocks"] = ["revenue_definition_incompatible"]
    result2 = qualify_peers(degraded)
    assert result2["peer_method_eligible"] is False
    assert result2["decision"].startswith("waive_peer_multiples")
