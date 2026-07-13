"""Pack-driven R5 reader report and traceability appendix writer."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


SECTION_HEADINGS = {
    "executive_summary": "## 一、核心研究观点",
    "company_context_and_scope": "## 二、公司背景与研究边界",
    "financial_history_and_cashflow_quality": "## 三、财务历史与现金流质量",
    "business_breakdown_and_economics": "## 四、业务拆分与细分经济性",
    "industry_structure_and_competition": "## 五、行业结构与竞争",
    "forecast_and_scenarios": "## 六、预测与情景",
    "valuation_and_market_expectations": "## 七、估值与市场预期",
    "dated_events": "## 八、有日期的公司事件",
    "risks_counterevidence_and_watchpoints": "## 九、风险、反证与观察条件",
    "research_conclusion": "## 十、研究结论与跟踪清单",
}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def _refs(refs: Sequence[str] | None) -> str:
    return "".join(f"[{ref}]" for ref in refs or [])


def _escape_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _render_table(block: Mapping[str, Any]) -> list[str]:
    headers = list(block.get("headers") or [])
    rows = list(block.get("rows") or [])
    if not headers:
        raise ValueError("table block requires headers")
    lines: list[str] = []
    title = str(block.get("title") or "").strip()
    if title:
        lines.extend([title, ""])
    lines.append("| " + " | ".join(_escape_cell(item) for item in headers) + " |")
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        values = list(row)
        if len(values) != len(headers):
            raise ValueError("table row length must match headers")
        lines.append("| " + " | ".join(_escape_cell(item) for item in values) + " |")
    note = str(block.get("note") or "").strip()
    if note:
        lines.extend(["", note + (" " if block.get("refs") else "") + _refs(block.get("refs"))])
    return lines


def _render_block(block: Mapping[str, Any]) -> list[str]:
    block_type = str(block.get("type") or "paragraph")
    if block_type == "paragraph":
        text = str(block.get("text") or "").strip()
        if not text:
            return []
        suffix = _refs(block.get("refs"))
        return [text + (" " if suffix else "") + suffix]
    if block_type == "bullets":
        lines: list[str] = []
        for item in block.get("items") or []:
            if isinstance(item, Mapping):
                text = str(item.get("text") or "").strip()
                suffix = _refs(item.get("refs"))
            else:
                text = str(item).strip()
                suffix = ""
            if text:
                lines.append(f"- {text}" + (" " if suffix else "") + suffix)
        return lines
    if block_type == "table":
        return _render_table(block)
    if block_type == "subheading":
        text = str(block.get("text") or "").strip()
        return [f"### {text}"] if text else []
    raise ValueError(f"unsupported reader block type: {block_type}")


def _section_map(pack: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = pack.get("sections") or []
    if not isinstance(rows, list):
        raise ValueError("reader report pack sections must be a list")
    mapped: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("reader report section must be a mapping")
        section_id = str(row.get("section_id") or "")
        if not section_id or section_id in mapped:
            raise ValueError(f"invalid or duplicate section_id: {section_id}")
        mapped[section_id] = row
    return mapped


def build_reader_report(pack: Mapping[str, Any]) -> str:
    """Render a reader-facing report without introducing company-specific content."""

    if pack.get("artifact_type") != "R5_reader_report_pack":
        raise ValueError("artifact_type must be R5_reader_report_pack")
    metadata = pack.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("reader report pack metadata is required")
    company_name = str(metadata.get("company_name") or "").strip()
    stock_code = str(metadata.get("stock_code") or "").strip()
    cutoff_date = str(metadata.get("cutoff_date") or "").strip()
    report_level = str(metadata.get("report_level") or "研究候选稿").strip()
    if not company_name or not stock_code or not cutoff_date:
        raise ValueError("company_name, stock_code and cutoff_date are required")

    sections = _section_map(pack)
    missing = [section_id for section_id in SECTION_HEADINGS if section_id not in sections]
    if missing:
        raise ValueError(f"reader report pack missing sections: {', '.join(missing)}")

    title_pattern = str(metadata.get("title_pattern") or "{company_name}（{stock_code}）读者型研究报告候选稿")
    title = title_pattern.format(company_name=company_name, stock_code=stock_code)
    lines = [
        f"# {title}",
        "",
        f"**数据截止日：{cutoff_date}｜报告层级：{report_level}｜外部人工复核：待进行**",
        "",
        "> 本文用于证据约束下的公司研究，只提供研究情景、风险与验证条件，不提供交易动作、配置比例或收益承诺。",
        "",
    ]
    for section_id, heading in SECTION_HEADINGS.items():
        section = sections[section_id]
        lines.extend([heading, ""])
        judgment = str(section.get("judgment") or "").strip()
        judgment_refs = _refs(section.get("judgment_refs"))
        if judgment:
            lines.extend([judgment + (" " if judgment_refs else "") + judgment_refs, ""])
        for block in section.get("blocks") or []:
            if not isinstance(block, Mapping):
                raise ValueError(f"{section_id} block must be a mapping")
            rendered = _render_block(block)
            if rendered:
                lines.extend(rendered)
                lines.append("")

    footer = str(pack.get("footer") or "外部人工复核仍待完成；在签署前，本稿不获得样例质量或横向比较许可。").strip()
    lines.extend(["---", "", footer, ""])
    return "\n".join(lines)


def build_traceability_appendix(pack: Mapping[str, Any]) -> dict[str, Any]:
    """Build the audit appendix from pack records; the report only sees display refs."""

    metadata = pack.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("reader report pack metadata is required")
    source_records = pack.get("traceability_records") or []
    if not isinstance(source_records, list) or not source_records:
        raise ValueError("traceability_records must be a non-empty list")
    records: list[dict[str, Any]] = []
    for source in source_records:
        if not isinstance(source, Mapping):
            raise ValueError("traceability record must be a mapping")
        record = dict(source)
        summary = str(record.get("claim_summary") or "")
        record["claim_text_digest"] = record.get("claim_text_digest") or hashlib.sha256(summary.encode("utf-8")).hexdigest()
        records.append(record)
    return {
        "artifact_type": "R5_stock_research_report_traceability_v2",
        "schema_version": "v0.2",
        "workflow_id": metadata.get("workflow_id"),
        "stock_code": str(metadata.get("stock_code")),
        "cutoff_date": metadata.get("cutoff_date"),
        "records": records,
        "human_review_status": "pending",
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
    }


def validate_citations(report: str, appendix: Mapping[str, Any]) -> list[str]:
    used = set(re.findall(r"\[(E[1-9][0-9]*)\]", report))
    counts: dict[str, int] = {}
    for record in appendix.get("records") or []:
        ref = str(record.get("display_reference_id") or "")
        counts[ref] = counts.get(ref, 0) + 1
    unresolved = sorted(ref for ref in used if counts.get(ref) != 1)
    invalid_records = sorted(ref for ref, count in counts.items() if not ref or count != 1)
    return unresolved + invalid_records
