from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import yaml

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    manifest = yaml.safe_load((root / "PACKAGE_MANIFEST.yaml").read_text(encoding="utf-8"))
    queue = yaml.safe_load((root / "task_queue.yaml").read_text(encoding="utf-8"))
    assert manifest["package_id"] == "R5_Overnight_Mission_04_20260721"
    assert manifest["mission_id"] == "r5_overnight_04_20260722"
    assert queue["baseline"]["source_commit"] == "758ab7557d9de9eea42a5aeb5df95e3d68c26f0c"
    assert len(queue["tasks"]) == 60
    ids = [t["id"] for t in queue["tasks"]]
    assert len(ids) == len(set(ids))
    known = set(ids)
    for task in queue["tasks"]:
        assert set(task.get("depends_on", [])) <= known
        assert task.get("acceptance_commands")
        assert task.get("required_artifacts")
    assert queue["program_goal"]["truth_at_start"]["candidate_ready"] == 43
    assert queue["program_goal"]["truth_at_start"]["dependency_blocked"] == 20
    assert queue["program_goal"]["truth_at_start"]["parent_pending"] == 6
    assert queue["program_goal"]["truth_at_start"]["blocker_occurrences_resolved"] == 0
    for rec in manifest["files"]:
        p = root / rec["path"]
        assert p.is_file(), p
        assert p.stat().st_size == rec["bytes"], p
        assert sha256(p) == rec["sha256"], p
    print(f"valid: {manifest['package_id']} files={len(manifest['files'])} tasks={len(queue['tasks'])}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
