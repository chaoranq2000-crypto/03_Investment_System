from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfWriter

from src.ingest.adapters import (
    baidu_kline_adapter,
    cninfo_irm_adapter,
    cls_telegraph_adapter,
    eastmoney_basic_adapter,
    eastmoney_capital_adapter,
    eastmoney_industry_report_adapter,
    eastmoney_news_adapter,
    exchange_fallback_adapter,
    mootdx_adapter,
    sina_financial_adapter,
    tencent_quote_adapter,
    ths_consensus_adapter,
)
from src.ingest.adapters.adapter_runtime import execute_standard_adapter
from src.ingest.adapters.eastmoney_report_pdf_adapter import _extract_pdf


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "r5_bundle8r"


CASES = [
    (mootdx_adapter, "daily_bar", "mootdx_daily.json"),
    (mootdx_adapter, "finance_snapshot", "mootdx_finance.json"),
    (mootdx_adapter, "f10", "mootdx_f10.json"),
    (tencent_quote_adapter, "quote_and_valuation", "tencent_quote.json"),
    (tencent_quote_adapter, "quote_or_kline", "tencent_quote.json"),
    (eastmoney_basic_adapter, "stock_info", "eastmoney_basic.json"),
    (eastmoney_industry_report_adapter, "industry_reportapi_metadata", "industry_report.json"),
    (eastmoney_capital_adapter, "lockup_expiry", "capital_lockup.json"),
    (eastmoney_capital_adapter, "holder_count", "capital_holder.json"),
    (eastmoney_capital_adapter, "dividend_history", "capital_dividend.json"),
    (eastmoney_capital_adapter, "fund_flow", "capital_fund_flow.json"),
    (eastmoney_capital_adapter, "margin_trading", "capital_margin.json"),
    (eastmoney_capital_adapter, "block_trade", "capital_block_trade.json"),
    (baidu_kline_adapter, "kline_with_ma", "baidu_kline.json"),
    (cls_telegraph_adapter, "telegraph", "cls_telegraph.json"),
    (ths_consensus_adapter, "consensus_eps", "ths_consensus.json"),
    (sina_financial_adapter, "financial_statements", "sina_financial.json"),
    (cninfo_irm_adapter, "irm_interaction", "cninfo_irm.json"),
    (exchange_fallback_adapter, "announcement_official", "exchange_announcement.json"),
    (eastmoney_news_adapter, "news_clue", "eastmoney_news.json"),
]


@pytest.mark.parametrize("module,endpoint,fixture_name", CASES)
def test_adapter_fixture_writes_raw_manifest_schema_and_boundary(
    tmp_path: Path,
    module: object,
    endpoint: str,
    fixture_name: str,
) -> None:
    receipt = tmp_path / f"{module.SPEC.adapter_id}_{endpoint}.yaml"
    code, result = execute_standard_adapter(
        [
            "--repo-root",
            str(tmp_path),
            "--stock-code",
            "002837",
            "--company-id",
            "cn_002837_invic",
            "--as-of-date",
            "2026-07-01",
            "--endpoint-hint",
            endpoint,
            "--mode",
            "fixture",
            "--fixture-json",
            str(FIXTURES / fixture_name),
            "--receipt-output",
            str(receipt),
        ],
        spec=module.SPEC,
        live_fetcher=module.fetch_live,
        description="fixture contract",
    )
    assert code == 0, result
    assert result["decision"] == "pass"
    assert result["checks"]["fixture_verified"] is True
    assert result["checks"]["raw_archive_verified"] is True
    assert result["checks"]["manifest_write_verified"] is True
    assert result["checks"]["schema_fingerprint_verified"] is True
    assert result["checks"]["claim_boundary_verified"] is True
    assert receipt.is_file()


def test_pdf_parser_preserves_page_map(tmp_path: Path) -> None:
    pdf_path = tmp_path / "fixture.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as handle:
        writer.write(handle)
    text_path = tmp_path / "fixture.md"
    page_map = tmp_path / "fixture_page_map.yaml"
    page_count, _ = _extract_pdf(pdf_path, text_path, page_map)
    assert page_count == 1
    assert text_path.is_file()
    assert page_map.is_file()


def test_cross_exchange_market_fixture_passes_contract(tmp_path: Path) -> None:
    code, result = execute_standard_adapter(
        [
            "--repo-root", str(tmp_path), "--stock-code", "600519",
            "--company-id", "cn_600519_kweichow_moutai", "--as-of-date", "2026-07-01",
            "--endpoint-hint", "kline_with_ma", "--mode", "fixture",
            "--fixture-json", str(FIXTURES / "baidu_kline_shanghai.json"),
            "--receipt-output", str(tmp_path / "cross_exchange.yaml"),
        ],
        spec=baidu_kline_adapter.SPEC,
        live_fetcher=baidu_kline_adapter.fetch_live,
        description="cross exchange fixture contract",
    )
    assert code == 0, result
    assert result["decision"] == "pass"
    assert result["checks"]["schema_fingerprint_verified"] is True
