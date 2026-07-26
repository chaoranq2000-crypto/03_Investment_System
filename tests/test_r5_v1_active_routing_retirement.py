from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "manage_r5_v1_historical_cleanup.py"


def load_tool():
    spec = importlib.util.spec_from_file_location(
        "manage_r5_v1_historical_cleanup_routing_tests", TOOL_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_active_roots_have_zero_candidate_worktree_routes() -> None:
    tool = load_tool()
    authority = tool.parse_authority(ROOT)
    a6 = tool.expand_a6(ROOT)
    inventory = tool.build_candidate_inventory(ROOT, authority, a6)
    scan = tool.scan_active_references(ROOT, inventory, authority)

    assert scan["unknown_classification_count"] == 0, scan[
        "unknown_classifications"
    ]
    assert scan["reference_count"] == 0, [
        (
            row["source_path"],
            row["line"],
            row["kind"],
            row["target"],
        )
        for row in scan["references"]
    ]


def test_retained_bundle_evaluators_are_explicit_and_noncanonical() -> None:
    bundle11 = read("scripts/run_r5_bundle11r_runtime.py")
    bundle12 = read("scripts/run_r5_bundle12r_operating_evidence_gate.py")
    bundle13 = read("scripts/run_r5_bundle13r_evidence_backflow.py")
    sources = "\n".join(
        read(path)
        for path in (
            "src/research/r5_bundle11r_runtime.py",
            "src/research/r5_bundle12r_operating_evidence.py",
            "src/research/r5_bundle13r_evidence_backflow.py",
        )
    )
    assert 'parser.add_argument("--segment-plan", required=True)' in bundle11
    assert 'parser.add_argument("--output", required=True)' in bundle11
    assert 'parser.add_argument("--input", required=True' in bundle12
    assert 'parser.add_argument("--output-dir", required=True' in bundle12
    assert 'parser.add_argument("--bundle12r-context-dir", required=True)' in bundle13
    assert 'parser.add_argument("--reviewed-backfill", required=True)' in bundle13
    assert 'parser.add_argument("--output-dir", required=True)' in bundle13
    assert "workflow_state.yaml" not in sources
    assert "validate_workflow_state" not in sources


def test_standard_ci_keeps_full_history_and_drops_retired_routes() -> None:
    ci = read(".github/workflows/ci.yml")
    runtime = read(".github/workflows/r5_bundle11r_runtime.yml")
    assert "fetch-depth: 0" in ci
    assert "tests/test_r5_night_shift_" not in ci
    assert "reports/p1_6/r5_night_shift/" not in ci
    assert "reports/p1_6/r5_bundle17r" not in ci
    assert "test_r5_bundle11r_runtime_integration.py" not in runtime
    assert "scripts/audit_r5_bundle11r_target.py" not in runtime
    assert "scripts/integrate_r5_bundle11r_workflow.py" not in runtime
