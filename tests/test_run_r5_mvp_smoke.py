from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

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
    assert report["repo_root"] == str(tmp_path)
    assert report["python_executable"]
    assert report["platform"]
    assert report["steps"] == report["results"]
    assert report["results"][0]["exit_code"] == 0
    assert "ok summary" in report["results"][0]["summary"]
    assert "ok summary" in report["results"][0]["stdout_tail"]
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


def test_default_steps_use_only_current_control_plane_inputs():
    runner = load_runner()
    steps = runner.default_steps(sys.executable, strict=True)
    truthfulness = next(
        step for step in steps if step["name"] == "current_pointer_truthfulness"
    )
    source_route = next(
        step for step in steps if step["name"] == "source_route_quality"
    )

    assert "--strict" in truthfulness["command"]
    assert source_route["artifact_outputs"] == [
        ".codex_tmp/research_smoke_source_route_quality_report.yaml"
    ]
    assert "--output" in source_route["command"]
    serialized = "\n".join(" ".join(step["command"]) for step in steps)
    assert "config/r5_readout_canonical_index.yaml" not in serialized
    assert "r5_patch_1_12_expected_artifacts" not in serialized
    assert "reports/p1_6/R5_PATCH_" not in serialized
    assert "historical_cleanup" not in serialized
    assert {step["name"] for step in steps} == {
        "r5_artifact_format_guard",
        "doc_drift",
        "current_pointer_truthfulness",
        "current_workflow_state",
        "source_route_quality",
        "active_routing_retirement",
        "research_pack_contracts",
        "current_research_fixture_smoke",
    }


def test_smoke_follows_replaced_and_multiple_current_pointers(tmp_path: Path):
    runner = load_runner()
    index = tmp_path / "config/r5_readout_canonical_index.yaml"
    index.parent.mkdir()
    states = [
        "reports/workflow_runs/wf_fixture_a/workflow_state.yaml",
        "reports/workflow_runs/wf_fixture_b/workflow_state.yaml",
    ]
    index.write_text(
        yaml.safe_dump({"current_runs": {
            f"fixture_{number}": {"workflow_id": f"wf_fixture_{name}", "state_path": state}
            for number, (name, state) in enumerate(zip(("a", "b"), states))
        }}),
        encoding="utf-8",
    )
    steps = runner.default_steps(sys.executable, True, tmp_path)
    selected = [step["command"][-1] for step in steps if step["name"].startswith("current_workflow_state")]
    assert selected == states
    assert all("20260725" not in state for state in selected)


@pytest.mark.parametrize("runs", [
    {},
    {"fixture": {"workflow_id": "../../escape", "state_path": "reports/workflow_runs/../../escape/workflow_state.yaml"}},
    {"fixture": {"workflow_id": "wf_a", "state_path": "C:/outside/workflow_state.yaml"}},
])
def test_smoke_rejects_missing_or_escaping_current_state(tmp_path: Path, runs):
    runner = load_runner()
    index = tmp_path / "config/r5_readout_canonical_index.yaml"
    index.parent.mkdir()
    index.write_text(yaml.safe_dump({"current_runs": runs}), encoding="utf-8")
    with pytest.raises(ValueError):
        runner.default_steps(sys.executable, True, tmp_path)


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
