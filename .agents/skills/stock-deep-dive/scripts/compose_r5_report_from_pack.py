#!/usr/bin/env python3
"""Compose a source-gapped R5 report note skeleton from an R5 pack."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: pip install pyyaml") from exc

FORBIDDEN = ["建议买入", "建议卖出", "买入评级", "卖出评级", "持有评级", "仓位建议", "保证收益"]
SECTIONS = [
    "前言",
    "财务概览",
    "业务拆分",
    "行业分析",
    "盈利预测",
    "估值分析",
    "技术分析",
    "情绪分析",
    "事件驱动",
    "研究结论",
]
SAMPLE_REQUIRED_PACKS = [
    "business_breakdown_pack",
    "forecast_model_pack",
    "valuation_pack",
]


def load_pack(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("pack root must be a mapping")
    if data.get("artifact_type") != "R5_stock_research_pack":
        raise ValueError("artifact_type must be R5_stock_research_pack")
    return data


def _walk(value: Any) -> list[str]:
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_walk(item))
        return out
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_walk(item))
        return out
    return [str(value)] if value is not None else []


def _forbidden_phrases(text: str) -> list[str]:
    return [phrase for phrase in FORBIDDEN if phrase in text]


def _sample_quality_blockers(pack: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    quality = pack.get("quality_status") if isinstance(pack.get("quality_status"), dict) else {}
    if quality.get("high_issue_count") not in (0, "0"):
        blockers.append("high_issue_count")
    if quality.get("no_advice_gate_passed") is not True:
        blockers.append("no_advice_gate")
    for pack_name in SAMPLE_REQUIRED_PACKS:
        subpack = pack.get(pack_name)
        if not isinstance(subpack, dict) or subpack.get("status") != "ready":
            blockers.append(pack_name)
    return blockers


def _source_gap_lines(pack: dict[str, Any]) -> list[str]:
    rows = pack.get("source_gap_register")
    lines: list[str] = []
    if isinstance(rows, list) and rows:
        for row in rows:
            if not isinstance(row, dict):
                continue
            gap_id = row.get("gap_id", "gap")
            section = row.get("section", "unknown")
            missing = row.get("missing_data", row.get("missing_reason", "TODO_SOURCE_REQUIRED"))
            action = row.get("next_action", "keep visible TODO")
            lines.append(f"- {gap_id} | {section} | {missing} | {action}")
    tokens = sorted({token for token in _walk(pack) if any(marker in token for marker in ["TODO", "MISSING", "UNVERIFIED"])})
    for token in tokens:
        if not any(token in line for line in lines):
            lines.append(f"- token | source_gap | {token} | keep visible")
    return lines or ["- no source gaps supplied; quality-review must verify before use"]


def _display_status(pack: dict[str, Any]) -> str:
    pack_status = str(pack.get("pack_status") or pack.get("quality_status", {}).get("allowed_report_level") or "research_draft")
    if pack_status == "sample_quality_candidate":
        if _sample_quality_blockers(pack):
            return "research_draft"
        return "sample_quality_candidate"
    if pack_status in {"blocked", "needs_fix"}:
        return pack_status
    return "research_draft"


def compose_note(pack: dict[str, Any]) -> str:
    pack_text = "\n".join(_walk(pack))
    blocked_phrases = _forbidden_phrases(pack_text)
    if blocked_phrases:
        raise ValueError(f"forbidden trading phrase present in pack: {blocked_phrases[0]}")

    stock = pack.get("stock") if isinstance(pack.get("stock"), dict) else {}
    company = stock.get("company_name") or pack.get("company_name") or "示例公司"
    status = _display_status(pack)
    quality = pack.get("quality_status") if isinstance(pack.get("quality_status"), dict) else {}
    source_gaps = _source_gap_lines(pack)
    blockers = _sample_quality_blockers(pack) if str(pack.get("pack_status")) == "sample_quality_candidate" else []

    lines = [
        f"# R5研究草稿：{company}",
        "",
        f"- pack_status: {status}",
        f"- r5_gate_status: {quality.get('r5_gate_status', 'not_reviewed')}",
        f"- allowed_report_level: {quality.get('allowed_report_level', status)}",
        "- composer_scope: fixture_or_reviewed_pack_translation_only",
    ]
    if blockers:
        lines.append(f"- downgrade_reason: {', '.join(blockers)}")
    lines.append("")
    for section in SECTIONS:
        lines.extend(
            [
                f"## {section}",
                "",
                "本节仅转译 `R5_stock_research_pack.yaml` 中已存在的字段；缺口见 Source Gap Appendix。",
                "",
            ]
        )
    lines.extend(["## Source Gap Appendix", "", *source_gaps, "", "## Evidence Appendix", "", "- evidence/metric/claim/assumption IDs must come from the pack."])
    note = "\n".join(lines) + "\n"
    blocked_generated_phrases = _forbidden_phrases(note)
    if blocked_generated_phrases:
        raise ValueError(f"forbidden trading phrase generated: {blocked_generated_phrases[0]}")
    return note


def numeric_tokens(text: str) -> set[str]:
    return set(re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?%?(?![A-Za-z])", text))


def assert_no_new_numbers(pack_text: str, note: str) -> None:
    new_numbers = numeric_tokens(note) - numeric_tokens(pack_text)
    if new_numbers:
        raise ValueError(f"composer introduced numbers not present in pack: {sorted(new_numbers)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compose R5 report note skeleton from pack.")
    parser.add_argument("pack", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        pack = load_pack(args.pack)
        note = compose_note(pack)
        assert_no_new_numbers(args.pack.read_text(encoding="utf-8"), note)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(note, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
