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
    "gate_id",
    "stage",
    "target_artifact",
    "description",
    "fix_owner",
    "status",
    "notes",
]

STRUCTURED_SOURCES = {"tushare", "baostock", "local_fixture", "tencent_finance", "mootdx"}
REQUIRED_PACKS = [
    "financial_metric_pack.csv",
    "valuation_snapshot.yaml",
    "technical_snapshot.yaml",
    "source_gap_report.md",
]


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
    gate_id: str,
    stage: str,
    target_artifact: str,
    description: str,
    fix_owner: str = "evidence-ingest",
    status: str = "open",
    notes: str = "",
) -> None:
    issue_id = f"DLQ-{gate_id}-{len(issues) + 1:03d}"
    issues.append(
        {
            "issue_id": issue_id,
            "severity": severity,
            "gate_id": gate_id,
            "stage": stage,
            "target_artifact": target_artifact,
            "description": description,
            "fix_owner": fix_owner,
            "status": status,
            "notes": notes,
        }
    )


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
                gate_id="G-DL1",
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
                    gate_id="G-DL1",
                    stage="source_permission",
                    target_artifact=str(manifest_path),
                    description=f"{source_name} does not allow source_type={source_type}",
                )
        if row.get("reliability_rank") == "D" and row.get("material_claim_allowed") != "false":
            add_issue(
                issues,
                severity="high",
                gate_id="G-DL1",
                stage="source_permission",
                target_artifact=str(manifest_path),
                description="D-rank source must use material_claim_allowed=false",
            )
        if source_name in STRUCTURED_SOURCES and row.get("material_claim_allowed") != "metric_only":
            add_issue(
                issues,
                severity="high",
                gate_id="G-DL1",
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
                    gate_id="G-DL2",
                    stage="raw_archive",
                    target_artifact=row.get("evidence_id", ""),
                    description="archive policy requires raw_file_path",
                )
            elif not resolve_path(target, repo_root=repo_root, run_dir=run_dir).exists():
                add_issue(
                    issues,
                    severity="high",
                    gate_id="G-DL2",
                    stage="raw_archive",
                    target_artifact=target,
                    description="raw file path does not exist",
                )
        if not (row.get("file_hash") or row.get("content_hash") or row.get("api_params_hash")):
            add_issue(
                issues,
                severity="high",
                gate_id="G-DL2",
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
                    gate_id="G-DL3",
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
                gate_id="G-DL4",
                stage="field_schema",
                target_artifact=table,
                description="processed table missing or empty",
            )
            continue
        if not header.intersection(id_fields):
            add_issue(
                issues,
                severity="high",
                gate_id="G-DL4",
                stage="field_schema",
                target_artifact=table,
                description="normalized table lacks stock_code/ts_code/code",
            )
        if not header.intersection(date_fields):
            add_issue(
                issues,
                severity="high",
                gate_id="G-DL4",
                stage="field_schema",
                target_artifact=table,
                description="normalized table lacks period/trade_date/as_of_date",
            )
        if not (header - non_metric):
            add_issue(
                issues,
                severity="high",
                gate_id="G-DL4",
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
                gate_id="G-DL5",
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
                gate_id="G-DL5",
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
                gate_id="G-DL8",
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
                gate_id="G-DL6",
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
                gate_id="G-DL7",
                stage="license_terms",
                target_artifact=str(path),
                description="artifact contains token_value field",
            )
        for value in token_values:
            if len(value) >= 8 and value in text:
                add_issue(
                    issues,
                    severity="high",
                    gate_id="G-DL7",
                    stage="license_terms",
                    target_artifact=str(path),
                    description="artifact contains an environment token value",
                )


def write_issue_list(path: Path, issues: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ISSUE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(issues)


def write_report(path: Path, *, final_status: str, issues: list[dict[str, str]]) -> None:
    high = sum(1 for issue in issues if issue["severity"] == "high")
    medium = sum(1 for issue in issues if issue["severity"] == "medium")
    lines = [
        "# Data Layer Quality Report",
        "",
        f"final_status: {final_status}",
        f"high_issues: {high}",
        f"medium_issues: {medium}",
        "",
        "| gate | status |",
        "|---|---|",
    ]
    for gate in ["G-DL1", "G-DL2", "G-DL3", "G-DL4", "G-DL5", "G-DL6", "G-DL7", "G-DL8"]:
        gate_issues = [issue for issue in issues if issue["gate_id"] == gate]
        lines.append(f"| {gate} | {'pass' if not gate_issues else 'needs_fix'} |")
    if issues:
        lines.extend(["", "## Issues", "", "| issue_id | severity | target_artifact | description |", "|---|---|---|---|"])
        for issue in issues:
            lines.append(
                f"| {issue['issue_id']} | {issue['severity']} | {issue['target_artifact']} | {issue['description']} |"
            )
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
            gate_id="G-DL2",
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

    high = sum(1 for issue in issues if issue["severity"] == "high")
    medium = sum(1 for issue in issues if issue["severity"] == "medium")
    final_status = "accepted" if high == 0 and medium == 0 else "accepted_with_todos" if high == 0 else "needs_fix"
    write_issue_list(run_dir / "data_layer_issue_list.csv", issues)
    write_report(run_dir / "data_layer_quality_report.md", final_status=final_status, issues=issues)
    return {"final_status": final_status, "high_issues": high, "medium_issues": medium, "issues": issues}


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
    return 1 if result["high_issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
