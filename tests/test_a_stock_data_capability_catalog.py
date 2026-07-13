from pathlib import Path

import yaml

from src.ingest.capability_coverage import build_coverage_report, validate_catalog


ROOT = Path(__file__).resolve().parents[1]


def test_all_43_upstream_capability_groups_are_accounted_for() -> None:
    catalog = yaml.safe_load((ROOT / "config/a_stock_data_capability_catalog.yaml").read_text(encoding="utf-8"))
    assert validate_catalog(catalog) == []
    capabilities = catalog["capabilities"]
    assert len(capabilities) == 43
    assert sum(item["upstream_layer"] != "fallback" for item in capabilities) == 40
    assert sum(item["upstream_layer"] == "fallback" for item in capabilities) == 3
    assert all(item["adoption_decision"] for item in capabilities)


def test_completed_forward_requalification_has_no_core_blocker() -> None:
    catalog = yaml.safe_load((ROOT / "config/a_stock_data_capability_catalog.yaml").read_text(encoding="utf-8"))
    report = build_coverage_report(catalog)
    assert report["decision"] == "pass"
    assert report["bundle8r_core_blocker_count"] == 0
    assert report["bundle8r_core_operational_count"] == report["bundle8r_core_count"]
    assert report["bundle8r_core_alternative_count"] == 2
