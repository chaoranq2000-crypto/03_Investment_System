"""Generic deterministic Reader renderer for Bundle 10R.

All issuer-specific wording belongs in the structured payload. The Writer only
controls document grammar, ordering, labels, and deterministic formatting.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def _refs(refs: Iterable[str] | None) -> str:
    values = sorted(set(refs or []), key=lambda x: (len(x), x))
    return "".join(f"[{value}]" for value in values)


def _text(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, Mapping):
        return str(item.get("text") or item.get("metric") or "").strip()
    return str(item).strip()


def _item_refs(item: Any) -> list[str]:
    if isinstance(item, Mapping):
        return list(item.get("refs") or [])
    return []


def _render_group(label: str, items: list[Any], *, bullets: bool = False) -> list[str]:
    if not items:
        return []
    lines = [f"**{label}：**"]
    for item in items:
        body = _text(item)
        suffix = _refs(_item_refs(item))
        prefix = "- " if bullets else ""
        lines.append(f"{prefix}{body}{suffix}")
    lines.append("")
    return lines


def _render_watchpoints(items: list[Any]) -> list[str]:
    lines = ["**后续验证与触发条件：**"]
    for item in items:
        if isinstance(item, Mapping):
            metric = str(item.get("metric") or "观察指标")
            trigger = str(item.get("trigger") or item.get("condition") or "待定义")
            horizon = str(item.get("horizon") or "持续跟踪")
            direction = str(item.get("direction") or item.get("interpretation") or "")
            body = f"{metric}：{trigger}；观察窗口：{horizon}"
            if direction:
                body += f"；含义：{direction}"
            lines.append(f"- {body}{_refs(item.get('refs') or [])}")
        else:
            lines.append(f"- {_text(item)}")
    lines.append("")
    return lines


def _render_tables(tables: list[Any]) -> list[str]:
    lines: list[str] = []
    for table in tables:
        if not isinstance(table, Mapping):
            continue
        title = table.get("title")
        if title:
            lines.extend([f"**{title}**", ""])
        headers = [str(x) for x in table.get("headers") or []]
        rows = table.get("rows") or []
        if headers and rows:
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "|".join("---" for _ in headers) + "|")
            for row in rows:
                cells = [str(x) for x in row]
                if len(cells) != len(headers):
                    raise ValueError(f"table row/header mismatch: {title!r}")
                lines.append("| " + " | ".join(cells) + " |")
            lines.append("")
        note = table.get("note")
        if note:
            lines.extend([f"> {note}{_refs(table.get('refs') or [])}", ""])
    return lines


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

    lines = [
        f"# {name}（{ticker}）读者型研究报告",
        "",
        f"**数据截止日：{as_of_date}｜报告层级：{report_level}｜人工复核：{review_display}**",
        "",
        "> 本文用于证据约束下的公司研究，不构成投资建议。事实、估计、分析师观点与推断应按配套追溯附录核验。",
        "",
    ]

    for index, section in enumerate(payload.get("sections") or [], start=1):
        title = section.get("title") or section.get("section_id")
        lines.extend([f"## {index}、{title}", ""])
        judgment = str(section.get("judgment") or "").strip()
        lines.extend([f"**本节判断：** {judgment}{_refs(section.get('judgment_refs') or section.get('references') or [])}", ""])
        lines.extend(_render_group("关键事实", section.get("facts") or [], bullets=True))
        lines.extend(_render_group("因果机制", section.get("causal_mechanism") or []))
        lines.extend(_render_group("经济含义", section.get("economic_implications") or []))
        lines.extend(_render_tables(section.get("tables") or []))

        technical = section.get("technical_context") or {}
        sentiment = section.get("sentiment_context") or {}
        events = section.get("events") or []
        if technical:
            lines.extend([
                f"**技术分析口径：** 数据状态为{technical.get('status', '未说明')}，截止日为{technical.get('as_of_date', '未说明')}，"
                f"历史序列起点为{technical.get('series_start', '未说明')}。{_refs(technical.get('refs') or section.get('references') or [])}",
                "",
            ])
        if sentiment:
            layers = "、".join(str(x) for x in sentiment.get("layers") or [])
            lines.extend([
                f"**情绪分析口径：** 数据状态为{sentiment.get('status', '未说明')}，截止日为{sentiment.get('as_of_date', '未说明')}"
                + (f"，覆盖{layers}" if layers else "")
                + f"。{_refs(sentiment.get('refs') or section.get('references') or [])}",
                "",
            ])
        if events:
            lines.append("**未来事件验证链：**")
            for event in events:
                if not isinstance(event, Mapping):
                    continue
                lines.append(
                    f"- {event.get('date', '日期未说明')}：{event.get('impact_path', '影响路径未说明')}；"
                    f"验证指标：{event.get('verification_metric', '未说明')}；"
                    f"反证条件：{event.get('counterevidence_condition', '未说明')}"
                    f"{_refs(event.get('refs') or [])}"
                )
            lines.append("")

        lines.extend(_render_group("反向证据", section.get("counterevidence") or [], bullets=True))
        lines.extend(_render_group("不确定性边界", section.get("uncertainty") or [], bullets=True))
        lines.extend(_render_watchpoints(section.get("watchpoints") or []))

    lines.extend([
        "---",
        "",
        "模型与证据代际、内部证据标识及计算口径见配套追溯附录。",
        "",
        "人工复核状态必须由独立审核记录更新；自动生成不得宣称审核已经完成。",
        "",
    ])
    return "\n".join(lines)
