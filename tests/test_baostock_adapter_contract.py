from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


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
