"""R5 Bundle 17R-BF1: deterministic targeted-backflow compiler.

The compiler consumes the *physical* Bundle 17R activation receipt, generation
lock, case matrix, and backflow queue.  It validates the exact hashes and
release boundaries, preserves every blocker, clusters blockers into executable
work orders, builds a dependency graph, and emits a non-canonical execution
plan.

It deliberately does not fetch evidence, alter upstream values, synthesize
human acceptance, mutate canonical workflow state, authorize sample quality,
or open P2.  After the work orders are resolved, the existing 16R -> 15R ->
14R -> 17R chain must be rerun from physical artifacts.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("PyYAML is required for Bundle 17R targeted backflow") from exc


SCHEMA_VERSION = "r5_bundle17r_backflow_compilation_v1"
BUNDLE_ID = "R5_BUNDLE17R_BF1_TARGETED_BACKFLOW_COMPILER"
REQUIRED_QUEUE_COLUMNS = (
    "case_id",
    "code",
    "stage",
    "field",
    "owner_skill",
    "target_stage",
    "message",
    "requested_action",
)
FALSE_RELEASE_KEYS = (
    "canonical_workflow_state_mutation_allowed",
    "sample_quality_allowed",
    "p2_allowed",
)


class BackflowContractError(ValueError):
    """Raised when a physical input or contract cannot be interpreted safely."""


@dataclass(frozen=True)
class ArtifactBinding:
    key: str
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    field: str
    message: str
    severity: str = "error"


@dataclass(frozen=True)
class RoutedIssue:
    issue_id: str
    sequence: int
    case_id: str
    code: str
    stage: str
    field: str
    source_owner_skill: str
    source_target_stage: str
    message: str
    requested_action: str
    route_id: str
    batch_id: str
    owner_skill: str
    target_stage: str
    priority: int
    route_score: int
    route_status: str


@dataclass(frozen=True)
class WorkOrder:
    work_order_id: str
    case_id: str
    route_id: str
    batch_id: str
    owner_skill: str
    target_stage: str
    priority: int
    issue_ids: tuple[str, ...]
    issue_count: int
    requested_actions: tuple[str, ...]
    required_outputs: tuple[str, ...]
    acceptance_checks: tuple[str, ...]
    depends_on: tuple[str, ...]
    execution_status: str = "open"


@dataclass(frozen=True)
class BackflowCompilation:
    schema_version: str
    bundle_id: str
    baseline_commit: str
    run_id: str
    source_activation_generation_id: str
    decision: str
    next_stage: str
    expected_case_count: int
    case_count: int
    engineering_pass_count: int
    source_blocker_count: int
    compiled_issue_count: int
    duplicate_row_count: int
    routed_issue_count: int
    manual_route_issue_count: int
    work_order_count: int
    validation_error_count: int
    canonical_workflow_state_mutation_allowed: bool
    sample_quality_allowed: bool
    p2_allowed: bool
    input_artifacts: Mapping[str, Mapping[str, Any]]
    validation_issues: tuple[ValidationIssue, ...]
    issues: tuple[RoutedIssue, ...]
    work_orders: tuple[WorkOrder, ...]


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_document(path: str | Path) -> Any:
    document_path = Path(path)
    suffix = document_path.suffix.lower()
    text = document_path.read_text(encoding="utf-8")
    if suffix == ".json":
        return json.loads(text)
    if suffix in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    if suffix in {".md", ".txt"}:
        return text
    raise BackflowContractError(f"unsupported document extension: {document_path}")


def _as_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BackflowContractError(f"{field_name} must be a mapping")
    return value


def _as_sequence(value: Any, field_name: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise BackflowContractError(f"{field_name} must be a sequence")
    return value


def _nonempty(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _is_false(value: Any) -> bool:
    return value is False


def _safe_relative_path(repo_root: Path, path_text: str, policy: Mapping[str, Any]) -> Path:
    if not path_text or Path(path_text).is_absolute():
        raise BackflowContractError(f"artifact path must be repository-relative: {path_text!r}")
    candidate = (repo_root / path_text).resolve()
    try:
        relative = candidate.relative_to(repo_root.resolve()).as_posix()
    except ValueError as exc:
        raise BackflowContractError(f"artifact path escapes repository: {path_text!r}") from exc

    allowed_roots = tuple(str(item).rstrip("/") + "/" for item in policy.get("allowed_artifact_roots", []))
    if allowed_roots and not any(relative.startswith(root) for root in allowed_roots):
        raise BackflowContractError(f"artifact path is outside allowed roots: {relative}")

    forbidden = [str(item).lower() for item in policy.get("forbidden_path_fragments", [])]
    lowered = relative.lower()
    if any(fragment in lowered for fragment in forbidden):
        raise BackflowContractError(f"forbidden artifact path fragment: {relative}")

    extensions = {str(item).lower() for item in policy.get("allowed_artifact_extensions", [])}
    if extensions and candidate.suffix.lower() not in extensions:
        raise BackflowContractError(f"unsupported artifact extension: {relative}")
    return candidate


def _verify_binding(
    *,
    key: str,
    repo_root: Path,
    value: Any,
    policy: Mapping[str, Any],
) -> ArtifactBinding:
    binding = _as_mapping(value, f"activation.{key}")
    path_text = _nonempty(binding.get("path"))
    expected_hash = _nonempty(binding.get("sha256")).lower()
    if len(expected_hash) != 64 or any(ch not in "0123456789abcdef" for ch in expected_hash):
        raise BackflowContractError(f"activation.{key}.sha256 must be a lowercase SHA-256")
    path = _safe_relative_path(repo_root, path_text, policy)
    if not path.is_file():
        raise BackflowContractError(f"bound artifact does not exist: {path_text}")
    actual_hash = sha256_file(path)
    if actual_hash != expected_hash:
        raise BackflowContractError(
            f"artifact hash mismatch for {key}: expected {expected_hash}, got {actual_hash}"
        )
    return ArtifactBinding(
        key=key,
        path=path_text,
        sha256=actual_hash,
        size_bytes=path.stat().st_size,
    )


def _read_csv(path: Path) -> tuple[list[dict[str, str]], tuple[str, ...]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        rows = [
            {str(key): "" if value is None else str(value).strip() for key, value in row.items()}
            for row in reader
        ]
    return rows, fieldnames


def _lock_output_hashes(generation_lock: Mapping[str, Any]) -> Mapping[str, str]:
    output_artifacts = generation_lock.get("output_artifacts")
    if not isinstance(output_artifacts, Mapping):
        return {}
    hashes: dict[str, str] = {}
    for path, value in output_artifacts.items():
        if isinstance(value, Mapping):
            digest = _nonempty(value.get("sha256"))
            if digest:
                hashes[str(path)] = digest
    return hashes


def _is_bound_in_lock(binding: ArtifactBinding, lock_hashes: Mapping[str, str]) -> bool:
    for lock_path, digest in lock_hashes.items():
        if digest != binding.sha256:
            continue
        if binding.path.endswith(lock_path) or Path(binding.path).name == Path(lock_path).name:
            return True
    return False


def _expected(policy: Mapping[str, Any], key: str) -> Any:
    expected = _as_mapping(policy.get("expected_activation"), "policy.expected_activation")
    if key not in expected:
        raise BackflowContractError(f"policy.expected_activation missing {key}")
    return expected[key]


def _validate_release_boundaries(
    *,
    receipt: Mapping[str, Any],
    generation_lock: Mapping[str, Any],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for key in FALSE_RELEASE_KEYS:
        if not _is_false(receipt.get(key)):
            issues.append(
                ValidationIssue(
                    code="release_boundary_not_false",
                    field=f"receipt.{key}",
                    message=f"Bundle 17R receipt must keep {key}=false",
                )
            )
    boundaries = generation_lock.get("release_boundaries")
    if not isinstance(boundaries, Mapping):
        issues.append(
            ValidationIssue(
                code="generation_lock_release_boundaries_missing",
                field="generation_lock.release_boundaries",
                message="Bundle 17R generation lock must declare release boundaries",
            )
        )
    else:
        for key in FALSE_RELEASE_KEYS:
            if not _is_false(boundaries.get(key)):
                issues.append(
                    ValidationIssue(
                        code="generation_lock_release_boundary_not_false",
                        field=f"generation_lock.release_boundaries.{key}",
                        message=f"Bundle 17R generation lock must keep {key}=false",
                    )
                )
    return issues


def _route_score(route: Mapping[str, Any], issue: Mapping[str, str]) -> int:
    match = route.get("match")
    if not isinstance(match, Mapping):
        return 0
    owner = issue.get("owner_skill", "").lower()
    code = issue.get("code", "").lower()
    text = " ".join(
        issue.get(field, "")
        for field in (
            "code",
            "stage",
            "field",
            "owner_skill",
            "target_stage",
            "message",
            "requested_action",
        )
    ).lower()

    score = 0
    owner_skills = [str(item).lower() for item in match.get("owner_skills", [])]
    if owner and owner in owner_skills:
        score += 120
    for prefix in match.get("code_prefixes", []):
        if code.startswith(str(prefix).lower()):
            score += 80
    for token in match.get("code_any", []):
        if str(token).lower() in code:
            score += 55
    matched_text = 0
    for token in match.get("text_any", []):
        if str(token).lower() in text:
            matched_text += 1
    score += min(matched_text, 5) * 15
    return score


def _select_route(
    issue: Mapping[str, str],
    policy: Mapping[str, Any],
) -> tuple[Mapping[str, Any], int, str]:
    routes = _as_sequence(policy.get("routes"), "policy.routes")
    fallback: Mapping[str, Any] | None = None
    scored: list[tuple[int, int, str, Mapping[str, Any]]] = []
    for route_raw in routes:
        route = _as_mapping(route_raw, "policy.routes[]")
        route_id = _nonempty(route.get("route_id"))
        if not route_id:
            raise BackflowContractError("every route requires route_id")
        if route.get("fallback") is True:
            fallback = route
            continue
        score = _route_score(route, issue)
        if score > 0:
            priority = int(route.get("match_priority", 0))
            scored.append((score, priority, route_id, route))
    if scored:
        scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
        score, _priority, _route_id, route = scored[0]
        return route, score, "routed"
    if fallback is None:
        raise BackflowContractError("policy requires a fallback route")
    return fallback, 0, "manual_route_review"


def _stable_issue_id(row: Mapping[str, str], occurrence: int) -> str:
    seed = {key: row.get(key, "") for key in REQUIRED_QUEUE_COLUMNS}
    seed["occurrence"] = occurrence
    return "BF17R-I-" + sha256_bytes(canonical_json_bytes(seed))[:16]


def _stable_work_order_id(case_id: str, route_id: str) -> str:
    seed = {"case_id": case_id or "suite", "route_id": route_id}
    return "BF17R-WO-" + sha256_bytes(canonical_json_bytes(seed))[:14]


def _normalize_issue_rows(
    rows: Sequence[Mapping[str, str]],
    policy: Mapping[str, Any],
) -> tuple[list[RoutedIssue], int]:
    occurrences: dict[str, int] = {}
    routed: list[RoutedIssue] = []
    duplicate_count = 0
    for index, row_raw in enumerate(rows, start=1):
        row = {key: str(row_raw.get(key, "")).strip() for key in REQUIRED_QUEUE_COLUMNS}
        signature = sha256_bytes(canonical_json_bytes(row))
        occurrence = occurrences.get(signature, 0) + 1
        occurrences[signature] = occurrence
        if occurrence > 1:
            duplicate_count += 1
        route, score, route_status = _select_route(row, policy)
        route_id = _nonempty(route.get("route_id"))
        routed.append(
            RoutedIssue(
                issue_id=_stable_issue_id(row, occurrence),
                sequence=index,
                case_id=row["case_id"],
                code=row["code"],
                stage=row["stage"],
                field=row["field"],
                source_owner_skill=row["owner_skill"],
                source_target_stage=row["target_stage"],
                message=row["message"],
                requested_action=row["requested_action"],
                route_id=route_id,
                batch_id=_nonempty(route.get("batch_id")),
                owner_skill=_nonempty(route.get("owner_skill")),
                target_stage=_nonempty(route.get("target_stage")),
                priority=int(route.get("priority", 100)),
                route_score=score,
                route_status=route_status,
            )
        )
    return routed, duplicate_count


def _route_by_id(policy: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for route_raw in _as_sequence(policy.get("routes"), "policy.routes"):
        route = _as_mapping(route_raw, "policy.routes[]")
        route_id = _nonempty(route.get("route_id"))
        if not route_id or route_id in result:
            raise BackflowContractError(f"duplicate or empty route_id: {route_id!r}")
        result[route_id] = route
    return result


def _build_work_orders(
    issues: Sequence[RoutedIssue],
    policy: Mapping[str, Any],
) -> list[WorkOrder]:
    routes = _route_by_id(policy)
    grouped: dict[tuple[str, str], list[RoutedIssue]] = {}
    for issue in issues:
        grouped.setdefault((issue.case_id, issue.route_id), []).append(issue)

    preliminary: dict[tuple[str, str], dict[str, Any]] = {}
    for key, group in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        case_id, route_id = key
        route = routes[route_id]
        preliminary[key] = {
            "work_order_id": _stable_work_order_id(case_id, route_id),
            "case_id": case_id,
            "route_id": route_id,
            "batch_id": _nonempty(route.get("batch_id")),
            "owner_skill": _nonempty(route.get("owner_skill")),
            "target_stage": _nonempty(route.get("target_stage")),
            "priority": int(route.get("priority", 100)),
            "issue_ids": tuple(sorted(issue.issue_id for issue in group)),
            "requested_actions": tuple(sorted({issue.requested_action for issue in group})),
            "required_outputs": tuple(str(item) for item in route.get("required_outputs", [])),
            "acceptance_checks": tuple(str(item) for item in route.get("acceptance_checks", [])),
        }

    orders: list[WorkOrder] = []
    for key, value in preliminary.items():
        case_id, route_id = key
        route = routes[route_id]
        dependencies: set[str] = set()
        for dependency_route in route.get("depends_on_routes", []):
            dependency_route_id = str(dependency_route)
            local = preliminary.get((case_id, dependency_route_id))
            suite = preliminary.get(("", dependency_route_id))
            if local:
                dependencies.add(str(local["work_order_id"]))
            if suite:
                dependencies.add(str(suite["work_order_id"]))
        if case_id:
            for (dep_case, dep_route), candidate in preliminary.items():
                if dep_case == "" and dep_route in route.get("depends_on_routes", []):
                    dependencies.add(str(candidate["work_order_id"]))
        orders.append(
            WorkOrder(
                work_order_id=str(value["work_order_id"]),
                case_id=str(value["case_id"]),
                route_id=str(value["route_id"]),
                batch_id=str(value["batch_id"]),
                owner_skill=str(value["owner_skill"]),
                target_stage=str(value["target_stage"]),
                priority=int(value["priority"]),
                issue_ids=tuple(value["issue_ids"]),
                issue_count=len(value["issue_ids"]),
                requested_actions=tuple(value["requested_actions"]),
                required_outputs=tuple(value["required_outputs"]),
                acceptance_checks=tuple(value["acceptance_checks"]),
                depends_on=tuple(sorted(dependencies)),
            )
        )

    terminal_route = _as_mapping(policy.get("terminal_rerun"), "policy.terminal_rerun")
    terminal_id = _nonempty(terminal_route.get("route_id"))
    if terminal_id:
        terminal_work_order_id = _stable_work_order_id("", terminal_id)
        orders.append(
            WorkOrder(
                work_order_id=terminal_work_order_id,
                case_id="",
                route_id=terminal_id,
                batch_id=_nonempty(terminal_route.get("batch_id")),
                owner_skill=_nonempty(terminal_route.get("owner_skill")),
                target_stage=_nonempty(terminal_route.get("target_stage")),
                priority=int(terminal_route.get("priority", 999)),
                issue_ids=(),
                issue_count=0,
                requested_actions=tuple(str(item) for item in terminal_route.get("requested_actions", [])),
                required_outputs=tuple(str(item) for item in terminal_route.get("required_outputs", [])),
                acceptance_checks=tuple(str(item) for item in terminal_route.get("acceptance_checks", [])),
                depends_on=tuple(sorted(order.work_order_id for order in orders)),
            )
        )

    return sorted(orders, key=lambda item: (item.priority, item.batch_id, item.case_id, item.route_id))


def _validate_dependency_graph(work_orders: Sequence[WorkOrder]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    identifiers = {order.work_order_id for order in work_orders}
    adjacency = {order.work_order_id: set(order.depends_on) for order in work_orders}
    for order in work_orders:
        unknown = sorted(set(order.depends_on).difference(identifiers))
        if unknown:
            issues.append(
                ValidationIssue(
                    code="unknown_work_order_dependency",
                    field=order.work_order_id,
                    message=f"unknown dependencies: {unknown}",
                )
            )

    temporary: set[str] = set()
    permanent: set[str] = set()

    def visit(node: str) -> None:
        if node in permanent:
            return
        if node in temporary:
            issues.append(
                ValidationIssue(
                    code="work_order_dependency_cycle",
                    field=node,
                    message="dependency graph contains a cycle",
                )
            )
            return
        temporary.add(node)
        for dependency in sorted(adjacency.get(node, set())):
            if dependency in identifiers:
                visit(dependency)
        temporary.remove(node)
        permanent.add(node)

    for node in sorted(identifiers):
        visit(node)
    return issues


def _case_matrix_summary(rows: Sequence[Mapping[str, str]]) -> tuple[int, int, set[str]]:
    case_ids: set[str] = set()
    passed = 0
    for row in rows:
        case_id = str(row.get("case_id", "")).strip()
        if case_id:
            case_ids.add(case_id)
        value = str(row.get("engineering_pass", "")).strip().lower()
        if value in {"true", "1", "yes", "pass", "passed"}:
            passed += 1
    return len(case_ids), passed, case_ids


def compile_backflow(
    *,
    repo_root: str | Path,
    manifest_path: str | Path,
    policy_path: str | Path,
) -> BackflowCompilation:
    root = Path(repo_root).resolve()
    manifest_file = Path(manifest_path)
    if not manifest_file.is_absolute():
        manifest_file = (root / manifest_file).resolve()
    policy_file = Path(policy_path)
    if not policy_file.is_absolute():
        policy_file = (root / policy_file).resolve()

    manifest = _as_mapping(load_document(manifest_file), "manifest")
    policy = _as_mapping(load_document(policy_file), "policy")
    if manifest.get("schema_version") != "r5_bundle17r_backflow_manifest_v1":
        raise BackflowContractError("unexpected backflow manifest schema_version")
    if policy.get("schema_version") != "r5_bundle17r_backflow_policy_v1":
        raise BackflowContractError("unexpected backflow policy schema_version")

    baseline_commit = _nonempty(manifest.get("baseline_commit"))
    required_ancestor = _nonempty(policy.get("required_ancestor_commit"))
    if baseline_commit != required_ancestor:
        raise BackflowContractError(
            f"manifest baseline {baseline_commit!r} does not match policy base {required_ancestor!r}"
        )
    run_id = _nonempty(manifest.get("run_id"))
    if not run_id:
        raise BackflowContractError("manifest.run_id must be non-empty")

    activation = _as_mapping(manifest.get("activation"), "manifest.activation")
    bindings: dict[str, ArtifactBinding] = {}
    for key in ("receipt", "generation_lock", "backflow_queue", "case_matrix"):
        if key not in activation:
            raise BackflowContractError(f"manifest.activation missing {key}")
        bindings[key] = _verify_binding(
            key=key,
            repo_root=root,
            value=activation[key],
            policy=policy,
        )

    receipt = _as_mapping(load_document(root / bindings["receipt"].path), "activation receipt")
    generation_lock = _as_mapping(
        load_document(root / bindings["generation_lock"].path),
        "activation generation lock",
    )
    queue_rows, queue_columns = _read_csv(root / bindings["backflow_queue"].path)
    case_rows, case_columns = _read_csv(root / bindings["case_matrix"].path)

    missing_columns = sorted(set(REQUIRED_QUEUE_COLUMNS).difference(queue_columns))
    if missing_columns:
        raise BackflowContractError(f"backflow queue missing required columns: {missing_columns}")
    required_case_columns = {"case_id", "engineering_pass"}
    missing_case_columns = sorted(required_case_columns.difference(case_columns))
    if missing_case_columns:
        raise BackflowContractError(f"case matrix missing required columns: {missing_case_columns}")

    validation: list[ValidationIssue] = []
    expected_pairs = {
        "decision": _expected(policy, "decision"),
        "next_stage": _expected(policy, "next_stage"),
        "expected_case_count": _expected(policy, "case_count"),
        "engineering_pass_count": _expected(policy, "engineering_pass_count"),
        "blocker_count": _expected(policy, "blocker_count"),
    }
    receipt_fields = {
        "decision": receipt.get("decision"),
        "next_stage": receipt.get("next_stage"),
        "expected_case_count": receipt.get("expected_case_count"),
        "engineering_pass_count": receipt.get("engineering_pass_count"),
        "blocker_count": receipt.get("blocker_count"),
    }
    for field, expected_value in expected_pairs.items():
        if receipt_fields[field] != expected_value:
            validation.append(
                ValidationIssue(
                    code="activation_receipt_expectation_mismatch",
                    field=f"receipt.{field}",
                    message=f"expected {expected_value!r}, got {receipt_fields[field]!r}",
                )
            )

    generation_id = _nonempty(receipt.get("generation_id"))
    if not generation_id:
        validation.append(
            ValidationIssue(
                code="activation_generation_id_missing",
                field="receipt.generation_id",
                message="activation receipt must contain generation_id",
            )
        )
    if _nonempty(generation_lock.get("generation_id")) != generation_id:
        validation.append(
            ValidationIssue(
                code="activation_generation_id_mismatch",
                field="generation_lock.generation_id",
                message="activation receipt and generation lock generation IDs differ",
            )
        )

    validation.extend(
        _validate_release_boundaries(receipt=receipt, generation_lock=generation_lock)
    )

    lock_hashes = _lock_output_hashes(generation_lock)
    for key in ("backflow_queue", "case_matrix"):
        if not _is_bound_in_lock(bindings[key], lock_hashes):
            validation.append(
                ValidationIssue(
                    code="activation_output_not_bound_in_generation_lock",
                    field=key,
                    message=f"{key} is not hash-bound in Bundle 17R generation lock",
                )
            )

    expected_blockers = int(_expected(policy, "blocker_count"))
    if len(queue_rows) != expected_blockers:
        validation.append(
            ValidationIssue(
                code="backflow_queue_count_mismatch",
                field="backflow_queue",
                message=f"expected {expected_blockers} rows, got {len(queue_rows)}",
            )
        )
    if receipt.get("blocker_count") != len(queue_rows):
        validation.append(
            ValidationIssue(
                code="receipt_queue_blocker_count_mismatch",
                field="receipt.blocker_count",
                message=(
                    f"receipt blocker_count={receipt.get('blocker_count')!r} "
                    f"but queue rows={len(queue_rows)}"
                ),
            )
        )

    case_count, engineering_pass_count, case_ids = _case_matrix_summary(case_rows)
    expected_cases = int(_expected(policy, "case_count"))
    if case_count != expected_cases:
        validation.append(
            ValidationIssue(
                code="case_matrix_count_mismatch",
                field="case_matrix",
                message=f"expected {expected_cases} distinct cases, got {case_count}",
            )
        )
    if engineering_pass_count != int(_expected(policy, "engineering_pass_count")):
        validation.append(
            ValidationIssue(
                code="case_matrix_engineering_pass_mismatch",
                field="case_matrix.engineering_pass",
                message=(
                    f"expected {_expected(policy, 'engineering_pass_count')} passing cases, "
                    f"got {engineering_pass_count}"
                ),
            )
        )

    for index, row in enumerate(queue_rows, start=1):
        for field in ("code", "stage", "owner_skill", "target_stage", "message", "requested_action"):
            if not str(row.get(field, "")).strip():
                validation.append(
                    ValidationIssue(
                        code="backflow_row_required_value_missing",
                        field=f"backflow_queue[{index}].{field}",
                        message="every blocker must retain an owner, target, message, and requested action",
                    )
                )
        case_id = str(row.get("case_id", "")).strip()
        if case_id and case_id not in case_ids:
            validation.append(
                ValidationIssue(
                    code="backflow_case_not_in_case_matrix",
                    field=f"backflow_queue[{index}].case_id",
                    message=f"case {case_id!r} is absent from the case matrix",
                )
            )

    routed_issues, duplicate_count = _normalize_issue_rows(queue_rows, policy)
    work_orders = _build_work_orders(routed_issues, policy)
    validation.extend(_validate_dependency_graph(work_orders))

    manual_count = sum(issue.route_status != "routed" for issue in routed_issues)
    validation_error_count = sum(issue.severity == "error" for issue in validation)
    if validation_error_count:
        decision = "backflow_compilation_blocked"
        next_stage = "R5_bundle17r_targeted_backflow"
    elif manual_count:
        decision = "needs_manual_route_review"
        next_stage = "R5_bundle17r_targeted_backflow_route_review"
    else:
        decision = "ready_for_targeted_backflow_execution"
        next_stage = "R5_bundle17r_targeted_backflow_execution"

    input_artifacts = {
        key: {
            "path": binding.path,
            "sha256": binding.sha256,
            "size_bytes": binding.size_bytes,
        }
        for key, binding in sorted(bindings.items())
    }
    return BackflowCompilation(
        schema_version=SCHEMA_VERSION,
        bundle_id=BUNDLE_ID,
        baseline_commit=baseline_commit,
        run_id=run_id,
        source_activation_generation_id=generation_id,
        decision=decision,
        next_stage=next_stage,
        expected_case_count=expected_cases,
        case_count=case_count,
        engineering_pass_count=engineering_pass_count,
        source_blocker_count=int(receipt.get("blocker_count") or 0),
        compiled_issue_count=len(routed_issues),
        duplicate_row_count=duplicate_count,
        routed_issue_count=len(routed_issues) - manual_count,
        manual_route_issue_count=manual_count,
        work_order_count=len(work_orders),
        validation_error_count=validation_error_count,
        canonical_workflow_state_mutation_allowed=False,
        sample_quality_allowed=False,
        p2_allowed=False,
        input_artifacts=input_artifacts,
        validation_issues=tuple(
            sorted(validation, key=lambda item: (item.severity, item.code, item.field, item.message))
        ),
        issues=tuple(routed_issues),
        work_orders=tuple(work_orders),
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_yaml(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def _case_matrix(compilation: BackflowCompilation) -> list[dict[str, Any]]:
    cases = sorted({issue.case_id for issue in compilation.issues if issue.case_id})
    rows: list[dict[str, Any]] = []
    for case_id in cases:
        case_issues = [issue for issue in compilation.issues if issue.case_id == case_id]
        case_orders = [order for order in compilation.work_orders if order.case_id == case_id]
        rows.append(
            {
                "case_id": case_id,
                "blocker_count": len(case_issues),
                "routed_count": sum(issue.route_status == "routed" for issue in case_issues),
                "manual_route_count": sum(issue.route_status != "routed" for issue in case_issues),
                "work_order_count": len(case_orders),
                "route_ids": "|".join(sorted({issue.route_id for issue in case_issues})),
                "execution_status": "blocked_pending_work_orders",
            }
        )
    suite_issues = [issue for issue in compilation.issues if not issue.case_id]
    if suite_issues:
        rows.append(
            {
                "case_id": "suite",
                "blocker_count": len(suite_issues),
                "routed_count": sum(issue.route_status == "routed" for issue in suite_issues),
                "manual_route_count": sum(issue.route_status != "routed" for issue in suite_issues),
                "work_order_count": len([order for order in compilation.work_orders if not order.case_id]),
                "route_ids": "|".join(sorted({issue.route_id for issue in suite_issues})),
                "execution_status": "blocked_pending_work_orders",
            }
        )
    return rows


def _batch_plan(compilation: BackflowCompilation) -> dict[str, Any]:
    batches: dict[str, list[WorkOrder]] = {}
    for order in compilation.work_orders:
        batches.setdefault(order.batch_id, []).append(order)
    return {
        "schema_version": "r5_bundle17r_backflow_execution_batches_v1",
        "source_activation_generation_id": compilation.source_activation_generation_id,
        "decision": compilation.decision,
        "batches": [
            {
                "batch_id": batch_id,
                "work_order_ids": [order.work_order_id for order in sorted(orders, key=lambda item: item.work_order_id)],
                "owner_skills": sorted({order.owner_skill for order in orders}),
                "target_stages": sorted({order.target_stage for order in orders}),
                "blocked_by": sorted({dependency for order in orders for dependency in order.depends_on}),
                "exit_condition": "all work-order acceptance checks are evidenced by physical artifacts",
            }
            for batch_id, orders in sorted(batches.items())
        ],
        "release_boundaries": {
            "canonical_workflow_state_mutation_allowed": False,
            "sample_quality_allowed": False,
            "p2_allowed": False,
        },
    }


def render_readout(compilation: BackflowCompilation) -> str:
    route_counts: dict[str, int] = {}
    for issue in compilation.issues:
        route_counts[issue.route_id] = route_counts.get(issue.route_id, 0) + 1
    route_rows = [
        f"| {route_id} | {count} |"
        for route_id, count in sorted(route_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    work_rows = [
        "| {work_order_id} | {case_id} | {route_id} | {batch_id} | {owner_skill} | {count} | {deps} |".format(
            work_order_id=order.work_order_id,
            case_id=order.case_id or "suite",
            route_id=order.route_id,
            batch_id=order.batch_id,
            owner_skill=order.owner_skill,
            count=order.issue_count,
            deps=", ".join(order.depends_on) or "—",
        )
        for order in compilation.work_orders
    ]
    return f"""# R5 Bundle 17R-BF1 Targeted Backflow Readout

- Baseline: `{compilation.baseline_commit}`
- Source activation generation: `{compilation.source_activation_generation_id}`
- Decision: `{compilation.decision}`
- Next stage: `{compilation.next_stage}`
- Cases passing engineering: `{compilation.engineering_pass_count}` / `{compilation.case_count}`
- Source blockers: `{compilation.source_blocker_count}`
- Compiled issues: `{compilation.compiled_issue_count}`
- Routed / manual route review: `{compilation.routed_issue_count}` / `{compilation.manual_route_issue_count}`
- Work orders: `{compilation.work_order_count}`
- Validation errors: `{compilation.validation_error_count}`
- Canonical workflow-state mutation: `false`
- Sample quality allowed: `false`
- P2 allowed: `false`

## Route distribution

| Route | Issues |
|---|---:|
{chr(10).join(route_rows) if route_rows else '| — | 0 |'}

## Work orders

| Work order | Case | Route | Batch | Owner | Issues | Depends on |
|---|---|---|---|---|---:|---|
{chr(10).join(work_rows) if work_rows else '| — | — | — | — | — | 0 | — |'}

## Close boundary

This compilation is an execution plan, not evidence completion. Resolve work orders through the existing workflow skills, then rerun Bundle 16R materialization, Bundle 15R qualification, Bundle 14R regression, and Bundle 17R activation. Bundle 18R exact-hash human review remains reserved until all four cases activate.
"""


def write_backflow_outputs(
    output_dir: str | Path,
    compilation: BackflowCompilation,
) -> Mapping[str, str]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    compilation_path = root / "R5_bundle17r_backflow_compilation.json"
    issue_path = root / "R5_bundle17r_backflow_issue_ledger.csv"
    work_order_path = root / "R5_bundle17r_backflow_work_orders.csv"
    dependency_path = root / "R5_bundle17r_backflow_dependency_graph.json"
    case_path = root / "R5_bundle17r_backflow_case_matrix.csv"
    batches_path = root / "R5_bundle17r_backflow_execution_batches.yaml"
    status_path = root / "R5_bundle17r_backflow_status_proposal.yaml"
    readout_path = root / "R5_bundle17r_backflow_close_readout.md"

    _write_json(compilation_path, asdict(compilation))
    _write_csv(
        issue_path,
        [asdict(issue) for issue in compilation.issues],
        [
            "issue_id",
            "sequence",
            "case_id",
            "code",
            "stage",
            "field",
            "source_owner_skill",
            "source_target_stage",
            "message",
            "requested_action",
            "route_id",
            "batch_id",
            "owner_skill",
            "target_stage",
            "priority",
            "route_score",
            "route_status",
        ],
    )
    _write_csv(
        work_order_path,
        [
            {
                **asdict(order),
                "issue_ids": "|".join(order.issue_ids),
                "requested_actions": " || ".join(order.requested_actions),
                "required_outputs": "|".join(order.required_outputs),
                "acceptance_checks": "|".join(order.acceptance_checks),
                "depends_on": "|".join(order.depends_on),
            }
            for order in compilation.work_orders
        ],
        [
            "work_order_id",
            "case_id",
            "route_id",
            "batch_id",
            "owner_skill",
            "target_stage",
            "priority",
            "issue_ids",
            "issue_count",
            "requested_actions",
            "required_outputs",
            "acceptance_checks",
            "depends_on",
            "execution_status",
        ],
    )
    _write_json(
        dependency_path,
        {
            "schema_version": "r5_bundle17r_backflow_dependency_graph_v1",
            "nodes": [
                {
                    "work_order_id": order.work_order_id,
                    "case_id": order.case_id,
                    "route_id": order.route_id,
                    "batch_id": order.batch_id,
                    "priority": order.priority,
                }
                for order in compilation.work_orders
            ],
            "edges": [
                {"from": dependency, "to": order.work_order_id}
                for order in compilation.work_orders
                for dependency in order.depends_on
            ],
        },
    )
    _write_csv(
        case_path,
        _case_matrix(compilation),
        [
            "case_id",
            "blocker_count",
            "routed_count",
            "manual_route_count",
            "work_order_count",
            "route_ids",
            "execution_status",
        ],
    )
    _write_yaml(batches_path, _batch_plan(compilation))
    _write_yaml(
        status_path,
        {
            "schema_version": "r5_bundle17r_backflow_status_proposal_v1",
            "bundle_id": compilation.bundle_id,
            "source_activation_generation_id": compilation.source_activation_generation_id,
            "proposed_state": compilation.decision,
            "next_stage": compilation.next_stage,
            "source_blocker_count": compilation.source_blocker_count,
            "compiled_issue_count": compilation.compiled_issue_count,
            "work_order_count": compilation.work_order_count,
            "canonical_workflow_state_mutation_allowed": False,
            "sample_quality_allowed": False,
            "p2_allowed": False,
            "note": "Non-canonical proposal. Apply only after orchestrator review of physical work-order outputs.",
        },
    )
    readout_path.write_text(render_readout(compilation), encoding="utf-8")

    handoff_root = root / "work_order_handoffs"
    for order in compilation.work_orders:
        _write_yaml(
            handoff_root / f"{order.work_order_id}.yaml",
            {
                "schema_version": "r5_bundle17r_backflow_work_order_handoff_v1",
                "work_order": asdict(order),
                "source_activation_generation_id": compilation.source_activation_generation_id,
                "completion": {
                    "status": "open",
                    "completed_by": None,
                    "completed_at": None,
                    "output_artifacts": [],
                    "output_hashes_verified": False,
                },
                "release_boundaries": {
                    "canonical_workflow_state_mutation_allowed": False,
                    "sample_quality_allowed": False,
                    "p2_allowed": False,
                },
            },
        )

    output_hashes: dict[str, Mapping[str, Any]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "R5_bundle17r_backflow_generation_lock.json":
            continue
        output_hashes[path.relative_to(root).as_posix()] = {
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }

    lock_seed = {
        "schema_version": "r5_bundle17r_backflow_generation_lock_v1",
        "bundle_id": compilation.bundle_id,
        "baseline_commit": compilation.baseline_commit,
        "run_id": compilation.run_id,
        "source_activation_generation_id": compilation.source_activation_generation_id,
        "decision": compilation.decision,
        "input_artifacts": compilation.input_artifacts,
        "output_artifacts": output_hashes,
        "release_boundaries": {
            "canonical_workflow_state_mutation_allowed": False,
            "sample_quality_allowed": False,
            "p2_allowed": False,
        },
    }
    generation_id = "backflow_gen_r5_bundle17r_" + sha256_bytes(canonical_json_bytes(lock_seed))[:16]
    lock = {**lock_seed, "generation_id": generation_id}
    lock_path = root / "R5_bundle17r_backflow_generation_lock.json"
    _write_json(lock_path, lock)

    return {
        "compilation": compilation_path.as_posix(),
        "issue_ledger": issue_path.as_posix(),
        "work_orders": work_order_path.as_posix(),
        "dependency_graph": dependency_path.as_posix(),
        "case_matrix": case_path.as_posix(),
        "execution_batches": batches_path.as_posix(),
        "status_proposal": status_path.as_posix(),
        "readout": readout_path.as_posix(),
        "generation_lock": lock_path.as_posix(),
    }


__all__ = [
    "ArtifactBinding",
    "BackflowCompilation",
    "BackflowContractError",
    "RoutedIssue",
    "ValidationIssue",
    "WorkOrder",
    "canonical_json_bytes",
    "compile_backflow",
    "load_document",
    "render_readout",
    "sha256_file",
    "write_backflow_outputs",
]
