from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ingest"))

from adapters.baostock_adapter import main as baostock_main  # noqa: E402
from adapters.tushare_adapter import main as tushare_main  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("ENABLE_LIVE_DATA_TESTS") != "1",
    reason="live data smoke tests require ENABLE_LIVE_DATA_TESTS=1",
)


def test_tushare_live_smoke_manual(tmp_path: Path) -> None:
    if not os.environ.get("TUSHARE_TOKEN"):
        pytest.skip("TUSHARE_TOKEN is required for manual Tushare live smoke")
    readout = tmp_path / "tushare_live_smoke.json"
    tushare_main(
        [
            "--repo-root",
            str(tmp_path),
            "--api-name",
            "daily_basic",
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
    assert readout.exists()
    text = readout.read_text(encoding="utf-8")
    payload = json.loads(text)
    assert payload["result"] == "SUCCESS"
    assert "TUSHARE_TOKEN" in text
    assert os.environ["TUSHARE_TOKEN"] not in text


def test_baostock_live_smoke_manual(tmp_path: Path) -> None:
    if importlib.util.find_spec("baostock") is None:
        pytest.skip("baostock package is required for manual Baostock live smoke")
    readout = tmp_path / "baostock_live_smoke.json"
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
            "--start-date",
            "2026-06-01",
            "--end-date",
            "2026-07-01",
            "--as-of-date",
            "2026-07-01",
            "--readout-output",
            str(readout),
        ]
    )
    assert readout.exists()
    payload = json.loads(readout.read_text(encoding="utf-8"))
    assert payload["result"] == "SUCCESS"
