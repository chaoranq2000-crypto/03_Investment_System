from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ingest"))

from adapters.tushare_adapter import main as tushare_main  # noqa: E402
from structured_api_pull import build_api_params_hash  # noqa: E402


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_tushare_no_token_dry_run_returns_blocked(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    readout = tmp_path / "tushare_dry_run.json"
    tushare_main(
        [
            "--repo-root",
            str(tmp_path),
            "--api-name",
            "income",
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
    assert payload["result"] == "BLOCKED"
    assert payload["params"]["token_env"] == "TUSHARE_TOKEN"


def test_tushare_live_mode_requires_explicit_network_flag(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TUSHARE_TOKEN", "x" * 56)
    readout = tmp_path / "tushare_live_blocked.json"
    tushare_main(
        [
            "--repo-root",
            str(tmp_path),
            "--api-name",
            "income",
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
    assert payload["permission_note"] == "live Tushare mode requires explicit --allow-network"
    assert "x" * 56 not in readout.read_text(encoding="utf-8")


def test_tushare_live_mode_with_network_requires_token_without_leaking(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    readout = tmp_path / "tushare_live_no_token.json"
    tushare_main(
        [
            "--repo-root",
            str(tmp_path),
            "--api-name",
            "income",
            "--stock-code",
            "002837",
            "--mode",
            "live",
            "--allow-network",
            "--as-of-date",
            "2026-07-01",
            "--readout-output",
            str(readout),
        ]
    )
    payload = json.loads(readout.read_text(encoding="utf-8"))
    assert payload["result"] == "BLOCKED"
    assert payload["permission_note"] == "missing TUSHARE_TOKEN"
    assert "token_value" not in readout.read_text(encoding="utf-8")


def test_tushare_live_mode_routes_mock_response_through_structured_ingest(
    tmp_path: Path, monkeypatch
) -> None:
    token = "sensitive-live-token-should-not-be-written"
    captured: dict[str, object] = {}

    class FakeFrame:
        def to_dict(self, orient: str) -> list[dict[str, str]]:
            assert orient == "records"
            return [{"ts_code": "002837.SZ", "end_date": "20251231", "total_revenue": "1000"}]

    class FakePro:
        def income(self, **params: str) -> FakeFrame:
            captured["params"] = params
            captured["http_url"] = getattr(self, "_DataApi__http_url", "")
            return FakeFrame()

    fake_tushare = SimpleNamespace(
        set_token=lambda value: captured.setdefault("token", value),
        pro_api=lambda: FakePro(),
    )
    monkeypatch.setitem(sys.modules, "tushare", fake_tushare)
    monkeypatch.setenv("TUSHARE_TOKEN", token)
    monkeypatch.setenv("TUSHARE_HTTP_URL", "https://tushare-proxy.example.test")

    readout = tmp_path / "tushare_live_readout.json"
    tushare_main(
        [
            "--repo-root",
            str(tmp_path),
            "--api-name",
            "income",
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
            "--unit",
            "CNY",
            "--readout-output",
            str(readout),
        ]
    )

    assert captured["token"] == token
    assert captured["params"]["ts_code"] == "002837.SZ"  # type: ignore[index]
    assert captured["http_url"] == "https://tushare-proxy.example.test"
    payload = json.loads(readout.read_text(encoding="utf-8"))
    assert payload["adapter_status"] == "live_completed"
    assert payload["rows"] == 1
    manifest = read_csv(tmp_path / "data/manifests/evidence_manifest.csv")
    metrics = read_csv(tmp_path / "data/manifests/metrics_draft.csv")
    assert manifest[0]["source_name"] == "tushare"
    assert manifest[0]["material_claim_allowed"] == "metric_only"
    assert manifest[0]["raw_file_path"]
    assert manifest[0]["processed_table_path"]
    assert manifest[0]["api_params_hash"]
    assert {row["metric_name"] for row in metrics} == {"total_revenue"}
    assert all(row["metric_candidate_id"].startswith("metric_company_") for row in metrics)
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert token not in path.read_text(encoding="utf-8", errors="ignore")


def test_tushare_income_fixture_generates_manifest_and_metrics(tmp_path: Path) -> None:
    fixture = tmp_path / "income.csv"
    fixture.write_text(
        "ts_code,end_date,total_revenue,n_income_attr_p\n002837.SZ,20251231,1000,120\n",
        encoding="utf-8",
    )
    tushare_main(
        [
            "--repo-root",
            str(tmp_path),
            "--api-name",
            "income",
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
            "--unit",
            "CNY",
        ]
    )
    manifest = read_csv(tmp_path / "data/manifests/evidence_manifest.csv")
    metrics = read_csv(tmp_path / "data/manifests/metrics_draft.csv")
    assert manifest[0]["source_name"] == "tushare"
    assert manifest[0]["material_claim_allowed"] == "metric_only"
    assert {"total_revenue", "n_income_attr_p"}.issubset({row["metric_name"] for row in metrics})


def test_tushare_fina_mainbz_does_not_create_claim_candidates(tmp_path: Path) -> None:
    fixture = tmp_path / "fina_mainbz.csv"
    fixture.write_text(
        "ts_code,end_date,bz_item,bz_sales,bz_profit\n002837.SZ,20251231,机房温控,100,20\n",
        encoding="utf-8",
    )
    tushare_main(
        [
            "--repo-root",
            str(tmp_path),
            "--api-name",
            "fina_mainbz",
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
            "--unit",
            "CNY",
        ]
    )
    assert not (tmp_path / "data/manifests/claims_draft.csv").exists()
    metrics = read_csv(tmp_path / "data/manifests/metrics_draft.csv")
    assert {row["metric_category"] for row in metrics} == {"fina_mainbz"}
    assert all("not business exposure evidence" in row["notes"] for row in metrics)


def test_tushare_api_params_hash_changes_when_params_change() -> None:
    first = build_api_params_hash(
        source_name="tushare",
        api_name="income",
        stock_code="002837",
        as_of_date="2026-07-01",
        start_date="20240101",
    )
    second = build_api_params_hash(
        source_name="tushare",
        api_name="income",
        stock_code="002837",
        as_of_date="2026-07-01",
        start_date="20250101",
    )
    assert first != second


def test_tushare_disclosure_date_uses_report_period_without_date_metrics(
    tmp_path: Path, monkeypatch
) -> None:
    captured: dict[str, object] = {}

    class FakeFrame:
        def to_dict(self, orient: str) -> list[dict[str, str]]:
            assert orient == "records"
            return [
                {
                    "ts_code": "002837.SZ",
                    "ann_date": "20260701",
                    "end_date": "20260630",
                    "pre_date": "20260825",
                    "actual_date": "",
                    "modify_date": "",
                }
            ]

    class FakePro:
        def disclosure_date(self, **params: str) -> FakeFrame:
            captured["params"] = params
            return FakeFrame()

    fake_tushare = SimpleNamespace(
        set_token=lambda value: captured.setdefault("token", value),
        pro_api=lambda: FakePro(),
    )
    monkeypatch.setitem(sys.modules, "tushare", fake_tushare)
    monkeypatch.setenv("TUSHARE_TOKEN", "event-calendar-token")

    tushare_main(
        [
            "--repo-root",
            str(tmp_path),
            "--api-name",
            "disclosure_date",
            "--stock-code",
            "002837",
            "--company-id",
            "cn_002837_invic",
            "--mode",
            "live",
            "--allow-network",
            "--start-date",
            "20260101",
            "--end-date",
            "20260630",
            "--as-of-date",
            "2026-07-13",
            "--publish-date",
            "2026-07-13",
        ]
    )

    assert captured["params"] == {"ts_code": "002837.SZ", "end_date": "20260630"}
    metrics_path = tmp_path / "data/manifests/metrics_draft.csv"
    assert not metrics_path.exists()
    manifest = read_csv(tmp_path / "data/manifests/evidence_manifest.csv")
    assert manifest[0]["candidate_status"] == "not_generated"
