from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "manage_r5_v1_historical_cleanup.py"


def load_tool():
    spec = importlib.util.spec_from_file_location(
        "manage_r5_v1_historical_cleanup_cleanup_tests", TOOL_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tool():
    return load_tool()


@pytest.fixture(scope="module")
def documents(tool):
    return (
        tool.load_yaml(ROOT / tool.BASELINE_MANIFEST_REL),
        tool.load_yaml(ROOT / tool.CLEANUP_MANIFEST_REL),
    )


def test_cleanup_manifest_is_exact_three_wave_partition(tool, documents) -> None:
    baseline, cleanup = documents
    rows = cleanup["files"]
    paths = [row["path"] for row in rows]
    waves = cleanup["waves"]
    baseline_by_path = {row["path"]: row for row in baseline["files"]}

    assert cleanup["schema_version"] == "r5_v1_historical_cleanup_manifest_v1"
    assert cleanup["deletion_actor"] == "user_manual_only"
    assert cleanup["codex_delete_authorized"] is False
    assert cleanup["wave_order"] == ["night", "bundle", "old002837"]
    assert [row["wave"] for row in waves] == cleanup["wave_order"]
    assert [row["order"] for row in waves] == [1, 2, 3]
    assert paths == sorted(paths)
    assert len(paths) == len(set(paths))
    assert cleanup["aggregate"] == tool._aggregate(rows)

    flattened = [
        path
        for wave in waves
        for path in wave["paths"]
    ]
    assert flattened == [
        row["path"]
        for wave in cleanup["wave_order"]
        for row in rows
        if row["wave"] == wave
    ]
    assert len(flattened) == len(set(flattened)) == len(paths)
    assert set(flattened) == set(paths)
    for wave in waves:
        wave_rows = [row for row in rows if row["wave"] == wave["wave"]]
        assert wave["paths"] == [row["path"] for row in wave_rows]
        assert wave["aggregate"] == tool._aggregate(wave_rows)
    for row in rows:
        baseline_row = baseline_by_path[row["path"]]
        for key in (
            "baseline_commit",
            "blob_oid",
            "byte_count",
            "content_sha256",
            "restore_command",
        ):
            assert row[key] == baseline_row[key]


def test_actual_paths_are_eligible_and_disjoint_from_every_retained_set(
    tool, documents
) -> None:
    _, cleanup = documents
    authority = tool.parse_authority(ROOT)
    a6 = tool.expand_a6(ROOT)
    actual = {row["path"] for row in cleanup["files"]}
    retained = (
        authority["a1"]
        | authority["a2"]
        | authority["a4"]
        | authority["a5"]
        | a6
    )
    assert actual.isdisjoint(retained)
    assert actual.issuperset(authority["a3"])
    assert all(not tool.is_protected(path, a6) for path in actual)
    assert all(
        not path.startswith(tool.RETAINED_EVALUATOR_DEPENDENCY_PREFIXES)
        for path in actual
    )
    assert all(
        tool.classify_wave(path, authority["a3"]) == row["wave"]
        for row in cleanup["files"]
        for path in [row["path"]]
    )


def test_actual_manifest_has_no_wildcard_absolute_or_escaping_path(
    tool, documents
) -> None:
    _, cleanup = documents
    for row in cleanup["files"]:
        path = row["path"]
        posix = Path(path)
        assert not posix.is_absolute()
        assert ".." not in posix.parts
        assert not any(token in path for token in ("*", "?", "[", "]", "{", "}"))
        assert "\\" not in path
        assert row["active_reference_count"] >= 0
        assert row["reference_scan_scope"] == "tracked_active_roots"
        assert row["deletion_preconditions"] == [
            "active_reference_count_equals_zero",
            "baseline_blob_and_full_restore_verified",
            "current_wave_armed_in_start_here",
            "user_manually_deletes_only_this_exact_path",
        ]


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            b" D alpha.txt\0 D dir/beta.yaml\0",
            [
                {"status": " D", "path": "alpha.txt"},
                {"status": " D", "path": "dir/beta.yaml"},
            ],
        ),
        (
            b"?? untracked.txt\0",
            [{"status": "??", "path": "untracked.txt"}],
        ),
        (
            b"R  new.txt\0old.txt\0",
            [{"status": "R ", "path": "new.txt", "source_path": "old.txt"}],
        ),
    ],
)
def test_porcelain_v1_z_parser_is_nul_safe(tool, payload, expected) -> None:
    assert tool.parse_porcelain_v1_z(payload) == expected


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            b"D\0alpha.txt\0D\0dir/beta.yaml\0",
            [
                {"status": "D", "path": "alpha.txt"},
                {"status": "D", "path": "dir/beta.yaml"},
            ],
        ),
        (
            b"R100\0old.txt\0new.txt\0",
            [
                {
                    "status": "R100",
                    "path": "old.txt",
                    "destination_path": "new.txt",
                }
            ],
        ),
    ],
)
def test_name_status_z_parser_is_nul_safe(tool, payload, expected) -> None:
    assert tool.parse_name_status_z(payload) == expected


def test_vector_parsers_and_document_validation_fail_closed(tool, documents) -> None:
    baseline, cleanup = documents
    with pytest.raises(tool.CleanupValidationError):
        tool.parse_porcelain_v1_z(b" D missing-nul")
    with pytest.raises(tool.CleanupValidationError):
        tool.parse_name_status_z(b"D\0")

    duplicate = copy.deepcopy(cleanup)
    duplicate["files"].append(copy.deepcopy(duplicate["files"][0]))
    with pytest.raises(tool.CleanupValidationError):
        tool.validate_documents(ROOT, baseline, duplicate)


def test_wave_verifier_has_no_delete_stage_or_commit_surface(tool) -> None:
    parser = tool.build_parser()
    help_text = parser.format_help().lower()
    assert "delete" not in parser._subparsers._group_actions[0].choices
    assert "stage" not in parser._subparsers._group_actions[0].choices
    assert "commit" not in parser._subparsers._group_actions[0].choices
    assert set(parser._subparsers._group_actions[0].choices) == {
        "build",
        "validate",
        "verify-restore",
        "verify-wave",
    }
    assert "historical-cleanup control plane" in help_text
