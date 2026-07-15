"""R5 Bundle 17R: deterministic activation receipt and human-review handoff.

This module binds the physical outputs of the existing Bundle 16R evidence-pack
materializer, Bundle 15R evidence qualification, and Bundle 14R real-company
regression into one deterministic receipt.  It does not fetch or review evidence,
rerun upstream engines, mutate canonical workflow state, accept human review, or
authorize sample quality/P2.

The activation manifest is deliberately pointer-based: it identifies the exact
physical stage and case artifacts, their SHA-256 hashes, and the JSON/YAML
pointers that prove required assertions.  The policy owns the expected values,
so a manifest cannot weaken a gate by changing an expected result.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    import yaml
except ImportError as exc:  # pragma: no cover - dependency is explicit in CI
    raise RuntimeError("PyYAML is required for Bundle 17R") from exc


class ActivationContractError(ValueError):
    """Raised when the manifest or policy cannot be interpreted safely."""


@dataclass(frozen=True)
class ActivationIssue:
    code: str
    stage: str
    field: str
    message: str
    case_id: str = ""
    owner_skill: str = "research-orchestrator"
    target_stage: str = "R5_bundle17r_targeted_backflow"
    requested_action: str = "inspect and repair the exact physical binding"


@dataclass(frozen=True)
class VerifiedArtifact:
    key: str
    path: str
    sha256: str
    size_bytes: int
    document: Any | None = field(default=None, compare=False, repr=False)


@dataclass(frozen=True)
class CaseActivationResult:
    case_id: str
    issuer_ticker: str
    passed: bool
    artifact_hashes: Mapping[str, str]
    issue_codes: tuple[str, ...]
    human_review_status: str


@dataclass(frozen=True)
class ActivationReceipt:
    schema_version: str
    bundle_id: str
    baseline_commit: str
    run_id: str
    input_manifest_sha256: str
    policy_sha256: str
    runtime_sha256: str
    generation_id: str
    decision: str
    next_stage: str
    expected_case_count: int
    case_count: int
    engineering_pass_count: int
    blocker_count: int
    stage_hashes: Mapping[str, Mapping[str, str]]
    case_results: tuple[CaseActivationResult, ...]
    canonical_workflow_state_mutation_allowed: bool
    sample_quality_allowed: bool
    p2_allowed: bool


@dataclass(frozen=True)
class ActivationArtifacts:
    receipt: ActivationReceipt
    issues: tuple[ActivationIssue, ...]
    handoffs: Mapping[str, Mapping[str, Any]]
    status_proposal: Mapping[str, Any]
    generation_lock: Mapping[str, Any]


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


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
    if suffix in {".md", ".txt", ".csv"}:
        return text
    raise ActivationContractError(f"unsupported document extension: {document_path}")


def _as_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ActivationContractError(f"{field_name} must be a mapping")
    return value


def _as_sequence(value: Any, field_name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ActivationContractError(f"{field_name} must be a sequence")
    return value


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _pointer_get(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise ActivationContractError(f"JSON pointer must start with '/': {pointer}")
    current = document
    for raw_token in pointer.split("/")[1:]:
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            if token not in current:
                raise KeyError(pointer)
            current = current[token]
        elif isinstance(current, Sequence) and not isinstance(current, (str, bytes, bytearray)):
            if not token.isdigit():
                raise KeyError(pointer)
            index = int(token)
            if index >= len(current):
                raise KeyError(pointer)
            current = current[index]
        else:
            raise KeyError(pointer)
    return current


def _safe_repo_path(repo_root: Path, raw_path: Any, policy: Mapping[str, Any], *, field_name: str) -> tuple[Path, str]:
    text = _string(raw_path)
    if not text:
        raise ActivationContractError(f"{field_name} is required")
    candidate = Path(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ActivationContractError(f"unsafe repository-relative path: {text}")
    normalized = candidate.as_posix()
    lowered = normalized.lower()
    for fragment in policy.get("forbidden_path_fragments", []):
        if _string(fragment).lower() in lowered:
            raise ActivationContractError(f"forbidden artifact path fragment in {text}: {fragment}")
    allowed_roots = tuple(_string(item).rstrip("/") + "/" for item in policy.get("allowed_artifact_roots", []))
    if allowed_roots and not any(normalized.startswith(root) for root in allowed_roots):
        raise ActivationContractError(f"artifact path is outside allowed roots: {text}")
    allowed_extensions = {_string(item).lower() for item in policy.get("allowed_artifact_extensions", [])}
    if allowed_extensions and candidate.suffix.lower() not in allowed_extensions:
        raise ActivationContractError(f"artifact extension is not allowed: {text}")
    resolved_root = repo_root.resolve()
    resolved = (repo_root / candidate).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ActivationContractError(f"artifact escapes repository root: {text}")
    return resolved, normalized


def _verify_artifact(
    *,
    repo_root: Path,
    key: str,
    binding: Mapping[str, Any],
    policy: Mapping[str, Any],
    stage: str,
    field_name: str,
    case_id: str = "",
) -> tuple[VerifiedArtifact | None, list[ActivationIssue]]:
    issues: list[ActivationIssue] = []
    try:
        physical, normalized = _safe_repo_path(repo_root, binding.get("path"), policy, field_name=f"{field_name}.path")
    except ActivationContractError as exc:
        issues.append(
            ActivationIssue(
                code="UNSAFE_ARTIFACT_PATH",
                stage=stage,
                field=f"{field_name}.path",
                message=str(exc),
                case_id=case_id,
                owner_skill="quality-review",
                requested_action="replace the binding with a safe repository-relative physical artifact path",
            )
        )
        return None, issues
    expected_sha = _string(binding.get("sha256")).lower()
    if len(expected_sha) != 64 or any(ch not in "0123456789abcdef" for ch in expected_sha):
        issues.append(
            ActivationIssue(
                code="ARTIFACT_SHA_INVALID",
                stage=stage,
                field=f"{field_name}.sha256",
                message="expected SHA-256 must be 64 lowercase hexadecimal characters",
                case_id=case_id,
                owner_skill="quality-review",
                requested_action="record the exact physical artifact SHA-256",
            )
        )
        return None, issues
    if not physical.is_file():
        issues.append(
            ActivationIssue(
                code="ARTIFACT_MISSING",
                stage=stage,
                field=field_name,
                message=f"physical artifact does not exist: {normalized}",
                case_id=case_id,
                owner_skill="research-orchestrator",
                requested_action="rerun the owning stage and bind the emitted physical artifact",
            )
        )
        return None, issues
    actual_sha = sha256_file(physical)
    if actual_sha != expected_sha:
        issues.append(
            ActivationIssue(
                code="ARTIFACT_HASH_MISMATCH",
                stage=stage,
                field=field_name,
                message=f"SHA-256 mismatch for {normalized}: expected {expected_sha}, actual {actual_sha}",
                case_id=case_id,
                owner_skill="quality-review",
                requested_action="regenerate or re-review the binding; do not reuse a stale hash",
            )
        )
        return None, issues
    try:
        document = load_document(physical)
    except Exception as exc:  # noqa: BLE001 - converted into a deterministic issue
        issues.append(
            ActivationIssue(
                code="ARTIFACT_PARSE_FAILED",
                stage=stage,
                field=field_name,
                message=f"cannot parse {normalized}: {exc}",
                case_id=case_id,
                owner_skill="quality-review",
                requested_action="repair the physical artifact or bind the correct output file",
            )
        )
        return None, issues
    return VerifiedArtifact(key=key, path=normalized, sha256=actual_sha, size_bytes=physical.stat().st_size, document=document), issues


def _expected_value(raw_expected: Any, *, case_id: str, issuer_ticker: str, artifacts: Mapping[str, VerifiedArtifact]) -> tuple[str, Any]:
    if raw_expected == "$nonempty":
        return "nonempty", None
    if raw_expected == "$pre_human_review":
        return "one_of", ("pending", "not_triggered")
    if raw_expected == "$case_id":
        return "equals", case_id
    if raw_expected == "$issuer_ticker":
        return "equals", issuer_ticker
    if isinstance(raw_expected, str) and raw_expected.startswith("$artifact_sha256:"):
        key = raw_expected.split(":", 1)[1]
        if key not in artifacts:
            raise ActivationContractError(f"dynamic expected value references missing artifact: {key}")
        return "equals", artifacts[key].sha256
    return "equals", raw_expected


def _check_assertions(
    *,
    stage: str,
    assertions: Mapping[str, Any],
    required: Mapping[str, Any],
    artifacts: Mapping[str, VerifiedArtifact],
    default_artifact_key: str | None,
    case_id: str = "",
    issuer_ticker: str = "",
) -> list[ActivationIssue]:
    issues: list[ActivationIssue] = []
    missing_ids = sorted(set(required).difference(assertions))
    for assertion_id in missing_ids:
        issues.append(
            ActivationIssue(
                code="ASSERTION_BINDING_MISSING",
                stage=stage,
                field=f"assertions.{assertion_id}",
                message=f"required assertion binding is missing: {assertion_id}",
                case_id=case_id,
                owner_skill="research-orchestrator",
                requested_action="bind the required assertion to an exact JSON/YAML pointer",
            )
        )
    for assertion_id, expected_raw in required.items():
        if assertion_id not in assertions:
            continue
        binding = assertions[assertion_id]
        if isinstance(binding, str):
            artifact_key = default_artifact_key or ""
            pointer = binding
        elif isinstance(binding, Mapping):
            artifact_key = _string(binding.get("artifact")) or (default_artifact_key or "")
            pointer = _string(binding.get("pointer"))
        else:
            issues.append(
                ActivationIssue(
                    code="ASSERTION_BINDING_INVALID",
                    stage=stage,
                    field=f"assertions.{assertion_id}",
                    message="assertion binding must be a pointer string or mapping",
                    case_id=case_id,
                    owner_skill="research-orchestrator",
                    requested_action="replace the assertion with an artifact key and JSON/YAML pointer",
                )
            )
            continue
        if artifact_key not in artifacts:
            issues.append(
                ActivationIssue(
                    code="ASSERTION_ARTIFACT_UNKNOWN",
                    stage=stage,
                    field=f"assertions.{assertion_id}.artifact",
                    message=f"assertion references unknown or invalid artifact: {artifact_key}",
                    case_id=case_id,
                    owner_skill="research-orchestrator",
                    requested_action="bind the assertion to a verified artifact",
                )
            )
            continue
        try:
            actual = _pointer_get(artifacts[artifact_key].document, pointer)
        except (ActivationContractError, KeyError) as exc:
            issues.append(
                ActivationIssue(
                    code="ASSERTION_POINTER_UNRESOLVED",
                    stage=stage,
                    field=f"assertions.{assertion_id}.pointer",
                    message=f"cannot resolve pointer {pointer!r} in {artifacts[artifact_key].path}: {exc}",
                    case_id=case_id,
                    owner_skill="quality-review",
                    requested_action="bind the assertion to the exact field emitted by the upstream artifact",
                )
            )
            continue
        try:
            mode, expected = _expected_value(
                expected_raw,
                case_id=case_id,
                issuer_ticker=issuer_ticker,
                artifacts=artifacts,
            )
        except ActivationContractError as exc:
            issues.append(
                ActivationIssue(
                    code="ASSERTION_EXPECTATION_INVALID",
                    stage=stage,
                    field=f"assertions.{assertion_id}",
                    message=str(exc),
                    case_id=case_id,
                    owner_skill="quality-review",
                    requested_action="repair the policy or artifact binding without weakening the gate",
                )
            )
            continue
        if mode == "nonempty":
            passed = bool(actual)
        elif mode == "one_of":
            passed = actual in expected
        else:
            passed = actual == expected
        if not passed:
            issues.append(
                ActivationIssue(
                    code="ASSERTION_FAILED",
                    stage=stage,
                    field=f"assertions.{assertion_id}",
                    message=(
                        f"assertion {assertion_id} failed in {artifacts[artifact_key].path}: "
                        f"actual={actual!r}, expected={expected_raw!r}"
                    ),
                    case_id=case_id,
                    owner_skill="quality-review",
                    requested_action="route the failed upstream gate to its owning stage; do not edit the expected value",
                )
            )
    return issues


def _load_mapping(path: str | Path, name: str) -> Mapping[str, Any]:
    value = load_document(path)
    return _as_mapping(value, name)


def evaluate_activation(
    *,
    repo_root: str | Path,
    manifest_path: str | Path,
    policy_path: str | Path,
) -> ActivationArtifacts:
    root = Path(repo_root)
    manifest_file = Path(manifest_path)
    policy_file = Path(policy_path)
    manifest = _load_mapping(manifest_file, "activation manifest")
    policy = _load_mapping(policy_file, "activation policy")

    if manifest.get("schema_version") != policy.get("manifest_schema_version"):
        raise ActivationContractError(
            f"manifest schema mismatch: {manifest.get('schema_version')!r} != {policy.get('manifest_schema_version')!r}"
        )
    if policy.get("schema_version") != "r5_bundle17r_activation_policy_v1":
        raise ActivationContractError("unsupported Bundle 17R policy schema")

    expected_case_count = int(policy.get("expected_case_count", 0))
    run_id = _string(manifest.get("run_id"))
    if not run_id:
        raise ActivationContractError("activation manifest run_id is required")
    baseline_commit = _string(manifest.get("baseline_commit"))
    if baseline_commit != _string(policy.get("required_ancestor_commit")):
        raise ActivationContractError("activation manifest must bind the exact Bundle 16R implementation baseline")

    issues: list[ActivationIssue] = []
    stage_hashes: dict[str, dict[str, str]] = {}
    stage_bindings = _as_mapping(manifest.get("stage_bindings"), "stage_bindings")
    required_stage_assertions = _as_mapping(policy.get("suite_assertions"), "suite_assertions")
    for stage_name in sorted(required_stage_assertions):
        stage = _as_mapping(stage_bindings.get(stage_name), f"stage_bindings.{stage_name}") if stage_name in stage_bindings else {}
        if not stage:
            issues.append(
                ActivationIssue(
                    code="STAGE_BINDING_MISSING",
                    stage=stage_name,
                    field=f"stage_bindings.{stage_name}",
                    message=f"required stage binding is missing: {stage_name}",
                    requested_action="run the upstream stage and bind its suite artifact and generation lock",
                )
            )
            continue
        stage_artifacts: dict[str, VerifiedArtifact] = {}
        for key in ("suite", "generation_lock"):
            raw_binding = stage.get(key)
            if not isinstance(raw_binding, Mapping):
                issues.append(
                    ActivationIssue(
                        code="STAGE_ARTIFACT_BINDING_MISSING",
                        stage=stage_name,
                        field=f"stage_bindings.{stage_name}.{key}",
                        message=f"required stage artifact binding is missing: {key}",
                        requested_action="bind the exact physical suite output and generation lock",
                    )
                )
                continue
            artifact, artifact_issues = _verify_artifact(
                repo_root=root,
                key=key,
                binding=raw_binding,
                policy=policy,
                stage=stage_name,
                field_name=f"stage_bindings.{stage_name}.{key}",
            )
            issues.extend(artifact_issues)
            if artifact is not None:
                stage_artifacts[key] = artifact
        if stage_artifacts:
            stage_hashes[stage_name] = {key: artifact.sha256 for key, artifact in sorted(stage_artifacts.items())}
        assertions = stage.get("assertions", {})
        if not isinstance(assertions, Mapping):
            assertions = {}
        issues.extend(
            _check_assertions(
                stage=stage_name,
                assertions=assertions,
                required=_as_mapping(required_stage_assertions[stage_name], f"suite_assertions.{stage_name}"),
                artifacts=stage_artifacts,
                default_artifact_key="suite",
            )
        )

    case_records = _as_sequence(manifest.get("cases"), "cases")
    case_ids: list[str] = []
    tickers: list[str] = []
    for index, raw_case in enumerate(case_records):
        if not isinstance(raw_case, Mapping):
            issues.append(
                ActivationIssue(
                    code="CASE_BINDING_INVALID",
                    stage="case_activation",
                    field=f"cases[{index}]",
                    message="case binding must be a mapping",
                    requested_action="replace the entry with a valid case binding",
                )
            )
            continue
        case_ids.append(_string(raw_case.get("case_id")))
        tickers.append(_string(raw_case.get("issuer_ticker")))
    if len(case_records) != expected_case_count:
        issues.append(
            ActivationIssue(
                code="CASE_COUNT_MISMATCH",
                stage="case_activation",
                field="cases",
                message=f"expected {expected_case_count} cases, found {len(case_records)}",
                requested_action="bind every registered real-company case exactly once",
            )
        )
    duplicate_case_ids = sorted({value for value in case_ids if value and case_ids.count(value) > 1})
    duplicate_tickers = sorted({value for value in tickers if value and tickers.count(value) > 1})
    if duplicate_case_ids:
        issues.append(
            ActivationIssue(
                code="CASE_ID_DUPLICATE",
                stage="case_activation",
                field="cases.case_id",
                message=f"duplicate case IDs: {duplicate_case_ids}",
                requested_action="deduplicate case bindings without dropping a registered case",
            )
        )
    if duplicate_tickers:
        issues.append(
            ActivationIssue(
                code="ISSUER_TICKER_DUPLICATE",
                stage="case_activation",
                field="cases.issuer_ticker",
                message=f"duplicate issuer tickers: {duplicate_tickers}",
                requested_action="bind each issuer exactly once",
            )
        )

    global_case_blocked = bool(issues)
    required_case_artifacts = tuple(_string(item) for item in policy.get("required_case_artifacts", []))
    required_case_assertions = _as_mapping(policy.get("case_assertions"), "case_assertions")
    case_results: list[CaseActivationResult] = []
    handoffs: dict[str, Mapping[str, Any]] = {}

    for index, raw_case in enumerate(case_records):
        if not isinstance(raw_case, Mapping):
            continue
        case_id = _string(raw_case.get("case_id"))
        issuer_ticker = _string(raw_case.get("issuer_ticker"))
        case_issue_start = len(issues)
        if not case_id:
            issues.append(
                ActivationIssue(
                    code="CASE_ID_MISSING",
                    stage="case_activation",
                    field=f"cases[{index}].case_id",
                    message="case_id is required",
                    requested_action="use the exact Bundle 14R case ID",
                )
            )
        if not issuer_ticker:
            issues.append(
                ActivationIssue(
                    code="ISSUER_TICKER_MISSING",
                    stage="case_activation",
                    field=f"cases[{index}].issuer_ticker",
                    message="issuer_ticker is required",
                    case_id=case_id,
                    requested_action="bind the issuer identifier from the registered case contract",
                )
            )
        raw_artifacts = raw_case.get("artifacts")
        artifact_bindings = raw_artifacts if isinstance(raw_artifacts, Mapping) else {}
        verified: dict[str, VerifiedArtifact] = {}
        for key in required_case_artifacts:
            raw_binding = artifact_bindings.get(key)
            if not isinstance(raw_binding, Mapping):
                issues.append(
                    ActivationIssue(
                        code="CASE_ARTIFACT_BINDING_MISSING",
                        stage="case_activation",
                        field=f"cases[{index}].artifacts.{key}",
                        message=f"required case artifact binding is missing: {key}",
                        case_id=case_id,
                        requested_action="run the owning stage and bind the exact physical artifact",
                    )
                )
                continue
            artifact, artifact_issues = _verify_artifact(
                repo_root=root,
                key=key,
                binding=raw_binding,
                policy=policy,
                stage="case_activation",
                field_name=f"cases[{index}].artifacts.{key}",
                case_id=case_id,
            )
            issues.extend(artifact_issues)
            if artifact is not None:
                verified[key] = artifact
        reader = verified.get("reader")
        if reader is not None and reader.size_bytes < int(policy.get("minimum_reader_bytes", 0)):
            issues.append(
                ActivationIssue(
                    code="READER_TOO_SMALL",
                    stage="case_activation",
                    field=f"cases[{index}].artifacts.reader",
                    message=f"Reader is only {reader.size_bytes} bytes",
                    case_id=case_id,
                    owner_skill="quality-review",
                    requested_action="bind the full Reader candidate generated by Bundle 14R",
                )
            )
        raw_assertions = raw_case.get("assertions")
        assertions = raw_assertions if isinstance(raw_assertions, Mapping) else {}
        issues.extend(
            _check_assertions(
                stage="case_activation",
                assertions=assertions,
                required=required_case_assertions,
                artifacts=verified,
                default_artifact_key=None,
                case_id=case_id,
                issuer_ticker=issuer_ticker,
            )
        )
        case_issues = [issue for issue in issues[case_issue_start:] if issue.case_id in {"", case_id}]
        passed = (not global_case_blocked) and (not case_issues) and len(verified) == len(required_case_artifacts)
        status = "pending" if passed else "not_ready"
        artifact_hashes = {key: artifact.sha256 for key, artifact in sorted(verified.items())}
        result = CaseActivationResult(
            case_id=case_id,
            issuer_ticker=issuer_ticker,
            passed=passed,
            artifact_hashes=artifact_hashes,
            issue_codes=tuple(sorted({issue.code for issue in case_issues})),
            human_review_status=status,
        )
        case_results.append(result)
        if case_id:
            handoffs[case_id] = {
                "schema_version": "r5_bundle17r_human_review_handoff_v1",
                "bundle_id": "R5_BUNDLE17R_ACTIVATION_RECEIPT",
                "case_id": case_id,
                "issuer_ticker": issuer_ticker,
                "review_status": status,
                "reviewer": None,
                "reviewed_at": None,
                "decision_notes": None,
                "reader": _artifact_handoff(verified.get("reader")),
                "generation_lock": _artifact_handoff(verified.get("generation_lock")),
                "quality_scorecard": _artifact_handoff(verified.get("quality_scorecard")),
                "traceability": _artifact_handoff(verified.get("traceability")),
                "automated_acceptance_allowed": False,
                "canonical_workflow_state_mutation_allowed": False,
                "sample_quality_allowed": False,
                "p2_allowed": False,
            }

    # Global stage issues apply to every case and therefore prevent activation.
    engineering_pass_count = sum(1 for result in case_results if result.passed)
    all_pass = (
        not issues
        and len(case_results) == expected_case_count
        and engineering_pass_count == expected_case_count
    )
    decision = "activation_ready_for_exact_hash_human_review" if all_pass else "needs_targeted_backflow"
    next_stage = "R5_bundle18r_exact_hash_human_review" if all_pass else "R5_bundle17r_targeted_backflow"

    manifest_sha = sha256_file(manifest_file)
    policy_sha = sha256_file(policy_file)
    runtime_sha = sha256_file(Path(__file__))
    receipt_seed = {
        "schema_version": "r5_bundle17r_activation_receipt_v1",
        "bundle_id": "R5_BUNDLE17R_ACTIVATION_RECEIPT",
        "baseline_commit": baseline_commit,
        "run_id": run_id,
        "input_manifest_sha256": manifest_sha,
        "policy_sha256": policy_sha,
        "runtime_sha256": runtime_sha,
        "decision": decision,
        "next_stage": next_stage,
        "expected_case_count": expected_case_count,
        "case_count": len(case_results),
        "engineering_pass_count": engineering_pass_count,
        "blocker_count": len(issues),
        "stage_hashes": stage_hashes,
        "case_results": [asdict(result) for result in sorted(case_results, key=lambda item: item.case_id)],
        "canonical_workflow_state_mutation_allowed": False,
        "sample_quality_allowed": False,
        "p2_allowed": False,
    }
    generation_id = "activation_gen_r5_bundle17r_" + sha256_bytes(canonical_json_bytes(receipt_seed))[:16]
    receipt = ActivationReceipt(
        schema_version=receipt_seed["schema_version"],
        bundle_id=receipt_seed["bundle_id"],
        baseline_commit=baseline_commit,
        run_id=run_id,
        input_manifest_sha256=manifest_sha,
        policy_sha256=policy_sha,
        runtime_sha256=runtime_sha,
        generation_id=generation_id,
        decision=decision,
        next_stage=next_stage,
        expected_case_count=expected_case_count,
        case_count=len(case_results),
        engineering_pass_count=engineering_pass_count,
        blocker_count=len(issues),
        stage_hashes=stage_hashes,
        case_results=tuple(sorted(case_results, key=lambda item: item.case_id)),
        canonical_workflow_state_mutation_allowed=False,
        sample_quality_allowed=False,
        p2_allowed=False,
    )
    for case_id, handoff in list(handoffs.items()):
        handoffs[case_id] = {**handoff, "activation_generation_id": generation_id}
    status_proposal = {
        "schema_version": "r5_bundle17r_status_proposal_v1",
        "bundle_id": receipt.bundle_id,
        "activation_generation_id": generation_id,
        "run_id": run_id,
        "proposed_state": decision,
        "next_stage": next_stage,
        "case_count": receipt.case_count,
        "engineering_pass_count": receipt.engineering_pass_count,
        "blocker_count": receipt.blocker_count,
        "canonical_workflow_state_mutation_allowed": False,
        "sample_quality_allowed": False,
        "p2_allowed": False,
        "note": "Non-canonical proposal. A later reviewed Bundle 18R decision is required before any sample-quality promotion.",
    }
    generation_lock = {
        "schema_version": "r5_bundle17r_generation_lock_v1",
        "bundle_id": receipt.bundle_id,
        "generation_id": generation_id,
        "baseline_commit": baseline_commit,
        "run_id": run_id,
        "input_manifest_sha256": manifest_sha,
        "policy_sha256": policy_sha,
        "runtime_sha256": runtime_sha,
        "stage_hashes": stage_hashes,
        "case_artifact_hashes": {
            result.case_id: dict(result.artifact_hashes) for result in receipt.case_results
        },
        "release_boundaries": {
            "canonical_workflow_state_mutation_allowed": False,
            "sample_quality_allowed": False,
            "p2_allowed": False,
        },
    }
    return ActivationArtifacts(
        receipt=receipt,
        issues=tuple(sorted(issues, key=lambda item: (item.case_id, item.stage, item.code, item.field, item.message))),
        handoffs={key: handoffs[key] for key in sorted(handoffs)},
        status_proposal=status_proposal,
        generation_lock=generation_lock,
    )


def _artifact_handoff(artifact: VerifiedArtifact | None) -> Mapping[str, Any] | None:
    if artifact is None:
        return None
    return {"path": artifact.path, "sha256": artifact.sha256, "size_bytes": artifact.size_bytes}


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_yaml(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def render_readout(artifacts: ActivationArtifacts) -> str:
    receipt = artifacts.receipt
    case_rows = []
    for result in receipt.case_results:
        case_rows.append(
            "| {case_id} | {ticker} | {passed} | {review} | {issues} |".format(
                case_id=result.case_id,
                ticker=result.issuer_ticker,
                passed="PASS" if result.passed else "BLOCKED",
                review=result.human_review_status,
                issues=", ".join(result.issue_codes) or "—",
            )
        )
    issue_rows = []
    for issue in artifacts.issues:
        issue_rows.append(
            "| {case_id} | {code} | {owner} | {stage} | {action} |".format(
                case_id=issue.case_id or "suite",
                code=issue.code,
                owner=issue.owner_skill,
                stage=issue.target_stage,
                action=issue.requested_action.replace("|", "/"),
            )
        )
    return f"""# R5 Bundle 17R Activation Receipt Readout

- Baseline: `{receipt.baseline_commit}`
- Run ID: `{receipt.run_id}`
- Generation ID: `{receipt.generation_id}`
- Decision: `{receipt.decision}`
- Next stage: `{receipt.next_stage}`
- Cases passed: `{receipt.engineering_pass_count}` / `{receipt.expected_case_count}`
- Blockers: `{receipt.blocker_count}`
- Canonical workflow-state mutation: `false`
- Sample quality allowed: `false`
- P2 allowed: `false`

## Case matrix

| Case | Ticker | Engineering | Human review | Issue codes |
|---|---|---|---|---|
{chr(10).join(case_rows)}

## Targeted backflow

| Case | Code | Owner skill | Target stage | Requested action |
|---|---|---|---|---|
{chr(10).join(issue_rows) if issue_rows else '| — | — | — | — | none |'}

## Boundary

Bundle 17R binds and validates physical Bundle 16R, 15R, and 14R outputs and emits exact-hash review handoffs. It does not create evidence, alter upstream results, synthesize reviewer approval, mutate canonical state, or authorize sample quality/P2.
"""


def write_activation_outputs(output_dir: str | Path, artifacts: ActivationArtifacts) -> None:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    receipt_dict = asdict(artifacts.receipt)
    receipt_path = root / "R5_bundle17r_activation_receipt.json"
    issues_path = root / "R5_bundle17r_backflow_queue.csv"
    matrix_path = root / "R5_bundle17r_case_matrix.csv"
    status_path = root / "R5_bundle17r_status_proposal.yaml"
    readout_path = root / "R5_bundle17r_close_readout.md"

    _write_json(receipt_path, receipt_dict)
    _write_csv(
        issues_path,
        [asdict(issue) for issue in artifacts.issues],
        ["case_id", "code", "stage", "field", "owner_skill", "target_stage", "message", "requested_action"],
    )
    _write_csv(
        matrix_path,
        [
            {
                "case_id": result.case_id,
                "issuer_ticker": result.issuer_ticker,
                "engineering_pass": result.passed,
                "human_review_status": result.human_review_status,
                "issue_codes": "|".join(result.issue_codes),
            }
            for result in artifacts.receipt.case_results
        ],
        ["case_id", "issuer_ticker", "engineering_pass", "human_review_status", "issue_codes"],
    )
    for case_id, handoff in artifacts.handoffs.items():
        _write_yaml(root / "human_review_handoffs" / f"{case_id}.yaml", handoff)
    _write_yaml(status_path, artifacts.status_proposal)
    readout_path.write_text(render_readout(artifacts), encoding="utf-8")

    locked_artifacts: dict[str, Mapping[str, Any]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "R5_bundle17r_generation_lock.json":
            continue
        locked_artifacts[path.relative_to(root).as_posix()] = {
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
    generation_lock = {**artifacts.generation_lock, "output_artifacts": locked_artifacts}
    _write_json(root / "R5_bundle17r_generation_lock.json", generation_lock)


__all__ = [
    "ActivationArtifacts",
    "ActivationContractError",
    "ActivationIssue",
    "ActivationReceipt",
    "CaseActivationResult",
    "canonical_json_bytes",
    "evaluate_activation",
    "load_document",
    "render_readout",
    "sha256_file",
    "write_activation_outputs",
]
