from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/build_r5_bundle5_market_peer_onboarding.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("r5_bundle5_market_peer_builder_test", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BUILDER = load_builder()


def fixture_rows() -> list[dict]:
    values = {
        "002837.SZ": (73.54, 179.5613, 194.2045, 27.0715, 15.4449, 14.8507, 127434.9692, 9371566.9584),
        "301018.SZ": (119.56, 215.0, 234.3524, 16.2152, 11.0, 10.6599, 37429.4739, 4474907.2228),
        "300499.SZ": (38.60, 350.0, 385.8974, 8.4621, 12.2, 11.9854, 30524.8600, 1178259.5960),
        "300731.SZ": (52.10, 380.0, 409.8812, 14.9378, 8.4, 8.1817, 17728.4600, 923652.7660),
        "300602.SZ": (45.82, 65.0, 69.9482, 6.4751, 4.0, 3.8447, 58644.3600, 2687084.5752),
    }
    rows = []
    for ts_code, (close, pe, pe_ttm, pb, ps, ps_ttm, shares, market_cap) in values.items():
        rows.append(
            {
                "ts_code": ts_code,
                "trade_date": "20260710",
                "close": close,
                "turnover_rate": 1.0,
                "volume_ratio": 1.0,
                "pe": pe,
                "pe_ttm": pe_ttm,
                "pb": pb,
                "ps": ps,
                "ps_ttm": ps_ttm,
                "dv_ratio": 0.0,
                "dv_ttm": 0.0,
                "total_share": shares,
                "float_share": shares * 0.8,
                "free_share": shares * 0.6,
                "total_mv": market_cap,
                "circ_mv": market_cap * 0.8,
            }
        )
    return rows


def test_raw_snapshot_is_same_date_complete_and_token_free() -> None:
    payload = BUILDER.raw_payload(fixture_rows())
    assert payload["trade_date"] == "20260710"
    assert len(payload["rows"]) == 5
    text = json.dumps(payload, ensure_ascii=False)
    assert "TUSHARE_TOKEN" not in text
    assert "fast.xiaodefa.cn" not in text


def test_native_units_are_explicitly_converted() -> None:
    rows = BUILDER.normalize_rows(fixture_rows(), "ev_test_market")
    subject = next(row for row in rows if row["stock_code"] == "002837")
    assert subject["close_price"] == 73.54
    assert subject["close_price_unit"] == "CNY_per_share"
    assert subject["total_share"] == 1_274_349_692
    assert subject["total_share_unit"] == "shares"
    assert subject["market_cap"] == 93_715_669_584
    assert subject["market_cap_unit"] == "CNY"
    assert subject["pe_ttm"] == 194.2045
    assert subject["pb"] == 27.0715
    assert subject["ps_ttm"] == 14.8507


def test_peer_selection_is_exposure_first_and_low_confidence() -> None:
    review = BUILDER.peer_selection_review(REPO_ROOT)
    assert [row["stock_code"] for row in review["included"]] == ["301018", "300499"]
    assert [row["stock_code"] for row in review["excluded"]] == ["300731", "300602"]
    assert review["selection_sequence"] == "exposure comparability first, market multiples second"
    assert review["peer_set_quality"] == "low"
    assert all("selected before reviewing valuation multiples" in row["reason"] for row in review["included"])
    assert all("exposure" in row["reason"] for row in review["included"] + review["excluded"])


def test_reviewed_market_and_peer_records_preserve_contract() -> None:
    evidence_id = "ev_test_market"
    normalized = BUILDER.normalize_rows(fixture_rows(), evidence_id)
    by_code = {row["stock_code"]: row for row in normalized}
    reviewed_at = "2026-07-12T01:30:00+08:00"
    market = BUILDER.build_market_record(by_code["002837"], evidence_id, "data/raw/market_data/test.json", reviewed_at)
    selection = BUILDER.peer_selection_review(REPO_ROOT)
    peers = BUILDER.build_peer_records(normalized, evidence_id, "data/raw/market_data/test.json", reviewed_at, selection)
    assert market["market_cap_method"] == "source_reported_total_mv_native_10k_CNY_x10000"
    assert market["price_adjustment_convention"] == "unadjusted_cash_close_from_daily_basic"
    assert market["review_status"] == "accepted"
    assert market["reviewer"] == "codex"
    assert market["no_live_api"] is True
    assert market["sample_quality_allowed"] is False
    assert len(peers) == 6
    assert {row["peer_stock_code"] for row in peers} == {"301018", "300499"}
    assert {row["peer_metric_name"] for row in peers} == {"pe_ttm", "pb", "ps_ttm"}
    assert all(row["stock_code"] == "002837" for row in peers)
    assert all(row["review_status"] == "accepted" for row in peers)
    assert all(row["sample_quality_allowed"] is False for row in peers)


def test_mixed_date_or_missing_required_field_fails_closed() -> None:
    rows = fixture_rows()
    rows[0]["trade_date"] = "20260709"
    try:
        BUILDER.validate_raw_rows(rows)
    except ValueError as exc:
        assert "mixed trade date" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("mixed-date snapshot must fail")

    rows = fixture_rows()
    rows[0]["total_mv"] = None
    try:
        BUILDER.validate_raw_rows(rows)
    except ValueError as exc:
        assert "missing required fields" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("missing market cap must fail")
