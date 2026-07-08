from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/check_r5_readout_truthfulness.py"


def load_checker():
    spec = importlib.util.spec_from_file_location("check_r5_readout_truthfulness", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_missing_commands_run_fails(tmp_path: Path):
    checker = load_checker()
    readout = tmp_path / "R5_PATCH_X_READOUT.md"
    readout.write_text(
        "# Readout\n\nstatus: PASS\n\n## Files Added\n\nNone\n\n## Known TODOs\n\nNone\n",
        encoding="utf-8",
    )

    result = checker.check_readout(readout, checker.DEFAULT_RULES)

    assert result["status"] == "fail"
    assert any("commands_run" in issue for issue in result["issues"])


def test_passed_without_exit_code_fails(tmp_path: Path):
    checker = load_checker()
    readout = tmp_path / "R5_PATCH_X_READOUT.md"
    readout.write_text(
        "# Readout\n\n"
        "status: PASS\n\n"
        "## Files Added\n\nNone\n\n"
        "## Files Modified\n\nNone\n\n"
        "## Commands Run\n\npytest passed\n\n"
        "stdout_or_stderr_summary: all tests passed\n\n"
        "line_count: 10\n\n"
        "## Known TODOs\n\nNone\n\n"
        "## Next Recommended Patch\n\nNone\n",
        encoding="utf-8",
    )

    result = checker.check_readout(readout, checker.DEFAULT_RULES)

    assert result["status"] == "fail"
    assert any("exit_code" in issue for issue in result["issues"])


def test_valid_readout_passes(tmp_path: Path):
    checker = load_checker()
    readout = tmp_path / "R5_PATCH_X_READOUT.md"
    readout.write_text(
        "# Readout\n\n"
        "status: PASS\n\n"
        "## Files Added\n\n- file\n\n"
        "## Files Modified\n\nNone\n\n"
        "## Commands Run\n\n```text\npython -m pytest tests/test_x.py\n```\n\n"
        "exit_code: `0`\n\n"
        "stdout_or_stderr_summary:\n\n```text\n3 passed in 0.01s\n```\n\n"
        "line_count: 42\n\n"
        "## Known TODOs\n\nNone\n\n"
        "## Next Recommended Patch\n\nR5_PATCH_Y\n",
        encoding="utf-8",
    )

    result = checker.check_readout(readout, checker.DEFAULT_RULES)

    assert result["status"] == "pass"


def test_cli_checks_glob(tmp_path: Path, capsys):
    checker = load_checker()
    good = tmp_path / "R5_PATCH_GOOD_READOUT.md"
    good.write_text(
        "status: PASS\nfiles_added\nfiles_modified\ncommands_run\nexit_code: 0\n"
        "stdout_or_stderr_summary\n1 passed in 0.01s\nline_count: 2\nknown_todos\nnext_recommended_patch\n",
        encoding="utf-8",
    )

    exit_code = checker.main(["--repo-root", str(tmp_path), "--glob", "R5_PATCH_*_READOUT.md", "--strict"])

    assert exit_code == 0
    assert "truthfulness_status=pass" in capsys.readouterr().out
