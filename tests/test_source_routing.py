from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml

from src.ingest.source_health import empty_health_ledger, record_failure
from src.ingest.source_routing import (
    load_route_catalog,
    load_source_registry,
    select_sources,
    validate_route_catalog,
)

ROOT = Path(__file__).resolve().parents[1]


def _catalog() -> dict:
    return load_route_catalog(ROOT / "config/evidence_source_routes.yaml")


def _registry() -> dict:
    return load_source_registry(ROOT / "config/source_registry.yaml")


def test_repository_route_catalog_has_no_blocking_issues() -> None:
    issues = validate_route_catalog(_catalog(), _registry())
    assert not [item for item in issues if item["severity"] in {"critical", "high"}]


def test_health_quarantine_moves_selection_to_independent_fallback() -> None:
    ledger = record_failure(
        empty_health_ledger(),
        source_name="mootdx",
        capability="daily_price",
        http_status=403,
    )
    selection = select_sources(
        _catalog(),
        _registry(),
        "daily_price",
        health_ledger=ledger,
    )
    assert selection.selected[0].source_name == "tencent_finance"
    assert any(item["source_name"] == "mootdx" for item in selection.skipped)


def test_material_fact_route_rejects_metric_only_source() -> None:
    catalog = deepcopy(_catalog())
    catalog["capabilities"]["official_disclosures"]["sources"][0][
        "source_name"
    ] = "tushare"
    issues = validate_route_catalog(catalog, _registry())
    codes = {item["code"] for item in issues}
    assert "MATERIAL_ROUTE_USES_NON_MATERIAL_SOURCE" in codes


def test_route_catalog_is_valid_yaml_fixture() -> None:
    payload = yaml.safe_load(
        (ROOT / "config/evidence_source_routes.yaml").read_text(encoding="utf-8")
    )
    assert payload["schema_version"] == 1
    assert "technical_history" in payload["capabilities"]
