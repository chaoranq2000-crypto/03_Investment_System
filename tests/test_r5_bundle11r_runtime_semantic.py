from copy import deepcopy
from pathlib import Path

from src.quality.semantic_research_gate import run_semantic_gate
from src.research.economic_archetypes import load_yaml

ROOT = Path(__file__).resolve().parents[1]


def payload_and_config():
    return (
        load_yaml(ROOT / "templates/r5_semantic_payload.example.yaml"),
        load_yaml(ROOT / "config/r5_bundle11r_semantic_gate.yaml"),
    )


def test_supported_semantic_payload_passes() -> None:
    payload, config = payload_and_config()
    payload["model_summary"] = {"proxy_revenue_share": 0.2}
    payload["peer_summary"] = {"peer_multiples_used": True, "eligible_count": 3}
    result = run_semantic_gate(payload, config)
    assert result["decision"] == "candidate_ready"
    assert result["critical_blockers"] == 0
    assert result["high_blockers"] == 0
    assert result["fixed_boundaries"]["sample_quality_allowed"] is False


def test_long_but_generic_section_fails() -> None:
    payload, config = payload_and_config()
    bad = deepcopy(payload)
    section = next(item for item in bad["sections"] if item["section_id"] == "business")
    section["text"] = ("行业需求持续增长，公司有望受益。竞争加剧可能影响毛利率，后续需要观察。" * 80)
    section["company_specific_metrics"] = []
    section["model_links"] = []
    bad["model_summary"] = {"proxy_revenue_share": 0.1}
    bad["peer_summary"] = {"peer_multiples_used": False, "eligible_count": 0}
    result = run_semantic_gate(bad, config)
    assert result["decision"] == "needs_research_backflow"
    codes = {issue["code"] for issue in result["issues"]}
    assert "SECTION_GENERIC" in codes
    assert "SECTION_NO_MODEL_LINK" in codes


def test_non_falsifiable_watchpoint_and_trading_language_fail() -> None:
    payload, config = payload_and_config()
    bad = deepcopy(payload)
    risk = next(item for item in bad["sections"] if item["section_id"] == "risks")
    risk["text"] += " 建议买入并设置目标价。"
    risk["watchpoints"] = [{"metric": "毛利率"}]
    bad["model_summary"] = {"proxy_revenue_share": 0.1}
    bad["peer_summary"] = {"peer_multiples_used": False, "eligible_count": 0}
    result = run_semantic_gate(bad, config)
    codes = {issue["code"] for issue in result["issues"]}
    assert "DIRECT_TRADING_LANGUAGE" in codes
    assert "WATCHPOINT_NOT_FALSIFIABLE" in codes
