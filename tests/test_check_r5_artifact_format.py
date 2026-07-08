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
