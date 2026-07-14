from copy import deepcopy
from pathlib import Path

from src.research.economic_archetypes import load_registry, load_yaml
from src.research.operating_driver_engine import build_operating_driver_pack
from src.research.peer_eligibility import qualify_peers

ROOT = Path(__file__).resolve().parents[1]


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
