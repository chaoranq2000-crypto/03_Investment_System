from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.test_r5_bundle17r_verified_result_materializer import build_fixture


def test_cli_runs_from_repository_script(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    script = Path(__file__).resolve().parents[1] / "scripts/run_r5_bundle17r_verified_result_materializer.py"
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(script),
            "--repo-root",
            str(tmp_path),
            "--manifest",
            str(fixture["manifest_path"]),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "passed=2" in completed.stdout
    assert "unresolved=0" in completed.stdout
