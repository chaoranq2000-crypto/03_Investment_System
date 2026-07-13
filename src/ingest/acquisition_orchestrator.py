from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import yaml

from src.ingest.source_health import (
    load_health_ledger,
    record_failure,
    record_success,
    save_health_ledger,
)
from src.ingest.source_routing import (
    load_route_catalog,
    load_source_registry,
    parse_capability_route,
    select_sources,
    validate_route_catalog,
)


@dataclass(frozen=True)
class AdapterResult:
    success: bool
    source_name: str
    capability: str
    fields: tuple[str, ...] = ()
    http_status: int | None = None
    raw_snapshot_path: str | None = None
    error_class: str | None = None
    message: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_yaml(path: str | Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return payload


def _required_capabilities(request_plan: Mapping[str, Any]) -> list[str]:
    explicit = request_plan.get("required_capabilities")
    if isinstance(explicit, list):
        return [str(item) for item in explicit]
    outputs = request_plan.get("required_outputs", [])
    output_to_capability = {
        "official_disclosures": "official_disclosures",
        "financial_metric_pack": "financial_statements",
        "financial_indicator_pack": "financial_indicators",
        "company_identity_pack": "security_master",
        "valuation_snapshot": "valuation_snapshot",
        "technical_snapshot": "technical_history",
        "market_sentiment_pack": "fund_flow_context",
        "industry_evidence_pack": "industry_policy",
        "research_report_inventory": "research_metadata",
        "news_clue_log": "news_clues",
        "investor_relations_pack": "investor_relations",
    }
    return [output_to_capability[item] for item in outputs if item in output_to_capability]


def build_adapter_run_queue(
    *,
    request_plan: Mapping[str, Any],
    route_catalog: Mapping[str, Any],
    source_registry: Mapping[str, Any],
    health_ledger: Mapping[str, Any] | None = None,
    mode: str = "dry_run",
) -> dict[str, Any]:
    if mode not in {"dry_run", "live"}:
        raise ValueError("mode must be dry_run or live")
    route_issues = validate_route_catalog(route_catalog, source_registry)
    blocking = [item for item in route_issues if item["severity"] in {"critical", "high"}]
    if blocking:
        raise ValueError(f"source route catalog has blocking issues: {blocking}")

    registry_sources = source_registry["sources"]
    queue: list[dict[str, Any]] = []
    blocked_capabilities: list[dict[str, Any]] = []
    warnings: list[str] = []
    request_id = str(request_plan.get("request_id", "request_unspecified"))

    for capability in _required_capabilities(request_plan):
        route = parse_capability_route(route_catalog, capability)
        selection = select_sources(
            route_catalog,
            source_registry,
            capability,
            health_ledger=health_ledger,
        )
        warnings.extend(selection.warnings)
        if not selection.selected:
            blocked_capabilities.append(
                {
                    "capability": capability,
                    "reason": "no_usable_source",
                    "skipped": list(selection.skipped),
                }
            )
            continue

        planned_options: list[tuple[Any, int, bool]] = [
            (option, option.priority, False) for option in selection.selected
        ]
        if mode == "dry_run":
            # Disabled sources may opt into an isolated schema probe.  The
            # probe exercises fallback and quarantine logic without making
            # the source eligible for live routing or operational readiness.
            probes = [
                option
                for option in route.sources
                if not option.enabled and option.dry_run_probe
            ]
            for probe_index, option in enumerate(
                sorted(probes, key=lambda item: item.priority)
            ):
                planned_options.append((option, -100 + probe_index, True))

        for index, (option, effective_priority, diagnostic_probe) in enumerate(
            sorted(planned_options, key=lambda item: item[1]), start=1
        ):
            source = registry_sources[option.source_name]
            queue.append(
                {
                    "queue_id": f"{request_id}__{capability}__{index:02d}",
                    "request_id": request_id,
                    "capability": capability,
                    "source_name": option.source_name,
                    "source_group": source.get("source_group"),
                    "role": "diagnostic_probe" if diagnostic_probe else option.role,
                    "priority": effective_priority,
                    "configured_priority": option.priority,
                    "diagnostic_probe": diagnostic_probe,
                    "independence_domain": option.independence_domain,
                    "adapter": option.adapter,
                    "endpoint_hint": option.endpoint_hint,
                    "claim_boundary": route.claim_boundary,
                    "retry_policy": route.retry_policy,
                    "serial_only": route.serial_only,
                    "stop_after_first_success": route.stop_after_first_success,
                    "expected_fields": list(route.expected_fields),
                    "raw_archive_policy": source.get("raw_archive_policy_default"),
                    "manual_review_required": source.get("manual_review_required", True),
                    "execution_mode": mode,
                    "status": "planned",
                }
            )

    return {
        "schema_version": 1,
        "generated_at": _now_iso(),
        "request_id": request_id,
        "mode": mode,
        "queue": queue,
        "blocked_capabilities": blocked_capabilities,
        "warnings": sorted(set(warnings)),
        "route_issue_count": len(route_issues),
    }


def execute_adapter_run_queue(
    queue_payload: Mapping[str, Any],
    *,
    executor: Callable[[Mapping[str, Any]], AdapterResult],
    health_ledger: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Execute a queue with source fallback and schema-drift protection.

    The executor is injected by the source-specific adapter layer. This module never writes
    report claims. It only records acquisition outcomes and leaves raw snapshots for normal
    manifest/candidate processing.
    """

    ledger = dict(health_ledger or {"schema_version": 1, "sources": {}, "events": []})
    run_results: list[dict[str, Any]] = []
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for task in queue_payload.get("queue", []):
        grouped.setdefault(str(task["capability"]), []).append(task)

    capability_results: list[dict[str, Any]] = []
    for capability, tasks in grouped.items():
        success = False
        used_source: str | None = None
        attempts = 0
        for task in sorted(tasks, key=lambda item: int(item.get("priority", 100))):
            attempts += 1
            result = executor(task)
            expected_fields = {str(field) for field in task.get("expected_fields", [])}
            actual_fields = {str(field) for field in result.fields}
            missing_fields = sorted(expected_fields - actual_fields)

            if result.success and missing_fields:
                result = AdapterResult(
                    success=False,
                    source_name=result.source_name,
                    capability=result.capability,
                    fields=result.fields,
                    http_status=result.http_status,
                    raw_snapshot_path=result.raw_snapshot_path,
                    error_class="schema_drift",
                    message=f"missing expected fields: {missing_fields}",
                )

            if result.success:
                ledger = record_success(
                    ledger,
                    source_name=result.source_name,
                    capability=capability,
                    fields=result.fields,
                    http_status=result.http_status,
                )
                success = True
                used_source = result.source_name
            else:
                ledger = record_failure(
                    ledger,
                    source_name=result.source_name,
                    capability=capability,
                    http_status=result.http_status,
                    error_class=result.error_class,
                    message=result.message,
                )

            result_payload = asdict(result)
            result_payload["missing_expected_fields"] = missing_fields
            run_results.append(result_payload)
            if success and bool(task.get("stop_after_first_success", True)):
                break

        capability_results.append(
            {
                "capability": capability,
                "success": success,
                "used_source": used_source,
                "source_attempts": attempts,
            }
        )

    result_payload = {
        "schema_version": 1,
        "completed_at": _now_iso(),
        "request_id": queue_payload.get("request_id"),
        "capability_results": capability_results,
        "adapter_results": run_results,
        "success": all(item["success"] for item in capability_results),
    }
    return result_payload, ledger


def write_yaml(path: str | Path, payload: Mapping[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(dict(payload), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def build_queue_from_files(
    *,
    request_path: str | Path,
    routes_path: str | Path,
    registry_path: str | Path,
    health_path: str | Path | None,
    output_path: str | Path,
    mode: str,
) -> dict[str, Any]:
    request_plan = _load_yaml(request_path)
    route_catalog = load_route_catalog(routes_path)
    source_registry = load_source_registry(registry_path)
    health_ledger = load_health_ledger(health_path)
    queue = build_adapter_run_queue(
        request_plan=request_plan,
        route_catalog=route_catalog,
        source_registry=source_registry,
        health_ledger=health_ledger,
        mode=mode,
    )
    write_yaml(output_path, queue)
    if health_path is not None and not Path(health_path).exists():
        save_health_ledger(health_path, health_ledger)
    return queue
