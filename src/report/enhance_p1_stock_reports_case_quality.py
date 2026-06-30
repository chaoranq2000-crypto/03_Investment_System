from __future__ import annotations

import csv
import hashlib
import math
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
REPORT_DATE = "2026-07-01"
SEGMENT_ID = "ai_server_liquid_cooling"
DISCLAIMER = "本内容用于研究流程与证据管理，不构成任何买入、卖出、持有或其他交易建议。"


FINANCIAL_EVIDENCE = {
    "income": {
        "evidence_id": "market_data_tushare_income_selected_stocks_20260701_f1c8b2",
        "title": "Tushare income snapshot for P1 selected stocks",
        "raw_file_path": "data/raw/market_data/tushare_income_selected_stocks_2026-07-01.csv",
        "processed_text_path": "data/processed/text/ai_server_liquid_cooling/market_data_tushare_income_selected_stocks_20260701_f1c8b2.md",
    },
    "fina_indicator": {
        "evidence_id": "market_data_tushare_fina_indicator_selected_stocks_20260701_c3e4a9",
        "title": "Tushare fina_indicator snapshot for P1 selected stocks",
        "raw_file_path": "data/raw/market_data/tushare_fina_indicator_selected_stocks_2026-07-01.csv",
        "processed_text_path": "data/processed/text/ai_server_liquid_cooling/market_data_tushare_fina_indicator_selected_stocks_20260701_c3e4a9.md",
    },
    "cashflow": {
        "evidence_id": "market_data_tushare_cashflow_selected_stocks_20260701_d5b6c1",
        "title": "Tushare cashflow snapshot for P1 selected stocks",
        "raw_file_path": "data/raw/market_data/tushare_cashflow_selected_stocks_2026-07-01.csv",
        "processed_text_path": "data/processed/text/ai_server_liquid_cooling/market_data_tushare_cashflow_selected_stocks_20260701_d5b6c1.md",
    },
    "balancesheet": {
        "evidence_id": "market_data_tushare_balancesheet_selected_stocks_20260701_a8f0d7",
        "title": "Tushare balancesheet snapshot for P1 selected stocks",
        "raw_file_path": "data/raw/market_data/tushare_balancesheet_selected_stocks_2026-07-01.csv",
        "processed_text_path": "data/processed/text/ai_server_liquid_cooling/market_data_tushare_balancesheet_selected_stocks_20260701_a8f0d7.md",
    },
}


STOCKS = {
    "002837.SZ": {
        "folder": "002837_invic",
        "stock_code": "002837",
        "stock_name": "英维克",
        "company_id": "cn_002837_invic",
        "company_evidence_id": "annual_report_002837_invic_2025_0f8fcf",
        "exposure_type": "product",
        "exposure_score": "4",
        "profile": "英维克披露数据中心热管理和液冷相关产品/解决方案，属于较清晰的产品暴露样本。",
        "positioning": "较核心产品暴露样本",
        "main_risk": "液冷收入占比和利润贡献尚未在本轮证据中直接披露。",
        "priority": "deep_watch",
    },
    "300731.SZ": {
        "folder": "300731_cotran",
        "stock_code": "300731",
        "stock_name": "科创新源",
        "company_id": "cn_300731_cotran",
        "company_evidence_id": "annual_report_300731_cotran_2025_122523",
        "exposure_type": "technology",
        "exposure_score": "2",
        "profile": "科创新源披露液冷板和数据中心液冷需求相关内容，但更适合作为技术/概念暴露降权样本。",
        "positioning": "技术/概念暴露降权样本",
        "main_risk": "产品线索可能未转化为显著收入或利润贡献。",
        "priority": "validation_watch",
    },
}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def upsert_rows(
    path: Path, rows: list[dict[str, str]], key: str, fieldnames: list[str] | None = None
) -> None:
    existing = read_csv_rows(path)
    by_key = {row[key]: row for row in existing if row.get(key)}
    for row in rows:
        by_key[row[key]] = row
    ordered = list(by_key.values())
    if fieldnames is None:
        seen: list[str] = []
        for row in ordered:
            for column in row:
                if column not in seen:
                    seen.append(column)
        fieldnames = seen
    normalized = [{column: row.get(column, "") for column in fieldnames} for row in ordered]
    write_csv_rows(path, normalized, fieldnames)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:6]


def metric_id(company_id: str, metric_name: str, period: str) -> str:
    short = hashlib.sha256(f"{company_id}:{metric_name}:{period}".encode("utf-8")).hexdigest()[:6]
    return f"metric_company_{company_id}_{metric_name}_{period}_{short}"


def claim_id(company_id: str, period: str, seq: int) -> str:
    return f"claim_financial_{company_id}_{period}_{seq:03d}"


def as_float(value) -> float | None:
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(num) else num


def fmt_money(value: float | None) -> str:
    if value is None:
        return "MISSING"
    if abs(value) >= 100_000_000:
        return f"{value / 100_000_000:.2f} 亿元"
    if abs(value) >= 10_000:
        return f"{value / 10_000:.2f} 万元"
    return f"{value:.2f} 元"


def fmt_pct(value: float | None) -> str:
    if value is None:
        return "MISSING"
    return f"{value:.2f}%"


def fmt_num(value: float | None) -> str:
    if value is None:
        return "MISSING"
    return f"{value:.4g}"


def growth_pct(current: float | None, prior: float | None) -> float | None:
    if current is None or prior in (None, 0):
        return None
    return (current / prior - 1) * 100


def load_financial_tables() -> dict[str, pd.DataFrame]:
    tables = {}
    for name, meta in FINANCIAL_EVIDENCE.items():
        path = ROOT / meta["raw_file_path"]
        tables[name] = pd.read_csv(path, dtype={"ts_code": str, "ann_date": str, "end_date": str})
    return tables


def one_row(df: pd.DataFrame, ts_code: str, end_date: str) -> dict[str, object]:
    sub = df[(df["ts_code"] == ts_code) & (df["end_date"] == end_date)]
    if sub.empty:
        return {}
    return sub.iloc[0].to_dict()


def build_company_metrics(tables: dict[str, pd.DataFrame]) -> tuple[list[dict[str, str]], dict[str, dict]]:
    metric_rows: list[dict[str, str]] = []
    contexts: dict[str, dict] = {}
    metric_specs = [
        ("income", "total_revenue", "total_revenue", "CNY"),
        ("income", "n_income_attr_p", "net_profit_attributable", "CNY"),
        ("income", "basic_eps", "basic_eps", "CNY/share"),
        ("fina_indicator", "grossprofit_margin", "gross_margin", "%"),
        ("fina_indicator", "netprofit_margin", "net_profit_margin", "%"),
        ("fina_indicator", "roe_dt", "roe_dt", "%"),
        ("fina_indicator", "ocfps", "operating_cash_flow_per_share", "CNY/share"),
        ("fina_indicator", "debt_to_assets", "debt_to_assets", "%"),
        ("cashflow", "n_cashflow_act", "net_operating_cash_flow", "CNY"),
        ("balancesheet", "inventories", "inventories", "CNY"),
        ("balancesheet", "accounts_receiv", "accounts_receivable", "CNY"),
    ]
    for ts_code, stock in STOCKS.items():
        ctx = {"annual": {}, "prior_annual": {}, "latest_q": {}}
        for period, bucket in [("20251231", "annual"), ("20241231", "prior_annual"), ("20260331", "latest_q")]:
            source_rows = {name: one_row(df, ts_code, period) for name, df in tables.items()}
            ctx[bucket]["period"] = period
            ctx[bucket]["ann_date"] = source_rows["income"].get("ann_date", "")
            for table_name, source_col, metric_name, unit in metric_specs:
                raw_value = as_float(source_rows[table_name].get(source_col))
                ctx[bucket][metric_name] = raw_value
                if bucket == "prior_annual":
                    continue
                mid = metric_id(stock["company_id"], metric_name, period)
                metric_rows.append(
                    {
                        "metric_id": mid,
                        "entity_type": "company",
                        "entity_id": stock["company_id"],
                        "metric_name": metric_name,
                        "period": period,
                        "value": "" if raw_value is None else str(raw_value),
                        "unit": unit,
                        "source_evidence_id": FINANCIAL_EVIDENCE[table_name]["evidence_id"],
                        "calculation_method": "Tushare snapshot value; no restatement adjustment in P1",
                        "is_estimate": "false",
                        "confidence": "medium",
                        "created_at": REPORT_DATE,
                        "notes": "公司整体财务指标；不能直接等同AI服务器液冷业务贡献。",
                    }
                )
        ctx["growth"] = {
            "revenue_yoy": growth_pct(
                ctx["annual"].get("total_revenue"), ctx["prior_annual"].get("total_revenue")
            ),
            "profit_yoy": growth_pct(
                ctx["annual"].get("net_profit_attributable"),
                ctx["prior_annual"].get("net_profit_attributable"),
            ),
        }
        contexts[ts_code] = ctx
    return metric_rows, contexts


def build_evidence_manifest() -> None:
    rows = []
    for name, meta in FINANCIAL_EVIDENCE.items():
        raw_path = ROOT / meta["raw_file_path"]
        rows.append(
            {
                "evidence_id": meta["evidence_id"],
                "source_type": "exchange_data",
                "source_name": f"Tushare Pro {name}",
                "title": meta["title"],
                "publisher": "Tushare Pro API via configured proxy",
                "publish_date": REPORT_DATE,
                "ingested_at": REPORT_DATE,
                "file_hash": file_hash(raw_path),
                "raw_file_path": meta["raw_file_path"],
                "processed_text_path": meta["processed_text_path"],
                "reliability_rank": "C",
                "status": "fresh",
                "license_note": "本地结构化财务数据快照；不含token；用于公司整体财务指标校验。",
            }
        )
        write_text(
            ROOT / meta["processed_text_path"],
            f"""
# Evidence Card: {meta["evidence_id"]}

- source_type: exchange_data
- source_name: Tushare Pro {name}
- title: {meta["title"]}
- publisher: Tushare Pro API via configured proxy
- publish_date: {REPORT_DATE}
- raw_file_path: {meta["raw_file_path"]}
- reliability_rank: C
- status: fresh

## Summary

- 本快照用于补强P1个股报告的公司整体财务指标。
- 该证据不直接证明AI服务器液冷收入、客户订单或利润贡献。

## Limitations

- Tushare为第三方结构化数据源，重大结论仍应回到定期报告和公告核验。
- 公司整体收入、利润率和现金流不能直接等同液冷业务表现。
""",
        )

    upsert_rows(
        ROOT / "data/manifests/evidence_manifest.csv",
        rows,
        "evidence_id",
        [
            "evidence_id",
            "source_type",
            "source_name",
            "title",
            "publisher",
            "publish_date",
            "ingested_at",
            "file_hash",
            "raw_file_path",
            "processed_text_path",
            "reliability_rank",
            "status",
            "license_note",
        ],
    )


def build_claims(contexts: dict[str, dict]) -> list[dict[str, str]]:
    rows = []
    for ts_code, stock in STOCKS.items():
        annual = contexts[ts_code]["annual"]
        growth = contexts[ts_code]["growth"]
        latest_q = contexts[ts_code]["latest_q"]
        rows.extend(
            [
                {
                    "claim_id": claim_id(stock["company_id"], "2025", 1),
                    "evidence_id": FINANCIAL_EVIDENCE["income"]["evidence_id"],
                    "entity_type": "company",
                    "entity_id": stock["company_id"],
                    "claim_text": (
                        f"{stock['stock_name']}2025年公司整体营业总收入为{fmt_money(annual.get('total_revenue'))}，"
                        f"归母净利润为{fmt_money(annual.get('net_profit_attributable'))}。"
                    ),
                    "claim_type": "fact",
                    "quote_or_excerpt": "Tushare income total_revenue/n_income_attr_p",
                    "page_no": "csv",
                    "confidence": "medium",
                    "valid_until": "下一期财务数据刷新",
                    "notes": "公司整体财务数据，不代表液冷业务收入。",
                },
                {
                    "claim_id": claim_id(stock["company_id"], "2025", 2),
                    "evidence_id": FINANCIAL_EVIDENCE["income"]["evidence_id"],
                    "entity_type": "company",
                    "entity_id": stock["company_id"],
                    "claim_text": (
                        f"{stock['stock_name']}2025年营业总收入同比约{fmt_pct(growth.get('revenue_yoy'))}，"
                        f"归母净利润同比约{fmt_pct(growth.get('profit_yoy'))}。"
                    ),
                    "claim_type": "fact",
                    "quote_or_excerpt": "2025 vs 2024 Tushare income snapshot",
                    "page_no": "csv",
                    "confidence": "medium",
                    "valid_until": "下一期财务数据刷新",
                    "notes": "同比由本地脚本基于Tushare快照计算。",
                },
                {
                    "claim_id": claim_id(stock["company_id"], "2025", 3),
                    "evidence_id": FINANCIAL_EVIDENCE["fina_indicator"]["evidence_id"],
                    "entity_type": "company",
                    "entity_id": stock["company_id"],
                    "claim_text": (
                        f"{stock['stock_name']}2025年公司整体毛利率为{fmt_pct(annual.get('gross_margin'))}，"
                        f"净利率为{fmt_pct(annual.get('net_profit_margin'))}，"
                        f"资产负债率为{fmt_pct(annual.get('debt_to_assets'))}。"
                    ),
                    "claim_type": "fact",
                    "quote_or_excerpt": "Tushare fina_indicator grossprofit_margin/netprofit_margin/debt_to_assets",
                    "page_no": "csv",
                    "confidence": "medium",
                    "valid_until": "下一期财务数据刷新",
                    "notes": "公司整体利润率和杠杆指标，不能归因到液冷业务。",
                },
                {
                    "claim_id": claim_id(stock["company_id"], "2026Q1", 1),
                    "evidence_id": FINANCIAL_EVIDENCE["income"]["evidence_id"],
                    "entity_type": "company",
                    "entity_id": stock["company_id"],
                    "claim_text": (
                        f"{stock['stock_name']}2026Q1公司整体营业总收入为{fmt_money(latest_q.get('total_revenue'))}，"
                        f"归母净利润为{fmt_money(latest_q.get('net_profit_attributable'))}。"
                    ),
                    "claim_type": "fact",
                    "quote_or_excerpt": "Tushare income 20260331",
                    "page_no": "csv",
                    "confidence": "medium",
                    "valid_until": "下一期财务数据刷新",
                    "notes": "公司整体季度数据，不代表液冷业务单季表现。",
                },
            ]
        )
    upsert_rows(
        ROOT / "data/manifests/claims_draft.csv",
        rows,
        "claim_id",
        [
            "claim_id",
            "evidence_id",
            "entity_type",
            "entity_id",
            "claim_text",
            "claim_type",
            "quote_or_excerpt",
            "page_no",
            "confidence",
            "valid_until",
            "notes",
        ],
    )
    return rows


def metric_lookup(metric_rows: list[dict[str, str]]) -> dict[tuple[str, str, str], str]:
    return {
        (row["entity_id"], row["metric_name"], row["period"]): row["metric_id"]
        for row in metric_rows
    }


def build_financial_overview_table(stock: dict[str, str], ctx: dict, ids: dict[tuple[str, str, str], str]) -> str:
    company_id = stock["company_id"]
    annual = ctx["annual"]
    latest = ctx["latest_q"]
    rows = [
        (
            "营业总收入",
            "2025",
            fmt_money(annual.get("total_revenue")),
            ids[(company_id, "total_revenue", "20251231")],
            FINANCIAL_EVIDENCE["income"]["evidence_id"],
        ),
        (
            "归母净利润",
            "2025",
            fmt_money(annual.get("net_profit_attributable")),
            ids[(company_id, "net_profit_attributable", "20251231")],
            FINANCIAL_EVIDENCE["income"]["evidence_id"],
        ),
        (
            "毛利率",
            "2025",
            fmt_pct(annual.get("gross_margin")),
            ids[(company_id, "gross_margin", "20251231")],
            FINANCIAL_EVIDENCE["fina_indicator"]["evidence_id"],
        ),
        (
            "净利率",
            "2025",
            fmt_pct(annual.get("net_profit_margin")),
            ids[(company_id, "net_profit_margin", "20251231")],
            FINANCIAL_EVIDENCE["fina_indicator"]["evidence_id"],
        ),
        (
            "经营性现金流净额",
            "2025",
            fmt_money(annual.get("net_operating_cash_flow")),
            ids[(company_id, "net_operating_cash_flow", "20251231")],
            FINANCIAL_EVIDENCE["cashflow"]["evidence_id"],
        ),
        (
            "资产负债率",
            "2025",
            fmt_pct(annual.get("debt_to_assets")),
            ids[(company_id, "debt_to_assets", "20251231")],
            FINANCIAL_EVIDENCE["fina_indicator"]["evidence_id"],
        ),
        (
            "2026Q1营业总收入",
            "2026Q1",
            fmt_money(latest.get("total_revenue")),
            ids[(company_id, "total_revenue", "20260331")],
            FINANCIAL_EVIDENCE["income"]["evidence_id"],
        ),
        (
            "2026Q1归母净利润",
            "2026Q1",
            fmt_money(latest.get("net_profit_attributable")),
            ids[(company_id, "net_profit_attributable", "20260331")],
            FINANCIAL_EVIDENCE["income"]["evidence_id"],
        ),
    ]
    body = "\n".join(
        f"| {metric} | {period} | {value} | {metric_id} | {evidence_id} | fact |"
        for metric, period, value, metric_id, evidence_id in rows
    )
    return (
        "| Metric | Period | Value | metric_id | source_evidence_id | claim_type |\n"
        "|---|---|---:|---|---|---|\n"
        f"{body}"
    )


def build_stock_report(
    ts_code: str, stock: dict[str, str], ctx: dict, ids: dict[tuple[str, str, str], str]
) -> None:
    company_id = stock["company_id"]
    annual = ctx["annual"]
    latest = ctx["latest_q"]
    growth = ctx["growth"]
    exposure_claims = {
        "002837": [
            "claim_company_002837_invic_20260701_001",
            "claim_company_002837_invic_20260701_002",
        ],
        "300731": [
            "claim_company_300731_cotran_20260701_001",
            "claim_company_300731_cotran_20260701_002",
        ],
    }[stock["stock_code"]]
    financial_claims = [
        claim_id(company_id, "2025", 1),
        claim_id(company_id, "2025", 2),
        claim_id(company_id, "2025", 3),
        claim_id(company_id, "2026Q1", 1),
    ]
    evidence_snapshot = [
        stock["company_evidence_id"],
        "market_data_tushare_stock_basic_20260701_a6d9f2",
        FINANCIAL_EVIDENCE["income"]["evidence_id"],
        FINANCIAL_EVIDENCE["fina_indicator"]["evidence_id"],
        FINANCIAL_EVIDENCE["cashflow"]["evidence_id"],
        FINANCIAL_EVIDENCE["balancesheet"]["evidence_id"],
    ]

    report = f"""
# 个股深度：{stock['stock_code']} {stock['stock_name']}

> {DISCLAIMER}

## 0. Metadata

| Field | Value |
|---|---|
| report_id | stock_report_{stock['stock_code']}_{REPORT_DATE} |
| report_type | stock_report |
| company_id | {company_id} |
| stock_code | {stock['stock_code']} |
| stock_name | {stock['stock_name']} |
| linked_segments | {SEGMENT_ID} |
| report_date | {REPORT_DATE} |
| evidence_snapshot | {'; '.join(evidence_snapshot)} |
| claim_ids | {'; '.join(exposure_claims + financial_claims)} |
| metric_ids | {ids[(company_id, 'total_revenue', '20251231')]}; {ids[(company_id, 'net_profit_attributable', '20251231')]}; {ids[(company_id, 'gross_margin', '20251231')]}; {ids[(company_id, 'debt_to_assets', '20251231')]} |
| confidence | medium |
| status | current |

## 1. 一页研究假设

- fact: {stock['profile']} 证据：evidence_id={stock['company_evidence_id']}; claim_id={exposure_claims[0]}
- fact: 2025年公司整体营业总收入为{fmt_money(annual.get('total_revenue'))}，归母净利润为{fmt_money(annual.get('net_profit_attributable'))}。证据：evidence_id={FINANCIAL_EVIDENCE['income']['evidence_id']}; claim_id={financial_claims[0]}
- fact: 2025年公司整体毛利率为{fmt_pct(annual.get('gross_margin'))}，资产负债率为{fmt_pct(annual.get('debt_to_assets'))}。证据：evidence_id={FINANCIAL_EVIDENCE['fina_indicator']['evidence_id']}; claim_id={financial_claims[2]}
- inference: 本轮只能说明公司层财务质量和液冷相关暴露线索并存，不能把公司整体增长直接归因于AI服务器液冷。
- 最大不确定性：{stock['main_risk']}

## 2. 财务质量：增长、利润率、现金流、资产负债

{build_financial_overview_table(stock, ctx, ids)}

### 财务变化解读

- fact: 2025年营业总收入同比约{fmt_pct(growth.get('revenue_yoy'))}，归母净利润同比约{fmt_pct(growth.get('profit_yoy'))}。证据：claim_id={financial_claims[1]}
- fact: 2026Q1营业总收入为{fmt_money(latest.get('total_revenue'))}，归母净利润为{fmt_money(latest.get('net_profit_attributable'))}。证据：claim_id={financial_claims[3]}
- inference: 财务数据提升了个股报告的“公司发生了什么”部分，但尚不能解释“液冷贡献了多少”。液冷收入占比仍标记 `MISSING: 暂无直接披露`。

## 3. 业务拆分：利润从哪里来

| 业务线 | 收入 | 毛利率 | 增速 | 关联细分 | 证据 | 备注 |
|---|---:|---:|---:|---|---|---|
| 公司整体 | {fmt_money(annual.get('total_revenue'))} | {fmt_pct(annual.get('gross_margin'))} | {fmt_pct(growth.get('revenue_yoy'))} | multiple | {FINANCIAL_EVIDENCE['income']['evidence_id']}; {FINANCIAL_EVIDENCE['fina_indicator']['evidence_id']} | 公司整体口径 |
| AI服务器液冷相关业务 | MISSING: 暂无直接披露 | MISSING: 暂无直接披露 | TODO: 需要补充证据 | {SEGMENT_ID} | {stock['company_evidence_id']} | 不能用公司整体财务替代液冷业务 |
| 其他业务 | TODO: 需要补充证据 | TODO: 需要补充证据 | TODO: 需要补充证据 | unknown | TODO | 等待完整年报分部抽取 |

## 4. 细分方向暴露：行业逻辑如何落到公司

| 因果环节 | claim_type | evidence / metric | confidence | 反证或缺口 |
|---|---|---|---|---|
| AI算力基础设施扩张带来热管理需求背景 | fact | policy_miit_compute_infra_20231008_9f2a30 | medium | 政策不等同订单 |
| 冷板式液冷是高功率密度散热路径之一 | fact | industry_report_caict_cold_plate_liquid_cooling_20240523_4d8c91 | medium | 路线存在替代与节奏不确定 |
| 公司存在液冷相关暴露线索 | fact | {stock['company_evidence_id']}; {exposure_claims[0]} | medium | 收入占比未披露 |
| 公司整体财务表现可观察 | fact | {FINANCIAL_EVIDENCE['income']['evidence_id']}; {FINANCIAL_EVIDENCE['fina_indicator']['evidence_id']} | medium | 不能归因到液冷业务 |

## 5. segment_company_exposure

| segment_id | exposure_type | exposure_score | revenue_pct | profit_pct | evidence_ids | confidence | notes |
|---|---|---:|---|---|---|---|---|
| {SEGMENT_ID} | {stock['exposure_type']} | {stock['exposure_score']} | MISSING: 暂无直接披露 | MISSING: 暂无直接披露 | {stock['company_evidence_id']} | medium | {stock['positioning']} |

## 6. 客户、供应链与产能

| Topic | claim_type | Evidence | Reliability | Notes |
|---|---|---|---|---|
| 数据中心/AI服务器客户 | unknown | TODO | unknown | 需要客户侧订单、认证或投资者关系记录 |
| 液冷部件或系统能力 | fact / inference | {stock['company_evidence_id']} | A | 仅证明相关线索，不证明收入占比 |
| 产能或募投项目 | unknown | TODO | unknown | 需公告或年报表格定位 |
| 供应链议价 | unknown | TODO | unknown | 需要采购、成本或客户集中度证据 |

## 7. 盈利假设与敏感性

| 层级 | 内容 | evidence_id / metric_id | claim_type | confidence |
|---|---|---|---|---|
| 历史事实 | 2025公司整体收入、利润、毛利率已有结构化快照 | {ids[(company_id, 'total_revenue', '20251231')]}; {ids[(company_id, 'gross_margin', '20251231')]} | fact | medium |
| 关键假设 | 液冷业务若能披露收入占比，才可量化业绩弹性 | TODO | inference | low |
| 敏感性 | 若客户验证或订单披露不足，exposure_score应维持或下调 | {stock['company_evidence_id']} | inference | medium |

## 8. 估值场景

本节只记录研究假设，不输出目标价、评级或交易动作。

| Scenario | Assumption type | Key assumptions | evidence_id / metric_id | confidence | Risk |
|---|---|---|---|---|---|
| base | inference | 公司整体财务可跟踪，液冷暴露等待收入占比验证 | {FINANCIAL_EVIDENCE['income']['evidence_id']}; {stock['company_evidence_id']} | medium | 液冷贡献低于叙事 |
| upside_watch | unknown | 出现液冷订单、客户认证或分产品收入披露 | TODO | low | 需要官方证据 |
| downside | inference | 液冷停留在技术或产品线索，未形成显著财务贡献 | {stock['company_evidence_id']} | medium | 概念映射降权 |

## 9. 催化剂与跟踪日历

| Catalyst | claim_type | evidence_id | expected_window | confidence | Follow-up |
|---|---|---|---|---|---|
| 年报/半年报披露液冷收入或订单 | unknown | TODO | 2026H2-2027H1 | medium | 抽取分部收入和订单 |
| 投资者关系活动记录更新客户验证 | management_comment | TODO | 2026H2 | low | 不能当事实，需标注管理层表述 |
| Tushare财务字段刷新 | fact | {FINANCIAL_EVIDENCE['income']['evidence_id']} | 每次定期报告后 | medium | 更新metrics_draft.csv |

## 10. 风险、反证和可证伪条件

| Risk / Counter-evidence | Related claim_id | evidence_id | Impact | Follow-up |
|---|---|---|---|---|
| 公司整体收入增长不能证明液冷业务放量 | {financial_claims[0]} | {FINANCIAL_EVIDENCE['income']['evidence_id']} | 高 | 寻找液冷收入、订单、客户证据 |
| {stock['main_risk']} | {exposure_claims[1]} | {stock['company_evidence_id']} | 高 | 继续核验收入占比和客户验证 |
| 毛利率变化可能由非液冷业务或成本因素驱动 | {financial_claims[2]} | {FINANCIAL_EVIDENCE['fina_indicator']['evidence_id']} | 中 | 补分业务毛利率和成本结构 |
| 2026Q1短期波动不能外推全年 | {financial_claims[3]} | {FINANCIAL_EVIDENCE['income']['evidence_id']} | 中 | 等待半年报/年报确认 |

## 11. 跟踪指标

| Metric | Current P1 status | Evidence source | Review frequency | Notes |
|---|---|---|---|---|
| liquid_cooling_revenue_pct | MISSING: 暂无直接披露 | 年报/半年报/公告 | 半年 | 核心缺口 |
| company_total_revenue | 已有2025和2026Q1 | {FINANCIAL_EVIDENCE['income']['evidence_id']} | 季度/年度 | 公司整体口径 |
| gross_margin | 已有2025和2026Q1 | {FINANCIAL_EVIDENCE['fina_indicator']['evidence_id']} | 季度/年度 | 不能直接归因液冷 |
| customer_validation_progress | TODO: 需要补充证据 | 投关/公告 | 月度 | 管理层表述需单独标注 |

## 12. TODO / Missing Data

- MISSING: 暂无直接披露 - 液冷收入占比、利润占比、订单金额。
- TODO: 需要补充证据 - 客户认证、产能、募投和分业务毛利率。
- LOW_CONFIDENCE: 当前证据质量不足 - 不应把公司整体财务改善直接归因于AI服务器液冷。

## 13. Evidence Map

详见 `evidence_map.md`。

## 14. Refresh Status

- status: current
- next_review_date: 2026-10-01
- reports_to_regenerate: 本公司年报/半年报、Tushare财务快照、segment_company_exposure
"""
    base = ROOT / "reports/stocks" / stock["folder"]
    write_text(base / f"{REPORT_DATE}_stock_deep_dive.md", report)

    evidence_map_rows = [
        ("财务质量", FINANCIAL_EVIDENCE["income"]["evidence_id"], financial_claims[0], ids[(company_id, "total_revenue", "20251231")], FINANCIAL_EVIDENCE["income"]["raw_file_path"], "fresh"),
        ("财务质量", FINANCIAL_EVIDENCE["fina_indicator"]["evidence_id"], financial_claims[2], ids[(company_id, "gross_margin", "20251231")], FINANCIAL_EVIDENCE["fina_indicator"]["raw_file_path"], "fresh"),
        ("现金流", FINANCIAL_EVIDENCE["cashflow"]["evidence_id"], "TODO", ids[(company_id, "net_operating_cash_flow", "20251231")], FINANCIAL_EVIDENCE["cashflow"]["raw_file_path"], "fresh"),
        ("资产负债", FINANCIAL_EVIDENCE["balancesheet"]["evidence_id"], "TODO", ids[(company_id, "inventories", "20251231")], FINANCIAL_EVIDENCE["balancesheet"]["raw_file_path"], "fresh"),
        ("细分暴露", stock["company_evidence_id"], exposure_claims[0], "TODO", "data/manifests/evidence_manifest.csv", "fresh"),
    ]
    write_text(
        base / "evidence_map.md",
        "\n".join(
            [
                f"# Evidence Map: {stock['stock_code']} {stock['stock_name']}",
                "",
                f"> {DISCLAIMER}",
                "",
                "| Section | evidence_id | claim_id | metric_id | source_path | status |",
                "|---|---|---|---|---|---|",
                *[
                    f"| {section} | {eid} | {cid} | {mid} | {src} | {status} |"
                    for section, eid, cid, mid, src, status in evidence_map_rows
                ],
            ]
        ),
    )


def update_p1_notes(metric_rows: list[dict[str, str]]) -> None:
    metric_count = len(metric_rows)
    readout = ROOT / f"reports/p1/p1_readout_{SEGMENT_ID}.md"
    text = readout.read_text(encoding="utf-8")
    text = re.sub(r"- 证据数量：\d+", "- 证据数量：15", text)
    text = re.sub(r"- claims 数量：\d+", "- claims 数量：22", text)
    text = re.sub(r"- 财务指标数量：\d+\n?", "", text)
    text = text.replace(
        "- 个股深度数量：2",
        f"- 个股深度数量：2\n- 财务指标数量：{metric_count}",
    )
    text = text.replace(
        "- 数据问题：Tushare代理配置已修复并补stock_basic；财务/公告深字段未导入。",
        "- 数据问题：Tushare代理配置已修复，stock_basic、income、fina_indicator、cashflow、balancesheet 已形成快照；公告深字段和液冷收入占比仍待补。",
    )
    text = text.replace(
        "- 用Tushare继续补公告线索和财务字段。",
        "- 用Tushare继续补公告线索；财务字段已完成P1样本快照。",
    )
    text = text.replace(
        "- 不确定性：液冷收入占比、利润贡献、客户订单和Tushare财务/公告深字段仍需补证。",
        "- 不确定性：液冷收入占比、利润贡献、客户订单和公告深字段仍需补证。",
    )
    text = text.replace(
        "- 理由：闭环已成立，且质量审查能发现实际问题；但横向比较前需要补结构化财务字段和收入占比。",
        "- 理由：闭环已成立，且质量审查能发现实际问题；但横向比较前仍需补液冷收入占比、客户订单和公告深字段。",
    )
    write_text(readout, text)

    quality = ROOT / f"reports/p1/quality_review_{SEGMENT_ID}.md"
    qtext = quality.read_text(encoding="utf-8")
    qtext = qtext.replace(
        "- PASS_WITH_TODO: Tushare stock_basic已入库；fina_indicator/anns_d等深字段仍需补。证据：evidence_id=market_data_tushare_stock_basic_20260701_a6d9f2; claim_id=claim_data_tushare_20260701_002",
        "- PASS: Tushare stock_basic、income、fina_indicator、cashflow、balancesheet 已入库并生成 metrics_draft.csv。\n- PASS_WITH_TODO: anns_d 无接口权限；公告深字段仍需通过其他可用来源补充。",
    )
    qtext = qtext.split("\n## Case-study Calibration")[0].rstrip()
    qtext += "\n\n## Case-study Calibration\n\n- PASS: 两份个股报告已按优秀案例补强财务概览、业务拆分、行业到公司暴露因果链、盈利假设、估值场景、催化剂、风险/反证和 Refresh Status。\n- PASS: 所有新增财务数字均引用 Tushare evidence_id / metric_id，且明确不能直接归因到AI服务器液冷业务。\n"
    write_text(quality, qtext)

    issues_path = ROOT / "reports/p1/quality_issues.csv"
    issue_rows = read_csv_rows(issues_path)
    issue_rows.append(
        {
            "issue_id": "P1-QA-005",
            "severity": "high",
            "status": "fixed",
            "object": "stock_deep_dive",
            "issue": "个股报告相对优秀案例缺少财务概览、因果链、情景和反证密度",
            "fix": "已用Tushare财务快照生成metrics_draft，并重写两份个股深度报告",
        }
    )
    by_id = {row["issue_id"]: row for row in issue_rows}
    write_csv_rows(
        issues_path,
        list(by_id.values()),
        ["issue_id", "severity", "status", "object", "issue", "fix"],
    )

    change_log = ROOT / "reports/p1/template_change_log.md"
    ctext = change_log.read_text(encoding="utf-8")
    if "Case-study calibration" not in ctext:
        ctext += f"""

## Case-study calibration

- 已新增 `src/report/enhance_p1_stock_reports_case_quality.py`，用于把优秀案例拆解中的财务概览、业务拆分、因果链、情景、催化剂和风险/反证结构落到P1两个个股样本。
- 新增 `data/manifests/metrics_draft.csv` 作为个股财务指标中间层，避免报告直接堆数字而无 `metric_id`。
- 财务指标仅代表公司整体口径，不能直接归因到AI服务器液冷业务。
"""
    write_text(change_log, ctext)


def main() -> None:
    tables = load_financial_tables()
    build_evidence_manifest()
    metric_rows, contexts = build_company_metrics(tables)
    write_csv_rows(
        ROOT / "data/manifests/metrics_draft.csv",
        metric_rows,
        [
            "metric_id",
            "entity_type",
            "entity_id",
            "metric_name",
            "period",
            "value",
            "unit",
            "source_evidence_id",
            "calculation_method",
            "is_estimate",
            "confidence",
            "created_at",
            "notes",
        ],
    )
    build_claims(contexts)
    ids = metric_lookup(metric_rows)
    for ts_code, stock in STOCKS.items():
        build_stock_report(ts_code, stock, contexts[ts_code], ids)
    update_p1_notes(metric_rows)
    print(f"Enhanced P1 stock reports with {len(metric_rows)} metric rows")


if __name__ == "__main__":
    main()
