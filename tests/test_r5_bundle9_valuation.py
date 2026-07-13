from pathlib import Path

import csv
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
RUN = REPO_ROOT / "reports/workflow_runs/wf_20260703_stock_first_002837_invic"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_bundle9_valuation_inputs_replace_todo_placeholders() -> None:
    with (RUN / "market_snapshot.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        market = next(csv.DictReader(handle))
    with (RUN / "peer_market_snapshot.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        peers = list(csv.DictReader(handle))
    assert market["snapshot_status"] == "reviewed"
    assert float(market["market_cap"]) == 93_715_669_584.0
    assert market["source_evidence_id"] == "ev_structured_market_data_002837_20260713_f8cc52"
    assert len(peers) == 4
    assert all(row["confidence"] == "low_confidence_fixture" for row in peers)


def test_bundle9_scenario_and_reverse_values_reconcile() -> None:
    scenario = load_yaml(RUN / "scenario_valuation.yaml")
    reverse = load_yaml(RUN / "reverse_valuation.yaml")
    base = scenario["scenarios"]["base"]
    profit = base["profit_anchor"]["value"]
    assert base["implied_market_cap_range"]["low"]["value"] == round(profit * 75.0, 2)
    assert base["implied_market_cap_range"]["high"]["value"] == round(profit * 100.0, 2)
    threshold_100 = next(row for row in reverse["thresholds"] if row["multiple"]["value"] == 100.0)
    assert threshold_100["required_net_profit"]["value"] == round(93_715_669_584.0 / 100.0, 2)


def test_bundle9_valuation_outputs_keep_method_and_language_boundaries() -> None:
    pack = load_yaml(RUN / "R5_bundle9_valuation_pack.yaml")
    handoff = load_yaml(RUN / "valuation/R5_valuation_handoff.yaml")
    readout = load_yaml(RUN / "R5_bundle9_valuation_build_readout.yaml")
    assert pack["status"] == "partial"
    assert pack["sample_quality_allowed"] is False
    assert handoff["sample_quality_allowed"] is False
    assert readout["methods_skipped"]["dcf"]
    assert readout["methods_skipped"]["sotp"]
    paths = [
        RUN / "R5_bundle9_valuation_input_registry.yaml",
        RUN / "R5_bundle9_valuation_pack.yaml",
        RUN / "reverse_valuation.yaml",
        RUN / "scenario_valuation.yaml",
        RUN / "valuation/valuation_output.yaml",
        RUN / "valuation/R5_valuation_handoff.yaml",
        RUN / "valuation/valuation_section_draft.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for token in ("买入", "卖出", "持有", "目标价", "仓位", "保证收益"):
        assert token not in text
