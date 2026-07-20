from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import yaml

SOURCE_COMMIT = "758ab7557d9de9eea42a5aeb5df95e3d68c26f0c"
SOURCE_BRANCH = "codex/r5-night03-targeted-backflow-intake"
CI_RUN_ID = 29693876604
SOURCE_ROOT = Path("reports/p1_6/r5_night_shift/r5_overnight_03_20260721")
OUT_ROOT = Path("reports/p1_6/r5_night_shift/r5_overnight_04_20260722")

class AuditError(RuntimeError):
    pass

def run(cmd: list[str], cwd: Path, check: bool = True) -> str:
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if check and p.returncode != 0:
        raise AuditError(f"command failed: {cmd}\nstdout={p.stdout}\nstderr={p.stderr}")
    return p.stdout.strip()

def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def ensure(cond: bool, msg: str):
    if not cond:
        raise AuditError(msg)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--phase", choices=["preflight","receipt","remote"], required=True)
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    out = repo / OUT_ROOT / "preflight"
    out.mkdir(parents=True, exist_ok=True)

    if args.phase == "preflight":
        local = run(["git","rev-parse","HEAD"], repo)
        remote_line = run(["git","ls-remote","--heads","origin",SOURCE_BRANCH], repo)
        remote = remote_line.split()[0] if remote_line else ""
        ensure(remote == SOURCE_COMMIT, f"remote SHA mismatch: {remote}")
        # A seed commit may already exist; source must be an ancestor and exact first parent.
        parent = run(["git","rev-parse","HEAD^"], repo, check=False)
        ensure(local == SOURCE_COMMIT or parent == SOURCE_COMMIT, f"source not exact parent: local={local} parent={parent}")
        payload = {"source_commit": SOURCE_COMMIT, "remote_sha": remote, "local_head": local, "status": "passed"}
        (out / "source_state.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    elif args.phase == "receipt":
        readout_json = repo / SOURCE_ROOT / "morning_readout.json"
        queue_path = repo / SOURCE_ROOT / "next_night_queue.yaml"
        ensure(readout_json.is_file(), f"missing {readout_json}")
        ensure(queue_path.is_file(), f"missing {queue_path}")
        r = load_json(readout_json)
        q = load_yaml(queue_path)
        text = json.dumps(r, ensure_ascii=False).lower()
        ensure("delivered_candidate_ready" in text, "Night03 outcome mismatch")
        ensure("0/63" in text or (r.get("resolved_occurrences") == 0 and r.get("total_occurrences") == 63), "resolution truth mismatch")
        tasks = q.get("tasks") or q.get("items") or []
        ensure(len(tasks) == 69, f"Night04 queue count mismatch: {len(tasks)}")
        payload = {"outcome": "delivered_candidate_ready", "queue_items": len(tasks), "status": "passed"}
        (out / "night03_receipt_audit.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    else:
        remote_line = run(["git","ls-remote","--heads","origin",SOURCE_BRANCH], repo)
        remote = remote_line.split()[0] if remote_line else ""
        ensure(remote == SOURCE_COMMIT, f"remote SHA mismatch: {remote}")
        gh = run(["gh","run","view",str(CI_RUN_ID),"--json","headSha,status,conclusion,url"], repo)
        ci = json.loads(gh)
        ensure(ci.get("headSha") == SOURCE_COMMIT, "CI head SHA mismatch")
        ensure(ci.get("conclusion") == "success", "CI not successful")
        prs = run(["gh","pr","list","--head",SOURCE_BRANCH,"--state","open","--json","number"], repo)
        ensure(len(json.loads(prs)) == 0, "open PR exists")
        payload = {"remote_sha": remote, "ci": ci, "open_prs": 0, "status": "passed"}
        (out / "remote_ci_reconciliation.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
