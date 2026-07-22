#!/usr/bin/env python3
"""Build the isolated, offline 002837 V1 replay run.

The source workflow is read-only.  This runner recomputes the archived Bundle 13R
result through pure functions, verifies real evidence hashes, and writes only the
contract-authorized target workflow directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.r5_bundle13r_evidence_backflow import (  # noqa: E402
    build_execution_queue,
    evaluate_backflow_execution,
    load_yaml,
    validate_bundle12r_context,
    validate_reviewed_backfill,
)


SOURCE_WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
TARGET_WORKFLOW_ID = "wf_20260723_stock_first_002837_v1_replay"
SOURCE_RUN_REL = Path("reports/workflow_runs") / SOURCE_WORKFLOW_ID
TARGET_RUN_REL = Path("reports/workflow_runs") / TARGET_WORKFLOW_ID
AS_OF_DATE = "2026-07-23"

EXACT_REPLAY_COMMAND = (
    r"C:\Projects\03_Investment_System\.conda\investment-system\python.exe -B "
    r"scripts\run_r5_v1_replay_002837.py --repo-root . "
    rf"--source-run reports\workflow_runs\{SOURCE_WORKFLOW_ID} "
    rf"--output-run reports\workflow_runs\{TARGET_WORKFLOW_ID}"
)

SELECTED_EVIDENCE_IDS = (
    "ev_annual_report_002837_20260421_2cbfc5",
    "ev_quarterly_report_002837_20260421_2f00c7",
    "ev_structured_financial_data_002837_20260713_38e6e4",
    "ev_structured_market_data_002837_20260713_f8cc52",
)
STRUCTURED_EVIDENCE_IDS = frozenset(SELECTED_EVIDENCE_IDS[2:])

EXPECTED_SOURCE_HASHES = {
    "config/r5_bundle13r_backflow_execution_contract.yaml": "7c313ce7b8a24e9c5615d3914501651702c403106a545a4479ff6ff03c919ffe",
    f"{SOURCE_RUN_REL.as_posix()}/bundle12r/R5_bundle12r_generation_lock.yaml": "ebf32dad2205641a36787456f5459a675757c2c48865e705868161a0786e985c",
    f"{SOURCE_RUN_REL.as_posix()}/bundle12r/R5_bundle12r_backflow_plan.yaml": "8aacce378fc1b4838d9470770b71a82efb0ba614fe2ab3917059904485c5103f",
    f"{SOURCE_RUN_REL.as_posix()}/bundle12r/R5_bundle12r_operating_evidence_input_snapshot.yaml": "9de6bc0588d0e27fb43d8071379880dfe02cd4b22218a5991cd11d177a3d203f",
    f"{SOURCE_RUN_REL.as_posix()}/bundle12r/R5_bundle12r_operating_evidence_result.yaml": "6bd9ff2064babdb013eb16b58f8b0b0dba2b89c7a9f2d8dd079ef6fbdf739eec",
    f"{SOURCE_RUN_REL.as_posix()}/bundle12r/R5_bundle12r_research_question_plan.yaml": "4260648fa3a9871dcea6031e2cb62af9141a46e4b2fd5709867aa1dd1bec0407",
    f"{SOURCE_RUN_REL.as_posix()}/bundle13r/R5_bundle13r_reviewed_backfill_input.yaml": "704d8fc40ed9f938c1588d0a0a76cfb7f2c80c807abcf20489024d649ceed011",
    f"{SOURCE_RUN_REL.as_posix()}/bundle13r/R5_bundle13r_backflow_execution_result.yaml": "5fdffe16e79f8c85cea938f6fa834c7054b10e58477eba884a5b838c5d5aa059",
    f"{SOURCE_RUN_REL.as_posix()}/bundle13r/R5_bundle13r_close_readout.md": "b62e64cafcd93bf164c4f4ff76adde1f0d107510a0e39807411d082515f92e5c",
    f"{SOURCE_RUN_REL.as_posix()}/bundle13r/R5_bundle13r_verification_summary.yaml": "4cfe4b07c12da3f108f164ca504018a825f33a4331cbbb2ebfa93cb29348b1c0",
    f"{SOURCE_RUN_REL.as_posix()}/bundle13r/R5_bundle13r_quality_report.md": "6b3c41dc521c916faf599439e94a261613fc6782b9de69698755a913ca169831",
    f"{SOURCE_RUN_REL.as_posix()}/bundle13r/R5_bundle13r_quality_issues.csv": "fa6f98f2a3ecc6363d6a7d7e458cae2892118b5081af8374cdd0174ebe795f57",
    f"{SOURCE_RUN_REL.as_posix()}/live_acquisition_run_log.yaml": "6395b1e65eec5961811a2fda322c29555e3d0e50786f7991d5632284d13fcd1c",
    f"{SOURCE_RUN_REL.as_posix()}/R5_bundle8r_evidence_manifest_delta.csv": "a41ba3eecdea561ee3ed58df173628058a832b695f88bacbb996d258d0521d78",
    "data/manifests/evidence_manifest.csv": "34568fb9f31dc84c16e4b086b751a81ef8770591086c59a901ea7107510175ae",
    "data/manifests/claims_registry.csv": "2c514ffb22320b9cb3e341088d384506d30d7612809850a9c1fad8b73dff0337",
    "data/manifests/metrics_draft.csv": "0b10415e98b29c350379881c4bc742fa27de8ea1bb197206e1a66c571af20ffe",
    "reports/segments/ai_server_liquid_cooling/segment_definition.yaml": "98ed8a66c57572be011dc7970b23bdd8a96593ab06308e2408a227e159bed1aa",
}

EXPECTED_BUNDLE13_RESULT = {
    "decision": "backflow_execution_in_progress",
    "queue_item_count": 21,
    "resolved_t1_t2_item_count": 6,
    "unresolved_t1_t2_item_count": 11,
    "validation_issue_count": 0,
    "blocker_count": 0,
}

EXPECTED_OPEN_ISSUES = (
    "R5B13R-G3-001",
    "R5B13R-G3-002",
    "R5B13R-G6-001",
    "R5B13R-G6-002",
)

PROVENANCE_FIELDS = [
    "input_id",
    "input_kind",
    "evidence_id",
    "source_type",
    "source_name",
    "source_group",
    "review_status",
    "source_path",
    "expected_sha256",
    "observed_sha256",
    "processed_path",
    "processed_sha256",
    "source_workflow_id",
    "usage_boundary",
]

CLAIM_FIELDS = [
    "claim_id",
    "evidence_id",
    "entity_type",
    "entity_id",
    "claim_text",
    "claim_type",
    "quote_or_excerpt",
    "page_no_or_section",
    "confidence",
    "valid_until",
    "status",
    "review_status",
    "notes",
]

TODO_FIELDS = [
    "issue_id",
    "severity",
    "stage",
    "gate_id",
    "target_artifact",
    "description",
    "fix_owner_skill",
    "status",
    "created_at",
    "resolved_at",
    "notes",
]

MANIFEST_FIELDS = [
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

HASH_FIELDS = ["path", "sha256", "bytes", "hash_scope", "source_trace"]

ARTIFACT_SPECS = (
    ("art_001", "workflow_state", "workflow_state.yaml", "research-orchestrator", "T10", True, "current", "canonical V1 state"),
    ("art_002", "run_log", "run_log.md", "research-orchestrator", "T10", True, "current", "exact offline replay command and stage log"),
    ("art_003", "manifest", "artifact_manifest.csv", "research-orchestrator", "T10", True, "current", "current run artifact index"),
    ("art_004", "open_todos", "open_todos.csv", "research-orchestrator", "T10", True, "current", "four source-preserved high research gaps"),
    ("art_005", "quality_gate_report", "quality_gate_report.md", "quality-review", "T9", True, "current", "canonical G0-G10 quality snapshot"),
    ("art_006", "readout", "workflow_readout.md", "research-orchestrator", "T10", True, "current", "canonical replay close readout"),
    ("art_007", "input_provenance", "inputs/input_provenance.csv", "evidence-ingest", "T1", True, "current", "hash-bound read-only inputs"),
    ("art_008", "claim_snapshot", "inputs/claim_snapshot.csv", "evidence-ingest", "T2", False, "current", "no new claim promotion in replay"),
    ("art_009", "metric_candidates", "inputs/metric_candidates.csv", "evidence-ingest", "T2", True, "current", "draft metric-only structured candidates"),
    ("art_010", "stock_research_pack", "research/stock_research_pack.yaml", "stock-deep-dive", "T7", True, "needs_fix", "run-scoped research projection with explicit gaps"),
    ("art_011", "segment_exposure", "research/segment_exposure.yaml", "segment-company-mapping", "T6", True, "needs_fix", "product-line clue only; percentages missing"),
    ("art_012", "report", "research/stock_report_draft.md", "stock-deep-dive", "T7", True, "needs_fix", "gap-visible replay report"),
    ("art_013", "backflow_decision", "research/backflow_decision.yaml", "segment-company-mapping", "T8", True, "current", "isolated backflow routing; no global update"),
    ("art_014", "artifact_hashes", "validation/artifact_hashes.csv", "research-orchestrator", "T10", True, "current", "non-recursive output hash index"),
    ("art_015", "replay_receipt", "validation/replay_receipt.yaml", "research-orchestrator", "T10", True, "current", "offline source and semantic receipt"),
    ("art_016", "idempotence_report", "validation/idempotence_report.yaml", "research-orchestrator", "T10", True, "current", "two-pass byte comparison"),
)

HASH_INDEX_PATHS = (
    "workflow_state.yaml",
    "run_log.md",
    "open_todos.csv",
    "quality_gate_report.md",
    "workflow_readout.md",
    "inputs/input_provenance.csv",
    "inputs/claim_snapshot.csv",
    "inputs/metric_candidates.csv",
    "research/stock_research_pack.yaml",
    "research/segment_exposure.yaml",
    "research/stock_report_draft.md",
    "research/backflow_decision.yaml",
)

REPLAY_COMPARE_PATHS = HASH_INDEX_PATHS + (
    "validation/artifact_hashes.csv",
    "validation/replay_receipt.yaml",
)


class ReplayContractError(RuntimeError):
    """Raised when a replay input or target violates the frozen contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def repo_path(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_bytes_if_changed(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_bytes() == content:
        return
    path.write_bytes(content)


def write_text_if_changed(path: Path, content: str) -> None:
    write_bytes_if_changed(path, content.replace("\r\n", "\n").encode("utf-8"))


def write_yaml_if_changed(path: Path, payload: Any) -> None:
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    write_text_if_changed(path, text)


def write_csv_if_changed(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
    fields: Sequence[str],
) -> None:
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    write_text_if_changed(path, buffer.getvalue())


def resolve_contract_paths(
    repo_root: Path,
    source_run: Path,
    output_run: Path,
) -> tuple[Path, Path, Path]:
    root = repo_root.resolve()
    expected_source = (root / SOURCE_RUN_REL).resolve()
    expected_output = (root / TARGET_RUN_REL).resolve()
    actual_source = source_run.resolve()
    actual_output = output_run.resolve()
    if actual_source != expected_source:
        raise ReplayContractError(
            f"source run must be {SOURCE_RUN_REL.as_posix()}, found {actual_source}"
        )
    if actual_output != expected_output:
        raise ReplayContractError(
            f"output run must be {TARGET_RUN_REL.as_posix()}, found {actual_output}"
        )
    if actual_source == actual_output:
        raise ReplayContractError("source and output runs must be different")
    if not actual_source.is_dir():
        raise ReplayContractError(f"source run is missing: {actual_source}")
    return root, actual_source, actual_output


def verify_expected_sources(repo_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for rel, expected in EXPECTED_SOURCE_HASHES.items():
        path = repo_root / rel
        if not path.is_file():
            raise ReplayContractError(f"required read-only source is missing: {rel}")
        actual = sha256_file(path)
        if actual != expected:
            raise ReplayContractError(
                f"read-only source hash mismatch: {rel}: expected {expected}, found {actual}"
            )
        kind = "workflow_anchor"
        if rel.startswith("data/"):
            kind = "registry_anchor"
        elif rel.startswith("reports/segments/"):
            kind = "segment_context"
        elif rel.startswith("config/"):
            kind = "runtime_contract"
        rows.append(
            {
                "input_id": f"anchor_{len(rows) + 1:03d}",
                "input_kind": kind,
                "evidence_id": "",
                "source_type": "read_only_artifact",
                "source_name": Path(rel).name,
                "source_group": "archived_repository_input",
                "review_status": "hash_verified",
                "source_path": rel,
                "expected_sha256": expected,
                "observed_sha256": actual,
                "processed_path": "",
                "processed_sha256": "",
                "source_workflow_id": SOURCE_WORKFLOW_ID if rel.startswith(SOURCE_RUN_REL.as_posix()) else "",
                "usage_boundary": "read-only provenance or deterministic replay input; no historical state transfer",
            }
        )
    return rows


def select_real_evidence(repo_root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    manifest_path = repo_root / "data/manifests/evidence_manifest.csv"
    _, manifest_rows = read_csv(manifest_path)
    by_id = {row.get("evidence_id", ""): row for row in manifest_rows}
    selected: list[dict[str, str]] = []
    provenance: list[dict[str, str]] = []

    for evidence_id in SELECTED_EVIDENCE_IDS:
        row = by_id.get(evidence_id)
        if row is None:
            raise ReplayContractError(f"selected evidence is missing from manifest: {evidence_id}")
        raw_rel = str(row.get("raw_file_path") or "")
        processed_rel = str(row.get("processed_text_path") or row.get("processed_table_path") or "")
        lowered_paths = f"{raw_rel}\n{processed_rel}".lower()
        if "fixture" in lowered_paths or "tests/fixtures" in lowered_paths:
            raise ReplayContractError(f"synthetic path is not allowed as replay evidence: {evidence_id}")
        raw_path = repo_root / raw_rel
        processed_path = repo_root / processed_rel
        if not raw_path.is_file() or not processed_path.is_file():
            raise ReplayContractError(f"evidence path is missing for {evidence_id}")
        observed_raw = sha256_file(raw_path)
        expected_raw = str(row.get("file_hash") or "")
        if observed_raw != expected_raw:
            raise ReplayContractError(
                f"evidence hash mismatch: {evidence_id}: expected {expected_raw}, found {observed_raw}"
            )
        source_group = str(row.get("source_group") or "")
        review_status = str(row.get("review_status") or "")
        if evidence_id in STRUCTURED_EVIDENCE_IDS:
            if source_group != "structured_database" or review_status != "draft":
                raise ReplayContractError(f"structured evidence boundary changed: {evidence_id}")
            boundary = "draft metric-only input; no metric, exposure, or review promotion"
        else:
            if source_group != "official_disclosure" or review_status != "reviewed":
                raise ReplayContractError(f"official evidence boundary changed: {evidence_id}")
            boundary = "reviewed official source; only locator-backed claims may be material"
        selected.append(dict(row))
        provenance.append(
            {
                "input_id": f"evidence_{len(provenance) + 1:03d}",
                "input_kind": "official_evidence" if source_group == "official_disclosure" else "structured_evidence",
                "evidence_id": evidence_id,
                "source_type": row.get("source_type", ""),
                "source_name": row.get("source_name", ""),
                "source_group": source_group,
                "review_status": review_status,
                "source_path": raw_rel,
                "expected_sha256": expected_raw,
                "observed_sha256": observed_raw,
                "processed_path": processed_rel,
                "processed_sha256": sha256_file(processed_path),
                "source_workflow_id": "",
                "usage_boundary": boundary,
            }
        )

    if sum(row["source_group"] == "official_disclosure" for row in provenance) != 2:
        raise ReplayContractError("replay must bind exactly two official disclosures")
    if sum(row["source_group"] == "structured_database" for row in provenance) != 2:
        raise ReplayContractError("replay must bind exactly two structured snapshots")
    return selected, provenance


def select_claim_rows(repo_root: Path) -> list[dict[str, str]]:
    _, rows = read_csv(repo_root / "data/manifests/claims_registry.csv")
    selected = [
        row
        for row in rows
        if row.get("entity_id") == "cn_002837_invic"
        and row.get("evidence_id") in SELECTED_EVIDENCE_IDS
    ]
    # The four selected replay sources have no promoted global claim rows.  Keep
    # the absence explicit rather than importing claims from another source hash.
    if selected:
        raise ReplayContractError("unexpected promoted claims appeared for the selected replay inputs")
    return []


def select_metric_candidates(repo_root: Path) -> tuple[list[str], list[dict[str, str]]]:
    fields, rows = read_csv(repo_root / "data/manifests/metrics_draft.csv")
    selected = [
        row
        for row in rows
        if row.get("source_evidence_id") in STRUCTURED_EVIDENCE_IDS
        and (row.get("entity_id") == "cn_002837_invic" or row.get("stock_code") == "002837")
    ]
    if not selected:
        raise ReplayContractError("no metric-only candidates found for the real structured inputs")
    for row in selected:
        if row.get("review_status") != "draft" or row.get("promote_to_metric_id"):
            raise ReplayContractError("structured replay candidates must remain draft and unpromoted")
    selected.sort(
        key=lambda row: (
            row.get("source_evidence_id", ""),
            row.get("metric_candidate_id", ""),
        )
    )
    return fields, selected


def recompute_bundle13(
    repo_root: Path,
    source_run: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    contract_path = repo_root / "config/r5_bundle13r_backflow_execution_contract.yaml"
    contract = load_yaml(contract_path)
    context_dir = source_run / "bundle12r"
    artifacts, context_issues = validate_bundle12r_context(
        context_dir,
        contract,
        verify_artifact_hashes=True,
    )
    if context_issues:
        raise ReplayContractError(
            "Bundle12R source validation failed: "
            + "; ".join(issue.message for issue in context_issues)
        )
    queue = build_execution_queue(
        artifacts["backflow"],
        artifacts["questions"],
        artifacts["input"],
        contract,
    )
    reviewed = load_yaml(source_run / "bundle13r/R5_bundle13r_reviewed_backfill_input.yaml")
    validation_issues = validate_reviewed_backfill(reviewed, queue, contract)
    result = evaluate_backflow_execution(
        queue=queue,
        reviewed_backfill=reviewed,
        validation_issues=validation_issues,
    )
    archived = load_yaml(source_run / "bundle13r/R5_bundle13r_backflow_execution_result.yaml")
    if result != archived:
        raise ReplayContractError("pure Bundle13R recomputation does not match the archived result")
    observed = {
        "decision": result.get("decision"),
        "queue_item_count": len(queue.get("items") or []),
        "resolved_t1_t2_item_count": result.get("resolved_t1_t2_item_count"),
        "unresolved_t1_t2_item_count": result.get("unresolved_t1_t2_item_count"),
        "validation_issue_count": result.get("validation_issue_count"),
        "blocker_count": result.get("blocker_count"),
    }
    if observed != EXPECTED_BUNDLE13_RESULT:
        raise ReplayContractError(f"Bundle13R replay result changed: {observed}")
    return queue, result


def build_open_todos(source_run: Path) -> list[dict[str, str]]:
    _, source_rows = read_csv(source_run / "bundle13r/R5_bundle13r_quality_issues.csv")
    by_id = {row.get("issue_id", ""): row for row in source_rows}
    if tuple(sorted(by_id)) != tuple(sorted(EXPECTED_OPEN_ISSUES)):
        raise ReplayContractError("Bundle13R high issue set changed")
    rows: list[dict[str, str]] = []
    for issue_id in EXPECTED_OPEN_ISSUES:
        source = by_id[issue_id]
        gate_id = source.get("gate_id", "")
        if source.get("severity") != "high" or source.get("status") != "open":
            raise ReplayContractError(f"source issue boundary changed: {issue_id}")
        target = (
            f"{TARGET_RUN_REL.as_posix()}/research/stock_research_pack.yaml"
            if gate_id == "G3"
            else f"{TARGET_RUN_REL.as_posix()}/research/segment_exposure.yaml"
        )
        rows.append(
            {
                "issue_id": issue_id,
                "severity": "high",
                "stage": "T9",
                "gate_id": gate_id,
                "target_artifact": target,
                "description": source.get("description", ""),
                "fix_owner_skill": source.get("fix_owner_skill", ""),
                "status": "open",
                "created_at": source.get("created_at", "") or "2026-07-15",
                "resolved_at": "",
                "notes": f"source_local_check={source.get('local_check_id', '')}; next_step={source.get('notes', '')}",
            }
        )
    return rows


def build_quality_gates() -> list[dict[str, Any]]:
    descriptions = {
        "G0": ("pass", "stock, scope, source run, target run and offline boundary are explicit"),
        "G1": ("pass", "two official and two structured sources exist and match frozen hashes"),
        "G2": ("pass", "no new claim is promoted; claim-type boundary remains explicit"),
        "G3": ("fail", "nine operating drivers remain unqualified; structured candidates remain draft"),
        "G4": ("pass", "existing ai_server_liquid_cooling segment definition is hash-bound"),
        "G5": ("not_applicable", "stock-first replay does not rebuild the company universe"),
        "G6": ("fail", "two liquid-cooling overlap adjustments remain missing"),
        "G7": ("pass", "the run-scoped report exposes gaps and source boundaries without unsupported conclusions"),
        "G8": ("pass", "all high gaps have owner, target and next step; no global state is changed"),
        "G9": ("pass", "no trading instruction, position sizing or certainty claim is present"),
        "G10": ("pass", "canonical state, TODOs, manifest, quality report and readout are materialized"),
    }
    return [
        {
            "gate_id": gate_id,
            "status": descriptions[gate_id][0],
            "checked_by": "quality-review",
            "checked_at": AS_OF_DATE,
            "notes": descriptions[gate_id][1],
        }
        for gate_id in (f"G{index}" for index in range(11))
    ]


def artifact_state_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, artifact_type, rel, skill, stage, required, status, notes in ARTIFACT_SPECS:
        rows.append(
            {
                "artifact_type": artifact_type,
                "path": f"{TARGET_RUN_REL.as_posix()}/{rel}",
                "created_by_skill": skill,
                "stage": stage,
                "status": status,
                "required": required,
                "notes": notes,
            }
        )
    return rows


def build_state(
    evidence_count: int,
    metric_candidate_count: int,
    todos: Sequence[Mapping[str, Any]],
    gates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "state_schema_version": "r5_v1",
        "workflow_id": TARGET_WORKFLOW_ID,
        "source_workflow_id": SOURCE_WORKFLOW_ID,
        "workflow_type": "stock_first_closed_loop",
        "run_mode": "normal",
        "status": "needs_fix",
        "created_at": AS_OF_DATE,
        "updated_at": AS_OF_DATE,
        "owner": "codex",
        "active_segment_id": "ai_server_liquid_cooling",
        "active_company_id": "cn_002837_invic",
        "current_stage": "T10",
        "completed_stages": [f"T{index}" for index in range(11)],
        "next_stage": "T1",
        "active_skill": "research-orchestrator",
        "required_next_skill": "evidence-ingest",
        "system_v1_complete": False,
        "sample_quality_ready": False,
        "p2_ready": False,
        "release_ready": False,
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "human_review_status": "not_triggered_no_new_reader",
        "evidence_snapshot": {
            "manifest_path": f"{TARGET_RUN_REL.as_posix()}/inputs/input_provenance.csv",
            "evidence_count": evidence_count,
            "notes": "offline hash-verified selection; historical sources remain read-only",
        },
        "claims_snapshot": {
            "draft_path": f"{TARGET_RUN_REL.as_posix()}/inputs/claim_snapshot.csv",
            "registry_path": "data/manifests/claims_registry.csv",
            "claim_count": 0,
            "notes": "no new claim promotion; no source hash substitution",
        },
        "metrics_snapshot": {
            "draft_path": f"{TARGET_RUN_REL.as_posix()}/inputs/metric_candidates.csv",
            "registry_path": None,
            "metric_count": 0,
            "candidate_count": metric_candidate_count,
            "notes": "real structured candidates remain draft and metric-only",
        },
        "artifacts": artifact_state_rows(),
        "open_todos": [dict(row) for row in todos],
        "quality_gates": [dict(row) for row in gates],
        "entry_criteria": [
            "P3 checkpoint passed",
            "source and target runs differ",
            "all frozen source hashes match",
            "no live network access",
        ],
        "exit_criteria": [
            "standard six-piece control plane exists",
            "canonical state validates",
            "two materialization passes have zero byte drift",
            "old workflow remains read-only",
        ],
        "notes": "Engineering replay closed honestly at needs_fix because G3 and G6 retain four open high research gaps.",
    }


def build_research_pack(
    queue: Mapping[str, Any],
    result: Mapping[str, Any],
    evidence_rows: Sequence[Mapping[str, str]],
    metric_candidate_count: int,
    todos: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "artifact_type": "r5_v1_replay_stock_research_pack",
        "workflow_id": TARGET_WORKFLOW_ID,
        "source_workflow_id": SOURCE_WORKFLOW_ID,
        "as_of_date": AS_OF_DATE,
        "company_identity": {
            "company_id": "cn_002837_invic",
            "stock_code": "002837",
            "company_name": "英维克",
        },
        "replay_mode": {
            "offline": True,
            "live_network_used": False,
            "synthetic_inputs_used": False,
            "historical_writes_allowed": False,
        },
        "source_evidence": [
            {
                "evidence_id": row.get("evidence_id"),
                "source_type": row.get("source_type"),
                "source_name": row.get("source_name"),
                "source_group": row.get("source_group"),
                "review_status": row.get("review_status"),
                "raw_file_path": row.get("raw_file_path"),
                "processed_path": row.get("processed_text_path") or row.get("processed_table_path"),
            }
            for row in evidence_rows
        ],
        "bundle13r_replay": {
            "source_generation_id": result.get("source_bundle12r_generation_id"),
            "archived_result_match": True,
            "decision": result.get("decision"),
            "queue_item_count": len(queue.get("items") or []),
            "resolved_t1_t2_item_count": result.get("resolved_t1_t2_item_count"),
            "unresolved_t1_t2_item_count": result.get("unresolved_t1_t2_item_count"),
            "unresolved_t1_t2_items": list(result.get("unresolved_t1_t2_items") or []),
            "validation_issue_count": result.get("validation_issue_count"),
            "validation_blocker_count": result.get("blocker_count"),
        },
        "claim_boundary": {
            "promoted_claim_count": 0,
            "reason": "selected source hashes have no matching promoted global claims; none were invented or borrowed",
        },
        "metric_boundary": {
            "candidate_count": metric_candidate_count,
            "promoted_metric_count": 0,
            "review_status": "draft",
            "allowed_use": "metric_only_after_review",
            "business_exposure_use_allowed": False,
        },
        "business_and_financial_skeleton": {
            "linked_segment_id": "ai_server_liquid_cooling",
            "exposure_type": "product_line_clue",
            "revenue_pct": "MISSING_DISCLOSURE",
            "profit_pct": "MISSING_DISCLOSURE",
            "liquid_cooling_revenue": "MISSING_DISCLOSURE",
            "liquid_cooling_gross_margin": "MISSING_DISCLOSURE",
            "operating_driver_status": "needs_fix",
            "overlap_reconciliation_status": "needs_fix",
        },
        "stage_results": [
            {"stage": "T0", "status": "pass", "owner": "research-orchestrator"},
            {"stage": "T1", "status": "pass_with_gaps", "owner": "evidence-ingest"},
            {"stage": "T2", "status": "needs_fix", "owner": "stock-deep-dive"},
            {"stage": "T3", "status": "pass", "owner": "stock-deep-dive"},
            {"stage": "T4", "status": "pass", "owner": "research-orchestrator"},
            {"stage": "T5", "status": "not_applicable_existing_segment", "owner": "segment-research"},
            {"stage": "T6", "status": "needs_fix", "owner": "segment-company-mapping"},
            {"stage": "T7", "status": "pass_with_visible_gaps", "owner": "stock-deep-dive"},
            {"stage": "T8", "status": "pass", "owner": "segment-company-mapping"},
            {"stage": "T9", "status": "needs_fix", "owner": "quality-review"},
            {"stage": "T10", "status": "pass", "owner": "research-orchestrator"},
        ],
        "open_issue_ids": [str(row.get("issue_id")) for row in todos],
        "research_outcome": {
            "status": "needs_fix",
            "summary": "归档输入与自动重算可复现；液冷经营驱动和重叠扣减仍缺正式证据。",
            "required_next_skill": "evidence-ingest",
            "next_stage": "T1",
        },
        "fixed_boundaries": {
            "human_review_transferred": False,
            "new_reader_generated": False,
            "sample_quality_ready": False,
            "p2_ready": False,
            "release_ready": False,
        },
    }


def build_segment_exposure() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "workflow_id": TARGET_WORKFLOW_ID,
        "source_workflow_id": SOURCE_WORKFLOW_ID,
        "company_id": "cn_002837_invic",
        "stock_code": "002837",
        "company_name": "英维克",
        "as_of_date": AS_OF_DATE,
        "exposures": [
            {
                "segment_id": "ai_server_liquid_cooling",
                "segment_name": "AI服务器液冷",
                "exposure_type": "product_line_clue",
                "exposure_score": 2,
                "confidence": "low",
                "revenue_pct": "MISSING_DISCLOSURE",
                "profit_pct": "MISSING_DISCLOSURE",
                "evidence_ids": list(SELECTED_EVIDENCE_IDS[:2]),
                "claim_ids": [],
                "metric_ids": [],
                "missing_reason": "MISSING_DISCLOSURE",
                "backflow_decision": "blocked",
                "next_action": "evidence-ingest must obtain same-period operating disclosure before exposure allocation",
            }
        ],
        "global_exposure_updated": False,
        "sample_quality_ready": False,
        "p2_ready": False,
    }


def build_backflow_decision(todos: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "artifact_type": "r5_v1_replay_backflow_decision",
        "workflow_id": TARGET_WORKFLOW_ID,
        "source_workflow_id": SOURCE_WORKFLOW_ID,
        "as_of_date": AS_OF_DATE,
        "backflow_decision": "blocked",
        "global_state_updated": False,
        "reason": "same-period operating drivers and numeric overlap adjustments remain missing",
        "issues": [
            {
                "issue_id": row.get("issue_id"),
                "gate_id": row.get("gate_id"),
                "owner": row.get("fix_owner_skill"),
                "next_step": row.get("notes"),
            }
            for row in todos
        ],
        "required_next_skill": "evidence-ingest",
        "next_stage": "T1",
        "sample_quality_ready": False,
        "p2_ready": False,
    }


def render_stock_report(result: Mapping[str, Any], metric_candidate_count: int) -> str:
    unresolved = int(result.get("unresolved_t1_t2_item_count") or 0)
    return f"""# 002837 V1 隔离重放研究稿

## 重放结论

本 run 在离线、只读来源边界内完成 T0–T10 自动链。Bundle13R 纯计算结果与归档结果一致：6 项已解决、{unresolved} 项未解决、输入校验阻断 0。研究质量状态为 `needs_fix`，不是样本质量或 P2 准入结论。

## 证据事实

- 年报全文：`ev_annual_report_002837_20260421_2cbfc5`，原件 `data/raw/annual_reports/cninfo_2025_annual_report_full_002837_2026-04-21.pdf`。
- 2026 年一季报：`ev_quarterly_report_002837_20260421_2f00c7`，原件 `data/raw/announcements/szse_2026_q1_report_002837_2026-04-21.pdf`。
- 两份 Tushare 结构化快照已归档并生成 {metric_candidate_count} 条候选；它们仍是 `draft`、`metric_only`，本 run 未提升为正式 metric，也未用于证明液冷业务暴露。

## 研究边界

`ai_server_liquid_cooling` 只保留为产品线索。液冷独立收入、毛利、项目量、单位价值、验收率，以及与机房/机柜宽口径的收入和毛利扣减均为 `MISSING_DISCLOSURE`。因此不形成同业估值或可执行交易结论。

## 风险、反证与下一步

若后续正式披露仍不能提供同期间量价与重叠分配，当前产品线索不能升级为收入或利润暴露。下一步由 `evidence-ingest` 在 T1 获取并审阅可定位的发行人正式经营披露，再由 `stock-deep-dive` 重做重叠分配。

本文是工程重放产物，不构成投资建议。
"""


def render_quality_report(
    gates: Sequence[Mapping[str, Any]],
    todos: Sequence[Mapping[str, Any]],
) -> str:
    lines = [
        "# 002837 V1 replay quality gate report",
        "",
        "## 结论",
        "",
        "离线闭环可复现，canonical 研究状态为 `needs_fix`。G3 与 G6 非补偿失败；其余门禁不能抵消这四项 high 研究缺口。",
        "",
        "## G0-G10",
        "",
        "| gate | status | evidence / limitation |",
        "|---|---|---|",
    ]
    for gate in gates:
        lines.append(f"| {gate['gate_id']} | {gate['status']} | {gate['notes']} |")
    lines.extend(["", "## Open high issues", ""])
    for row in todos:
        lines.append(
            f"- `{row['issue_id']}` / {row['gate_id']} / owner `{row['fix_owner_skill']}`: {row['description']} Next: {row['notes']}"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "No historical human decision is transferred. `sample_quality_ready=false`, `p2_ready=false`, `release_ready=false`. No direct trading instruction is produced.",
            "",
        ]
    )
    return "\n".join(lines)


def render_run_log(result: Mapping[str, Any]) -> str:
    return f"""# 002837 V1 replay run log

## Exact command

```powershell
{EXACT_REPLAY_COMMAND}
```

## T0-T10 execution

- T0: fixed 002837 scope, old source run and new target run verified.
- T1: two official and two structured archived inputs verified by path and SHA-256; no network used.
- T2: Bundle12R/13R context validated; structured candidates retained as draft and unpromoted.
- T3-T6: linked segment and run-scoped exposure projected; missing allocation remains visible.
- T7: gap-visible report produced without a new Reader or inherited human decision.
- T8: four high issues routed without updating global segment state.
- T9: G0-G10 evaluated; G3/G6 failed non-compensating checks.
- T10: singleton state, TODOs, quality report and readout materialized.

## Recomputed result

- decision: `{result.get('decision')}`
- resolved T1/T2 items: `{result.get('resolved_t1_t2_item_count')}`
- unresolved T1/T2 items: `{result.get('unresolved_t1_t2_item_count')}`
- validation issues: `{result.get('validation_issue_count')}`
- validation blockers: `{result.get('blocker_count')}`

The command performs two internal materialization passes and fails if any compared output byte changes.
"""


def render_readout(result: Mapping[str, Any], evidence_count: int, metric_count: int) -> str:
    return f"""# 002837 V1 replay close readout

## Outcome

The isolated offline stock-first chain completed its automatable T0-T10 scope and closed honestly at `needs_fix`. The pure Bundle13R recomputation exactly matched the archived result: queue 21, resolved 6, unresolved 11, validation blockers 0.

## Input and research boundary

- Real archived evidence objects: {evidence_count}; every raw hash matches `data/manifests/evidence_manifest.csv`.
- Structured metric candidates: {metric_count}; all remain draft and unpromoted.
- Historical source workflow: `{SOURCE_WORKFLOW_ID}` (read-only lineage only).
- Current workflow: `{TARGET_WORKFLOW_ID}`.
- No live network, raw copy, historical mutation, new Reader, or inherited human decision.

## Quality and next step

G3 and G6 fail because four high research gaps remain. The next route is `evidence-ingest` at T1; the required trigger is same-period, locator-backed official operating evidence. The exposure mapping remains blocked from global update.

## Four independent facts

- `system_v1_complete=false` during P4.
- `sample_quality_ready=false`.
- `p2_ready=false`.
- `release_ready=false`.

## Repeatability

Exact command:

```powershell
{EXACT_REPLAY_COMMAND}
```

The command performs two materializations and records zero byte drift in `validation/idempotence_report.yaml`.
"""


def build_semantic_payload(
    result: Mapping[str, Any],
    provenance: Sequence[Mapping[str, Any]],
    research_pack: Mapping[str, Any],
    exposure: Mapping[str, Any],
    backflow: Mapping[str, Any],
    state: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "workflow_id": TARGET_WORKFLOW_ID,
        "source_workflow_id": SOURCE_WORKFLOW_ID,
        "source_hashes": [
            {
                "path": row.get("source_path"),
                "sha256": row.get("observed_sha256"),
                "processed_path": row.get("processed_path"),
                "processed_sha256": row.get("processed_sha256"),
            }
            for row in provenance
        ],
        "recomputed_result": {
            key: result.get(key)
            for key in (
                "decision",
                "resolved_t1_t2_item_count",
                "unresolved_t1_t2_item_count",
                "unresolved_t1_t2_items",
                "validation_issue_count",
                "blocker_count",
            )
        },
        "research_pack": research_pack,
        "segment_exposure": exposure,
        "backflow_decision": backflow,
        "canonical_state": state,
    }


def build_hash_index(output_run: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rel in HASH_INDEX_PATHS:
        path = output_run / rel
        if not path.is_file():
            raise ReplayContractError(f"expected replay artifact is missing: {rel}")
        rows.append(
            {
                "path": f"{TARGET_RUN_REL.as_posix()}/{rel}",
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "hash_scope": "file_bytes",
                "source_trace": "inputs/input_provenance.csv or workflow-local derivation",
            }
        )
    return rows


def capture_compare_hashes(output_run: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for rel in REPLAY_COMPARE_PATHS:
        path = output_run / rel
        if not path.is_file():
            raise ReplayContractError(f"comparison artifact is missing: {rel}")
        hashes[rel] = sha256_file(path)
    return hashes


def materialize_once(repo_root: Path, source_run: Path, output_run: Path) -> dict[str, Any]:
    anchor_rows = verify_expected_sources(repo_root)
    evidence_rows, evidence_provenance = select_real_evidence(repo_root)
    provenance = anchor_rows + evidence_provenance
    claim_rows = select_claim_rows(repo_root)
    metric_fields, metric_rows = select_metric_candidates(repo_root)
    queue, result = recompute_bundle13(repo_root, source_run)
    todos = build_open_todos(source_run)
    gates = build_quality_gates()

    input_dir = output_run / "inputs"
    research_dir = output_run / "research"
    validation_dir = output_run / "validation"
    input_dir.mkdir(parents=True, exist_ok=True)
    research_dir.mkdir(parents=True, exist_ok=True)
    validation_dir.mkdir(parents=True, exist_ok=True)

    write_csv_if_changed(input_dir / "input_provenance.csv", provenance, PROVENANCE_FIELDS)
    write_csv_if_changed(input_dir / "claim_snapshot.csv", claim_rows, CLAIM_FIELDS)
    write_csv_if_changed(input_dir / "metric_candidates.csv", metric_rows, metric_fields)

    research_pack = build_research_pack(
        queue,
        result,
        evidence_rows,
        len(metric_rows),
        todos,
    )
    exposure = build_segment_exposure()
    backflow = build_backflow_decision(todos)
    state = build_state(len(evidence_rows), len(metric_rows), todos, gates)

    write_yaml_if_changed(research_dir / "stock_research_pack.yaml", research_pack)
    write_yaml_if_changed(research_dir / "segment_exposure.yaml", exposure)
    write_yaml_if_changed(research_dir / "backflow_decision.yaml", backflow)
    write_text_if_changed(research_dir / "stock_report_draft.md", render_stock_report(result, len(metric_rows)))
    write_csv_if_changed(output_run / "open_todos.csv", todos, TODO_FIELDS)
    write_yaml_if_changed(output_run / "workflow_state.yaml", state)
    write_text_if_changed(output_run / "run_log.md", render_run_log(result))
    write_text_if_changed(output_run / "quality_gate_report.md", render_quality_report(gates, todos))
    write_text_if_changed(output_run / "workflow_readout.md", render_readout(result, len(evidence_rows), len(metric_rows)))

    hash_rows = build_hash_index(output_run)
    write_csv_if_changed(validation_dir / "artifact_hashes.csv", hash_rows, HASH_FIELDS)
    semantic_payload = build_semantic_payload(
        result,
        provenance,
        research_pack,
        exposure,
        backflow,
        state,
    )
    receipt = {
        "schema_version": 1,
        "artifact_type": "r5_v1_replay_receipt",
        "workflow_id": TARGET_WORKFLOW_ID,
        "source_workflow_id": SOURCE_WORKFLOW_ID,
        "as_of_date": AS_OF_DATE,
        "exact_replay_command": EXACT_REPLAY_COMMAND,
        "offline": True,
        "live_network_used": False,
        "synthetic_inputs_used": False,
        "source_input_count": len(provenance),
        "selected_evidence_ids": list(SELECTED_EVIDENCE_IDS),
        "source_hash_set_sha256": canonical_sha256(
            [(row["source_path"], row["observed_sha256"]) for row in provenance]
        ),
        "output_hash_index_sha256": sha256_file(validation_dir / "artifact_hashes.csv"),
        "semantic_content_sha256": canonical_sha256(semantic_payload),
        "recomputed_result": dict(EXPECTED_BUNDLE13_RESULT),
        "terminal_research_status": "needs_fix",
        "human_review_transferred": False,
        "sample_quality_ready": False,
        "p2_ready": False,
        "release_ready": False,
    }
    write_yaml_if_changed(validation_dir / "replay_receipt.yaml", receipt)
    return {
        "result": result,
        "evidence_count": len(evidence_rows),
        "metric_candidate_count": len(metric_rows),
        "semantic_content_sha256": receipt["semantic_content_sha256"],
    }


def write_idempotence_report(
    output_run: Path,
    first: Mapping[str, Any],
    second: Mapping[str, Any],
    first_hashes: Mapping[str, str],
    second_hashes: Mapping[str, str],
) -> dict[str, Any]:
    drift = [path for path in sorted(first_hashes) if first_hashes[path] != second_hashes.get(path)]
    report = {
        "schema_version": 1,
        "artifact_type": "r5_v1_replay_idempotence_report",
        "workflow_id": TARGET_WORKFLOW_ID,
        "source_workflow_id": SOURCE_WORKFLOW_ID,
        "as_of_date": AS_OF_DATE,
        "comparison_mode": "two consecutive materializations to the same explicit run-scoped target",
        "allowed_normalizations": [],
        "first_semantic_content_sha256": first["semantic_content_sha256"],
        "second_semantic_content_sha256": second["semantic_content_sha256"],
        "compared_artifact_count": len(first_hashes),
        "semantic_drift_count": len(drift),
        "drift_paths": drift,
        "compared_artifacts": [
            {
                "path": f"{TARGET_RUN_REL.as_posix()}/{path}",
                "first_sha256": first_hashes[path],
                "second_sha256": second_hashes[path],
            }
            for path in sorted(first_hashes)
        ],
        "decision": "pass" if not drift else "fail",
    }
    write_yaml_if_changed(output_run / "validation/idempotence_report.yaml", report)
    if drift:
        raise ReplayContractError("replay materialization is not byte-idempotent: " + ", ".join(drift))
    return report


def write_artifact_manifest(output_run: Path, compare_hashes: Mapping[str, str]) -> None:
    idempotence_path = output_run / "validation/idempotence_report.yaml"
    idempotence_hash = sha256_file(idempotence_path)
    rows: list[dict[str, Any]] = []
    for artifact_id, artifact_type, rel, skill, stage, required, status, notes in ARTIFACT_SPECS:
        path = output_run / rel
        if rel == "artifact_manifest.csv":
            trace = "self-manifest; recursive self-hash intentionally omitted"
        elif rel == "validation/idempotence_report.yaml":
            trace = f"sha256={idempotence_hash}"
        else:
            trace = f"sha256={compare_hashes.get(rel, '')}"
        rows.append(
            {
                "artifact_id": artifact_id,
                "artifact_type": artifact_type,
                "path": f"{TARGET_RUN_REL.as_posix()}/{rel}",
                "created_by_skill": skill,
                "stage": stage,
                "required": str(required).lower(),
                "exists": "true",
                "status": status,
                "notes": f"{notes}; {trace}",
            }
        )
        if rel != "artifact_manifest.csv" and not path.is_file():
            raise ReplayContractError(f"manifest target is missing: {rel}")
    write_csv_if_changed(output_run / "artifact_manifest.csv", rows, MANIFEST_FIELDS)


def materialize_replay(
    repo_root: Path,
    source_run: Path,
    output_run: Path,
) -> dict[str, Any]:
    """Materialize a replay into an already-authorized directory.

    Tests use this pure target parameter with a temporary directory.  The CLI
    always enters through :func:`execute_replay`, which enforces the one frozen
    repository target before calling this helper.
    """
    output_run.mkdir(parents=True, exist_ok=True)
    first = materialize_once(repo_root, source_run, output_run)
    first_hashes = capture_compare_hashes(output_run)
    second = materialize_once(repo_root, source_run, output_run)
    second_hashes = capture_compare_hashes(output_run)
    idempotence = write_idempotence_report(
        output_run,
        first,
        second,
        first_hashes,
        second_hashes,
    )
    write_artifact_manifest(output_run, second_hashes)
    return {
        "workflow_id": TARGET_WORKFLOW_ID,
        "source_workflow_id": SOURCE_WORKFLOW_ID,
        "decision": "needs_fix",
        "recomputed_result": second["result"]["decision"],
        "evidence_count": second["evidence_count"],
        "metric_candidate_count": second["metric_candidate_count"],
        "semantic_content_sha256": second["semantic_content_sha256"],
        "semantic_drift_count": idempotence["semantic_drift_count"],
    }


def execute_replay(
    repo_root: Path,
    source_run: Path,
    output_run: Path,
) -> dict[str, Any]:
    root, source, output = resolve_contract_paths(repo_root, source_run, output_run)
    return materialize_replay(root, source, output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the isolated offline 002837 V1 replay")
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--source-run", required=True, type=Path)
    parser.add_argument("--output-run", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = execute_replay(
            args.repo_root,
            args.source_run,
            args.output_run,
        )
    except ReplayContractError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
