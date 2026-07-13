from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from importlib import import_module
from io import StringIO
from pathlib import Path
from typing import Any, Mapping, Sequence
import sys

from src.ingest.adapter_contracts import READY_STATUSES


class AdapterDispatchError(RuntimeError):
    pass


def _effective_contract(registry: Mapping[str, Any], adapter_id: str, source_name: str) -> dict[str, Any]:
    adapters = registry.get("adapters", {})
    raw = adapters.get(adapter_id) if isinstance(adapters, Mapping) else None
    if not isinstance(raw, Mapping):
        raise AdapterDispatchError(f"adapter contract not found: {adapter_id}")
    contract = dict(raw)
    bindings = raw.get("source_bindings", {})
    if isinstance(bindings, Mapping) and isinstance(bindings.get(source_name), Mapping):
        contract.update(bindings[source_name])
    contract.setdefault("status", raw.get("default_status", "planned"))
    return contract


def invoke_cli_adapter(
    *,
    registry: Mapping[str, Any],
    adapter_id: str,
    source_name: str,
    argv: Sequence[str],
    repo_root: str | Path,
) -> dict[str, Any]:
    """Invoke only a contract-verified CLI-style adapter.

    This function deliberately does not infer missing arguments or promote evidence. The
    adapter must write raw/manifest receipts through its normal evidence-ingest path.
    """
    contract = _effective_contract(registry, adapter_id, source_name)
    if str(contract.get("status")) not in READY_STATUSES:
        raise AdapterDispatchError(f"adapter is not operational: {adapter_id}/{source_name}")
    if str(contract.get("interface")) != "cli_main":
        raise AdapterDispatchError(f"unsupported adapter interface: {contract.get('interface')}")
    module_name = str(contract.get("module", ""))
    entrypoint_name = str(contract.get("entrypoint", ""))
    root = Path(repo_root).resolve()
    for item in reversed([root, root / "src", root / "src" / "ingest", root / "src" / "ingest" / "adapters"]):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)
    try:
        module = import_module(module_name)
        entrypoint = getattr(module, entrypoint_name)
    except Exception as exc:
        raise AdapterDispatchError(f"cannot load {module_name}:{entrypoint_name}: {type(exc).__name__}: {exc}") from exc
    stdout = StringIO()
    stderr = StringIO()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = entrypoint(list(argv))
    except SystemExit as exc:
        exit_code = int(exc.code or 0)
    except Exception as exc:
        raise AdapterDispatchError(f"adapter execution failed: {type(exc).__name__}: {exc}") from exc
    return {
        "adapter": adapter_id,
        "source_name": source_name,
        "exit_code": int(exit_code or 0),
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
        "success": int(exit_code or 0) == 0,
    }
