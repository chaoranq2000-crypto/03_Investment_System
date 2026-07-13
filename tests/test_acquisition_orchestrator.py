from __future__ import annotations

from pathlib import Path

from src.ingest.acquisition_orchestrator import (
    AdapterResult,
    build_adapter_run_queue,
    execute_adapter_run_queue,
)
from src.ingest.source_health import empty_health_ledger
from src.ingest.source_routing import load_route_catalog, load_source_registry

ROOT = Path(__file__).resolve().parents[1]


def test_build_queue_is_dry_run_by_default_and_preserves_claim_boundary() -> None:
    request = {
        "request_id": "REQ_TEST",
        "required_capabilities": ["official_disclosures", "technical_history"],
    }
    queue = build_adapter_run_queue(
        request_plan=request,
        route_catalog=load_route_catalog(ROOT / "config/evidence_source_routes.yaml"),
        source_registry=load_source_registry(ROOT / "config/source_registry.yaml"),
        health_ledger=empty_health_ledger(),
    )
    assert queue["mode"] == "dry_run"
    assert not queue["blocked_capabilities"]
    official_tasks = [
        item for item in queue["queue"] if item["capability"] == "official_disclosures"
    ]
    assert official_tasks[0]["claim_boundary"] == "material_fact"
    assert official_tasks[0]["source_name"] == "cninfo"


def test_schema_drift_falls_back_to_next_independent_source() -> None:
    request = {
        "request_id": "REQ_DRIFT",
        "required_capabilities": ["daily_price"],
    }
    queue = build_adapter_run_queue(
        request_plan=request,
        route_catalog=load_route_catalog(ROOT / "config/evidence_source_routes.yaml"),
        source_registry=load_source_registry(ROOT / "config/source_registry.yaml"),
        health_ledger=empty_health_ledger(),
    )

    def executor(task: dict) -> AdapterResult:
        if task["source_name"] == "mootdx":
            return AdapterResult(
                success=True,
                source_name="mootdx",
                capability="daily_price",
                fields=("trade_date", "close"),
                http_status=200,
            )
        return AdapterResult(
            success=True,
            source_name=task["source_name"],
            capability="daily_price",
            fields=("trade_date", "open", "high", "low", "close", "volume"),
            http_status=200,
        )

    result, ledger = execute_adapter_run_queue(
        queue,
        executor=executor,
        health_ledger=empty_health_ledger(),
    )
    assert result["success"]
    assert result["capability_results"][0]["used_source"] == "tencent_finance"
    assert ledger["sources"]["mootdx"]["last_error_class"] == "schema_drift"
