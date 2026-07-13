from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.report.r5_reader_report_writer import (  # noqa: E402
    SECTION_HEADINGS,
    build_reader_report,
    build_traceability_appendix,
    validate_citations,
)


SECTION_FIELDS = {
    "executive_summary": ("thesis", "financial", "risk"),
    "company_context_and_scope": ("company_context", "business", "risk"),
    "financial_history_and_cashflow_quality": ("financial", "business", "risk"),
    "business_breakdown_and_economics": ("business", "company_context", "watch_metric"),
    "industry_structure_and_competition": ("industry_context", "risk", "watch_metric"),
    "forecast_and_scenarios": ("forecast", "financial", "risk"),
    "valuation_and_market_expectations": ("valuation", "forecast", "risk"),
    "dated_events": ("event", "watch_metric", "risk"),
    "risks_counterevidence_and_watchpoints": ("risk", "financial", "watch_metric"),
    "research_conclusion": ("conclusion", "thesis", "watch_metric"),
}

SECTION_PARAGRAPH_TEMPLATES = {
    "executive_summary": (
        "财务侧的直接观察是“{financial}”。核心主线应由“{watch_metric}”继续验证，"
        "并由“{risk}”作为降级条件"
    ),
    "company_context_and_scope": (
        "研究边界只覆盖样例 pack 提供的公司经营机制；{watch_metric}是把业务描述"
        "转化为可验证判断的接口，不把{industry}景气线索外推为公司事实"
    ),
    "financial_history_and_cashflow_quality": (
        "该财务现象需要把利润、营运资金和现金流放在同一条验证链上，"
        "重点观察{watch_metric}"
    ),
    "business_breakdown_and_economics": (
        "上述业务结构需分别核对收入、毛利与现金转换，"
        "不能用公司总量替代细分经济性"
    ),
    "industry_structure_and_competition": (
        "行业需求与公司兑现能力应分开判断，"
        "竞争或监管变化通过{watch_metric}反映"
    ),
    "forecast_and_scenarios": (
        "三种情景由{watch_metric}区分；{risk}"
    ),
    "valuation_and_market_expectations": (
        "这一估值框架只用于比较不同经营情景隐含的市场预期，"
        "不转化为交易动作"
    ),
    "dated_events": (
        "该事件是验证窗口而非预设利好，影响链落到{watch_metric}"
    ),
    "risks_counterevidence_and_watchpoints": (
        "风险监测以{watch_metric}为主，反证持续出现时应下调结论置信度"
    ),
    "research_conclusion": (
        "后续跟踪围绕{watch_metric}展开。当前输出只验证 Writer 跨行业渲染，"
        "不代表真实公司研究结论或样例质量许可"
    ),
}

SECTION_BULLET_LABELS = {
    "executive_summary": "核心反证",
    "company_context_and_scope": "边界校验",
    "financial_history_and_cashflow_quality": "财务校验",
    "business_breakdown_and_economics": "业务校验",
    "industry_structure_and_competition": "行业校验",
    "forecast_and_scenarios": "情景校验",
    "valuation_and_market_expectations": "估值校验",
    "dated_events": "事件校验",
    "risks_counterevidence_and_watchpoints": "风险校验",
    "research_conclusion": "后续观察",
}

MALFORMED_TEXT_PATTERNS = ("若若", "。。", "，，", "；；", "，。", "；。", "。；")
PROHIBITED_ADVICE_PATTERNS = ("建议买入", "建议卖出", "建议持有", "目标价", "建议仓位")


def load_cases(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        raise ValueError("cross-industry fixture cases are malformed")
    return [dict(row) for row in data["cases"]]


def _terminal_clean(value: Any) -> str:
    return str(value).strip().rstrip("。；， ")


def _section_paragraph(section_id: str, case: Mapping[str, Any]) -> str:
    context = {key: _terminal_clean(value) for key, value in case.items()}
    return SECTION_PARAGRAPH_TEMPLATES[section_id].format(**context) + "。"


def _narrative_quality(pack: Mapping[str, Any], report: str) -> dict[str, Any]:
    paragraphs = [
        str(block.get("text") or "").strip()
        for section in pack.get("sections") or []
        for block in section.get("blocks") or []
        if isinstance(block, Mapping) and block.get("type") == "paragraph"
    ]
    judgments = [str(section.get("judgment") or "").strip() for section in pack.get("sections") or []]
    malformed_hits = [pattern for pattern in MALFORMED_TEXT_PATTERNS if pattern in report]
    prohibited_hits = [pattern for pattern in PROHIBITED_ADVICE_PATTERNS if pattern in report]
    duplicate_paragraph_count = len(paragraphs) - len(set(paragraphs))
    unique_judgment_count = len(set(judgments))
    judgment_restatement_count = sum(
        1
        for judgment, paragraph in zip(judgments, paragraphs, strict=True)
        if _terminal_clean(judgment) in paragraph
    )
    errors: list[str] = []
    if malformed_hits:
        errors.append(f"malformed text patterns: {malformed_hits}")
    if prohibited_hits:
        errors.append(f"prohibited advice patterns: {prohibited_hits}")
    if duplicate_paragraph_count:
        errors.append(f"duplicate paragraphs: {duplicate_paragraph_count}")
    if unique_judgment_count != len(SECTION_HEADINGS):
        errors.append(
            f"section judgments are not distinct: {unique_judgment_count}/{len(SECTION_HEADINGS)}"
        )
    if judgment_restatement_count:
        errors.append(f"section judgment repeated verbatim in paragraph: {judgment_restatement_count}")
    return {
        "status": "pass" if not errors else "fail",
        "paragraph_count": len(paragraphs),
        "duplicate_paragraph_count": duplicate_paragraph_count,
        "unique_section_judgment_count": unique_judgment_count,
        "judgment_restatement_count": judgment_restatement_count,
        "malformed_pattern_hits": malformed_hits,
        "prohibited_advice_hits": prohibited_hits,
        "errors": errors,
    }


def case_to_pack(case: Mapping[str, Any]) -> dict[str, Any]:
    sections = []
    for section_id in SECTION_HEADINGS:
        primary, _secondary, tertiary = SECTION_FIELDS[section_id]
        sections.append(
            {
                "section_id": section_id,
                "judgment": str(case[primary]),
                "judgment_refs": ["E1", "E2"],
                "blocks": [
                    {
                        "type": "paragraph",
                        "text": _section_paragraph(section_id, case),
                        "refs": ["E1", "E2"],
                    },
                    {
                        "type": "bullets",
                        "items": [
                            {
                                "text": f"{SECTION_BULLET_LABELS[section_id]}：{_terminal_clean(case[tertiary])}。",
                                "refs": ["E1" if tertiary != "risk" else "E2"],
                            },
                        ],
                    },
                ],
            }
        )
    return {
        "artifact_type": "R5_reader_report_pack",
        "schema_version": "r5_reader_report_pack_v0.2",
        "metadata": {
            "workflow_id": f"fixture_{case['sample_id']}",
            "company_id": case["company_id"],
            "company_name": case["company_name"],
            "stock_code": case["stock_code"],
            "cutoff_date": "2026-07-13",
            "report_level": "Writer跨行业回归样例",
            "human_review_status": "pending",
            "sample_quality_report_allowed": False,
            "p2_allowed": False,
        },
        "sections": sections,
        "traceability_records": [
            {
                "display_reference_id": "E1", "claim_type": "fixture_fact",
                "claim_summary": f"{case['industry']}样例事实输入", "period": "fixture", "unit": None,
                "raw_evidence_ids": [f"fixture_{case['sample_id']}_source_1"], "source_category": "other",
                "source_path": "tests/fixtures/r5_reader_writer/cross_industry_cases.yaml",
                "method": "synthetic_writer_regression", "confidence": "fixture_only",
                "limitation": "只验证动态渲染，不进入研究结论", "reviewer_state": "fixture",
                "conflict_or_staleness_status": "not_applicable",
            },
            {
                "display_reference_id": "E2", "claim_type": "fixture_counterevidence",
                "claim_summary": f"{case['industry']}样例反证输入", "period": "fixture", "unit": None,
                "raw_evidence_ids": [f"fixture_{case['sample_id']}_source_2"], "source_category": "other",
                "source_path": "tests/fixtures/r5_reader_writer/cross_industry_cases.yaml",
                "method": "synthetic_writer_regression", "confidence": "fixture_only",
                "limitation": "只验证动态渲染，不进入研究结论", "reviewer_state": "fixture",
                "conflict_or_staleness_status": "not_applicable",
            },
        ],
        "footer": "该文件是合成Writer回归样例，不代表真实公司研究或质量许可。",
        "no_advice_boundary": True,
    }


def run_regression(cases_path: Path, output_dir: Path) -> dict[str, Any]:
    cases = load_cases(cases_path)
    if len(cases) < 2:
        raise ValueError("at least two cross-industry cases are required")
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    rendered_by_id: dict[str, str] = {}
    for case in cases:
        pack = case_to_pack(case)
        report = build_reader_report(pack)
        appendix = build_traceability_appendix(pack)
        unresolved = validate_citations(report, appendix)
        if unresolved:
            raise ValueError(f"{case['sample_id']} unresolved citations: {unresolved}")
        for heading in SECTION_HEADINGS.values():
            if report.count(heading) != 1:
                raise ValueError(f"{case['sample_id']} missing or duplicate heading: {heading}")
        if str(case["company_name"]) not in report or str(case["stock_code"]) not in report:
            raise ValueError(f"{case['sample_id']} identity did not render")
        narrative_quality = _narrative_quality(pack, report)
        if narrative_quality["status"] != "pass":
            raise ValueError(
                f"{case['sample_id']} narrative quality failed: {narrative_quality['errors']}"
            )
        report_path = output_dir / f"{case['sample_id']}_reader.md"
        appendix_path = output_dir / f"{case['sample_id']}_traceability.yaml"
        report_path.write_text(report, encoding="utf-8")
        appendix_path.write_text(yaml.safe_dump(appendix, allow_unicode=True, sort_keys=False), encoding="utf-8")
        rendered_by_id[str(case["sample_id"])] = report
        results.append(
            {
                "sample_id": case["sample_id"],
                "industry": case["industry"],
                "company_name": case["company_name"],
                "stock_code": case["stock_code"],
                "section_count": len(SECTION_HEADINGS),
                "citation_count": len(appendix["records"]),
                "report_sha256": hashlib.sha256(report.encode("utf-8")).hexdigest(),
                "narrative_quality": narrative_quality,
                "status": "pass",
            }
        )
    for case in cases:
        own_id = str(case["sample_id"])
        for other in cases:
            if other is case:
                continue
            if str(other["company_name"]) in rendered_by_id[own_id] or str(other["stock_code"]) in rendered_by_id[own_id]:
                raise ValueError(f"cross-sample identity leakage into {own_id}")
    writer_source = (ROOT / "src/report/r5_reader_report_writer.py").read_text(encoding="utf-8")
    hardcoded_tokens = [token for token in ("英维克", "002837", DEFAULT_WORKFLOW_TOKEN) if token in writer_source]
    if hardcoded_tokens:
        raise ValueError(f"writer source contains workflow identity tokens: {hardcoded_tokens}")
    aggregate_narrative = {
        "status": "pass",
        "case_count": len(results),
        "total_duplicate_paragraph_count": sum(
            row["narrative_quality"]["duplicate_paragraph_count"] for row in results
        ),
        "malformed_pattern_hits": sorted(
            {
                hit
                for row in results
                for hit in row["narrative_quality"]["malformed_pattern_hits"]
            }
        ),
        "prohibited_advice_hits": sorted(
            {
                hit
                for row in results
                for hit in row["narrative_quality"]["prohibited_advice_hits"]
            }
        ),
        "minimum_unique_section_judgment_count": min(
            row["narrative_quality"]["unique_section_judgment_count"] for row in results
        ),
        "total_judgment_restatement_count": sum(
            row["narrative_quality"]["judgment_restatement_count"] for row in results
        ),
    }
    return {
        "artifact_type": "R5_bundle10_cross_industry_writer_regression",
        "schema_version": "v0.2",
        "fixture_boundary": "synthetic_layout_and_schema_regression_only",
        "case_count": len(results),
        "distinct_industries": len({row["industry"] for row in results}),
        "results": results,
        "writer_identity_hardcoding": False,
        "cross_sample_identity_leakage": False,
        "narrative_quality": aggregate_narrative,
        "decision": "pass",
    }


DEFAULT_WORKFLOW_TOKEN = "wf_20260703_stock_first_002837_invic"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Bundle 10 cross-industry dynamic Writer regression.")
    parser.add_argument("--cases", default="tests/fixtures/r5_reader_writer/cross_industry_cases.yaml")
    parser.add_argument(
        "--output-dir",
        default="reports/workflow_runs/wf_20260703_stock_first_002837_invic/bundle10_cross_industry_regression",
    )
    parser.add_argument(
        "--summary",
        default="reports/workflow_runs/wf_20260703_stock_first_002837_invic/R5_bundle10_cross_industry_writer_regression.yaml",
    )
    args = parser.parse_args()
    result = run_regression(ROOT / args.cases, ROOT / args.output_dir)
    summary = ROOT / args.summary
    summary.write_text(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
