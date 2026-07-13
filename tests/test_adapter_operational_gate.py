from pathlib import Path

import yaml

from src.ingest.adapter_contracts import validate_route_adapter_readiness


ROOT = Path(__file__).resolve().parents[1]


def test_enabled_live_routes_do_not_use_offline_snapshot_registrar() -> None:
    routes = yaml.safe_load((ROOT / "config/evidence_source_routes.yaml").read_text(encoding="utf-8"))
    registry = yaml.safe_load((ROOT / "config/adapter_contract_registry.yaml").read_text(encoding="utf-8"))
    issues = validate_route_adapter_readiness(routes, registry)
    assert not any(
        item["issue_id"] == "ADAPTER_NOT_OPERATIONAL"
        and item["adapter"] == "market_snapshot_pull"
        and item["source_name"] in {"mootdx", "tencent_finance"}
        for item in issues
    )
    assert not [item for item in issues if item["severity"] in {"critical", "high"}], issues


def test_planned_adapter_on_enabled_route_fails_closed() -> None:
    routes = {
        "capabilities": {
            "x": {
                "sources": [
                    {"source_name": "s", "role": "primary", "adapter": "planned", "endpoint_hint": "x", "enabled": True}
                ]
            }
        }
    }
    registry = {
        "adapters": {
            "planned": {
                "module": "",
                "entrypoint": "",
                "default_status": "planned",
                "source_bindings": {"s": {"status": "planned", "supported_endpoint_hints": ["x"]}},
            }
        }
    }
    issues = validate_route_adapter_readiness(routes, registry)
    assert [item for item in issues if item["issue_id"] == "ADAPTER_NOT_OPERATIONAL"]
