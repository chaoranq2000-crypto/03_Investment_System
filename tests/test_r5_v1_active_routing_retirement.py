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
    current_contract = tool.verify_current_contract(ROOT)
    assert current_contract["canonical_sha256"] == tool.CURRENT_CONTRACT_SHA256
    assert current_contract["source_baseline"] == tool.CURRENT_PACKAGE_SOURCE_BASELINE
    contract = (ROOT / tool.CURRENT_CONTRACT_REL).read_text(encoding="utf-8")
    assert tool._section_paths(
        contract,
        "### A.8 `final_regression_repair_exact`",
        "### A.9 `controlled_stage_closure_authority`",
    ) == tool.EXPECTED_A8
    assert len(tool.EXPECTED_A8) == 14
    assert "### A.10 `extended_exact_cleanup_waves`" in contract
    assert "每个调用只能处理 manifest 当前 ordinal 的一个" in contract
    assert "没有合格候选时，记录 `extended_wave_count=0`" in contract


def test_transition_tests_and_retained_ci_are_equal_strength() -> None:
    tool = load_tool()
    authority = tool.parse_authority(ROOT)
    transition = tool.validate_transition_contract(ROOT, authority)

    assert transition["path_count"] == 3
    assert set(transition["paths"]) == tool.EXPECTED_A7
    assert all(
        row["source_commit"] == tool.DECOUPLING_CHECKPOINT
        for row in transition["tests"]
    )
    assert all(
        row["equal_strength_retirement_assertions"] is True
        for row in transition["tests"]
    )
    assert all(transition["ci"].values())


def test_retained_builders_require_explicit_workflow_roots() -> None:
    explicit_cli_paths = (
        "scripts/build_r5_bundle10_reader_pack.py",
        "scripts/build_r5_bundle9_forecast.py",
        "scripts/build_r5_reader_section_payloads.py",
        "src/ingest/business_segment_extraction.py",
        "src/qa/r4_disclosure_backflow_review.py",
    )
    for path in explicit_cli_paths:
        source = read(path)
        assert 'add_argument("--workflow-run", required=True)' in source, path

    valuation = read("scripts/build_r5_bundle9_valuation.py")
    assert 'f"reports/workflow_runs/{run_dir.name}/valuation"' in valuation

    backflow = read("src/research/r5_bundle13r_evidence_backflow.py")
    assert '(output_root.parent / "bundle12r_rerun_after_13r").as_posix()' in backflow


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

    indirect_call = f"""
from pathlib import Path
ROOT = Path.cwd()
RUN = ROOT / {candidate!r}
def validate_context(context_dir):
    return context_dir
validate_context(RUN)
"""
    indirect_references = tool._python_references("indirect.py", indirect_call)
    assert len(indirect_references) == 1
    assert indirect_references[0]["kind"] == "candidate_indirect_path_operation"

    bare_workflow_router = f"""
def load_by_workflow_id(workflow_id):
    return workflow_id
load_by_workflow_id({tool.OLD_WORKFLOW_ID!r})
"""
    assert len(
        tool._python_references("bare_workflow_router.py", bare_workflow_router)
    ) == 1

    explicit_nonrouting_metadata = f"""
def build_result(workflow_id, dropzone_root, output_run_dir):
    return workflow_id, dropzone_root, output_run_dir
build_result(
    workflow_id={tool.OLD_WORKFLOW_ID!r},
    dropzone_root="tests/fixtures/reviewed",
    output_run_dir="task-temp/output",
)
"""
    assert (
        tool._python_references(
            "explicit_nonrouting_metadata.py",
            explicit_nonrouting_metadata,
        )
        == []
    )

    default_branch = f"""
from pathlib import Path
ROOT = Path.cwd()
RUN = ROOT / {candidate!r}
def load_context(path=None):
    actual = path or RUN
    return actual.read_text(encoding="utf-8")
load_context()
"""
    default_references = tool._python_references("default_branch.py", default_branch)
    assert any(
        row["kind"] == "candidate_worktree_path_operation"
        for row in default_references
    )

    manifest_bound_blob = f"""
HISTORICAL_RUN = {candidate!r}
def test_case(historical_blob_bytes):
    return historical_blob_bytes(f"{{HISTORICAL_RUN}}/input.yaml")
"""
    assert tool._python_references("manifest_blob.py", manifest_bound_blob) == []

    manifest_bound_wrapper = f"""
import yaml
HISTORICAL_RUN = {candidate!r}
def load_historical_yaml(historical_blob_bytes, source_path):
    return yaml.safe_load(historical_blob_bytes(source_path))
def test_case(historical_blob_bytes):
    return load_historical_yaml(historical_blob_bytes, HISTORICAL_RUN + "/input.yaml")
"""
    assert (
        tool._python_references("manifest_blob_wrapper.py", manifest_bound_wrapper)
        == []
    )

    verified_git_blob = f"""
import hashlib
import subprocess
HISTORICAL_RUN = {candidate!r}
EXPECTED_OID = "abc"
EXPECTED_BYTES = 1
EXPECTED_SHA256 = "def"
def git_blob_bytes(relative_path):
    spec = f"baseline:{{relative_path}}"
    observed_oid = subprocess.check_output(["git", "rev-parse", spec], text=True)
    assert observed_oid.strip() == EXPECTED_OID
    payload = subprocess.check_output(["git", "cat-file", "blob", spec])
    assert len(payload) == EXPECTED_BYTES
    assert hashlib.sha256(payload).hexdigest() == EXPECTED_SHA256
    return payload
def test_case():
    return git_blob_bytes(HISTORICAL_RUN + "/input.yaml")
"""
    assert tool._python_references("verified_git_blob.py", verified_git_blob) == []


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
    assert {
        row["kind"] for row in references
    } == {
        "candidate_text_route_or_path",
        "candidate_yaml_artifact_path",
    }

    yaml_artifact = tool._text_references(
        "artifact.yaml",
        "artifacts:\n"
        f"  - reports/workflow_runs/{candidate}/input.yaml\n",
    )
    assert any(
        row["kind"] == "candidate_yaml_artifact_path"
        for row in yaml_artifact
    )


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
