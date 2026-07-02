from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from evidence_io import normalize_stock_code, stock_to_ts_code, utc_now_iso

TEMPLATE = """# Generated stock evidence plan for stock_first_closed_loop.
workflow_id: "{workflow_id}"
stock_code: "{stock_code}"
ts_code: "{ts_code}"
company_id: "{company_id}"
company_name: "{company_name}"
exchange: "{exchange}"
date_range:
  start: "{start_date}"
  end: "{end_date}"
as_of_date: "{as_of_date}"
created_at: "{created_at}"

required_evidence:
  official_filings:
    - evidence_need: latest_annual_report
      source_type: annual_report
      preferred_sources: [cninfo, sse, szse, bse]
      required_for: [business_exposure, business_breakdown, risk]
      status: TODO
      evidence_id: ""
      notes: "Annual report required before claiming revenue/product exposure."
    - evidence_need: latest_interim_report
      source_type: interim_report
      preferred_sources: [cninfo, sse, szse, bse]
      required_for: [business_update, financial_update]
      status: TODO
      evidence_id: ""
      notes: "Use TODO if not published in date range."
    - evidence_need: latest_quarterly_report
      source_type: quarterly_report
      preferred_sources: [cninfo, sse, szse, bse]
      required_for: [financial_update]
      status: TODO
      evidence_id: ""
      notes: "Quarterly report supports metrics, not segment exposure alone."
    - evidence_need: material_announcements_last_12m
      source_type: announcement
      preferred_sources: [cninfo, sse, szse, bse]
      required_for: [orders, capex, projects, risks]
      status: TODO
      evidence_id: ""
      notes: "Do not treat framework agreements as revenue."

  structured_financial_data:
    - api_name: stock_basic
      source_type: structured_market_data
      preferred_sources: [tushare, baostock]
      status: TODO
      evidence_id: ""
    - api_name: income
      source_type: structured_financial_data
      preferred_sources: [tushare]
      status: TODO
      evidence_id: ""
    - api_name: balancesheet
      source_type: structured_financial_data
      preferred_sources: [tushare]
      status: TODO
      evidence_id: ""
    - api_name: cashflow
      source_type: structured_financial_data
      preferred_sources: [tushare]
      status: TODO
      evidence_id: ""
    - api_name: fina_indicator
      source_type: structured_financial_data
      preferred_sources: [tushare]
      status: TODO
      evidence_id: ""

  optional_context:
    - evidence_need: investor_relations
      source_type: company_ir_product
      status: TODO
      notes: "Management comments must be tagged management_comment."
    - evidence_need: company_website
      source_type: company_ir_product
      status: TODO
      notes: "Useful for product clues; not enough for financial exposure."
    - evidence_need: exchange_inquiry_reply
      source_type: announcement
      status: TODO
      notes: "Prefer official exchange disclosure if available."
    - evidence_need: news_clues
      source_type: news_social_clue
      status: TODO
      notes: "Clue only; must be verified with official disclosure."

rules:
  annual_report_required_for_business_exposure: true
  structured_data_metric_only: true
  news_clue_only: true
  management_comment_not_fact: true
  revenue_pct_profit_pct_must_be_disclosed_or_missing: true
  no_buy_sell_hold_advice: true
"""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a stock evidence plan YAML file.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--stock-code", required=True)
    parser.add_argument("--company-id", default="")
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--exchange", default="")
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output", default="")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    stock_code = normalize_stock_code(args.stock_code)
    as_of_date = args.as_of_date or args.end_date or utc_now_iso()[:10]
    output = Path(args.output) if args.output else repo_root / "reports" / "workflow_runs" / args.workflow_id / "stock_evidence_plan.yaml"
    if not output.is_absolute():
        output = repo_root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        TEMPLATE.format(
            workflow_id=args.workflow_id,
            stock_code=stock_code,
            ts_code=stock_to_ts_code(stock_code),
            company_id=args.company_id,
            company_name=args.company_name,
            exchange=args.exchange,
            start_date=args.start_date,
            end_date=args.end_date,
            as_of_date=as_of_date,
            created_at=utc_now_iso(),
        ),
        encoding="utf-8",
    )
    print(output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
