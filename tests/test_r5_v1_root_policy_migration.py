from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT / "reports/p1_6/r5_v1_governance_cleanup/root_policy_migration.yaml"
)
SCHEMA = ROOT / "schemas/r5_v1_root_policy_migration.schema.json"
SOURCE_MAP = ROOT / "reports/p1_6/r5_v1_convergence/blocker_root_cause_map.yaml"
RECEIPT = ROOT / (
    "reports/p1_6/r5_v1_governance_cleanup/validation/"
    "blocker_root_reconciliation.yaml"
)
CANONICAL_INDEX = ROOT / "config/r5_readout_canonical_index.yaml"
SCRIPT = ROOT / "scripts/validate_r5_v1_root_policy_migration.py"

EXPECTED_DISPOSITIONS = {
    "external_approval_and_independent_receipts_absent": (
        20,
        "policy_retired",
        "none",
        "no_canonical_impact",
        [],
    ),
    "analyst_conclusions_pending": (
        20,
        "report_limitation",
        "section",
        "visible_nonblocking_report_limitation",
        [
            "historical_case_driver_analysis",
            "historical_case_forecast_analysis",
            "historical_case_overlap_analysis",
            "historical_case_semantic_analysis",
            "historical_case_valuation_analysis",
        ],
    ),
    "reviewed_evidence_acceptance_absent": (
        8,
        "unknown",
        "claim",
        "visible_unused_claim_unknown",
        [
            "historical_official_source_coverage",
            "historical_reviewed_evidence_coverage",
        ],
    ),
    "suite_exact_hash_review_pending": (
        3,
        "not_required_for_active_v1",
        "none",
        "no_canonical_impact",
        [],
    ),
    "legacy_quality_case_id_contract_gap": (
        4,
        "historical_backlog",
        "none",
        "no_canonical_impact",
        [],
    ),
    "legacy_generation_id_pointer_contract_gap": (
        4,
        "historical_backlog",
        "none",
        "no_canonical_impact",
        [],
    ),
    "legacy_quality_ready_pointer_contract_gap": (
        4,
        "historical_backlog",
        "none",
        "no_canonical_impact",
        [],
    ),
}


def load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_r5_v1_root_policy_migration",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def load_documents() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        load_yaml(MIGRATION),
        json.loads(SCHEMA.read_text(encoding="utf-8")),
        load_yaml(SOURCE_MAP),
    )


def test_migration_conforms_to_strict_seven_root_schema() -> None:
    validator = load_validator()
    migration, schema, _ = load_documents()
    validator.validate_schema(migration, schema, schema)

    assert schema["additionalProperties"] is False
    root_schema = schema["$defs"]["migration_root"]
    assert root_schema["additionalProperties"] is False
    assert schema["properties"]["migration_roots"]["minItems"] == 7
    assert schema["properties"]["migration_roots"]["maxItems"] == 7
    assert migration["migration_is_historical_resolution"] is False
    assert len(migration["migration_roots"]) == 7

    invalid = copy.deepcopy(migration)
    invalid["occurrences"] = []
    with pytest.raises(validator.MigrationValidationError, match="extra keys"):
        validator.validate_schema(invalid, schema, schema)

    invalid = copy.deepcopy(migration)
    invalid["migration_roots"][0]["candidate_decisions"] = []
    with pytest.raises(validator.MigrationValidationError, match="extra keys"):
        validator.validate_schema(invalid, schema, schema)

    invalid = copy.deepcopy(migration)
    invalid["migration_roots"] = invalid["migration_roots"][:-1]
    with pytest.raises(validator.MigrationValidationError, match="too few"):
        validator.validate_schema(invalid, schema, schema)


def test_exact_root_dispositions_follow_current_goal_truth_table() -> None:
    validator = load_validator()
    migration, schema, source = load_documents()
    receipt = validator.validate_documents(ROOT, migration, schema, source)
    rows = {row["root_cause_id"]: row for row in migration["migration_roots"]}

    assert set(rows) == set(EXPECTED_DISPOSITIONS)
    assert all(row["historical_root_status"] == "open" for row in rows.values())
    assert all(row["historical_resolved"] is False for row in rows.values())
    assert all(row["blocks_current_goal"] is False for row in rows.values())
    assert all("severity" not in row for row in rows.values())
    for root_id, expected in EXPECTED_DISPOSITIONS.items():
        count, disposition, scope, impact, capabilities = expected
        row = rows[root_id]
        assert row["primary_occurrence_count"] == count
        assert row["active_disposition"] == disposition
        assert row["impact_scope"] == scope
        assert row["active_v1_impact"] == impact
        assert row["affected_capabilities"] == capabilities

    assert receipt["policy_summary"] == {
        "policy_retired_root_count": 1,
        "report_limitation_root_count": 1,
        "visible_unknown_root_count": 1,
        "not_required_for_active_v1_root_count": 1,
        "historical_backlog_root_count": 3,
        "active_defect_root_count": 0,
        "historical_engineering_root_count": 3,
        "historical_resolved_occurrence_count": 0,
    }


def test_dynamic_reconciliation_derives_63_20_6_69_43_0_from_rows() -> None:
    validator = load_validator()
    receipt = validator.validate_repository(ROOT)
    dynamic = receipt["dynamic_reconciliation"]
    assert {
        key: dynamic[key]
        for key in (
            "occurrence_count",
            "dependency_blocked_occurrence_count",
            "parent_work_order_count",
            "carry_forward_task_count",
            "candidate_ready_count",
            "historical_resolved_occurrence_count",
            "node_count",
            "edge_count",
            "duplicate_reference_count",
        )
    } == {
        "occurrence_count": 63,
        "dependency_blocked_occurrence_count": 20,
        "parent_work_order_count": 6,
        "carry_forward_task_count": 69,
        "candidate_ready_count": 43,
        "historical_resolved_occurrence_count": 0,
        "node_count": 69,
        "edge_count": 532,
        "duplicate_reference_count": 6,
    }
    coverage = {
        row["root_cause_id"]: row["source_occurrence_count"]
        for row in receipt["root_coverage"]
    }
    assert coverage == {
        root_id: expected[0]
        for root_id, expected in EXPECTED_DISPOSITIONS.items()
    }
    assert dynamic["root_coverage_count"] == dynamic["root_cause_count"] == 7
    assert dynamic["orphan_root_count"] == 0
    assert dynamic["duplicate_node_id_count"] == 0
    assert dynamic["dependency_cycle_count"] == 0
    assert dynamic["duplicate_reference_cycle_count"] == 0


def test_declared_counts_cannot_override_dynamic_source_truth() -> None:
    validator = load_validator()
    migration, schema, source = load_documents()

    mutants: list[dict[str, Any]] = []

    declared = copy.deepcopy(source)
    declared["reconciliation"]["occurrence_count"] = 64
    mutants.append(declared)

    classification = copy.deepcopy(source)
    row = next(
        item
        for item in classification["occurrences"]
        if item["source_classification"] == "dependency_blocked"
    )
    row["source_classification"] = "analysis_required"
    classification["reconciliation"]["dependency_blocked_occurrence_count"] = 19
    mutants.append(classification)

    candidate = copy.deepcopy(source)
    row = next(
        item
        for item in candidate["occurrences"]
        if item["baseline_state"] == "candidate_ready"
    )
    row["baseline_state"] = "dependency_blocked"
    candidate["reconciliation"]["candidate_ready_count"] = 42
    mutants.append(candidate)

    resolved = copy.deepcopy(source)
    resolved["occurrences"][0]["baseline_resolved"] = True
    resolved["reconciliation"]["baseline_resolved_occurrence_count"] = 1
    mutants.append(resolved)

    missing_parent = copy.deepcopy(source)
    missing_parent["parent_work_orders"].pop()
    missing_parent["reconciliation"]["parent_work_order_count"] = 5
    missing_parent["reconciliation"]["carry_forward_task_count"] = 68
    missing_parent["reconciliation"]["source_node_count"] = 68
    mutants.append(missing_parent)

    duplicate_provenance = copy.deepcopy(source)
    duplicate_provenance["occurrences"][1]["source_occurrence_id"] = (
        duplicate_provenance["occurrences"][0]["source_occurrence_id"]
    )
    mutants.append(duplicate_provenance)

    duplicate_carry_forward = copy.deepcopy(source)
    duplicate_carry_forward["occurrences"][1]["carry_forward_id"] = (
        duplicate_carry_forward["occurrences"][0]["carry_forward_id"]
    )
    mutants.append(duplicate_carry_forward)

    unknown_root = copy.deepcopy(source)
    unknown_root["occurrences"][0]["primary_root_id"] = "unknown_root"
    mutants.append(unknown_root)

    for mutant in mutants:
        with pytest.raises(validator.MigrationValidationError):
            validator.validate_documents(
                ROOT,
                migration,
                schema,
                mutant,
                verify_source_binding=False,
            )


def test_dependency_and_duplicate_graph_mutations_fail_closed() -> None:
    validator = load_validator()
    migration, schema, source = load_documents()

    orphan = copy.deepcopy(source)
    orphan["occurrences"][0]["blocked_by"].append("ns02_t30_occ_ffffffffffffffff")

    duplicate_dependency = copy.deepcopy(source)
    dependent = next(
        item for item in duplicate_dependency["occurrences"] if item["blocked_by"]
    )
    dependent["blocked_by"].append(dependent["blocked_by"][0])

    self_cycle = copy.deepcopy(source)
    self_cycle["occurrences"][0]["blocked_by"].append(
        self_cycle["occurrences"][0]["carry_forward_id"]
    )

    two_node_cycle = copy.deepcopy(source)
    cycle_rows = [
        item
        for item in two_node_cycle["occurrences"]
        if not item["blocked_by"]
    ][:2]
    cycle_rows[0]["blocked_by"].append(cycle_rows[1]["carry_forward_id"])
    cycle_rows[1]["blocked_by"].append(cycle_rows[0]["carry_forward_id"])

    duplicate_chain = copy.deepcopy(source)
    duplicate_rows = [
        item for item in duplicate_chain["occurrences"] if item["duplicate_of"]
    ]
    canonical_id = duplicate_rows[0]["duplicate_of"]
    canonical = next(
        item
        for item in duplicate_chain["occurrences"]
        if item["carry_forward_id"] == canonical_id
    )
    canonical["duplicate_of"] = duplicate_rows[1]["carry_forward_id"]

    bad_groups = copy.deepcopy(source)
    bad_groups["dependency_groups"]["suite"] = []

    for mutant in (
        orphan,
        duplicate_dependency,
        self_cycle,
        two_node_cycle,
        duplicate_chain,
        bad_groups,
    ):
        with pytest.raises(validator.MigrationValidationError):
            validator.validate_documents(
                ROOT,
                migration,
                schema,
                mutant,
                verify_source_binding=False,
            )


def test_semantic_mutations_cannot_create_active_defect_or_fake_resolution() -> None:
    validator = load_validator()
    migration, schema, source = load_documents()

    mutants: list[dict[str, Any]] = []

    missing_root = copy.deepcopy(migration)
    missing_root["migration_roots"].pop()
    mutants.append(missing_root)

    duplicate_root = copy.deepcopy(migration)
    duplicate_root["migration_roots"][1]["root_cause_id"] = (
        duplicate_root["migration_roots"][0]["root_cause_id"]
    )
    mutants.append(duplicate_root)

    active_defect = copy.deepcopy(migration)
    active_defect["migration_roots"][0]["active_disposition"] = "active_defect"
    active_defect["migration_roots"][0]["impact_scope"] = "workflow"
    active_defect["migration_roots"][0]["active_v1_impact"] = (
        "current_goal_blocking"
    )
    active_defect["migration_roots"][0]["blocks_current_goal"] = True
    active_defect["migration_roots"][0]["affected_capabilities"] = [
        "workflow_materialization"
    ]
    mutants.append(active_defect)

    fake_resolution = copy.deepcopy(migration)
    fake_resolution["migration_roots"][0]["historical_resolved"] = True
    mutants.append(fake_resolution)

    blocking_unknown = copy.deepcopy(migration)
    unknown = next(
        row
        for row in blocking_unknown["migration_roots"]
        if row["active_disposition"] == "unknown"
    )
    unknown["blocks_current_goal"] = True
    mutants.append(blocking_unknown)

    hidden_overlay = copy.deepcopy(migration)
    hidden_overlay["migration_roots"][0]["next_step"] = "x" * 513
    mutants.append(hidden_overlay)

    for mutant in mutants:
        with pytest.raises(validator.MigrationValidationError):
            validator.validate_documents(ROOT, mutant, schema, source)


def test_p3_references_are_policy_examples_not_historical_resolution() -> None:
    validator = load_validator()
    migration, schema, source = load_documents()
    receipt = validator.validate_documents(ROOT, migration, schema, source)
    rows = {row["root_cause_id"]: row for row in migration["migration_roots"]}

    traced = {
        "analyst_conclusions_pending",
        "reviewed_evidence_acceptance_absent",
    }
    for root_id, row in rows.items():
        paths = {
            Path(str(ref["path"])).as_posix()
            for ref in row["evidence_references"]
        }
        assert not any("r5_night_shift" in path for path in paths)
        assert not any("r5_bundle17r" in path for path in paths)
        if root_id in traced:
            assert row["current_limitation_references"]
            assert all(
                str(path).startswith(
                    "reports/workflow_runs/"
                    "wf_20260725_stock_first_002837_v1_policy_refresh/"
                )
                for path in row["current_limitation_references"]
            )
            assert any(
                ref["role"] == "current_limitation_example"
                for ref in row["evidence_references"]
            )
        else:
            assert row["current_limitation_references"] == []

    assert receipt["current_limitation_trace"]["historical_resolution_claimed"] is False
    assert set(receipt["current_limitation_trace"]["paths"]) == {
        "reports/workflow_runs/"
        "wf_20260725_stock_first_002837_v1_policy_refresh/"
        "inputs/input_provenance.csv",
        "reports/workflow_runs/"
        "wf_20260725_stock_first_002837_v1_policy_refresh/"
        "research/limitations.yaml",
        "reports/workflow_runs/"
        "wf_20260725_stock_first_002837_v1_policy_refresh/"
        "research/stock_report_draft.md",
    }
    assert receipt["migration"]["migration_is_historical_resolution"] is False
    assert receipt["guards"]["historical_resolution_delta"] == 0
    assert receipt["guards"]["system_v1_complete_claimed"] is False


def test_source_binding_is_exact_and_durable() -> None:
    validator = load_validator()
    migration, schema, source = load_documents()
    receipt = validator.validate_documents(ROOT, migration, schema, source)
    binding = receipt["source_root_map"]
    assert binding == {
        "path": "reports/p1_6/r5_v1_convergence/blocker_root_cause_map.yaml",
        "sha256": (
            "39aadff44cf51d1ad5607d8ec8481bbab42650723eaf5a981415df0ee3facacf"
        ),
        "engineering_source_revision": (
            "f60f220ae252262a537c612ce193fc779901984b"
        ),
        "git_blob_oid": "526d9964a95ddc866fa960a1b9556e720ca80178",
        "matches_engineering_source_blob": True,
    }
    assert hashlib.sha256(SOURCE_MAP.read_bytes()).hexdigest() == binding["sha256"]


def test_receipt_is_deterministic_aggregate_only_and_checked_in() -> None:
    validator = load_validator()
    migration, schema, source = load_documents()
    first = validator.validate_documents(ROOT, migration, schema, source)
    second = validator.validate_documents(ROOT, migration, schema, source)
    assert first == second
    rendered = validator.render_receipt(first)
    assert rendered == validator.render_receipt(second)
    assert "ns02_t30_occ_" not in rendered
    assert "BF17R-I-" not in rendered
    assert "candidate_registry" not in rendered
    assert RECEIPT.is_file()
    assert RECEIPT.read_text(encoding="utf-8") == rendered

    changed = copy.deepcopy(migration)
    changed["migration_roots"][0]["next_step"] += " No historical action is executed."
    changed_receipt = validator.validate_documents(ROOT, changed, schema, source)
    assert (
        first["migration"]["semantic_sha256"]
        != changed_receipt["migration"]["semantic_sha256"]
    )


def test_receipt_output_is_limited_to_canonical_path(tmp_path: Path) -> None:
    validator = load_validator()
    receipt = validator.validate_repository(ROOT)
    forbidden = tmp_path / "blocker_root_reconciliation.yaml"
    with pytest.raises(validator.MigrationValidationError, match="output must be"):
        validator._write_receipt(ROOT, forbidden, receipt)
    assert not forbidden.exists()


def test_canonical_index_points_to_migration_and_reconciliation() -> None:
    index = load_yaml(CANONICAL_INDEX)
    pointer = index["policy_migrations"]["blocker_root_policy"]
    assert pointer == {
        "path": (
            "reports/p1_6/r5_v1_governance_cleanup/"
            "root_policy_migration.yaml"
        ),
        "reconciliation_path": (
            "reports/p1_6/r5_v1_governance_cleanup/validation/"
            "blocker_root_reconciliation.yaml"
        ),
        "source_root_map_path": (
            "reports/p1_6/r5_v1_convergence/blocker_root_cause_map.yaml"
        ),
        "decision": "pass",
    }
