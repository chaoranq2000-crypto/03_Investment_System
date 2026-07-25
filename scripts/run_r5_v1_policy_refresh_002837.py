#!/usr/bin/env python3
"""Materialize the offline 002837 V1 policy-refresh workflow.

The runner is intentionally independent from historical workflow directories.
It reads one evidence manifest and four fixed official-source files, verifies
their identities and page locators, then writes a deterministic run tree under
the caller-selected output directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml


WORKFLOW_ID = "wf_20260725_stock_first_002837_v1_policy_refresh"
TARGET_RUN_REL = Path("reports/workflow_runs") / WORKFLOW_ID
AS_OF_DATE = "2026-07-25"
MANIFEST_REL = Path("data/manifests/evidence_manifest.csv")

EXACT_REPLAY_COMMAND = (
    r"C:\Projects\03_Investment_System\.conda\investment-system\python.exe -B "
    r"scripts\run_r5_v1_policy_refresh_002837.py --repo-root . "
    rf"--output-dir {TARGET_RUN_REL.as_posix()}"
)

ANNUAL_EVIDENCE_ID = "ev_annual_report_002837_20260421_2cbfc5"
INTERIM_EVIDENCE_ID = "ev_interim_report_002837_20250819_47054e"

SOURCE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "role": "annual_report_2025",
        "evidence_id": ANNUAL_EVIDENCE_ID,
        "source_type": "annual_report",
        "source_name": "cninfo",
        "source_group": "official_disclosure",
        "publisher": "深圳证券交易所",
        "publish_date": "2026-04-21",
        "title": "深圳市英维克科技股份有限公司2025年年度报告全文",
        "raw_path": (
            "data/raw/annual_reports/"
            "cninfo_2025_annual_report_full_002837_2026-04-21.pdf"
        ),
        "raw_sha256": (
            "2cbfc5dc8a60b01212b68d930fb06d0a25bd74563cd1942bd87161246c3a1472"
        ),
        "processed_path": (
            "data/processed/text/002837/"
            "cninfo_2025_annual_report_full_002837_2026-04-21.txt"
        ),
        "processed_file_sha256": (
            "0218a5ce464eb23d869ff0fb97b4e7233d0d2f02758eb2e9016d70b525f0f0bb"
        ),
        "processed_canonical_lf_sha256": (
            "503b62a47363ca5c985a22980e4eb36fe883821db92d1d9febe0fffb74224876"
        ),
        "page_count": 196,
        "locators": (
            (15, "机房温控节能产品 3,448,477,492.62 56.83%"),
            (15, "机柜温控节能产品 1,977,423,139.19 32.59%"),
            (
                16,
                "机房温控节能产品 3,448,477,492.62 "
                "2,470,650,226.09 28.36%",
            ),
            (
                16,
                "机柜温控节能产品 1,977,423,139.19 "
                "1,438,783,613.25 27.24%",
            ),
            (16, "销售量 台 324,058 257,932 25.64%"),
        ),
    },
    {
        "role": "interim_report_2025",
        "evidence_id": INTERIM_EVIDENCE_ID,
        "source_type": "interim_report",
        "source_name": "cninfo",
        "source_group": "official_disclosure",
        "publisher": "深圳证券交易所",
        "publish_date": "2025-08-19",
        "title": "深圳市英维克科技股份有限公司2025年半年度报告全文",
        "raw_path": (
            "data/raw/announcements/"
            "cninfo_2025_interim_report_full_002837_2025-08-19.pdf"
        ),
        "raw_sha256": (
            "47054e736c74130385e4cab67f04708599c4bae0df5599b4446614039b3f0ffb"
        ),
        "processed_path": (
            "data/processed/text/002837/"
            "cninfo_2025_interim_report_full_002837_2025-08-19.txt"
        ),
        "processed_file_sha256": (
            "1c26dcc25fe19fa761c72bd709a8dd5d7c703b4f3aca2a0e09241f413cf8c58f"
        ),
        "processed_canonical_lf_sha256": (
            "30c20a4350f114143b4bd7634ce39489a6dba2ed0fd937bb830b52288c858653"
        ),
        "page_count": 162,
        "locators": (
            (9, "液冷相关营业收入超过 2 亿元"),
            (9, "相关营业收入部分计入“机房温控"),
            (9, "节能产品”，部分计入“其他”"),
        ),
    },
)

PROVENANCE_FIELDS = (
    "input_id",
    "input_kind",
    "evidence_id",
    "source_type",
    "source_name",
    "source_group",
    "publisher",
    "publish_date",
    "review_status",
    "source_path",
    "hash_scope",
    "expected_sha256",
    "observed_sha256",
    "file_sha256",
    "paired_input_path",
    "page_count",
    "usage_boundary",
)

TODO_FIELDS = (
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
    "impact_scope",
    "active_disposition",
    "affected_capabilities",
    "blocks_current_goal",
)

ISSUE_CHANGE_FIELDS = (
    "prior_issue_id",
    "current_issue_id",
    "severity",
    "change_type",
    "historical_resolved",
    "prior_assertion",
    "current_disposition",
    "impact_scope",
    "affected_capabilities",
    "blocks_current_goal",
    "numeric_use",
    "evidence_id",
    "page_no",
    "rationale",
)

MANIFEST_FIELDS = (
    "artifact_id",
    "artifact_type",
    "path",
    "created_by_skill",
    "stage",
    "required",
    "exists",
    "status",
    "notes",
)

HASH_FIELDS = ("path", "sha256", "bytes", "hash_scope", "source_trace")

ARTIFACT_SPECS: tuple[tuple[Any, ...], ...] = (
    (
        "art_001",
        "workflow_state",
        "workflow_state.yaml",
        "research-orchestrator",
        "T10",
        True,
        "current",
        "canonical current-goal V1 state",
    ),
    (
        "art_002",
        "run_log",
        "run_log.md",
        "research-orchestrator",
        "T10",
        True,
        "current",
        "exact offline refresh command and stage log",
    ),
    (
        "art_003",
        "manifest",
        "artifact_manifest.csv",
        "research-orchestrator",
        "T10",
        True,
        "current",
        "current run artifact index",
    ),
    (
        "art_004",
        "open_todos",
        "open_todos.csv",
        "research-orchestrator",
        "T10",
        True,
        "current",
        "four visible nonblocking research limitations",
    ),
    (
        "art_005",
        "quality_gate_report",
        "quality_gate_report.md",
        "quality-review",
        "T9",
        True,
        "current",
        "canonical G0-G10 automatic quality snapshot",
    ),
    (
        "art_006",
        "readout",
        "workflow_readout.md",
        "research-orchestrator",
        "T10",
        True,
        "current",
        "canonical policy-refresh readout",
    ),
    (
        "art_007",
        "input_provenance",
        "inputs/input_provenance.csv",
        "evidence-ingest",
        "T1",
        True,
        "current",
        "four hash-bound official input files",
    ),
    (
        "art_008",
        "disclosed_facts",
        "research/disclosed_facts.yaml",
        "evidence-ingest",
        "T2",
        True,
        "current",
        "page-located official facts and one bounded inference",
    ),
    (
        "art_009",
        "limitations",
        "research/limitations.yaml",
        "stock-deep-dive",
        "T7",
        True,
        "current",
        "unknowns and prohibited calculations",
    ),
    (
        "art_010",
        "issue_change_log",
        "research/issue_change_log.csv",
        "refresh-research",
        "T9",
        True,
        "current",
        "four historical issue policy reclassifications",
    ),
    (
        "art_011",
        "stock_research_pack",
        "research/stock_research_pack.yaml",
        "stock-deep-dive",
        "T7",
        True,
        "current",
        "run-scoped disclosure-first research pack",
    ),
    (
        "art_012",
        "segment_exposure",
        "research/segment_exposure.yaml",
        "segment-company-mapping",
        "T6",
        True,
        "current",
        "lower-bound liquid exposure with explicit allocation gaps",
    ),
    (
        "art_013",
        "report",
        "research/stock_report_draft.md",
        "stock-deep-dive",
        "T7",
        True,
        "current",
        "gap-visible automatic report draft",
    ),
    (
        "art_014",
        "backflow_decision",
        "research/backflow_decision.yaml",
        "segment-company-mapping",
        "T8",
        True,
        "current",
        "run-scoped exposure update; no global mutation",
    ),
    (
        "art_015",
        "artifact_hashes",
        "validation/artifact_hashes.csv",
        "research-orchestrator",
        "T10",
        True,
        "current",
        "non-recursive generated-artifact hash index",
    ),
    (
        "art_016",
        "replay_receipt",
        "validation/replay_receipt.yaml",
        "research-orchestrator",
        "T10",
        True,
        "current",
        "offline source and semantic receipt",
    ),
    (
        "art_017",
        "idempotence_report",
        "validation/idempotence_report.yaml",
        "research-orchestrator",
        "T10",
        True,
        "current",
        "two-pass byte comparison",
    ),
)

EXPECTED_ARTIFACT_PATHS = tuple(spec[2] for spec in ARTIFACT_SPECS)
BASE_HASH_PATHS = tuple(
    path
    for path in EXPECTED_ARTIFACT_PATHS
    if path
    not in {
        "artifact_manifest.csv",
        "validation/artifact_hashes.csv",
        "validation/replay_receipt.yaml",
        "validation/idempotence_report.yaml",
    }
)
REPLAY_COMPARE_PATHS = BASE_HASH_PATHS + (
    "validation/artifact_hashes.csv",
    "validation/replay_receipt.yaml",
)


class ReplayContractError(RuntimeError):
    """Raised when a fixed source or output boundary is violated."""


def _canonical_text_bytes(payload: bytes) -> bytes:
    return payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_canonical_lf_text(path: Path) -> str:
    return sha256_bytes(_canonical_text_bytes(path.read_bytes()))


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(encoded)


def _yaml_text(payload: Any) -> str:
    return yaml.safe_dump(
        payload,
        allow_unicode=True,
        sort_keys=False,
        width=1000,
    )


def _csv_text(
    fieldnames: Sequence[str],
    rows: Iterable[Mapping[str, Any]],
) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=list(fieldnames),
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        normalized: dict[str, Any] = {}
        for field in fieldnames:
            value = row.get(field, "")
            if isinstance(value, bool):
                value = str(value).lower()
            elif isinstance(value, (list, tuple)):
                value = "|".join(str(item) for item in value)
            elif value is None:
                value = ""
            normalized[field] = value
        writer.writerow(normalized)
    return stream.getvalue()


def _write_text_if_changed(path: Path, content: str) -> None:
    payload = content.encode("utf-8")
    if path.is_file() and path.read_bytes() == payload:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _read_manifest(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise ReplayContractError(f"evidence manifest missing: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ReplayContractError("evidence manifest has no header")
        return [dict(row) for row in reader]


def _normalized_text(path: Path) -> str:
    return _canonical_text_bytes(path.read_bytes()).decode("utf-8")


def resolve_printed_page(text: str, page_no: int, locator: str) -> str:
    """Return one printed-page segment after validating its header and locator."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    pages = normalized.split(r"\n\f\n")
    if page_no < 1:
        raise ReplayContractError(f"invalid printed page number: {page_no}")
    header_pattern = re.compile(
        rf"(?:^|\n)\s*{page_no}\s*(?:\n|$)"
    )
    candidates = [
        page
        for page in pages
        if header_pattern.search(page[:300]) and locator in page
    ]
    if len(candidates) != 1:
        raise ReplayContractError(
            f"expected one locator match on printed page {page_no}; "
            f"observed {len(candidates)}: {locator}"
        )
    return candidates[0]


def _validate_manifest_row(row: Mapping[str, str], spec: Mapping[str, Any]) -> None:
    expected_fields = {
        "evidence_id": spec["evidence_id"],
        "source_type": spec["source_type"],
        "source_name": spec["source_name"],
        "source_group": spec["source_group"],
        "publisher": spec["publisher"],
        "publish_date": spec["publish_date"],
        "title": spec["title"],
        "raw_file_path": spec["raw_path"],
        "file_hash": spec["raw_sha256"],
        "content_hash": spec["raw_sha256"],
        "processed_text_path": spec["processed_path"],
        "reliability_rank": "A",
        "material_claim_allowed": "true",
        "status": "active",
        "parse_status": "parsed",
        "review_status": "reviewed",
        "page_count": str(spec["page_count"]),
    }
    mismatches = [
        f"{field}={row.get(field)!r}, expected {expected!r}"
        for field, expected in expected_fields.items()
        if row.get(field) != expected
    ]
    if mismatches:
        raise ReplayContractError(
            f"manifest identity mismatch for {spec['evidence_id']}: "
            + "; ".join(mismatches)
        )


def verify_official_sources(repo_root: Path) -> list[dict[str, Any]]:
    """Verify the two evidence identities and all four fixed source files."""

    manifest_rows = _read_manifest(repo_root / MANIFEST_REL)
    selected: list[dict[str, Any]] = []
    for spec in SOURCE_SPECS:
        matches = [
            row
            for row in manifest_rows
            if row.get("evidence_id") == spec["evidence_id"]
        ]
        if len(matches) != 1:
            raise ReplayContractError(
                f"expected one manifest row for {spec['evidence_id']}; "
                f"observed {len(matches)}"
            )
        _validate_manifest_row(matches[0], spec)

        raw_path = repo_root / spec["raw_path"]
        processed_path = repo_root / spec["processed_path"]
        if not raw_path.is_file() or not processed_path.is_file():
            raise ReplayContractError(
                f"fixed official inputs missing for {spec['evidence_id']}"
            )

        observed_raw = sha256_file(raw_path)
        observed_processed_file = sha256_file(processed_path)
        observed_processed_canonical = sha256_canonical_lf_text(processed_path)
        if observed_raw != spec["raw_sha256"]:
            raise ReplayContractError(
                f"raw SHA-256 mismatch for {spec['evidence_id']}: {observed_raw}"
            )
        if observed_processed_file != spec["processed_file_sha256"]:
            raise ReplayContractError(
                "processed file-byte SHA-256 mismatch for "
                f"{spec['evidence_id']}: {observed_processed_file}"
            )
        if observed_processed_canonical != spec["processed_canonical_lf_sha256"]:
            raise ReplayContractError(
                "processed canonical-LF SHA-256 mismatch for "
                f"{spec['evidence_id']}: {observed_processed_canonical}"
            )

        text = _normalized_text(processed_path)
        page_count = len(text.split(r"\n\f\n"))
        if page_count != spec["page_count"]:
            raise ReplayContractError(
                f"processed page count mismatch for {spec['evidence_id']}: "
                f"{page_count}"
            )
        for page_no, locator in spec["locators"]:
            resolve_printed_page(text, page_no, locator)

        selected.append(
            {
                "spec": spec,
                "manifest": matches[0],
                "raw_sha256": observed_raw,
                "processed_file_sha256": observed_processed_file,
                "processed_canonical_lf_sha256": observed_processed_canonical,
            }
        )
    return selected


def build_provenance_rows(
    verified_sources: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in verified_sources:
        spec = source["spec"]
        common = {
            "evidence_id": spec["evidence_id"],
            "source_type": spec["source_type"],
            "source_name": spec["source_name"],
            "source_group": spec["source_group"],
            "publisher": spec["publisher"],
            "publish_date": spec["publish_date"],
            "review_status": "reviewed",
            "page_count": spec["page_count"],
            "usage_boundary": (
                "official disclosure facts only; no unsupported allocation "
                "or driver inference"
            ),
        }
        rows.append(
            {
                **common,
                "input_id": f"input_{len(rows) + 1:03d}",
                "input_kind": "raw_official_pdf",
                "source_path": spec["raw_path"],
                "hash_scope": "file_bytes",
                "expected_sha256": spec["raw_sha256"],
                "observed_sha256": source["raw_sha256"],
                "file_sha256": source["raw_sha256"],
                "paired_input_path": spec["processed_path"],
            }
        )
        rows.append(
            {
                **common,
                "input_id": f"input_{len(rows) + 1:03d}",
                "input_kind": "processed_official_text",
                "source_path": spec["processed_path"],
                "hash_scope": "canonical_lf_text_bytes",
                "expected_sha256": spec["processed_canonical_lf_sha256"],
                "observed_sha256": source["processed_canonical_lf_sha256"],
                "file_sha256": source["processed_file_sha256"],
                "paired_input_path": spec["raw_path"],
            }
        )
    return rows


def build_disclosed_facts() -> list[dict[str, Any]]:
    annual_path = SOURCE_SPECS[0]["raw_path"]
    annual_text = SOURCE_SPECS[0]["processed_path"]
    interim_path = SOURCE_SPECS[1]["raw_path"]
    interim_text = SOURCE_SPECS[1]["processed_path"]
    direct = "direct_disclosure_no_calculation"
    display = "display_only"
    return [
        {
            "fact_id": "fact_002837_2025_room_revenue",
            "claim_type": "fact",
            "metric": "room_cooling_revenue",
            "period": "2025A",
            "value": "3448477492.62",
            "comparison_operator": "equal",
            "unit": "CNY",
            "evidence_id": ANNUAL_EVIDENCE_ID,
            "source_path": annual_path,
            "processed_text_path": annual_text,
            "page_no": 15,
            "locator": "机房温控节能产品 3,448,477,492.62 56.83%",
            "calculation_method": direct,
            "numeric_use": display,
        },
        {
            "fact_id": "fact_002837_2025_room_revenue_share",
            "claim_type": "fact",
            "metric": "room_cooling_revenue_share",
            "period": "2025A",
            "value": "56.83",
            "comparison_operator": "equal",
            "unit": "percent",
            "evidence_id": ANNUAL_EVIDENCE_ID,
            "source_path": annual_path,
            "processed_text_path": annual_text,
            "page_no": 15,
            "locator": "机房温控节能产品 3,448,477,492.62 56.83%",
            "calculation_method": direct,
            "numeric_use": display,
        },
        {
            "fact_id": "fact_002837_2025_cabinet_revenue",
            "claim_type": "fact",
            "metric": "cabinet_cooling_revenue",
            "period": "2025A",
            "value": "1977423139.19",
            "comparison_operator": "equal",
            "unit": "CNY",
            "evidence_id": ANNUAL_EVIDENCE_ID,
            "source_path": annual_path,
            "processed_text_path": annual_text,
            "page_no": 15,
            "locator": "机柜温控节能产品 1,977,423,139.19 32.59%",
            "calculation_method": direct,
            "numeric_use": display,
        },
        {
            "fact_id": "fact_002837_2025_cabinet_revenue_share",
            "claim_type": "fact",
            "metric": "cabinet_cooling_revenue_share",
            "period": "2025A",
            "value": "32.59",
            "comparison_operator": "equal",
            "unit": "percent",
            "evidence_id": ANNUAL_EVIDENCE_ID,
            "source_path": annual_path,
            "processed_text_path": annual_text,
            "page_no": 15,
            "locator": "机柜温控节能产品 1,977,423,139.19 32.59%",
            "calculation_method": direct,
            "numeric_use": display,
        },
        {
            "fact_id": "fact_002837_2025_room_cost",
            "claim_type": "fact",
            "metric": "room_cooling_cost",
            "period": "2025A",
            "value": "2470650226.09",
            "comparison_operator": "equal",
            "unit": "CNY",
            "evidence_id": ANNUAL_EVIDENCE_ID,
            "source_path": annual_path,
            "processed_text_path": annual_text,
            "page_no": 16,
            "locator": (
                "机房温控节能产品 3,448,477,492.62 "
                "2,470,650,226.09 28.36%"
            ),
            "calculation_method": direct,
            "numeric_use": display,
        },
        {
            "fact_id": "fact_002837_2025_room_gross_margin",
            "claim_type": "fact",
            "metric": "room_cooling_gross_margin",
            "period": "2025A",
            "value": "28.36",
            "comparison_operator": "equal",
            "unit": "percent",
            "evidence_id": ANNUAL_EVIDENCE_ID,
            "source_path": annual_path,
            "processed_text_path": annual_text,
            "page_no": 16,
            "locator": (
                "机房温控节能产品 3,448,477,492.62 "
                "2,470,650,226.09 28.36%"
            ),
            "calculation_method": direct,
            "numeric_use": display,
        },
        {
            "fact_id": "fact_002837_2025_cabinet_cost",
            "claim_type": "fact",
            "metric": "cabinet_cooling_cost",
            "period": "2025A",
            "value": "1438783613.25",
            "comparison_operator": "equal",
            "unit": "CNY",
            "evidence_id": ANNUAL_EVIDENCE_ID,
            "source_path": annual_path,
            "processed_text_path": annual_text,
            "page_no": 16,
            "locator": (
                "机柜温控节能产品 1,977,423,139.19 "
                "1,438,783,613.25 27.24%"
            ),
            "calculation_method": direct,
            "numeric_use": display,
        },
        {
            "fact_id": "fact_002837_2025_cabinet_gross_margin",
            "claim_type": "fact",
            "metric": "cabinet_cooling_gross_margin",
            "period": "2025A",
            "value": "27.24",
            "comparison_operator": "equal",
            "unit": "percent",
            "evidence_id": ANNUAL_EVIDENCE_ID,
            "source_path": annual_path,
            "processed_text_path": annual_text,
            "page_no": 16,
            "locator": (
                "机柜温控节能产品 1,977,423,139.19 "
                "1,438,783,613.25 27.24%"
            ),
            "calculation_method": direct,
            "numeric_use": display,
        },
        {
            "fact_id": "fact_002837_2025_industry_sales_volume",
            "claim_type": "fact",
            "metric": "precision_temperature_control_industry_sales_volume",
            "period": "2025A",
            "value": "324058",
            "comparison_operator": "equal",
            "unit": "unit",
            "aggregation_scope": (
                "precision_temperature_control_energy_saving_equipment_industry_total"
            ),
            "allocation_allowed": False,
            "evidence_id": ANNUAL_EVIDENCE_ID,
            "source_path": annual_path,
            "processed_text_path": annual_text,
            "page_no": 16,
            "locator": "销售量 台 324,058 257,932 25.64%",
            "calculation_method": direct,
            "numeric_use": display,
        },
        {
            "fact_id": "fact_002837_2025h1_liquid_revenue_lower_bound",
            "claim_type": "fact",
            "metric": "liquid_cooling_related_revenue",
            "period": "2025H1",
            "value": "200000000",
            "comparison_operator": "greater_than",
            "unit": "CNY",
            "evidence_id": INTERIM_EVIDENCE_ID,
            "source_path": interim_path,
            "processed_text_path": interim_text,
            "page_no": 9,
            "locator": "液冷相关营业收入超过 2 亿元",
            "calculation_method": direct,
            "numeric_use": display,
        },
        {
            "fact_id": "fact_002837_2025h1_room_liquid_partial_overlap",
            "claim_type": "inference",
            "metric": "room_liquid_classification_relationship",
            "period": "2025H1",
            "value": "partial_overlap_confirmed",
            "comparison_operator": "not_applicable",
            "unit": "not_applicable",
            "overlap_amount": "UNKNOWN_NOT_DISCLOSED",
            "cabinet_relationship": "UNKNOWN_NOT_DISCLOSED",
            "evidence_id": INTERIM_EVIDENCE_ID,
            "source_path": interim_path,
            "processed_text_path": interim_text,
            "page_no": 9,
            "locator": (
                "相关营业收入部分计入“机房温控\n"
                "节能产品”，部分计入“其他”"
            ),
            "calculation_method": (
                "bounded_inference_from_explicit_disclosure_classification"
            ),
            "numeric_use": "prohibited",
        },
    ]


def build_limitations() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "artifact_type": "r5_v1_policy_refresh_limitations",
        "workflow_id": WORKFLOW_ID,
        "as_of_date": AS_OF_DATE,
        "unknowns": [
            {
                "limitation_id": "lim_room_cabinet_driver_disaggregation",
                "status": "UNKNOWN_NOT_DISCLOSED",
                "fields": [
                    "room_cooling_volume",
                    "room_cooling_unit_price",
                    "room_cooling_product_mix",
                    "cabinet_cooling_volume",
                    "cabinet_cooling_unit_price",
                    "cabinet_cooling_product_mix",
                ],
                "numeric_use": "prohibited",
                "reason": (
                    "324058 units is an industry-classification total and cannot "
                    "be split between product lines"
                ),
            },
            {
                "limitation_id": "lim_liquid_unit_economics",
                "status": "METHOD_UNAVAILABLE",
                "fields": [
                    "liquid_unit_value",
                    "liquid_acceptance_rate",
                    "liquid_standalone_gross_margin",
                ],
                "numeric_use": "prohibited",
                "reason": "official sources do not disclose the required standalone fields",
            },
            {
                "limitation_id": "lim_room_liquid_exact_allocation",
                "status": "METHOD_UNAVAILABLE",
                "known_relationship": "partial_overlap_confirmed",
                "fields": ["overlap_revenue_amount", "overlap_gross_profit_amount"],
                "numeric_use": "prohibited",
                "reason": (
                    "the interim report confirms partial classification overlap "
                    "but discloses no allocation amount"
                ),
            },
            {
                "limitation_id": "lim_cabinet_liquid_relationship",
                "status": "UNKNOWN_NOT_DISCLOSED",
                "fields": ["cabinet_liquid_overlap_relationship"],
                "numeric_use": "prohibited",
                "assertions_forbidden": ["overlaps", "never_overlaps"],
                "reason": (
                    "the interim disclosure names room cooling and other, not "
                    "cabinet cooling"
                ),
            },
        ],
        "prohibited_operations": [
            "split_industry_total_volume_into_room_or_cabinet",
            "treat_liquid_lower_bound_as_exact_value",
            "add_liquid_revenue_to_room_revenue",
            "add_liquid_revenue_to_cabinet_revenue",
            "calculate_room_liquid_overlap_without_disclosed_allocation",
            "assert_cabinet_liquid_overlap",
            "assert_cabinet_liquid_never_overlap",
        ],
        "calculations": [],
    }


def build_open_todos() -> list[dict[str, Any]]:
    pack_path = (
        f"{TARGET_RUN_REL.as_posix()}/research/stock_research_pack.yaml"
    )
    exposure_path = (
        f"{TARGET_RUN_REL.as_posix()}/research/segment_exposure.yaml"
    )
    return [
        {
            "issue_id": "R5V1P3-G3-001",
            "historical_issue_id": "R5B13R-G3-001",
            "severity": "high",
            "stage": "T9",
            "gate_id": "G3",
            "target_artifact": pack_path,
            "description": (
                "机房与机柜产品线的销量、单价和产品组合未披露；行业分类总销量仅展示，"
                "未拆分且未进入产品线驱动计算。"
            ),
            "fix_owner_skill": "evidence-ingest",
            "status": "open",
            "created_at": AS_OF_DATE,
            "resolved_at": "",
            "notes": (
                "next_step=仅在发行人披露同期间同口径分产品数据后更新；"
                "324058台不得替代产品线销量"
            ),
            "impact_scope": "claim",
            "active_disposition": "unknown",
            "affected_capabilities": [
                "room_cooling_driver_disaggregation",
                "cabinet_cooling_driver_disaggregation",
            ],
            "blocks_current_goal": False,
            "used_in_numeric_calculation": False,
        },
        {
            "issue_id": "R5V1P3-G3-002",
            "historical_issue_id": "R5B13R-G3-002",
            "severity": "high",
            "stage": "T9",
            "gate_id": "G3",
            "target_artifact": pack_path,
            "description": (
                "液冷单机价值、验收率和独立毛利率未披露；当前报告未建立该驱动模型。"
            ),
            "fix_owner_skill": "evidence-ingest",
            "status": "open",
            "created_at": AS_OF_DATE,
            "resolved_at": "",
            "notes": (
                "next_step=仅在合同、验收或独立毛利披露出现后建立模型；"
                "大于2亿元的收入下界不得推导单位经济性"
            ),
            "impact_scope": "method",
            "active_disposition": "method_unavailable",
            "affected_capabilities": ["liquid_driver_model"],
            "blocks_current_goal": False,
            "used_in_numeric_calculation": False,
        },
        {
            "issue_id": "R5V1P3-G6-001",
            "historical_issue_id": "R5B13R-G6-001",
            "severity": "high",
            "stage": "T9",
            "gate_id": "G6",
            "target_artifact": exposure_path,
            "description": (
                "机房与液冷存在部分分类重叠，但具体收入和毛利分配金额未披露；"
                "当前没有执行分配或跨线相加。"
            ),
            "fix_owner_skill": "stock-deep-dive",
            "status": "open",
            "created_at": AS_OF_DATE,
            "resolved_at": "",
            "notes": (
                "next_step=等待同期间可核验分配证据；在此之前保持金额unknown并禁止聚合"
            ),
            "impact_scope": "method",
            "active_disposition": "method_unavailable",
            "affected_capabilities": [
                "room_liquid_exact_allocation",
                "cross_line_aggregation",
            ],
            "blocks_current_goal": False,
            "used_in_numeric_calculation": False,
        },
        {
            "issue_id": "R5V1P3-G6-002",
            "historical_issue_id": "R5B13R-G6-002",
            "severity": "high",
            "stage": "T9",
            "gate_id": "G6",
            "target_artifact": exposure_path,
            "description": (
                "机柜与液冷的关系未披露；当前既不主张overlap，也不主张never-overlap。"
            ),
            "fix_owner_skill": "stock-deep-dive",
            "status": "open",
            "created_at": AS_OF_DATE,
            "resolved_at": "",
            "notes": (
                "next_step=等待发行人明确业务线归类或可核验分配证据；"
                "历史overlaps假设已退出当前口径"
            ),
            "impact_scope": "claim",
            "active_disposition": "unknown",
            "affected_capabilities": ["cabinet_liquid_relationship"],
            "blocks_current_goal": False,
            "used_in_numeric_calculation": False,
        },
    ]


def derive_status(issues: Sequence[Mapping[str, Any]]) -> str:
    """Derive the workflow outcome from current-goal issue semantics."""

    outcomes: list[str] = []
    non_active = {
        "historical_backlog",
        "policy_retired",
        "not_required_for_active_v1",
    }
    for issue in issues:
        if issue.get("status") == "closed":
            continue
        disposition = issue.get("active_disposition")
        impact_scope = issue.get("impact_scope")
        capabilities = issue.get("affected_capabilities")
        blocks_value = issue.get("blocks_current_goal")
        if impact_scope not in {
            "workflow",
            "report",
            "section",
            "claim",
            "method",
            "none",
        }:
            raise ReplayContractError(f"invalid impact_scope: {impact_scope!r}")
        if (
            not isinstance(capabilities, list)
            or any(
                not isinstance(value, str) or not value.strip()
                for value in capabilities
            )
            or len(capabilities) != len(set(capabilities))
        ):
            raise ReplayContractError(
                "affected_capabilities must be a unique list of non-empty strings"
            )
        if not isinstance(blocks_value, bool):
            raise ReplayContractError("blocks_current_goal must be a boolean")
        blocks = blocks_value
        used = issue.get("used_in_numeric_calculation") is True
        if disposition in non_active:
            if impact_scope != "none" or capabilities or blocks:
                raise ReplayContractError(
                    f"{disposition} requires impact_scope=none, no capabilities, "
                    "and blocks_current_goal=false"
                )
            outcomes.append("accepted")
        elif disposition == "active_defect":
            if impact_scope == "none" or not capabilities or not blocks:
                raise ReplayContractError(
                    "active_defect requires active scope, capabilities and "
                    "blocks_current_goal=true"
                )
            outcomes.append("blocked" if impact_scope == "workflow" else "needs_fix")
        elif disposition == "unknown":
            if impact_scope in {None, "none", "workflow"} or not capabilities:
                raise ReplayContractError(
                    "unknown must be scoped below workflow with affected capabilities"
                )
            outcomes.append(
                "needs_fix" if used or blocks else "accepted_with_todos"
            )
        elif disposition == "method_unavailable":
            if impact_scope != "method" or not capabilities:
                raise ReplayContractError(
                    "method_unavailable requires method scope and capabilities"
                )
            outcomes.append(
                "blocked" if blocks else (
                    "needs_fix" if used else "accepted_with_todos"
                )
            )
        elif disposition == "report_limitation":
            if (
                impact_scope in {None, "none", "workflow"}
                or not capabilities
                or blocks
            ):
                raise ReplayContractError(
                    "report_limitation must be visible, below workflow and nonblocking"
                )
            outcomes.append(
                "needs_fix" if used else "accepted_with_todos"
            )
        else:
            raise ReplayContractError(
                f"unsupported active disposition: {disposition!r}"
            )
    if "blocked" in outcomes:
        return "blocked"
    if "needs_fix" in outcomes:
        return "needs_fix"
    if "accepted_with_todos" in outcomes:
        return "accepted_with_todos"
    return "accepted"


def build_quality_gates(
    issues: Sequence[Mapping[str, Any]],
    status: str,
) -> list[dict[str, Any]]:
    if any(issue.get("used_in_numeric_calculation") for issue in issues):
        raise ReplayContractError("unknown or unavailable values entered a calculation")
    if status not in {"accepted", "accepted_with_todos"}:
        raise ReplayContractError(
            f"automatic quality cannot pass for derived status {status}"
        )
    notes = {
        "G0": "002837、两份正式披露、离线边界和目标run均明确。",
        "G1": "两份PDF与两份processed text哈希一致，页码locator全部解析。",
        "G2": "直接披露标为fact；room/liquid关系标为有边界的inference。",
        "G3": "使用的每个数均有期间、单位、来源、页码和方法；缺失驱动未使用。",
        "G4": "ai_server_liquid_cooling exposure由正式披露下界与显式缺口支持。",
        "G5": "本次stock-first刷新不重建company universe。",
        "G6": "room/liquid部分重叠与未知金额并存；cabinet关系保持unknown且未聚合。",
        "G7": "自动报告展示事实、来源、限制和TODO，无隐藏缺口。",
        "G8": "backflow为run-scoped更新；未越权修改全局exposure。",
        "G9": "没有交易指令、仓位建议、收益保证或确定性承诺。",
        "G10": "六件套唯一，辅助产物、重放receipt和哈希索引齐全。",
    }
    return [
        {
            "gate_id": f"G{index}",
            "status": "not_applicable" if index == 5 else "pass",
            "checked_by": "quality-review",
            "checked_at": AS_OF_DATE,
            "notes": notes[f"G{index}"],
        }
        for index in range(11)
    ]


def _artifact_state_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, artifact_type, relative, skill, stage, required, status, notes in ARTIFACT_SPECS:
        rows.append(
            {
                "artifact_type": artifact_type,
                "path": f"{TARGET_RUN_REL.as_posix()}/{relative}",
                "created_by_skill": skill,
                "stage": stage,
                "status": status,
                "required": required,
                "notes": notes,
            }
        )
    return rows


def build_state(
    facts: Sequence[Mapping[str, Any]],
    issues: Sequence[Mapping[str, Any]],
    gates: Sequence[Mapping[str, Any]],
    status: str,
) -> dict[str, Any]:
    automatic_pass = (
        status in {"accepted", "accepted_with_todos"}
        and len(gates) == 11
        and all(gate["status"] in {"pass", "not_applicable"} for gate in gates)
    )
    return {
        "state_schema_version": "r5_v1",
        "decision_semantics_version": "current_goal_v1",
        "final_report_review_semantics_version": "final_report_review_v1",
        "workflow_id": WORKFLOW_ID,
        "workflow_type": "stock_first_closed_loop",
        "run_mode": "normal",
        "status": status,
        "created_at": AS_OF_DATE,
        "updated_at": AS_OF_DATE,
        "owner": "codex",
        "active_segment_id": "ai_server_liquid_cooling",
        "active_company_id": "cn_002837_invic",
        "current_stage": "T10",
        "completed_stages": [f"T{index}" for index in range(11)],
        "next_stage": None,
        "active_skill": "research-orchestrator",
        "required_next_skill": None,
        "automated_report_quality_passed": automatic_pass,
        "system_v1_complete": False,
        "sample_quality_ready": False,
        "p2_ready": False,
        "release_ready": False,
        "final_report_review_status": "not_requested",
        "final_report_review": {
            "report_path": None,
            "report_sha256": None,
            "reviewer": None,
            "reviewed_at": None,
            "decision": "not_requested",
            "notes": None,
            "change_scope": None,
        },
        "evidence_snapshot": {
            "manifest_path": (
                f"{TARGET_RUN_REL.as_posix()}/inputs/input_provenance.csv"
            ),
            "evidence_count": 2,
            "input_file_count": 4,
            "notes": "two hash-bound official disclosures; offline only",
        },
        "claims_snapshot": {
            "draft_path": (
                f"{TARGET_RUN_REL.as_posix()}/research/disclosed_facts.yaml"
            ),
            "registry_path": "data/manifests/claims_registry.csv",
            "claim_count": len(facts),
            "notes": "direct facts plus one bounded relationship inference",
        },
        "metrics_snapshot": {
            "draft_path": (
                f"{TARGET_RUN_REL.as_posix()}/research/disclosed_facts.yaml"
            ),
            "registry_path": None,
            "metric_count": sum(
                fact.get("unit") not in {None, "not_applicable"}
                for fact in facts
            ),
            "notes": "direct-disclosure values only; no derived allocation",
        },
        "artifacts": _artifact_state_rows(),
        "open_todos": list(issues),
        "quality_gates": list(gates),
        "entry_criteria": [
            "P2 checkpoint passed",
            "four official input files match fixed hashes",
            "all required printed-page locators resolve",
            "no network access",
        ],
        "exit_criteria": [
            "standard six-piece control plane exists",
            "current-goal workflow state validates",
            "two materialization passes have zero byte drift",
            "unknown values are visible and unused",
            "historical workflow directories are not read",
        ],
        "notes": (
            "Automatic report quality passed. Four high-severity research "
            "limitations remain visible, unused and nonblocking; therefore the "
            "derived status is accepted_with_todos. Final report review is not requested."
        ),
    }


def build_issue_change_rows(
    issues: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    prior_assertions = {
        "R5B13R-G3-001": (
            "missing line drivers were treated as a high automatic close blocker"
        ),
        "R5B13R-G3-002": (
            "missing liquid unit economics were treated as a high automatic close blocker"
        ),
        "R5B13R-G6-001": (
            "room/liquid overlap allocation gap was treated as an automatic close blocker"
        ),
        "R5B13R-G6-002": (
            "cabinet/liquid relationship was assumed overlaps and treated as a blocker"
        ),
    }
    evidence = {
        "R5B13R-G3-001": (ANNUAL_EVIDENCE_ID, "15|16"),
        "R5B13R-G3-002": (INTERIM_EVIDENCE_ID, "9"),
        "R5B13R-G6-001": (INTERIM_EVIDENCE_ID, "9"),
        "R5B13R-G6-002": (INTERIM_EVIDENCE_ID, "9"),
    }
    rationales = {
        "R5B13R-G3-001": (
            "产品线收入与毛利可直接展示；总销量不拆分，缺失驱动不参与计算。"
        ),
        "R5B13R-G3-002": (
            "液冷收入只披露下界，单位价值、验收率和独立毛利模型被明确省略。"
        ),
        "R5B13R-G6-001": (
            "正式披露确认液冷收入部分计入机房，但未披露金额；保持unknown且禁止相加。"
        ),
        "R5B13R-G6-002": (
            "正式披露未提及机柜归类；历史overlaps假设退休，never-overlap也不成立。"
        ),
    }
    rows: list[dict[str, Any]] = []
    for issue in issues:
        prior = issue["historical_issue_id"]
        evidence_id, page_no = evidence[prior]
        rows.append(
            {
                "prior_issue_id": prior,
                "current_issue_id": issue["issue_id"],
                "severity": issue["severity"],
                "change_type": "policy_reclassification",
                "historical_resolved": False,
                "prior_assertion": prior_assertions[prior],
                "current_disposition": issue["active_disposition"],
                "impact_scope": issue["impact_scope"],
                "affected_capabilities": issue["affected_capabilities"],
                "blocks_current_goal": issue["blocks_current_goal"],
                "numeric_use": "unused",
                "evidence_id": evidence_id,
                "page_no": page_no,
                "rationale": rationales[prior],
            }
        )
    return rows


def build_research_pack(
    facts: Sequence[Mapping[str, Any]],
    issues: Sequence[Mapping[str, Any]],
    status: str,
) -> dict[str, Any]:
    fact_ids = [fact["fact_id"] for fact in facts]
    annual_trace = {"evidence_id": ANNUAL_EVIDENCE_ID}
    missing_metric = {
        "value": None,
        "missing_reason": "MISSING_DISCLOSURE",
    }
    return {
        "schema_version": "r5_mvp_v0.3",
        "artifact_type": "R5_stock_research_pack",
        "status": "draft",
        "pack_status": "research_draft",
        "metadata": {
            "workflow_id": WORKFLOW_ID,
            "generated_at": AS_OF_DATE,
            "source_pack": (
                f"{TARGET_RUN_REL.as_posix()}/research/disclosed_facts.yaml"
            ),
            "generation_mode": "offline_official_disclosure_policy_refresh",
        },
        "stock": {
            "company_id": "cn_002837_invic",
            "company_name": "英维克",
            "stock_code": "002837",
            "exchange": "SZSE",
            "currency": "CNY",
        },
        "quality_status": {
            "r5_gate_status": "pass",
            "allowed_report_level": "research_draft",
            "r5_external_state": "R5_research_draft",
            "high_issue_count": 0,
            "high_issue_count_semantics": (
                "active_machine_validation_defects_only"
            ),
            "medium_issue_count": 0,
            "descriptive_high_limitation_count": len(issues),
            "active_defect_count": 0,
            "source_gap_visible": True,
            "no_advice_gate_passed": True,
            "current_goal_status": status,
            "final_report_review_status": "not_requested",
        },
        "source_gap_policy": {
            "missing_value_tokens": [
                "MISSING_DISCLOSURE",
                "TODO_SOURCE_REQUIRED",
                "TODO_MODEL_INPUT",
                "TODO_MARKET_DATA",
                "TODO_PEER_DATA",
                "LOW_CONFIDENCE_CLUE_ONLY",
            ],
            "rule": (
                "Keep every gap visible and never convert a missing value into "
                "a factual claim."
            ),
        },
        "company_identity_pack": {
            "status": "ready",
            "company_id": "cn_002837_invic",
            "legal_name": "深圳市英维克科技股份有限公司",
            "stock_code": "002837",
            "exchange": "SZSE",
            "identity_evidence_ids": [
                ANNUAL_EVIDENCE_ID,
                INTERIM_EVIDENCE_ID,
            ],
        },
        "evidence_snapshot_pack": {
            "status": "ready",
            "as_of_date": AS_OF_DATE,
            "evidence_manifest_path": MANIFEST_REL.as_posix(),
            "evidence_ids": [ANNUAL_EVIDENCE_ID, INTERIM_EVIDENCE_ID],
            "evidence_count": 2,
            "official_filings_status": "ready",
            "critical_missing_sources": [],
        },
        "financial_history_pack": {
            "status": "partial",
            "periods": ["2025A", "2025H1"],
            "metrics": [
                {
                    "metric_name": "room_cooling_revenue",
                    "period": "2025A",
                    "value": "3448477492.62",
                    "unit": "CNY",
                    **annual_trace,
                },
                {
                    "metric_name": "cabinet_cooling_revenue",
                    "period": "2025A",
                    "value": "1977423139.19",
                    "unit": "CNY",
                    **annual_trace,
                },
                {
                    "metric_name": "liquid_cooling_related_revenue",
                    "period": "2025H1",
                    "operator": "greater_than",
                    "value": "200000000",
                    "unit": "CNY",
                    "evidence_id": INTERIM_EVIDENCE_ID,
                },
            ],
            "non_recurring_items": [],
            "adjusted_profit_bridge": [],
            "cashflow_quality": {
                "claim_type": "unknown",
                "summary": None,
                "missing_reason": "TODO_SOURCE_REQUIRED",
            },
        },
        "business_breakdown_pack": {
            "status": "partial",
            "business_lines": [
                {
                    "business_name": "机房温控节能产品",
                    "revenue": {
                        "value": "3448477492.62",
                        "unit": "CNY",
                        **annual_trace,
                    },
                    "revenue_pct": {
                        "value": "56.83",
                        "unit": "percent",
                        **annual_trace,
                    },
                    "gross_margin": {
                        "value": "28.36",
                        "unit": "percent",
                        **annual_trace,
                    },
                    "gross_profit": dict(missing_metric),
                    "gross_profit_pct": dict(missing_metric),
                    "cost": {
                        "value": "2470650226.09",
                        "unit": "CNY",
                        **annual_trace,
                    },
                    "volume": {
                        "value": None,
                        "missing_reason": "MISSING_DISCLOSURE",
                    },
                    "unit_price": {
                        "value": None,
                        "missing_reason": "MISSING_DISCLOSURE",
                    },
                    "product_mix": {
                        "value": None,
                        "missing_reason": "MISSING_DISCLOSURE",
                    },
                    "confidence": "high",
                },
                {
                    "business_name": "机柜温控节能产品",
                    "revenue": {
                        "value": "1977423139.19",
                        "unit": "CNY",
                        **annual_trace,
                    },
                    "revenue_pct": {
                        "value": "32.59",
                        "unit": "percent",
                        **annual_trace,
                    },
                    "gross_margin": {
                        "value": "27.24",
                        "unit": "percent",
                        **annual_trace,
                    },
                    "gross_profit": dict(missing_metric),
                    "gross_profit_pct": dict(missing_metric),
                    "cost": {
                        "value": "1438783613.25",
                        "unit": "CNY",
                        **annual_trace,
                    },
                    "volume": {
                        "value": None,
                        "missing_reason": "MISSING_DISCLOSURE",
                    },
                    "unit_price": {
                        "value": None,
                        "missing_reason": "MISSING_DISCLOSURE",
                    },
                    "product_mix": {
                        "value": None,
                        "missing_reason": "MISSING_DISCLOSURE",
                    },
                    "confidence": "high",
                },
            ],
            "profit_pool_summary": {
                "status": "omitted",
                "missing_reason": "MISSING_DISCLOSURE",
            },
            "missing_items": [
                "MISSING_DISCLOSURE: line-level volume, unit price, product mix",
                "MISSING_DISCLOSURE: directly disclosed gross-profit amount",
            ],
        },
        "segment_exposure_pack": {
            "status": "partial",
            "exposures": [
                {
                    "segment_id": "ai_server_liquid_cooling",
                    "exposure_type": "revenue",
                    "exposure_score": 4,
                    "confidence": "high",
                    "revenue_pct": "MISSING_DISCLOSURE",
                    "profit_pct": "MISSING_DISCLOSURE",
                    "evidence_ids": [INTERIM_EVIDENCE_ID],
                    "missing_reason": (
                        "MISSING_DISCLOSURE: revenue share and exact allocation"
                    ),
                    "exposure_score_rationale": (
                        "issuer-disclosed positive revenue lower bound confirms "
                        "business exposure; undisclosed share prevents score 5"
                    ),
                    "backflow_decision": "update_exposure",
                }
            ],
        },
        "industry_context_pack": {
            "status": "TODO",
            "industry_cards": [],
            "missing_reason": "TODO_SOURCE_REQUIRED",
        },
        "peer_comparison_pack": {
            "status": "TODO",
            "peer_set": [],
            "missing_reason": "TODO_PEER_DATA",
        },
        "forecast_model_pack": {
            "status": "TODO",
            "forecast_years": ["2026E", "2027E", "2028E"],
            "required_metrics": [
                "revenue",
                "gross_margin",
                "net_profit_attributable",
                "eps",
            ],
            "scenarios": {},
            "missing_reason": "TODO_MODEL_INPUT",
        },
        "valuation_pack": {
            "status": "TODO",
            "market_snapshot": {
                "as_of_date": None,
                "current_price": None,
                "missing_reason": "TODO_MARKET_DATA",
            },
            "peer_context": {"missing_reason": "TODO_PEER_DATA"},
        },
        "technical_market_pack": {
            "status": "TODO",
            "as_of_date": None,
            "missing_reason": "TODO_MARKET_DATA",
        },
        "sentiment_event_pack": {
            "status": "TODO",
            "as_of_date": None,
            "missing_reason": "TODO_SOURCE_REQUIRED",
        },
        "risk_counterevidence_pack": {
            "status": "partial",
            "risks": [
                {
                    "risk_name": "liquid allocation remains undisclosed",
                    "missing_reason": "MISSING_DISCLOSURE",
                },
                {
                    "risk_name": "cabinet-liquid relationship remains unknown",
                    "missing_reason": "MISSING_DISCLOSURE",
                },
            ],
            "counterevidence": [
                {
                    "claim_type": "fact",
                    "summary": (
                        "2025H1 liquid-related revenue is above CNY 200m and "
                        "partly classified under room cooling and other."
                    ),
                    "evidence_id": INTERIM_EVIDENCE_ID,
                }
            ],
        },
        "source_gap_register": [
            {
                "gap_id": "R5P3_GAP_DISCLOSURE",
                "section": "business_and_exposure",
                "missing_data": "MISSING_DISCLOSURE",
                "impact_on_conclusion": (
                    "line drivers and exact overlap allocation are omitted"
                ),
                "fix_owner_skill": "evidence-ingest",
                "next_action": "keep the disclosed gaps visible",
            },
            {
                "gap_id": "R5P3_GAP_SOURCE",
                "section": "industry_sentiment_cashflow",
                "missing_data": "TODO_SOURCE_REQUIRED",
                "impact_on_conclusion": "no unsupported context or cashflow claim",
                "fix_owner_skill": "evidence-ingest",
                "next_action": "register an official source before use",
            },
            {
                "gap_id": "R5P3_GAP_MODEL",
                "section": "forecast",
                "missing_data": "TODO_MODEL_INPUT",
                "impact_on_conclusion": "forecast model omitted",
                "fix_owner_skill": "stock-deep-dive",
                "next_action": "add reviewed assumptions before modeling",
            },
            {
                "gap_id": "R5P3_GAP_MARKET",
                "section": "valuation_and_technical",
                "missing_data": "TODO_MARKET_DATA",
                "impact_on_conclusion": "market and valuation language omitted",
                "fix_owner_skill": "evidence-ingest",
                "next_action": "register a machine-qualified market snapshot",
            },
            {
                "gap_id": "R5P3_GAP_PEER",
                "section": "peer_and_valuation",
                "missing_data": "TODO_PEER_DATA",
                "impact_on_conclusion": "peer comparison omitted",
                "fix_owner_skill": "company-valuation",
                "next_action": "register a reviewed peer snapshot",
            },
        ],
        "report_composition_pack": {
            "status": "partial",
            "allowed_report_level": "research_draft",
            "source_gap_report_path": (
                f"{TARGET_RUN_REL.as_posix()}/research/limitations.yaml"
            ),
            "open_questions_path": (
                f"{TARGET_RUN_REL.as_posix()}/open_todos.csv"
            ),
            "composer_may_create_new_facts": False,
        },
        "policy_refresh_extension": {
            "periods": ["2025A", "2025H1"],
            "disclosed_metric_fact_ids": fact_ids[:-1],
            "relationship_inference_fact_ids": [fact_ids[-1]],
            "industry_sales_volume": {
                "period": "2025A",
                "value": "324058",
                "unit": "unit",
                "scope": (
                    "precision_temperature_control_energy_saving_equipment_"
                    "industry_total"
                ),
                "allocation_allowed": False,
                "numeric_use": "display_only",
            },
            "liquid_cooling_related": {
                "revenue_2025h1_cny": {
                    "operator": "greater_than",
                    "value": "200000000",
                    "evidence_id": INTERIM_EVIDENCE_ID,
                },
                "classification": {
                    "room_cooling": "partial_overlap_confirmed",
                    "other": "partial_overlap_confirmed",
                    "cabinet_cooling": "UNKNOWN_NOT_DISCLOSED",
                },
                "unit_value": "UNKNOWN_NOT_DISCLOSED",
                "acceptance_rate": "UNKNOWN_NOT_DISCLOSED",
                "standalone_gross_margin": "UNKNOWN_NOT_DISCLOSED",
                "exact_allocation": "UNKNOWN_NOT_DISCLOSED",
            },
            "calculation_policy": {
                "calculations": [],
                "cross_line_aggregation_allowed": False,
                "unknown_values_used": False,
                "lower_bound_treated_as_exact": False,
            },
            "current_issue_ids": [issue["issue_id"] for issue in issues],
        },
        "workflow_controls": {
            "automatic_quality_status": "pass",
            "final_report_review_status": "not_requested",
            "sample_quality_ready": False,
            "p2_ready": False,
        },
    }


def build_segment_exposure() -> dict[str, Any]:
    return {
        "schema_version": "segment_exposure_v0.1",
        "artifact_type": "segment_exposure",
        "status": "current",
        "workflow_id": WORKFLOW_ID,
        "company_id": "cn_002837_invic",
        "stock_code": "002837",
        "company_name": "英维克",
        "as_of_date": AS_OF_DATE,
        "exposures": [
            {
                "exposure_id": "exp_002837_ai_server_liquid_cooling_2025h1",
                "segment_id": "ai_server_liquid_cooling",
                "segment_name": "AI服务器液冷",
                "exposure_type": "revenue",
                "exposure_score": 4,
                "confidence": "high",
                "period": "2025H1",
                "liquid_related_revenue": {
                    "operator": "greater_than",
                    "value": "200000000",
                    "unit": "CNY",
                },
                "revenue_pct": "MISSING_DISCLOSURE",
                "profit_pct": "MISSING_DISCLOSURE",
                "evidence_ids": [INTERIM_EVIDENCE_ID],
                "claim_ids": [],
                "metric_ids": [],
                "missing_reason": (
                    "MISSING_DISCLOSURE: revenue share, profit share and exact "
                    "business-line allocation"
                ),
                "exposure_score_rationale": (
                    "issuer-disclosed positive revenue lower bound confirms "
                    "business exposure; undisclosed share prevents score 5"
                ),
                "backflow_decision": "update_exposure",
                "next_action": (
                    "keep exact allocation unknown until issuer disclosure"
                ),
                "source_metric_scope": (
                    "liquid_cooling_related_revenue_lower_bound"
                ),
                "uses_company_total_revenue_as_segment_revenue": False,
                "fact_ids": [
                    "fact_002837_2025h1_liquid_revenue_lower_bound",
                    "fact_002837_2025h1_room_liquid_partial_overlap",
                ],
                "line_relationships": {
                    "room_cooling": {
                        "relationship": "partial_overlap_confirmed",
                        "allocation_amount": "UNKNOWN_NOT_DISCLOSED",
                    },
                    "other": {
                        "relationship": "partial_overlap_confirmed",
                        "allocation_amount": "UNKNOWN_NOT_DISCLOSED",
                    },
                    "cabinet_cooling": {
                        "relationship": "UNKNOWN_NOT_DISCLOSED",
                        "overlap_asserted": False,
                        "never_overlap_asserted": False,
                    },
                },
                "allocation_status": "MISSING_DISCLOSURE",
                "aggregation_allowed": False,
                "confidence_detail": {
                    "revenue_lower_bound": "high",
                    "room_other_classification": "high",
                    "cabinet_relationship": "unknown",
                },
            }
        ],
        "global_exposure_updated": False,
        "sample_quality_ready": False,
        "p2_ready": False,
    }


def build_backflow_decision() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "artifact_type": "r5_v1_policy_refresh_backflow_decision",
        "workflow_id": WORKFLOW_ID,
        "as_of_date": AS_OF_DATE,
        "backflow_decision": "update_exposure",
        "run_scoped_update_recorded": True,
        "run_scoped_exposure_path": (
            f"{TARGET_RUN_REL.as_posix()}/research/segment_exposure.yaml"
        ),
        "global_state_updated": False,
        "global_update_required_for_current_goal": False,
        "reason": (
            "P3 authorizes a canonical run-scoped refresh only. The official "
            "liquid-revenue lower bound and overlap boundary are captured in the "
            "run; no global exposure artifact is mutated."
        ),
        "unresolved_limitations_visible": True,
        "required_next_skill": None,
        "next_stage": None,
    }


def render_report(status: str) -> str:
    return f"""# 002837 英维克：2025 正式披露政策刷新

## 自动质量结论

- 当前自动状态：`{status}`。
- 该状态由四条可见、未使用、非阻断的研究限制推导，不代表缺失字段已经披露。
- 最终报告人审：`not_requested`；`sample_quality_ready=false`，`p2_ready=false`。

## 正式披露事实

- 2025 年年报第 15 页：机房温控节能产品营业收入为 3,448,477,492.62 元，占营业收入 56.83%；机柜温控节能产品营业收入为 1,977,423,139.19 元，占营业收入 32.59%。来源：`{ANNUAL_EVIDENCE_ID}`。
- 2025 年年报第 16 页：机房温控节能产品营业成本为 2,470,650,226.09 元、毛利率 28.36%；机柜温控节能产品营业成本为 1,438,783,613.25 元、毛利率 27.24%。来源：`{ANNUAL_EVIDENCE_ID}`。
- 2025 年年报第 16 页披露精密温控节能设备行业分类总销量 324,058 台。该数仅按原披露口径展示，不拆分为机房、机柜或液冷销量。
- 2025 年半年报第 9 页披露，报告期内算力设备及机房液冷相关营业收入超过 2 亿元；这里是严格下界，不是精确等于 2 亿元。来源：`{INTERIM_EVIDENCE_ID}`。

## 业务线关系

- 半年报明确液冷相关收入部分计入“机房温控节能产品”，部分计入“其他”，因此机房与液冷存在部分分类重叠。
- 披露没有给出重叠收入或毛利金额。本次不执行分配，也不把液冷收入与机房收入相加。
- 披露没有说明机柜与液冷的关系。本次既不主张 overlap，也不主张 never-overlap。

## 可见限制

- 机房和机柜的产品线销量、单价与产品组合：`UNKNOWN_NOT_DISCLOSED`，未进入数值计算。
- 液冷的单机价值、验收率与独立毛利率：`METHOD_UNAVAILABLE`，未建立模型。
- 机房与液冷的精确分配：`METHOD_UNAVAILABLE`，禁止跨业务线聚合。
- 机柜与液冷的关系：`UNKNOWN_NOT_DISCLOSED`。

## 使用边界

本稿只呈现正式披露事实、受限推断和显式未知项，不提供交易指令或收益承诺，不构成投资建议。
"""


def render_quality_report(
    gates: Sequence[Mapping[str, Any]],
    status: str,
) -> str:
    rows = "\n".join(
        f"| {gate['gate_id']} | {gate['status']} | {gate['notes']} |"
        for gate in gates
    )
    return f"""# 002837 V1 policy refresh quality gate

- Workflow: `{WORKFLOW_ID}`
- Derived status: `{status}`
- Automated report quality: `pass`
- Final report review: `not_requested`

| Gate | Status | Evidence summary |
|---|---|---|
{rows}

四条 high issue 均保持 open，但它们是可见、未使用、非阻断的 unknown 或 method limitation。severity 本身不替代 current-goal disposition。
"""


def render_run_log(status: str, semantic_digest: str) -> str:
    return f"""# 002837 V1 policy refresh run log

- Date: `{AS_OF_DATE}`
- Mode: offline official-disclosure refresh
- Workflow: `{WORKFLOW_ID}`
- Command: `{EXACT_REPLAY_COMMAND}`
- Network access: `false`
- Historical workflow reads: `false`
- Raw overwrite: `false`
- Derived status: `{status}`
- Canonical semantic digest: `{semantic_digest}`

Stages T0–T10 were materialized from two hash-bound evidence identities and four fixed input files. Missing values remained explicit and unused.
"""


def render_readout(status: str, semantic_digest: str) -> str:
    return f"""# 002837 V1 policy refresh readout

## Result

- Workflow: `{WORKFLOW_ID}`
- Derived automatic status: `{status}`
- Automatic G0–G10: `pass` (`G5=not_applicable`)
- Semantic digest: `{semantic_digest}`
- Final report review: `not_requested`
- `system_v1_complete=false`
- `sample_quality_ready=false`
- `p2_ready=false`
- `release_ready=false`

## Source truth

- 2025 annual official disclosure: `{ANNUAL_EVIDENCE_ID}`; PDF and processed text hashes verified; pages 15–16 resolved.
- 2025 interim official disclosure: `{INTERIM_EVIDENCE_ID}`; PDF and processed text hashes verified; page 9 resolved.

## Issue disposition

The four historical high issues are not recorded as resolved. They are reclassified into current nonblocking limitations because their unknown values are visible and unused. Room/liquid partial overlap is confirmed while its amount remains unknown. The cabinet/liquid relationship remains unknown in both directions.

## Replay

`{EXACT_REPLAY_COMMAND}`
"""


def _build_semantic_objects(
    verified_sources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    provenance_rows = build_provenance_rows(verified_sources)
    facts = build_disclosed_facts()
    limitations = build_limitations()
    issues = build_open_todos()
    status = derive_status(issues)
    gates = build_quality_gates(issues, status)
    issue_changes = build_issue_change_rows(issues)
    research_pack = build_research_pack(facts, issues, status)
    exposure = build_segment_exposure()
    backflow = build_backflow_decision()
    state = build_state(facts, issues, gates, status)
    semantic_payload = {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "as_of_date": AS_OF_DATE,
        "sources": [
            {
                "evidence_id": row["evidence_id"],
                "source_path": row["source_path"],
                "hash_scope": row["hash_scope"],
                "observed_sha256": row["observed_sha256"],
            }
            for row in provenance_rows
        ],
        "facts": facts,
        "limitations": limitations,
        "issues": issues,
        "issue_changes": issue_changes,
        "quality_gates": gates,
        "status": status,
        "research_pack": research_pack,
        "segment_exposure": exposure,
        "backflow_decision": backflow,
        "artifact_specs": ARTIFACT_SPECS,
    }
    semantic_digest = canonical_sha256(semantic_payload)
    return {
        "provenance_rows": provenance_rows,
        "facts": facts,
        "limitations": limitations,
        "issues": issues,
        "status": status,
        "gates": gates,
        "issue_changes": issue_changes,
        "research_pack": research_pack,
        "exposure": exposure,
        "backflow": backflow,
        "state": state,
        "semantic_digest": semantic_digest,
    }


def _base_rendered_files(objects: Mapping[str, Any]) -> dict[str, str]:
    facts_document = {
        "schema_version": 1,
        "artifact_type": "r5_v1_policy_refresh_disclosed_facts",
        "workflow_id": WORKFLOW_ID,
        "as_of_date": AS_OF_DATE,
        "source_policy": "hash_verified_official_disclosures_only",
        "facts": objects["facts"],
    }
    return {
        "workflow_state.yaml": _yaml_text(objects["state"]),
        "run_log.md": render_run_log(
            objects["status"], objects["semantic_digest"]
        ),
        "open_todos.csv": _csv_text(TODO_FIELDS, objects["issues"]),
        "quality_gate_report.md": render_quality_report(
            objects["gates"], objects["status"]
        ),
        "workflow_readout.md": render_readout(
            objects["status"], objects["semantic_digest"]
        ),
        "inputs/input_provenance.csv": _csv_text(
            PROVENANCE_FIELDS, objects["provenance_rows"]
        ),
        "research/disclosed_facts.yaml": _yaml_text(facts_document),
        "research/limitations.yaml": _yaml_text(objects["limitations"]),
        "research/issue_change_log.csv": _csv_text(
            ISSUE_CHANGE_FIELDS, objects["issue_changes"]
        ),
        "research/stock_research_pack.yaml": _yaml_text(
            objects["research_pack"]
        ),
        "research/segment_exposure.yaml": _yaml_text(objects["exposure"]),
        "research/stock_report_draft.md": render_report(objects["status"]),
        "research/backflow_decision.yaml": _yaml_text(objects["backflow"]),
    }


def _hash_rows(
    output_dir: Path,
    paths: Sequence[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relative in paths:
        path = output_dir / relative
        if not path.is_file():
            raise ReplayContractError(f"generated artifact missing: {relative}")
        rows.append(
            {
                "path": f"{TARGET_RUN_REL.as_posix()}/{relative}",
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "hash_scope": "file_bytes",
                "source_trace": "hash_verified_official_inputs",
            }
        )
    return rows


def _compare_hashes(
    output_dir: Path,
    paths: Sequence[str],
) -> dict[str, str]:
    return {relative: sha256_file(output_dir / relative) for relative in paths}


def _tree_digest(rows: Mapping[str, str] | Sequence[Mapping[str, Any]]) -> str:
    if isinstance(rows, Mapping):
        payload = [{"path": key, "sha256": rows[key]} for key in sorted(rows)]
    else:
        payload = sorted(
            (
                {"path": row["path"], "sha256": row["sha256"]}
                for row in rows
            ),
            key=lambda row: row["path"],
        )
    return canonical_sha256(payload)


def _write_core_pass(
    output_dir: Path,
    objects: Mapping[str, Any],
) -> dict[str, str]:
    for relative, content in _base_rendered_files(objects).items():
        _write_text_if_changed(output_dir / relative, content)

    hash_rows = _hash_rows(output_dir, BASE_HASH_PATHS)
    _write_text_if_changed(
        output_dir / "validation/artifact_hashes.csv",
        _csv_text(HASH_FIELDS, hash_rows),
    )
    generated_digest = _tree_digest(
        _compare_hashes(
            output_dir,
            BASE_HASH_PATHS + ("validation/artifact_hashes.csv",),
        )
    )
    receipt = {
        "schema_version": 1,
        "artifact_type": "r5_v1_policy_refresh_replay_receipt",
        "workflow_id": WORKFLOW_ID,
        "as_of_date": AS_OF_DATE,
        "mode": "offline",
        "network_access": False,
        "historical_workflow_reads": False,
        "raw_overwrite": False,
        "manifest_path": MANIFEST_REL.as_posix(),
        "evidence_ids": [ANNUAL_EVIDENCE_ID, INTERIM_EVIDENCE_ID],
        "input_file_count": 4,
        "printed_pages_verified": [9, 15, 16],
        "derived_status": objects["status"],
        "semantic_digest": objects["semantic_digest"],
        "generated_artifact_digest": generated_digest,
        "canonical_command": EXACT_REPLAY_COMMAND,
    }
    _write_text_if_changed(
        output_dir / "validation/replay_receipt.yaml",
        _yaml_text(receipt),
    )
    return _compare_hashes(output_dir, REPLAY_COMPARE_PATHS)


def _write_idempotence_report(
    output_dir: Path,
    first: Mapping[str, str],
    second: Mapping[str, str],
    semantic_digest: str,
) -> dict[str, Any]:
    drift = [
        {
            "path": relative,
            "first_sha256": first.get(relative),
            "second_sha256": second.get(relative),
        }
        for relative in sorted(set(first) | set(second))
        if first.get(relative) != second.get(relative)
    ]
    report = {
        "schema_version": 1,
        "artifact_type": "r5_v1_policy_refresh_idempotence_report",
        "workflow_id": WORKFLOW_ID,
        "as_of_date": AS_OF_DATE,
        "pass_count": 2,
        "compare_path_count": len(REPLAY_COMPARE_PATHS),
        "first_pass_tree_sha256": _tree_digest(first),
        "second_pass_tree_sha256": _tree_digest(second),
        "semantic_digest": semantic_digest,
        "first_semantic_digest": semantic_digest,
        "second_semantic_digest": semantic_digest,
        "semantic_drift_count": 0,
        "allowed_normalizations": [],
        "byte_drift_count": len(drift),
        "byte_drift": drift,
        "decision": "pass" if not drift else "fail",
    }
    _write_text_if_changed(
        output_dir / "validation/idempotence_report.yaml",
        _yaml_text(report),
    )
    if drift:
        raise ReplayContractError(
            "two-pass materialization drift: "
            + ", ".join(item["path"] for item in drift)
        )
    return report


def _write_artifact_manifest(output_dir: Path) -> None:
    rows: list[dict[str, Any]] = []
    for spec in ARTIFACT_SPECS:
        artifact_id, artifact_type, relative, skill, stage, required, status, notes = spec
        path = output_dir / relative
        if not path.is_file() and relative != "artifact_manifest.csv":
            raise ReplayContractError(f"artifact missing before manifest: {relative}")
        if relative == "artifact_manifest.csv":
            hash_note = (
                "self-manifest; recursive self-hash intentionally omitted"
            )
        else:
            hash_note = (
                f"sha256={sha256_file(path)}; bytes={path.stat().st_size}"
            )
        rows.append(
            {
                "artifact_id": artifact_id,
                "artifact_type": artifact_type,
                "path": f"{TARGET_RUN_REL.as_posix()}/{relative}",
                "created_by_skill": skill,
                "stage": stage,
                "required": required,
                "exists": True,
                "status": status,
                "notes": f"{notes}; {hash_note}",
            }
        )
    _write_text_if_changed(
        output_dir / "artifact_manifest.csv",
        _csv_text(MANIFEST_FIELDS, rows),
    )


def _resolve_output(repo_root: Path, output_dir: Path) -> Path:
    root = repo_root.resolve()
    output = output_dir if output_dir.is_absolute() else root / output_dir
    output = output.resolve()
    if output == root:
        raise ReplayContractError("output directory cannot be the repository root")
    try:
        relative = output.relative_to(root)
    except ValueError:
        temp_root = Path(tempfile.gettempdir()).resolve()
        try:
            output.relative_to(temp_root)
        except ValueError as exc:
            raise ReplayContractError(
                "out-of-repository output is allowed only under the system "
                "temporary directory"
            ) from exc
        return output
    if relative.as_posix() != TARGET_RUN_REL.as_posix():
        raise ReplayContractError(
            "in-repository output must be the canonical authorized run path: "
            f"{TARGET_RUN_REL.as_posix()}"
        )
    return output


def _reject_unexpected_existing_files(output_dir: Path) -> None:
    if not output_dir.exists():
        return
    expected = set(EXPECTED_ARTIFACT_PATHS)
    observed = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    unexpected = sorted(observed - expected)
    if unexpected:
        raise ReplayContractError(
            "output contains unexpected files; no cleanup attempted: "
            + ", ".join(unexpected)
        )


def _assert_exact_tree(output_dir: Path) -> None:
    observed = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    expected = set(EXPECTED_ARTIFACT_PATHS)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise ReplayContractError(
            f"output tree mismatch; missing={missing}; extra={extra}"
        )


def materialize_refresh(repo_root: Path, output_dir: Path) -> dict[str, Any]:
    """Verify fixed inputs and materialize one deterministic refresh run."""

    root = repo_root.resolve()
    output = _resolve_output(root, output_dir)
    _reject_unexpected_existing_files(output)
    verified = verify_official_sources(root)
    objects = _build_semantic_objects(verified)
    output.mkdir(parents=True, exist_ok=True)

    first = _write_core_pass(output, objects)
    second = _write_core_pass(output, objects)
    idempotence = _write_idempotence_report(
        output,
        first,
        second,
        objects["semantic_digest"],
    )
    _write_artifact_manifest(output)
    _assert_exact_tree(output)

    complete_hashes = _compare_hashes(output, EXPECTED_ARTIFACT_PATHS)
    return {
        "workflow_id": WORKFLOW_ID,
        "status": objects["status"],
        "semantic_digest": objects["semantic_digest"],
        "tree_digest": _tree_digest(complete_hashes),
        "artifact_count": len(complete_hashes),
        "byte_drift_count": idempotence["byte_drift_count"],
        "network_access": False,
        "historical_workflow_reads": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Materialize the offline 002837 V1 policy refresh."
    )
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    try:
        result = materialize_refresh(
            Path(args.repo_root),
            Path(args.output_dir),
        )
    except ReplayContractError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(_yaml_text(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
