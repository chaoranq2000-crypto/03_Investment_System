from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/run_r5_mvp_smoke.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("run_r5_mvp_smoke", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_steps_records_success(tmp_path: Path):
    runner = load_runner()
    report = runner.run_steps(
        [
            {
                "name": "ok",
                "command": [sys.executable, "-c", "print('ok summary')"],
            }
        ],
        tmp_path,
    )

    assert report["status"] == "pass"
    assert report["results"][0]["exit_code"] == 0
    assert "ok summary" in report["results"][0]["summary"]
    assert "duration_seconds" in report["results"][0]


def test_run_steps_marks_failure_and_preserves_stderr(tmp_path: Path):
    runner = load_runner()
    report = runner.run_steps(
        [
            {
                "name": "bad",
                "command": [sys.executable, "-c", "import sys; print('bad stderr', file=sys.stderr); raise SystemExit(3)"],
            }
        ],
        tmp_path,
    )

    assert report["status"] == "fail"
    assert report["failed"] == 1
    assert report["results"][0]["exit_code"] == 3
    assert "bad stderr" in report["results"][0]["stderr"]


def test_write_json_creates_report(tmp_path: Path):
    runner = load_runner()
    path = tmp_path / "nested" / "report.json"
    runner.write_json(path, {"status": "pass", "results": []})

    assert path.exists()
    assert '"status": "pass"' in path.read_text(encoding="utf-8")


def test_default_steps_adds_strict_to_advisory_gates():
    runner = load_runner()
    steps = runner.default_steps(sys.executable, strict=True)
    inventory = next(step for step in steps if step["name"] == "r5_patch_inventory_check")
    truthfulness = next(step for step in steps if step["name"] == "r5_readout_truthfulness_gate")

    assert "--strict" in inventory["command"]
    assert "--strict" in truthfulness["command"]


def test_emit_report_writes_stderr(capsys):
    runner = load_runner()
    runner.emit_report(
        {
            "status": "fail",
            "checked": 1,
            "failed": 1,
            "results": [
                {
                    "name": "bad",
                    "exit_code": 1,
                    "duration_seconds": 0.01,
                    "summary": "bad summary",
                    "stderr": "bad stderr\n",
                }
            ],
        }
    )

    captured = capsys.readouterr()
    assert "bad summary" in captured.out
    assert "bad stderr" in captured.err
