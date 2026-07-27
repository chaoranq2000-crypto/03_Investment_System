from __future__ import annotations

import ast
import copy
import importlib.util
import inspect
import subprocess
from pathlib import Path, PurePosixPath, PureWindowsPath

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
    assert cleanup["deletion_actor"] == "wave_specific"
    assert cleanup["codex_delete_authorized"] is False
    assert cleanup["authorization_scope"] == "wave_specific_only"
    assert cleanup["wave_order"] == ["night", "bundle", "old002837"]
    assert [row["wave"] for row in waves] == cleanup["wave_order"]
    assert [row["order"] for row in waves] == [1, 2, 3]
    assert {
        wave["wave"]: {
            "deletion_actor": wave["deletion_actor"],
            "codex_delete_authorized": wave["codex_delete_authorized"],
        }
        for wave in waves
    } == tool.WAVE_ACTORS
    assert paths == sorted(paths)
    assert len(paths) == len(set(paths))
    assert cleanup["aggregate"] == tool._aggregate(rows)
    directories = cleanup["old002837_empty_directory_cleanup"]
    assert directories == tool.build_old002837_directory_manifest(ROOT)
    assert directories["aggregate"] == {
        "directory_count": 29,
        "path_vector_encoding": "deepest_first_utf8_nul",
        "path_vector_byte_count": 2208,
        "path_vector_sha256": (
            "1e987f07ab4aa9b7c54a7444b053949b5c5d377655903d9715d8948e42446cd3"
        ),
        "absolute_path_vector_byte_count": 3803,
        "absolute_path_vector_sha256": (
            "31669a8f873c2510709a7f9828b27dad4eab9fe49a159071d40345693e770b75"
        ),
    }
    assert directories["paths"] == list(tool.OLD002837_DIRECTORIES)
    assert set(directories["paths"]).isdisjoint(paths)

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
        assert [row["wave_ordinal"] for row in wave_rows] == list(
            range(1, len(wave_rows) + 1)
        )
    for row in rows:
        baseline_row = baseline_by_path[row["path"]]
        assert {
            "deletion_actor": row["deletion_actor"],
            "codex_delete_authorized": row["codex_delete_authorized"],
        } == tool.WAVE_ACTORS[row["wave"]]
        for key in (
            "baseline_commit",
            "blob_oid",
            "byte_count",
            "content_sha256",
            "restore_command",
        ):
            assert row[key] == baseline_row[key]


def test_fixed_absolute_directory_receipt_is_path_flavour_independent(
    tool, monkeypatch
) -> None:
    dedicated_root_text = str(tool.DEDICATED_WORKTREE_ROOT)
    monkeypatch.setattr(
        tool,
        "DEDICATED_WORKTREE_ROOT",
        PurePosixPath(dedicated_root_text),
    )

    directories = tool.build_old002837_directory_manifest(ROOT)
    expected_paths = [
        str(
            PureWindowsPath(dedicated_root_text).joinpath(
                *PurePosixPath(path).parts
            )
        )
        for path in tool.OLD002837_DIRECTORIES
    ]

    assert directories["dedicated_worktree_root"] == dedicated_root_text
    assert directories["absolute_paths"] == expected_paths
    assert directories["aggregate"]["absolute_path_vector_byte_count"] == 3803
    assert directories["aggregate"]["absolute_path_vector_sha256"] == (
        "31669a8f873c2510709a7f9828b27dad4eab9fe49a159071d40345693e770b75"
    )


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
    assert actual & authority["a7"] == authority["a7"] == tool.EXPECTED_A7
    assert all(
        row["wave"] == "night"
        for row in cleanup["files"]
        if row["path"] in authority["a7"]
    )
    assert actual.issuperset(authority["a3"])
    assert all(not tool.is_protected(path, a6) for path in actual)
    assert actual.isdisjoint(tool.RETAINED_EVALUATOR_DEPENDENCIES)
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
            "codex_unlinks_only_this_exact_literal_regular_file",
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


def test_cli_rejects_completed_night_and_has_no_stage_or_commit_surface(tool) -> None:
    parser = tool.build_parser()
    help_text = parser.format_help().lower()
    assert "stage" not in parser._subparsers._group_actions[0].choices
    assert "commit" not in parser._subparsers._group_actions[0].choices
    assert set(parser._subparsers._group_actions[0].choices) == {
        "build",
        "validate",
        "verify-restore",
        "verify-wave",
        "delete-wave",
    }
    assert "historical-cleanup control plane" in help_text
    delete_parser = parser._subparsers._group_actions[0].choices["delete-wave"]
    wave_action = next(
        action for action in delete_parser._actions if action.dest == "wave"
    )
    assert tuple(wave_action.choices) == ("bundle", "old002837")
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["delete-wave", "--wave", "night", "--wave-parent", "deadbeef"]
        )

    tree = ast.parse(inspect.getsource(tool))
    forbidden_git_verbs = {"add", "commit", "clean", "reset", "checkout"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "_git":
            continue
        literal_args = {
            arg.value
            for arg in node.args
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
        }
        assert literal_args.isdisjoint(forbidden_git_verbs)


def _status_payload(paths: list[str]) -> bytes:
    return b"".join(b" D " + path.encode("utf-8") + b"\0" for path in paths)


def _diff_payload(paths: list[str]) -> bytes:
    return b"".join(b"D\0" + path.encode("utf-8") + b"\0" for path in paths)


def test_file_vector_accepts_only_an_exact_ordinal_prefix(tool) -> None:
    expected = ["a.txt", "b.txt", "c.txt"]
    assert tool.validate_deletion_prefix_vectors(b"", b"", b"", expected)[
        "prefix_count"
    ] == 0
    prefix = tool.validate_deletion_prefix_vectors(
        _status_payload(expected[:2]),
        _diff_payload(expected[:2]),
        b"",
        expected,
    )
    assert prefix["prefix_count"] == 2
    assert prefix["complete"] is False
    complete = tool.validate_deletion_prefix_vectors(
        _status_payload(expected),
        _diff_payload(expected),
        b"",
        expected,
        require_complete=True,
    )
    assert complete["complete"] is True

    with pytest.raises(tool.CleanupValidationError, match="ordinal manifest prefix"):
        tool.validate_deletion_prefix_vectors(
            _status_payload(["a.txt", "c.txt"]),
            _diff_payload(["a.txt", "c.txt"]),
            b"",
            expected,
        )
    with pytest.raises(tool.CleanupValidationError, match="non-worktree-deletion"):
        tool.validate_deletion_prefix_vectors(
            b"?? unexpected.txt\0", b"", b"", expected
        )
    with pytest.raises(tool.CleanupValidationError, match="staged"):
        tool.validate_deletion_prefix_vectors(b"", b"", b"M\0a.txt\0", expected)


def test_v8_actor_generation_and_tampering_fail_closed(tool) -> None:
    _, cleanup, receipt = tool.build_documents(ROOT)
    tool.validate_fixed_cleanup_aggregates(cleanup)
    tool.validate_actor_bindings(cleanup)
    assert receipt["deletion_control"]["root_agents"]["blob_oid"] == (
        tool.EXPECTED_AGENTS_BLOB_OID
    )
    assert receipt["deletion_control"]["wave_actors"] == tool.WAVE_ACTORS
    assert receipt["guards"]["codex_delete_command_exists"] is True
    assert all(
        actor == {
            "deletion_actor": "codex_exact_manifest_one_file_at_a_time",
            "codex_delete_authorized": True,
        }
        for actor in tool.WAVE_ACTORS.values()
    )
    assert receipt["deletion_control"]["file_delete_surface"][
        "completed_night_rejected"
    ] is True
    assert receipt["deletion_control"]["old002837_directory_surface"][
        "requires_complete_501_file_deletion_vector"
    ] is True

    tampered_wave = copy.deepcopy(cleanup)
    tampered_wave["waves"][0]["codex_delete_authorized"] = False
    with pytest.raises(tool.CleanupValidationError, match="actor/authorization"):
        tool.validate_actor_bindings(tampered_wave)

    tampered_row = copy.deepcopy(cleanup)
    first_bundle = next(
        row for row in tampered_row["files"] if row["wave"] == "bundle"
    )
    first_bundle["codex_delete_authorized"] = False
    with pytest.raises(tool.CleanupValidationError, match="actor/authorization"):
        tool.validate_actor_bindings(tampered_row)


def test_bundle_arm_requires_exact_v8_checkpoint_subject_and_section_scoped_start(
    tool, documents, tmp_path: Path
) -> None:
    repo = tmp_path / "arm_repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Codex Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "codex@example.invalid"],
        check=True,
    )
    _, cleanup = documents
    expected = next(
        list(wave["paths"]) for wave in cleanup["waves"] if wave["wave"] == "bundle"
    )
    start = repo / tool.START_HERE_REL
    start.parent.mkdir(parents=True)
    lines = [
        "---",
        'task_id: "v1_governance_integration_cleanup_v8"',
        f'contract_sha256: "{tool.EXPECTED_CONTRACT_SHA256}"',
        f'source_baseline: "{tool.PACKAGE_SOURCE_BASELINE}"',
        'state: "running"',
        "---",
        tool.ARM_SECTION_HEADINGS["bundle"],
        "- Wave: `bundle`",
        tool.ARM_STATE_MARKER,
        "- Contract deletion actor: `codex_exact_manifest_one_file_at_a_time`",
        "- Contract Codex deletion authorization: `true`",
        "- Expected deletion count: 205",
        tool.EXPECTED_WAVE_AGGREGATES["bundle"]["path_vector_sha256"],
        "#### Bundle exact absolute per-file manifest",
    ]
    lines.extend(
        f"- `{repo.joinpath(*Path(path).parts)}`" for path in expected
    )
    start.write_text("\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "--", start.as_posix()], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "commit",
            "-q",
            "-m",
            "chore(v1): bind bundle deletion to codex exact-file actor",
        ],
        check=True,
    )
    migration = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    with pytest.raises(tool.CleanupValidationError, match="exact v8 arm checkpoint"):
        tool.validate_wave_arm_identity(repo, migration, "bundle", expected)

    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "commit",
            "--allow-empty",
            "-q",
            "-m",
            tool.ARM_COMMIT_SUBJECTS["bundle"],
        ],
        check=True,
    )
    arm = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    identity = tool.validate_wave_arm_identity(repo, arm, "bundle", expected)
    assert identity["commit_subject"] == tool.ARM_COMMIT_SUBJECTS["bundle"]
    assert identity["path_count"] == 205
    with pytest.raises(tool.CleanupValidationError, match="completed or unauthorized"):
        tool.validate_wave_arm_identity(repo, arm, "night", expected)


def test_literal_file_guard_and_single_unlink_use_a_real_temp_git_index(
    tool, tmp_path: Path
) -> None:
    repo = tmp_path / "literal_repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    regular = repo / "regular.txt"
    regular.write_text("temporary", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "--", "regular.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Codex Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "codex@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", "fixture"],
        check=True,
    )
    blob_oid = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD:regular.txt"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()

    target = tool.validate_literal_tracked_file(
        repo, "regular.txt", expected_blob_oid=blob_oid
    )
    assert target == regular.resolve()
    with pytest.raises(tool.CleanupValidationError, match="index blob OID"):
        tool.validate_literal_tracked_file(
            repo, "regular.txt", expected_blob_oid="0" * 40
        )
    with pytest.raises(tool.CleanupValidationError, match="escaping"):
        tool.validate_literal_tracked_file(repo, "../outside.txt")
    directory = repo / "directory"
    directory.mkdir()
    with pytest.raises(tool.CleanupValidationError, match="non-regular"):
        tool.validate_literal_tracked_file(repo, "directory")

    class ReparseStat:
        st_file_attributes = 0x400

    assert tool._is_reparse_stat(ReparseStat()) is True
    regular.write_text("index drift", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "--", "regular.txt"], check=True)
    with pytest.raises(tool.CleanupValidationError, match="index blob OID"):
        tool.validate_literal_tracked_file(
            repo, "regular.txt", expected_blob_oid=blob_oid
        )
    tool._unlink_one_literal(target)
    assert not regular.exists()


def test_directory_surface_is_deepest_first_prefix_only_and_git_invisible(
    tool, tmp_path: Path
) -> None:
    repo = tmp_path / "directory_repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Codex Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "codex@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "--allow-empty", "-q", "-m", "root"],
        check=True,
    )
    parent = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    paths = ["run/a", "run/b", "run"]
    for path in paths[:2]:
        repo.joinpath(*Path(path).parts).mkdir(parents=True, exist_ok=True)

    frozen_vectors = tool.capture_deletion_vectors(repo, parent)
    state = tool.validate_directory_prefix_state(repo, paths, processed_count=0)
    assert state["current_path"] == "run/a"
    for index, path in enumerate(paths, start=1):
        target = repo.joinpath(*Path(path).parts)
        tool._rmdir_one_literal(target)
        assert tool.capture_deletion_vectors(repo, parent) == frozen_vectors
        state = tool.validate_directory_prefix_state(
            repo, paths, processed_count=index
        )
    assert state["complete"] is True
    assert not (repo / "run").exists()


def test_directory_surface_rejects_extra_nonempty_gap_and_worktree_root(
    tool, tmp_path: Path
) -> None:
    extra_repo = tmp_path / "extra_repo"
    (extra_repo / "run" / "a").mkdir(parents=True)
    (extra_repo / "run" / "extra").mkdir()
    with pytest.raises(tool.CleanupValidationError, match="enumeration"):
        tool.validate_directory_prefix_state(extra_repo, ["run/a", "run"])

    file_repo = tmp_path / "file_repo"
    (file_repo / "run" / "a").mkdir(parents=True)
    (file_repo / "run" / "unexpected.txt").write_text(
        "unexpected", encoding="utf-8"
    )
    with pytest.raises(tool.CleanupValidationError, match="non-directory entry"):
        tool.validate_directory_prefix_state(file_repo, ["run/a", "run"])
    with pytest.raises(tool.CleanupValidationError, match="non-empty"):
        tool._rmdir_one_literal(file_repo / "run")

    gap_repo = tmp_path / "gap_repo"
    (gap_repo / "run" / "a").mkdir(parents=True)
    (gap_repo / "run" / "b").mkdir()
    (gap_repo / "run" / "b").rmdir()
    with pytest.raises(tool.CleanupValidationError, match="prefix/remaining-suffix"):
        tool.validate_directory_prefix_state(
            gap_repo, ["run/a", "run/b", "run"]
        )

    root_repo = tmp_path / "root_repo"
    root_repo.mkdir()
    with pytest.raises(tool.CleanupValidationError, match="worktree root"):
        tool.validate_directory_prefix_state(root_repo, ["."])


def test_baseline_recovery_metadata_tampering_fails_closed(tool, documents) -> None:
    baseline, _ = documents
    row = copy.deepcopy(baseline["files"][0])
    tool._validate_baseline_row(ROOT, row)
    row["content_sha256"] = "0" * 64
    with pytest.raises(tool.CleanupValidationError, match="content SHA-256"):
        tool._validate_baseline_row(ROOT, row)
