from __future__ import annotations

from pathlib import Path

from src.research.r5_bundle17r_backflow_execution import run_execution
from tests.r5_bundle17r_bf2_test_support import add_passed_result, build_fixture


def _snapshot(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def test_identical_inputs_produce_identical_outputs(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    add_passed_result(fixture)
    out_a = tmp_path / "out-a"
    out_b = tmp_path / "out-b"

    run_execution(tmp_path, fixture["manifest_path"], out_a)
    run_execution(tmp_path, fixture["manifest_path"], out_b)

    assert _snapshot(out_a) == _snapshot(out_b)
