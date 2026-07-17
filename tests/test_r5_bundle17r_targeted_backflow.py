from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.r5_bundle17r_targeted_backflow import (  # noqa: E402
    BackflowContractError,
    compile_backflow,
    sha256_file,
    write_backflow_outputs,
)

POLICY = ROOT / "config" / "r5_bundle17r_backflow_routes.yaml"
BASELINE = "d61df6e457dc9bd02d13f1722a0630c9d6b134ea"
CASES = ("CASE-A", "CASE-B", "CASE-C", "CASE-D")


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def write_yaml(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def route_rows() -> list[dict[str, str]]:
    specs = [
        (10, "missing_official_source", "evidence", "evidence-ingest", "T1", "official source missing"),
        (10, "mapping_not_qualified", "qualification", "stock-deep-dive", "T5", "mapping qualification incomplete"),
        (10, "driver_coverage_low", "operating", "stock-deep-dive", "RP5", "economic driver revenue explained coverage"),
        (8, "overlap_unresolved", "operating", "stock-deep-dive", "RP5", "overlap double count allocation rule"),
        (8, "forecast_bridge_incomplete", "forecast", "forecasting", "RP6", "forecast bridge assumption traceability"),
        (7, "valuation_not_eligible", "valuation", "company-valuation", "RP6", "valuation peer DCF SOTP eligibility"),
        (5, "semantic_gate_failed", "reader", "quality-review", "RP8", "semantic reader traceability quality"),
        (5, "artifact_hash_mismatch", "activation", "research-orchestrator", "R5_bundle17r_targeted_backflow", "physical hash binding generation lock"),
    ]
    rows: list[dict[str, str]] = []
    sequence = 0
    for count, code, stage, owner, target, message in specs:
        for _ in range(count):
            sequence += 1
            case_id = CASES[(sequence - 1) % len(CASES)]
            rows.append(
                {
                    "case_id": case_id,
                    "code": f"{code}_{sequence:02d}",
                    "stage": stage,
                    "field": f"field_{sequence:02d}",
                    "owner_skill": owner,
                    "target_stage": target,
                    "message": message,
                    "requested_action": f"produce physical resolution artifact {sequence:02d}",
                }
            )
    assert len(rows) == 63
    return rows


def build_fixture(tmp_path: Path) -> dict[str, Path]:
    run = tmp_path / "reports" / "p1_6" / "r5_bundle17r" / "run"
    queue = run / "R5_bundle17r_backflow_queue.csv"
    matrix = run / "R5_bundle17r_case_matrix.csv"
    receipt = run / "R5_bundle17r_activation_receipt.json"
    lock = run / "R5_bundle17r_generation_lock.json"
    manifest = run / "backflow_manifest.yaml"

    write_csv(
        queue,
        route_rows(),
        [
            "case_id",
            "code",
            "stage",
            "field",
            "owner_skill",
            "target_stage",
            "message",
            "requested_action",
        ],
    )
    write_csv(
        matrix,
        [
            {
                "case_id": case_id,
                "issuer_ticker": f"TICKER-{index}",
                "engineering_pass": "False",
                "human_review_status": "not_ready",
                "issue_codes": "blocked",
            }
            for index, case_id in enumerate(CASES, start=1)
        ],
        ["case_id", "issuer_ticker", "engineering_pass", "human_review_status", "issue_codes"],
    )
    write_json(
        receipt,
        {
            "schema_version": "r5_bundle17r_activation_receipt_v1",
            "bundle_id": "R5_BUNDLE17R_ACTIVATION_RECEIPT",
            "baseline_commit": BASELINE,
            "run_id": "activation-test-run",
            "generation_id": "activation_gen_r5_bundle17r_test1234",
            "decision": "needs_targeted_backflow",
            "next_stage": "R5_bundle17r_targeted_backflow",
            "expected_case_count": 4,
            "case_count": 4,
            "engineering_pass_count": 0,
            "blocker_count": 63,
            "canonical_workflow_state_mutation_allowed": False,
            "sample_quality_allowed": False,
            "p2_allowed": False,
        },
    )
    write_json(
        lock,
        {
            "schema_version": "r5_bundle17r_generation_lock_v1",
            "bundle_id": "R5_BUNDLE17R_ACTIVATION_RECEIPT",
            "generation_id": "activation_gen_r5_bundle17r_test1234",
            "output_artifacts": {
                queue.name: {"sha256": sha256_file(queue), "size_bytes": queue.stat().st_size},
                matrix.name: {"sha256": sha256_file(matrix), "size_bytes": matrix.stat().st_size},
            },
            "release_boundaries": {
                "canonical_workflow_state_mutation_allowed": False,
                "sample_quality_allowed": False,
                "p2_allowed": False,
            },
        },
    )
    write_yaml(
        manifest,
        {
            "schema_version": "r5_bundle17r_backflow_manifest_v1",
            "baseline_commit": BASELINE,
            "run_id": "backflow-test-run",
            "activation": {
                "receipt": {"path": receipt.relative_to(tmp_path).as_posix(), "sha256": sha256_file(receipt)},
                "generation_lock": {"path": lock.relative_to(tmp_path).as_posix(), "sha256": sha256_file(lock)},
                "backflow_queue": {"path": queue.relative_to(tmp_path).as_posix(), "sha256": sha256_file(queue)},
                "case_matrix": {"path": matrix.relative_to(tmp_path).as_posix(), "sha256": sha256_file(matrix)},
            },
        },
    )
    return {
        "run": run,
        "queue": queue,
        "matrix": matrix,
        "receipt": receipt,
        "lock": lock,
        "manifest": manifest,
    }


def refresh_bindings(tmp_path: Path, paths: dict[str, Path]) -> None:
    lock = json.loads(paths["lock"].read_text(encoding="utf-8"))
    lock["output_artifacts"][paths["queue"].name] = {
        "sha256": sha256_file(paths["queue"]),
        "size_bytes": paths["queue"].stat().st_size,
    }
    lock["output_artifacts"][paths["matrix"].name] = {
        "sha256": sha256_file(paths["matrix"]),
        "size_bytes": paths["matrix"].stat().st_size,
    }
    write_json(paths["lock"], lock)
    manifest = yaml.safe_load(paths["manifest"].read_text(encoding="utf-8"))
    for key, path_key in (
        ("receipt", "receipt"),
        ("generation_lock", "lock"),
        ("backflow_queue", "queue"),
        ("case_matrix", "matrix"),
    ):
        manifest["activation"][key]["path"] = paths[path_key].relative_to(tmp_path).as_posix()
        manifest["activation"][key]["sha256"] = sha256_file(paths[path_key])
    write_yaml(paths["manifest"], manifest)


def compile_fixture(tmp_path: Path, paths: dict[str, Path]):
    return compile_backflow(repo_root=tmp_path, manifest_path=paths["manifest"], policy_path=POLICY)


def read_queue(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def test_valid_63_blocker_run_compiles_to_routed_work_orders(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    result = compile_fixture(tmp_path, paths)
    assert result.decision == "ready_for_targeted_backflow_execution"
    assert result.compiled_issue_count == 63
    assert result.routed_issue_count == 63
    assert result.manual_route_issue_count == 0
    assert result.validation_error_count == 0
    assert result.canonical_workflow_state_mutation_allowed is False
    assert result.sample_quality_allowed is False
    assert result.p2_allowed is False
    assert result.work_orders[-1].route_id == "rerun_16r_15r_14r_17r_chain"


def test_each_source_blocker_is_preserved_with_unique_issue_id(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    rows, fields = read_queue(paths["queue"])
    rows[1] = dict(rows[0])
    write_csv(paths["queue"], rows, fields)
    refresh_bindings(tmp_path, paths)
    result = compile_fixture(tmp_path, paths)
    assert result.compiled_issue_count == 63
    assert result.duplicate_row_count == 1
    assert len({issue.issue_id for issue in result.issues}) == 63


def test_outputs_are_byte_deterministic(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    result = compile_fixture(tmp_path, paths)
    out_a = tmp_path / "out_a"
    out_b = tmp_path / "out_b"
    write_backflow_outputs(out_a, result)
    write_backflow_outputs(out_b, result)
    files_a = {path.relative_to(out_a).as_posix(): path.read_bytes() for path in out_a.rglob("*") if path.is_file()}
    files_b = {path.relative_to(out_b).as_posix(): path.read_bytes() for path in out_b.rglob("*") if path.is_file()}
    assert files_a == files_b


def test_output_generation_lock_hashes_every_generated_artifact(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    result = compile_fixture(tmp_path, paths)
    output = tmp_path / "out"
    write_backflow_outputs(output, result)
    lock = json.loads((output / "R5_bundle17r_backflow_generation_lock.json").read_text(encoding="utf-8"))
    assert lock["release_boundaries"]["sample_quality_allowed"] is False
    assert lock["release_boundaries"]["p2_allowed"] is False
    for relative, metadata in lock["output_artifacts"].items():
        assert sha256_file(output / relative) == metadata["sha256"]


def test_physical_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    manifest = yaml.safe_load(paths["manifest"].read_text(encoding="utf-8"))
    manifest["activation"]["receipt"]["sha256"] = "0" * 64
    write_yaml(paths["manifest"], manifest)
    with pytest.raises(BackflowContractError, match="hash mismatch"):
        compile_fixture(tmp_path, paths)


def test_wrong_activation_decision_blocks_compilation(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    receipt = json.loads(paths["receipt"].read_text(encoding="utf-8"))
    receipt["decision"] = "activation_ready_for_exact_hash_human_review"
    write_json(paths["receipt"], receipt)
    refresh_bindings(tmp_path, paths)
    result = compile_fixture(tmp_path, paths)
    assert result.decision == "backflow_compilation_blocked"
    assert any(issue.field == "receipt.decision" for issue in result.validation_issues)


def test_release_boundary_truthy_blocks_compilation(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    receipt = json.loads(paths["receipt"].read_text(encoding="utf-8"))
    receipt["sample_quality_allowed"] = True
    write_json(paths["receipt"], receipt)
    refresh_bindings(tmp_path, paths)
    result = compile_fixture(tmp_path, paths)
    assert result.validation_error_count > 0
    assert any(issue.code == "release_boundary_not_false" for issue in result.validation_issues)


def test_generation_id_mismatch_blocks_compilation(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    lock = json.loads(paths["lock"].read_text(encoding="utf-8"))
    lock["generation_id"] = "different_generation"
    write_json(paths["lock"], lock)
    refresh_bindings(tmp_path, paths)
    result = compile_fixture(tmp_path, paths)
    assert any(issue.code == "activation_generation_id_mismatch" for issue in result.validation_issues)


def test_queue_count_mismatch_blocks_compilation(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    rows, fields = read_queue(paths["queue"])
    write_csv(paths["queue"], rows[:-1], fields)
    refresh_bindings(tmp_path, paths)
    result = compile_fixture(tmp_path, paths)
    assert result.decision == "backflow_compilation_blocked"
    assert any(issue.code == "backflow_queue_count_mismatch" for issue in result.validation_issues)


def test_missing_queue_column_is_contract_error(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    rows, fields = read_queue(paths["queue"])
    fields.remove("requested_action")
    for row in rows:
        row.pop("requested_action", None)
    write_csv(paths["queue"], rows, fields)
    refresh_bindings(tmp_path, paths)
    with pytest.raises(BackflowContractError, match="missing required columns"):
        compile_fixture(tmp_path, paths)


def test_queue_and_matrix_must_be_bound_in_activation_lock(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    lock = json.loads(paths["lock"].read_text(encoding="utf-8"))
    lock["output_artifacts"] = {}
    write_json(paths["lock"], lock)
    manifest = yaml.safe_load(paths["manifest"].read_text(encoding="utf-8"))
    manifest["activation"]["generation_lock"]["sha256"] = sha256_file(paths["lock"])
    write_yaml(paths["manifest"], manifest)
    result = compile_fixture(tmp_path, paths)
    codes = {issue.code for issue in result.validation_issues}
    assert "activation_output_not_bound_in_generation_lock" in codes


def test_case_matrix_count_mismatch_blocks_compilation(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    rows = [
        {
            "case_id": case_id,
            "issuer_ticker": "X",
            "engineering_pass": "False",
            "human_review_status": "not_ready",
            "issue_codes": "blocked",
        }
        for case_id in CASES[:3]
    ]
    write_csv(
        paths["matrix"],
        rows,
        ["case_id", "issuer_ticker", "engineering_pass", "human_review_status", "issue_codes"],
    )
    refresh_bindings(tmp_path, paths)
    result = compile_fixture(tmp_path, paths)
    assert any(issue.code == "case_matrix_count_mismatch" for issue in result.validation_issues)


def test_unknown_issue_is_retained_for_manual_route_review(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    rows, fields = read_queue(paths["queue"])
    rows[0].update(
        {
            "code": "opaque_problem",
            "stage": "opaque",
            "field": "opaque",
            "owner_skill": "unknown-skill",
            "target_stage": "unknown-stage",
            "message": "opaque problem",
            "requested_action": "manual inspection required",
        }
    )
    write_csv(paths["queue"], rows, fields)
    refresh_bindings(tmp_path, paths)
    result = compile_fixture(tmp_path, paths)
    assert result.decision == "needs_manual_route_review"
    assert result.manual_route_issue_count == 1
    assert any(issue.route_id == "manual_orchestrator_triage" for issue in result.issues)


def test_empty_requested_action_is_a_blocker_not_silently_dropped(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    rows, fields = read_queue(paths["queue"])
    rows[0]["requested_action"] = ""
    write_csv(paths["queue"], rows, fields)
    refresh_bindings(tmp_path, paths)
    result = compile_fixture(tmp_path, paths)
    assert result.decision == "backflow_compilation_blocked"
    assert any(issue.code == "backflow_row_required_value_missing" for issue in result.validation_issues)


def test_dependency_graph_is_acyclic_and_terminal_rerun_waits_for_all(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    result = compile_fixture(tmp_path, paths)
    terminal = next(order for order in result.work_orders if order.route_id == "rerun_16r_15r_14r_17r_chain")
    assert len(terminal.depends_on) == len(result.work_orders) - 1
    assert not any(issue.code == "work_order_dependency_cycle" for issue in result.validation_issues)


def test_forbidden_sample_path_cannot_be_used_as_activation_input(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    sample_dir = tmp_path / "reports" / "samples"
    sample_dir.mkdir(parents=True)
    sample_receipt = sample_dir / "receipt.json"
    shutil.copy2(paths["receipt"], sample_receipt)
    manifest = yaml.safe_load(paths["manifest"].read_text(encoding="utf-8"))
    manifest["activation"]["receipt"] = {
        "path": sample_receipt.relative_to(tmp_path).as_posix(),
        "sha256": sha256_file(sample_receipt),
    }
    write_yaml(paths["manifest"], manifest)
    with pytest.raises(BackflowContractError, match="forbidden artifact path"):
        compile_fixture(tmp_path, paths)


def test_manifest_baseline_must_match_policy_base(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    manifest = yaml.safe_load(paths["manifest"].read_text(encoding="utf-8"))
    manifest["baseline_commit"] = "a" * 40
    write_yaml(paths["manifest"], manifest)
    with pytest.raises(BackflowContractError, match="does not match policy base"):
        compile_fixture(tmp_path, paths)


def test_case_specific_and_suite_work_orders_keep_case_identity(tmp_path: Path) -> None:
    paths = build_fixture(tmp_path)
    rows, fields = read_queue(paths["queue"])
    rows[0]["case_id"] = ""
    write_csv(paths["queue"], rows, fields)
    refresh_bindings(tmp_path, paths)
    result = compile_fixture(tmp_path, paths)
    assert any(not order.case_id and order.issue_count > 0 for order in result.work_orders)
    assert any(order.case_id == "CASE-A" for order in result.work_orders)


def test_policy_and_manifest_yaml_are_parseable_and_schema_has_four_bindings() -> None:
    policy = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
    schema = yaml.safe_load((ROOT / "schemas" / "r5_bundle17r_backflow_manifest.schema.yaml").read_text(encoding="utf-8"))
    template = yaml.safe_load((ROOT / "templates" / "r5_bundle17r_backflow_manifest.example.yaml").read_text(encoding="utf-8"))
    assert policy["expected_activation"]["blocker_count"] == 63
    assert set(schema["properties"]["activation"]["properties"]) == {
        "receipt",
        "generation_lock",
        "backflow_queue",
        "case_matrix",
    }
    assert set(template["activation"]) == {
        "receipt",
        "generation_lock",
        "backflow_queue",
        "case_matrix",
    }
