from __future__ import annotations

import json
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
from src.ingest.adapters.eastmoney_report_pdf_adapter import (
    _extract_pdf,
    _report_pdf_run_id,
)
from src.ingest.evidence_io import (
    INGEST_RUN_FIELDNAMES,
    hash_json,
    read_csv_dicts,
    safe_slug,
    short_hash,
    write_csv_rows,
)


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
    assert result["run_id"].startswith("adapter_run_")
    assert not result["run_id"].startswith("r5_bundle8r_")
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


def test_adapter_run_id_reuses_matching_legacy_ledger_row(tmp_path: Path) -> None:
    fixture_path = FIXTURES / "tencent_quote.json"
    payload_hash = hash_json(json.loads(fixture_path.read_text(encoding="utf-8")))
    endpoint = "quote_and_valuation"
    run_suffix = (
        f"{safe_slug(tencent_quote_adapter.SPEC.adapter_id)}_{safe_slug(endpoint)}_"
        f"{short_hash(payload_hash, 8)}"
    )
    legacy_run_id = f"r5_bundle8r_{run_suffix}"
    write_csv_rows(
        tmp_path / "data/manifests/ingest_runs.csv",
        INGEST_RUN_FIELDNAMES,
        [{"run_id": legacy_run_id}],
    )

    code, result = execute_standard_adapter(
        [
            "--repo-root", str(tmp_path), "--stock-code", "002837",
            "--company-id", "cn_002837_invic", "--as-of-date", "2026-07-01",
            "--endpoint-hint", endpoint, "--mode", "fixture",
            "--fixture-json", str(fixture_path),
            "--receipt-output", str(tmp_path / "legacy_adapter.yaml"),
        ],
        spec=tencent_quote_adapter.SPEC,
        live_fetcher=tencent_quote_adapter.fetch_live,
        description="legacy run id compatibility",
    )

    assert code == 0, result
    assert result["run_id"] == legacy_run_id
    rows = read_csv_dicts(tmp_path / "data/manifests/ingest_runs.csv")
    assert [row["run_id"] for row in rows] == [legacy_run_id]

    log_path = tmp_path / result["ingest_log_path"]
    preserved_log = '{"historical": true}\n'
    log_path.write_text(preserved_log, encoding="utf-8")
    code, repeated_result = execute_standard_adapter(
        [
            "--repo-root", str(tmp_path), "--stock-code", "002837",
            "--company-id", "cn_002837_invic", "--as-of-date", "2026-07-01",
            "--endpoint-hint", endpoint, "--mode", "fixture",
            "--fixture-json", str(fixture_path),
            "--receipt-output", str(tmp_path / "legacy_adapter_repeat.yaml"),
        ],
        spec=tencent_quote_adapter.SPEC,
        live_fetcher=tencent_quote_adapter.fetch_live,
        description="legacy run id compatibility repeat",
    )
    assert code == 0, repeated_result
    assert repeated_result["run_id"] == legacy_run_id
    assert log_path.read_text(encoding="utf-8") == preserved_log


def test_report_pdf_run_id_is_neutral_and_legacy_compatible(tmp_path: Path) -> None:
    pdf_rows = [{"info_code": "fixture", "file_hash": "abc123"}]
    neutral_run_id = _report_pdf_run_id(tmp_path, "002837", pdf_rows)
    assert neutral_run_id.startswith("report_pdf_run_002837_")

    legacy_run_id = neutral_run_id.replace(
        "report_pdf_run_", "r5_bundle8r_report_pdf_", 1
    )
    write_csv_rows(
        tmp_path / "data/manifests/ingest_runs.csv",
        INGEST_RUN_FIELDNAMES,
        [{"run_id": legacy_run_id}],
    )
    assert _report_pdf_run_id(tmp_path, "002837", pdf_rows) == legacy_run_id
