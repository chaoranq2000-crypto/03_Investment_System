from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

from src.research.r5_bundle11r_runtime import run_runtime


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_r5_bundle11r_002837_inputs.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_r5_bundle11r_002837_inputs", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_002837_inputs_are_real_source_bound_and_runtime_ready(tmp_path: Path) -> None:
    builder = _load_builder()
    builder.build_inputs(ROOT, tmp_path)

    plan = yaml.safe_load((tmp_path / "R5_bundle11r_segment_driver_plan.yaml").read_text(encoding="utf-8"))
    assert [segment["method_tier"] for segment in plan["segments"]] == ["hybrid", "hybrid", "proxy"]
    assert plan["operating_model_boundary"]["liquid_cooling_standalone_revenue"] == "MISSING_DISCLOSURE"

    result = run_runtime(
        registry_path=ROOT / "config/economic_archetype_registry.yaml",
        runtime_contract_path=ROOT / "config/r5_bundle11r_runtime_contract.yaml",
        segment_plan_path=tmp_path / "R5_bundle11r_segment_driver_plan.yaml",
        evidence_status_path=tmp_path / "R5_bundle11r_evidence_status.yaml",
        peer_pack_path=tmp_path / "R5_bundle11r_peer_pack.yaml",
        semantic_payload_path=tmp_path / "R5_bundle11r_semantic_payload.yaml",
        semantic_config_path=ROOT / "config/r5_bundle11r_semantic_gate.yaml",
    )
    assert result["decision"] == "candidate_inputs_ready"
    assert result["research_question_matrix"]["summary"]["critical_open"] == 0
    assert result["peer_eligibility"]["peer_method_eligible"] is False
    assert result["peer_eligibility"]["decision"] == "context_only"
    assert max(row["proxy_revenue_share"] for row in result["operating_driver_pack"]["consolidated"]) < 0.45
    assert not [issue for issue in result["all_issues"] if issue.get("severity") in {"critical", "high"}]


def test_operating_metric_candidate_keeps_company_scope(tmp_path: Path) -> None:
    builder = _load_builder()
    builder.build_inputs(ROOT, tmp_path)
    row = builder.metric_candidate_row()
    assert row["source_evidence_id"] == "ev_annual_report_002837_20260421_2cbfc5"
    assert row["value"] == "324058"
    assert row["is_reported"] == "true"
    assert "不得直接解释为液冷" in row["notes"]
