from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML must be a mapping: {path}")
    return payload


def write_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        yaml.safe_dump(dict(payload), allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    temporary.replace(path)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _append_unique(items: list[Any], value: Any) -> None:
    if value not in items:
        items.append(value)


def _update_state(run: Path) -> dict[str, int]:
    state_path = run / "workflow_state.yaml"
    state = load_yaml(state_path)
    state.update(
        {
            "status": "needs_fix",
            "updated_at": "2026-07-13",
            "current_stage": "R5_bundle8_closed",
            "next_stage": "R5_bundle9_forecast_valuation",
            "active_skill": "research-orchestrator",
            "required_next_skill": "stock-deep-dive",
        }
    )
    completed = state.setdefault("completed_stages", [])
    for stage in (
        "R5_bundle8a_evidence_acquisition_resilience",
        "R5_bundle8b_live_evidence_gap_closure",
        "R5_bundle8_research_depth_close",
    ):
        _append_unique(completed, stage)
    evidence = state.setdefault("evidence_snapshot", {})
    evidence.update(
        {
            "manifest_path": (
                "reports/workflow_runs/wf_20260703_stock_first_002837_invic/"
                "R5_bundle8b_evidence_manifest_delta.csv"
            ),
            "evidence_count": 46,
            "bundle8b_official_ir_count": 4,
            "bundle8b_reviewed_official_ir_count": 4,
            "bundle8b_notes": (
                "46 live evidence rows archived; official IR management comments reviewed; "
                "structured and research metadata remain draft."
            ),
        }
    )
    metrics = state.setdefault("metrics_snapshot", {})
    metrics.update(
        {
            "bundle8b_draft_path": "data/manifests/metrics_draft.csv",
            "bundle8b_new_draft_metric_count": 25586,
            "bundle8b_metric_promotion": False,
            "bundle8b_notes": (
                "Units normalized and non-metric status/date codes removed; new candidates "
                "remain draft until downstream review."
            ),
        }
    )
    state_artifacts = state.setdefault("artifacts", [])
    state_paths = {
        str(item.get("path")) for item in state_artifacts if isinstance(item, Mapping)
    }
    artifacts = [
        ("live_acquisition_run_log", "live_acquisition_run_log.yaml", "evidence-ingest", "T2"),
        ("R5_bundle8b_evidence_manifest_delta", "R5_bundle8b_evidence_manifest_delta.csv", "evidence-ingest", "T2"),
        ("schema_drift_issue_list", "schema_drift_issue_list.csv", "evidence-ingest", "T2"),
        ("liquid_cooling_disclosure_gap_register", "liquid_cooling_disclosure_gap_register.yaml", "evidence-ingest", "T2"),
        ("peer_operating_evidence_pack", "peer_operating_evidence_pack.yaml", "evidence-ingest", "T2"),
        ("market_event_pack", "market_event_pack.yaml", "evidence-ingest", "T7"),
        ("R5_bundle8b_management_comment_review", "R5_bundle8b_management_comment_review.yaml", "quality-review", "T9"),
        ("R5_bundle8b_close_input_validation", "R5_bundle8b_close_input_validation.json", "quality-review", "T9"),
        ("R5_bundle8b_close_quality_issues", "R5_bundle8b_close_quality_issues.csv", "quality-review", "T9"),
        ("bundle8_close_quality_report", "bundle8_close_quality_report.md", "quality-review", "T9"),
        ("bundle8_close_readout", "bundle8_close_readout.md", "research-orchestrator", "T11"),
    ]
    for artifact_type, name, skill, stage in artifacts:
        path_value = f"reports/workflow_runs/{WORKFLOW_ID}/{name}"
        if path_value not in state_paths:
            state_artifacts.append(
                {
                    "artifact_type": artifact_type,
                    "path": path_value,
                    "created_by_skill": skill,
                    "stage": stage,
                    "status": "current",
                    "required": True,
                }
            )
            state_paths.add(path_value)
    resolved_statuses = {
        "P2-BLOCK-004": (
            "resolved_live_smoke_completed",
            "Live smoke completed across Tushare, Baostock, CNINFO and Eastmoney reportapi.",
        ),
        "R5Q-B7-0BF5FA3E": (
            "resolved_bundle8_analysis_pack",
            "Bundle 8 analysis pack has 7/7 complete analytical units.",
        ),
        "R5Q-B7-44F6297D": (
            "resolved_bundle8_evidence_diversity",
            "Bundle 8 source catalog and Bundle 8B live delta satisfy independent-source coverage.",
        ),
        "R5Q-B7-8E0E9760": (
            "resolved_bundle8_industry_inputs",
            "Independent industry and policy sources with counter-evidence are present.",
        ),
        "R5Q-B7-E54AC257": (
            "resolved_bundle8_peer_inputs",
            "Four peer entities now have reviewed scope anchors and same-period structured metrics.",
        ),
        "R5Q-B7-0B636DD2": (
            "resolved_bundle8_technical_inputs",
            "A dated 250-day technical snapshot is available for downstream use.",
        ),
    }
    open_todos = state.setdefault("open_todos", [])
    for todo in open_todos:
        if not isinstance(todo, dict):
            continue
        issue_id = str(todo.get("issue_id", ""))
        if issue_id in resolved_statuses:
            todo["status"], todo["notes"] = resolved_statuses[issue_id]
            todo["resolved_at"] = "2026-07-13"
        if issue_id == "P2-BLOCK-002":
            todo["status"] = "accepted_disclosure_todo_partial_update"
            todo["notes"] = (
                "2024 approximate liquid-cooling-related revenue is available only as a B-class "
                "management comment; 2025 revenue, numeric margin, orders and project cash "
                "collection remain MISSING_DISCLOSURE."
            )
        if issue_id == "R5Q-B7-9A50BA49":
            todo["status"] = "accepted_todo_bundle8_event_chain"
            todo["notes"] = (
                "Planned 2026H1 disclosure date and watch metrics exist; issuer-date verification "
                "and Reader consumption remain pending."
            )
    todo_ids = {
        str(todo.get("issue_id")) for todo in open_todos if isinstance(todo, Mapping)
    }
    carry_todos = [
        ("R5B8B-G3-001", "medium", "T6_forecast_valuation_model", "liquid_cooling_disclosure_gap_register.yaml", "evidence-ingest", "accepted_todo", "Preserve category B approximation and five visible disclosure gaps."),
        ("R5B8B-G8-001", "medium", "T7_technical_sentiment_event_pack", "market_event_pack.yaml", "evidence-ingest", "accepted_todo", "Verify issuer event date and analyst EPS share basis before use."),
        ("R5B8B-QR-SCHEMA-001", "medium", "T2_evidence_acquire_parse", "schema_drift_issue_list.csv", "evidence-ingest", "accepted_todo", "Add reviewed Baostock financial field mapping before promotion."),
        ("R5B8B-QR-PEER-001", "medium", "RP6_valuation", "peer_operating_evidence_pack.yaml", "company-valuation", "accepted_todo", "Reconcile peer metrics to official annual filings and retain scope limits."),
        ("R5B8B-QR-PROXY-001", "low", "T2_evidence_acquire_parse", "source_health_ledger.yaml", "evidence-ingest", "accepted_todo", "Keep push2 degraded until fixture and live-smoke adapter support exists."),
        ("R5B8B-QR-IR004-001", "low", "T2_evidence_acquire_parse", "live_acquisition_run_log.yaml", "evidence-ingest", "accepted_todo", "Acquire the official 2025-004 IR original when a confirmed URL is available."),
        ("R5B8B-QR-CI-001", "low", "T11_close_readout", "bundle8_close_quality_report.md", "research-orchestrator", "accepted_todo", "Run remote CI only after explicit publish authorization."),
    ]
    for issue_id, severity, stage, target, owner, status, notes in carry_todos:
        if issue_id not in todo_ids:
            open_todos.append(
                {
                    "issue_id": issue_id,
                    "severity": severity,
                    "stage": stage,
                    "target_artifact": target,
                    "fix_owner_skill": owner,
                    "status": status,
                    "notes": notes,
                }
            )
    gates = state.setdefault("quality_gates", [])
    gate_ids = {
        str(gate.get("gate_id")) for gate in gates if isinstance(gate, Mapping)
    }
    if "R5_BUNDLE8_CLOSE" not in gate_ids:
        gates.append(
            {
                "gate_id": "R5_BUNDLE8_CLOSE",
                "status": "accepted_with_todos",
                "checked_by": "quality-review",
                "notes": (
                    "46 evidence rows, 45 peer metrics and disclosure boundaries validated; "
                    "full regression 605 passed, 2 skipped; Reader unchanged."
                ),
                "current_scope": "bundle8_local_close",
            }
        )
    state["bundle8_close"] = {
        "decision": "accepted_with_todos",
        "bundle_closed": True,
        "closed_at": "2026-07-13",
        "reader_regenerated": False,
        "reader_score": 59,
        "reader_decision": "rejected",
        "remote_ci": "TODO_AFTER_EXPLICIT_PUBLISH",
        "next_bundle": "R5_bundle9_forecast_valuation",
    }
    backflow = state.setdefault("quality_backflow", {})
    backflow["bundle8_evidence_route_completed"] = True
    backflow["current_first_route"] = "stock-deep-dive"
    backflow["current_first_stage"] = "T6_forecast_valuation_model"
    backflow["sample_quality_report_allowed"] = False
    backflow["p2_allowed"] = False
    write_yaml(state_path, state)
    return {"completed_stages": len(completed), "state_artifacts": len(state_artifacts)}


def _update_open_todos(run: Path) -> dict[str, int]:
    path = run / "open_todos.csv"
    fields, rows = read_csv(path)
    by_id = {row["issue_id"]: row for row in rows}
    resolutions = {
        "P2-BLOCK-004": ("resolved_live_smoke_completed", "Live acquisition completed across multiple independent interfaces."),
        "R5Q-B7-0BF5FA3E": ("resolved_bundle8_analysis_pack", "Bundle 8 analysis pack has 7/7 complete units."),
        "R5Q-B7-44F6297D": ("resolved_bundle8_evidence_diversity", "Independent source coverage is now above the minimum."),
        "R5Q-B7-8E0E9760": ("resolved_bundle8_industry_inputs", "Independent industry and policy inputs are present."),
        "R5Q-B7-E54AC257": ("resolved_bundle8_peer_inputs", "Four peer entities have same-period operating inputs and official scope anchors."),
        "R5Q-B7-0B636DD2": ("resolved_bundle8_technical_inputs", "Dated 250-day technical inputs are present."),
    }
    for issue_id, (status, note) in resolutions.items():
        if issue_id in by_id:
            by_id[issue_id]["status"] = status
            by_id[issue_id]["resolved_at"] = "2026-07-13"
            by_id[issue_id]["notes"] = note
    for issue_id in ("GAP002837-001", "P2-BLOCK-002"):
        if issue_id in by_id:
            by_id[issue_id]["notes"] = (
                "2024 approximate liquid-cooling-related revenue is a B-class management comment; "
                "2025 revenue, numeric margin, orders and project cash collection remain MISSING."
            )
    if "R5Q-B7-9A50BA49" in by_id:
        by_id["R5Q-B7-9A50BA49"]["status"] = "accepted_todo"
        by_id["R5Q-B7-9A50BA49"]["notes"] = (
            "Planned disclosure date and watch metrics exist; issuer verification and Reader "
            "consumption remain pending."
        )
    quality_fields, quality_rows = read_csv(run / "R5_bundle8b_close_quality_issues.csv")
    del quality_fields
    added = 0
    for issue in quality_rows:
        if issue["status"] != "accepted_todo" or issue["issue_id"] in by_id:
            continue
        row = {
            "issue_id": issue["issue_id"],
            "severity": issue["severity"],
            "stage": issue["stage"],
            "target_artifact": issue["target_artifact"],
            "description": issue["description"],
            "fix_owner_skill": issue["fix_owner_skill"],
            "status": "accepted_todo",
            "created_at": "2026-07-13",
            "resolved_at": "",
            "notes": issue["next_action"],
        }
        rows.append(row)
        by_id[row["issue_id"]] = row
        added += 1
    write_csv(path, fields, rows)
    return {"rows": len(rows), "added": added}


def _update_artifact_manifest(repo_root: Path, run: Path) -> dict[str, int]:
    path = run / "artifact_manifest.csv"
    fields, rows = read_csv(path)
    existing_paths = {row["path"] for row in rows}
    numbers = [
        int(row["artifact_id"].split("_")[-1])
        for row in rows
        if row.get("artifact_id", "").startswith("art_")
    ]
    next_number = max(numbers, default=0) + 1
    specs = [
        ("bundle8b_live_acquisition_run_log", "live_acquisition_run_log.yaml", "evidence-ingest", "T2", "46 source runs and proxy matrix"),
        ("bundle8b_evidence_manifest_delta", "R5_bundle8b_evidence_manifest_delta.csv", "evidence-ingest", "T2", "46 unique evidence rows"),
        ("bundle8b_schema_drift_issue_list", "schema_drift_issue_list.csv", "evidence-ingest", "T2", "six schema alias or drift findings"),
        ("bundle8b_liquid_cooling_gap_register", "liquid_cooling_disclosure_gap_register.yaml", "evidence-ingest", "T2", "category B approximation and visible category C gaps"),
        ("bundle8b_peer_operating_evidence_pack", "peer_operating_evidence_pack.yaml", "evidence-ingest", "T2", "five companies and 45 same-period metrics"),
        ("bundle8b_market_event_pack", "market_event_pack.yaml", "evidence-ingest", "T7", "technical valuation event and analyst metadata inputs"),
        ("bundle8b_technical_snapshot", "R5_bundle8b_technical_snapshot.yaml", "evidence-ingest", "T7", "250-day technical snapshot"),
        ("bundle8b_valuation_snapshot", "R5_bundle8b_valuation_snapshot.yaml", "evidence-ingest", "T7", "subject valuation snapshot"),
        ("bundle8b_peer_valuation_300499", "R5_bundle8b_peer_valuation_300499.yaml", "evidence-ingest", "T7", "peer valuation snapshot"),
        ("bundle8b_peer_valuation_300731", "R5_bundle8b_peer_valuation_300731.yaml", "evidence-ingest", "T7", "peer valuation snapshot"),
        ("bundle8b_peer_valuation_301018", "R5_bundle8b_peer_valuation_301018.yaml", "evidence-ingest", "T7", "peer valuation snapshot"),
        ("bundle8b_peer_valuation_300602", "R5_bundle8b_peer_valuation_300602.yaml", "evidence-ingest", "T7", "peer valuation snapshot"),
        ("bundle8b_research_metadata_readout", "R5_bundle8b_eastmoney_research_metadata_readout.json", "evidence-ingest", "T2", "reportapi live smoke readout"),
        ("bundle8b_management_comment_review", "R5_bundle8b_management_comment_review.yaml", "quality-review", "T9", "seven reviewed workflow-local management comments"),
        ("bundle8b_close_input_validation", "R5_bundle8b_close_input_validation.json", "quality-review", "T9", "deterministic decision pass"),
        ("bundle8b_source_route_quality", "R5_bundle8b_source_route_quality_report.yaml", "quality-review", "T9", "12 capabilities and zero blocking"),
        ("bundle8b_quality_issues", "R5_bundle8b_close_quality_issues.csv", "quality-review", "T9", "accepted_with_todos"),
        ("bundle8b_close_quality_report", "bundle8_close_quality_report.md", "quality-review", "T9", "local close authorized"),
        ("bundle8b_handoff_quality", "handoffs/18_to_quality-review_bundle8b_close_gate.md", "research-orchestrator", "T9", "quality dispatch"),
        ("bundle8b_handoff_close", "handoffs/19_to_research-orchestrator_bundle8b_close.md", "quality-review", "T10", "close dispatch"),
        ("bundle8b_close_readout", "bundle8_close_readout.md", "research-orchestrator", "T11", "Bundle 8 locally closed"),
    ]
    added = 0
    for artifact_type, name, skill, stage, notes in specs:
        rel = f"reports/workflow_runs/{WORKFLOW_ID}/{name}"
        if rel in existing_paths:
            continue
        if not (repo_root / rel).exists():
            raise FileNotFoundError(f"required close artifact missing: {rel}")
        rows.append(
            {
                "artifact_id": f"art_{next_number:03d}",
                "artifact_type": artifact_type,
                "path": rel,
                "created_by_skill": skill,
                "stage": stage,
                "required": "True",
                "exists": "True",
                "status": "current",
                "notes": notes,
            }
        )
        existing_paths.add(rel)
        next_number += 1
        added += 1
    write_csv(path, fields, rows)
    return {"rows": len(rows), "added": added}


def _append_run_log(run: Path) -> bool:
    path = run / "run_log.md"
    text = path.read_text(encoding="utf-8")
    marker = "## Bundle 8A/8B local close"
    if marker in text:
        return False
    addition = f"""

{marker}

| Step | Status | Notes |
|---|---|---|
| Live acquisition | done | 46 evidence rows; 25,586 retained new draft metrics after unit and non-metric code normalization. |
| Official IR review | done | Four CNINFO IR files parsed; seven management comments reviewed; no global claim promotion. |
| Disclosure boundary | accepted_with_todos | 2024 approximate liquid-cooling-related revenue is category B; five category C gaps remain visible. |
| Peer and market inputs | done | Five-company 2025 operating pack, four peer valuations, subject valuation, 250-day technical and event packs generated. |
| Proxy audit | done | Tushare, Baostock, CNINFO, SZSE, Tencent and Eastmoney reportapi work; push2 remains degraded via inherited proxy. |
| Quality gate | accepted_with_todos | No active critical/high issue; issue validator and Bundle 8B deterministic validator passed. |
| Regression | done_local | Full repository pytest: 605 passed, 2 skipped. |
| Canonical close | done_local | Bundle 8 closed; workflow remains needs_fix; Reader remains 59/82 rejected; next route is Bundle 9 stock-deep-dive. |
| Publish boundary | preserved | No staging, commit, push or remote CI claim was performed. |
"""
    path.write_text(text.rstrip() + addition + "\n", encoding="utf-8")
    return True


def close_bundle8b(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    run = repo_root / "reports/workflow_runs" / WORKFLOW_ID
    validation = json.loads((run / "R5_bundle8b_close_input_validation.json").read_text(encoding="utf-8"))
    if validation.get("decision") != "pass":
        raise ValueError("Bundle 8B deterministic validation is not pass")
    quality_text = (run / "bundle8_close_quality_report.md").read_text(encoding="utf-8")
    if "decision: `accepted_with_todos`" not in quality_text:
        raise ValueError("Bundle 8B quality decision is not accepted_with_todos")
    result = {
        "state": _update_state(run),
        "todos": _update_open_todos(run),
        "artifacts": _update_artifact_manifest(repo_root, run),
        "run_log_appended": _append_run_log(run),
    }
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Close R5 Bundle 8B locally after quality pass.")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args(argv)
    result = close_bundle8b(Path(args.repo_root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
