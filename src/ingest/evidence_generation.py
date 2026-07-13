from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable
import json


def file_digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_generation_record(
    *,
    repo_root: str | Path,
    input_paths: Iterable[str],
    generation_label: str,
    created_at: str,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    files: list[dict[str, Any]] = []
    for raw in sorted(set(str(item) for item in input_paths)):
        path = root / raw
        files.append({
            "path": raw,
            "exists": path.is_file(),
            "sha256": file_digest(path) if path.is_file() else None,
        })
    canonical = json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "schema_version": 1,
        "generation_label": generation_label,
        "generation_id": f"evidence_gen_{generation_label}_{digest[:16]}",
        "created_at": created_at,
        "input_count": len(files),
        "missing_input_count": sum(not item["exists"] for item in files),
        "inputs": files,
        "aggregate_sha256": digest,
    }


def downstream_freshness(current_generation_id: str, recorded_generation_id: str | None) -> dict[str, Any]:
    fresh = bool(recorded_generation_id) and current_generation_id == recorded_generation_id
    return {
        "fresh": fresh,
        "current_generation_id": current_generation_id,
        "recorded_generation_id": recorded_generation_id,
        "status": "current" if fresh else "stale_due_to_upstream_evidence_generation_change",
    }
