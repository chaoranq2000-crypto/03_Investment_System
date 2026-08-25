from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/check_r5_task_readout_sync.py"


def load_checker():
    spec = importlib.util.spec_from_file_location("check_r5_task_readout_sync", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_readout(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# Readout",
                "",
                "status: accepted_with_todos",
                "",
                "## commands_run",
                "",
                "- python example.py",
                "",
                "## exit_code",
                "",
                "- example: 0",
                "",
                "## stdout_or_stderr_summary",
                "",
                "- ok",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_completed_row_requires_task_readout_and_command_evidence(tmp_path: Path):
    checker = load_checker()
    task = "compatibility/task_cards/PATCH_ALPHA.md"
    readout = "compatibility/readouts/PATCH_ALPHA_READOUT.md"
    (tmp_path / task).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / task).write_text("# task\n", encoding="utf-8")
    write_readout(tmp_path / readout)

    row = checker.evaluate_row(
        tmp_path,
        checker.PatchExpectation("PATCH_ALPHA", task, readout, True),
        f"| `{readout}` | `canonical` | `true` | ok |",
    )

    assert row["status"] == "completed_with_command_evidence"
    assert row["canonical_status"] == "canonical"


def test_distinguishes_missing_task_card_from_missing_readout(tmp_path: Path):
    checker = load_checker()
    readout = "compatibility/readouts/PATCH_BETA_READOUT.md"
    write_readout(tmp_path / readout)

    row = checker.evaluate_row(
        tmp_path,
        checker.PatchExpectation(
            "PATCH_BETA",
            "compatibility/task_cards/PATCH_BETA.md",
            readout,
            True,
        ),
        "",
    )

    assert row["status"] == "readout_exists_task_card_missing"


def test_nonstandard_close_readout_relation_is_explicit(tmp_path: Path):
    checker = load_checker()
    task = "compatibility/task_cards/PATCH_OMEGA.md"
    readout = "compatibility/readouts/HISTORICAL_CLOSE_READOUT.md"
    (tmp_path / task).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / task).write_text("# task\n", encoding="utf-8")
    write_readout(tmp_path / readout)

    row = checker.evaluate_row(
        tmp_path,
        checker.PatchExpectation(
            "PATCH_OMEGA",
            task,
            readout,
            True,
            close_readout_relation="close_readout_exists_under_non_patch_filename",
        ),
        "",
    )

    assert row["status"] == "completed_with_command_evidence"
    assert row["close_readout_relation"] == "close_readout_exists_under_non_patch_filename"


def test_cli_uses_only_explicit_expectations(tmp_path: Path):
    checker = load_checker()
    task = "compatibility/task_cards/PATCH_EXPLICIT.md"
    readout = "compatibility/readouts/PATCH_EXPLICIT_READOUT.md"
    (tmp_path / task).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / task).write_text("# task\n", encoding="utf-8")
    write_readout(tmp_path / readout)
    expectations = tmp_path / "fixtures/expectations.yaml"
    expectations.parent.mkdir(parents=True)
    expectations.write_text(
        yaml.safe_dump(
            {
                "expectations": [
                    {
                        "patch_id": "PATCH_EXPLICIT",
                        "task_card_path": task,
                        "readout_path": readout,
                        "blocking_for_next": True,
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = checker.main(
        [
            "--repo-root",
            str(tmp_path),
            "--expectations",
            str(expectations),
        ]
    )

    assert result == 0
    assert not hasattr(checker, "PATCH_EXPECTATIONS")
    payload = checker.build_matrix(
        tmp_path,
        checker.load_expectations(expectations),
    )
    assert payload["expectation_source"] == "explicit_input"
    assert [row["patch_id"] for row in payload["rows"]] == ["PATCH_EXPLICIT"]
