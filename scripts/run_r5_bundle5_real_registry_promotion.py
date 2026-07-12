#!/usr/bin/env python3
"""Prepare, back up, promote and verify Bundle 5.5 real registries."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import promote_r5_reviewed_inputs_to_registries as promoter  # noqa: E402
import r5_reviewed_input_registry_io as registry_io  # noqa: E402
import validate_r5_reviewed_input_dropzone as dropzone  # noqa: E402

WORKFLOW_ID = "wf_20260703_stock_first_002837_invic"
STOCK_CODE = "002837"


def _repo_rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _semantic_summary(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"artifact_type": None, "status": "missing"}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"artifact_type": None, "status": "unreadable", "error": type(exc).__name__}
    if not isinstance(data, dict):
        return {"artifact_type": None, "status": "non_mapping"}
    rows = data.get("assumptions") or data.get("items") or data.get("valuation_input_refs") or []
    return {
        "artifact_type": data.get("artifact_type"),
        "schema_version": data.get("schema_version"),
        "review_status": data.get("review_status"),
        "status": data.get("status"),
        "row_count_hint": len(rows) if isinstance(rows, list) else None,
    }


def registry_paths(run_dir: Path) -> dict[str, Path]:
    return {key: run_dir / filename for key, filename in promoter.REGISTRY_FILENAMES.items()}


def build_prepromotion_inventory(
    repo_root: Path,
    run_dir: Path,
    dropzone_root: Path,
    dry_run: dict[str, Any],
) -> dict[str, Any]:
    validation = dropzone.validate_root(dropzone_root)
    if validation["status"] != "pass":
        raise ValueError("full dropzone validation must pass before pre-promotion inventory")
    input_files = []
    for path in dropzone.iter_input_files(dropzone_root):
        input_files.append(
            {
                "path": _repo_rel(path, repo_root),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
                "record_count": len(dropzone.read_dropzone_file(path)),
            }
        )
    targets: dict[str, Any] = {}
    for key, path in registry_paths(run_dir).items():
        targets[key] = {
            "path": _repo_rel(path, repo_root),
            "exists": path.is_file(),
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size if path.is_file() else 0,
            "semantic_summary": _semantic_summary(path),
        }
    signature_payload = {
        "inputs": [(row["path"], row["sha256"]) for row in input_files],
        "targets": [(key, row["sha256"]) for key, row in sorted(targets.items())],
    }
    signature = hashlib.sha256(json.dumps(signature_payload, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "artifact_type": "R5_bundle5_prepromotion_inventory",
        "schema_version": "r5_bundle5_prepromotion_inventory_v0.1",
        "workflow_id": WORKFLOW_ID,
        "stock_code": STOCK_CODE,
        "inventory_signature": signature,
        "dropzone_validation_status": validation["status"],
        "accepted_count": validation["accepted_count"],
        "accepted_degraded_count": validation["accepted_degraded_count"],
        "input_files": input_files,
        "registry_targets": targets,
        "dry_run": {
            "promotion_status": dry_run.get("promotion_status"),
            "validation_status": dry_run.get("validation_status"),
            "allowed_report_level": dry_run.get("allowed_report_level"),
            "sample_quality_report_allowed": dry_run.get("sample_quality_report_allowed"),
            "p2_allowed": dry_run.get("p2_allowed"),
            "planned_actions": {
                key: item.get("planned_action")
                for key, item in (dry_run.get("registry_results") or {}).items()
            },
        },
        "hard_boundaries": {
            "sample_quality_report_allowed": False,
            "p2_allowed": False,
            "canonical_write_authorized_by_card": "card_5_5",
        },
    }


def create_backup_manifest(repo_root: Path, run_dir: Path, inventory: dict[str, Any]) -> dict[str, Any]:
    signature = str(inventory["inventory_signature"])
    backup_dir = run_dir / "backups" / f"r5_bundle5_pre_promotion_{signature[:12]}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for key, target_info in inventory["registry_targets"].items():
        target = repo_root / target_info["path"]
        backup_path = backup_dir / f"{target.name}.pre_promotion.bak"
        if target_info["exists"]:
            if backup_path.exists():
                if _sha256(backup_path) != target_info["sha256"]:
                    raise ValueError(f"existing backup hash mismatch: {backup_path}")
                action = "verified_existing"
            else:
                shutil.copy2(target, backup_path)
                action = "created"
            backup_hash = _sha256(backup_path)
            if backup_hash != target_info["sha256"]:
                raise ValueError(f"backup verification failed: {backup_path}")
            backup_rel: str | None = _repo_rel(backup_path, repo_root)
        else:
            action = "recorded_missing_target"
            backup_hash = None
            backup_rel = None
        items.append(
            {
                "registry_key": key,
                "target_path": target_info["path"],
                "pre_exists": target_info["exists"],
                "pre_hash": target_info["sha256"],
                "backup_path": backup_rel,
                "backup_hash": backup_hash,
                "action": action,
            }
        )
    return {
        "artifact_type": "R5_bundle5_registry_backup_manifest",
        "schema_version": "r5_bundle5_registry_backup_manifest_v0.1",
        "workflow_id": WORKFLOW_ID,
        "inventory_signature": signature,
        "backup_dir": _repo_rel(backup_dir, repo_root),
        "backup_verified": True,
        "items": items,
        "restore_strategy": "restore verified pre-existing bytes atomically; remove only targets recorded as absent before promotion",
    }


def verify_backup_and_prestate(repo_root: Path, manifest: dict[str, Any]) -> None:
    if manifest.get("backup_verified") is not True:
        raise ValueError("backup manifest is not verified")
    for item in manifest.get("items") or []:
        target = repo_root / item["target_path"]
        if target.is_file() != bool(item["pre_exists"]):
            raise ValueError(f"registry existence changed after backup: {target}")
        if _sha256(target) != item.get("pre_hash"):
            raise ValueError(f"registry hash changed after backup: {target}")
        if item["pre_exists"]:
            backup = repo_root / item["backup_path"]
            if _sha256(backup) != item.get("backup_hash") or item.get("backup_hash") != item.get("pre_hash"):
                raise ValueError(f"backup no longer matches pre-state: {backup}")


def restore_from_backup(repo_root: Path, manifest: dict[str, Any]) -> dict[str, str | None]:
    candidates: dict[Path, bytes] = {}
    missing_before: list[Path] = []
    for item in manifest.get("items") or []:
        target = repo_root / item["target_path"]
        if item["pre_exists"]:
            backup = repo_root / item["backup_path"]
            data = backup.read_bytes()
            if hashlib.sha256(data).hexdigest() != item["pre_hash"]:
                raise ValueError(f"cannot restore from invalid backup: {backup}")
            candidates[target] = data
        else:
            missing_before.append(target)
    if candidates:
        registry_io.commit_registry_bytes(candidates)
    for target in missing_before:
        if target.exists():
            target.unlink()
    restored = {item["registry_key"]: _sha256(repo_root / item["target_path"]) for item in manifest.get("items") or []}
    expected = {item["registry_key"]: item.get("pre_hash") for item in manifest.get("items") or []}
    if restored != expected:
        raise RuntimeError(f"rollback hash mismatch: restored={restored} expected={expected}")
    return restored


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(registry_io.dump_yaml_bytes(payload))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare(repo_root: Path, run_dir: Path, dropzone_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    dry_run = promoter.promote_reviewed_inputs(
        repo_root=repo_root,
        workflow_id=WORKFLOW_ID,
        stock_code=STOCK_CODE,
        dropzone_root=dropzone_root,
        output_run_dir=run_dir,
        fixture_mode=False,
        dry_run=True,
    )
    if dry_run["promotion_status"] != "dry_run_ready" or dry_run["validation_status"] != "pass":
        raise RuntimeError(f"promotion dry-run failed: {dry_run['promotion_status']}")
    if dry_run["sample_quality_report_allowed"] or dry_run["p2_allowed"]:
        raise RuntimeError("promotion dry-run violated fixed Bundle 5 boundaries")
    inventory = build_prepromotion_inventory(repo_root, run_dir, dropzone_root, dry_run)
    backup = create_backup_manifest(repo_root, run_dir, inventory)
    write_yaml(run_dir / "R5_bundle5_prepromotion_inventory.yaml", inventory)
    write_yaml(run_dir / "R5_bundle5_registry_backup_manifest.yaml", backup)
    promoter.write_result(run_dir / "R5_bundle5_registry_promotion_dry_run.yaml", dry_run)
    return inventory, backup


def promote_twice(repo_root: Path, run_dir: Path, dropzone_root: Path, backup: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    verify_backup_and_prestate(repo_root, backup)
    try:
        first = promoter.promote_reviewed_inputs(
            repo_root=repo_root,
            workflow_id=WORKFLOW_ID,
            stock_code=STOCK_CODE,
            dropzone_root=dropzone_root,
            output_run_dir=run_dir,
            fixture_mode=False,
            dry_run=False,
        )
        if first["validation_status"] != "pass" or first["promotion_status"] not in {"accepted_inputs_promoted", "accepted_inputs_unchanged"}:
            raise RuntimeError(f"first promotion failed: {first['promotion_status']}")
        if first["sample_quality_report_allowed"] or first["p2_allowed"]:
            raise RuntimeError("first promotion violated fixed Bundle 5 boundaries")
        first_hashes = {key: _sha256(path) for key, path in registry_paths(run_dir).items()}
        second = promoter.promote_reviewed_inputs(
            repo_root=repo_root,
            workflow_id=WORKFLOW_ID,
            stock_code=STOCK_CODE,
            dropzone_root=dropzone_root,
            output_run_dir=run_dir,
            fixture_mode=False,
            dry_run=False,
        )
        second_hashes = {key: _sha256(path) for key, path in registry_paths(run_dir).items()}
        actions = {key: item.get("action") for key, item in second["registry_results"].items()}
        if second["promotion_status"] != "accepted_inputs_unchanged" or second.get("registries_changed"):
            raise RuntimeError(f"second promotion is not idempotent: {second['promotion_status']}")
        if first_hashes != second_hashes or any(action != "unchanged" for action in actions.values()):
            raise RuntimeError("second promotion changed registry bytes or semantics")
    except Exception:
        restore_from_backup(repo_root, backup)
        raise
    promoter.write_result(run_dir / "R5_bundle5_registry_promotion_result.yaml", first)
    idempotency = {
        "artifact_type": "R5_bundle5_registry_idempotency_result",
        "schema_version": "r5_bundle5_registry_idempotency_result_v0.1",
        "status": "pass",
        "first_promotion_status": first["promotion_status"],
        "second_promotion_status": second["promotion_status"],
        "first_hashes": first_hashes,
        "second_hashes": second_hashes,
        "second_actions": actions,
        "byte_level_idempotent": first_hashes == second_hashes,
        "semantic_idempotent": all(action == "unchanged" for action in actions.values()),
        "sample_quality_report_allowed": False,
        "p2_allowed": False,
    }
    write_json(run_dir / "R5_bundle5_registry_idempotency_result.json", idempotency)
    return first, idempotency


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the guarded R5 Bundle 5.5 real registry promotion.")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--workflow-id", default=WORKFLOW_ID)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--promote", action="store_true")
    args = parser.parse_args(argv)
    if args.workflow_id != WORKFLOW_ID:
        raise SystemExit(f"this runner is scoped to {WORKFLOW_ID}")
    if args.prepare_only == args.promote:
        raise SystemExit("choose exactly one of --prepare-only or --promote")
    repo_root = args.repo_root.resolve()
    run_dir = repo_root / "reports/workflow_runs" / WORKFLOW_ID
    dropzone_root = repo_root / "data/reviewed_inputs" / WORKFLOW_ID
    if args.prepare_only:
        inventory, backup = prepare(repo_root, run_dir, dropzone_root)
        print(
            "r5_bundle5_card_5_5_prepare status=pass "
            f"accepted={inventory['accepted_count']} backups={len(backup['items'])} "
            "sample_quality=false p2=false"
        )
        return 0
    backup_path = run_dir / "R5_bundle5_registry_backup_manifest.yaml"
    backup = yaml.safe_load(backup_path.read_text(encoding="utf-8"))
    if not isinstance(backup, dict):
        raise SystemExit("backup manifest is missing or invalid; run --prepare-only first")
    first, idempotency = promote_twice(repo_root, run_dir, dropzone_root, backup)
    print(
        "r5_bundle5_card_5_5_promotion status=pass "
        f"first={first['promotion_status']} second={idempotency['second_promotion_status']} "
        "sample_quality=false p2=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
