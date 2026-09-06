from pathlib import Path

import csv
import io
import yaml
import pytest

# Published historical results; current algorithms are covered in the default suite.
pytestmark = pytest.mark.legacy_compatibility


REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_RUN = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def historical_yaml(historical_blob_bytes, name: str):
    return yaml.safe_load(historical_blob_bytes(f"{HISTORICAL_RUN}/{name}").decode("utf-8"))


def historical_csv(historical_blob_bytes, name: str) -> list[dict[str, str]]:
    text = historical_blob_bytes(f"{HISTORICAL_RUN}/{name}").decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def test_bundle9_valuation_inputs_replace_todo_placeholders(
    historical_blob_bytes,
) -> None:
    market = historical_csv(historical_blob_bytes, "market_snapshot.csv")[0]
    peers = historical_csv(historical_blob_bytes, "peer_market_snapshot.csv")
    assert market["snapshot_status"] == "reviewed"
    assert float(market["market_cap"]) == 93_715_669_584.0
    assert market["source_evidence_id"] == "ev_structured_market_data_002837_20260713_f8cc52"
    assert len(peers) == 4
    assert all(row["confidence"] == "low_confidence_fixture" for row in peers)


def test_bundle9_scenario_and_reverse_values_reconcile(historical_blob_bytes) -> None:
    scenario = historical_yaml(historical_blob_bytes, "scenario_valuation.yaml")
    reverse = historical_yaml(historical_blob_bytes, "reverse_valuation.yaml")
    base = scenario["scenarios"]["base"]
    profit = base["profit_anchor"]["value"]
    assert base["implied_market_cap_range"]["low"]["value"] == round(profit * 75.0, 2)
    assert base["implied_market_cap_range"]["high"]["value"] == round(profit * 100.0, 2)
    threshold_100 = next(row for row in reverse["thresholds"] if row["multiple"]["value"] == 100.0)
    assert threshold_100["required_net_profit"]["value"] == round(93_715_669_584.0 / 100.0, 2)


def test_bundle9_valuation_outputs_keep_method_and_language_boundaries(
    historical_blob_bytes,
) -> None:
    pack = historical_yaml(historical_blob_bytes, "R5_bundle9_valuation_pack.yaml")
    handoff = historical_yaml(
        historical_blob_bytes, "valuation/R5_valuation_handoff.yaml"
    )
    readout = historical_yaml(
        historical_blob_bytes, "R5_bundle9_valuation_build_readout.yaml"
    )
    assert pack["status"] == "partial"
    assert pack["sample_quality_allowed"] is False
    assert handoff["sample_quality_allowed"] is False
    assert readout["methods_skipped"]["dcf"]
    assert readout["methods_skipped"]["sotp"]
    names = [
        "R5_bundle9_valuation_input_registry.yaml",
        "R5_bundle9_valuation_pack.yaml",
        "reverse_valuation.yaml",
        "scenario_valuation.yaml",
        "valuation/valuation_output.yaml",
        "valuation/R5_valuation_handoff.yaml",
        "valuation/valuation_section_draft.md",
    ]
    text = "\n".join(
        historical_blob_bytes(f"{HISTORICAL_RUN}/{name}").decode("utf-8")
        for name in names
    )
    for token in ("买入", "卖出", "持有", "目标价", "仓位", "保证收益"):
        assert token not in text
