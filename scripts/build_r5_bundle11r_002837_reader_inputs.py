#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
from pathlib import Path
from typing import Any, Mapping

import yaml


WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
WORKFLOW_REL = Path("reports/workflow_runs") / WORKFLOW_ID
AS_OF_DATE = "2026-07-13"
SCENARIOS = ("bear", "base", "bull")
PERIODS = ("2026E", "2027E", "2028E")
RECONCILIATION_TOLERANCE_CNY = 0.02


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return payload


def dump_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(dict(payload), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )


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


def split_runtime_result(runtime: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    if runtime.get("decision") != "candidate_inputs_ready":
        raise ValueError("Bundle 11R runtime is not ready for Reader construction")
    severe = [
        issue
        for issue in runtime.get("all_issues") or []
        if str(issue.get("severity") or "").lower() in {"critical", "high"}
    ]
    if severe:
        raise ValueError(f"Bundle 11R runtime contains {len(severe)} critical/high issues")

    mapping = {
        "research_question_matrix": "R5_bundle11r_research_question_matrix.yaml",
        "operating_driver_pack": "R5_bundle11r_operating_driver_pack.yaml",
        "peer_eligibility": "R5_bundle11r_peer_eligibility.yaml",
        "semantic_quality": "R5_bundle11r_semantic_quality_scorecard.yaml",
        "backflow_plan": "R5_bundle11r_backflow_plan.yaml",
    }
    outputs: dict[str, Path] = {}
    for source_key, filename in mapping.items():
        payload = runtime.get(source_key)
        if not isinstance(payload, Mapping):
            raise ValueError(f"runtime result is missing {source_key}")
        path = output_dir / filename
        dump_yaml(path, payload)
        outputs[source_key] = path
    return outputs


def build_reconciliation(
    model: Mapping[str, Any],
    runtime: Mapping[str, Any],
    *,
    runtime_sha256: str,
    model_generation_id: str,
) -> dict[str, Any]:
    operating = runtime["operating_driver_pack"]
    runtime_index = {
        (str(row["scenario"]), str(row["period"])): row
        for row in operating.get("consolidated") or []
    }
    rows: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        for period in PERIODS:
            model_period = model["scenarios"][scenario][period]
            segments = model_period["segments"]
            model_revenue = sum(float(segment["revenue"]["value"]) for segment in segments.values())
            model_gross_profit = sum(float(segment["gross_profit"]["value"]) for segment in segments.values())
            runtime_row = runtime_index[(scenario, period)]
            revenue_difference = float(runtime_row["revenue"]) - model_revenue
            gross_profit_difference = float(runtime_row["gross_profit"]) - model_gross_profit
            within_tolerance = (
                abs(revenue_difference) <= RECONCILIATION_TOLERANCE_CNY
                and abs(gross_profit_difference) <= RECONCILIATION_TOLERANCE_CNY
            )
            rows.append(
                {
                    "scenario": scenario,
                    "period": period,
                    "bundle9r_revenue_CNY": round(model_revenue, 6),
                    "bundle11r_revenue_CNY": round(float(runtime_row["revenue"]), 6),
                    "revenue_difference_CNY": round(revenue_difference, 6),
                    "bundle9r_gross_profit_CNY": round(model_gross_profit, 6),
                    "bundle11r_gross_profit_CNY": round(float(runtime_row["gross_profit"]), 6),
                    "gross_profit_difference_CNY": round(gross_profit_difference, 6),
                    "proxy_revenue_share": float(runtime_row["proxy_revenue_share"]),
                    "within_tolerance": within_tolerance,
                }
            )

    passed = sum(bool(row["within_tolerance"]) for row in rows)
    return {
        "schema_version": 1,
        "artifact_type": "R5_bundle11r_operating_to_9r_reconciliation",
        "workflow_id": WORKFLOW_ID,
        "as_of_date": AS_OF_DATE,
        "input_model_generation_id": model_generation_id,
        "input_runtime_result_sha256": runtime_sha256,
        "decision": "pass" if passed == len(rows) else "needs_fix",
        "method": "sum Bundle 9R broad-line segment revenue and gross profit, then compare with Bundle 11R consolidated operating-driver output",
        "tolerance_CNY": RECONCILIATION_TOLERANCE_CNY,
        "summary": {
            "row_count": len(rows),
            "passed_row_count": passed,
            "max_absolute_revenue_difference_CNY": round(
                max(abs(float(row["revenue_difference_CNY"])) for row in rows), 6
            ),
            "max_absolute_gross_profit_difference_CNY": round(
                max(abs(float(row["gross_profit_difference_CNY"])) for row in rows), 6
            ),
            "max_proxy_revenue_share": max(float(row["proxy_revenue_share"]) for row in rows),
            "base_2026_proxy_revenue_share": next(
                float(row["proxy_revenue_share"])
                for row in rows
                if row["scenario"] == "base" and row["period"] == "2026E"
            ),
            "forecast_and_valuation_values_changed": False,
        },
        "rows": rows,
        "interpretation_boundary": (
            "11R decomposes the existing 9R broad-line model. It does not add standalone liquid-cooling revenue "
            "or replace the reviewed reverse/scenario valuation inputs."
        ),
        "fixed_boundaries": {"sample_quality_allowed": False, "p2_allowed": False},
    }


def _section(reader_input: Mapping[str, Any], section_id: str) -> dict[str, Any]:
    for section in reader_input.get("sections") or []:
        if section.get("section_id") == section_id:
            return section
    raise KeyError(section_id)


def _add_refs(section: dict[str, Any], *refs: str) -> None:
    declared = list(section.get("references") or [])
    for ref in refs:
        if ref not in declared:
            declared.append(ref)
    section["references"] = declared


def _reference(
    display_id: str,
    source_id: str,
    title: str,
    category: str,
    claim_type: str,
    source_path: str,
    limitation: str,
    *,
    period: str = AS_OF_DATE,
    confidence: str = "medium",
) -> dict[str, Any]:
    return {
        "display_reference_id": display_id,
        "underlying_source_id": source_id,
        "source_title": title,
        "source_category": category,
        "independent": False,
        "claim_type": claim_type,
        "period": period,
        "source_path": source_path,
        "confidence": confidence,
        "limitation": limitation,
    }


def build_reader_input(
    old_reader_input: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    *,
    runtime_sha256: str,
) -> dict[str, Any]:
    reader_input = copy.deepcopy(dict(old_reader_input))
    reader_input["artifact_type"] = "R5_bundle11r_reader_input_pack"
    reader_input["human_review_status"] = "pending"
    reader_input["source_generation"]["runtime_result_sha256"] = runtime_sha256
    reader_input["source_generation"]["runtime_decision"] = "candidate_inputs_ready"
    reader_input["source_generation"]["historical_reader_status"] = "superseded_reference_only"
    reader_input["source_generation"]["reader_revision_reason"] = (
        "11R operating-driver, peer-eligibility and semantic-quality outputs added without changing 9R forecasts"
    )

    ref_paths = {
        "E23": "reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle11r/R5_bundle11r_operating_metric_registry.csv",
        "E24": "reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle11r/R5_bundle11r_research_question_matrix.yaml",
        "E25": "reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle11r/R5_bundle11r_operating_driver_pack.yaml",
        "E26": "reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle11r/R5_bundle11r_peer_eligibility.yaml",
        "E27": "reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle11r/R5_bundle11r_semantic_quality_scorecard.yaml",
        "E28": "reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle11r/R5_bundle11r_operating_to_9r_reconciliation.yaml",
    }
    reader_input["reference_catalog"].extend(
        [
            _reference(
                "E23",
                "metric_company_cn_002837_invic_precision_thermal_management_sales_volume_2025A_11r",
                "2025年公司级精密温控节能设备销量",
                "issuer",
                "fact",
                ref_paths["E23"],
                "公司级销量，不代表液冷、机房温控或机柜温控分部销量",
                period="2025A",
                confidence="high",
            ),
            _reference(
                "E24",
                "r5_bundle11r_research_question_matrix_002837",
                "11R经营问题与缺口矩阵",
                "model",
                "estimate_and_unknown",
                ref_paths["E24"],
                "关键量价为有边界估计；产品组合和单位成本等支持性问题仍缺失",
                confidence="low",
            ),
            _reference(
                "E25",
                "r5_bundle11r_operating_driver_pack_002837",
                "11R经营驱动包",
                "model",
                "estimate",
                ref_paths["E25"],
                "等价销量使用公司级混合单价，只约束宽口径业务线，不代表披露分部出货",
                confidence="low",
            ),
            _reference(
                "E26",
                "r5_bundle11r_peer_eligibility_002837",
                "11R同业方法资格审阅",
                "peer",
                "analytical_view",
                ref_paths["E26"],
                "四家候选对象均缺少同口径液冷纯度、会计边界和预测日期，不能用于倍数锚",
                confidence="low",
            ),
            _reference(
                "E27",
                "r5_bundle11r_semantic_quality_scorecard_002837",
                "11R研究语义完整性检查",
                "quality",
                "analytical_view",
                ref_paths["E27"],
                "检查通过不补齐缺失证据，也不代表人工复核结论",
            ),
            _reference(
                "E28",
                "r5_bundle11r_operating_to_9r_reconciliation_002837",
                "11R经营桥与9R预测逐项勾稽",
                "model",
                "estimate",
                ref_paths["E28"],
                "只证明既有宽口径收入和毛利未被改写，不验证预测假设一定兑现",
            ),
        ]
    )

    reader_input["claims"].extend(
        [
            {
                "claim_id": "r5b11r_operating_driver_boundary",
                "topic": "broad_line_operating_driver_bridge",
                "claim_type": "estimate",
                "additivity": "non_additive",
                "confidence": "low",
                "falsification_condition": "发行人披露分部出货、单价或项目量后替换等价销量并重算",
                "refs": ["E23", "E24", "E25", "E28"],
            },
            {
                "claim_id": "r5b11r_peer_method_qualification",
                "topic": "peer_valuation_method_eligibility",
                "claim_type": "analytical_view",
                "peer_confidence": "context_only",
                "ranking_performed": False,
                "falsification_condition": "至少三家同业形成同期间、同经营定义和同预测日期的官方口径后重审",
                "refs": ["E26"],
            },
        ]
    )

    executive = _section(reader_input, "executive_summary")
    executive["facts"].append(
        {
            "text": (
                "11R将机房与机柜温控拆成等价量价桥，其他业务保留显式代理；三种情景的代理收入占比最高约9.52%，"
                "并在分币级容差内与原9R宽口径收入和毛利勾稽，不额外增加液冷收入。"
            ),
            "refs": ["E24", "E25", "E28"],
        }
    )
    _add_refs(executive, "E24", "E25", "E28")

    segment = _section(reader_input, "segment_economics")
    segment["facts"].append(
        {
            "text": (
                "2025年公司级精密温控节能设备销量为324,058台。11R以公司总收入除以该销量形成混合单价，"
                "再把两条宽产品线收入换算为等价销量；这是低置信度研究估计，不是发行人披露的分部出货量、项目数或液冷销量。"
            ),
            "refs": ["E23", "E24", "E25"],
        }
    )
    _add_refs(segment, "E23", "E24", "E25")

    forecast = _section(reader_input, "forecast_and_scenarios")
    forecast["facts"].append(
        {
            "text": (
                "11R经营桥对三种情景、三个期间共9组收入和毛利逐项复算；收入最大差额不足0.0001元，"
                "毛利最大差额约0.0101元，均在0.02元容差内。基准2026E代理收入占比约9.32%，预测与估值总量未改变。"
            ),
            "refs": ["E25", "E28"],
        }
    )
    _add_refs(forecast, "E25", "E28")

    valuation = _section(reader_input, "valuation_and_market_implied_expectations")
    valuation["facts"].append(
        {
            "text": (
                "11R对4家候选同业逐项检查经营定义、收入纯度、会计边界、期间与预测日期，合格对象为0家；"
                "因此不采用同业倍数，继续只用原9R反向估值和情景压力测试解释市场隐含要求。"
            ),
            "refs": ["E26", "E28"],
        }
    )
    _add_refs(valuation, "E26", "E28")

    risks = _section(reader_input, "risks_and_falsification")
    risks["facts"].append(
        {
            "text": (
                "11R仍缺少液冷项目或交付容量、单位价值、测试至验收周期、宽口径重叠消除、独立毛利与营运资金口径；"
                "语义完整性检查没有发现高等级冲突，但不会替代这些正式证据。"
            ),
            "refs": ["E24", "E27"],
        }
    )
    _add_refs(risks, "E24", "E27")

    conclusion = _section(reader_input, "conclusion_and_watchlist")
    conclusion["facts"].append(
        {
            "text": (
                "11R新增了宽产品线经营驱动、同业方法资格与9R逐项勾稽，但没有改变原预测和估值输入；"
                "新Reader的人工作业状态重新置为待进行，旧报告的人审结论不跨哈希继承。"
            ),
            "refs": ["E25", "E26", "E27", "E28"],
        }
    )
    _add_refs(conclusion, "E25", "E26", "E27", "E28")

    reader_input["guardrails"].update(
        {
            "sample_quality_allowed": False,
            "p2_allowed": False,
            "direct_action_language_allowed": False,
            "liquid_cooling_standalone_additivity": "non_additive",
            "peer_ranking_allowed": False,
            "peer_multiples_allowed": False,
        }
    )
    return reader_input


def _chapter(plan: Mapping[str, Any], chapter_id: str) -> dict[str, Any]:
    for chapter in plan.get("narrative_chapters") or []:
        if chapter.get("chapter_id") == chapter_id:
            return chapter
    raise KeyError(chapter_id)


def build_narrative_plan(old_plan: Mapping[str, Any]) -> dict[str, Any]:
    plan = copy.deepcopy(dict(old_plan))
    plan["artifact_type"] = "R5_bundle11r_reader_narrative_plan"
    plan["source_payload"] = "R5_bundle11r_reader_payload.yaml"
    plan["revision_reason"] = (
        "在保留10R证据与叙事边界的前提下，加入11R经营驱动、同业方法资格和9R勾稽结果。"
    )

    core = _chapter(plan, "core_question")
    core["paragraphs"].append(
        {
            "text": (
                "新一轮拆解没有改变这个核心矛盾。三种情景的宽产品线收入和毛利都能与原模型勾稽，"
                "六个研究维度也没有发现高等级语义冲突；但项目数、单位价值、验收周期和独立液冷利润仍然缺失，"
                "所以经营桥提高的是可解释性，而不是液冷结论的置信度。"
            ),
            "refs": ["E24", "E25", "E27", "E28"],
        }
    )

    business = _chapter(plan, "business_model")
    business["paragraphs"].insert(
        1,
        {
            "text": (
                "年报还披露公司级精密温控节能设备销量324,058台。以公司总收入除以该销量，可以得到一个公司级混合单价，"
                "再将机房与机柜温控收入换算成等价销量，从而把宽口径预测写成量价关系。这个换算不是发行人披露的分部出货，"
                "更不是液冷项目数；它只能作为有边界的低置信度估计。"
            ),
            "refs": ["E23", "E24", "E25"],
        },
    )

    financial = _chapter(plan, "financial_delivery")
    after_tables = list(financial.get("paragraphs_after_tables") or [])
    after_tables.insert(
        0,
        {
            "text": (
                "11R按三种情景和三个期间复算了9组宽产品线结果。收入最大差额不足一分钱的万分之一，"
                "毛利最大差额约一分钱，均落在两分钱容差内；基准2026E其他业务代理占收入约9.32%。"
                "因此这次拆解没有通过新增液冷收入抬高预测，原反向估值和情景压力测试也无需改写。"
            ),
            "refs": ["E25", "E28"],
        },
    )
    financial["paragraphs_after_tables"] = after_tables

    market = _chapter(plan, "market_expectations")
    market["paragraphs"].insert(
        1,
        {
            "text": (
                "同业比较也需要先过方法资格。高澜股份、科创新源、申菱环境和飞荣达在液冷收入纯度、会计边界、"
                "报告期间与预测日期上都没有形成同口径，当前合格对象为零。因此同业只能解释行业背景，不能提供估值倍数锚；"
                "这里仍以公司自身的利润压力点和三情景结果为主。"
            ),
            "refs": ["E26", "E28"],
        },
    )

    falsification = _chapter(plan, "falsification")
    falsification["paragraphs"].append(
        {
            "text": (
                "经营桥的替换条件也已经明确：发行人一旦给出可复算的分部出货或项目量、单位价值、验收节奏、独立毛利和回款口径，"
                "就应替换当前等价销量与其他业务代理并重算；若至少三家同业形成同期间同经营定义的官方口径，才重新评估同业方法。"
            ),
            "refs": ["E24", "E25", "E26", "E28"],
        }
    )
    falsification.setdefault("watchpoints", []).append(
        {
            "metric": "经营驱动替换条件",
            "trigger": "任一分部出货、单位价值或验收周期获得可复算官方披露",
            "horizon": "每次正式披露后",
            "direction": "替换等价销量并重跑三情景与勾稽",
            "refs": ["E24", "E25", "E28"],
        }
    )
    return plan


def build_reader_inputs(repo_root: Path, output_dir: Path) -> dict[str, Path]:
    run_dir = repo_root / WORKFLOW_REL
    runtime_path = output_dir / "R5_bundle11r_runtime_result.yaml"
    model_path = run_dir / "R5_bundle9r_segment_driver_model.yaml"
    model_lock_path = run_dir / "R5_bundle9r_model_generation_lock.yaml"
    old_reader_input_path = run_dir / "R5_bundle10r_reader_input_pack.yaml"
    old_narrative_path = run_dir / "R5_bundle10r_reader_narrative_plan_v5.yaml"

    runtime = load_yaml(runtime_path)
    model = load_yaml(model_path)
    model_lock = load_yaml(model_lock_path)
    runtime_sha256 = sha256_file(runtime_path)
    outputs = split_runtime_result(runtime, output_dir)

    reconciliation = build_reconciliation(
        model,
        runtime,
        runtime_sha256=runtime_sha256,
        model_generation_id=str(model_lock["generation_id"]),
    )
    if reconciliation["decision"] != "pass":
        raise ValueError("Bundle 11R operating results do not reconcile to Bundle 9R")
    reconciliation_path = output_dir / "R5_bundle11r_operating_to_9r_reconciliation.yaml"
    dump_yaml(reconciliation_path, reconciliation)
    outputs["reconciliation"] = reconciliation_path

    reader_input = build_reader_input(
        load_yaml(old_reader_input_path),
        reconciliation,
        runtime_sha256=runtime_sha256,
    )
    reader_input_path = output_dir / "R5_bundle11r_reader_input_pack.yaml"
    dump_yaml(reader_input_path, reader_input)
    outputs["reader_input"] = reader_input_path

    narrative_plan = build_narrative_plan(load_yaml(old_narrative_path))
    narrative_path = output_dir / "R5_bundle11r_reader_narrative_plan.yaml"
    dump_yaml(narrative_path, narrative_plan)
    outputs["narrative_plan"] = narrative_path

    receipt = {
        "schema_version": 1,
        "artifact_type": "R5_bundle11r_reader_input_build_receipt",
        "workflow_id": WORKFLOW_ID,
        "as_of_date": AS_OF_DATE,
        "decision": "pass",
        "input_artifacts": [
            {"path": display_path(path, repo_root), "sha256": sha256_file(path)}
            for path in (runtime_path, model_path, model_lock_path, old_reader_input_path, old_narrative_path)
        ],
        "output_artifacts": [
            {"path": display_path(path, repo_root), "sha256": sha256_file(path)}
            for path in outputs.values()
        ],
        "reconciliation_summary": reconciliation["summary"],
        "historical_human_review_transfer_allowed": False,
        "fixed_boundaries": {"sample_quality_allowed": False, "p2_allowed": False},
    }
    receipt_path = output_dir / "R5_bundle11r_reader_input_build_receipt.yaml"
    dump_yaml(receipt_path, receipt)
    outputs["receipt"] = receipt_path
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Bundle 11R split outputs, 9R reconciliation, and Reader inputs")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else repo_root / WORKFLOW_REL / "bundle11r"
    outputs = build_reader_inputs(repo_root, output_dir)
    print(f"output_dir={output_dir} files={len(outputs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
