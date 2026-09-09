from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from conftest import GOVERNANCE_BASELINE, GOVERNANCE_MANIFEST, HistoricalGit


COMMIT_A = "1" * 40
COMMIT_B = "2" * 40


def batch_blob(payload: bytes) -> bytes:
    oid = hashlib.sha1(
        f"blob {len(payload)}\0".encode("ascii") + payload, usedforsecurity=False,
    ).hexdigest()
    return f"{oid} blob {len(payload)}\n".encode("ascii") + payload + b"\n"


def test_real_fixed_history_remains_recoverable_without_materializing_files():
    history = HistoricalGit(Path(__file__).resolve().parents[1])
    blob = history.blob(GOVERNANCE_BASELINE, GOVERNANCE_MANIFEST)
    assert blob.object_type == "blob"
    assert blob.byte_count == len(blob.payload)
    assert blob.sha256 == hashlib.sha256(blob.payload).hexdigest()
    assert b"docs_reports_retention_dependency_manifest_v1" in blob.payload


@pytest.mark.parametrize("commit", ["HEAD", "main", COMMIT_A[:12], COMMIT_A + ":file.txt"])
def test_reader_rejects_mutable_or_noncommit_specs_before_git(monkeypatch, tmp_path, commit):
    def unexpected_git(*args, **kwargs):
        pytest.fail("unsafe identity reached Git")

    monkeypatch.setattr("conftest.subprocess.check_output", unexpected_git)
    with pytest.raises(AssertionError, match="fixed full commit"):
        HistoricalGit(tmp_path).blob(commit, "file.txt")


@pytest.mark.parametrize("path", [
    "", ".", "../outside.txt", "/outside.txt", "C:/outside.txt", "C:outside.txt",
    "dir//file.txt", "dir/./file.txt", ".git/config", "dir\\file.txt",
    "dir/*.txt", "file.txt\nHEAD:file.txt", "file.txt\0suffix",
])
def test_reader_rejects_nonliteral_paths_before_git(monkeypatch, tmp_path, path):
    def unexpected_git(*args, **kwargs):
        pytest.fail("unsafe path reached Git")

    monkeypatch.setattr("conftest.subprocess.check_output", unexpected_git)
    with pytest.raises(AssertionError):
        HistoricalGit(tmp_path).blob(COMMIT_A, path)


def test_cache_separates_commits_and_deduplicates_only_immutable_objects(monkeypatch, tmp_path):
    batches = []
    commits = []

    def git_output(command, **kwargs):
        if "rev-parse" in command:
            commit = command[-1].removesuffix("^{commit}")
            commits.append(commit)
            return commit + "\n"
        specs = kwargs["input"].decode("utf-8").splitlines()
        batches.append(specs)
        return b"".join(batch_blob(spec.encode("utf-8")) for spec in specs)

    monkeypatch.setattr("conftest.subprocess.check_output", git_output)
    history = HistoricalGit(tmp_path)
    first = history.blobs(COMMIT_A, ["a.txt", "b.txt", "a.txt"])
    assert history.blob(COMMIT_A, "a.txt") is first["a.txt"]
    second = history.blob(COMMIT_B, "a.txt")
    assert second.payload != first["a.txt"].payload
    assert history.text(COMMIT_A, "a.txt") == f"{COMMIT_A}:a.txt"
    assert batches == [
        [f"{COMMIT_A}:a.txt", f"{COMMIT_A}:b.txt"], [f"{COMMIT_B}:a.txt"],
    ]
    assert commits == [COMMIT_A, COMMIT_B]


@pytest.mark.parametrize("bad_record", [
    b"missing:path missing\n",
    b"0" * 40 + b" tree 0\n\n",
    b"0" * 40 + b" blob -1\n",
    b"0" * 40 + b" blob 5\nshort\n",
    batch_blob(b"second")[:-2],
    batch_blob(b"second") + b"unexpected trailing bytes",
])
def test_invalid_batch_fails_closed_without_partial_cache(monkeypatch, tmp_path, bad_record):
    batches = []
    broken = True

    def git_output(command, **kwargs):
        if "rev-parse" in command:
            return COMMIT_A + "\n"
        specs = kwargs["input"].decode("utf-8").splitlines()
        batches.append(specs)
        if broken:
            return batch_blob(b"first") + bad_record
        return batch_blob(b"first") + batch_blob(b"second")

    monkeypatch.setattr("conftest.subprocess.check_output", git_output)
    history = HistoricalGit(tmp_path)
    with pytest.raises(AssertionError):
        history.blobs(COMMIT_A, ["a.txt", "b.txt"])
    broken = False
    recovered = history.blobs(COMMIT_A, ["a.txt", "b.txt"])
    assert recovered["a.txt"].payload == b"first"
    assert recovered["b.txt"].payload == b"second"
    assert batches == [[f"{COMMIT_A}:a.txt", f"{COMMIT_A}:b.txt"]] * 2


def test_full_hash_must_resolve_to_itself_as_a_commit(monkeypatch, tmp_path):
    calls = []

    def git_output(command, **kwargs):
        calls.append(command)
        return COMMIT_B + "\n"

    monkeypatch.setattr("conftest.subprocess.check_output", git_output)
    with pytest.raises(AssertionError, match="must be a commit object"):
        HistoricalGit(tmp_path).blob(COMMIT_A, "a.txt")
    assert len(calls) == 1 and "rev-parse" in calls[0]
