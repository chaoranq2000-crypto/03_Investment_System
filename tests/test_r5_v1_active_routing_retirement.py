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


def test_transition_tests_and_retained_ci_are_equal_strength() -> None:
    tool = load_tool()
    authority = tool.parse_authority(ROOT)
    transition = tool.validate_transition_contract(ROOT, authority)

    assert transition["path_count"] == 3
    assert set(transition["paths"]) == tool.EXPECTED_A7
    assert all(
        row["equal_strength_retirement_assertions"] is True
        for row in transition["tests"]
    )
    assert all(transition["ci"].values())


def test_reference_scanner_only_exempts_proven_tmp_paths() -> None:
    tool = load_tool()
    candidate = "reports/workflow_runs/wf_20260703_stock_first_002837_invic"

    pure_tmp = f"""
from pathlib import Path
def test_case(tmp_path):
    target = tmp_path / {candidate!r} / "input.yaml"
    target.read_text(encoding="utf-8")
"""
    assert tool._python_references("pure_tmp.py", pure_tmp) == []

    scoped = f"""
from pathlib import Path
RUN = Path({candidate!r})
def test_case(tmp_path):
    run = tmp_path / RUN.name
    run.read_text(encoding="utf-8")
def active_reader():
    RUN.read_text(encoding="utf-8")
"""
    scoped_references = tool._python_references("scoped.py", scoped)
    assert len(scoped_references) == 1
    assert scoped_references[0]["kind"] == "candidate_worktree_path_operation"

    mixed = f"""
from pathlib import Path
ROOT = Path.cwd()
def active_reader(tmp_path, use_tmp):
    root = tmp_path if use_tmp else ROOT
    target = root / {candidate!r} / "input.yaml"
    target.read_text(encoding="utf-8")
"""
    mixed_references = tool._python_references("mixed.py", mixed)
    assert len(mixed_references) == 1
    assert mixed_references[0]["kind"] == "candidate_worktree_path_operation"

    relative_cwd = f"""
from pathlib import Path
Path({candidate!r}).read_text(encoding="utf-8")
"""
    assert len(tool._python_references("relative.py", relative_cwd)) == 1

    cli_default = f"""
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--run-root", default={candidate!r})
"""
    default_references = tool._python_references("default.py", cli_default)
    assert len(default_references) == 1
    assert default_references[0]["kind"] == "candidate_default_routing"

    protected_reviewed_input = f"""
from pathlib import Path
Path("data/reviewed_inputs/{tool.OLD_WORKFLOW_ID}/input.yaml").read_text(
    encoding="utf-8"
)
"""
    assert (
        tool._python_references(
            "protected_reviewed_input.py",
            protected_reviewed_input,
        )
        == []
    )


def test_text_scanner_separates_metadata_from_physical_paths() -> None:
    tool = load_tool()
    candidate = "wf_20260703_stock_first_002837_invic"
    assert (
        tool._text_references(
            "metadata.yaml",
            f"bundle12r_workflow_id: {candidate}\n",
        )
        == []
    )
    references = tool._text_references(
        "routing.yaml",
        "default_paths:\n"
        f"  input_path: reports/workflow_runs/{candidate}/input.yaml\n",
    )
    assert len(references) == 1
    assert references[0]["kind"] == "candidate_text_route_or_path"


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
