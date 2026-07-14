#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path
from typing import Any, Mapping

import yaml


WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
WORKFLOW_REL = Path("reports/workflow_runs") / WORKFLOW_ID
PERIODS = ("2026E", "2027E", "2028E")
SCENARIOS = ("bear", "base", "bull")
ANNUAL_REPORT_EVIDENCE_ID = "ev_annual_report_002837_20260421_2cbfc5"
ANNUAL_REPORT_SOURCE_PATH = "data/processed/text/002837/cninfo_2025_annual_report_full_002837_2026-04-21.txt"
SALES_VOLUME_METRIC_ID = "metric_company_cn_002837_invic_precision_thermal_management_sales_volume_2025A_11r"
SALES_VOLUME_2025 = 324_058.0


METRIC_CANDIDATE_FIELDS = [
    "metric_candidate_id",
    "source_evidence_id",
    "source_name",
    "source_type",
    "entity_type",
    "entity_id",
    "segment_id",
    "company_id",
    "stock_code",
    "metric_name",
    "metric_category",
    "period",
    "period_type",
    "value",
    "unit",
    "currency",
    "original_value_text",
    "original_unit_text",
    "table_id",
    "page_no_or_section",
    "calculation_method",
    "is_estimate",
    "is_reported",
    "confidence",
    "review_status",
    "promote_to_metric_id",
    "created_at",
    "notes",
]


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return payload


def dump_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(dict(payload), allow_unicode=True, sort_keys=False), encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path, repo_root: Path) -> str:
    try:
        value = path.relative_to(repo_root)
    except ValueError:
        value = path
    return str(value).replace("\\", "/")


def _matrix(model: Mapping[str, Any], segment_id: str, field: str, *, divisor: float = 1.0) -> dict[str, dict[str, float]]:
    return {
        scenario: {
            period: round(float(model["scenarios"][scenario][period]["segments"][segment_id][field]["value"]) / divisor, 10)
            for period in PERIODS
        }
        for scenario in SCENARIOS
    }


def _constant_matrix(value: float) -> dict[str, dict[str, float]]:
    return {scenario: {period: round(value, 10) for period in PERIODS} for scenario in SCENARIOS}


def build_segment_plan(model: Mapping[str, Any]) -> dict[str, Any]:
    historical = model["historical_anchor"]
    company_revenue = float(historical["company_revenue"])
    blended_revenue_per_unit = company_revenue / SALES_VOLUME_2025
    segments: list[dict[str, Any]] = []

    for segment_id in ("room_cooling", "cabinet_cooling"):
        historical_segment = historical["segments"][segment_id]
        revenue_matrix = _matrix(model, segment_id, "revenue")
        volume_matrix = {
            scenario: {
                period: round(revenue_matrix[scenario][period] / blended_revenue_per_unit, 10)
                for period in PERIODS
            }
            for scenario in SCENARIOS
        }
        segments.append(
            {
                "segment_id": segment_id,
                "reported_name": historical_segment["reported_name"],
                "archetype_id": "volume_price_mix",
                "method_tier": "hybrid",
                "allow_proxy": False,
                "thesis_critical_drivers": ["volume", "unit_price"],
                "driver_values": {
                    "volume": volume_matrix,
                    "unit_price": _constant_matrix(blended_revenue_per_unit),
                },
                "gross_margin": _matrix(model, segment_id, "gross_margin", divisor=100.0),
                "evidence_basis": {
                    "historical_segment_revenue_CNY": historical_segment["revenue"],
                    "company_sales_volume_units": int(SALES_VOLUME_2025),
                    "company_blended_revenue_per_unit_CNY": round(blended_revenue_per_unit, 10),
                    "source_evidence_ids": [ANNUAL_REPORT_EVIDENCE_ID],
                    "metric_ids": [SALES_VOLUME_METRIC_ID],
                    "source_path": ANNUAL_REPORT_SOURCE_PATH,
                    "calculation_method": "forecast segment revenue / 2025A company blended revenue per reported unit",
                    "claim_type": "estimate",
                    "confidence": "low",
                    "limitation": "equivalent units are a bounded estimate, not issuer-disclosed segment shipments or project count",
                },
            }
        )

    segments.append(
        {
            "segment_id": "other_businesses",
            "reported_name": historical["segments"]["other_businesses"]["reported_name"],
            "archetype_id": "volume_price_mix",
            "method_tier": "proxy",
            "allow_proxy": True,
            "proxy_reason": "issuer disclosure supports only a residual revenue line; no stable line-level volume or unit-price equation is reviewable",
            "thesis_critical_drivers": ["volume", "unit_price"],
            "proxy_revenue": _matrix(model, "other_businesses", "revenue"),
            "proxy_gross_margin": _matrix(model, "other_businesses", "gross_margin", divisor=100.0),
            "evidence_basis": {
                "source_evidence_ids": [ANNUAL_REPORT_EVIDENCE_ID],
                "source_path": ANNUAL_REPORT_SOURCE_PATH,
                "calculation_method": "audited company total minus two reported major product lines, then apply reviewed Bundle 9R scenario assumptions",
                "claim_type": "estimate",
                "confidence": "low",
            },
        }
    )
    return {
        "schema_version": 1,
        "artifact_type": "R5_bundle11r_002837_segment_driver_plan",
        "workflow_id": WORKFLOW_ID,
        "company_id": "cn_002837_invic",
        "stock_code": "002837",
        "as_of_date": "2026-07-13",
        "input_evidence_generation_id": model.get("input_evidence_generation_id"),
        "operating_model_boundary": {
            "liquid_cooling_standalone_additivity": "non_additive",
            "liquid_cooling_standalone_revenue": "MISSING_DISCLOSURE",
            "liquid_cooling_standalone_gross_margin": "MISSING_DISCLOSURE",
            "project_count_unit_value_acceptance": "TODO_SOURCE_REQUIRED",
            "proxy_share_ceiling": 0.45,
        },
        "segments": segments,
    }


def build_evidence_status(plan: Mapping[str, Any]) -> dict[str, Any]:
    status: dict[str, Any] = {}
    for segment in plan["segments"]:
        segment_id = segment["segment_id"]
        if segment["method_tier"] == "hybrid":
            volume_matrix = segment["driver_values"]["volume"]
            price_matrix = segment["driver_values"]["unit_price"]
        else:
            volume_matrix = {
                scenario: {
                    period: segment["proxy_revenue"][scenario][period]
                    / float(plan["segments"][0]["evidence_basis"]["company_blended_revenue_per_unit_CNY"])
                    for period in PERIODS
                }
                for scenario in SCENARIOS
            }
            price_matrix = _constant_matrix(float(plan["segments"][0]["evidence_basis"]["company_blended_revenue_per_unit_CNY"]))
        for driver_id, matrix in (("volume", volume_matrix), ("unit_price", price_matrix)):
            values_2026 = [float(matrix[scenario]["2026E"]) for scenario in SCENARIOS]
            status[f"{segment_id}.{driver_id}"] = {
                "status": "bounded_estimate",
                "evidence_ids": [ANNUAL_REPORT_EVIDENCE_ID],
                "metric_ids": [SALES_VOLUME_METRIC_ID],
                "range": [round(min(values_2026), 6), round(max(values_2026), 6)],
                "period": "2026E",
                "confidence": "low",
                "source_path": ANNUAL_REPORT_SOURCE_PATH,
                "calculation_method": "bounded from reported 2025A company units and reviewed Bundle 9R scenario revenue; not a disclosed segment value",
            }
    return {
        "schema_version": 1,
        "artifact_type": "R5_bundle11r_002837_evidence_status",
        "workflow_id": WORKFLOW_ID,
        "as_of_date": "2026-07-13",
        "evidence_status": status,
        "fixed_boundaries": {"sample_quality_allowed": False, "p2_allowed": False},
    }


def build_peer_pack(peer_reconciliation: Mapping[str, Any]) -> dict[str, Any]:
    peers = []
    for row in peer_reconciliation.get("rows", []):
        peers.append(
            {
                "peer_id": row.get("company_id"),
                "peer_name": row.get("company_name"),
                "source_ids": list(row.get("source_evidence_ids", [])) + [row.get("official_scope_anchor")],
                "dimensions": {},
                "hard_blocks": [
                    "liquid_cooling_revenue_purity_not_comparable",
                    "official_operating_definition_not_fully_reconciled",
                    "forward_forecast_date_not_reconciled",
                ],
                "notes": "Context only. Missing dimensions are intentionally not scored; company-level metrics cannot establish liquid-cooling operating comparability.",
            }
        )
    return {
        "schema_version": 1,
        "artifact_type": "R5_bundle11r_002837_peer_pack",
        "workflow_id": WORKFLOW_ID,
        "as_of_date": "2026-07-13",
        "valuation_method_requested": "reverse_and_scenario_valuation",
        "peer_multiple_boundary": "waived_until_at_least_three_operating_definition_compatible_peers",
        "peers": peers,
        "fixed_boundaries": {"ranking_allowed": False, "sample_quality_allowed": False, "p2_allowed": False},
    }


def build_semantic_payload(model: Mapping[str, Any], plan: Mapping[str, Any], peer_count: int) -> dict[str, Any]:
    historical = model["historical_anchor"]
    base_2026 = model["scenarios"]["base"]["2026E"]["segments"]
    base_revenue = sum(float(item["revenue"]["value"]) for item in base_2026.values())
    base_proxy = float(base_2026["other_businesses"]["revenue"]["value"])
    proxy_share = base_proxy / base_revenue
    room_revenue = float(historical["segments"]["room_cooling"]["revenue"])
    cabinet_revenue = float(historical["segments"]["cabinet_cooling"]["revenue"])
    return {
        "schema_version": 1,
        "artifact_type": "R5_bundle11r_002837_semantic_payload",
        "workflow_id": WORKFLOW_ID,
        "as_of_date": "2026-07-13",
        "section_materiality": {
            "business": "high",
            "forecast": "high",
            "financials": "medium",
            "industry": "low",
            "valuation": "medium",
            "risks": "medium",
        },
        "sections": [
            {
                "section_id": "financials",
                "text": "2025年公司营业收入60.68亿元、综合毛利率27.86%，经营现金流净额1.57亿元。11R只把公司级指标用于财务桥和营运资金约束，不把它们写成液冷分部事实。",
                "company_specific_metrics": ["2025A营业收入60.68亿元", "2025A综合毛利率27.86%", "2025A经营现金流1.57亿元"],
                "model_links": ["R5_bundle9r_financial_statement_bridge", "R5_bundle11r_operating_driver_pack.consolidated"],
                "insights": ["规模增长与现金转化必须分开验证"],
                "source_ids": [ANNUAL_REPORT_EVIDENCE_ID],
                "watchpoints": [
                    {
                        "metric": "经营现金流净额/归母净利润",
                        "trigger": "滚动十二个月低于0.5",
                        "timeframe": "未来两个报告期",
                        "disconfirming_condition": "经营现金流持续转正且应收与存货增速低于收入增速",
                    }
                ],
            },
            {
                "section_id": "business",
                "text": (
                    f"2025年机房温控和机柜温控收入分别为{room_revenue / 1e8:.2f}亿元和{cabinet_revenue / 1e8:.2f}亿元。"
                    "11R以年报披露的公司级324,058台销量为锚，将两条主要宽口径产品线拆为等价销量乘公司级混合单价；"
                    "等价销量属于bounded_estimate，不代表发行人披露的液冷项目数、出货量或订单。其他业务继续使用显式代理，液冷独立经济性保持不加总。"
                ),
                "company_specific_metrics": [f"2025A机房温控收入{room_revenue / 1e8:.2f}亿元", f"2025A机柜温控收入{cabinet_revenue / 1e8:.2f}亿元", "2025A公司级销量324058台"],
                "model_links": ["room_cooling.volume_price_mix", "cabinet_cooling.volume_price_mix", "liquid_cooling_non_additive_boundary"],
                "insights": ["宽口径销量桥可以约束报表预测，但不能替代液冷独立项目证据"],
                "source_ids": [ANNUAL_REPORT_EVIDENCE_ID, SALES_VOLUME_METRIC_ID],
                "watchpoints": [
                    {
                        "metric": "液冷项目数、单位价值与验收率",
                        "trigger": "任一指标获得可复算官方披露",
                        "timeframe": "每次定期报告和投资者关系记录更新",
                        "disconfirming_condition": "项目或产品线证据无法与宽口径收入、毛利和回款勾稽",
                    }
                ],
            },
            {
                "section_id": "industry",
                "text": "公司已披露端到端液冷产品覆盖与规模采购应用线索，但行业渗透和产品验证只有在宽口径收入、毛利与现金流中形成可复算兑现时，才能提高公司层面的结论置信度。",
                "company_specific_metrics": [f"2025A机房温控收入{room_revenue / 1e8:.2f}亿元"],
                "model_links": ["room_cooling.volume_price_mix"],
                "insights": ["行业需求证据不等于公司液冷独立收入证据"],
                "source_ids": [ANNUAL_REPORT_EVIDENCE_ID],
                "watchpoints": [
                    {
                        "metric": "机房温控收入增速与毛利率",
                        "trigger": "收入增速低于10%或毛利率低于24%",
                        "timeframe": "未来两个报告期",
                        "disconfirming_condition": "行业液冷扩张但公司宽口径机房温控收入与毛利未同步",
                    }
                ],
            },
            {
                "section_id": "forecast",
                "text": (
                    f"基准情景2026E营业收入为{base_revenue / 1e8:.2f}亿元。机房与机柜温控由等价销量和混合单价驱动，"
                    f"其他业务代理收入占比为{proxy_share:.2%}，低于45%硬上限；驱动结果与Bundle 9R宽口径分部收入和毛利逐项勾稽，"
                    "因此没有通过额外加总液冷收入来抬高公司预测。"
                ),
                "company_specific_metrics": [f"2026E基准收入{base_revenue / 1e8:.2f}亿元", f"2026E基准代理收入占比{proxy_share:.2%}"],
                "model_links": ["R5_bundle11r_operating_driver_pack", "R5_bundle9r_segment_driver_model", "R5_bundle9r_financial_statement_bridge"],
                "insights": ["经营驱动桥先约束宽口径报表，再保留液冷独立经济性缺口"],
                "source_ids": [ANNUAL_REPORT_EVIDENCE_ID, SALES_VOLUME_METRIC_ID],
                "watchpoints": [
                    {
                        "metric": "公司级代理收入占比",
                        "trigger": "高于45%",
                        "timeframe": "每次模型重算",
                        "disconfirming_condition": "两条主要业务线重新依赖宽口径收入增长代理而无经营驱动约束",
                    }
                ],
            },
            {
                "section_id": "valuation",
                "text": f"已审阅{peer_count}家候选同业，但液冷收入纯度、会计边界、期间和预测日期不能同时对齐，因此同业倍数不作为核心锚；11R继续使用Bundle 9R反向估值与情景估值解释市场隐含要求。",
                "company_specific_metrics": [f"候选同业{peer_count}家", "合格同业0家"],
                "model_links": ["R5_bundle11r_peer_eligibility", "R5_bundle9r_reverse_valuation", "R5_bundle9r_scenario_valuation"],
                "insights": ["估值方法资格先于倍数结论"],
                "source_ids": ["R5_bundle9r_peer_operating_reconciliation"],
                "watchpoints": [
                    {
                        "metric": "经营定义合格同业数量",
                        "trigger": "少于3家",
                        "timeframe": "每个估值基准日",
                        "disconfirming_condition": "同业液冷收入纯度、会计边界或预测日期无法形成同口径审阅",
                    }
                ],
            },
            {
                "section_id": "risks",
                "text": "2025年末应收账款30.54亿元、存货9.83亿元，经营现金流1.57亿元；若宽口径收入增长未转化为毛利和回款，或液冷产品验证没有形成可复算交付与验收，经营驱动模型需要下修。",
                "company_specific_metrics": ["2025A应收账款30.54亿元", "2025A存货9.83亿元", "2025A经营现金流1.57亿元"],
                "model_links": ["R5_bundle9r_financial_statement_bridge"],
                "insights": ["收入兑现必须同时接受毛利和营运资金反证"],
                "source_ids": [ANNUAL_REPORT_EVIDENCE_ID],
                "watchpoints": [
                    {
                        "metric": "应收账款与存货合计增速",
                        "trigger": "连续两个报告期高于收入增速",
                        "timeframe": "未来两个报告期",
                        "disconfirming_condition": "收入、毛利和经营现金流同步改善且资金占用增速回落",
                    }
                ],
            },
        ],
        "model_summary": {"proxy_revenue_share": round(proxy_share, 8)},
        "peer_summary": {"eligible_count": 0, "peer_multiples_used": False},
        "fixed_boundaries": {"sample_quality_allowed": False, "p2_allowed": False},
    }


def build_gap_requests() -> dict[str, Any]:
    gaps = [
        ("R5B11R-GAP-001", "liquid_cooling_project_or_delivery_capacity", "液冷项目数、交付容量或可复算等价容量未单独披露"),
        ("R5B11R-GAP-002", "liquid_cooling_unit_value", "液冷项目或产品组合的单位价值未单独披露"),
        ("R5B11R-GAP-003", "test_delivery_acceptance_revenue_cycle", "测试、交付、验收与收入确认周期缺少可复算官方口径"),
        ("R5B11R-GAP-004", "liquid_cooling_overlap_elimination", "液冷与机房/机柜宽口径收入的重叠消除规则未披露"),
        ("R5B11R-GAP-005", "liquid_cooling_gross_margin_bounds", "液冷独立毛利率上下限未披露"),
        ("R5B11R-GAP-006", "liquid_cooling_working_capital", "液冷独立回款、应收与存货占用未披露"),
    ]
    return {
        "schema_version": 1,
        "artifact_type": "R5_bundle11r_operating_evidence_gap_requests",
        "workflow_id": WORKFLOW_ID,
        "as_of_date": "2026-07-13",
        "gaps": [
            {
                "gap_id": gap_id,
                "severity": "medium",
                "status": "open",
                "target_driver": target,
                "description": description,
                "required_source_type": "issuer_official_disclosure_or_reviewed_ir_record",
                "fix_owner_skill": "evidence-ingest",
                "next_action": "保持TODO_SOURCE_REQUIRED；获得官方可复算口径后替换bounded_estimate并重跑11R",
                "blocking_for_automated_candidate": False,
                "blocking_for_sample_quality": True,
            }
            for gap_id, target, description in gaps
        ],
        "fixed_boundaries": {"sample_quality_allowed": False, "p2_allowed": False},
    }


def metric_candidate_row() -> dict[str, str]:
    return {
        "metric_candidate_id": "metriccand_company_cn_002837_invic_precision_thermal_management_sales_volume_2025A_11r",
        "source_evidence_id": ANNUAL_REPORT_EVIDENCE_ID,
        "source_name": "cninfo",
        "source_type": "annual_report",
        "entity_type": "company",
        "entity_id": "cn_002837_invic",
        "segment_id": "",
        "company_id": "cn_002837_invic",
        "stock_code": "002837",
        "metric_name": "precision_thermal_management_equipment_sales_volume",
        "metric_category": "operating_volume",
        "period": "2025A",
        "period_type": "annual",
        "value": "324058",
        "unit": "units",
        "currency": "",
        "original_value_text": "324,058",
        "original_unit_text": "台",
        "table_id": "annual_report_2025_physical_sales_inventory_table",
        "page_no_or_section": "2025年年度报告全文 第四节主营业务分析/主要销售客户和主要供应商情况之前的产销量库存量表",
        "calculation_method": "direct_reported_value",
        "is_estimate": "false",
        "is_reported": "true",
        "confidence": "high",
        "review_status": "needs_review",
        "promote_to_metric_id": SALES_VOLUME_METRIC_ID,
        "created_at": "2026-07-13T00:00:00Z",
        "notes": "公司级精密温控节能设备销量；不得直接解释为液冷、机房温控或机柜温控分部销量。",
    }


def write_metric_candidates(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=METRIC_CANDIDATE_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerow(metric_candidate_row())


def build_inputs(repo_root: Path, output_dir: Path) -> dict[str, Any]:
    run_dir = repo_root / WORKFLOW_REL
    model_path = run_dir / "R5_bundle9r_segment_driver_model.yaml"
    peer_path = run_dir / "R5_bundle9r_peer_operating_reconciliation.yaml"
    model = load_yaml(model_path)
    peer_reconciliation = load_yaml(peer_path)

    plan = build_segment_plan(model)
    outputs = {
        "metric_candidates": output_dir / "R5_bundle11r_operating_metric_candidates.csv",
        "segment_plan": output_dir / "R5_bundle11r_segment_driver_plan.yaml",
        "evidence_status": output_dir / "R5_bundle11r_evidence_status.yaml",
        "peer_pack": output_dir / "R5_bundle11r_peer_pack.yaml",
        "semantic_payload": output_dir / "R5_bundle11r_semantic_payload.yaml",
        "gap_requests": output_dir / "R5_bundle11r_operating_evidence_gap_requests.yaml",
    }
    write_metric_candidates(outputs["metric_candidates"])
    dump_yaml(outputs["segment_plan"], plan)
    dump_yaml(outputs["evidence_status"], build_evidence_status(plan))
    dump_yaml(outputs["peer_pack"], build_peer_pack(peer_reconciliation))
    dump_yaml(outputs["semantic_payload"], build_semantic_payload(model, plan, len(peer_reconciliation.get("rows", []))))
    dump_yaml(outputs["gap_requests"], build_gap_requests())

    receipt = {
        "schema_version": 1,
        "artifact_type": "R5_bundle11r_002837_input_build_receipt",
        "workflow_id": WORKFLOW_ID,
        "as_of_date": "2026-07-13",
        "input_artifacts": [
            {"path": str(model_path.relative_to(repo_root)).replace("\\", "/"), "sha256": sha256_file(model_path)},
            {"path": str(peer_path.relative_to(repo_root)).replace("\\", "/"), "sha256": sha256_file(peer_path)},
        ],
        "output_artifacts": [
            {"path": display_path(path, repo_root), "sha256": sha256_file(path)}
            for path in outputs.values()
        ],
        "method_boundary": "two major reported product lines use hybrid equivalent-unit models; residual businesses remain explicit proxy",
        "source_gap_boundary": "project count, unit value, acceptance cycle, liquid-cooling margin and working capital remain visible TODOs",
        "fixed_boundaries": {"sample_quality_allowed": False, "p2_allowed": False},
    }
    receipt_path = output_dir / "R5_bundle11r_input_build_receipt.yaml"
    dump_yaml(receipt_path, receipt)
    return {"outputs": outputs, "receipt": receipt_path}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build reviewed-evidence-bound Bundle 11R inputs for 002837")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else repo_root / WORKFLOW_REL / "bundle11r"
    result = build_inputs(repo_root, output_dir)
    print(f"output_dir={output_dir} files={len(result['outputs']) + 1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
