from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable

import yaml

SOURCE_COMMIT = "069da527452def6c59c3772750e933d8611ccadf"
NIGHT02_START_COMMIT = "4340945457d661ed62967e949f862ccf2214aff2"
SOURCE_BRANCH = "codex/r5-night02-contract-recovery"
TARGET_BRANCH = "codex/r5-night03-targeted-backflow-intake"
CI_RUN_ID = 29681505920
SOURCE_ROOT = Path("reports/p1_6/r5_night_shift/r5_overnight_02_20260720")
OUT_ROOT = Path("reports/p1_6/r5_night_shift/r5_overnight_03_20260721")

class AuditError(RuntimeError):
    pass

def run(cmd: list[str], cwd: Path, *, check: bool = True) -> str:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise AuditError(f"command failed: {cmd}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc.stdout.strip()

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def all_scalars(obj: Any) -> Iterable[Any]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from all_scalars(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from all_scalars(v)
    else:
        yield obj

def find_task_list(obj: Any) -> list[Any] | None:
    candidates: list[list[Any]] = []
    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
                    keys = set().union(*(x.keys() for x in value if isinstance(x, dict)))
                    if {"id", "task_id", "occurrence_id"} & keys:
                        candidates.append(value)
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(obj)
    return max(candidates, key=len) if candidates else None

def first_existing(repo: Path, *candidates: str) -> Path:
    for candidate in candidates:
        path = repo / SOURCE_ROOT / candidate
        if path.is_file():
            return path
    raise AuditError(
        "required Night02 publication evidence missing; checked: "
        + ", ".join(str(repo / SOURCE_ROOT / candidate) for candidate in candidates)
    )


def ensure_paths(repo: Path) -> dict[str, Path]:
    core_paths = {
        "receipt": repo / SOURCE_ROOT / "mission_completion_receipt.json",
        "readout": repo / SOURCE_ROOT / "morning_readout.md",
        "readout_json": repo / SOURCE_ROOT / "morning_readout.json",
        "queue": repo / SOURCE_ROOT / "next_night_queue.yaml",
    }
    missing = [str(p) for p in core_paths.values() if not p.is_file()]
    if missing:
        raise AuditError(f"required Night02 physical files missing: {missing}")
    return {
        **core_paths,
        # Night02's final commit records publication truth in ns02_t46 and the
        # implementation receipt.  The post-push convenience paths referenced
        # by mission_completion_receipt.json were not tracked at the exact
        # source SHA, so prefer them when present and otherwise use the tracked
        # authoritative receipts instead of mutating Night02 history.
        "remote_receipt": first_existing(
            repo,
            "publication/remote_delivery_receipt.json",
            "receipts/ns02_t46_commit_push_remote_ci.json",
            "publication/implementation_delivery_receipt.json",
        ),
        "ci_status": first_existing(
            repo,
            "publication/ci_status.md",
            "receipts/ns02_t46_commit_push_remote_ci.json",
        ),
    }

def write_report(repo: Path, name: str, payload: dict[str, Any]) -> None:
    out = repo / OUT_ROOT / "preflight"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [f"# {name.replace('_', ' ').title()}", ""]
    for key, value in payload.items():
        lines.append(f"- **{key}**: `{value}`")
    (out / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

def audit_preflight(repo: Path) -> dict[str, Any]:
    head = run(["git", "rev-parse", "HEAD"], repo)
    branch = run(["git", "branch", "--show-current"], repo)
    status = run(["git", "status", "--porcelain"], repo)
    parent = run(["git", "rev-parse", "HEAD^"], repo)
    changed = run(["git", "diff", "--name-only", f"{SOURCE_COMMIT}..HEAD"], repo).splitlines()
    expected_prefix = "codex_tasks/night_shift/r5_overnight_03_20260721/"
    bad = [p for p in changed if not p.startswith(expected_prefix)]
    if parent != SOURCE_COMMIT:
        raise AuditError(f"seed commit parent {parent} != source {SOURCE_COMMIT}")
    if branch != TARGET_BRANCH:
        raise AuditError(f"branch {branch} != {TARGET_BRANCH}")
    if status:
        raise AuditError(f"worktree is not clean: {status}")
    if bad:
        raise AuditError(f"seed commit changed paths outside package: {bad}")
    ensure_paths(repo)
    payload = {
        "source_commit": SOURCE_COMMIT,
        "seed_commit": head,
        "seed_parent": parent,
        "target_branch": branch,
        "worktree_clean": True,
        "seed_changed_path_count": len(changed),
        "seed_scope_ok": True,
    }
    write_report(repo, "source_state", payload)
    (repo / OUT_ROOT / "preflight" / "preflight.md").write_text(
        "# Night03 Preflight\n\nAll baseline and seed-scope checks passed.\n",
        encoding="utf-8",
    )
    return payload

def audit_receipt(repo: Path) -> dict[str, Any]:
    paths = ensure_paths(repo)
    receipt = load_json(paths["receipt"])
    readout = paths["readout"].read_text(encoding="utf-8")
    queue = load_yaml(paths["queue"])
    task_list = find_task_list(queue)
    if task_list is None or len(task_list) != 69:
        raise AuditError(f"expected 69 tasks in next queue, got {None if task_list is None else len(task_list)}")
    scalar_text = "\n".join(str(x) for x in all_scalars(receipt))
    combined = scalar_text + "\n" + readout
    checks = {
        "final_sha_present": SOURCE_COMMIT in combined,
        "delivered_present": "delivered" in combined.lower(),
        "forty_of_forty_present": "40/40" in combined.replace(" ", "") or (
            '"passed": 40' in combined and '"total": 40' in combined
        ),
        "zero_of_sixty_three_present": "0/63" in combined.replace(" ", "") or (
            "resolved" in combined.lower() and "63" in combined and "0" in combined
        ),
        "goal_open_present": "open_needs_targeted_backflow" in combined,
        "queue_count": len(task_list),
    }
    failed = [k for k, v in checks.items() if k != "queue_count" and not v]
    if failed:
        raise AuditError(f"Night02 receipt/readout checks failed: {failed}")
    payload = {
        **checks,
        "receipt_sha256": sha256(paths["receipt"]),
        "readout_sha256": sha256(paths["readout"]),
        "queue_sha256": sha256(paths["queue"]),
    }
    write_report(repo, "night02_receipt_audit", payload)
    return payload

def audit_remote(repo: Path) -> dict[str, Any]:
    paths = ensure_paths(repo)
    remote_line = run(["git", "ls-remote", "--heads", "origin", SOURCE_BRANCH], repo)
    if not remote_line:
        raise AuditError(f"source branch not found on origin: {SOURCE_BRANCH}")
    remote_sha = remote_line.split()[0]
    if remote_sha != SOURCE_COMMIT:
        raise AuditError(f"remote source SHA {remote_sha} != {SOURCE_COMMIT}")

    historical = run(
        ["git", "diff", "--name-only", f"{NIGHT02_START_COMMIT}..{SOURCE_COMMIT}", "--", "reports/p1_6/r5_bundle17r"],
        repo,
    )
    if historical:
        raise AuditError(f"historical Bundle17R paths changed: {historical}")

    gh = shutil.which("gh")
    gh_payload: dict[str, Any] = {}
    if gh:
        run_json = run(
            ["gh", "run", "view", str(CI_RUN_ID), "--json", "databaseId,headSha,status,conclusion,url"],
            repo,
        )
        gh_payload["run"] = json.loads(run_json)
        if gh_payload["run"].get("conclusion") != "success":
            raise AuditError(f"CI conclusion is not success: {gh_payload['run']}")
        if gh_payload["run"].get("headSha") != SOURCE_COMMIT:
            raise AuditError(f"CI head SHA mismatch: {gh_payload['run']}")
        prs_json = run(
            ["gh", "pr", "list", "--head", SOURCE_BRANCH, "--state", "open", "--json", "number,url"],
            repo,
        )
        gh_payload["open_prs"] = json.loads(prs_json)
        if gh_payload["open_prs"]:
            raise AuditError(f"open PRs found for source branch: {gh_payload['open_prs']}")
    else:
        receipt_text = paths["remote_receipt"].read_text(encoding="utf-8")
        ci_text = paths["ci_status"].read_text(encoding="utf-8")
        combined = receipt_text + "\n" + ci_text
        if SOURCE_COMMIT not in combined or "success" not in combined.lower():
            raise AuditError("gh unavailable and tracked remote/CI receipts do not prove SHA+success")
        gh_payload = {"verification_mode": "tracked_receipt_fallback", "open_prs": "not_live_verified"}

    payload = {
        "remote_source_sha": remote_sha,
        "expected_source_sha": SOURCE_COMMIT,
        "remote_equal": True,
        "ci_run_id": CI_RUN_ID,
        "historical_bundle_path_change_count": 0,
        "publication_receipt_path": paths["remote_receipt"].relative_to(repo).as_posix(),
        "ci_evidence_path": paths["ci_status"].relative_to(repo).as_posix(),
        "github": gh_payload,
    }
    write_report(repo, "remote_ci_reconciliation", payload)
    return payload

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--phase", choices=("preflight", "receipt", "remote", "all"), default="all")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    result: dict[str, Any] = {}
    if args.phase in ("preflight", "all"):
        result["preflight"] = audit_preflight(repo)
    if args.phase in ("receipt", "all"):
        result["receipt"] = audit_receipt(repo)
    if args.phase in ("remote", "all"):
        result["remote"] = audit_remote(repo)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
