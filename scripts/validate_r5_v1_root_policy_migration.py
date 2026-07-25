#!/usr/bin/env python3
"""Validate the root-level V1 policy migration and render its reconciliation.

The validator deliberately expands the frozen 63-occurrence root map only in
memory.  The committed migration contains seven root rows, and the committed
receipt contains aggregate proof rather than a second occurrence ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


MIGRATION_REL = Path(
    "reports/p1_6/r5_v1_governance_cleanup/root_policy_migration.yaml"
)
SCHEMA_REL = Path("schemas/r5_v1_root_policy_migration.schema.json")
SOURCE_MAP_REL = Path(
    "reports/p1_6/r5_v1_convergence/blocker_root_cause_map.yaml"
)
RECEIPT_REL = Path(
    "reports/p1_6/r5_v1_governance_cleanup/validation/"
    "blocker_root_reconciliation.yaml"
)
ENGINEERING_SOURCE = "f60f220ae252262a537c612ce193fc779901984b"
SOURCE_MAP_SHA256 = (
    "39aadff44cf51d1ad5607d8ec8481bbab42650723eaf5a981415df0ee3facacf"
)
SOURCE_MAP_BLOB_OID = "526d9964a95ddc866fa960a1b9556e720ca80178"
P3_RUN_PREFIX = (
    "reports/workflow_runs/"
    "wf_20260725_stock_first_002837_v1_policy_refresh/"
)

EXPECTED_RECONCILIATION = {
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

EXPECTED_DISPOSITIONS = {
    "external_approval_and_independent_receipts_absent": "policy_retired",
    "analyst_conclusions_pending": "report_limitation",
    "reviewed_evidence_acceptance_absent": "unknown",
    "suite_exact_hash_review_pending": "not_required_for_active_v1",
    "legacy_quality_case_id_contract_gap": "historical_backlog",
    "legacy_generation_id_pointer_contract_gap": "historical_backlog",
    "legacy_quality_ready_pointer_contract_gap": "historical_backlog",
}


class MigrationValidationError(ValueError):
    """Raised when migration or source reconciliation truth is invalid."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MigrationValidationError(message)


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"{path} must contain a mapping")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"{path} must contain a mapping")
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
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
    raise MigrationValidationError(f"unsupported schema type: {expected}")


def validate_schema(
    value: Any,
    schema: Mapping[str, Any],
    root_schema: Mapping[str, Any],
    path: str = "$",
) -> None:
    """Apply the dependency-free strict subset used by the migration schema."""

    if "$ref" in schema:
        ref = str(schema["$ref"])
        _require(ref.startswith("#/"), f"{path}: unsupported reference {ref}")
        target: Any = root_schema
        for part in ref[2:].split("/"):
            _require(isinstance(target, Mapping) and part in target, f"{path}: bad ref")
            target = target[part]
        validate_schema(value, target, root_schema, path)
        return

    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = (
            expected_type if isinstance(expected_type, list) else [expected_type]
        )
        _require(
            any(_type_matches(value, str(item)) for item in expected_types),
            f"{path}: expected {expected_types}, got {type(value).__name__}",
        )

    if "const" in schema:
        _require(value == schema["const"], f"{path}: const mismatch")
    if "enum" in schema:
        _require(value in schema["enum"], f"{path}: enum mismatch {value!r}")

    if isinstance(value, str):
        if "minLength" in schema:
            _require(
                len(value) >= int(schema["minLength"]),
                f"{path}: string too short",
            )
        if "maxLength" in schema:
            _require(
                len(value) <= int(schema["maxLength"]),
                f"{path}: string too long",
            )
        if "pattern" in schema:
            _require(
                re.fullmatch(str(schema["pattern"]), value) is not None,
                f"{path}: pattern mismatch",
            )

    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema:
            _require(value >= int(schema["minimum"]), f"{path}: below minimum")

    if isinstance(value, dict):
        required = set(schema.get("required", []))
        missing = required - set(value)
        _require(not missing, f"{path}: missing keys {sorted(missing)}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(properties)
            _require(not extra, f"{path}: extra keys {sorted(extra)}")
        for key, item in value.items():
            if key in properties:
                validate_schema(
                    item,
                    properties[key],
                    root_schema,
                    f"{path}.{key}",
                )

    if isinstance(value, list):
        if "minItems" in schema:
            _require(
                len(value) >= int(schema["minItems"]),
                f"{path}: too few items",
            )
        if "maxItems" in schema:
            _require(
                len(value) <= int(schema["maxItems"]),
                f"{path}: too many items",
            )
        if schema.get("uniqueItems"):
            rendered = [_canonical_json_bytes(item) for item in value]
            _require(
                len(rendered) == len(set(rendered)),
                f"{path}: duplicate items",
            )
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                validate_schema(
                    item,
                    item_schema,
                    root_schema,
                    f"{path}[{index}]",
                )


def _assert_acyclic(
    nodes: set[str],
    edges: set[tuple[str, str]],
    label: str,
) -> None:
    outgoing: dict[str, set[str]] = defaultdict(set)
    indegree = {node: 0 for node in nodes}
    for source, target in edges:
        _require(source in nodes, f"{label}: orphan source {source}")
        _require(target in nodes, f"{label}: orphan target {target}")
        _require(source != target, f"{label}: self-cycle at {source}")
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
    _require(visited == len(nodes), f"{label}: cycle detected")


def _verify_source_binding(
    repo_root: Path,
    migration: Mapping[str, Any],
    source_map_path: Path,
) -> None:
    binding = migration["source_root_map"]
    _require(
        Path(str(binding["path"])).as_posix() == SOURCE_MAP_REL.as_posix(),
        "source root-map path mismatch",
    )
    payload = source_map_path.read_bytes()
    observed_sha = hashlib.sha256(payload).hexdigest()
    _require(observed_sha == SOURCE_MAP_SHA256, "source root-map SHA-256 drift")
    _require(binding["sha256"] == observed_sha, "migration source SHA-256 mismatch")
    _require(
        binding["engineering_source_revision"] == ENGINEERING_SOURCE,
        "engineering source revision mismatch",
    )
    revision_path = f"{ENGINEERING_SOURCE}:{SOURCE_MAP_REL.as_posix()}"
    try:
        blob_oid = subprocess.check_output(
            ["git", "rev-parse", revision_path],
            cwd=repo_root,
            text=True,
        ).strip()
        blob_payload = subprocess.check_output(
            ["git", "cat-file", "blob", revision_path],
            cwd=repo_root,
        )
    except subprocess.CalledProcessError as exc:
        raise MigrationValidationError(
            "source root-map engineering blob is unavailable"
        ) from exc
    _require(blob_oid == SOURCE_MAP_BLOB_OID, "source root-map blob OID drift")
    _require(binding["git_blob_oid"] == blob_oid, "migration blob OID mismatch")
    _require(blob_payload == payload, "source root-map differs from engineering blob")


def _derive_source_truth(source_map: Mapping[str, Any]) -> dict[str, Any]:
    roots = list(source_map.get("root_causes", []))
    occurrences = list(source_map.get("occurrences", []))
    parents = list(source_map.get("parent_work_orders", []))
    _require(all(isinstance(item, dict) for item in roots), "invalid source roots")
    _require(
        all(isinstance(item, dict) for item in occurrences),
        "invalid source occurrences",
    )
    _require(all(isinstance(item, dict) for item in parents), "invalid source parents")

    root_ids = [str(item.get("root_cause_id")) for item in roots]
    occurrence_ids = [str(item.get("carry_forward_id")) for item in occurrences]
    source_occurrence_ids = [
        str(item.get("source_occurrence_id")) for item in occurrences
    ]
    parent_ids = [str(item.get("carry_forward_id")) for item in parents]
    _require(len(root_ids) == len(set(root_ids)), "duplicate source root ID")
    _require(
        len(occurrence_ids) == len(set(occurrence_ids)),
        "duplicate source occurrence ID",
    )
    _require(
        len(source_occurrence_ids) == len(set(source_occurrence_ids)),
        "duplicate source occurrence provenance ID",
    )
    _require(len(parent_ids) == len(set(parent_ids)), "duplicate source parent ID")
    nodes = set(occurrence_ids) | set(parent_ids)
    _require(
        len(nodes) == len(occurrence_ids) + len(parent_ids),
        "duplicate carry-forward node ID",
    )

    assignments = Counter(str(item.get("primary_root_id")) for item in occurrences)
    _require(set(assignments) == set(root_ids), "orphan or uncovered source root")
    for item in occurrences:
        _require(
            str(item.get("primary_root_id")) in set(root_ids),
            "occurrence references an unknown root",
        )

    dependency_edges = {
        (str(dependency), str(item["carry_forward_id"]))
        for item in [*occurrences, *parents]
        for dependency in item.get("blocked_by", [])
    }
    for item in [*occurrences, *parents]:
        blocked_by = [str(value) for value in item.get("blocked_by", [])]
        _require(
            len(blocked_by) == len(set(blocked_by)),
            f"duplicate dependency in {item.get('carry_forward_id')}",
        )
        _require(
            item.get("baseline_resolved") is False,
            f"historical node resolved: {item.get('carry_forward_id')}",
        )
        _require(
            item.get("resolution_receipt_sha256") is None,
            f"historical resolution receipt present: {item.get('carry_forward_id')}",
        )
    _assert_acyclic(nodes, dependency_edges, "dependency graph")

    occurrence_by_id = {
        str(item["carry_forward_id"]): item for item in occurrences
    }
    duplicate_edges: set[tuple[str, str]] = set()
    for item in occurrences:
        duplicate_of = item.get("duplicate_of")
        if duplicate_of is None:
            continue
        duplicate = str(item["carry_forward_id"])
        canonical = str(duplicate_of)
        _require(canonical in occurrence_by_id, f"orphan duplicate reference {canonical}")
        _require(
            occurrence_by_id[canonical]["primary_root_id"]
            == item["primary_root_id"],
            "duplicate reference crosses roots",
        )
        _require(
            occurrence_by_id[canonical].get("duplicate_of") is None,
            "duplicate reference points to another duplicate",
        )
        duplicate_edges.add((canonical, duplicate))
    _assert_acyclic(set(occurrence_ids), duplicate_edges, "duplicate graph")

    expected_groups: dict[str, list[str]] = {}
    for item in occurrences:
        if item.get("source_classification") != "dependency_blocked":
            continue
        key = "suite" if item.get("case_id") == "__suite__" else str(
            item.get("case_id")
        )
        dependencies = [str(value) for value in item.get("blocked_by", [])]
        previous = expected_groups.setdefault(key, dependencies)
        _require(
            previous == dependencies,
            f"dependency group {key} is internally inconsistent",
        )
    _require(
        source_map.get("dependency_groups") == expected_groups,
        "source dependency_groups disagree with occurrence rows",
    )

    derived = {
        "occurrence_count": len(occurrences),
        "dependency_blocked_occurrence_count": sum(
            item.get("source_classification") == "dependency_blocked"
            for item in occurrences
        ),
        "parent_work_order_count": len(parents),
        "carry_forward_task_count": len(nodes),
        "candidate_ready_count": sum(
            item.get("baseline_state") == "candidate_ready"
            for item in occurrences
        ),
        "historical_resolved_occurrence_count": sum(
            item.get("baseline_resolved") is True for item in occurrences
        ),
        "node_count": len(nodes),
        "edge_count": len(dependency_edges),
        "duplicate_reference_count": len(duplicate_edges),
    }
    _require(
        derived == EXPECTED_RECONCILIATION,
        f"derived source truth mismatch: {derived}",
    )
    reconciliation = source_map.get("reconciliation", {})
    source_claims = {
        "occurrence_count": reconciliation.get("occurrence_count"),
        "dependency_blocked_occurrence_count": reconciliation.get(
            "dependency_blocked_occurrence_count"
        ),
        "parent_work_order_count": reconciliation.get("parent_work_order_count"),
        "carry_forward_task_count": reconciliation.get("carry_forward_task_count"),
        "candidate_ready_count": reconciliation.get("candidate_ready_count"),
        "historical_resolved_occurrence_count": reconciliation.get(
            "baseline_resolved_occurrence_count"
        ),
        "node_count": reconciliation.get("source_node_count"),
        "edge_count": reconciliation.get("source_edge_count"),
        "duplicate_reference_count": reconciliation.get(
            "duplicate_reference_count"
        ),
    }
    _require(
        source_claims == derived,
        "source reconciliation block disagrees with dynamically derived rows",
    )
    return {
        "roots": roots,
        "root_ids": root_ids,
        "assignments": assignments,
        "derived": derived,
    }


def _validate_migration_roots(
    repo_root: Path,
    migration: Mapping[str, Any],
    source_truth: Mapping[str, Any],
) -> list[dict[str, Any]]:
    migration_roots = list(migration["migration_roots"])
    root_ids = [str(item["root_cause_id"]) for item in migration_roots]
    _require(len(root_ids) == len(set(root_ids)) == 7, "migration root IDs not unique")
    _require(
        set(root_ids) == set(EXPECTED_DISPOSITIONS),
        "migration does not cover the exact seven roots",
    )

    source_roots = {
        str(item["root_cause_id"]): item for item in source_truth["roots"]
    }
    assignments: Counter[str] = source_truth["assignments"]
    coverage: list[dict[str, Any]] = []
    for row in migration_roots:
        root_id = str(row["root_cause_id"])
        source = source_roots[root_id]
        _require(
            row["historical_category"] == source["category"],
            f"{root_id}: historical category drift",
        )
        _require(
            row["historical_root_status"] == source["status"] == "open",
            f"{root_id}: historical root status drift",
        )
        _require(row["historical_resolved"] is False, f"{root_id}: fake resolution")
        _require(
            int(row["primary_occurrence_count"])
            == int(source["primary_occurrence_count"])
            == assignments[root_id],
            f"{root_id}: occurrence-count drift",
        )
        _require(
            row["active_disposition"] == EXPECTED_DISPOSITIONS[root_id],
            f"{root_id}: active disposition mismatch",
        )

        disposition = str(row["active_disposition"])
        impact = str(row["active_v1_impact"])
        limitations = list(row["current_limitation_references"])
        blocks_current_goal = row["blocks_current_goal"]
        impact_scope = str(row["impact_scope"])
        capabilities = list(row["affected_capabilities"])
        if disposition == "report_limitation":
            _require(
                impact == "visible_nonblocking_report_limitation",
                f"{root_id}: report limitation impact mismatch",
            )
            _require(
                impact_scope == "section" and capabilities,
                f"{root_id}: report limitation scope/capability mismatch",
            )
            _require(
                blocks_current_goal is False,
                f"{root_id}: report limitation blocks current goal",
            )
            _require(limitations, f"{root_id}: missing P3 limitation trace")
            for relative in limitations:
                relative_text = Path(str(relative)).as_posix()
                _require(
                    relative_text.startswith(P3_RUN_PREFIX),
                    f"{root_id}: limitation trace is not in the current P3 run",
                )
                _require(
                    (repo_root / relative_text).is_file(),
                    f"{root_id}: missing limitation trace {relative_text}",
                )
        elif disposition == "unknown":
            _require(
                impact == "visible_unused_claim_unknown",
                f"{root_id}: unknown impact mismatch",
            )
            _require(
                impact_scope == "claim" and capabilities,
                f"{root_id}: unknown scope/capability mismatch",
            )
            _require(
                blocks_current_goal is False,
                f"{root_id}: visible unused unknown blocks current goal",
            )
            _require(limitations, f"{root_id}: missing P3 unknown trace")
            for relative in limitations:
                relative_text = Path(str(relative)).as_posix()
                _require(
                    relative_text.startswith(P3_RUN_PREFIX),
                    f"{root_id}: unknown trace is not in the current P3 run",
                )
                _require(
                    (repo_root / relative_text).is_file(),
                    f"{root_id}: missing unknown trace {relative_text}",
                )
        else:
            _require(
                impact == "no_canonical_impact",
                f"{root_id}: inactive row has active impact",
            )
            _require(
                impact_scope == "none" and not capabilities,
                f"{root_id}: inactive row has scope or affected capability",
            )
            _require(
                blocks_current_goal is False,
                f"{root_id}: inactive row blocks current goal",
            )
            _require(
                not limitations,
                f"{root_id}: inactive row has current limitation references",
            )

        references = list(row["evidence_references"])
        historical_refs = [
            ref for ref in references if ref["role"] == "historical_root"
        ]
        _require(
            len(historical_refs) == 1,
            f"{root_id}: expected one historical-root reference",
        )
        historical_ref = historical_refs[0]
        _require(
            Path(str(historical_ref["path"])).as_posix()
            == SOURCE_MAP_REL.as_posix(),
            f"{root_id}: historical-root path mismatch",
        )
        _require(
            historical_ref["selector"] == f"root_cause_id={root_id}",
            f"{root_id}: historical-root selector mismatch",
        )
        _require(
            any(ref["role"] == "active_policy" for ref in references),
            f"{root_id}: active-policy evidence missing",
        )
        for reference in references:
            relative = Path(str(reference["path"]))
            _require(not relative.is_absolute(), f"{root_id}: absolute evidence path")
            _require(".." not in relative.parts, f"{root_id}: escaping evidence path")
            _require(
                (repo_root / relative).is_file(),
                f"{root_id}: missing evidence path {relative.as_posix()}",
            )
            relative_text = relative.as_posix()
            forbidden_physical_prefixes = (
                "reports/p1_6/r5_night_shift/",
                "reports/p1_6/r5_bundle",
                "reports/workflow_runs/wf_20260715_",
                "reports/workflow_runs/wf_20260703_",
            )
            _require(
                not relative_text.startswith(forbidden_physical_prefixes),
                f"{root_id}: direct evidence depends on retireable history",
            )
            if reference["role"] == "current_limitation_example":
                selector = str(reference["selector"])
                _require(
                    "=" in selector,
                    f"{root_id}: limitation selector must be key=value",
                )
                selector_value = selector.split("=", 1)[1]
                _require(
                    selector_value
                    in (repo_root / relative).read_text(encoding="utf-8"),
                    f"{root_id}: limitation selector not found",
                )

        coverage.append(
            {
                "root_cause_id": root_id,
                "source_occurrence_count": assignments[root_id],
                "active_disposition": disposition,
                "impact_scope": impact_scope,
                "active_v1_impact": impact,
                "blocks_current_goal": blocks_current_goal,
                "covered_once": True,
            }
        )

    serialized = yaml.safe_dump(
        migration,
        allow_unicode=True,
        sort_keys=False,
    )
    forbidden_tokens = (
        "ns02_t30_occ_",
        "BF17R-I-",
        "\noccurrences:",
        "\ncandidate_decisions:",
    )
    _require(
        not any(token in serialized for token in forbidden_tokens),
        "migration persists an occurrence overlay or copied candidate decision",
    )
    return coverage


def validate_documents(
    repo_root: Path,
    migration: Mapping[str, Any],
    schema: Mapping[str, Any],
    source_map: Mapping[str, Any],
    *,
    verify_source_binding: bool = True,
) -> dict[str, Any]:
    """Validate provided documents and return a deterministic summary receipt."""

    validate_schema(migration, schema, schema)
    source_map_path = repo_root / SOURCE_MAP_REL
    if verify_source_binding:
        _verify_source_binding(repo_root, migration, source_map_path)
    source_truth = _derive_source_truth(source_map)
    coverage = _validate_migration_roots(repo_root, migration, source_truth)

    _require(
        migration["migration_is_historical_resolution"] is False,
        "migration claims historical resolution",
    )
    dispositions = Counter(
        str(row["active_disposition"]) for row in migration["migration_roots"]
    )
    active_defects = dispositions["active_defect"]
    _require(active_defects == 0, "active V1 engineering defect remains")
    historical_engineering = [
        row
        for row in migration["migration_roots"]
        if row["historical_category"] == "engineering_defect"
    ]
    _require(
        len(historical_engineering) == 3
        and all(
            row["active_disposition"] == "historical_backlog"
            and row["active_v1_impact"] == "no_canonical_impact"
            for row in historical_engineering
        ),
        "historical engineering roots are not isolated as backlog",
    )

    limitation_paths = sorted(
        {
            Path(str(path)).as_posix()
            for row in migration["migration_roots"]
            if row["active_disposition"] in {"report_limitation", "unknown"}
            for path in row["current_limitation_references"]
        }
    )
    derived = source_truth["derived"]
    return {
        "schema_version": "r5_v1_blocker_root_reconciliation_v1",
        "validation_id": "V-005",
        "phase": "P4",
        "decision": "pass",
        "checked_at": "2026-07-25",
        "source_root_map": {
            "path": SOURCE_MAP_REL.as_posix(),
            "sha256": SOURCE_MAP_SHA256,
            "engineering_source_revision": ENGINEERING_SOURCE,
            "git_blob_oid": SOURCE_MAP_BLOB_OID,
            "matches_engineering_source_blob": True,
        },
        "migration": {
            "path": MIGRATION_REL.as_posix(),
            "schema_path": SCHEMA_REL.as_posix(),
            "root_count": len(coverage),
            "occurrence_overlay_persisted": False,
            "candidate_decisions_copied": False,
            "migration_is_historical_resolution": False,
            "semantic_sha256": hashlib.sha256(
                _canonical_json_bytes(migration)
            ).hexdigest(),
        },
        "dynamic_reconciliation": {
            **derived,
            "root_cause_count": len(coverage),
            "root_coverage_count": len(coverage),
            "orphan_root_count": 0,
            "duplicate_node_id_count": 0,
            "dependency_cycle_count": 0,
            "duplicate_reference_cycle_count": 0,
        },
        "root_coverage": sorted(
            coverage,
            key=lambda item: str(item["root_cause_id"]),
        ),
        "policy_summary": {
            "policy_retired_root_count": dispositions["policy_retired"],
            "report_limitation_root_count": dispositions["report_limitation"],
            "visible_unknown_root_count": dispositions["unknown"],
            "not_required_for_active_v1_root_count": dispositions[
                "not_required_for_active_v1"
            ],
            "historical_backlog_root_count": dispositions["historical_backlog"],
            "active_defect_root_count": active_defects,
            "historical_engineering_root_count": len(historical_engineering),
            "historical_resolved_occurrence_count": derived[
                "historical_resolved_occurrence_count"
            ],
        },
        "current_limitation_trace": {
            "source_workflow_id": (
                "wf_20260725_stock_first_002837_v1_policy_refresh"
            ),
            "paths": limitation_paths,
            "historical_resolution_claimed": False,
        },
        "guards": {
            "all_63_occurrences_dynamically_covered_once": True,
            "historical_root_map_mutated": False,
            "historical_occurrence_resolution_changed": False,
            "historical_resolution_delta": 0,
            "second_occurrence_ledger_created": False,
            "active_v1_engineering_defect_count": 0,
            "system_v1_complete_claimed": False,
        },
    }


def validate_repository(
    repo_root: Path,
    *,
    migration_path: Path | None = None,
    schema_path: Path | None = None,
    source_map_path: Path | None = None,
) -> dict[str, Any]:
    root = repo_root.resolve()
    migration_file = (
        migration_path
        if migration_path is not None
        else root / MIGRATION_REL
    )
    schema_file = schema_path if schema_path is not None else root / SCHEMA_REL
    source_file = (
        source_map_path
        if source_map_path is not None
        else root / SOURCE_MAP_REL
    )
    migration = _load_yaml(migration_file)
    schema = _load_json(schema_file)
    source_map = _load_yaml(source_file)
    _require(
        source_file.resolve() == (root / SOURCE_MAP_REL).resolve(),
        "validator source map must be the protected canonical root map",
    )
    return validate_documents(root, migration, schema, source_map)


def render_receipt(receipt: Mapping[str, Any]) -> str:
    return yaml.safe_dump(
        dict(receipt),
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=100,
    )


def _write_receipt(repo_root: Path, output: Path, receipt: Mapping[str, Any]) -> None:
    root = repo_root.resolve()
    target = output if output.is_absolute() else root / output
    target = target.resolve()
    authorized = (root / RECEIPT_REL).resolve()
    _require(target == authorized, f"output must be {RECEIPT_REL.as_posix()}")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = render_receipt(receipt)
    if target.exists() and target.read_text(encoding="utf-8") == payload:
        return
    target.write_text(payload, encoding="utf-8", newline="\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--migration", type=Path)
    parser.add_argument("--schema", type=Path)
    parser.add_argument("--source-map", type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.repo_root.resolve()
    try:
        receipt = validate_repository(
            root,
            migration_path=args.migration,
            schema_path=args.schema,
            source_map_path=args.source_map,
        )
        if args.output is not None:
            _write_receipt(root, args.output, receipt)
    except (MigrationValidationError, OSError, ValueError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    counts = receipt["dynamic_reconciliation"]
    print(
        "decision=pass "
        f"roots={counts['root_cause_count']} "
        f"occurrences={counts['occurrence_count']} "
        f"active_defects={receipt['policy_summary']['active_defect_root_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
