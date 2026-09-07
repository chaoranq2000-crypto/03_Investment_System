from __future__ import annotations

import hashlib
import io
import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from itertools import count
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Iterable

import pytest
import yaml


GOVERNANCE_BASELINE = "457c7ee0ed3db7565320709f0b8b2cdeedf05aff"
GOVERNANCE_MANIFEST = "docs/meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml"


@dataclass(frozen=True)
class HistoricalBlob:
    oid: str
    object_type: str
    byte_count: int
    payload: bytes
    sha256: str


class HistoricalGit:
    """Cache verified immutable objects, never live worktree state or mutable refs."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._commits: set[str] = set()
        self._blobs: dict[tuple[str, str], HistoricalBlob] = {}

    def _commit(self, commit: str) -> None:
        assert re.fullmatch(r"[0-9a-f]{40}", commit), "fixed full commit required"
        if commit not in self._commits:
            resolved = subprocess.check_output(
                ["git", "-C", str(self.root), "rev-parse", "--verify", f"{commit}^{{commit}}"],
                text=True, encoding="utf-8",
            ).strip()
            assert resolved == commit, "historical identity must be a commit object"
            self._commits.add(commit)

    @staticmethod
    def _path(source_path: str) -> None:
        pure = PurePosixPath(source_path)
        assert source_path and source_path == pure.as_posix(), "non-canonical historical path"
        assert not pure.is_absolute() and not PureWindowsPath(source_path).drive, "absolute historical path"
        assert pure.parts and ".." not in pure.parts and pure.parts[0] != ".git", "forbidden historical path"
        assert not any(token in source_path for token in "\\\0\r\n*?[]{}"), "non-literal historical path"

    def blobs(self, commit: str, source_paths: Iterable[str]) -> dict[str, HistoricalBlob]:
        paths = list(dict.fromkeys(source_paths))
        for source_path in paths:
            self._path(source_path)
        self._commit(commit)
        missing = [path for path in paths if (commit, path) not in self._blobs]
        if missing:
            specs = [f"{commit}:{path}" for path in missing]
            output = subprocess.check_output(
                ["git", "-C", str(self.root), "cat-file", "--batch"],
                input=("\n".join(specs) + "\n").encode("utf-8"),
            )
            stream = io.BytesIO(output)
            verified: dict[tuple[str, str], HistoricalBlob] = {}
            for path in missing:
                header = stream.readline().rstrip(b"\n").split()
                assert len(header) == 3 and header[1] == b"blob", f"not a recoverable Git blob: {path}"
                assert re.fullmatch(rb"[0-9a-f]{40}", header[0]), f"invalid Git object ID: {path}"
                assert header[2].isdigit(), f"invalid Git blob size: {path}"
                size = int(header[2])
                payload = stream.read(size)
                assert len(payload) == size and stream.read(1) == b"\n", f"truncated Git blob: {path}"
                oid = hashlib.sha1(
                    f"blob {len(payload)}\0".encode("ascii") + payload,
                    usedforsecurity=False,
                ).hexdigest()
                assert oid == header[0].decode("ascii"), f"Git blob OID mismatch: {path}"
                verified[commit, path] = HistoricalBlob(
                    oid=oid, object_type="blob", byte_count=size, payload=payload,
                    sha256=hashlib.sha256(payload).hexdigest(),
                )
            assert stream.read() == b"", "unexpected trailing Git batch data"
            # A malformed batch must not leave partially verified objects in the cache.
            self._blobs.update(verified)
        return {path: self._blobs[commit, path] for path in paths}

    def blob(self, commit: str, source_path: str) -> HistoricalBlob:
        return self.blobs(commit, [source_path])[source_path]

    def prefetch(self, specs: Iterable[tuple[str, str]]) -> None:
        by_commit: dict[str, list[str]] = {}
        for commit, source_path in specs:
            by_commit.setdefault(commit, []).append(source_path)
        for commit, source_paths in by_commit.items():
            self.blobs(commit, source_paths)

    @lru_cache(maxsize=None)
    def text(self, commit: str, source_path: str, errors: str = "strict") -> str:
        return self.blob(commit, source_path).payload.decode("utf-8", errors=errors)


GIT_HISTORY = HistoricalGit(Path(__file__).resolve().parents[1])


@lru_cache(maxsize=1)
def governance_paths() -> frozenset[str]:
    GIT_HISTORY._commit(GOVERNANCE_BASELINE)
    root = Path(__file__).resolve().parents[1]
    output = subprocess.check_output(
        ["git", "-C", str(root), "ls-tree", "-r", "--name-only", "-z", GOVERNANCE_BASELINE]
    )
    return frozenset(path.decode("utf-8") for path in output.split(b"\0") if path)


@lru_cache(maxsize=None)
def governance_blob(source_path: str) -> bytes:
    """Read a published governance receipt; never select a current workflow."""
    return GIT_HISTORY.blob(GOVERNANCE_BASELINE, source_path).payload


def governance_text(source_path: str) -> str:
    return GIT_HISTORY.text(GOVERNANCE_BASELINE, source_path)


@lru_cache(maxsize=1)
def governance_snapshot() -> dict[str, Any]:
    data = yaml.safe_load(governance_text(GOVERNANCE_MANIFEST))
    assert data["schema_version"] == "docs_reports_retention_dependency_manifest_v1"
    return data


@lru_cache(maxsize=1)
def prefetch_governance_recovery() -> None:
    manifest = governance_snapshot()
    items = [item for group in manifest["candidate_groups"] for item in group["items"]]
    recovery = {item["path"]: item["recovery_basis"]["commit"] for item in items}
    specs = list((commit, path) for path, commit in recovery.items())
    sources = {
        path
        for item in items + manifest["legacy_route_surfaces"] + manifest["legacy_route_writers"]
        for reference in item["inbound_references"]
        for path in (reference["source_path"], reference.get("via_source_path"))
        if path
    }
    for source in sources:
        commit = (
            GOVERNANCE_BASELINE if source in governance_paths()
            else recovery.get(source, manifest["audit"]["baseline_commit"])
        )
        specs.append((commit, source))
    GIT_HISTORY.prefetch(specs)


@lru_cache(maxsize=1)
def governance_text_index() -> dict[str, str]:
    suffixes = {".py", ".md", ".yaml", ".yml", ".toml", ".json", ".csv", ".txt", ".ps1", ".js", ".ts", ".html", ".css"}
    paths = sorted(
        path for path in governance_paths()
        if path != GOVERNANCE_MANIFEST and PurePosixPath(path).suffix in suffixes
    )
    GIT_HISTORY.blobs(GOVERNANCE_BASELINE, paths)
    texts = {}
    for path in paths:
        try:
            texts[path] = governance_text(path)
        except UnicodeDecodeError:
            continue
    return texts


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
