from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ingest"))

from build_peer_market_snapshot import FIELDNAMES, TODO_MARKET_DATA, build_peer_market_snapshot  # noqa: E402


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_peer_market_snapshot_fixture_builder_keeps_schema_and_todos(tmp_path: Path) -> None:
    peers = tmp_path / "company_universe.csv"
    peers.write_text(
        "segment_id,stock_code,stock_name,company_id\n"
        "ai_server_liquid_cooling,002837,英维克,cn_002837_invic\n"
        "ai_server_liquid_cooling,300731,科创新源,cn_300731_cotran\n",
        encoding="utf-8",
    )
    valuation = tmp_path / "valuation_snapshot.yaml"
    valuation.write_text(
        "stock_code: '002837'\n"
        "as_of_date: '20260701'\n"
        "sources:\n"
        "  - source_name: tushare\n"
        "    evidence_id: ev_structured_market_data_002837_20260701_daa823\n"
        "    api_params_hash: abc123\n"
        "market_values:\n"
        "  price: '32.50'\n"
        "  market_cap: '2418000'\n"
        "  pe_ttm: '38.2'\n"
        "  pe_forward: TODO_MARKET_DATA\n"
        "  pb: '4.1'\n"
        "  ps: '6.7'\n",
        encoding="utf-8",
    )
    output = tmp_path / "peer_market_snapshot.csv"

    rows = build_peer_market_snapshot(
        peer_source_csv=peers,
        valuation_snapshot_path=valuation,
        output_path=output,
        as_of_date="2026-07-01",
        peer_group="ai_server_liquid_cooling",
    )

    assert len(rows) == 2
    parsed_rows = read_rows(output)
    assert list(parsed_rows[0]) == FIELDNAMES
    assert all(all(value != "" for value in row.values()) for row in parsed_rows)

    target = parsed_rows[0]
    assert target["stock_code"] == "002837"
    assert target["price"] == "32.50"
    assert target["pe_forward"] == TODO_MARKET_DATA
    assert "pe_forward" in target["missing_fields"]
    assert target["source_evidence_id"] == "ev_structured_market_data_002837_20260701_daa823"

    peer = parsed_rows[1]
    assert peer["stock_code"] == "300731"
    assert peer["price"] == TODO_MARKET_DATA
    assert peer["pe_forward"] == TODO_MARKET_DATA
    assert "price" in peer["missing_fields"]
    assert "pe_forward" in peer["missing_fields"]
    assert "trading conclusion" in peer["notes"]

    text = output.read_text(encoding="utf-8")
    assert "买入" not in text
    assert "卖出" not in text
    assert "持有" not in text


def test_current_peer_snapshot_and_reconciliation_stub_remain_metric_only() -> None:
    run_dir = ROOT / "reports/workflow_runs/wf_20260703_data_layer_002837_invic"
    peer_snapshot = run_dir / "peer_market_snapshot.csv"
    reconciliation_stub = run_dir / "official_disclosure_reconciliation_stub.md"

    assert peer_snapshot.exists()
    assert reconciliation_stub.exists()
    rows = read_rows(peer_snapshot)
    assert list(rows[0]) == FIELDNAMES
    assert rows
    assert all(row["pe_forward"] for row in rows)
    assert all(row["notes"] == "Fixture-only peer valuation context; no trading conclusion." for row in rows)

    peer_text = peer_snapshot.read_text(encoding="utf-8")
    stub_text = reconciliation_stub.read_text(encoding="utf-8")
    for forbidden in ["买入", "卖出", "持有", "目标价"]:
        assert forbidden not in peer_text
        assert forbidden not in stub_text
    assert "metric-only" in stub_text
    assert "business exposure fact" in stub_text
