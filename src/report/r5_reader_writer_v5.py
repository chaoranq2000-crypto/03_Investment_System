"""Deterministic narrative Reader renderer for Bundle 10R v5.

The ten structured analysis units remain the quality-control surface.  This
renderer composes them into a smaller set of reader-facing chapters so the
report can read as research rather than as a repeated audit form.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


DEFAULT_CHAPTER_GROUPS = (
    ("核心判断", ("executive_summary", "conclusion_and_watchlist")),
    ("公司靠什么赚钱", ("company_context_and_scope", "segment_economics")),
    ("需求如何转化为经营结果", ("industry_and_competition",)),
    ("增长的成色", ("financial_quality", "forecast_and_scenarios")),
    ("市场计入了什么", ("valuation_and_market_implied_expectations", "market_technical_sentiment_and_events")),
    ("什么会证明判断有误", ("risks_and_falsification",)),
)


def _refs(refs: Iterable[str] | None) -> str:
    values = sorted({str(value) for value in refs or []}, key=lambda value: (len(value), value))
    return "".join(f"[{value}]" for value in values)


def _text(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, Mapping):
        return str(item.get("text") or item.get("metric") or "").strip()
    return str(item).strip()


def _item_refs(item: Any) -> list[str]:
    return list(item.get("refs") or []) if isinstance(item, Mapping) else []


def _render_tables(tables: list[Any]) -> list[str]:
    lines: list[str] = []
    for table in tables:
        if not isinstance(table, Mapping):
            continue
        title = str(table.get("title") or "数据快照")
        headers = [str(value) for value in table.get("headers") or []]
        rows = table.get("rows") or []
        if not headers or not rows:
            continue
        lines.extend([f"### {title}", "", "| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"])
        for row in rows:
            cells = [str(value) for value in row]
            if len(cells) != len(headers):
                raise ValueError(f"table row/header mismatch: {title!r}")
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
        if table.get("note"):
            lines.extend([f"> {table['note']}{_refs(table.get('refs') or [])}", ""])
    return lines


def _render_watchpoints(items: list[Any]) -> list[str]:
    if not items:
        return []
    lines = ["### 接下来真正值得盯的变量", "", "| 变量 | 触发条件 | 观察窗口 | 判断影响 |", "|---|---|---|---|"]
    seen: set[tuple[str, str]] = set()
    for item in items:
        if not isinstance(item, Mapping):
            continue
        metric = str(item.get("metric") or "观察指标")
        trigger = str(item.get("trigger") or item.get("condition") or "待定义")
        key = (metric, trigger)
        if key in seen:
            continue
        seen.add(key)
        horizon = str(item.get("horizon") or "持续跟踪")
        direction = str(item.get("direction") or item.get("interpretation") or "据此更新判断")
        lines.append(f"| {metric} | {trigger}{_refs(item.get('refs') or [])} | {horizon} | {direction} |")
    lines.append("")
    return lines


def _render_events(items: list[Any]) -> list[str]:
    if not items:
        return []
    lines = ["### 临近验证节点", ""]
    for event in items:
        if not isinstance(event, Mapping):
            continue
        text = _text(event)
        if text:
            lines.append(f"- {text}{_refs(event.get('refs') or [])}")
            continue
        lines.append(
            f"- {event.get('date', '日期待确认')}：{event.get('impact_path', '影响路径待确认')}；"
            f"重点核对{event.get('verification_metric', '相关经营指标')}。"
            f"若{event.get('counterevidence_condition', '反向条件出现')}，则需下调原判断。"
            f"{_refs(event.get('refs') or [])}"
        )
    lines.append("")
    return lines


def _fallback_chapters(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_id = {
        str(section.get("section_id")): section
        for section in payload.get("sections") or []
        if isinstance(section, Mapping)
    }
    chapters: list[dict[str, Any]] = []
    for title, section_ids in DEFAULT_CHAPTER_GROUPS:
        selected = [by_id[section_id] for section_id in section_ids if section_id in by_id]
        paragraphs: list[dict[str, Any]] = []
        table_sources: list[str] = []
        for section in selected:
            paragraphs.append({"text": section.get("judgment") or "", "refs": section.get("judgment_refs") or section.get("references") or []})
            for field in ("facts", "causal_mechanism", "economic_implications", "counterevidence", "uncertainty"):
                paragraphs.extend(item for item in section.get(field) or [] if _text(item))
            if section.get("tables"):
                table_sources.append(str(section.get("section_id")))
        chapters.append({"title": title, "paragraphs": paragraphs, "table_sources": table_sources})
    return chapters


def render_reader_report(payload: Mapping[str, Any]) -> str:
    company = payload["company"]
    name = company["name"]
    ticker = company["ticker"]
    as_of_date = company["as_of_date"]
    report_level = payload.get("report_level") or "研究候选稿"
    review_status = payload.get("human_review_status") or "pending"
    review_display = {
        "pending": "待进行",
        "not_started": "未开始",
        "accepted": "已通过",
        "rejected": "未通过",
        "revision_required": "需修订",
    }.get(str(review_status), str(review_status))
    sections = {
        str(section.get("section_id")): section
        for section in payload.get("sections") or []
        if isinstance(section, Mapping)
    }
    chapters = payload.get("narrative_chapters") or _fallback_chapters(payload)
    if not 4 <= len(chapters) <= 8:
        raise ValueError("v5 narrative_chapters must contain 4 to 8 reader-facing chapters")

    lines = [
        f"# {name}（{ticker}）研究报告",
        "",
        f"**数据截止日：{as_of_date}｜报告层级：{report_level}｜人工复核：{review_display}**",
        "",
        "> 这是一份证据约束下的研究候选稿，不构成投资建议。文中的事实、估计、分析师观点和推断可在配套追溯附录中逐项核验。",
        "",
    ]

    for index, chapter in enumerate(chapters, start=1):
        if not isinstance(chapter, Mapping):
            raise ValueError("narrative chapter must be a mapping")
        title = str(chapter.get("title") or f"章节{index}")
        lines.extend([f"## {index}、{title}", ""])
        lead = chapter.get("lead")
        if lead and _text(lead):
            lines.extend([f"**{_text(lead)}**{_refs(_item_refs(lead))}", ""])
        for paragraph in chapter.get("paragraphs") or []:
            body = _text(paragraph)
            if body:
                lines.extend([f"{body}{_refs(_item_refs(paragraph))}", ""])

        tables: list[Any] = list(chapter.get("tables") or [])
        for section_id in chapter.get("table_sources") or []:
            tables.extend((sections.get(str(section_id)) or {}).get("tables") or [])
        lines.extend(_render_tables(tables))

        for paragraph in chapter.get("paragraphs_after_tables") or []:
            body = _text(paragraph)
            if body:
                lines.extend([f"{body}{_refs(_item_refs(paragraph))}", ""])

        trailing_tables: list[Any] = list(chapter.get("tables_after") or [])
        for section_id in chapter.get("table_sources_after") or []:
            trailing_tables.extend((sections.get(str(section_id)) or {}).get("tables") or [])
        lines.extend(_render_tables(trailing_tables))

        events: list[Any] = list(chapter.get("events") or [])
        for section_id in chapter.get("event_sources") or []:
            events.extend((sections.get(str(section_id)) or {}).get("events") or [])
        lines.extend(_render_events(events))

        watchpoints: list[Any] = list(chapter.get("watchpoints") or [])
        for section_id in chapter.get("watchpoint_sources") or []:
            watchpoints.extend((sections.get(str(section_id)) or {}).get("watchpoints") or [])
        lines.extend(_render_watchpoints(watchpoints))

    lines.extend([
        "---",
        "",
        "配套追溯附录保留来源、口径和证据标识；正文只呈现对读者有用的研究链条。",
        "",
        "人工复核状态由独立审核记录更新，自动生成不能替代人工判断。",
        "",
    ])
    return "\n".join(lines)
