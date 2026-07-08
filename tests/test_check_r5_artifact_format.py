from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/check_r5_artifact_format.py"


def load_guard():
    spec = importlib.util.spec_from_file_location("check_r5_artifact_format", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_r5_artifacts_pass_default_guard():
    guard = load_guard()
    report = guard.run_checks(REPO_ROOT)
    assert report["status"] == "pass"
    assert report["summary"]["failed"] == 0


def test_one_line_python_is_reported(tmp_path: Path):
    guard = load_guard()
    path = tmp_path / "one_line.py"
    path.write_text("#!/usr/bin/env python3", encoding="utf-8")

    result = guard.check_artifact(tmp_path, guard.ArtifactRule("one_line.py", "python"))

    assert result.status == "fail"
    assert any("one-line" in issue or "shebang" in issue for issue in result.issues)


def test_one_line_yaml_is_reported(tmp_path: Path):
    guard = load_guard()
    path = tmp_path / "one_line.yaml"
    path.write_text("schema_version: r5_test", encoding="utf-8")

    result = guard.check_artifact(tmp_path, guard.ArtifactRule("one_line.yaml", "yaml"))

    assert result.status == "fail"
    assert any("one-line" in issue or "line_count" in issue for issue in result.issues)


def test_empty_pytest_file_is_reported(tmp_path: Path):
    guard = load_guard()
    path = tmp_path / "test_empty.py"
    path.write_text("from __future__ import annotations\n\nVALUE = 1\n", encoding="utf-8")

    result = guard.check_artifact(tmp_path, guard.ArtifactRule("test_empty.py", "pytest"))

    assert result.status == "fail"
    assert any("no test function" in issue for issue in result.issues)


def test_literal_newline_blob_is_reported(tmp_path: Path):
    guard = load_guard()
    path = tmp_path / "blob.yaml"
    path.write_text("schema_version: r5\\nartifact_type: blob\\nitems:\\n- a\\n- b\\n- c\\n", encoding="utf-8")

    result = guard.check_artifact(tmp_path, guard.ArtifactRule("blob.yaml", "yaml"))

    assert result.status == "fail"
    assert any("literal" in issue for issue in result.issues)


def test_shebang_blob_swallowing_code_is_reported(tmp_path: Path):
    guard = load_guard()
    path = tmp_path / "blob.py"
    path.write_text("#!/usr/bin/env python3 from __future__ import annotations\n", encoding="utf-8")

    result = guard.check_artifact(tmp_path, guard.ArtifactRule("blob.py", "python"))

    assert result.status == "fail"
    assert any("shebang" in issue or "empty" in issue for issue in result.issues)


def test_one_line_syntax_blob_is_reported(tmp_path: Path):
    guard = load_guard()
    path = tmp_path / "syntax_blob.py"
    path.write_text("from __future__ import annotations from pathlib import Path\n", encoding="utf-8")

    result = guard.check_artifact(tmp_path, guard.ArtifactRule("syntax_blob.py", "python"))

    assert result.status == "fail"
    assert any("py_compile" in issue or "one-line" in issue for issue in result.issues)


def test_comment_only_module_is_reported(tmp_path: Path):
    guard = load_guard()
    path = tmp_path / "comment_only.py"
    path.write_text("# comment only\n# still no executable module body\n", encoding="utf-8")

    result = guard.check_artifact(tmp_path, guard.ArtifactRule("comment_only.py", "python"))

    assert result.status == "fail"
    assert any("empty" in issue for issue in result.issues)


def test_docstring_only_module_is_reported(tmp_path: Path):
    guard = load_guard()
    path = tmp_path / "docstring_only.py"
    path.write_text('"""Only a docstring."""\n', encoding="utf-8")

    result = guard.check_artifact(tmp_path, guard.ArtifactRule("docstring_only.py", "python"))

    assert result.status == "fail"
    assert any("comments/docstrings/constants" in issue for issue in result.issues)


def test_multiline_cli_script_with_help_passes(tmp_path: Path):
    guard = load_guard()
    path = tmp_path / "ok_cli.py"
    path.write_text(
        "from __future__ import annotations\n\n"
        "import argparse\n\n"
        "def main() -> int:\n"
        "    parser = argparse.ArgumentParser(description='ok')\n"
        "    parser.parse_args()\n"
        "    return 0\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = guard.check_artifact(tmp_path, guard.ArtifactRule("ok_cli.py", "python", min_lines=8, requires_cli_help=True))

    assert result.status == "pass"


def test_cli_help_nonzero_is_reported(tmp_path: Path):
    guard = load_guard()
    path = tmp_path / "bad_cli.py"
    path.write_text(
        "from __future__ import annotations\n\n"
        "def main() -> int:\n"
        "    return 3\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    result = guard.check_artifact(tmp_path, guard.ArtifactRule("bad_cli.py", "python", min_lines=6, requires_cli_help=True))

    assert result.status == "fail"
    assert any("--help exit_code" in issue for issue in result.issues)
