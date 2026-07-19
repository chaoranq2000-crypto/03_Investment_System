from __future__ import annotations

import hashlib
from itertools import count
from pathlib import Path
from typing import Any, Callable

import pytest
import yaml

from src.maintenance.night_shift.night03 import SOURCE_QUEUE


@pytest.fixture
def night03_decision_factory(tmp_path: Path) -> Callable[..., tuple[Path, dict[str, Any], Path, Path]]:
    repo_root = Path(__file__).resolve().parents[1]
    root = tmp_path / "repo"
    source = repo_root / SOURCE_QUEUE
    target = root / SOURCE_QUEUE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    queue = yaml.safe_load(target.read_text(encoding="utf-8"))
    tasks = queue["tasks"]
    work_type_by_kind = {
        "evidence_acceptance": "evidence_required",
        "analysis_acceptance": "analysis_required",
        "human_exact_hash": "human_gate",
        "pointer_contract_approval": "engineering_local",
    }
    serial = count(1)

    def factory(
        kind: str,
        review_packet: dict[str, Any],
        *,
        candidate: dict[str, Any] | None = None,
        reviewer: str = "Q Reviewer",
        reviewer_authority: str | None = None,
        reviewed_at: str = "2026-07-19T12:00:00+00:00",
        decision: str = "approved",
    ) -> tuple[Path, dict[str, Any], Path, Path]:
        index = next(serial)
        work_type = work_type_by_kind[kind]
        occurrence = next(task for task in tasks if task["work_type"] == work_type)
        candidate_path = root / f"decision_inputs/candidate_{index}.yaml"
        review_path = root / f"decision_inputs/review_{index}.yaml"
        candidate_path.parent.mkdir(parents=True, exist_ok=True)
        candidate_path.write_text(
            yaml.safe_dump(candidate or {"candidate_id": f"candidate_{index}"}, sort_keys=True),
            encoding="utf-8",
        )
        review_path.write_text(
            yaml.safe_dump(review_packet, sort_keys=True),
            encoding="utf-8",
        )
        candidate_hash = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
        review_hash = hashlib.sha256(review_path.read_bytes()).hexdigest()
        authorities = {
            "evidence_acceptance": "evidence_reviewer",
            "analysis_acceptance": "research_reviewer",
            "human_exact_hash": "human_gate_reviewer",
            "pointer_contract_approval": "engineering_contract_reviewer",
        }
        manifest = {
            "schema_version": "r5_night03_external_decision_manifest_v1",
            "source_queue_path": SOURCE_QUEUE.as_posix(),
            "source_queue_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "created_by": "Q Operator",
            "created_at": "2026-07-19T12:05:00+00:00",
            "decisions": [
                {
                    "occurrence_id": occurrence["id"],
                    "decision_kind": kind,
                    "decision": decision,
                    "candidate_artifact_path": candidate_path.relative_to(root).as_posix(),
                    "candidate_artifact_sha256": candidate_hash,
                    "review_packet_path": review_path.relative_to(root).as_posix(),
                    "review_packet_sha256": review_hash,
                    "reviewer": reviewer,
                    "reviewer_authority": reviewer_authority or authorities[kind],
                    "reviewed_at": reviewed_at,
                    "notes": [],
                }
            ],
            "machine_must_not_populate_reviewer_fields": True,
        }
        return root, manifest, candidate_path, review_path

    return factory
