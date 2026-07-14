from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


class ContractError(ValueError):
    """Raised when a Bundle 11R runtime contract is invalid."""


@dataclass(frozen=True)
class DriverSpec:
    driver_id: str
    unit: str
    required: bool = True
    lower_bound: float | None = None
    upper_bound: float | None = None
    description: str = ""

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "DriverSpec":
        driver_id = str(raw.get("driver_id", "")).strip()
        unit = str(raw.get("unit", "")).strip()
        if not driver_id or not unit:
            raise ContractError("driver requires non-empty driver_id and unit")
        return cls(
            driver_id=driver_id,
            unit=unit,
            required=bool(raw.get("required", True)),
            lower_bound=_maybe_float(raw.get("lower_bound")),
            upper_bound=_maybe_float(raw.get("upper_bound")),
            description=str(raw.get("description", "")).strip(),
        )


@dataclass(frozen=True)
class ArchetypeSpec:
    archetype_id: str
    equation: str
    drivers: tuple[DriverSpec, ...]
    output_unit: str = "currency"
    financial_mapping: Mapping[str, str] = field(default_factory=dict)
    allowed_method_tiers: tuple[str, ...] = ("bottom_up", "hybrid")
    notes: str = ""

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ArchetypeSpec":
        archetype_id = str(raw.get("archetype_id", "")).strip()
        equation = str(raw.get("equation", "")).strip()
        if not archetype_id or not equation:
            raise ContractError("archetype requires archetype_id and equation")
        drivers = tuple(DriverSpec.from_mapping(item) for item in raw.get("drivers", []))
        if not drivers:
            raise ContractError(f"archetype {archetype_id} has no drivers")
        tiers = tuple(str(x) for x in raw.get("allowed_method_tiers", ["bottom_up", "hybrid"]))
        return cls(
            archetype_id=archetype_id,
            equation=equation,
            drivers=drivers,
            output_unit=str(raw.get("output_unit", "currency")),
            financial_mapping=dict(raw.get("financial_mapping", {})),
            allowed_method_tiers=tiers,
            notes=str(raw.get("notes", "")).strip(),
        )


@dataclass(frozen=True)
class ArchetypeRegistry:
    registry_id: str
    version: int
    archetypes: Mapping[str, ArchetypeSpec]

    def get(self, archetype_id: str) -> ArchetypeSpec:
        try:
            return self.archetypes[archetype_id]
        except KeyError as exc:
            raise ContractError(f"unknown archetype_id: {archetype_id}") from exc


def _maybe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"expected numeric value, got {value!r}") from exc


def load_yaml(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(target)
    raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ContractError(f"YAML root must be a mapping: {target}")
    return raw


def load_registry(path: str | Path) -> ArchetypeRegistry:
    raw = load_yaml(path)
    registry_id = str(raw.get("registry_id", "")).strip()
    version = int(raw.get("schema_version", 0))
    if not registry_id or version < 1:
        raise ContractError("registry requires registry_id and schema_version >= 1")
    specs = [ArchetypeSpec.from_mapping(item) for item in raw.get("archetypes", [])]
    by_id = {spec.archetype_id: spec for spec in specs}
    if len(by_id) != len(specs):
        raise ContractError("duplicate archetype_id in registry")
    if not by_id:
        raise ContractError("registry contains no archetypes")
    return ArchetypeRegistry(registry_id=registry_id, version=version, archetypes=by_id)


def validate_segment_plan(
    plan: Mapping[str, Any],
    registry: ArchetypeRegistry,
    *,
    periods: Iterable[str] | None = None,
    scenarios: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Validate business-line archetype assignment without inventing missing evidence."""
    issues: list[dict[str, Any]] = []
    segments = plan.get("segments", [])
    if not isinstance(segments, list) or not segments:
        return [_issue("SEGMENT_PLAN_EMPTY", "critical", "segments", "no business lines defined")]

    seen: set[str] = set()
    expected_periods = set(periods or [])
    expected_scenarios = set(scenarios or [])
    for index, segment in enumerate(segments):
        if not isinstance(segment, Mapping):
            issues.append(_issue("SEGMENT_NOT_MAPPING", "critical", f"segments[{index}]", "segment must be a mapping"))
            continue
        segment_id = str(segment.get("segment_id", "")).strip()
        path = f"segments[{index}]"
        if not segment_id:
            issues.append(_issue("SEGMENT_ID_MISSING", "critical", path, "segment_id is required"))
            continue
        if segment_id in seen:
            issues.append(_issue("SEGMENT_ID_DUPLICATE", "critical", path, segment_id))
        seen.add(segment_id)
        archetype_id = str(segment.get("archetype_id", "")).strip()
        method_tier = str(segment.get("method_tier", "")).strip()
        try:
            spec = registry.get(archetype_id)
        except ContractError as exc:
            issues.append(_issue("ARCHETYPE_UNKNOWN", "critical", path, str(exc), segment_id=segment_id))
            continue
        if method_tier not in {"bottom_up", "hybrid", "proxy"}:
            issues.append(_issue("METHOD_TIER_INVALID", "critical", path, method_tier, segment_id=segment_id))
        if method_tier != "proxy" and method_tier not in spec.allowed_method_tiers:
            issues.append(_issue("METHOD_TIER_NOT_ALLOWED", "high", path, method_tier, segment_id=segment_id))

        driver_values = segment.get("driver_values", {})
        if not isinstance(driver_values, Mapping):
            issues.append(_issue("DRIVER_VALUES_INVALID", "critical", path, "driver_values must be a mapping", segment_id=segment_id))
            continue
        if method_tier != "proxy":
            for driver in spec.drivers:
                if driver.required and driver.driver_id not in driver_values:
                    issues.append(_issue("REQUIRED_DRIVER_MISSING", "high", path, driver.driver_id, segment_id=segment_id))
        if method_tier == "proxy" and not segment.get("proxy_reason"):
            issues.append(_issue("PROXY_REASON_MISSING", "high", path, "proxy_reason is required", segment_id=segment_id))

        if expected_periods or expected_scenarios:
            for driver_id, matrix in driver_values.items():
                if not isinstance(matrix, Mapping):
                    issues.append(_issue("DRIVER_MATRIX_INVALID", "high", f"{path}.driver_values.{driver_id}", "expected scenario mapping", segment_id=segment_id))
                    continue
                if expected_scenarios and not expected_scenarios.issubset(matrix.keys()):
                    missing = sorted(expected_scenarios.difference(matrix.keys()))
                    issues.append(_issue("DRIVER_SCENARIO_MISSING", "high", f"{path}.driver_values.{driver_id}", ",".join(missing), segment_id=segment_id))
                for scenario, by_period in matrix.items():
                    if not isinstance(by_period, Mapping):
                        issues.append(_issue("DRIVER_PERIOD_MATRIX_INVALID", "high", f"{path}.driver_values.{driver_id}.{scenario}", "expected period mapping", segment_id=segment_id))
                    elif expected_periods and not expected_periods.issubset(by_period.keys()):
                        missing = sorted(expected_periods.difference(by_period.keys()))
                        issues.append(_issue("DRIVER_PERIOD_MISSING", "high", f"{path}.driver_values.{driver_id}.{scenario}", ",".join(missing), segment_id=segment_id))
    return issues


def _issue(code: str, severity: str, path: str, message: str, **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"code": code, "severity": severity, "path": path, "message": message}
    result.update(extra)
    return result
