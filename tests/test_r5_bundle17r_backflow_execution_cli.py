from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.r5_bundle17r_bf2_test_support import add_passed_result, build_fixture


def test_cli_runs_from_repo_root(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    add_passed_result(fixture)
    source_script = Path(__file__).parents[1] / "scripts/run_r5_bundle17r_backflow_execution.py"
    target_script = tmp_path / "scripts/run_r5_bundle17r_backflow_execution.py"
    target_script.parent.mkdir(parents=True, exist_ok=True)
    target_script.write_text(source_script.read_text(encoding="utf-8"), encoding="utf-8")

    # The implementation package is imported from the test checkout, while --repo-root points to
    # the isolated data fixture.  Calling the module directly exercises the same argparse path.
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.research.r5_bundle17r_backflow_execution",
            "--repo-root",
            str(tmp_path),
            "--manifest",
            str(fixture["manifest_path"]),
        ],
        cwd=Path(__file__).parents[1],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert "decision=ready_for_exact_hash_human_review" in completed.stdout
