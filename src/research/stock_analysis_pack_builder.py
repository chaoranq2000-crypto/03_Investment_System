from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Sequence

import yaml

from business_breakdown_builder import build_business_breakdown
from event_calendar_builder import build_catalyst_calendar
from financial_quality_builder import build_financial_quality
from forecast_model_builder import build_forecast_model
from valuation_model_builder import build_valuation_model


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_yaml(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def build_stock_analysis_pack(
    *,
    run_dir: Path,
    claims_registry: Path,
    metrics_registry: Path,
    stock_code: str,
    stock_name: str,
    company_id: str,
    as_of_date: str,
    quality_target: str = "R3_sample_quality_draft",
) -> dict[str, object]:
    claims = read_csv_dicts(claims_registry)
    metrics = read_csv_dicts(metrics_registry)
    claim_ids = [row.get("claim_id", "") for row in claims if row.get("claim_id")]
    metric_ids = [row.get("metric_id", "") for row in metrics if row.get("metric_id")]
    financial_quality = build_financial_quality(metrics)
    business_breakdown = build_business_breakdown(claims)
    forecast_model = build_forecast_model(metrics)
    valuation_model = build_valuation_model(
        metrics=metrics,
        output_peer_csv=run_dir / "peer_comparison.csv",
        as_of_date=as_of_date,
    )
    catalyst_calendar = build_catalyst_calendar(claims, as_of_date)
    industry_context = {
        "linked_segments": ["ai_server_liquid_cooling"],
        "demand_drivers": ["AI算力密度提升带来数据中心热管理需求"],
        "supply_competition": ["TODO_SOURCE_REQUIRED: 需补同业和行业报告证据"],
        "value_chain_position": "公司披露数据中心/温控/液冷相关产品，当前按产品暴露处理。",
        "key_indicators": ["分业务收入", "毛利率", "订单/项目", "经营现金流"],
    }
    technical_sentiment_event = {
        "technical_snapshot": yaml.safe_load((run_dir / "technical_snapshot.yaml").read_text(encoding="utf-8"))
        if (run_dir / "technical_snapshot.yaml").exists()
        else {"as_of_date": as_of_date, "status": "TODO_MARKET_DATA"},
        "macro_sentiment": "TODO_SOURCE_REQUIRED",
        "industry_sentiment": "LOW_CONFIDENCE_CLUE_ONLY",
        "company_sentiment": "TODO_SOURCE_REQUIRED",
        "catalyst_calendar": catalyst_calendar,
    }
    risk_counter_evidence = {
        "risks": [
            "分业务收入和液冷收入占比缺失，不能把公司整体收入归因到液冷。",
            "结构化财务指标来自公司整体，不能替代官方披露中的业务暴露证据。",
        ],
        "counter_evidence": ["如果后续年报/公告未继续披露相关产品或订单，产品暴露判断需下调。"],
        "falsification_conditions": ["分业务表或公告显示相关业务收入贡献不足或不可持续。"],
        "tracking_items": ["下一期定期报告", "分业务收入表", "订单/客户/产能公告"],
    }
    evidence_gaps = [
        {
            "gap_id": "gap_liquid_cooling_revenue_pct",
            "target_section": "business_breakdown",
            "missing_claim_or_metric": "液冷收入占比和毛利率",
            "required_source_type": "annual_report_or_announcement_table",
            "blocking_level": "medium",
            "owner_skill": "evidence-ingest",
        }
    ]
    pack = {
        "metadata": {
            "run_id": run_dir.name,
            "stock_code": stock_code,
            "stock_name": stock_name,
            "company_id": company_id,
            "analysis_date": as_of_date,
            "quality_target": quality_target,
            "evidence_snapshot": str(run_dir / "evidence_manifest_delta.csv"),
            "claim_ids": claim_ids,
            "metric_ids": metric_ids[:20],
        },
        "core_thesis": {
            "one_sentence": "英维克的样例质量报告应围绕数据中心热管理/液冷产品暴露与公司层面财务兑现之间的证据差距展开。",
            "facts": claim_ids[:5],
            "inferences": ["产品暴露可进入观察，但收入暴露仍需分业务证据。"],
            "key_assumptions": ["AI算力热管理需求延续；公司产品线具备相关供给能力。"],
            "largest_uncertainties": ["液冷收入占比", "订单持续性", "现金流兑现"],
        },
        "financial_quality": financial_quality,
        "business_breakdown": business_breakdown,
        "industry_context": industry_context,
        "forecast_model": forecast_model,
        "valuation_model": valuation_model,
        "technical_sentiment_event": technical_sentiment_event,
        "risks_and_counter_evidence": risk_counter_evidence,
        "evidence_gaps": evidence_gaps,
    }
    component_files = {
        "stock_analysis_pack.yaml": pack,
        "financial_quality.yaml": financial_quality,
        "business_breakdown.yaml": business_breakdown,
        "segment_exposure_draft.yaml": business_breakdown["segment_links"],
        "industry_context_card.yaml": industry_context,
        "forecast_model.yaml": forecast_model,
        "valuation_model.yaml": valuation_model,
        "catalyst_calendar.yaml": catalyst_calendar,
        "risk_counter_evidence.yaml": risk_counter_evidence,
        "evidence_gap_requests.yaml": evidence_gaps,
    }
    for name, payload in component_files.items():
        write_yaml(run_dir / name, payload)
    return pack


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build stock_analysis_pack.yaml from reviewed registries.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--claims-registry", required=True)
    parser.add_argument("--metrics-registry", required=True)
    parser.add_argument("--stock-code", required=True)
    parser.add_argument("--stock-name", required=True)
    parser.add_argument("--company-id", required=True)
    parser.add_argument("--as-of-date", required=True)
    args = parser.parse_args(argv)
    pack = build_stock_analysis_pack(
        run_dir=Path(args.run_dir),
        claims_registry=Path(args.claims_registry),
        metrics_registry=Path(args.metrics_registry),
        stock_code=args.stock_code,
        stock_name=args.stock_name,
        company_id=args.company_id,
        as_of_date=args.as_of_date,
    )
    print(yaml.safe_dump(pack["metadata"], allow_unicode=True, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
