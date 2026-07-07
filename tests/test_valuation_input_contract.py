from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".agents/skills/stock-deep-dive/scripts/validate_valuation_inputs.py"

MARKET_COLUMNS = [
    "stock_code",
    "company_id",
    "stock_name",
    "exchange",
    "as_of_date",
    "currency",
    "close_price",
    "market_cap",
    "free_float_market_cap",
    "shares_outstanding",
    "float_shares",
    "pe_ttm",
    "pe_lyr",
    "pe_forward_2026e",
    "pb_lf",
    "ps_ttm",
    "ev",
    "ev_ebitda_ttm",
    "dividend_yield",
    "turnover_rate",
    "pct_chg_20d",
    "pct_chg_60d",
    "source_name",
    "source_type",
    "source_path",
    "source_evidence_id",
    "source_metric_id",
    "reliability_rank",
    "capture_method",
    "snapshot_status",
    "limitations",
]

PEER_COLUMNS = [
    "subject_stock_code",
    "subject_company_id",
    "peer_company",
    "peer_stock_code",
    "exchange",
    "peer_selection_reason",
    "business_similarity",
    "segment_overlap",
    "as_of_date",
    "currency",
    "market_cap",
    "pe_ttm",
    "pe_forward_2026e",
    "pe_forward_2027e",
    "pb_lf",
    "ps_ttm",
    "ev_ebitda_ttm",
    "revenue_growth_2026e",
    "net_profit_growth_2026e",
    "roe",
    "gross_margin",
    "source_name",
    "source_type",
    "source_path",
    "source_evidence_id",
    "reliability_rank",
    "confidence",
    "limitations",
]

FINANCIAL_COLUMNS = [
    "metric_id",
    "company_id",
    "stock_code",
    "metric_name",
    "period",
    "value",
    "unit",
    "currency",
    "source_evidence_id",
    "source_path",
    "calculation_method",
    "claim_type",
    "confidence",
    "review_status",
    "limitations",
]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_workflow_run(case_name: str) -> Path:
    run = (
        REPO_ROOT
        / "reports/workflow_runs/wf_20260703_stock_first_002837_invic/.tmp_mineru_output/valuation_input_contract_tests"
        / case_name
    )
    run.mkdir(parents=True, exist_ok=True)
    stock_code = "002837"
    company_id = "cn_002837_invic"

    market_row = {column: "" for column in MARKET_COLUMNS}
    market_row.update(
        {
            "stock_code": stock_code,
            "company_id": company_id,
            "stock_name": "英维克",
            "exchange": "SZSE",
            "as_of_date": "2026-07-03",
            "currency": "CNY",
            "capture_method": "not_acquired",
            "snapshot_status": "TODO_MARKET_DATA",
            "limitations": "No reviewed market valuation snapshot available.",
        }
    )
    write_csv(run / "market_snapshot.csv", MARKET_COLUMNS, [market_row])

    peer_row = {column: "" for column in PEER_COLUMNS}
    peer_row.update(
        {
            "subject_stock_code": stock_code,
            "subject_company_id": company_id,
            "peer_company": "TODO_PEER_DATA",
            "as_of_date": "2026-07-03",
            "currency": "CNY",
            "confidence": "todo",
            "limitations": "No reviewed peer market snapshot available.",
        }
    )
    write_csv(run / "peer_market_snapshot.csv", PEER_COLUMNS, [peer_row])

    financial_row = {
        "metric_id": "metric_cn_002837_invic_revenue_20260331_4f7f22",
        "company_id": company_id,
        "stock_code": stock_code,
        "metric_name": "revenue",
        "period": "20260331",
        "value": "1175329313.61",
        "unit": "CNY",
        "currency": "CNY",
        "source_evidence_id": "ev_structured_financial_data_002837_20260701_89213a",
        "source_path": "data/raw/market_data/local_tushare_fixture_income_002837_2026-07-01_89213a96.csv",
        "calculation_method": "raw_adapter_snapshot_no_recalculation",
        "claim_type": "metric_snapshot",
        "confidence": "medium",
        "review_status": "reviewed_r3_candidate",
        "limitations": "Metric-only company-level fixture; not exposure proof.",
    }
    write_csv(run / "financial_metric_pack.csv", FINANCIAL_COLUMNS, [financial_row])

    (run / "stock_analysis_pack.yaml").write_text(
        yaml.safe_dump({"stock_code": stock_code, "company_id": company_id}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (run / "forecast_model.yaml").write_text(
        yaml.safe_dump({"periods": ["2026E"], "net_profit_forecast": "TODO_MODEL_INPUT"}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    readiness = {
        "valuation_input_readiness": {
            "workflow_id": "wf_test",
            "stock_code": stock_code,
            "company_id": company_id,
            "as_of_date": "2026-07-03",
            "generated_by": "stock-deep-dive",
            "no_advice_boundary": True,
            "input_paths": {
                "market_snapshot": str(run / "market_snapshot.csv"),
                "peer_market_snapshot": str(run / "peer_market_snapshot.csv"),
                "financial_metric_pack": str(run / "financial_metric_pack.csv"),
                "forecast_model": str(run / "forecast_model.yaml"),
                "valuation_request": str(run / "valuation_request.yaml"),
            },
            "statuses": {
                "market_snapshot": {
                    "status": "TODO_MARKET_DATA",
                    "source_paths": [],
                    "source_metric_ids": [],
                    "open_gaps": ["TODO_MARKET_DATA"],
                    "limitations": ["No reviewed market valuation snapshot."],
                },
                "peer_market_snapshot": {
                    "status": "TODO_PEER_DATA",
                    "source_paths": [],
                    "source_metric_ids": [],
                    "open_gaps": ["TODO_PEER_DATA"],
                    "limitations": ["No reviewed peer market snapshot."],
                },
                "financial_metric_pack": {
                    "status": "partial",
                    "source_paths": ["data/raw/market_data/local_tushare_fixture_income_002837_2026-07-01_89213a96.csv"],
                    "source_metric_ids": ["metric_cn_002837_invic_revenue_20260331_4f7f22"],
                    "open_gaps": [],
                    "limitations": ["Metric-only company-level fixture; not exposure proof."],
                },
                "forecast_model": {
                    "status": "partial",
                    "source_paths": [str(run / "forecast_model.yaml")],
                    "source_metric_ids": ["metric_cn_002837_invic_revenue_20260331_4f7f22"],
                    "open_gaps": ["TODO_FORECAST_MODEL_NET_PROFIT"],
                    "limitations": ["Revenue estimate only; net profit remains TODO."],
                },
            },
            "open_gaps": ["TODO_MARKET_DATA", "TODO_PEER_DATA", "TODO_FORECAST_MODEL_NET_PROFIT"],
        }
    }
    (run / "valuation_input_readiness.yaml").write_text(
        yaml.safe_dump(readiness, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    request = {
        "valuation_request": {
            "workflow_id": "wf_test",
            "stock_code": stock_code,
            "company_id": company_id,
            "stock_name": "英维克",
            "exchange": "SZSE",
            "as_of_date": "2026-07-03",
            "caller_skill": "stock-deep-dive",
            "parent_stage": "RP6",
            "quality_target": "publishable_candidate",
            "no_advice_boundary": True,
            "input_paths": {
                "stock_analysis_pack": str(run / "stock_analysis_pack.yaml"),
                "forecast_model": str(run / "forecast_model.yaml"),
                "financial_metric_pack": str(run / "financial_metric_pack.csv"),
                "reviewed_claims": "",
                "reviewed_metrics": "",
                "market_snapshot": str(run / "market_snapshot.csv"),
                "peer_market_snapshot": str(run / "peer_market_snapshot.csv"),
                "valuation_input_readiness": str(run / "valuation_input_readiness.yaml"),
                "source_gap_report": "",
            },
            "known_gaps": ["TODO_MARKET_DATA", "TODO_PEER_DATA", "TODO_FORECAST_MODEL_NET_PROFIT"],
        }
    }
    (run / "valuation_request.yaml").write_text(
        yaml.safe_dump(request, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return run


def run_validator(run: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--workflow-run", str(run)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_templates_are_parseable() -> None:
    assets = REPO_ROOT / ".agents/skills/stock-deep-dive/assets"
    for name in ["market_snapshot_template.csv", "peer_market_snapshot_template.csv", "financial_metric_pack_template.csv"]:
        with (assets / name).open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            assert reader.fieldnames
    readiness = yaml.safe_load((assets / "valuation_input_readiness_template.yaml").read_text(encoding="utf-8"))
    assert "valuation_input_readiness" in readiness


def test_todo_blank_numeric_fields_pass() -> None:
    run = make_workflow_run("todo_blank_numeric_fields_pass")
    result = run_validator(run)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "accepted_with_todos" in result.stdout


def test_missing_required_columns_fail() -> None:
    run = make_workflow_run("missing_required_columns_fail")
    bad_columns = MARKET_COLUMNS[:-1]
    write_csv(run / "market_snapshot.csv", bad_columns, [{column: "" for column in bad_columns}])
    result = run_validator(run)
    assert result.returncode == 1
    assert "CSV_MISSING_COLUMNS" in result.stdout


def test_ready_status_without_sources_fails() -> None:
    run = make_workflow_run("ready_status_without_sources_fails")
    readiness = yaml.safe_load((run / "valuation_input_readiness.yaml").read_text(encoding="utf-8"))
    entry = readiness["valuation_input_readiness"]["statuses"]["financial_metric_pack"]
    entry["status"] = "ready"
    entry["source_paths"] = []
    entry["source_metric_ids"] = []
    (run / "valuation_input_readiness.yaml").write_text(
        yaml.safe_dump(readiness, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    result = run_validator(run)
    assert result.returncode == 1
    assert "READY_WITHOUT_SOURCE" in result.stdout


def test_prohibited_advice_language_fails() -> None:
    run = make_workflow_run("prohibited_advice_language_fails")
    rows = list(csv.DictReader((run / "market_snapshot.csv").open("r", encoding="utf-8", newline="")))
    rows[0]["limitations"] = "建议" + "买" + "入"
    write_csv(run / "market_snapshot.csv", MARKET_COLUMNS, rows)
    result = run_validator(run)
    assert result.returncode == 1
    assert "NO_ADVICE_VIOLATION" in result.stdout


def test_identity_mismatch_fails() -> None:
    run = make_workflow_run("identity_mismatch_fails")
    rows = list(csv.DictReader((run / "market_snapshot.csv").open("r", encoding="utf-8", newline="")))
    rows[0]["stock_code"] = "000001"
    write_csv(run / "market_snapshot.csv", MARKET_COLUMNS, rows)
    result = run_validator(run)
    assert result.returncode == 1
    assert "IDENTITY_MISMATCH" in result.stdout
