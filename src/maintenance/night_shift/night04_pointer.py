"""Night04 sandboxed pointer prevalidation.

Every proposal is applied only in a detached child worktree.  The target
branch receives patch and test receipts, never the proposed source change,
unless a later authentic exact-hash approval passes the execution gate.
"""

from __future__ import annotations

import hashlib
import base64
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from .night03 import load_yaml, sha256_file, stable_payload, write_json, write_yaml
from .night03_execution import validate_approved_command
from .night04 import OUTPUT_ROOT, SOURCE_COMMIT


POINTER_SOURCE = Path("reports/p1_6/r5_night_shift/r5_overnight_03_20260721/candidates/pointer_review_index.yaml")
TARGET_SOURCE_PATHS = (
    "scripts/build_r5_bundle16r_case_pack.py",
    "tests/test_r5_bundle16r_case_pack_builder.py",
)
FORBIDDEN_PATHS = (
    "data/raw/**",
    "reports/p1_6/r5_bundle17r/**",
    "reports/p1_6/r5_night_shift/r5_overnight_02_20260720/**",
    "reports/p1_6/r5_night_shift/r5_overnight_03_20260721/**",
    "reports/workflow_runs/**/workflow_state.yaml",
    "config/r5_readout_canonical_index.yaml",
)


class PointerPrevalidationError(RuntimeError):
    """Raised when a pointer dry-run leaves its exact sandbox contract."""


def _run(
    argv: Sequence[str],
    *,
    cwd: Path,
    check: bool = True,
    text: bool = True,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[Any]:
    result = subprocess.run(
        list(argv),
        cwd=cwd,
        capture_output=True,
        text=text,
        check=False,
        env=dict(env) if env is not None else None,
    )
    if check and result.returncode != 0:
        stderr = result.stderr if text else result.stderr.decode(errors="replace")
        stdout = result.stdout if text else result.stdout.decode(errors="replace")
        raise PointerPrevalidationError(f"command failed: {argv}\nstdout={stdout}\nstderr={stderr}")
    return result


def pointer_proposals(repo_root: Path) -> list[dict[str, Any]]:
    payload = load_yaml(repo_root / POINTER_SOURCE)
    proposals = payload.get("proposals")
    if not isinstance(proposals, list) or len(proposals) != 8:
        raise PointerPrevalidationError("Night03 pointer index must contain eight proposals")
    result = sorted((dict(item) for item in proposals), key=lambda item: str(item["occurrence_id"]))
    ids = {str(item["occurrence_id"]) for item in result}
    if len(ids) != 8:
        raise PointerPrevalidationError("pointer occurrence IDs are duplicated")
    return result


def build_path_resolution(repo_root: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for proposal in pointer_proposals(repo_root):
        paths = [str(item).replace("\\", "/") for item in proposal.get("exact_paths") or []]
        valid = (
            paths == list(TARGET_SOURCE_PATHS)
            and all(not PurePosixPath(path).is_absolute() and "*" not in path for path in paths)
            and all((repo_root / path).is_file() for path in paths)
        )
        if not valid:
            raise PointerPrevalidationError(f"unsafe pointer paths: {proposal['occurrence_id']}")
        records.append(
            {
                "occurrence_id": proposal["occurrence_id"],
                "case_id": proposal["case_id"],
                "missing_pointer": proposal["missing_pointer"],
                "proposal_sha256": proposal["source_proposal_sha256"],
                "exact_allowed_paths": paths,
                "forbidden_paths": list(FORBIDDEN_PATHS),
                "diff_ceiling": proposal["diff_ceiling"],
                "passed": True,
            }
        )
    return stable_payload({"schema_version": "r5_night04_pointer_path_resolution_v1", "pointer_count": 8, "records": records})


def build_command_safety(repo_root: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for proposal in pointer_proposals(repo_root):
        commands = proposal.get("acceptance_commands") or []
        hashes = proposal.get("acceptance_command_sha256") or {}
        validated = []
        for command in commands:
            argv = validate_approved_command(str(command), approved_command_sha256=str(hashes.get(str(command)) or ""))
            validated.append({"command": command, "sha256": hashes[command], "argv": argv, "passed": True})
        records.append({"occurrence_id": proposal["occurrence_id"], "commands": validated})
    return stable_payload(
        {
            "schema_version": "r5_night04_pointer_command_safety_v1",
            "pointer_count": len(records),
            "network_allowed": False,
            "mutating_git_allowed": False,
            "records": records,
            "passed": True,
        }
    )


def _replace_once(text: str, old: str, new: str, *, label: str) -> str:
    if text.count(old) != 1:
        raise PointerPrevalidationError(f"{label}: expected one patch anchor, found {text.count(old)}")
    return text.replace(old, new, 1)


def _apply_generation_id_variant(sandbox: Path) -> None:
    script = sandbox / TARGET_SOURCE_PATHS[0]
    text = script.read_text(encoding="utf-8")
    old = '''    generation_lock = {
        "schema_version": 1,
        "artifact_type": "r5_bundle16r_generation_lock",
        "case_id": case_id,
'''
    new = '''    generation_seed = json.dumps(
        {
            "case_id": case_id,
            "input_sha256": sha256_file(input_path),
            "artifact_hashes": pre_lock_hashes,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    generation_id = "bundle16r_case_pack_" + hashlib.sha256(generation_seed).hexdigest()[:16]
    generation_lock = {
        "schema_version": 1,
        "artifact_type": "r5_bundle16r_generation_lock",
        "case_id": case_id,
        "generation_id": generation_id,
'''
    script.write_bytes(_replace_once(text, old, new, label="generation script").encode("utf-8"))

    test = sandbox / TARGET_SOURCE_PATHS[1]
    text = test.read_text(encoding="utf-8")
    old = '''    assert first["human_review_status"] == "pending"


def test_case_builder_rejects_unreconciled_historical_bridge(tmp_path: Path) -> None:
'''
    new = '''    assert first["human_review_status"] == "pending"


def test_generation_lock_exposes_deterministic_generation_id(tmp_path: Path) -> None:
    input_path, registry_path = _fixture(tmp_path)
    kwargs = {
        "repo_root": tmp_path,
        "input_path": input_path,
        "registry_path": registry_path,
        "output_dir": tmp_path / "reports/output",
        "case_results_dir": tmp_path / "bundle16r/generated/case_results",
    }
    result = build_case(**kwargs)
    lock_path = tmp_path / result["output_dir"] / "generation_lock.json"
    first = __import__("json").loads(lock_path.read_text(encoding="utf-8"))["generation_id"]
    build_case(**kwargs)
    second = __import__("json").loads(lock_path.read_text(encoding="utf-8"))["generation_id"]
    assert first == second
    assert first.startswith("bundle16r_case_pack_")


def test_case_builder_rejects_unreconciled_historical_bridge(tmp_path: Path) -> None:
'''
    test.write_bytes(_replace_once(text, old, new, label="generation test").encode("utf-8"))


def _apply_candidate_ready_variant(sandbox: Path) -> None:
    script = sandbox / TARGET_SOURCE_PATHS[0]
    text = script.read_text(encoding="utf-8")
    old = '''        "backflow_tasks": [*declared_backflow, *route_gate_issues(gate_issues)],
        "sample_quality_allowed": False,
'''
    new = '''        "backflow_tasks": [*declared_backflow, *route_gate_issues(gate_issues)],
        "candidate_ready_for_exact_hash_review": not gate_issues,
        "sample_quality_allowed": False,
'''
    script.write_bytes(_replace_once(text, old, new, label="quality script").encode("utf-8"))

    test = sandbox / TARGET_SOURCE_PATHS[1]
    text = test.read_text(encoding="utf-8")
    old = '''    assert all(row["severity"] == "critical" and row["next_step"] for row in routed)
'''
    new = '''    assert all(row["severity"] == "critical" and row["next_step"] for row in routed)


def test_quality_readout_exposes_exact_hash_review_readiness(tmp_path: Path) -> None:
    input_path, registry_path = _fixture(tmp_path)
    result = build_case(
        repo_root=tmp_path,
        input_path=input_path,
        registry_path=registry_path,
        output_dir=tmp_path / "reports/output",
        case_results_dir=tmp_path / "bundle16r/generated/case_results",
    )
    quality_path = tmp_path / result["output_dir"] / "quality_readout.json"
    quality = __import__("json").loads(quality_path.read_text(encoding="utf-8"))
    assert quality["candidate_ready_for_exact_hash_review"] is True
    assert quality["sample_quality_allowed"] is False
    assert quality["p2_allowed"] is False
'''
    test.write_bytes(_replace_once(text, old, new, label="quality test").encode("utf-8"))


def _variant(proposal: Mapping[str, Any]) -> str:
    pointer = str(proposal.get("missing_pointer") or "")
    if pointer == "/generation_id":
        return "generation_id"
    if pointer == "/candidate_ready_for_exact_hash_review":
        return "candidate_ready_for_exact_hash_review"
    raise PointerPrevalidationError(f"unsupported pointer proposal: {pointer}")


def _sandbox_root(repo_root: Path) -> Path:
    return repo_root.parent / f"{repo_root.name}_pointer_sandboxes"


def _ensure_sandbox(repo_root: Path, sandbox: Path, base_commit: str) -> None:
    if sandbox.exists():
        head = _run(["git", "rev-parse", "HEAD"], cwd=sandbox).stdout.strip()
        if head != base_commit:
            raise PointerPrevalidationError(f"existing sandbox head mismatch: {sandbox}")
        return
    sandbox.parent.mkdir(parents=True, exist_ok=True)
    _run(["git", "worktree", "add", "--detach", str(sandbox), base_commit], cwd=repo_root)


def _apply_variant(sandbox: Path, variant: str) -> None:
    if variant == "generation_id":
        _apply_generation_id_variant(sandbox)
    else:
        _apply_candidate_ready_variant(sandbox)


def run_pointer_sandboxes(repo_root: Path) -> dict[str, Any]:
    base_commit = _run(["git", "rev-parse", "HEAD"], cwd=repo_root).stdout.strip()
    sandbox_root = _sandbox_root(repo_root)
    patch_root = repo_root / OUTPUT_ROOT / "pointer_prevalidation/patches"
    records: list[dict[str, Any]] = []
    test_receipts: list[dict[str, Any]] = []
    rollback: list[dict[str, Any]] = []
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    for proposal in pointer_proposals(repo_root):
        occurrence_id = str(proposal["occurrence_id"])
        sandbox = sandbox_root / occurrence_id.rsplit("_", 1)[-1]
        _ensure_sandbox(repo_root, sandbox, base_commit)
        variant = _variant(proposal)
        status_before = _run(["git", "status", "--porcelain"], cwd=sandbox).stdout.strip()
        if status_before:
            existing_changed = _run(["git", "diff", "--name-only"], cwd=sandbox).stdout.splitlines()
            marker = "bundle16r_case_pack_" if variant == "generation_id" else "candidate_ready_for_exact_hash_review"
            if set(existing_changed) != set(TARGET_SOURCE_PATHS) or marker not in (sandbox / TARGET_SOURCE_PATHS[0]).read_text(encoding="utf-8"):
                raise PointerPrevalidationError(f"existing sandbox does not match resumable dry-run: {sandbox}")
        else:
            _apply_variant(sandbox, variant)
        _run(["git", "diff", "--check"], cwd=sandbox)
        changed = _run(["git", "diff", "--name-only", "--", *TARGET_SOURCE_PATHS], cwd=sandbox).stdout.splitlines()
        changed = [item.replace("\\", "/") for item in changed if item]
        ceiling = int((proposal.get("diff_ceiling") or {}).get("max_changed_paths") or 0)
        if not changed or set(changed) - set(TARGET_SOURCE_PATHS) or len(changed) > ceiling:
            raise PointerPrevalidationError(f"pointer diff ceiling failed: {occurrence_id} {changed}")
        patch_bytes = _run(
            ["git", "diff", "--binary", "--", *TARGET_SOURCE_PATHS],
            cwd=sandbox,
            text=False,
        ).stdout
        preview_bytes = _run(
            ["git", "diff", "--binary", "--unified=0", "--", *TARGET_SOURCE_PATHS],
            cwd=sandbox,
            text=False,
        ).stdout
        preview_path = patch_root / f"{occurrence_id}.patch"
        patch_path = patch_root / f"{occurrence_id}.patch.b64"
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.write_bytes(preview_bytes)
        encoded_patch = base64.b64encode(patch_bytes) + b"\n"
        patch_path.write_bytes(encoded_patch)
        command = str((proposal.get("acceptance_commands") or [""])[0])
        result = _run(
            [sys.executable, "-m", "pytest", "-q", "tests/test_r5_bundle16r_case_pack_builder.py"],
            cwd=sandbox,
            check=False,
            env=environment,
        )
        passed_match = re.search(r"(\d+) passed", result.stdout)
        if result.returncode != 0 or passed_match is None:
            raise PointerPrevalidationError(f"pointer targeted test failed: {occurrence_id}\n{result.stdout}\n{result.stderr}")
        reverse = subprocess.run(
            ["git", "apply", "--reverse", "--check", "-"],
            cwd=sandbox,
            input=patch_bytes,
            capture_output=True,
            check=False,
        )
        if reverse.returncode != 0:
            raise PointerPrevalidationError(f"pointer rollback check failed: {occurrence_id}")
        patch_sha = hashlib.sha256(patch_bytes).hexdigest()
        records.append(
            {
                "occurrence_id": occurrence_id,
                "case_id": proposal["case_id"],
                "missing_pointer": proposal["missing_pointer"],
                "variant": variant,
                "proposal_sha256": proposal["source_proposal_sha256"],
                "candidate_packet_sha256": proposal["packet_sha256"],
                "base_commit": base_commit,
                "sandbox_path": sandbox.as_posix(),
                "sandbox_mode": "detached_child_worktree",
                "patch_path": patch_path.relative_to(repo_root).as_posix(),
                "patch_encoding": "base64",
                "patch_sha256": patch_sha,
                "encoded_patch_sha256": hashlib.sha256(encoded_patch).hexdigest(),
                "forward_preview_path": preview_path.relative_to(repo_root).as_posix(),
                "forward_preview_sha256": hashlib.sha256(preview_bytes).hexdigest(),
                "changed_paths": changed,
                "changed_path_count": len(changed),
                "diff_ceiling": ceiling,
                "target_branch_applied": False,
            }
        )
        test_receipts.append(
            {
                "occurrence_id": occurrence_id,
                "command": command,
                "command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
                "exit_code": result.returncode,
                "passed_tests": int(passed_match.group(1)),
                "terminal_status": "passed",
                "sandbox_patch_sha256": patch_sha,
            }
        )
        rollback.append(
            {
                "occurrence_id": occurrence_id,
                "strategy": "git_apply_reverse_exact_patch",
                "reverse_check_passed": True,
                "patch_sha256": patch_sha,
            }
        )
    return {"base_commit": base_commit, "sandbox_root": sandbox_root, "records": records, "tests": test_receipts, "rollback": rollback}


def build_conflict_matrix(repo_root: Path, records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_id = {str(item["occurrence_id"]): item for item in records}
    pairs: list[dict[str, Any]] = []
    ids = sorted(by_id)
    for index, left_id in enumerate(ids):
        left = by_id[left_id]
        left_sandbox = Path(str(left["sandbox_path"]))
        for right_id in ids[index + 1 :]:
            right = by_id[right_id]
            right_patch = repo_root / str(right["patch_path"])
            raw_patch = base64.b64decode(right_patch.read_bytes().strip(), validate=True)
            combine = subprocess.run(
                ["git", "apply", "--check", "-"],
                cwd=left_sandbox,
                input=raw_patch,
                capture_output=True,
                check=False,
            )
            same_patch = left["patch_sha256"] == right["patch_sha256"]
            if same_patch:
                conflict_type = "duplicate_semantic_change"
            elif combine.returncode == 0:
                conflict_type = "shared_files_non_overlapping_hunks"
            else:
                conflict_type = "overlapping_patch_conflict"
            pairs.append(
                {
                    "left": left_id,
                    "right": right_id,
                    "shared_paths": sorted(set(left["changed_paths"]) & set(right["changed_paths"])),
                    "same_patch": same_patch,
                    "combined_apply_check_passed": combine.returncode == 0,
                    "conflict_type": conflict_type,
                }
            )
    return stable_payload({"schema_version": "r5_night04_pointer_conflict_matrix_v1", "pair_count": len(pairs), "pairs": pairs})


def build_batch_simulation(records: Sequence[Mapping[str, Any]], conflicts: Mapping[str, Any]) -> dict[str, Any]:
    compatible = {
        frozenset((str(item["left"]), str(item["right"])))
        for item in conflicts["pairs"]
        if item["combined_apply_check_passed"] and not item["same_patch"]
    }
    pending = [str(item["occurrence_id"]) for item in records]
    batches: list[list[str]] = []
    while pending:
        first = pending.pop(0)
        partner = next((item for item in pending if frozenset((first, item)) in compatible), None)
        batch = [first]
        if partner is not None:
            pending.remove(partner)
            batch.append(partner)
        batches.append(batch)
    return stable_payload(
        {
            "schema_version": "r5_night04_pointer_batch_simulation_v1",
            "pointer_count": len(records),
            "batch_count": len(batches),
            "max_batch_size": max(map(len, batches)),
            "batches": [{"batch_id": index, "occurrence_ids": items, "execution_performed": False} for index, items in enumerate(batches, start=1)],
            "simulation_only": True,
        }
    )


def materialize_phase_d(repo_root: Path) -> dict[str, Any]:
    root = repo_root / OUTPUT_ROOT / "pointer_prevalidation"
    paths = build_path_resolution(repo_root)
    commands = build_command_safety(repo_root)
    sandbox = run_pointer_sandboxes(repo_root)
    conflicts = build_conflict_matrix(repo_root, sandbox["records"])
    batches = build_batch_simulation(sandbox["records"], conflicts)
    write_yaml(root / "path_resolution.yaml", paths)
    write_yaml(root / "command_safety.yaml", commands)
    write_yaml(
        root / "sandbox_manager_contract.yaml",
        {
            "schema_version": "r5_night04_pointer_sandbox_manager_v1",
            "base_commit": sandbox["base_commit"],
            "sandbox_root": sandbox["sandbox_root"].as_posix(),
            "sandbox_count": 8,
            "mode": "detached_child_worktrees",
            "target_branch_mutation_without_approval": False,
            "sandboxes": [{"occurrence_id": item["occurrence_id"], "path": item["sandbox_path"]} for item in sandbox["records"]],
        },
    )
    patch_index = stable_payload(
        {
            "schema_version": "r5_night04_pointer_dry_run_patch_index_v1",
            "pointer_count": 8,
            "dry_run_only": True,
            "patches": sandbox["records"],
        }
    )
    write_yaml(root / "dry_run_patch_index.yaml", patch_index)
    write_json(
        root / "diff_ceiling_receipt.json",
        stable_payload(
            {
                "schema_version": "r5_night04_pointer_diff_ceiling_receipt_v1",
                "pointer_count": 8,
                "all_passed": all(item["changed_path_count"] <= item["diff_ceiling"] for item in sandbox["records"]),
                "records": [{key: item[key] for key in ("occurrence_id", "changed_paths", "changed_path_count", "diff_ceiling")} for item in sandbox["records"]],
            }
        ),
    )
    write_json(root / "targeted_test_receipts.json", stable_payload({"schema_version": "r5_night04_pointer_targeted_tests_v1", "pointer_count": 8, "all_passed": True, "receipts": sandbox["tests"]}))
    write_yaml(root / "batch_simulation.yaml", batches)
    write_yaml(root / "conflict_matrix.yaml", conflicts)
    write_json(root / "rollback_receipt.json", stable_payload({"schema_version": "r5_night04_pointer_rollback_v1", "pointer_count": 8, "all_reverse_checks_passed": True, "records": sandbox["rollback"]}))
    previews = [
        {
            "occurrence_id": item["occurrence_id"],
            "proposal_sha256": item["proposal_sha256"],
            "sandbox_patch_sha256": item["patch_sha256"],
            "base_commit": item["base_commit"],
            "preview_generation_id": "night04_pointer_preview_" + hashlib.sha256(f"{item['proposal_sha256']}:{item['patch_sha256']}:{item['base_commit']}".encode()).hexdigest()[:16],
            "resolution_receipt_emitted": False,
        }
        for item in sandbox["records"]
    ]
    write_yaml(root / "generation_lock_previews.yaml", stable_payload({"schema_version": "r5_night04_pointer_generation_lock_previews_v1", "preview_count": 8, "previews": previews}))
    write_yaml(
        root / "conditional_execution_contract.yaml",
        {
            "schema_version": "r5_night04_pointer_conditional_execution_v1",
            "required_gates": [
                "authentic_external_exact_hash_approval",
                "candidate_and_review_packet_hashes_current",
                "clean_scoped_sandbox",
                "targeted_tests_pass",
                "conflict_recheck_pass",
            ],
            "external_approvals_present": 0,
            "target_branch_executions": 0,
            "dry_run_is_resolution": False,
        },
    )
    historical = _run(
        [
            "git",
            "diff",
            "--name-only",
            SOURCE_COMMIT,
            "--",
            "reports/p1_6/r5_bundle17r",
            "reports/p1_6/r5_night_shift/r5_overnight_02_20260720",
            "reports/p1_6/r5_night_shift/r5_overnight_03_20260721",
        ],
        cwd=repo_root,
    ).stdout.splitlines()
    target_changes = _run(["git", "diff", "--name-only", "HEAD", "--", *TARGET_SOURCE_PATHS], cwd=repo_root).stdout.splitlines()
    truth = stable_payload(
        {
            "schema_version": "r5_night04_pointer_dry_run_truth_v1",
            "pointer_dry_runs": 8,
            "target_branch_pointer_changes": target_changes,
            "historical_path_changes": historical,
            "external_approvals_consumed": 0,
            "resolution_receipts_emitted": 0,
            "resolved_delta": 0,
            "passed": not target_changes and not historical,
        }
    )
    if not truth["passed"]:
        raise PointerPrevalidationError(f"dry-run mutated target or history: {truth}")
    write_json(root / "dry_run_truth_receipt.json", truth)
    return {"patch_index": patch_index, "tests": sandbox["tests"], "truth": truth}
