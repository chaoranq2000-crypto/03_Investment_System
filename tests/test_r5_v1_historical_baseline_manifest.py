from __future__ import annotations

import copy
import hashlib
import importlib.util
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "manage_r5_v1_historical_cleanup.py"


def load_tool():
    spec = importlib.util.spec_from_file_location(
        "manage_r5_v1_historical_cleanup", TOOL_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tool():
    return load_tool()


@pytest.fixture(scope="module")
def manifest(tool):
    return tool.load_yaml(ROOT / tool.BASELINE_MANIFEST_REL)


def test_frozen_contract_authority_and_a6_inventory_are_exact(tool) -> None:
    contract = tool.verify_contract(ROOT)
    assert contract == {
        "path": tool.CONTRACT_REL.as_posix(),
        "canonical_sha256": tool.EXPECTED_CONTRACT_SHA256,
        "status": "frozen",
        "source_baseline": tool.PACKAGE_SOURCE_BASELINE,
    }
    assert tool.verify_root_agents(ROOT) == {
        "path": "AGENTS.md",
        "blob_oid": tool.EXPECTED_AGENTS_BLOB_OID,
        "byte_count": tool.EXPECTED_AGENTS_BYTE_COUNT,
        "sha256": tool.EXPECTED_AGENTS_SHA256,
    }
    authority = tool.parse_authority(ROOT)
    assert {key: len(value) for key, value in authority.items()} == {
        "a1": 120,
        "a2": 13,
        "a3": 44,
        "a4": 35,
        "a5": 27,
        "a7": 3,
    }
    assert authority["a1"] & authority["a5"] == tool.EXPECTED_A1_A5_OVERLAP
    assert all(
        not (authority[left] & authority[right])
        for left in authority
        for right in authority
        if left < right and {left, right} != {"a1", "a5"}
    )

    a6 = tool.expand_a6(ROOT)
    vector_bytes, vector_sha256 = tool.path_vector(a6)
    assert len(a6) == 116
    assert vector_bytes == 8065
    assert (
        vector_sha256
        == "6c667b2aa0db007d5e89baf5b7bae837fd62249be3d85613f16aba3d14d32e6a"
    )


def test_baseline_manifest_is_exact_sorted_and_durable(tool, manifest) -> None:
    authority = tool.parse_authority(ROOT)
    a6 = tool.expand_a6(ROOT)
    inventory = tool.build_candidate_inventory(ROOT, authority, a6)
    rows = manifest["files"]
    paths = [row["path"] for row in rows]

    assert manifest["schema_version"] == "r5_v1_historical_baseline_manifest_v1"
    assert manifest["source_snapshot"] == tool.HISTORICAL_SOURCE_SNAPSHOT
    assert manifest["durable_restore_refs"] == {
        "night_source": tool.NIGHT_SOURCE,
        "engineering_source": tool.ENGINEERING_SOURCE,
    }
    assert paths == sorted(paths)
    assert len(paths) == len(set(paths))
    assert set(paths) == set(inventory)
    assert manifest["aggregate"] == tool._aggregate(rows)
    assert all(row["wave"] == inventory[row["path"]] for row in rows)
    assert {
        row["baseline_commit"] for row in rows
    } <= {tool.NIGHT_SOURCE, tool.ENGINEERING_SOURCE}


def test_every_row_is_cat_file_bound_and_hash_exact(tool, manifest) -> None:
    for row in manifest["files"]:
        path = row["path"]
        revision = row["baseline_commit"]
        spec = f"{revision}:{path}"
        completed = subprocess.run(
            ["git", "-C", str(ROOT), "cat-file", "-e", spec],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert completed.returncode == 0, spec
        payload = tool.git_blob(ROOT, revision, path)
        assert len(payload) == row["byte_count"]
        assert hashlib.sha256(payload).hexdigest() == row["content_sha256"]
        assert tool.git_blob_oid(ROOT, revision, path) == row["blob_oid"]
        assert row["cat_file_spec"] == spec
        assert row["restore_command"] == tool._restore_command(revision, path)


def test_full_restore_is_byte_for_byte_in_unique_temp_root(
    tool, manifest, tmp_path: Path
) -> None:
    restore_root = tmp_path / "r5_v1_historical_restore"
    receipt = tool.restore_all(ROOT, restore_root, manifest)
    assert receipt["file_count"] == manifest["aggregate"]["file_count"]
    assert (
        receipt["content_byte_count"]
        == manifest["aggregate"]["content_byte_count"]
    )
    assert receipt["cat_file_e_verified"] is True
    assert receipt["content_hash_verified"] is True
    assert receipt["full_restore_verified"] is True
    assert receipt["byte_for_byte_match"] is True
    for row in manifest["files"]:
        restored = restore_root / row["path"]
        filesystem_restored = tool._filesystem_path(restored)
        assert filesystem_restored.is_file()
        assert filesystem_restored.read_bytes() == tool.git_blob(
            ROOT, row["baseline_commit"], row["path"]
        )


def test_baseline_tampering_and_unsafe_restore_root_fail_closed(
    tool, manifest, tmp_path: Path
) -> None:
    cleanup = tool.load_yaml(ROOT / tool.CLEANUP_MANIFEST_REL)
    tampered = copy.deepcopy(manifest)
    tampered["files"][0]["content_sha256"] = "0" * 64
    with pytest.raises(tool.CleanupValidationError):
        tool.validate_documents(ROOT, tampered, cleanup)

    with pytest.raises(tool.CleanupValidationError, match="outside"):
        tool.restore_all(ROOT, ROOT / ".unsafe_restore", manifest)
