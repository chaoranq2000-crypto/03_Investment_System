from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from src.ingest.source_health import source_state

ALLOWED_BOUNDARIES = {
    "material_fact",
    "metric_only",
    "contextual_fact",
    "management_comment_only",
    "analyst_view_only",
    "clue_only",
}
ALLOWED_ROLES = {"primary", "fallback"}
BLOCKED_HEALTH_STATES = {"circuit_open", "quarantined"}


@dataclass(frozen=True)
class SourceOption:
    source_name: str
    role: str
    priority: int
    independence_domain: str
    adapter: str
    endpoint_hint: str
    enabled: bool


@dataclass(frozen=True)
class CapabilityRoute:
    capability: str
    claim_boundary: str
    min_independent_domains: int
    require_official_source: bool
    retry_policy: str
    serial_only: bool
    stop_after_first_success: bool
    expected_fields: tuple[str, ...]
    sources: tuple[SourceOption, ...]


@dataclass(frozen=True)
class RouteSelection:
    capability: str
    selected: tuple[SourceOption, ...]
    skipped: tuple[dict[str, str], ...]
    warnings: tuple[str, ...]


def _load_yaml(path: str | Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return payload


def load_source_registry(path: str | Path) -> dict[str, Any]:
    payload = _load_yaml(path)
    if not isinstance(payload.get("sources"), dict):
        raise ValueError("source registry must contain a sources mapping")
    return payload


def load_route_catalog(path: str | Path) -> dict[str, Any]:
    payload = _load_yaml(path)
    if not isinstance(payload.get("capabilities"), dict):
        raise ValueError("route catalog must contain a capabilities mapping")
    return payload


def parse_capability_route(
    catalog: Mapping[str, Any],
    capability: str,
) -> CapabilityRoute:
    capabilities = catalog.get("capabilities", {})
    if capability not in capabilities:
        raise KeyError(f"unknown evidence capability: {capability}")
    defaults = dict(catalog.get("defaults", {}))
    raw_route = dict(capabilities[capability] or {})
    raw_sources = raw_route.get("sources", [])
    sources = tuple(
        SourceOption(
            source_name=str(item["source_name"]),
            role=str(item.get("role", "fallback")),
            priority=int(item.get("priority", 100)),
            independence_domain=str(
                item.get("independence_domain") or item["source_name"]
            ),
            adapter=str(item.get("adapter", "manual_or_snapshot")),
            endpoint_hint=str(item.get("endpoint_hint", "unspecified")),
            enabled=bool(item.get("enabled", True)),
        )
        for item in raw_sources
    )
    return CapabilityRoute(
        capability=capability,
        claim_boundary=str(raw_route.get("claim_boundary", "clue_only")),
        min_independent_domains=int(raw_route.get("min_independent_domains", 1)),
        require_official_source=bool(raw_route.get("require_official_source", False)),
        retry_policy=str(
            raw_route.get("retry_policy", defaults.get("retry_policy", "polite_public_http"))
        ),
        serial_only=bool(raw_route.get("serial_only", defaults.get("serial_only", True))),
        stop_after_first_success=bool(
            raw_route.get(
                "stop_after_first_success",
                defaults.get("stop_after_first_success", True),
            )
        ),
        expected_fields=tuple(str(field) for field in raw_route.get("expected_fields", [])),
        sources=sources,
    )


def _issue(
    severity: str,
    code: str,
    capability: str,
    message: str,
) -> dict[str, str]:
    return {
        "severity": severity,
        "code": code,
        "capability": capability,
        "message": message,
    }


def validate_route_catalog(
    catalog: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    registry_sources = registry.get("sources", {})
    retry_policies = catalog.get("retry_policies", {})

    for capability in catalog.get("capabilities", {}):
        try:
            route = parse_capability_route(catalog, capability)
        except (KeyError, TypeError, ValueError) as exc:
            issues.append(_issue("critical", "ROUTE_PARSE_FAILED", capability, str(exc)))
            continue

        if route.claim_boundary not in ALLOWED_BOUNDARIES:
            issues.append(
                _issue(
                    "critical",
                    "INVALID_CLAIM_BOUNDARY",
                    capability,
                    f"unsupported claim boundary: {route.claim_boundary}",
                )
            )
        if route.retry_policy not in retry_policies:
            issues.append(
                _issue(
                    "high",
                    "UNKNOWN_RETRY_POLICY",
                    capability,
                    f"retry policy is not defined: {route.retry_policy}",
                )
            )
        if not route.sources:
            issues.append(
                _issue("critical", "NO_ROUTE_SOURCES", capability, "route has no sources")
            )
            continue

        seen_priorities: set[int] = set()
        enabled_domains: set[str] = set()
        enabled_official_sources = 0
        enabled_sources = 0

        for option in route.sources:
            if option.role not in ALLOWED_ROLES:
                issues.append(
                    _issue(
                        "high",
                        "INVALID_SOURCE_ROLE",
                        capability,
                        f"{option.source_name}: invalid role {option.role}",
                    )
                )
            if option.priority in seen_priorities:
                issues.append(
                    _issue(
                        "high",
                        "DUPLICATE_PRIORITY",
                        capability,
                        f"priority {option.priority} is duplicated",
                    )
                )
            seen_priorities.add(option.priority)

            source = registry_sources.get(option.source_name)
            if source is None:
                issues.append(
                    _issue(
                        "critical",
                        "UNKNOWN_SOURCE",
                        capability,
                        f"source is absent from source_registry.yaml: {option.source_name}",
                    )
                )
                continue
            if not option.enabled:
                continue

            enabled_sources += 1
            enabled_domains.add(option.independence_domain)
            source_group = str(source.get("source_group", ""))
            if source_group == "official_disclosure":
                enabled_official_sources += 1

            material_permission = source.get("material_claim_allowed", False)
            if route.claim_boundary == "material_fact" and material_permission is not True:
                issues.append(
                    _issue(
                        "critical",
                        "MATERIAL_ROUTE_USES_NON_MATERIAL_SOURCE",
                        capability,
                        f"{option.source_name} cannot directly support material facts",
                    )
                )
            if route.claim_boundary == "metric_only" and source_group in {"clue"}:
                issues.append(
                    _issue(
                        "high",
                        "METRIC_ROUTE_USES_CLUE_SOURCE",
                        capability,
                        f"{option.source_name} is clue-only but is enabled for metrics",
                    )
                )

        if enabled_sources == 0:
            issues.append(
                _issue(
                    "critical",
                    "NO_ENABLED_SOURCE",
                    capability,
                    "route has no enabled source",
                )
            )
        if len(enabled_domains) < route.min_independent_domains:
            issues.append(
                _issue(
                    "high",
                    "INSUFFICIENT_INDEPENDENT_FALLBACKS",
                    capability,
                    (
                        f"requires {route.min_independent_domains} independent domains, "
                        f"found {len(enabled_domains)}"
                    ),
                )
            )
        if route.require_official_source and enabled_official_sources == 0:
            issues.append(
                _issue(
                    "critical",
                    "OFFICIAL_SOURCE_REQUIRED",
                    capability,
                    "route requires an enabled official disclosure source",
                )
            )

    return issues


def select_sources(
    catalog: Mapping[str, Any],
    registry: Mapping[str, Any],
    capability: str,
    *,
    health_ledger: Mapping[str, Any] | None = None,
) -> RouteSelection:
    del registry  # registry validation is performed before selection
    route = parse_capability_route(catalog, capability)
    health = health_ledger or {"sources": {}}
    selected: list[SourceOption] = []
    skipped: list[dict[str, str]] = []
    warnings: list[str] = []

    for option in sorted(route.sources, key=lambda item: item.priority):
        if not option.enabled:
            skipped.append(
                {"source_name": option.source_name, "reason": "disabled_or_planned"}
            )
            continue
        state = source_state(health, option.source_name)
        if state in BLOCKED_HEALTH_STATES:
            skipped.append(
                {"source_name": option.source_name, "reason": f"health_{state}"}
            )
            continue
        if state == "degraded":
            warnings.append(f"{option.source_name} is degraded; retain fallback coverage")
        selected.append(option)

    if not selected:
        warnings.append(f"no usable source remains for capability {capability}")
    return RouteSelection(
        capability=capability,
        selected=tuple(selected),
        skipped=tuple(skipped),
        warnings=tuple(warnings),
    )


def enabled_capabilities(catalog: Mapping[str, Any]) -> Sequence[str]:
    return tuple(str(name) for name in catalog.get("capabilities", {}).keys())
