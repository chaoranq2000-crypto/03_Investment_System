"""Deterministic Reader-generation lock helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.report.r5_bundle10r_contracts import sha256_file


def aggregate_artifacts(records: Iterable[Mapping[str, str]]) -> str:
    material = "".join(f"{item['path']}\0{item['sha256']}\n" for item in sorted(records, key=lambda x: x["path"]))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def build_reader_generation_lock(
    repo_root: str | Path,
    artifact_paths: Iterable[str],
    *,
    model_generation_id: str,
    model_aggregate_sha256: str,
    evidence_generation_id: str,
    created_at: str,
    human_review_status: str,
    generation_label: str = "r5_bundle10r_reader",
    generation_id_prefix: str = "reader_gen_r5_bundle10r",
) -> dict[str, Any]:
    root = Path(repo_root)
    records: list[dict[str, str]] = []
    missing: list[str] = []
    for rel in sorted(set(artifact_paths)):
        path = root / rel
        if not path.is_file():
            missing.append(rel)
            continue
        records.append({"path": rel, "sha256": sha256_file(path)})
    aggregate = aggregate_artifacts(records)
    return {
        "schema_version": 1,
        "generation_label": generation_label,
        "generation_id": f"{generation_id_prefix}_{aggregate[:16]}",
        "created_at": created_at,
        "input_model_generation_id": model_generation_id,
        "input_model_aggregate_sha256": model_aggregate_sha256,
        "input_evidence_generation_id": evidence_generation_id,
        "human_review_status": human_review_status,
        "artifact_count": len(records),
        "missing_artifact_count": len(missing),
        "missing_artifacts": missing,
        "artifacts": records,
        "aggregate_sha256": aggregate,
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "downstream_consumers": ["R5_HUMAN_REVIEW_FINALIZATION"],
    }
