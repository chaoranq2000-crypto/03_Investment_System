from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from utils.tushare_client import get_tushare_pro, tushare_config_summary


REPORT_DATE = "2026-07-01"
CODES = ["002837", "301018", "300499", "300731", "300602"]
RAW_PATH = ROOT / "data/raw/market_data/tushare_stock_basic_ai_server_liquid_cooling_2026-07-01.csv"
PROCESSED_PATH = (
    ROOT / "data/processed/tables/tushare_stock_basic_ai_server_liquid_cooling_2026-07-01.csv"
)


def write_once(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return "unchanged"
        raise RuntimeError(f"{path} already exists with different content; raw evidence is immutable")
    path.write_text(content, encoding="utf-8")
    return "created"


def main() -> None:
    summary = tushare_config_summary(ROOT / ".env.local")
    print(
        {
            "token_present": summary["token_present"],
            "token_length": summary["token_length"],
            "token_alnum": summary["token_alnum"],
            "api_url": summary["api_url"],
        }
    )

    pro = get_tushare_pro(ROOT / ".env.local")
    df = pro.stock_basic(
        exchange="",
        list_status="L",
        fields="ts_code,symbol,name,area,industry,market,list_date",
    )
    snapshot = df[df["symbol"].isin(CODES)].sort_values("symbol")
    csv_text = snapshot.to_csv(index=False, lineterminator="\n")

    raw_status = write_once(RAW_PATH, csv_text)
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_PATH.write_text(csv_text, encoding="utf-8")

    print(
        {
            "rows": len(snapshot),
            "raw_status": raw_status,
            "raw_path": str(RAW_PATH),
            "processed_path": str(PROCESSED_PATH),
        }
    )


if __name__ == "__main__":
    main()
