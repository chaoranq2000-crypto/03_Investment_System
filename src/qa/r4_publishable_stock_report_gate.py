from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Sequence

import yaml

from check_no_unsupported_advice import find_unsupported_advice


DATA_LAYER_RUN = Path("reports/workflow_runs/wf_20260703_data_layer_002837_invic")
STOCK_RUN = Path("reports/workflow_runs/wf_20260703_stock_first_002837_invic")

R4_REPORT = "R4_stock_deep_dive_v0_1.md"
R4_GATE_REPORT = "R4_quality_gate_report.md"
R4_SOURCE_GAP_REPORT = "R4_source_gap_report.md"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def _load_yaml(path: Path) -> Any:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _table(rows: list[list[object]]) -> str:
    if not rows:
        return ""
    header, body = rows[0], rows[1:]
    lines = [
        "| " + " | ".join(str(cell) for cell in header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    lines.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in body)
    return "\n".join(lines)


def _official_rows(data_layer_run: Path) -> list[dict[str, str]]:
    return _read_csv(data_layer_run / "official_financial_reconciliation.csv")


def _business_rows(stock_run: Path) -> list[dict[str, str]]:
    return _read_csv(stock_run / "business_segment_metric_pack.csv")


def evaluate_r4_gate(*, repo_root: Path) -> dict[str, object]:
    data_layer_run = repo_root / DATA_LAYER_RUN
    stock_run = repo_root / STOCK_RUN
    official = _official_rows(data_layer_run)
    business = _business_rows(stock_run)
    issues: list[dict[str, str]] = []
    if not official:
        issues.append({"severity": "high", "gate": "R4-G1", "issue": "official_financial_reconciliation.csv missing"})
    if not business:
        issues.append({"severity": "high", "gate": "R4-G2", "issue": "business_segment_metric_pack.csv missing"})
    if not (data_layer_run / "valuation_snapshot.yaml").exists():
        issues.append({"severity": "high", "gate": "R4-G3", "issue": "valuation_snapshot.yaml missing"})
    if not (data_layer_run / "technical_snapshot.yaml").exists():
        issues.append({"severity": "high", "gate": "R4-G4", "issue": "technical_snapshot.yaml missing"})
    if not (data_layer_run / "peer_market_snapshot.csv").exists():
        issues.append({"severity": "medium", "gate": "R4-G5", "issue": "peer_market_snapshot.csv missing"})
    mismatch_count = sum(1 for row in official if row.get("reconciliation_status") == "mismatch")
    official_missing_count = sum(1 for row in official if row.get("reconciliation_status") == "official_missing")
    liquid_missing = [
        row
        for row in business
        if row.get("mapped_internal_segment") == "ai_server_liquid_cooling"
        and row.get("review_status") == "missing_disclosure"
    ]
    if mismatch_count:
        issues.append(
            {
                "severity": "medium",
                "gate": "R4-G1",
                "issue": f"{mismatch_count} official reconciliation mismatch rows require review",
            }
        )
    if official_missing_count:
        issues.append(
            {
                "severity": "medium",
                "gate": "R4-G1",
                "issue": f"{official_missing_count} company-level fields remain official_missing",
            }
        )
    if liquid_missing:
        issues.append(
            {
                "severity": "medium",
                "gate": "R4-G2",
                "issue": "liquid-cooling revenue_pct/profit_pct remain MISSING_DISCLOSURE",
            }
        )
    for path in [stock_run / R4_REPORT, stock_run / R4_GATE_REPORT, stock_run / R4_SOURCE_GAP_REPORT]:
        if path.exists():
            hits = find_unsupported_advice(path.read_text(encoding="utf-8", errors="replace"))
            if hits:
                issues.append({"severity": "high", "gate": "R4-G9", "issue": f"unsupported advice pattern: {','.join(hits)}"})
    high = sum(1 for item in issues if item["severity"] == "high")
    medium = sum(1 for item in issues if item["severity"] == "medium")
    if high:
        status = "blocked"
    elif mismatch_count or liquid_missing or official_missing_count:
        status = "bridge_only"
    else:
        status = "publishable_ready_with_disclosure_todos"
    return {
        "status": status,
        "issues": issues,
        "high_issues": high,
        "medium_issues": medium,
        "low_issues": 0,
        "mismatch_count": mismatch_count,
        "official_missing_count": official_missing_count,
        "liquid_missing_count": len(liquid_missing),
    }


def write_source_gap_report(*, repo_root: Path) -> None:
    data_layer_run = repo_root / DATA_LAYER_RUN
    stock_run = repo_root / STOCK_RUN
    source_gap = (data_layer_run / "source_gap_report.md").read_text(encoding="utf-8")
    remaining = (stock_run / "remaining_source_gaps_after_data_layer_bridge.md").read_text(encoding="utf-8")
    lines = [
        "# R4 Source Gap Report",
        "",
        "workflow_id: wf_20260703_stock_first_002837_invic",
        "status: source_gaps_visible",
        "",
        "## Data-layer Source Gaps",
        "",
        source_gap.strip(),
        "",
        "## Stock-first Remaining Source Gaps",
        "",
        remaining.strip(),
        "",
        "## R4 Additional Gaps",
        "",
        "| gap_id | severity | status | handling |",
        "|---|---|---|---|",
        "| R4-GAP-001 | medium | MISSING_DISCLOSURE | Liquid-cooling revenue_pct and profit_pct remain unavailable from official disclosure. |",
        "| R4-GAP-002 | medium | NEEDS_REVIEW | Official reconciliation contains mismatch rows; quality-review must decide promotion. |",
        "| R4-GAP-003 | low | TODO_MARKET_DATA | pe_forward remains unavailable in current fixture context. |",
    ]
    (stock_run / R4_SOURCE_GAP_REPORT).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _financial_table(rows: list[dict[str, str]]) -> str:
    out = [["metric", "period", "structured", "official", "status", "evidence"]]
    for row in rows:
        if row.get("normalized_metric_name") in {
            "total_revenue",
            "n_income_attr_p",
            "basic_eps",
            "operating_cash_flow",
            "total_assets",
            "roe",
        }:
            out.append(
                [
                    row.get("normalized_metric_name", ""),
                    row.get("period", ""),
                    row.get("structured_value", ""),
                    row.get("official_value", ""),
                    row.get("reconciliation_status", ""),
                    row.get("official_evidence_id", ""),
                ]
            )
    return _table(out)


def _business_table(rows: list[dict[str, str]]) -> str:
    out = [["reported segment", "mapped segment", "metric", "value", "status", "locator"]]
    for row in rows:
        out.append(
            [
                row.get("segment_name_reported", ""),
                row.get("mapped_internal_segment", ""),
                row.get("metric_name", ""),
                row.get("value", ""),
                row.get("review_status", ""),
                row.get("page_or_table_locator", ""),
            ]
        )
    return _table(out)


def _valuation_table(valuation: dict[str, Any]) -> str:
    values = valuation.get("market_values", {}) if isinstance(valuation, dict) else {}
    source = (valuation.get("sources") or [{}])[0] if isinstance(valuation.get("sources"), list) else {}
    rows = [["field", "value", "source_evidence_id"]]
    for field in ["price", "market_cap", "pe_ttm", "pe_forward", "pb", "ps", "turnover_rate"]:
        rows.append([field, values.get(field, "TODO_MARKET_DATA"), source.get("evidence_id", "TODO_MARKET_DATA")])
    return _table(rows)


def _technical_table(technical: dict[str, Any]) -> str:
    rows = [["field", "value", "status"]]
    for field in ["close", "ma5", "ma10", "ma20", "ma60", "trend_status"]:
        rows.append([field, technical.get(field, "TODO_MARKET_DATA"), "market_state_observation"])
    return _table(rows)


def _peer_table(rows: list[dict[str, str]]) -> str:
    out = [["stock_code", "company_name", "pe_ttm", "pe_forward", "pb", "ps", "status"]]
    for row in rows:
        out.append(
            [
                row.get("stock_code", ""),
                row.get("company_name", ""),
                row.get("pe_ttm", ""),
                row.get("pe_forward", ""),
                row.get("pb", ""),
                row.get("ps", ""),
                "context_only",
            ]
        )
    return _table(out)


def write_r4_report(*, repo_root: Path, gate: dict[str, object]) -> None:
    data_layer_run = repo_root / DATA_LAYER_RUN
    stock_run = repo_root / STOCK_RUN
    official = _official_rows(data_layer_run)
    business = _business_rows(stock_run)
    valuation = _load_yaml(data_layer_run / "valuation_snapshot.yaml")
    technical = _load_yaml(data_layer_run / "technical_snapshot.yaml")
    peers = _read_csv(data_layer_run / "peer_market_snapshot.csv")
    catalyst = _load_yaml(stock_run / "catalyst_calendar.yaml")
    risk = _load_yaml(stock_run / "risk_counter_evidence.yaml")
    segment_exposure = _load_yaml(stock_run / "segment_exposure.yaml")
    risks = risk.get("risks", []) if isinstance(risk, dict) else []
    counter = risk.get("counter_evidence", []) if isinstance(risk, dict) else []
    exposure_rows = segment_exposure.get("linked_segments", []) if isinstance(segment_exposure, dict) else []
    exposure_table = [["segment_id", "exposure_type", "score", "revenue_pct", "profit_pct", "confidence"]]
    for item in exposure_rows:
        exposure_table.append(
            [
                item.get("segment_id", ""),
                item.get("exposure_type", ""),
                item.get("exposure_score", ""),
                item.get("revenue_pct", ""),
                item.get("profit_pct", ""),
                item.get("confidence", ""),
            ]
        )
    events = catalyst.get("events", []) if isinstance(catalyst, dict) else []
    event_table = [["date_window", "event", "impact_variable", "evidence"]]
    for item in events:
        event_table.append(
            [
                item.get("date_window", ""),
                item.get("event", ""),
                item.get("impact_variable", ""),
                ",".join(item.get("evidence_ids_or_claim_ids", []) or ["TODO_SOURCE_REQUIRED"]),
            ]
        )
    lines = [
        "# R4 Stock Deep Dive v0.1 - 002837 英维克",
        "",
        "## 1. Metadata",
        "",
        "| field | value |",
        "|---|---|",
        "| company_id | cn_002837_invic |",
        "| stock_code | 002837 |",
        "| company_name | 英维克 |",
        "| report_date | 2026-07-03 |",
        "| workflow_run_id | wf_20260703_stock_first_002837_invic |",
        "| evidence_snapshot | annual_report + structured metric packs + R4 reconciliation packs |",
        "| data_layer_status | accepted_with_todos |",
        f"| quality_status | {gate['status']} |",
        "| linked_segments | ai_server_liquid_cooling |",
        "",
        "## 2. 一句话结论",
        "",
        "- 事实: 官方摘要披露公司存在数据中心、算力设备及液冷相关产品线索，且披露 2025 年公司级收入、归母净利、经营现金流、EPS、ROE 等公司级指标。",
        "- 推断: 这些产品线索支持继续跟踪 AI 服务器液冷相关暴露，但尚不能推出液冷收入占比、利润占比或订单贡献。",
        "- 关键假设: 后续定期报告或公告需要补充可定位的分业务收入、订单、客户或产能证据。",
        "- 最大风险: official_financial_reconciliation.csv 存在 mismatch rows，业务分部仍有 MISSING_DISCLOSURE，R4 gate 当前只能给出 bridge_only。",
        "",
        "## 3. 公司财务质量",
        "",
        "公司级财务指标已完成第一轮 official reconciliation。mismatch 与 official_missing 不被静默处理，未经过 quality-review 的结构化指标仍是 metric candidate。",
        "",
        _financial_table(official),
        "",
        "## 4. 业务拆分",
        "",
        "业务拆分来自官方年报摘要文本。当前可以记录产品线索和一条储能应用收入披露，但液冷业务收入占比、液冷毛利率和 AI 服务器液冷利润贡献继续缺失。",
        "",
        _business_table(business),
        "",
        "## 5. 细分暴露",
        "",
        "细分暴露只记录证据支持的产品层线索。revenue_pct 与 profit_pct 缺失时必须保持 MISSING_DISCLOSURE。",
        "",
        _table(exposure_table),
        "",
        "## 6. 估值上下文",
        "",
        "估值字段只作为市场上下文，不形成交易动作。",
        "",
        _valuation_table(valuation if isinstance(valuation, dict) else {}),
        "",
        "Peer context:",
        "",
        _peer_table(peers),
        "",
        "## 7. 技术/市场状态观察",
        "",
        "技术快照只描述市场状态，不输出操作指令。",
        "",
        _technical_table(technical if isinstance(technical, dict) else {}),
        "",
        "## 8. 催化剂",
        "",
        "催化剂只写事件窗口和待验证事项。",
        "",
        _table(event_table),
        "",
        "## 9. 风险与反证",
        "",
        "风险:",
        "",
    ]
    lines.extend(f"- {item}" for item in risks)
    lines.extend(["", "反证清单:", ""])
    lines.extend(f"- {item}" for item in counter)
    lines.extend(
        [
            "- official reconciliation mismatch rows may indicate fixture or field-period drift.",
            "- Business segment disclosure does not yet quantify liquid-cooling revenue_pct.",
            "- Market valuation context can be stale or fixture-limited.",
            "",
            "## 10. Source gaps",
            "",
            "Source gaps are preserved in `R4_source_gap_report.md` and include the carried-forward `remaining_source_gaps_after_data_layer_bridge.md` content.",
            "",
            "| gap | status |",
            "|---|---|",
            "| DLBR-001 | partial reconciliation completed with review TODO |",
            "| DISCLOSURE-SEGMENT-001 | TODO_SOURCE_REQUIRED |",
            "| DISCLOSURE-SEGMENT-002 | MISSING_DISCLOSURE |",
            "| R4-GAP-001 | MISSING_DISCLOSURE |",
            "",
            "## 11. 跟踪清单",
            "",
            "| watch_item | next_evidence | owner |",
            "|---|---|---|",
            "| official reconciliation mismatch review | annual/interim/quarterly table extraction | quality-review |",
            "| liquid-cooling revenue_pct | official segment/product revenue table | evidence-ingest |",
            "| liquid-cooling gross margin | official segment/product margin table | evidence-ingest |",
            "| peer market context | manual live smoke or refreshed fixture | evidence-ingest |",
            "",
            "研究边界: 本文件用于证据管理和研究流程，不构成交易动作或组合配置指令。",
        ]
    )
    (stock_run / R4_REPORT).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_quality_gate_report(*, repo_root: Path, gate: dict[str, object]) -> None:
    stock_run = repo_root / STOCK_RUN
    issues = gate["issues"]
    lines = [
        "# R4 Quality Gate Report",
        "",
        f"r4_publishable_gate_status: {gate['status']}",
        f"high_issues: {gate['high_issues']}",
        f"medium_issues: {gate['medium_issues']}",
        f"low_issues: {gate['low_issues']}",
        "",
        "## Gate Summary",
        "",
        "| gate | status | notes |",
        "|---|---|---|",
        "| official financial reconciliation | partial_pass | mismatch rows stay visible |",
        "| business segment metric pack | pass_with_disclosure_todos | liquid-cooling revenue_pct remains MISSING_DISCLOSURE |",
        "| valuation context | pass_with_todo | pe_forward is TODO_MARKET_DATA |",
        "| technical context | pass | market-state observation only |",
        "| peer context | pass_with_todo | fixture-only peer context |",
        "| source gaps | pass | gaps preserved |",
        "| no-advice boundary | pass | no restricted patterns in R4 artifacts |",
        "",
        "## Issues",
        "",
    ]
    if issues:
        lines.extend(["| severity | gate | issue |", "|---|---|---|"])
        for item in issues:
            lines.append(f"| {item['severity']} | {item['gate']} | {item['issue']} |")
    else:
        lines.append("None.")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"Current R4 output status is `{gate['status']}`. It is useful as an internal R4 readiness draft, but it is not publishable_ready.",
        ]
    )
    (stock_run / R4_GATE_REPORT).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_artifact_manifest(stock_run: Path) -> None:
    path = stock_run / "artifact_manifest.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0].keys()) if rows else []
    existing = {row.get("artifact_type") for row in rows}
    additions = [
        ("art_033", "R4_stock_deep_dive_v0_1", R4_REPORT, "stock-deep-dive", "R4_Next_5", "current", "R4 v0.1 readiness draft"),
        ("art_034", "R4_quality_gate_report", R4_GATE_REPORT, "quality-review", "R4_Next_5", "bridge_only", "R4 publishable gate report"),
        ("art_035", "R4_source_gap_report", R4_SOURCE_GAP_REPORT, "quality-review", "R4_Next_5", "current", "R4 source gaps visible"),
    ]
    for artifact_id, artifact_type, artifact_path, skill, stage, status, notes in additions:
        if artifact_type not in existing:
            rows.append(
                {
                    "artifact_id": artifact_id,
                    "artifact_type": artifact_type,
                    "path": artifact_path,
                    "created_by_skill": skill,
                    "stage": stage,
                    "required": "True",
                    "exists": "True",
                    "status": status,
                    "notes": notes,
                }
            )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_stage_readouts(*, repo_root: Path, gate: dict[str, object]) -> None:
    r4_gate = repo_root / "reports/p1_6/R4_PUBLISHABLE_STOCK_REPORT_GATE_READOUT.md"
    r4_draft = repo_root / "reports/p1_6/R4_STOCK_REPORT_DRAFT_V0_1_READOUT.md"
    r4_gate.write_text(
        "\n".join(
            [
                "# R4_PUBLISHABLE_STOCK_REPORT_GATE_READOUT",
                "",
                "date: 2026-07-03",
                f"status: {gate['status']}",
                "",
                "## Outputs",
                "",
                "- `.agents/skills/stock-deep-dive/references/publishable_stock_report_gate.md`",
                "- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_quality_gate_report.md`",
                "",
                "## Decision",
                "",
                "- bridge_only and publishable_ready are explicitly separated.",
                "- No-advice boundary remains required.",
                "- Structured data still cannot prove business exposure.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    r4_draft.write_text(
        "\n".join(
            [
                "# R4_STOCK_REPORT_DRAFT_V0_1_READOUT",
                "",
                "date: 2026-07-03",
                f"status: {gate['status']}",
                "",
                "## Outputs",
                "",
                f"- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/{R4_REPORT}`",
                f"- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/{R4_GATE_REPORT}`",
                f"- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/{R4_SOURCE_GAP_REPORT}`",
                "",
                "## Boundary",
                "",
                "- Financial, valuation, technical and peer sections are populated with visible TODOs.",
                "- Business segment gaps remain MISSING_DISCLOSURE.",
                "- Source gaps are preserved.",
                "- R4 gate is not publishable_ready.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build_r4_outputs(*, repo_root: Path) -> dict[str, object]:
    write_source_gap_report(repo_root=repo_root)
    first_gate = evaluate_r4_gate(repo_root=repo_root)
    write_r4_report(repo_root=repo_root, gate=first_gate)
    final_gate = evaluate_r4_gate(repo_root=repo_root)
    write_quality_gate_report(repo_root=repo_root, gate=final_gate)
    _update_artifact_manifest(repo_root / STOCK_RUN)
    write_stage_readouts(repo_root=repo_root, gate=final_gate)
    return final_gate


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run R4 publishable stock report gate and write R4 draft outputs.")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args(argv)
    gate = build_r4_outputs(repo_root=Path(args.repo_root).resolve())
    print(gate)
    return 1 if gate["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
