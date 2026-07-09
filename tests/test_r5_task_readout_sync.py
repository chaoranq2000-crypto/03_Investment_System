from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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
    task = "codex_tasks/r5_after_patch36/R5_PATCH_43.md"
    readout = "reports/p1_6/R5_PATCH_43_READOUT.md"
    (tmp_path / task).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / task).write_text("# task\n", encoding="utf-8")
    write_readout(tmp_path / readout)

    row = checker.evaluate_row(
        tmp_path,
        checker.PatchExpectation("R5_PATCH_43", task, readout, True),
        f"| `{readout}` | `canonical` | `true` | ok |",
    )

    assert row["status"] == "completed_with_command_evidence"
    assert row["canonical_status"] == "canonical"


def test_distinguishes_missing_task_card_from_missing_readout(tmp_path: Path):
    checker = load_checker()
    readout = "reports/p1_6/R5_PATCH_44_READOUT.md"
    write_readout(tmp_path / readout)

    row = checker.evaluate_row(
        tmp_path,
        checker.PatchExpectation("R5_PATCH_44", "codex_tasks/r5_after_patch36/R5_PATCH_44.md", readout, True),
        "",
    )

    assert row["status"] == "readout_exists_task_card_missing"


def test_patch48_non_patch_close_readout_is_explicit(tmp_path: Path):
    checker = load_checker()
    task = "codex_tasks/r5_after_patch36/R5_PATCH_48.md"
    readout = "reports/p1_6/R5_AFTER_PATCH36_REVIEWED_INPUT_CLOSE_READOUT.md"
    (tmp_path / task).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / task).write_text("# task\n", encoding="utf-8")
    write_readout(tmp_path / readout)

    row = checker.evaluate_row(
        tmp_path,
        checker.PatchExpectation("R5_PATCH_48", task, readout, True),
        "",
    )

    assert row["status"] == "completed_with_command_evidence"
    assert row["close_readout_relation"] == "close_readout_exists_under_non_patch_filename"
