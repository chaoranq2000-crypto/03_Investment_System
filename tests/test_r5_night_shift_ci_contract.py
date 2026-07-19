from __future__ import annotations

from pathlib import Path

import yaml


def test_ci_runs_night_shift_suite_and_preserves_full_regression() -> None:
    workflow_path = Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["tests"]["steps"]
    commands = [str(step.get("run", "")) for step in steps]
    assert any("tests/test_r5_night_shift_*.py" in command for command in commands)
    assert "python -m pytest -q" in commands
    assert any("run_source_route_quality_gate.py" in command for command in commands)


def test_ci_contract_does_not_add_mutating_publication_steps() -> None:
    text = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text(
        encoding="utf-8"
    )
    lowered = text.casefold()
    assert "git push" not in lowered
    assert "gh pr create" not in lowered
    assert "--force" not in lowered
