from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Mapping
import sys

import yaml

VALID_STATUSES = {
    "planned",
    "routed_only",
    "manual_only",
    "offline_snapshot_only",
    "fixture_verified",
    "live_verified",
    "operational",
    "out_of_scope",
}
READY_STATUSES = {"live_verified", "operational"}
REQUIRED_PROOFS = (
    "fixture_verified",
    "live_smoke_verified",
    "raw_archive_verified",
    "manifest_write_verified",
    "schema_fingerprint_verified",
    "claim_boundary_verified",
)


@dataclass(frozen=True)
class ContractIssue:
    issue_id: str
    severity: str
    adapter: str
    source_name: str = ""
    capability: str = ""
    endpoint_hint: str = ""
    message: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "issue_id": self.issue_id,
            "severity": self.severity,
            "adapter": self.adapter,
            "source_name": self.source_name,
            "capability": self.capability,
            "endpoint_hint": self.endpoint_hint,
            "message": self.message,
        }


def load_yaml(path: str | Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return payload


def load_contract_registry(path: str | Path) -> dict[str, Any]:
    return load_yaml(path)


def _effective_binding(contract: Mapping[str, Any], source_name: str) -> dict[str, Any]:
    result = dict(contract)
    bindings = contract.get("source_bindings", {})
    if isinstance(bindings, Mapping) and source_name in bindings:
        binding = bindings[source_name]
        if isinstance(binding, Mapping):
            result.update(binding)
    result.setdefault("status", contract.get("default_status", "planned"))
    return result


def validate_contract_registry(
    payload: Mapping[str, Any], *, repo_root: str | Path | None = None
) -> list[dict[str, str]]:
    issues: list[ContractIssue] = []
    adapters = payload.get("adapters")
    if not isinstance(adapters, Mapping):
        return [ContractIssue("ADAPTER_REGISTRY_INVALID", "critical", "", message="adapters must be a mapping").as_dict()]

    for adapter_id, raw_contract in adapters.items():
        if not isinstance(raw_contract, Mapping):
            issues.append(ContractIssue("ADAPTER_CONTRACT_INVALID", "high", str(adapter_id), message="contract must be a mapping"))
            continue
        default_status = str(raw_contract.get("default_status", "planned"))
        if default_status not in VALID_STATUSES:
            issues.append(ContractIssue("ADAPTER_STATUS_INVALID", "high", str(adapter_id), message=f"invalid status: {default_status}"))
        bindings = raw_contract.get("source_bindings", {})
        if bindings and not isinstance(bindings, Mapping):
            issues.append(ContractIssue("SOURCE_BINDINGS_INVALID", "high", str(adapter_id), message="source_bindings must be a mapping"))
            continue
        for source_name, raw_binding in (bindings.items() if isinstance(bindings, Mapping) else []):
            if not isinstance(raw_binding, Mapping):
                issues.append(ContractIssue("SOURCE_BINDING_INVALID", "high", str(adapter_id), str(source_name), message="binding must be a mapping"))
                continue
            status = str(raw_binding.get("status", default_status))
            if status not in VALID_STATUSES:
                issues.append(ContractIssue("ADAPTER_STATUS_INVALID", "high", str(adapter_id), str(source_name), message=f"invalid status: {status}"))
            if status in READY_STATUSES:
                if not raw_contract.get("module") or not raw_contract.get("entrypoint"):
                    issues.append(ContractIssue("OPERATIONAL_ENTRYPOINT_MISSING", "critical", str(adapter_id), str(source_name), message="ready binding requires module and entrypoint"))
                for proof in REQUIRED_PROOFS:
                    if not bool(raw_binding.get(proof, False)):
                        issues.append(ContractIssue("OPERATIONAL_PROOF_MISSING", "high", str(adapter_id), str(source_name), message=f"missing proof: {proof}"))
                proof_paths = raw_binding.get("proof_paths", [])
                if not isinstance(proof_paths, list) or not proof_paths:
                    issues.append(
                        ContractIssue(
                            "OPERATIONAL_PROOF_PATH_MISSING",
                            "high",
                            str(adapter_id),
                            str(source_name),
                            message="ready binding requires at least one proof path",
                        )
                    )
                elif repo_root is not None:
                    root = Path(repo_root).resolve()
                    for raw_path in proof_paths:
                        proof_path = Path(str(raw_path))
                        if not proof_path.is_absolute():
                            proof_path = root / proof_path
                        if not proof_path.is_file() or proof_path.stat().st_size == 0:
                            issues.append(
                                ContractIssue(
                                    "OPERATIONAL_PROOF_PATH_INVALID",
                                    "high",
                                    str(adapter_id),
                                    str(source_name),
                                    message=f"proof path is missing or empty: {raw_path}",
                                )
                            )
    return [issue.as_dict() for issue in issues]


def check_importability(contract: Mapping[str, Any], repo_root: str | Path) -> tuple[bool, str]:
    module_name = str(contract.get("module", "")).strip()
    entrypoint_name = str(contract.get("entrypoint", "")).strip()
    if not module_name or not entrypoint_name:
        return False, "module or entrypoint is blank"
    root = Path(repo_root).resolve()
    additions = [root, root / "src", root / "src" / "ingest", root / "src" / "ingest" / "adapters"]
    for item in reversed(additions):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)
    try:
        module = import_module(module_name)
    except Exception as exc:  # import errors are evidence for the gate
        return False, f"{type(exc).__name__}: {exc}"
    target = getattr(module, entrypoint_name, None)
    if not callable(target):
        return False, f"entrypoint is not callable: {entrypoint_name}"
    return True, "ok"


def validate_route_adapter_readiness(
    route_catalog: Mapping[str, Any],
    contract_registry: Mapping[str, Any],
    *,
    repo_root: str | Path | None = None,
    import_check: bool = False,
) -> list[dict[str, str]]:
    issues: list[ContractIssue] = []
    adapters = contract_registry.get("adapters", {})
    capabilities = route_catalog.get("capabilities", {})
    if not isinstance(capabilities, Mapping):
        return [ContractIssue("ROUTE_CATALOG_INVALID", "critical", "", message="capabilities must be a mapping").as_dict()]

    imported: dict[str, tuple[bool, str]] = {}
    for capability, raw_route in capabilities.items():
        if not isinstance(raw_route, Mapping):
            continue
        for source in raw_route.get("sources", []) or []:
            if not isinstance(source, Mapping) or not bool(source.get("enabled", True)):
                continue
            adapter_id = str(source.get("adapter", ""))
            source_name = str(source.get("source_name", ""))
            endpoint_hint = str(source.get("endpoint_hint", ""))
            severity = "critical" if str(source.get("role", "")) == "primary" else "high"
            contract = adapters.get(adapter_id) if isinstance(adapters, Mapping) else None
            if not isinstance(contract, Mapping):
                issues.append(ContractIssue("ADAPTER_CONTRACT_MISSING", severity, adapter_id, source_name, str(capability), endpoint_hint, "enabled route has no adapter contract"))
                continue
            binding = _effective_binding(contract, source_name)
            status = str(binding.get("status", "planned"))
            if status not in READY_STATUSES:
                issues.append(ContractIssue("ADAPTER_NOT_OPERATIONAL", severity, adapter_id, source_name, str(capability), endpoint_hint, f"enabled route status is {status}"))
                continue
            hints = {str(item) for item in binding.get("supported_endpoint_hints", []) or []}
            if endpoint_hint and endpoint_hint not in hints and "*" not in hints:
                issues.append(ContractIssue("ENDPOINT_HINT_UNSUPPORTED", severity, adapter_id, source_name, str(capability), endpoint_hint, f"supported hints: {sorted(hints)}"))
            for proof in REQUIRED_PROOFS:
                if not bool(binding.get(proof, False)):
                    issues.append(ContractIssue("OPERATIONAL_PROOF_MISSING", severity, adapter_id, source_name, str(capability), endpoint_hint, f"missing proof: {proof}"))
            if import_check and repo_root is not None:
                if adapter_id not in imported:
                    imported[adapter_id] = check_importability(contract, repo_root)
                ok, message = imported[adapter_id]
                if not ok:
                    issues.append(ContractIssue("ADAPTER_IMPORT_FAILED", severity, adapter_id, source_name, str(capability), endpoint_hint, message))
    return [issue.as_dict() for issue in issues]
