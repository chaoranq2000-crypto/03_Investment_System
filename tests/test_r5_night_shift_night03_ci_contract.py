from __future__ import annotations

from pathlib import Path

import yaml


V006_TESTS = (
    "tests/test_r5_v1_historical_baseline_manifest.py",
    "tests/test_r5_v1_historical_cleanup_manifest.py",
    "tests/test_r5_v1_active_routing_retirement.py",
)
RETIRED_CI_MARKERS = (
    "tests/test_r5_night_shift_",
    "reports/p1_6/r5_night_shift/",
    "reports/p1_6/r5_bundle17r",
    "run night-shift contract",
    "069da527452def6c59c3772750e933d8611ccadf",
    "758ab7557d9de9eea42a5aeb5df95e3d68c26f0c",
)


def test_night03_ci_proves_equal_strength_retirement_contract() -> None:
    workflow_path = Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml"
    text = workflow_path.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    steps = workflow["jobs"]["tests"]["steps"]
    commands = [str(step.get("run", "")) for step in steps]
    lowered = text.casefold()

    assert all(marker not in lowered for marker in RETIRED_CI_MARKERS)
    assert all("tests/test_r5_night_shift_" not in command for command in commands)
    assert all("reports/p1_6/r5_night_shift/" not in command for command in commands)
    assert "continue-on-error: true" not in lowered
    assert "|| true" not in lowered

    checkout_steps = [
        step for step in steps if str(step.get("uses", "")).startswith("actions/checkout@")
    ]
    assert len(checkout_steps) == 1
    assert str(checkout_steps[0].get("with", {}).get("fetch-depth")) == "0"
    assert commands.count("python -m pytest -q") == 1
    assert sum("run_source_route_quality_gate.py" in command for command in commands) == 1
    assert (
        sum(all(test_path in command for test_path in V006_TESTS) for command in commands)
        == 1
    )
    assert "git push" not in lowered
    assert "gh pr create" not in lowered
    assert "--force" not in lowered
