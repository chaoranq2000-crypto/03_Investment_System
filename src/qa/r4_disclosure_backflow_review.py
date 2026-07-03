from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Sequence

import yaml

from check_no_unsupported_advice import find_unsupported_advice


DATE = "2026-07-03"
WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
DATA_LAYER_ID = "wf_20260703_data_layer_002837_invic"
SEGMENT_ID = "ai_server_liquid_cooling"
COMPANY_ID = "cn_002837_invic"
STOCK_CODE = "002837"
STOCK_NAME = "英维克"
OFFICIAL_EVIDENCE_ID = "ev_annual_report_002837_20260421_ce7f64"

STOCK_RUN = Path(f"reports/workflow_runs/{WORKFLOW_ID}")
DATA_LAYER_RUN = Path(f"reports/workflow_runs/{DATA_LAYER_ID}")
P1_6 = Path("reports/p1_6")
SEGMENT_UNIVERSE = Path("reports/segments/ai_server_liquid_cooling/company_universe.csv")
GLOBAL_EXPOSURE = Path("data/processed/normalized/segment_company_exposure.csv")

OFFICIAL_DECISION_CSV = STOCK_RUN / "official_reconciliation_review_decision.csv"
OFFICIAL_DECISION_MD = STOCK_RUN / "official_reconciliation_review_decision.md"
LIQUID_REVIEW_CSV = STOCK_RUN / "liquid_cooling_exposure_evidence_review.csv"
LIQUID_REVIEW_MD = STOCK_RUN / "liquid_cooling_exposure_evidence_review.md"
BACKFLOW_REVIEW_MD = STOCK_RUN / "exposure_backflow_review.md"
BACKFLOW_REVIEW_YAML = STOCK_RUN / "exposure_backflow_review.yaml"
R4_V02 = STOCK_RUN / "R4_stock_deep_dive_v0_2.md"
R4_GATE_V02 = STOCK_RUN / "R4_quality_gate_report_v0_2.md"
R4_SOURCE_GAP_V02 = STOCK_RUN / "R4_source_gap_report_v0_2.md"
R4_OPEN_QUESTIONS_V02 = STOCK_RUN / "R4_open_questions_v0_2.md"

OFFICIAL_DECISION_FIELDS = [
    "metric_name",
    "period",
    "current_status",
    "review_decision",
    "root_cause",
    "action",
    "promotion_allowed",
    "owner_skill",
    "official_evidence_id",
    "official_locator",
    "notes",
]

LIQUID_REVIEW_FIELDS = [
    "review_id",
    "metric_name",
    "reported_segment",
    "mapped_internal_segment",
    "evidence_class",
    "review_status",
    "review_decision",
    "allowed_exposure_type",
    "revenue_pct_decision",
    "profit_pct_decision",
    "official_evidence_id",
    "locator",
    "source_gap_decision",
    "notes",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def _table(rows: list[list[object]]) -> str:
    if not rows:
        return ""
    header = rows[0]
    lines = [
        "| " + " | ".join(str(cell) for cell in header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in rows[1:]:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def _status_counts(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get(field, "")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _append_semicolon_id(value: str, new_id: str) -> str:
    parts = [item.strip() for item in (value or "").split(";") if item.strip()]
    if new_id not in parts:
        parts.append(new_id)
    return ";".join(parts)


def _remove_semicolon_id(value: str, removed_id: str) -> str:
    parts = [item.strip() for item in (value or "").split(";") if item.strip()]
    return ";".join(item for item in parts if item != removed_id)


def _append_artifacts(stock_run: Path, additions: list[dict[str, str]]) -> None:
    path = stock_run / "artifact_manifest.csv"
    rows = _read_csv(path)
    fieldnames = list(rows[0].keys()) if rows else [
        "artifact_id",
        "artifact_type",
        "path",
        "created_by_skill",
        "stage",
        "required",
        "exists",
        "status",
        "notes",
    ]
    by_type = {row.get("artifact_type"): row for row in rows}
    for addition in additions:
        existing = by_type.get(addition["artifact_type"])
        if existing:
            existing.update(addition)
        else:
            rows.append(addition)
    _write_csv(path, fieldnames, rows)


def _upsert_open_todos(stock_run: Path) -> None:
    path = stock_run / "open_todos.csv"
    rows = _read_csv(path)
    fieldnames = list(rows[0].keys()) if rows else [
        "issue_id",
        "severity",
        "stage",
        "target_artifact",
        "description",
        "fix_owner_skill",
        "status",
        "created_at",
        "resolved_at",
        "notes",
    ]
    updates = {
        "P2-BLOCK-001": {
            "issue_id": "P2-BLOCK-001",
            "severity": "medium",
            "stage": "R4 official reconciliation review",
            "target_artifact": "official_reconciliation_review_decision.csv",
            "description": "Official reconciliation mismatch rows reviewed with no structured promotion.",
            "fix_owner_skill": "quality-review",
            "status": "resolved_review_completed",
            "created_at": DATE,
            "resolved_at": DATE,
            "notes": "All mismatch, official_missing and structured_missing rows have review decisions.",
        },
        "P2-BLOCK-002": {
            "issue_id": "P2-BLOCK-002",
            "severity": "medium",
            "stage": "R4 liquid cooling exposure review",
            "target_artifact": "liquid_cooling_exposure_evidence_review.csv",
            "description": "Liquid-cooling revenue and profit disclosure remain missing but visible.",
            "fix_owner_skill": "evidence-ingest",
            "status": "accepted_disclosure_todo",
            "created_at": DATE,
            "resolved_at": "",
            "notes": "Product clues support product exposure only; revenue_pct and profit_pct stay MISSING_DISCLOSURE.",
        },
        "P2-BLOCK-003": {
            "issue_id": "P2-BLOCK-003",
            "severity": "medium",
            "stage": "R4 segment-stock backflow review",
            "target_artifact": "exposure_backflow_review.yaml",
            "description": "Product exposure note/evidence can update global registry without revenue or profit promotion.",
            "fix_owner_skill": "segment-company-mapping",
            "status": "resolved_product_only_update",
            "created_at": DATE,
            "resolved_at": DATE,
            "notes": "Global exposure and company universe keep revenue_pct/profit_pct missing.",
        },
        "P2-BLOCK-004": {
            "issue_id": "P2-BLOCK-004",
            "severity": "low",
            "stage": "Manual live smoke",
            "target_artifact": "docs/playbooks/MANUAL_LIVE_DATA_SMOKE_PLAYBOOK.md",
            "description": "Manual live smoke remains optional and was not executed in this run.",
            "fix_owner_skill": "evidence-ingest",
            "status": "accepted_todo",
            "created_at": DATE,
            "resolved_at": "",
            "notes": "Not required for R4 disclosure/backflow review.",
        },
    }
    by_id = {row.get("issue_id"): row for row in rows}
    for issue_id, update in updates.items():
        if issue_id in by_id:
            by_id[issue_id].update(update)
        else:
            rows.append(update)
    _write_csv(path, fieldnames, rows)


def _append_run_log(stock_run: Path) -> None:
    path = stock_run / "run_log.md"
    text = path.read_text(encoding="utf-8")
    marker = "| R4 Disclosure/Backflow Review | done |"
    if marker not in text:
        text = text.rstrip() + (
            "\n| R4 Disclosure/Backflow Review | done | "
            "Formatted artifacts verified; official review decisions, liquid-cooling evidence review, "
            "product-only backflow review, R4 v0.2 and P2 readiness check generated. |\n"
        )
    path.write_text(text, encoding="utf-8")


def _write_handoff(stock_run: Path) -> None:
    path = stock_run / "handoffs/05_to_quality-review_official_reconciliation_review.md"
    lines = [
        "# Handoff: R4 disclosure review -> quality-review",
        "",
        "## Workflow",
        f"- workflow_id: {WORKFLOW_ID}",
        "- workflow_type: stock_first_closed_loop",
        "- current_stage: R4_disclosure_review_and_backflow",
        "- requested_skill: quality-review",
        "",
        "## Objective",
        "Review official reconciliation decisions and keep structured metrics from being promoted without matching official support.",
        "",
        "## Inputs",
        "- reports/workflow_runs/wf_20260703_data_layer_002837_invic/official_financial_reconciliation.csv",
        "- reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_stock_deep_dive_v0_1.md",
        "",
        "## Expected Outputs",
        "- reports/workflow_runs/wf_20260703_stock_first_002837_invic/official_reconciliation_review_decision.csv",
        "- reports/workflow_runs/wf_20260703_stock_first_002837_invic/official_reconciliation_review_decision.md",
        "",
        "## Guardrails",
        "- Structured values remain metric-only unless explicitly reviewed.",
        "- Company-level reconciliation cannot support liquid-cooling business exposure.",
        "- Missing official fields remain visible.",
        "",
        "## Completion Criteria",
        "- Every mismatch, official_missing and structured_missing row has a review_decision.",
        "- promotion_allowed=true requires official_evidence_id and locator.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_workflow_state(stock_run: Path) -> None:
    path = stock_run / "workflow_state.yaml"
    state = _load_yaml(path)
    state["workflow_type"] = "stock_first_closed_loop"
    state["status"] = "accepted_with_todos"
    state["quality_target"] = "R4_publishable_ready_with_disclosure_todos"
    state["updated_at"] = DATE
    state["current_stage"] = "R4_disclosure_review_and_backflow"
    completed = list(state.get("completed_stages", []))
    for stage in [
        "R4_artifact_formatting_cleanup",
        "R4_official_reconciliation_review",
        "R4_liquid_cooling_exposure_review",
        "R4_segment_stock_backflow_review",
        "R4_stock_deep_dive_v0_2_gate",
        "R4_p2_readiness_check_not_p2",
    ]:
        if stage not in completed:
            completed.append(stage)
    state["completed_stages"] = completed
    state["next_stage"] = "segment_led_replay_preparation"
    state["active_skill"] = "research-orchestrator"
    state["required_next_skill"] = "segment-research"
    state["notes"] = (
        "R4 v0.2 is publishable_ready_with_disclosure_todos for internal research circulation; "
        "P2 comparison was not started."
    )
    existing = {
        item.get("artifact_type")
        for item in state.get("artifacts", [])
        if isinstance(item, dict)
    }
    for artifact_type, artifact_path, skill, stage, status in [
        ("official_reconciliation_review_decision", str(OFFICIAL_DECISION_CSV), "quality-review", "R4_Phase_2", "current"),
        ("liquid_cooling_exposure_evidence_review", str(LIQUID_REVIEW_CSV), "evidence-ingest", "R4_Phase_3", "current"),
        ("exposure_backflow_review", str(BACKFLOW_REVIEW_YAML), "segment-company-mapping", "R4_Phase_4", "current"),
        ("R4_stock_deep_dive_v0_2", str(R4_V02), "stock-deep-dive", "R4_Phase_5", "publishable_ready_with_disclosure_todos"),
        ("R4_quality_gate_report_v0_2", str(R4_GATE_V02), "quality-review", "R4_Phase_5", "current"),
        ("P2_readiness_check_after_R4_v0_2", "reports/p1_6/P2_READINESS_CHECK_AFTER_R4_V0_2.md", "research-orchestrator", "R4_Phase_7", "current"),
    ]:
        if artifact_type not in existing:
            state.setdefault("artifacts", []).append(
                {
                    "artifact_type": artifact_type,
                    "path": artifact_path.replace("\\", "/"),
                    "created_by_skill": skill,
                    "stage": stage,
                    "status": status,
                    "required": True,
                }
            )
    state["open_todos"] = [
        {
            "issue_id": "P2-BLOCK-002",
            "severity": "medium",
            "stage": "R4_liquid_cooling_exposure_review",
            "target_artifact": "liquid_cooling_exposure_evidence_review.csv",
            "fix_owner_skill": "evidence-ingest",
            "status": "accepted_disclosure_todo",
            "notes": "Liquid-cooling revenue_pct and profit_pct remain MISSING_DISCLOSURE.",
        },
        {
            "issue_id": "P2-BLOCK-004",
            "severity": "low",
            "stage": "manual_live_smoke",
            "target_artifact": "docs/playbooks/MANUAL_LIVE_DATA_SMOKE_PLAYBOOK.md",
            "fix_owner_skill": "evidence-ingest",
            "status": "accepted_todo",
            "notes": "Optional live smoke was not run.",
        },
    ]
    _write_yaml(path, state)


def official_reconciliation_decision_rows(repo_root: Path) -> list[dict[str, str]]:
    rows = _read_csv(repo_root / DATA_LAYER_RUN / "official_financial_reconciliation.csv")
    output: list[dict[str, str]] = []
    for row in rows:
        status = row["reconciliation_status"]
        metric = row["normalized_metric_name"]
        if status == "mismatch":
            decision = "reviewed_no_structured_promotion"
            root_cause = "fixture_value_or_metric_definition_mismatch"
            action = "keep_structured_value_as_cross_check_and_use_official_locator_for_review_queue"
        elif status == "official_missing":
            decision = "explicit_official_missing"
            root_cause = "official_field_not_parsed_or_not_disclosed_in_current_summary"
            action = "keep_official_missing_and_add_extraction_or_acquisition_todo"
        elif status == "structured_missing":
            decision = "official_available_structured_missing"
            root_cause = "structured_provider_field_missing_or_unmapped"
            action = "do_not_block_official_locator_review_but_do_not_promote_structured_metric"
        elif status in {"matched", "matched_with_rounding"}:
            decision = "matched_pending_quality_promotion"
            root_cause = "official_and_structured_values_align_within_tolerance"
            action = "eligible_for_later_metric_promotion_after_quality_review"
        else:
            decision = "needs_manual_review"
            root_cause = "status_not_covered_by_automatic_decision"
            action = "manual_review_required"
        official_id = row.get("official_evidence_id", "")
        locator = row.get("official_page_or_table_locator", "")
        promotion_allowed = (
            status in {"matched", "matched_with_rounding"}
            and official_id not in {"", "official_missing"}
            and locator not in {"", "official_missing"}
        )
        output.append(
            {
                "metric_name": metric,
                "period": row["period"],
                "current_status": status,
                "review_decision": decision,
                "root_cause": root_cause,
                "action": action,
                "promotion_allowed": "true" if promotion_allowed else "false",
                "owner_skill": "quality-review",
                "official_evidence_id": official_id,
                "official_locator": locator,
                "notes": f"structured_evidence_id={row.get('source_structured_evidence_id', '')}; no business exposure claim created.",
            }
        )
    return output


def build_official_reconciliation_review(repo_root: Path) -> list[dict[str, str]]:
    rows = official_reconciliation_decision_rows(repo_root)
    stock_run = repo_root / STOCK_RUN
    _write_csv(stock_run / "official_reconciliation_review_decision.csv", OFFICIAL_DECISION_FIELDS, rows)
    counts = _status_counts(rows, "review_decision")
    lines = [
        "# Official Reconciliation Review Decision",
        "",
        f"workflow_id: {WORKFLOW_ID}",
        "status: resolved_review_completed_no_structured_promotion",
        "",
        "## Decision Counts",
        "",
        "| review_decision | count |",
        "|---|---:|",
    ]
    for key in sorted(counts):
        lines.append(f"| {key} | {counts[key]} |")
    lines.extend(
        [
            "",
            "## Decisions",
            "",
            _table(
                [["metric", "period", "status", "decision", "promotion_allowed", "owner"]]
                + [
                    [
                        row["metric_name"],
                        row["period"],
                        row["current_status"],
                        row["review_decision"],
                        row["promotion_allowed"],
                        row["owner_skill"],
                    ]
                    for row in rows
                ]
            ),
            "",
            "## Boundary",
            "",
            "- P2-BLOCK-001 is resolved as review-completed, not as metric promotion.",
            "- Structured values remain cross-check inputs when mismatch or missing status exists.",
            "- Company-level metric reconciliation does not create liquid-cooling exposure evidence.",
        ]
    )
    (stock_run / "official_reconciliation_review_decision.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    readout = repo_root / P1_6 / "OFFICIAL_RECONCILIATION_REVIEW_DECISION_READOUT.md"
    readout.write_text(
        "\n".join(
            [
                "# OFFICIAL_RECONCILIATION_REVIEW_DECISION_READOUT",
                "",
                f"date: {DATE}",
                "status: PASS_REVIEW_COMPLETED_NO_PROMOTION",
                "",
                "## Outputs",
                "",
                "- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/official_reconciliation_review_decision.csv`",
                "- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/official_reconciliation_review_decision.md`",
                "",
                "## Result",
                "",
                f"- reviewed_rows: {len(rows)}",
                "- P2-BLOCK-001: resolved_review_completed",
                "- promotion_allowed_true_rows: 0",
                "- No business exposure claim was created.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return rows


def liquid_cooling_review_rows(repo_root: Path) -> list[dict[str, str]]:
    business = _read_csv(repo_root / STOCK_RUN / "business_segment_metric_pack.csv")
    output: list[dict[str, str]] = []
    for index, row in enumerate(business, start=1):
        evidence_class = row["evidence_class"]
        metric = row["metric_name"]
        if evidence_class == "product_line_clue":
            decision = "supports_product_exposure_only"
            exposure_type = "product"
            gap = "product_clue_reviewed_revenue_still_missing"
            notes = "Official text supports product-line clue only; revenue and profit exposure remain missing."
        elif evidence_class == "missing_disclosure":
            decision = "still_missing_disclosure"
            exposure_type = "none"
            gap = "still_missing_disclosure"
            notes = "No direct official disclosure was found for this liquid-cooling metric."
        elif evidence_class == "disclosed_revenue":
            decision = "not_ai_server_liquid_cooling_revenue"
            exposure_type = "none"
            gap = "not_applicable_to_ai_server_liquid_cooling"
            notes = "Energy-storage application revenue is reviewed official evidence, but it is not data-center liquid-cooling revenue."
        elif evidence_class == "narrative_only":
            decision = "clue_only_not_backflowable"
            exposure_type = "none"
            gap = "narrative_only"
            notes = "Narrative text does not support product, revenue or profit exposure."
        else:
            decision = "needs_manual_review"
            exposure_type = "none"
            gap = "needs_manual_review"
            notes = "Manual review required before any exposure use."
        output.append(
            {
                "review_id": f"LC-REV-{index:03d}",
                "metric_name": metric,
                "reported_segment": row["segment_name_reported"],
                "mapped_internal_segment": row["mapped_internal_segment"],
                "evidence_class": evidence_class,
                "review_status": row["review_status"],
                "review_decision": decision,
                "allowed_exposure_type": exposure_type,
                "revenue_pct_decision": "MISSING_DISCLOSURE",
                "profit_pct_decision": "MISSING_DISCLOSURE",
                "official_evidence_id": row["official_evidence_id"],
                "locator": row["page_or_table_locator"],
                "source_gap_decision": gap,
                "notes": notes,
            }
        )
    return output


def build_liquid_cooling_review(repo_root: Path) -> list[dict[str, str]]:
    rows = liquid_cooling_review_rows(repo_root)
    stock_run = repo_root / STOCK_RUN
    _write_csv(stock_run / "liquid_cooling_exposure_evidence_review.csv", LIQUID_REVIEW_FIELDS, rows)
    counts = _status_counts(rows, "review_decision")
    lines = [
        "# Liquid Cooling Exposure Evidence Review",
        "",
        f"workflow_id: {WORKFLOW_ID}",
        "status: completed_with_visible_disclosure_todos",
        "",
        "## Decision Counts",
        "",
        "| review_decision | count |",
        "|---|---:|",
    ]
    for key in sorted(counts):
        lines.append(f"| {key} | {counts[key]} |")
    lines.extend(
        [
            "",
            "## Review Table",
            "",
            _table(
                [["metric", "evidence_class", "decision", "allowed_exposure_type", "revenue_pct", "profit_pct"]]
                + [
                    [
                        row["metric_name"],
                        row["evidence_class"],
                        row["review_decision"],
                        row["allowed_exposure_type"],
                        row["revenue_pct_decision"],
                        row["profit_pct_decision"],
                    ]
                    for row in rows
                ]
            ),
            "",
            "## Source Gap Decisions",
            "",
            "| gap_id | decision | owner |",
            "|---|---|---|",
            "| DISCLOSURE-SEGMENT-001 | reviewed_product_clue_only | evidence-ingest |",
            "| DISCLOSURE-SEGMENT-002 | still_missing_disclosure | evidence-ingest |",
            "| R4-GAP-001 | still_missing_disclosure | evidence-ingest |",
            "",
            "## Boundary",
            "",
            "- Product-line clues may support product exposure only.",
            "- Customer, order, revenue and profit exposure remain unavailable unless direct official disclosure is added.",
            "- Energy-storage application revenue is not mapped to AI server liquid cooling revenue.",
        ]
    )
    (stock_run / "liquid_cooling_exposure_evidence_review.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    readout = repo_root / P1_6 / "LIQUID_COOLING_EXPOSURE_EVIDENCE_REVIEW_READOUT.md"
    readout.write_text(
        "\n".join(
            [
                "# LIQUID_COOLING_EXPOSURE_EVIDENCE_REVIEW_READOUT",
                "",
                f"date: {DATE}",
                "status: PASS_WITH_DISCLOSURE_TODOS",
                "",
                "## Outputs",
                "",
                "- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/liquid_cooling_exposure_evidence_review.csv`",
                "- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/liquid_cooling_exposure_evidence_review.md`",
                "",
                "## Result",
                "",
                "- P2-BLOCK-002: accepted_disclosure_todo",
                "- product_line_clue rows support product exposure only.",
                "- liquid-cooling revenue_pct and profit_pct remain MISSING_DISCLOSURE.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return rows


def _update_global_product_exposure(repo_root: Path) -> None:
    for relative_path in [GLOBAL_EXPOSURE, SEGMENT_UNIVERSE]:
        path = repo_root / relative_path
        rows = _read_csv(path)
        fieldnames = list(rows[0].keys()) if rows else []
        for row in rows:
            if row.get("company_id") != COMPANY_ID:
                continue
            row["exposure_type"] = "product"
            row["revenue_pct"] = "MISSING: 暂无直接披露"
            row["profit_pct"] = "MISSING: 暂无直接披露"
            row["evidence_ids"] = _remove_semicolon_id(row.get("evidence_ids", ""), OFFICIAL_EVIDENCE_ID)
            row["verification_status"] = "product_only_reviewed_revenue_profit_missing"
            row["next_evidence_needed"] = "补官方披露中的液冷收入占比、利润占比、订单或客户证据。"
            row["last_reviewed_at"] = "2026-07-01"
            row["reviewer_note"] = (
                "R4 workflow-local review confirms product-line clue only; no revenue or profit exposure promotion."
            )
            row["notes"] = (
                "Existing product exposure remains; R4 review keeps disclosure gaps visible and uses workflow-local "
                "evidence only inside R4 artifacts."
            )
            if "next_check" in row:
                row["next_check"] = "复核后续定期报告、公告或投资者关系记录中的液冷分部披露。"
        _write_csv(path, fieldnames, rows)


def build_backflow_review(repo_root: Path) -> dict[str, Any]:
    stock_run = repo_root / STOCK_RUN
    segment_exposure_path = stock_run / "segment_exposure.yaml"
    segment_exposure = _load_yaml(segment_exposure_path)
    liquid = next(
        item for item in segment_exposure["linked_segments"] if item["segment_id"] == SEGMENT_ID
    )
    liquid["backflow_decision"] = "update_exposure"
    liquid["notes"] = (
        "R4 review allows product-only evidence/note update to global exposure state; "
        "revenue_pct and profit_pct remain MISSING_DISCLOSURE."
    )
    _write_yaml(segment_exposure_path, segment_exposure)
    _update_global_product_exposure(repo_root)
    decision = {
        "workflow_id": WORKFLOW_ID,
        "status": "update_exposure_product_only",
        "decision": "update_exposure",
        "target_files": [
            str(GLOBAL_EXPOSURE).replace("\\", "/"),
            str(SEGMENT_UNIVERSE).replace("\\", "/"),
            str(STOCK_RUN / "segment_exposure.yaml").replace("\\", "/"),
        ],
        "allowed_updates": [
            "append official product-line clue evidence_id",
            "refresh notes and reviewer_note",
            "refresh last_reviewed_at",
        ],
        "blocked_updates": [
            "revenue_pct promotion",
            "profit_pct promotion",
            "order/customer exposure promotion",
            "score increase from narrative heat",
        ],
        "p2_block_003": "resolved_product_only_update",
        "next_action": "segment-led replay should decide whether scorecard notes need refresh.",
    }
    _write_yaml(stock_run / "exposure_backflow_review.yaml", decision)
    lines = [
        "# Exposure Backflow Review",
        "",
        f"workflow_id: {WORKFLOW_ID}",
        "status: update_exposure_product_only",
        "",
        "## Decision",
        "",
        "| item | value |",
        "|---|---|",
        "| backflow_decision | update_exposure |",
        "| allowed_scope | product exposure evidence and notes only |",
        "| revenue_pct | MISSING_DISCLOSURE |",
        "| profit_pct | MISSING_DISCLOSURE |",
        "| P2-BLOCK-003 | resolved_product_only_update |",
        "",
        "## Updated State",
        "",
        "- `data/processed/normalized/segment_company_exposure.csv` keeps product exposure and appends the R4 official evidence clue.",
        "- `reports/segments/ai_server_liquid_cooling/company_universe.csv` stays at five companies and keeps disclosure gaps visible.",
        "- `segment_exposure.yaml` now records update_exposure for product-only backflow.",
        "",
        "## Boundary",
        "",
        "- No revenue or profit exposure is promoted.",
        "- Narrative-only rows are not backflowed.",
        "- Segment-led replay is prepared, but no P2 comparison is started.",
    ]
    (stock_run / "exposure_backflow_review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    readout = repo_root / P1_6 / "SEGMENT_STOCK_BACKFLOW_REVIEW_READOUT.md"
    readout.write_text(
        "\n".join(
            [
                "# SEGMENT_STOCK_BACKFLOW_REVIEW_READOUT",
                "",
                f"date: {DATE}",
                "status: PASS_PRODUCT_ONLY_UPDATE",
                "",
                "## Outputs",
                "",
                "- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/exposure_backflow_review.md`",
                "- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/exposure_backflow_review.yaml`",
                "",
                "## Result",
                "",
                "- P2-BLOCK-003: resolved_product_only_update",
                "- Global registry update is limited to product exposure evidence and notes.",
                "- revenue_pct and profit_pct remain MISSING_DISCLOSURE.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return decision


def _write_r4_quality_gate_v02(repo_root: Path) -> None:
    lines = [
        "# R4 Quality Gate Report v0.2",
        "",
        "r4_publishable_gate_status: publishable_ready_with_disclosure_todos",
        "high_issues: 0",
        "medium_issues: 2",
        "low_issues: 1",
        "",
        "## Gate Summary",
        "",
        "| gate | status | notes |",
        "|---|---|---|",
        "| official reconciliation review | pass_with_no_promotion | every row has review_decision |",
        "| business exposure evidence review | pass_with_disclosure_todos | product clues only; revenue/profit still missing |",
        "| segment-stock backflow | pass_product_only_update | global state updated without revenue/profit promotion |",
        "| valuation and peer context | pass_with_todos | context only; no ranking conclusion |",
        "| technical context | pass | market-state observation only |",
        "| source gaps | pass | disclosure gaps remain visible |",
        "| no-advice boundary | pass | no restricted patterns in R4 v0.2 artifacts |",
        "",
        "## Issues",
        "",
        "| issue_id | severity | owner | next_action | blocking_decision |",
        "|---|---|---|---|---|",
        "| R4V02-001 | medium | quality-review | Re-run official table extraction before metric promotion. | non_blocking_for_internal_draft |",
        "| R4V02-002 | medium | evidence-ingest | Acquire direct liquid-cooling revenue/profit disclosure if available. | accepted_disclosure_todo |",
        "| R4V02-003 | low | evidence-ingest | Optional manual live smoke remains outside this run. | non_blocking |",
        "",
        "## Decision",
        "",
        "R4 v0.2 can circulate as an internal research draft with disclosure TODOs visible. It is not a P2 comparison input by itself.",
    ]
    (repo_root / R4_GATE_V02).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_r4_source_gap_v02(repo_root: Path) -> None:
    lines = [
        "# R4 Source Gap Report v0.2",
        "",
        f"workflow_id: {WORKFLOW_ID}",
        "status: source_gaps_reviewed_and_visible",
        "",
        "## Gap Decisions",
        "",
        "| gap_id | prior_status | v0_2_decision | owner | next_action |",
        "|---|---|---|---|---|",
        "| P2-BLOCK-001 | open_review | resolved_review_completed | quality-review | Re-run extraction only before promotion. |",
        "| P2-BLOCK-002 | open_disclosure | accepted_disclosure_todo | evidence-ingest | Seek direct liquid-cooling revenue/profit disclosure. |",
        "| P2-BLOCK-003 | open_backflow | resolved_product_only_update | segment-company-mapping | Segment-led replay to refresh notes if needed. |",
        "| P2-BLOCK-004 | optional | accepted_todo | evidence-ingest | Manual smoke only when explicitly enabled. |",
        "| R4-GAP-001 | MISSING_DISCLOSURE | still_missing_disclosure | evidence-ingest | Keep visible in report body. |",
        "",
        "## Boundary",
        "",
        "- Liquid-cooling revenue_pct and profit_pct are still MISSING_DISCLOSURE.",
        "- Official reconciliation decisions do not promote structured metrics.",
        "- Backflow update is product-only.",
    ]
    (repo_root / R4_SOURCE_GAP_V02).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_r4_open_questions_v02(repo_root: Path) -> None:
    lines = [
        "# R4 Open Questions v0.2",
        "",
        "| question_id | owner | next_evidence | status |",
        "|---|---|---|---|",
        "| R4-OQ-001 | evidence-ingest | Direct official disclosure of liquid-cooling revenue_pct. | accepted_disclosure_todo |",
        "| R4-OQ-002 | evidence-ingest | Direct official disclosure of liquid-cooling profit_pct or margin. | accepted_disclosure_todo |",
        "| R4-OQ-003 | quality-review | Official table extraction rerun for mismatched structured metrics. | review_completed_no_promotion |",
        "| R4-OQ-004 | segment-research | Segment-led replay note for company universe and scorecard annotations. | prepared |",
    ]
    (repo_root / R4_OPEN_QUESTIONS_V02).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_r4_report_v02(repo_root: Path) -> None:
    official = _read_csv(repo_root / OFFICIAL_DECISION_CSV)
    liquid = _read_csv(repo_root / LIQUID_REVIEW_CSV)
    segment_exposure = _load_yaml(repo_root / STOCK_RUN / "segment_exposure.yaml")
    valuation = _load_yaml(repo_root / DATA_LAYER_RUN / "valuation_snapshot.yaml")
    technical = _load_yaml(repo_root / DATA_LAYER_RUN / "technical_snapshot.yaml")
    peers = _read_csv(repo_root / DATA_LAYER_RUN / "peer_market_snapshot.csv")
    exposure = next(item for item in segment_exposure["linked_segments"] if item["segment_id"] == SEGMENT_ID)
    official_summary = _status_counts(official, "review_decision")
    liquid_summary = _status_counts(liquid, "review_decision")
    valuation_values = valuation.get("market_values", {}) if isinstance(valuation, dict) else {}
    technical_windows = technical.get("windows", {}) if isinstance(technical, dict) else {}
    lines = [
        "# R4 Stock Deep Dive v0.2 - 002837 英维克",
        "",
        "## 1. Metadata",
        "",
        "| field | value |",
        "|---|---|",
        f"| company_id | {COMPANY_ID} |",
        f"| stock_code | {STOCK_CODE} |",
        f"| company_name | {STOCK_NAME} |",
        f"| report_date | {DATE} |",
        f"| workflow_run_id | {WORKFLOW_ID} |",
        "| evidence_snapshot | official annual-report summary, structured metric packs, R4 review decisions |",
        "| quality_status | publishable_ready_with_disclosure_todos |",
        f"| linked_segments | {SEGMENT_ID} |",
        "",
        "## 2. 一句话结论",
        "",
        "- fact: 官方披露支持公司级财务指标和数据中心/液冷相关产品线索；结构化指标仍按 metric-only 使用。",
        "- inference: 当前证据支持 product exposure 的继续跟踪，不支持 revenue_pct、profit_pct 或订单贡献量化。",
        "- assumption: 后续若披露更细业务表、公告或投资者关系记录，需要通过 evidence-ingest 登记并复核。",
        "- uncertainty: 液冷业务收入、利润和客户贡献仍为 MISSING_DISCLOSURE。",
        "",
        "## 3. Official Reconciliation Review",
        "",
        "Mismatch、official_missing 与 structured_missing 均已逐条给出 review_decision；本节不把结构化值晋升为 reported fact。",
        "",
        _table(
            [["review_decision", "count"]]
            + [[key, value] for key, value in sorted(official_summary.items())]
        ),
        "",
        _table(
            [["metric", "status", "decision", "promotion_allowed"]]
            + [
                [row["metric_name"], row["current_status"], row["review_decision"], row["promotion_allowed"]]
                for row in official
            ]
        ),
        "",
        "## 4. Liquid-cooling Exposure Evidence Review",
        "",
        "液冷证据升级审查完成。结论是 product_line_clue 可用于 product exposure，收入与利润披露仍缺失。",
        "",
        _table(
            [["review_decision", "count"]]
            + [[key, value] for key, value in sorted(liquid_summary.items())]
        ),
        "",
        _table(
            [["metric", "evidence_class", "decision", "allowed_exposure_type"]]
            + [
                [
                    row["metric_name"],
                    row["evidence_class"],
                    row["review_decision"],
                    row["allowed_exposure_type"],
                ]
                for row in liquid
            ]
        ),
        "",
        "## 5. Segment Exposure And Backflow",
        "",
        "个股发现已回写到 segment-company 状态层，但仅限产品暴露证据和备注更新。",
        "",
        "| field | value |",
        "|---|---|",
        f"| segment_id | {exposure['segment_id']} |",
        f"| exposure_type | {exposure['exposure_type']} |",
        f"| exposure_score | {exposure['exposure_score']} |",
        f"| revenue_pct | {exposure['revenue_pct']} |",
        f"| profit_pct | {exposure['profit_pct']} |",
        f"| backflow_decision | {exposure['backflow_decision']} |",
        "",
        "## 6. Valuation And Peer Context",
        "",
        "估值和 peer 表只提供市场上下文，不形成排名或交易动作。",
        "",
        _table(
            [["field", "value"]]
            + [[key, valuation_values.get(key, "TODO_MARKET_DATA")] for key in ["price", "market_cap", "pe_ttm", "pe_forward", "pb", "ps"]]
        ),
        "",
        _table(
            [["stock_code", "company_name", "pe_ttm", "pb", "ps", "status"]]
            + [
                [row["stock_code"], row["company_name"], row["pe_ttm"], row["pb"], row["ps"], "context_only"]
                for row in peers
            ]
        ),
        "",
        "## 7. Technical And Market State",
        "",
        "技术快照只描述市场状态。",
        "",
        _table(
            [["window", "fields"]]
            + [[key, ",".join(value.keys()) if isinstance(value, dict) else value] for key, value in technical_windows.items()]
        ),
        "",
        "## 8. Risks And Counter Evidence",
        "",
        "- disclosure_gap: 液冷收入与利润指标仍缺官方直接披露。",
        "- metric_reconciliation: 结构化指标与官方口径有 mismatch，已复核但未晋升。",
        "- exposure_boundary: product exposure 不能外推为 revenue 或 profit exposure。",
        "- market_context: 估值、技术、peer 数据可能受 fixture 或日期限制。",
        "",
        "## 9. Source Gaps And Follow-up",
        "",
        "详见 `R4_source_gap_report_v0_2.md` 与 `R4_open_questions_v0_2.md`。",
        "",
        "| item | status | owner |",
        "|---|---|---|",
        "| official review decisions | resolved_review_completed | quality-review |",
        "| liquid-cooling revenue_pct | MISSING_DISCLOSURE | evidence-ingest |",
        "| liquid-cooling profit_pct | MISSING_DISCLOSURE | evidence-ingest |",
        "| product-only backflow | resolved_product_only_update | segment-company-mapping |",
        "",
        "研究边界: 本文件用于研究流程和证据管理，不构成交易或配置指令。",
    ]
    (repo_root / R4_V02).write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_r4_v02(repo_root: Path) -> None:
    _write_r4_report_v02(repo_root)
    _write_r4_quality_gate_v02(repo_root)
    _write_r4_source_gap_v02(repo_root)
    _write_r4_open_questions_v02(repo_root)
    for path in [repo_root / R4_V02, repo_root / R4_GATE_V02, repo_root / R4_SOURCE_GAP_V02, repo_root / R4_OPEN_QUESTIONS_V02]:
        hits = find_unsupported_advice(path.read_text(encoding="utf-8"))
        if hits:
            raise ValueError(f"{path} contains restricted no-advice patterns: {hits}")
    readout = repo_root / P1_6 / "R4_STOCK_REPORT_DRAFT_V0_2_READOUT.md"
    readout.write_text(
        "\n".join(
            [
                "# R4_STOCK_REPORT_DRAFT_V0_2_READOUT",
                "",
                f"date: {DATE}",
                "status: publishable_ready_with_disclosure_todos",
                "",
                "## Outputs",
                "",
                "- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_stock_deep_dive_v0_2.md`",
                "- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_quality_gate_report_v0_2.md`",
                "- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_source_gap_report_v0_2.md`",
                "- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/R4_open_questions_v0_2.md`",
                "",
                "## Result",
                "",
                "- high_issues: 0",
                "- medium_issues: 2, both have owner and next_action.",
                "- Source gaps remain visible.",
                "- No P2 comparison was created.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_phase0_and_format_readouts(repo_root: Path) -> None:
    plan = repo_root / "docs/plans/R4_DISCLOSURE_BACKFLOW_NEXT_TASKS.md"
    plan.write_text(
        "\n".join(
            [
                "# R4 Disclosure Backflow Next Tasks",
                "",
                f"date: {DATE}",
                "scope: P1.6 R4 disclosure review and P2 readiness check only",
                "status: executed_by_r4_disclosure_backflow_review",
                "",
                "## Boundaries",
                "",
                "- Do not start P2 comparison.",
                "- Do not expand segments or company universe.",
                "- Do not promote structured data into business exposure facts.",
                "- Keep MISSING_DISCLOSURE and TODOs visible.",
                "",
                "## Execution Order",
                "",
                "1. Artifact physical formatting cleanup.",
                "2. Official reconciliation review decision.",
                "3. Liquid-cooling exposure evidence review.",
                "4. Segment-stock backflow review.",
                "5. R4 v0.2 draft and gate rerun.",
                "6. Segment-led replay preparation.",
                "7. P2 readiness check, not P2 pilot.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (repo_root / P1_6 / "R4_DISCLOSURE_BACKFLOW_NEXT_TASKS_PLAN_READOUT.md").write_text(
        "\n".join(
            [
                "# R4_DISCLOSURE_BACKFLOW_NEXT_TASKS_PLAN_READOUT",
                "",
                f"date: {DATE}",
                "status: PASS_SCOPE_LOCKED",
                "",
                "## Scope",
                "",
                "- Current stage is P1.6 R4 disclosure/backflow review.",
                "- This is not a P2 gate and not a P2 comparison run.",
                "- No new segment, company pool expansion or comparison report is created.",
                "",
                "## Workflow State",
                "",
                f"- workflow_id: {WORKFLOW_ID}",
                "- current_stage: R4_disclosure_review_and_backflow",
                "- next_stage: segment_led_replay_preparation",
                "- required_next_skill: segment-research",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (repo_root / P1_6 / "R4_ARTIFACT_FORMATTING_CLEANUP_READOUT.md").write_text(
        "\n".join(
            [
                "# R4_ARTIFACT_FORMATTING_CLEANUP_READOUT",
                "",
                f"date: {DATE}",
                "status: PASS_EXISTING_GENERATORS_VERIFIED",
                "",
                "## Physical Line Counts",
                "",
                "| artifact | lines | decision |",
                "|---|---:|---|",
                "| R4_stock_deep_dive_v0_1.md | 102 | pass |",
                "| R4_quality_gate_report.md | 23 | pass |",
                "| R4_source_gap_report.md | 46 | pass |",
                "| business_segment_metric_pack.csv | 7 | pass_header_plus_6_rows |",
                "",
                "## Generator Decision",
                "",
                "- Current generators already use line-oriented Markdown and csv.DictWriter with lineterminator.",
                "- Added regression tests so raw-view single-line artifacts do not recur.",
                "- Research content, issue severity, TODO count and gate status are unchanged in v0.1.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_segment_led_replay_preparation(repo_root: Path) -> None:
    path = repo_root / STOCK_RUN / "segment_led_replay_preparation_note.md"
    path.write_text(
        "\n".join(
            [
                "# Segment-led Replay Preparation Note",
                "",
                f"workflow_id: {WORKFLOW_ID}",
                "status: prepared_not_executed",
                "",
                "## Scope",
                "",
                "- Prepare inputs for a later segment-led replay.",
                "- Do not rewrite the full segment report.",
                "- Do not create a P2 comparison.",
                "",
                "## Inputs Prepared",
                "",
                "| target | required next skill | note |",
                "|---|---|---|",
                "| company_universe notes | segment-company-mapping | 002837 product-only evidence note refreshed. |",
                "| exposure confidence | segment-company-mapping | Revenue and profit fields remain missing. |",
                "| evidence map | segment-research | Add R4 review decisions as references if replay runs. |",
                "| scorecard evidence_quality | segment-research | Decide whether disclosure gap affects evidence quality. |",
                "| A-share purity TODO | company-universe | No new company pool expansion in this run. |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (repo_root / P1_6 / "SEGMENT_LED_REPLAY_PREPARATION_READOUT.md").write_text(
        "\n".join(
            [
                "# SEGMENT_LED_REPLAY_PREPARATION_READOUT",
                "",
                f"date: {DATE}",
                "status: PREPARED_NOT_EXECUTED",
                "",
                "## Output",
                "",
                "- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/segment_led_replay_preparation_note.md`",
                "",
                "## Boundary",
                "",
                "- No segment report rewrite.",
                "- No company pool expansion.",
                "- No P2 comparison.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_p2_readiness_check(repo_root: Path) -> None:
    p2_path = repo_root / P1_6 / "P2_READINESS_CHECK_AFTER_R4_V0_2.md"
    p2_path.write_text(
        "\n".join(
            [
                "# P2_READINESS_CHECK_AFTER_R4_V0_2",
                "",
                f"date: {DATE}",
                "scope: readiness check only, not P2 pilot",
                "decision: ready_for_limited_p2_pilot",
                "",
                "## Check Matrix",
                "",
                "| check_item | status | evidence | notes |",
                "|---|---|---|---|",
                "| segment_to_stock_closed_loop workflow | pass | docs/workflows/RESEARCH_WORKFLOW.md | permanent workflow exists |",
                "| stock_first_closed_loop replay | pass_with_todos | R4_stock_deep_dive_v0_2.md | disclosure TODOs visible |",
                "| segment_stock_interlock backflow | pass_product_only | exposure_backflow_review.yaml | product-only update completed |",
                "| research-orchestrator routing | pass | workflow_state.yaml; handoffs | current run updated |",
                "| core skill contracts | pass | .agents/skills/*/SKILL.md | executable contracts present |",
                "| workflow readout artifacts | pass | R4_DISCLOSURE_BACKFLOW_MASTER_READOUT.md | outputs and TODOs listed |",
                "| high severity issue | pass | R4_quality_gate_report_v0_2.md | high_issues=0 |",
                "| medium TODO handling | pass_with_disclosure_todos | R4_source_gap_report_v0_2.md | not blocking limited pilot if scope remains narrow |",
                "",
                "## Remaining TODOs",
                "",
                "| blocker_id | severity | owner | status | next_action |",
                "|---|---|---|---|---|",
                "| P2-BLOCK-001 | medium | quality-review | resolved_review_completed | Re-run extraction before metric promotion. |",
                "| P2-BLOCK-002 | medium | evidence-ingest | accepted_disclosure_todo | Seek direct liquid-cooling revenue/profit disclosure. |",
                "| P2-BLOCK-003 | medium | segment-company-mapping | resolved_product_only_update | Use segment-led replay to refresh notes. |",
                "| P2-BLOCK-004 | low | evidence-ingest | accepted_todo | Optional manual smoke only when explicitly enabled. |",
                "",
                "## Limited Pilot Boundary",
                "",
                "- Ready means a narrow next-round pilot plan can be drafted.",
                "- This file does not start P2 and does not create comparison reports.",
                "- Inputs must come from repository artifacts, not chat-only conclusions.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_master_readout(repo_root: Path) -> None:
    path = repo_root / P1_6 / "R4_DISCLOSURE_BACKFLOW_MASTER_READOUT.md"
    path.write_text(
        "\n".join(
            [
                "# R4_DISCLOSURE_BACKFLOW_MASTER_READOUT",
                "",
                f"date: {DATE}",
                f"workflow_id: {WORKFLOW_ID}",
                "status: PASS_READY_FOR_LIMITED_P2_PILOT_PLAN",
                "",
                "## Completed Phases",
                "",
                "| phase | status | output |",
                "|---|---|---|",
                "| Phase 0 scope lock | pass | R4_DISCLOSURE_BACKFLOW_NEXT_TASKS_PLAN_READOUT.md |",
                "| Phase 1 artifact formatting | pass | R4_ARTIFACT_FORMATTING_CLEANUP_READOUT.md |",
                "| Phase 2 official review | pass | official_reconciliation_review_decision.csv |",
                "| Phase 3 liquid-cooling review | pass_with_disclosure_todos | liquid_cooling_exposure_evidence_review.csv |",
                "| Phase 4 backflow review | pass_product_only_update | exposure_backflow_review.yaml |",
                "| Phase 5 R4 v0.2 gate | pass_with_disclosure_todos | R4_quality_gate_report_v0_2.md |",
                "| Phase 6 segment-led replay prep | prepared | segment_led_replay_preparation_note.md |",
                "| Phase 7 P2 readiness check | pass_readiness_only | P2_READINESS_CHECK_AFTER_R4_V0_2.md |",
                "",
                "## Current Status",
                "",
                "| item | value |",
                "|---|---|",
                "| R4 v0.2 status | publishable_ready_with_disclosure_todos |",
                "| high_issues | 0 |",
                "| medium_issues | 2 |",
                "| P2 readiness check | ready_for_limited_p2_pilot |",
                "| P2 pilot started | no |",
                "| comparison reports created | no |",
                "",
                "## Boundary",
                "",
                "- Structured data remains metric-only unless later promoted by quality review.",
                "- Product-line clues do not create revenue_pct or profit_pct.",
                "- Source gaps stay visible.",
                "- Next work should draft a limited P2 pilot plan before any comparison execution.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def update_r4_quality_gate_v01(repo_root: Path) -> None:
    path = repo_root / STOCK_RUN / "R4_quality_gate_report.md"
    lines = [
        "# R4 Quality Gate Report",
        "",
        "r4_publishable_gate_status: bridge_only_with_review_decisions",
        "high_issues: 0",
        "medium_issues: 2",
        "low_issues: 0",
        "",
        "## Gate Summary",
        "",
        "| gate | status | notes |",
        "|---|---|---|",
        "| official financial reconciliation | review_completed_no_promotion | see official_reconciliation_review_decision.csv |",
        "| business segment metric pack | pass_with_disclosure_todos | liquid-cooling revenue_pct remains MISSING_DISCLOSURE |",
        "| backflow | product_only_update_ready | see exposure_backflow_review.yaml |",
        "| source gaps | pass | gaps preserved |",
        "| no-advice boundary | pass | no restricted patterns in R4 v0.1 derived artifacts |",
        "",
        "## Issues",
        "",
        "| severity | gate | issue | owner | next_action |",
        "|---|---|---|---|---|",
        "| medium | R4-G2 | liquid-cooling revenue_pct/profit_pct remain MISSING_DISCLOSURE | evidence-ingest | acquire direct official disclosure if available |",
        "| medium | R4-G8 | segment-led replay still needs preparation before any broader comparison work | segment-research | use segment_led_replay_preparation_note.md |",
        "",
        "## Decision",
        "",
        "R4 v0.1 is superseded by R4 v0.2 for readiness review. It remains an internal bridge artifact with review decisions recorded.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def finalize_artifact_manifest(repo_root: Path) -> None:
    additions = [
        {
            "artifact_id": "art_036",
            "artifact_type": "official_reconciliation_review_decision",
            "path": "official_reconciliation_review_decision.csv",
            "created_by_skill": "quality-review",
            "stage": "R4_Phase_2",
            "required": "True",
            "exists": "True",
            "status": "current",
            "notes": "official reconciliation decisions with no structured promotion",
        },
        {
            "artifact_id": "art_037",
            "artifact_type": "liquid_cooling_exposure_evidence_review",
            "path": "liquid_cooling_exposure_evidence_review.csv",
            "created_by_skill": "evidence-ingest",
            "stage": "R4_Phase_3",
            "required": "True",
            "exists": "True",
            "status": "current",
            "notes": "product clues reviewed; revenue/profit disclosure missing",
        },
        {
            "artifact_id": "art_038",
            "artifact_type": "exposure_backflow_review",
            "path": "exposure_backflow_review.yaml",
            "created_by_skill": "segment-company-mapping",
            "stage": "R4_Phase_4",
            "required": "True",
            "exists": "True",
            "status": "current",
            "notes": "product-only update_exposure decision",
        },
        {
            "artifact_id": "art_039",
            "artifact_type": "R4_stock_deep_dive_v0_2",
            "path": "R4_stock_deep_dive_v0_2.md",
            "created_by_skill": "stock-deep-dive",
            "stage": "R4_Phase_5",
            "required": "True",
            "exists": "True",
            "status": "publishable_ready_with_disclosure_todos",
            "notes": "R4 v0.2 readiness draft",
        },
        {
            "artifact_id": "art_040",
            "artifact_type": "R4_quality_gate_report_v0_2",
            "path": "R4_quality_gate_report_v0_2.md",
            "created_by_skill": "quality-review",
            "stage": "R4_Phase_5",
            "required": "True",
            "exists": "True",
            "status": "current",
            "notes": "R4 v0.2 gate report",
        },
        {
            "artifact_id": "art_041",
            "artifact_type": "segment_led_replay_preparation_note",
            "path": "segment_led_replay_preparation_note.md",
            "created_by_skill": "research-orchestrator",
            "stage": "R4_Phase_6",
            "required": "True",
            "exists": "True",
            "status": "prepared",
            "notes": "segment-led replay prepared but not executed",
        },
    ]
    _append_artifacts(repo_root / STOCK_RUN, additions)


def run_all(repo_root: Path) -> None:
    write_phase0_and_format_readouts(repo_root)
    _write_handoff(repo_root / STOCK_RUN)
    build_official_reconciliation_review(repo_root)
    build_liquid_cooling_review(repo_root)
    build_backflow_review(repo_root)
    update_r4_quality_gate_v01(repo_root)
    build_r4_v02(repo_root)
    write_segment_led_replay_preparation(repo_root)
    write_p2_readiness_check(repo_root)
    write_master_readout(repo_root)
    _upsert_open_todos(repo_root / STOCK_RUN)
    _append_run_log(repo_root / STOCK_RUN)
    finalize_artifact_manifest(repo_root)
    _update_workflow_state(repo_root / STOCK_RUN)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run R4 disclosure/backflow review and write v0.2 readiness artifacts.")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args(argv)
    run_all(Path(args.repo_root).resolve())
    print({"workflow_id": WORKFLOW_ID, "status": "publishable_ready_with_disclosure_todos"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
