from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs/meta/DOCS_REPORTS_RETENTION_DEPENDENCY_MANIFEST.yaml"


def load_manifest() -> dict[str, Any]:
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def ready_items(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for group in manifest["candidate_groups"]
        if group["status"] == "READY_FOR_MANUAL_DELETE"
        for item in group["items"]
    ]


def test_manifest_has_one_authority_chain_and_explicit_status_vocabulary() -> None:
    manifest = load_manifest()

    assert manifest["schema_version"] == "docs_reports_retention_dependency_manifest_v1"
    assert manifest["audit"]["baseline_commit"] == "33ff9fe05704259d205fc26e97505725d3f872f1"
    assert manifest["authority"] == {
        "project_rules": "AGENTS.md",
        "research_workflow": "docs/workflows/RESEARCH_WORKFLOW.md",
        "document_ownership": "docs/meta/DOC_OWNERSHIP_MATRIX.md",
        "current_run_pointer": "config/r5_readout_canonical_index.yaml.current_runs",
    }
    assert set(manifest["status_definitions"]) == {
        "KEEP_ACTIVE",
        "KEEP_EVIDENCE",
        "LEGACY_BOUND",
        "READY_FOR_MANUAL_DELETE",
        "USER_DECISION",
    }
    assert manifest["deletion_control"]["codex_delete_authorized"] is False
    assert manifest["deletion_control"]["directories_authorized"] is False


def test_ready_paths_are_exact_unique_and_git_recoverable() -> None:
    manifest = load_manifest()
    items = ready_items(manifest)
    paths = [item["path"] for item in items]

    assert len(paths) == len(set(paths))
    assert paths
    for group in manifest["candidate_groups"]:
        group_paths = [item["path"] for item in group["items"]]
        assert group_paths == sorted(group_paths)
    for item in items:
        path = item["path"]
        pure = PurePosixPath(path)
        assert path == pure.as_posix()
        assert not pure.is_absolute()
        assert ".." not in pure.parts
        assert not any(token in path for token in ("*", "?", "[", "]", "{", "}"))
        recovery = item["recovery_basis"]
        assert recovery["kind"] == "git_blob"
        recovery_commit = recovery["commit"]
        object_name = f"{recovery_commit}:{path}"
        oid = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", object_name],
            text=True,
            encoding="utf-8",
        ).strip()
        size = int(
            subprocess.check_output(
                ["git", "-C", str(ROOT), "cat-file", "-s", object_name],
                text=True,
                encoding="utf-8",
            ).strip()
        )
        payload = subprocess.check_output(
            ["git", "-C", str(ROOT), "cat-file", "blob", object_name]
        )
        calculated_oid = hashlib.sha1(
            f"blob {len(payload)}\0".encode("ascii") + payload,
            usedforsecurity=False,
        ).hexdigest()
        assert oid == item["blob_oid"] == calculated_oid
        assert size == item["byte_count"] == len(payload)
        assert recovery == {
            "kind": "git_blob",
            "commit": recovery_commit,
        }


def test_ready_aggregate_is_derived_from_exact_items() -> None:
    manifest = load_manifest()
    items = ready_items(manifest)
    expected = {
        "file_count": len(items),
        "byte_count": sum(item["byte_count"] for item in items),
    }

    assert manifest["summary"]["READY_FOR_MANUAL_DELETE_ALL_PHASES"] == expected
    for group in manifest["candidate_groups"]:
        if group["status"] != "READY_FOR_MANUAL_DELETE":
            continue
        assert group["aggregate"] == {
            "file_count": len(group["items"]),
            "byte_count": sum(item["byte_count"] for item in group["items"]),
        }


def test_protected_current_and_evidence_prefixes_are_disjoint_from_ready() -> None:
    manifest = load_manifest()
    ready = {item["path"] for item in ready_items(manifest)}
    protected = manifest["protected_paths"]

    for entry in protected:
        if "path" in entry:
            assert entry["path"] not in ready
        if "path_prefix" in entry:
            prefix = entry["path_prefix"].rstrip("/") + "/"
            assert not any(path.startswith(prefix) for path in ready)

    assert all(entry["status"] in {"KEEP_ACTIVE", "KEEP_EVIDENCE"} for entry in protected)
