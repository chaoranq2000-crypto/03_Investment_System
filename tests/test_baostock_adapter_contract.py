from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ingest"))

from adapters.baostock_adapter import main as baostock_main  # noqa: E402


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_baostock_fixture_k_line_creates_metric_seed(tmp_path: Path) -> None:
    fixture = tmp_path / "kline.csv"
    fixture.write_text(
        "date,code,open,high,low,close,volume,amount\n"
        "2026-07-01,sz.002837,10,11,9,10.5,1000,10500\n",
        encoding="utf-8",
    )
    baostock_main(
        [
            "--repo-root",
            str(tmp_path),
            "--api-name",
            "query_history_k_data_plus",
            "--stock-code",
            "002837",
            "--company-id",
            "cn_002837_invic",
            "--fixture-csv",
            str(fixture),
            "--as-of-date",
            "2026-07-01",
            "--publish-date",
            "2026-07-01",
        ]
    )
    manifest = read_csv(tmp_path / "data/manifests/evidence_manifest.csv")
    metrics = read_csv(tmp_path / "data/manifests/metrics_draft.csv")
    assert manifest[0]["source_name"] == "baostock"
    assert manifest[0]["source_type"] == "structured_market_data"
    assert "close" in {row["metric_name"] for row in metrics}
    assert not (tmp_path / "data/manifests/claims_draft.csv").exists()


def test_baostock_dry_run_or_missing_package_maps_to_non_crashing_status(tmp_path: Path) -> None:
    readout = tmp_path / "baostock_dry_run.json"
    baostock_main(
        [
            "--repo-root",
            str(tmp_path),
            "--api-name",
            "query_history_k_data_plus",
            "--stock-code",
            "002837",
            "--dry-run",
            "--as-of-date",
            "2026-07-01",
            "--readout-output",
            str(readout),
        ]
    )
    payload = json.loads(readout.read_text(encoding="utf-8"))
    assert payload["result"] in {"SUCCESS", "BLOCKED"}
    assert payload["source_name"] == "baostock"


def test_baostock_live_mode_requires_explicit_network_flag(tmp_path: Path) -> None:
    readout = tmp_path / "baostock_live_blocked.json"
    baostock_main(
        [
            "--repo-root",
            str(tmp_path),
            "--api-name",
            "query_history_k_data_plus",
            "--stock-code",
            "002837",
            "--mode",
            "live",
            "--as-of-date",
            "2026-07-01",
            "--readout-output",
            str(readout),
        ]
    )
    payload = json.loads(readout.read_text(encoding="utf-8"))
    assert payload["result"] == "BLOCKED"
    assert payload["mode"] == "live"
    assert payload["allow_network"] is False
    assert payload["permission_note"] == "live Baostock mode requires explicit --allow-network"


def test_baostock_live_mode_routes_mock_response_through_structured_ingest(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[str] = []

    class FakeLogin:
        error_code = "0"
        error_msg = ""

    class FakeResult:
        error_code = "0"
        error_msg = ""
        fields = ["date", "code", "close", "volume"]

        def __init__(self) -> None:
            self._rows = [["2026-07-01", "sz.002837", "10.5", "1000"]]
            self._current: list[str] = []

        def next(self) -> bool:
            if not self._rows:
                return False
            self._current = self._rows.pop(0)
            return True

        def get_row_data(self) -> list[str]:
            return self._current

    def fake_login() -> FakeLogin:
        calls.append("login")
        return FakeLogin()

    def fake_query_history_k_data_plus(*args: object, **kwargs: object) -> FakeResult:
        calls.append("query")
        assert args[0] == "sz.002837"
        assert kwargs["frequency"] == "d"
        assert kwargs["adjustflag"] == "3"
        return FakeResult()

    def fake_logout() -> None:
        calls.append("logout")

    fake_baostock = SimpleNamespace(
        login=fake_login,
        query_history_k_data_plus=fake_query_history_k_data_plus,
        logout=fake_logout,
    )
    monkeypatch.setitem(sys.modules, "baostock", fake_baostock)
    readout = tmp_path / "baostock_live_readout.json"

    baostock_main(
        [
            "--repo-root",
            str(tmp_path),
            "--api-name",
            "query_history_k_data_plus",
            "--stock-code",
            "002837",
            "--company-id",
            "cn_002837_invic",
            "--mode",
            "live",
            "--allow-network",
            "--as-of-date",
            "2026-07-01",
            "--publish-date",
            "2026-07-01",
            "--readout-output",
            str(readout),
        ]
    )

    assert calls == ["login", "query", "logout"]
    payload = json.loads(readout.read_text(encoding="utf-8"))
    assert payload["adapter_status"] == "live_completed"
    assert payload["rows"] == 1
    manifest = read_csv(tmp_path / "data/manifests/evidence_manifest.csv")
    metrics = read_csv(tmp_path / "data/manifests/metrics_draft.csv")
    assert manifest[0]["source_name"] == "baostock"
    assert manifest[0]["source_type"] == "structured_market_data"
    assert manifest[0]["raw_file_path"]
    assert manifest[0]["processed_table_path"]
    assert manifest[0]["api_params_hash"]
    assert "close" in {row["metric_name"] for row in metrics}
