from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "PACKAGE_MANIFEST.yaml"
QUEUE = ROOT / "task_queue.yaml"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")

manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
for item in manifest["payload_files"]:
    p = ROOT / item["path"]
    if not p.is_file():
        fail(f"missing {item['path']}")
    actual = sha256(p)
    if actual != item["sha256"]:
        fail(f"digest mismatch {item['path']}: {actual}")

queue = yaml.safe_load(QUEUE.read_text(encoding="utf-8"))
if queue["baseline"]["source_commit"] != "4340945457d661ed62967e949f862ccf2214aff2":
    fail("wrong source SHA")
if queue["baseline"]["target_branch"] != "codex/r5-night02-contract-recovery":
    fail("wrong target branch")
if queue["long_term_goal"]["close_allowed"] is not False:
    fail("long-term Goal close must be false")
if queue["mission_policy"]["no_safe_pilot_is_success"] is not False:
    fail("no_safe_pilot must not be success")
if queue["mission_policy"].get("continue_claiming_after_delivery_until_cutoff_if_ready") is not True:
    fail("runner must continue with ready strategic tasks after delivery-required work")
if queue["mission_policy"].get("stop_early_only_when_all_tasks_complete_and_next_queue_ready") is not True:
    fail("early stop policy is not strict enough")

tasks = queue["tasks"]
if len(tasks) < 36:
    fail(f"expected a substantial queue, got {len(tasks)} tasks")
ids = [t["id"] for t in tasks]
if len(ids) != len(set(ids)):
    fail("duplicate task IDs")
idset = set(ids)
for t in tasks:
    if not t.get("allowed_paths"):
        fail(f"{t['id']} has empty allowed_paths")
    if not t.get("acceptance_commands"):
        fail(f"{t['id']} has empty acceptance_commands")
    if t.get("status") != "pending":
        fail(f"{t['id']} must start pending")
    for dep in t.get("depends_on", []):
        if dep not in idset:
            fail(f"{t['id']} references missing dependency {dep}")

state = {}
by_id = {t["id"]: t for t in tasks}
def visit(node: str) -> None:
    if state.get(node) == 1:
        fail(f"cycle at {node}")
    if state.get(node) == 2:
        return
    state[node] = 1
    for dep in by_id[node].get("depends_on", []):
        visit(dep)
    state[node] = 2
for tid in ids:
    visit(tid)

ready_after_preflight = [
    t["id"] for t in tasks
    if t.get("depends_on") == ["ns02_t00_exact_baseline_preflight"]
]
if len(ready_after_preflight) < 6:
    fail(f"only {len(ready_after_preflight)} tasks unlock directly after preflight")

print(f"PASS: {len(tasks)} tasks; {len(manifest['payload_files'])} payload files; package digest {manifest['payload_digest_sha256']}")
