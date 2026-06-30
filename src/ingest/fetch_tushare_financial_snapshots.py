from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from utils.tushare_client import get_tushare_pro, tushare_config_summary


REPORT_DATE = "2026-07-01"
STOCKS = ["002837.SZ", "300731.SZ"]
START_DATE = "20240101"
END_DATE = "20260701"
REQUEST_INTERVAL_SECONDS = 0.8

DATASETS = {
    "income": {
        "fields": (
            "ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,total_revenue,"
            "revenue,operate_profit,total_profit,n_income,n_income_attr_p,basic_eps,diluted_eps"
        )
    },
    "fina_indicator": {
        "fields": (
            "ts_code,ann_date,end_date,roe,roe_dt,grossprofit_margin,netprofit_margin,"
            "ocfps,debt_to_assets,invturn_days,arturn_days"
        )
    },
    "cashflow": {
        "fields": (
            "ts_code,ann_date,end_date,net_profit,c_fr_sale_sg,c_inf_fr_operate_a,"
            "n_cashflow_act"
        )
    },
    "balancesheet": {
        "fields": (
            "ts_code,ann_date,end_date,total_assets,total_liab,total_hldr_eqy_exc_min_int,"
            "inventories,accounts_receiv"
        )
    },
}


def write_raw_once(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") == content:
            return "unchanged"
        raise RuntimeError(f"{path} already exists with different content; raw evidence is immutable")
    path.write_text(content, encoding="utf-8")
    return "created"


def fetch_dataset(pro, api_name: str, fields: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for ts_code in STOCKS:
        time.sleep(REQUEST_INTERVAL_SECONDS)
        df = getattr(pro, api_name)(
            ts_code=ts_code,
            start_date=START_DATE,
            end_date=END_DATE,
            fields=fields,
        )
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    summary = tushare_config_summary(ROOT / ".env.local")
    print(
        {
            "token_present": summary["token_present"],
            "token_length": summary["token_length"],
            "api_url": summary["api_url"],
        }
    )
    pro = get_tushare_pro(ROOT / ".env.local")

    for api_name, config in DATASETS.items():
        df = fetch_dataset(pro, api_name, config["fields"])
        if not df.empty and "ts_code" in df.columns and "end_date" in df.columns:
            df = df.sort_values(["ts_code", "end_date"], ascending=[True, False])
        csv_text = df.to_csv(index=False, lineterminator="\n")

        raw_path = (
            ROOT
            / "data/raw/market_data"
            / f"tushare_{api_name}_selected_stocks_{REPORT_DATE}.csv"
        )
        processed_path = (
            ROOT
            / "data/processed/tables"
            / f"tushare_{api_name}_selected_stocks_{REPORT_DATE}.csv"
        )
        raw_status = write_raw_once(raw_path, csv_text)
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        processed_path.write_text(csv_text, encoding="utf-8")
        print(
            {
                "api_name": api_name,
                "rows": int(len(df)),
                "raw_status": raw_status,
                "raw_path": str(raw_path),
                "processed_path": str(processed_path),
            }
        )


if __name__ == "__main__":
    main()
