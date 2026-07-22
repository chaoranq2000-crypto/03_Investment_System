from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "reports/p1_6/r5_v1_convergence/blocker_root_cause_map.yaml"
SCHEMA_PATH = ROOT / "schemas/r5_v1_blocker_root_cause_map.schema.json"
OCCURRENCE_PATH = ROOT / (
    "reports/p1_6/r5_night_shift/r5_overnight_02_20260720/"
    "backflow/occurrence_inventory.json"
)
DAG_PATH = ROOT / (
    "reports/p1_6/r5_night_shift/r5_overnight_02_20260720/"
    "backflow/dependency_dag.json"
)
QUEUE_METRICS_PATH = ROOT / (
    "reports/p1_6/r5_night_shift/r5_overnight_02_20260720/"
    "backflow/queue_metrics.json"
)
NIGHT04_ROOT = ROOT / "reports/p1_6/r5_night_shift/r5_overnight_04_20260722"
NIGHT05_ROOT = ROOT / "reports/p1_6/r5_night_shift/r5_overnight_05_20260723"
QUEUE_PATH = NIGHT05_ROOT / "next_night_queue.yaml"


EXPECTED_BINDINGS = {
    "night02_source_queue": (
        "reports/p1_6/r5_bundle17r/activation_run_a/R5_bundle17r_backflow_queue.csv",
        "da23cb727e020946a79d4a7b93e7af00326010acb81cdfec7dfe1bbd2dd76107",
    ),
    "night02_occurrence_inventory": (
        "reports/p1_6/r5_night_shift/r5_overnight_02_20260720/backflow/occurrence_inventory.json",
        "aa57d84ffae7798803c8604cc4150b79ee0b3fa5d0d59a9ef4559c34dff42ba6",
    ),
    "night02_dependency_dag": (
        "reports/p1_6/r5_night_shift/r5_overnight_02_20260720/backflow/dependency_dag.json",
        "23ff698741c90de20c29aa0e425aaa3f50f1259569e5b5362c70540635490859",
    ),
    "night02_queue_metrics": (
        "reports/p1_6/r5_night_shift/r5_overnight_02_20260720/backflow/queue_metrics.json",
        "4d97d4251224f4050d8e1efd4dd2bdd2f75a495b42cec72a062d0b3f95bfa868",
    ),
    "night04_taxonomy_audit": (
        "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/queue/taxonomy_audit.json",
        "ea626394ec7e1c9ae94f70359127ca81f02122e5aa3bab43263a6f63ed5f20a9",
    ),
    "night04_truth_snapshot": (
        "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/queue/truth_snapshot.json",
        "139c6a30c67affdde6e49c12ef9f287fe3b72b28864dfc85f9a060bcb3993b18",
    ),
    "night04_blocker_ledger": (
        "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/progress/blocker_ledger.json",
        "221cfd76fdeac2163be1817ab5574af36e813d26021e52669d2d8235466b677d",
    ),
    "night04_candidate_registry": (
        "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/review_control/candidate_registry.yaml",
        "c4577d21fa83951b6d7b001e1164b5e307f6bf388406a0cef7efc0c17ebf2fa1",
    ),
    "night04_dependency_recompute": (
        "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/execution/dependency_recompute.json",
        "7e8b3b224e0a9be8f5185e8050e23b76570baa02d1155df6b174e35649cedac3",
    ),
    "night04_parent_recompute": (
        "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/execution/parent_recompute.json",
        "5506683b4e9a98e9c79570ac62cb0945768838410393592a121a23a1d3d8f2d4",
    ),
    "night04_pointer_conflict_matrix": (
        "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/pointer_prevalidation/conflict_matrix.yaml",
        "ac1b65be239531a8d0bf2d46c2f89183d9c7f6f90d5c9b3332e31ec4f749be3f",
    ),
    "night04_pointer_dry_run_truth": (
        "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/pointer_prevalidation/dry_run_truth_receipt.json",
        "a99818f7fdc64fb6e53c452bb2cf80cbc4a73dc146f2fa2e181d6e5901bff1bd",
    ),
    "night04_carry_forward_queue": (
        "reports/p1_6/r5_night_shift/r5_overnight_04_20260722/next_night_queue.yaml",
        "57bef7dd3969d8b5405fdf9570e7792d11dd5b33f9a061f8664b513250f60700",
    ),
    "night05_carry_forward_queue": (
        "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/next_night_queue.yaml",
        "b7ce5bb3f1e1cd7e0081152d562583a7d89f677fac5ab66b79e2811942ce979a",
    ),
    "night05_blocker_ledger": (
        "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/progress/blocker_ledger.json",
        "114e2dac7d1f25edd2103e8c3e239177077fba61455c6c0d64862db60ff0a8d6",
    ),
    "night05_mission_state": (
        "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/mission_state.yaml",
        "3958ebee5a35df093987332f2a9e444c76c575ddea1b013054b633579586b866",
    ),
    "night05_morning_readout": (
        "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/morning_readout.json",
        "aa43cc1b4883392d3760ed1b4df73e3f6b4a0882154461f6dfed249849f112b7",
    ),
    "night05_recompute_summary": (
        "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/execution/recompute_summary.json",
        "f0611bd3afe6b65144ccd6fe4faa61815f468c2fbd3d3472037328dab755bcd1",
    ),
    "night05_change_log": (
        "reports/p1_6/r5_night_shift/r5_overnight_05_20260723/progress/change_log.json",
        "4513964245d9f6fd3b1dbf9888d0bd815ac0e97e699b186d2db10070c6993b4f",
    ),
}


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    raise AssertionError(f"unsupported schema type: {expected}")


def validate_schema(
    value: Any, schema: dict[str, Any], root_schema: dict[str, Any], path: str = "$"
) -> None:
    if "$ref" in schema:
        ref = schema["$ref"]
        assert ref.startswith("#/")
        target: Any = root_schema
        for part in ref[2:].split("/"):
            target = target[part]
        validate_schema(value, target, root_schema, path)
        return

    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = (
            expected_type if isinstance(expected_type, list) else [expected_type]
        )
        assert any(_type_matches(value, item) for item in expected_types), (
            f"{path}: expected {expected_types}, got {type(value).__name__}"
        )

    if "const" in schema:
        assert value == schema["const"], f"{path}: const mismatch"
    if "enum" in schema:
        assert value in schema["enum"], f"{path}: enum mismatch {value!r}"
    if isinstance(value, str):
        if "minLength" in schema:
            assert len(value) >= schema["minLength"], f"{path}: string too short"
        if "pattern" in schema:
            assert re.fullmatch(schema["pattern"], value), f"{path}: pattern mismatch"
    if isinstance(value, int) and not isinstance(value, bool) and "minimum" in schema:
        assert value >= schema["minimum"], f"{path}: below minimum"

    if isinstance(value, dict):
        required = schema.get("required", [])
        missing = set(required) - set(value)
        assert not missing, f"{path}: missing keys {sorted(missing)}"
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(properties)
            assert not extra, f"{path}: extra keys {sorted(extra)}"
        for key, item in value.items():
            if key in properties:
                validate_schema(item, properties[key], root_schema, f"{path}.{key}")

    if isinstance(value, list):
        if "minItems" in schema:
            assert len(value) >= schema["minItems"], f"{path}: too few items"
        if schema.get("uniqueItems"):
            rendered = [canonical_json_bytes(item) for item in value]
            assert len(rendered) == len(set(rendered)), f"{path}: duplicate items"
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                validate_schema(item, item_schema, root_schema, f"{path}[{index}]")


def assert_acyclic(nodes: set[str], edges: set[tuple[str, str]]) -> None:
    outgoing: dict[str, set[str]] = defaultdict(set)
    indegree = {node: 0 for node in nodes}
    for source, target in edges:
        assert source in nodes
        assert target in nodes
        assert source != target
        if target not in outgoing[source]:
            outgoing[source].add(target)
            indegree[target] += 1
    ready = deque(sorted(node for node, degree in indegree.items() if degree == 0))
    visited = 0
    while ready:
        node = ready.popleft()
        visited += 1
        for target in sorted(outgoing[node]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    assert visited == len(nodes)


def test_map_conforms_to_its_strict_dependency_free_schema() -> None:
    document = load_yaml(MAP_PATH)
    schema = load_json(SCHEMA_PATH)
    validate_schema(document, schema, schema)

    assert schema["additionalProperties"] is False
    assert schema["$defs"]["root_cause"]["additionalProperties"] is False
    assert schema["$defs"]["occurrence"]["additionalProperties"] is False
    assert schema["$defs"]["parent_work_order"]["additionalProperties"] is False
    categories = schema["$defs"]["root_cause"]["properties"]["category"]["enum"]
    assert categories == [
        "engineering_defect",
        "obtainable_evidence_gap",
        "issuer_not_disclosed",
        "human_judgment_pending",
    ]

    invalid = copy.deepcopy(document)
    invalid["unexpected"] = True
    with pytest.raises(AssertionError, match="extra keys"):
        validate_schema(invalid, schema, schema)


def test_all_source_bindings_are_exact_and_physically_hash_bound() -> None:
    document = load_yaml(MAP_PATH)
    bindings = {
        item["role"]: (item["path"], item["sha256"])
        for item in document["source_bindings"]
    }
    assert bindings == EXPECTED_BINDINGS
    for relative, expected_hash in bindings.values():
        source = ROOT / relative
        assert source.is_file(), relative
        assert sha256_file(source) == expected_hash, relative


def test_occurrences_and_parents_preserve_all_69_ids_and_532_edges() -> None:
    document = load_yaml(MAP_PATH)
    inventory = load_json(OCCURRENCE_PATH)
    dag = load_json(DAG_PATH)
    queue = load_yaml(QUEUE_PATH)
    source_occurrences = {
        item["blocker_occurrence_id"]: item for item in inventory["occurrences"]
    }
    queue_tasks = {item["id"]: item for item in queue["tasks"]}
    mapped_occurrences = {
        item["carry_forward_id"]: item for item in document["occurrences"]
    }
    mapped_parents = {
        item["carry_forward_id"]: item for item in document["parent_work_orders"]
    }

    assert len(source_occurrences) == 63
    assert len(mapped_occurrences) == 63
    assert len(mapped_parents) == 6
    assert set(mapped_occurrences) | set(mapped_parents) == set(queue_tasks)
    assert set(queue_tasks) == {item["task_id"] for item in dag["nodes"]}

    for carry_id, mapped in mapped_occurrences.items():
        source = source_occurrences[mapped["source_occurrence_id"]]
        task = queue_tasks[carry_id]
        assert task["title"].endswith(mapped["source_occurrence_id"])
        assert carry_id == (
            "ns02_t30_occ_"
            + hashlib.sha256(mapped["source_occurrence_id"].encode("utf-8")).hexdigest()[:16]
        )
        assert mapped["source_work_order_id"] == source["work_order_id"]
        assert mapped["case_id"] == source["case_id"]
        assert mapped["issuer_ticker"] == (source["issuer_ticker"] or None)
        assert mapped["source_classification"] == source["classification"]
        assert mapped["field"] == source["field"]
        assert mapped["baseline_state"] == task["night04_state"]
        assert mapped["blocked_by"] == task["depends_on"]
        assert mapped["baseline_resolved"] is False
        assert mapped["resolution_receipt_sha256"] is None
        assert mapped["source_artifact_path"] == (source["source_artifact_path"] or None)
        assert mapped["source_artifact_sha256"] == (
            source["source_artifact_sha256"] or None
        )

    for carry_id, mapped in mapped_parents.items():
        task = queue_tasks[carry_id]
        assert mapped["blocked_by"] == task["depends_on"]
        assert mapped["baseline_state"] == "parent_pending"
        assert mapped["baseline_resolved"] is False
        assert mapped["resolution_receipt_sha256"] is None
        assert f"source_work_order_id={mapped['source_work_order_id']}" in task["notes"]

    mapped_edges = {
        (dependency, carry_id)
        for carry_id, item in {**mapped_occurrences, **mapped_parents}.items()
        for dependency in item["blocked_by"]
    }
    source_edges = {(item["from"], item["to"]) for item in dag["edges"]}
    assert mapped_edges == source_edges
    assert len(mapped_edges) == 532
    assert_acyclic(set(queue_tasks), mapped_edges)


def test_dependency_groups_duplicates_and_references_are_exact_and_acyclic() -> None:
    document = load_yaml(MAP_PATH)
    queue = load_yaml(QUEUE_PATH)
    queue_tasks = {item["id"]: item for item in queue["tasks"]}
    mapped = {item["carry_forward_id"]: item for item in document["occurrences"]}
    root_ids = {item["root_cause_id"] for item in document["root_causes"]}

    expected_groups: dict[str, list[str]] = {}
    for item in document["occurrences"]:
        if item["source_classification"] != "dependency_blocked":
            continue
        key = "suite" if item["case_id"] == "__suite__" else item["case_id"]
        previous = expected_groups.setdefault(key, item["blocked_by"])
        assert previous == item["blocked_by"]
    assert document["dependency_groups"] == expected_groups

    for item in document["occurrences"]:
        assert item["primary_root_id"] in root_ids
        assert all(reference in queue_tasks for reference in item["blocked_by"])
        if item["duplicate_of"] is not None:
            assert item["duplicate_of"] in mapped
            assert item["duplicate_of"] != item["carry_forward_id"]
            assert mapped[item["duplicate_of"]]["primary_root_id"] == item["primary_root_id"]

    expected_duplicates = {
        "ns02_t30_occ_6b198842cf80755a": "ns02_t30_occ_3caf2ad00e1b6285",
        "ns02_t30_occ_c7f5c80f4b2e7a9c": "ns02_t30_occ_3caf2ad00e1b6285",
        "ns02_t30_occ_c8af30bbe2f10e8a": "ns02_t30_occ_3caf2ad00e1b6285",
        "ns02_t30_occ_d2ef6aeae1113c9c": "ns02_t30_occ_99e77539490b01ad",
        "ns02_t30_occ_db819651b1640db8": "ns02_t30_occ_99e77539490b01ad",
        "ns02_t30_occ_e3fefccd3e77fd5a": "ns02_t30_occ_99e77539490b01ad",
    }
    actual_duplicates = {
        item["carry_forward_id"]: item["duplicate_of"]
        for item in document["occurrences"]
        if item["duplicate_of"] is not None
    }
    assert actual_duplicates == expected_duplicates

    conflict = load_yaml(
        NIGHT04_ROOT / "pointer_prevalidation/conflict_matrix.yaml"
    )
    same_patch_edges = {
        frozenset((item["left"], item["right"]))
        for item in conflict["pairs"]
        if item["same_patch"]
    }
    for duplicate, canonical in actual_duplicates.items():
        assert frozenset((duplicate, canonical)) in same_patch_edges

    duplicate_edges = {(canonical, duplicate) for duplicate, canonical in actual_duplicates.items()}
    assert_acyclic(set(mapped), duplicate_edges)


def test_root_assignments_are_complete_truthful_and_leave_no_active_engineering_defect() -> None:
    document = load_yaml(MAP_PATH)
    roots = {item["root_cause_id"]: item for item in document["root_causes"]}
    assignments = Counter(item["primary_root_id"] for item in document["occurrences"])
    categories = Counter(item["category"] for item in roots.values())
    reconciliation = document["reconciliation"]

    assert len(roots) == reconciliation["root_cause_count"] == 7
    assert set(assignments) == set(roots)
    assert assignments == Counter(
        {item["root_cause_id"]: item["primary_occurrence_count"] for item in roots.values()}
    )
    assert dict(categories) == {
        "human_judgment_pending": 3,
        "obtainable_evidence_gap": 1,
        "engineering_defect": 3,
    }
    assert reconciliation["root_category_counts"] == {
        "engineering_defect": 3,
        "obtainable_evidence_gap": 1,
        "issuer_not_disclosed": 0,
        "human_judgment_pending": 3,
    }
    assert not any(item["category"] == "issuer_not_disclosed" for item in roots.values())

    open_active_engineering = [
        item
        for item in roots.values()
        if item["category"] == "engineering_defect"
        and item["status"] == "open"
        and item["affects_system_v1"]
    ]
    open_historical_engineering = [
        item
        for item in roots.values()
        if item["category"] == "engineering_defect"
        and item["status"] == "open"
        and not item["affects_system_v1"]
    ]
    assert len(open_active_engineering) == reconciliation[
        "open_active_v1_engineering_root_count"
    ] == 0
    assert len(open_historical_engineering) == reconciliation[
        "open_historical_engineering_root_count"
    ] == 3

    for item in roots.values():
        assert item["evidence_paths"]
        assert item["active_v1_evidence_paths"]
        assert all((ROOT / path).is_file() for path in item["evidence_paths"])
        assert all((ROOT / path).is_file() for path in item["active_v1_evidence_paths"])
        if item["status"] == "resolved":
            assert item["resolution_evidence_paths"]
        else:
            assert item["resolution_evidence_paths"] == []

    ledger = load_json(NIGHT05_ROOT / "progress/blocker_ledger.json")
    source_blocker_ids = {
        blocker_id
        for item in roots.values()
        for blocker_id in item["source_blocker_ids"]
    }
    assert source_blocker_ids == {item["blocker_id"] for item in ledger["blockers"]}

    quality_case_rows = [
        item
        for item in document["occurrences"]
        if item["field"] == "assertions.quality_case_id"
    ]
    assert len(quality_case_rows) == 4
    assert {
        item["primary_root_id"] for item in quality_case_rows
    } == {"legacy_quality_case_id_contract_gap"}


def test_source_truth_reconciles_63_20_6_69_43_0_without_fake_resolution() -> None:
    document = load_yaml(MAP_PATH)
    inventory = load_json(OCCURRENCE_PATH)
    dag = load_json(DAG_PATH)
    metrics = load_json(QUEUE_METRICS_PATH)
    taxonomy = load_json(NIGHT04_ROOT / "queue/taxonomy_audit.json")
    truth = load_json(NIGHT04_ROOT / "queue/truth_snapshot.json")
    candidates = load_yaml(NIGHT04_ROOT / "review_control/candidate_registry.yaml")
    dependency = load_json(NIGHT04_ROOT / "execution/dependency_recompute.json")
    parents = load_json(NIGHT04_ROOT / "execution/parent_recompute.json")
    pointer_truth = load_json(
        NIGHT04_ROOT / "pointer_prevalidation/dry_run_truth_receipt.json"
    )
    queue = load_yaml(QUEUE_PATH)
    mission = load_yaml(NIGHT05_ROOT / "mission_state.yaml")
    recompute = load_json(NIGHT05_ROOT / "execution/recompute_summary.json")
    change_log = load_json(NIGHT05_ROOT / "progress/change_log.json")
    reconciliation = document["reconciliation"]

    assert inventory["occurrence_count"] == reconciliation["occurrence_count"] == 63
    assert dag["dependency_blocker_count"] == reconciliation[
        "dependency_blocked_occurrence_count"
    ] == 20
    assert parents["parent_count"] == reconciliation["parent_work_order_count"] == 6
    assert len(queue["tasks"]) == reconciliation["carry_forward_task_count"] == 69
    assert candidates["candidate_count"] == reconciliation["candidate_ready_count"] == 43
    assert inventory["resolved_blocker_count"] == reconciliation[
        "baseline_resolved_occurrence_count"
    ] == 0
    assert all(item["classification_is_resolution"] is False for item in inventory["occurrences"])
    assert all(item["resolved"] is False for item in inventory["occurrences"])
    assert all(item["resolution_receipt_sha256"] is None for item in inventory["occurrences"])
    assert all(item["baseline_resolved"] is False for item in document["occurrences"])

    assert metrics["total_count"] == 69
    assert metrics["ready_count"] == 0
    assert metrics["fallback_ready_count"] == 1
    assert taxonomy["night03_state_counts"] == {
        "candidate_ready": 43,
        "dependency_blocked": 20,
        "parent_pending": 6,
    }
    assert taxonomy["work_type_counts"] == {
        "analysis_required": 24,
        "bf2_work_order": 6,
        "dependency_blocked": 20,
        "engineering_local": 8,
        "evidence_required": 8,
        "human_gate": 3,
    }
    assert truth["dry_run_is_resolution"] is False
    assert truth["starting_truth"]["blocker_occurrences_resolved"] == 0
    assert truth["starting_truth"]["sample_quality_allowed"] is False
    assert truth["starting_truth"]["p2_allowed"] is False

    assert dependency["dependency_count"] == 20
    assert dependency["unlocked_count"] == dependency["resolved_count"] == 0
    assert parents["pending_parent_count"] == 6
    assert parents["resolved_parent_count"] == 0
    assert pointer_truth["resolution_receipts_emitted"] == 0
    assert pointer_truth["resolved_delta"] == 0
    assert mission["truth_boundary"]["machine_generated_decisions"] == 0
    assert mission["truth_boundary"]["sample_quality_passed"] is False
    assert mission["truth_boundary"]["p2_ready"] is False
    assert recompute["state_change_allowed"] is False
    assert recompute["trigger"] == "no_independent_passed_execution_receipts"
    assert change_log["changed_occurrence_ids"] == []
    assert change_log["changed_dependency_ids"] == []
    assert change_log["changed_parent_ids"] == []
    assert change_log["resolved_delta"] == 0

    task_ids = [item["id"] for item in queue["tasks"]]
    stable_id_hash = hashlib.sha256("\n".join(sorted(task_ids)).encode("utf-8")).hexdigest()
    task_id_set_hash = hashlib.sha256(canonical_json_bytes(task_ids)).hexdigest()
    source_hashes = [
        {
            "id": item["id"],
            "source_artifact_sha256": next(
                (
                    note.split("=", 1)[1]
                    for note in item.get("notes", [])
                    if note.startswith("source_artifact_sha256=")
                ),
                None,
            ),
        }
        for item in queue["tasks"]
    ]
    source_hash_set_hash = hashlib.sha256(canonical_json_bytes(source_hashes)).hexdigest()
    assert stable_id_hash == reconciliation["night04_stable_id_set_sha256"]
    assert task_id_set_hash == reconciliation["night05_task_id_set_sha256"]
    assert source_hash_set_hash == reconciliation["night05_source_hash_set_sha256"]


def test_source_artifact_traceability_is_preserved_including_eight_pointer_nulls() -> None:
    document = load_yaml(MAP_PATH)
    inventory = load_json(OCCURRENCE_PATH)
    source_by_id = {
        item["blocker_occurrence_id"]: item for item in inventory["occurrences"]
    }
    pointer_nulls = []
    for mapped in document["occurrences"]:
        source = source_by_id[mapped["source_occurrence_id"]]
        if mapped["source_artifact_path"] is None:
            pointer_nulls.append(mapped)
            assert mapped["source_artifact_sha256"] is None
            assert mapped["source_classification"] == "engineering_local"
            match = re.search(r" in ([^:]+): '/", source["message"])
            assert match is not None
            assert (ROOT / match.group(1)).is_file()
        else:
            path = ROOT / mapped["source_artifact_path"]
            assert path.is_file()
            assert sha256_file(path) == mapped["source_artifact_sha256"]
    assert len(pointer_nulls) == 8
    assert Counter(item["field"] for item in pointer_nulls) == {
        "assertions.generation_id_present.pointer": 4,
        "assertions.quality_gate_pass.pointer": 4,
    }
