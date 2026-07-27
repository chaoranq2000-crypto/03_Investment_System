from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from check_no_unsupported_advice import find_unsupported_advice


ISSUE_FIELDNAMES = [
    "issue_id",
    "severity",
    "issue_class",
    "gate_id",
    "local_check_id",
    "mapped_global_gate_ids",
    "stage",
    "target_artifact",
    "description",
    "fix_owner",
    "status",
    "notes",
]

STRUCTURED_SOURCES = {"tushare", "baostock", "local_fixture", "tencent_finance", "mootdx"}
SEVERITY_ORDER = {"high": 3, "medium": 2, "low": 1}
REQUIRED_PACKS = [
    "financial_metric_pack.csv",
    "valuation_snapshot.yaml",
    "technical_snapshot.yaml",
    "source_gap_report.md",
]

LOCAL_CHECK_GATE_MAP = {
    "DLQ-1": ("G1",),
    "DLQ-2": ("G1",),
    "DLQ-3": ("G1", "G3"),
    "DLQ-4": ("G3",),
    "DLQ-5": ("G2", "G3", "G9"),
    "DLQ-6": ("G3", "G7"),
    "DLQ-7": ("G1", "G10"),
    "DLQ-8": ("G7", "G10"),
}


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def csv_header(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(next(csv.reader(handle), []))


def load_yaml(path: Path) -> Any:
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def resolve_path(value: str, *, repo_root: Path, run_dir: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    repo_path = repo_root / path
    if repo_path.exists():
        return repo_path
    return run_dir / path


def add_issue(
    issues: list[dict[str, str]],
    *,
    severity: str,
    local_check_id: str,
    stage: str,
    target_artifact: str,
    description: str,
    issue_id: str = "",
    fix_owner: str = "evidence-ingest",
    status: str = "",
    notes: str = "",
) -> None:
    severity = severity.lower()
    issue_class = "blocking_issue" if severity == "high" else "accepted_todo"
    mapped_gate_ids = LOCAL_CHECK_GATE_MAP[local_check_id]
    issue_id = issue_id or f"{local_check_id}-{len(issues) + 1:03d}"
    status = status or ("open" if issue_class == "blocking_issue" else "accepted_todo")
    issues.append(
        {
            "issue_id": issue_id,
            "severity": severity,
            "issue_class": issue_class,
            "gate_id": mapped_gate_ids[0],
            "local_check_id": local_check_id,
            "mapped_global_gate_ids": "|".join(mapped_gate_ids),
            "stage": stage,
            "target_artifact": target_artifact,
            "description": description,
            "fix_owner": fix_owner,
            "status": status,
            "notes": notes,
        }
    )


def add_open_todos(run_dir: Path, issues: list[dict[str, str]]) -> None:
    for row in read_csv_dicts(run_dir / "open_todos.csv"):
        severity = row.get("severity", "").lower()
        if severity not in SEVERITY_ORDER:
            severity = "medium"
        status = row.get("status", "accepted_todo") or "accepted_todo"
        add_issue(
            issues,
            issue_id=row.get("issue_id", ""),
            severity=severity,
            local_check_id="DLQ-8",
            stage=row.get("stage", "open_todos"),
            target_artifact=row.get("target_artifact", ""),
            description=row.get("description", ""),
            fix_owner=row.get("fix_owner_skill") or row.get("fix_owner") or "evidence-ingest",
            status=status,
            notes=row.get("notes", ""),
        )


def split_issue_state(issues: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    blocking_issues = [issue for issue in issues if issue["issue_class"] == "blocking_issue"]
    accepted_todos = [issue for issue in issues if issue["issue_class"] == "accepted_todo"]
    return blocking_issues, accepted_todos


def final_status_for(issues: list[dict[str, str]]) -> str:
    blocking_issues, accepted_todos = split_issue_state(issues)
    if blocking_issues:
        return "blocked"
    if accepted_todos:
        return "accepted_with_todos"
    return "accepted"


def source_registry(path: Path) -> dict[str, Any]:
    data = load_yaml(path)
    if not isinstance(data, Mapping):
        return {}
    sources = data.get("sources", {})
    return dict(sources) if isinstance(sources, Mapping) else {}


def check_source_permission(
    *,
    rows: list[dict[str, str]],
    sources: Mapping[str, Any],
    issues: list[dict[str, str]],
    manifest_path: Path,
) -> None:
    for row in rows:
        source_name = row.get("source_name", "")
        source_type = row.get("source_type", "")
        source = sources.get(source_name)
        if source_name != "unknown_source" and not isinstance(source, Mapping):
            add_issue(
                issues,
                severity="high",
                local_check_id="DLQ-1",
                stage="source_permission",
                target_artifact=str(manifest_path),
                description=f"source_name not in source_registry: {source_name}",
            )
            continue
        if isinstance(source, Mapping):
            supported = set(source.get("supported_source_types", []) or [])
            if supported and source_type not in supported:
                add_issue(
                    issues,
                    severity="high",
                    local_check_id="DLQ-1",
                    stage="source_permission",
                    target_artifact=str(manifest_path),
                    description=f"{source_name} does not allow source_type={source_type}",
                )
        if row.get("reliability_rank") == "D" and row.get("material_claim_allowed") != "false":
            add_issue(
                issues,
                severity="high",
                local_check_id="DLQ-1",
                stage="source_permission",
                target_artifact=str(manifest_path),
                description="D-rank source must use material_claim_allowed=false",
            )
        if source_name in STRUCTURED_SOURCES and row.get("material_claim_allowed") != "metric_only":
            add_issue(
                issues,
                severity="high",
                local_check_id="DLQ-1",
                stage="source_permission",
                target_artifact=str(manifest_path),
                description=f"{source_name} structured snapshot must stay metric_only",
            )


def check_raw_archive(
    *,
    rows: list[dict[str, str]],
    repo_root: Path,
    run_dir: Path,
    issues: list[dict[str, str]],
) -> None:
    for row in rows:
        target = row.get("raw_file_path", "")
        policy = row.get("raw_archive_policy", "")
        if policy in {"full_file_archived", "snapshot_archived"}:
            if not target:
                add_issue(
                    issues,
                    severity="high",
                    local_check_id="DLQ-2",
                    stage="raw_archive",
                    target_artifact=row.get("evidence_id", ""),
                    description="archive policy requires raw_file_path",
                )
            elif not resolve_path(target, repo_root=repo_root, run_dir=run_dir).exists():
                add_issue(
                    issues,
                    severity="high",
                    local_check_id="DLQ-2",
                    stage="raw_archive",
                    target_artifact=target,
                    description="raw file path does not exist",
                )
        if not (row.get("file_hash") or row.get("content_hash") or row.get("api_params_hash")):
            add_issue(
                issues,
                severity="high",
                local_check_id="DLQ-2",
                stage="raw_archive",
                target_artifact=row.get("evidence_id", ""),
                description="manifest row lacks file/content/API hash",
            )


def check_reproducibility(
    *,
    rows: list[dict[str, str]],
    issues: list[dict[str, str]],
    manifest_path: Path,
) -> None:
    for row in rows:
        if not row.get("source_type", "").startswith("structured_"):
            continue
        for field in ["api_params_hash", "as_of_date", "retrieved_at", "license_note"]:
            if not row.get(field):
                add_issue(
                    issues,
                    severity="high" if field == "api_params_hash" else "medium",
                    local_check_id="DLQ-3",
                    stage="reproducibility",
                    target_artifact=str(manifest_path),
                    description=f"structured snapshot missing {field}",
                )


def check_field_schema(
    *,
    rows: list[dict[str, str]],
    repo_root: Path,
    run_dir: Path,
    issues: list[dict[str, str]],
) -> None:
    id_fields = {"stock_code", "ts_code", "code"}
    date_fields = {"period", "end_date", "trade_date", "as_of_date", "date"}
    non_metric = id_fields | date_fields | {"name", "symbol", "ann_date", "f_ann_date"}
    for row in rows:
        table = row.get("processed_table_path", "")
        if not table:
            continue
        path = resolve_path(table, repo_root=repo_root, run_dir=run_dir)
        header = set(csv_header(path))
        if not header:
            add_issue(
                issues,
                severity="high",
                local_check_id="DLQ-4",
                stage="field_schema",
                target_artifact=table,
                description="processed table missing or empty",
            )
            continue
        if not header.intersection(id_fields):
            add_issue(
                issues,
                severity="high",
                local_check_id="DLQ-4",
                stage="field_schema",
                target_artifact=table,
                description="normalized table lacks stock_code/ts_code/code",
            )
        if not header.intersection(date_fields):
            add_issue(
                issues,
                severity="high",
                local_check_id="DLQ-4",
                stage="field_schema",
                target_artifact=table,
                description="normalized table lacks period/trade_date/as_of_date",
            )
        if not (header - non_metric):
            add_issue(
                issues,
                severity="high",
                local_check_id="DLQ-4",
                stage="field_schema",
                target_artifact=table,
                description="normalized table lacks metric fields",
            )


def check_metric_only_boundary(
    *,
    run_dir: Path,
    issues: list[dict[str, str]],
) -> None:
    claims_path = run_dir / "claim_candidates.csv"
    for row in read_csv_dicts(claims_path):
        if row.get("source_name") in STRUCTURED_SOURCES:
            add_issue(
                issues,
                severity="high",
                local_check_id="DLQ-5",
                stage="metric_only_boundary",
                target_artifact=str(claims_path),
                description="structured data generated claim candidates",
            )
    for path in list(run_dir.glob("*.md")) + list(run_dir.glob("*.yaml")):
        hits = find_unsupported_advice(path.read_text(encoding="utf-8", errors="replace"))
        if hits:
            add_issue(
                issues,
                severity="high",
                local_check_id="DLQ-5",
                stage="metric_only_boundary",
                target_artifact=str(path),
                description="data layer artifact contains unsupported advice language",
                notes=";".join(hits),
            )


def check_pack_completeness(run_dir: Path, issues: list[dict[str, str]]) -> None:
    for file_name in REQUIRED_PACKS:
        if not (run_dir / file_name).exists():
            add_issue(
                issues,
                severity="medium",
                local_check_id="DLQ-8",
                stage="pack_completeness",
                target_artifact=file_name,
                description=f"required downstream pack missing: {file_name}",
            )
    valuation = load_yaml(run_dir / "valuation_snapshot.yaml")
    if isinstance(valuation, Mapping):
        if valuation.get("as_of_date") in {"", "TODO_MARKET_DATA", None}:
            add_issue(
                issues,
                severity="high",
                local_check_id="DLQ-6",
                stage="freshness",
                target_artifact="valuation_snapshot.yaml",
                description="valuation snapshot lacks trade/as-of date",
            )


def check_token_leak(run_dir: Path, issues: list[dict[str, str]]) -> None:
    token_values = [value for key, value in os.environ.items() if key.endswith("TOKEN") and value]
    for path in [p for p in run_dir.rglob("*") if p.is_file()]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "token_value" in text:
            add_issue(
                issues,
                severity="high",
                local_check_id="DLQ-7",
                stage="license_terms",
                target_artifact=str(path),
                description="artifact contains token_value field",
            )
        for value in token_values:
            if len(value) >= 8 and value in text:
                add_issue(
                    issues,
                    severity="high",
                    local_check_id="DLQ-7",
                    stage="license_terms",
                    target_artifact=str(path),
                    description="artifact contains an environment token value",
                )


def write_issue_list(path: Path, issues: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ISSUE_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(issues)


def write_report(path: Path, *, final_status: str, issues: list[dict[str, str]]) -> None:
    blocking_issues, accepted_todos = split_issue_state(issues)
    high = sum(1 for issue in issues if issue["severity"] == "high")
    medium = sum(1 for issue in issues if issue["severity"] == "medium")
    low = sum(1 for issue in issues if issue["severity"] == "low")
    lines = [
        "# Data Layer Quality Report",
        "",
        f"final_status: {final_status}",
        f"blocking_issues: {len(blocking_issues)}",
        f"accepted_todos: {len(accepted_todos)}",
        f"high_issues: {high}",
        f"medium_issues: {medium}",
        f"low_issues: {low}",
        "",
        "## Summary",
        "",
        "| item | value |",
        "|---|---|",
        f"| final_status | {final_status} |",
        f"| blocking_issues | {len(blocking_issues)} |",
        f"| accepted_todos | {len(accepted_todos)} |",
        f"| high_issues | {high} |",
        f"| medium_issues | {medium} |",
        f"| low_issues | {low} |",
        "",
        "| local_check_id | mapped_global_gate_ids | status |",
        "|---|---|---|",
    ]
    for local_check_id, mapped_gate_ids in LOCAL_CHECK_GATE_MAP.items():
        gate_issues = [issue for issue in issues if issue["local_check_id"] == local_check_id]
        gate_blockers = [issue for issue in gate_issues if issue["issue_class"] == "blocking_issue"]
        status = "blocked" if gate_blockers else "accepted_todo" if gate_issues else "pass"
        lines.append(f"| {local_check_id} | {', '.join(mapped_gate_ids)} | {status} |")
    lines.extend(["", "## Blocking Issues", ""])
    if blocking_issues:
        lines.extend(["| issue_id | severity | target_artifact | description |", "|---|---|---|---|"])
        for issue in blocking_issues:
            lines.append(
                f"| {issue['issue_id']} | {issue['severity']} | {issue['target_artifact']} | {issue['description']} |"
            )
    else:
        lines.append("None.")
    lines.extend(["", "## Accepted Todos", ""])
    if accepted_todos:
        lines.extend(["| issue_id | severity | target_artifact | description |", "|---|---|---|---|"])
        for issue in sorted(
            accepted_todos,
            key=lambda item: (-SEVERITY_ORDER.get(item["severity"], 0), item["issue_id"]),
        ):
            lines.append(
                f"| {issue['issue_id']} | {issue['severity']} | {issue['target_artifact']} | {issue['description']} |"
            )
    else:
        lines.append("None.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def review_data_layer_run(
    *,
    run_dir: Path,
    repo_root: Path,
    source_registry_path: Path,
) -> dict[str, object]:
    manifest_path = run_dir / "evidence_manifest.csv"
    rows = read_csv_dicts(manifest_path)
    issues: list[dict[str, str]] = []
    if not rows:
        add_issue(
            issues,
            severity="high",
            local_check_id="DLQ-2",
            stage="raw_archive",
            target_artifact=str(manifest_path),
            description="workflow-local evidence_manifest.csv is missing or empty",
        )
    sources = source_registry(source_registry_path)
    check_source_permission(rows=rows, sources=sources, issues=issues, manifest_path=manifest_path)
    check_raw_archive(rows=rows, repo_root=repo_root, run_dir=run_dir, issues=issues)
    check_reproducibility(rows=rows, issues=issues, manifest_path=manifest_path)
    check_field_schema(rows=rows, repo_root=repo_root, run_dir=run_dir, issues=issues)
    check_metric_only_boundary(run_dir=run_dir, issues=issues)
    check_pack_completeness(run_dir, issues)
    check_token_leak(run_dir, issues)
    add_open_todos(run_dir, issues)

    blocking_issues, accepted_todos = split_issue_state(issues)
    high = sum(1 for issue in issues if issue["severity"] == "high")
    medium = sum(1 for issue in issues if issue["severity"] == "medium")
    low = sum(1 for issue in issues if issue["severity"] == "low")
    final_status = final_status_for(issues)
    write_issue_list(run_dir / "data_layer_issue_list.csv", issues)
    write_report(run_dir / "data_layer_quality_report.md", final_status=final_status, issues=issues)
    return {
        "final_status": final_status,
        "blocking_issue_count": len(blocking_issues),
        "accepted_todo_count": len(accepted_todos),
        "high_issues": high,
        "medium_issues": medium,
        "low_issues": low,
        "blocking_issues": blocking_issues,
        "accepted_todos": accepted_todos,
        "issues": issues,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run data-layer quality gates.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--source-registry", default="config/source_registry.yaml")
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    result = review_data_layer_run(
        run_dir=Path(args.run_dir),
        repo_root=repo_root,
        source_registry_path=(repo_root / args.source_registry),
    )
    print(result)
    return 1 if result["blocking_issue_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
