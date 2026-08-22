from __future__ import annotations

import hashlib
import subprocess
from itertools import count
from pathlib import Path, PurePosixPath
from typing import Any, Callable

import pytest
import yaml


HISTORICAL_BASELINE = "312adc73821706b0b7ca6aa00e80ee608bd10b32"
SOURCE_QUEUE = Path(
    "reports/p1_6/r5_night_shift/r5_overnight_02_20260720/next_night_queue.yaml"
)
SOURCE_QUEUE_BLOB_OID = "3e84cc0eb380dd771807f484370a262d8d03cd49"
SOURCE_QUEUE_BYTES = 115020
SOURCE_QUEUE_SHA256 = "dc2d6d6bb91b7ff326d3985d96f8eb8956a43710c61230eb06e6144e490e8ea1"


def _historical_queue_blob(repo_root: Path) -> bytes:
    object_name = f"{HISTORICAL_BASELINE}:{SOURCE_QUEUE.as_posix()}"
    oid = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", object_name],
        text=True,
        encoding="utf-8",
    ).strip()
    assert oid == SOURCE_QUEUE_BLOB_OID
    size = int(
        subprocess.check_output(
            ["git", "-C", str(repo_root), "cat-file", "-s", object_name],
            text=True,
            encoding="utf-8",
        ).strip()
    )
    assert size == SOURCE_QUEUE_BYTES
    payload = subprocess.check_output(
        ["git", "-C", str(repo_root), "cat-file", "blob", object_name]
    )
    assert len(payload) == SOURCE_QUEUE_BYTES
    assert hashlib.sha256(payload).hexdigest() == SOURCE_QUEUE_SHA256
    return payload


@pytest.fixture(scope="session")
def historical_blob_bytes() -> Callable[[str], bytes]:
    repo_root = Path(__file__).resolve().parents[1]
    resolved_commit = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", f"{HISTORICAL_BASELINE}^{{commit}}"],
        text=True,
        encoding="utf-8",
    ).strip()
    assert resolved_commit == HISTORICAL_BASELINE
    cache: dict[str, bytes] = {}

    def read(source_path: str) -> bytes:
        if source_path in cache:
            return cache[source_path]
        pure = PurePosixPath(source_path)
        assert source_path == pure.as_posix(), f"non-canonical historical path: {source_path}"
        assert not pure.is_absolute(), f"absolute historical path: {source_path}"
        assert ".." not in pure.parts, f"escaping historical path: {source_path}"
        assert pure.parts and pure.parts[0] != ".git", f"forbidden historical path: {source_path}"
        object_name = f"{HISTORICAL_BASELINE}:{source_path}"
        subprocess.run(
            ["git", "-C", str(repo_root), "cat-file", "-e", object_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        oid = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", object_name],
            text=True,
            encoding="utf-8",
        ).strip()
        size = int(
            subprocess.check_output(
                ["git", "-C", str(repo_root), "cat-file", "-s", object_name],
                text=True,
                encoding="utf-8",
            ).strip()
        )
        payload = subprocess.check_output(
            ["git", "-C", str(repo_root), "cat-file", "blob", object_name]
        )
        assert len(payload) == size
        expected_oid = hashlib.sha1(
            f"blob {len(payload)}\0".encode("ascii") + payload,
            usedforsecurity=False,
        ).hexdigest()
        assert oid == expected_oid
        cache[source_path] = payload
        return payload

    return read


@pytest.fixture
def historical_blob_file(
    tmp_path: Path,
    historical_blob_bytes: Callable[[str], bytes],
) -> Callable[[str, str], Path]:
    root = (tmp_path / "fixed_baseline_inputs").resolve()

    def materialize(source_path: str, local_relative: str) -> Path:
        local_path = Path(local_relative)
        assert not local_path.is_absolute()
        assert ".." not in local_path.parts
        assert "wf_20260703_stock_first_002837_invic" not in local_path.as_posix()
        target = (root / local_path).resolve()
        assert target.is_relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = historical_blob_bytes(source_path)
        if target.exists():
            assert target.read_bytes() == payload
        else:
            target.write_bytes(payload)
        return target

    return materialize


@pytest.fixture
def night03_decision_factory(tmp_path: Path) -> Callable[..., tuple[Path, dict[str, Any], Path, Path]]:
    repo_root = Path(__file__).resolve().parents[1]
    root = tmp_path / "repo"
    target = root / SOURCE_QUEUE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_historical_queue_blob(repo_root))
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
