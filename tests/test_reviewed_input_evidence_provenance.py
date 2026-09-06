"""Keep retained reviewed-input provenance independent of historical generators."""
from __future__ import annotations

import csv
import hashlib
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
REVIEWED_ROOT = ROOT / "data/reviewed_inputs"


def test_retained_evidence_manifest_has_unique_ids_and_physical_files() -> None:
    with (ROOT / "data/manifests/evidence_manifest.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    ids = [row["evidence_id"] for row in rows]
    assert all(ids) and len(ids) == len(set(ids))
    for row in rows:
        assert row["raw_file_path"], row["evidence_id"]
        for field in ("raw_file_path", "processed_text_path", "processed_table_path", "page_map_path"):
            value = row.get(field)
            if not value:
                continue
            target = (ROOT / value).resolve()
            assert target.is_relative_to(ROOT / "data"), (row["evidence_id"], field)
            assert target.is_file(), (row["evidence_id"], field, value)


def test_committed_accepted_inputs_have_reviewed_physical_evidence() -> None:
    tracked = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-z", "--", "data/reviewed_inputs"],
    ).decode("utf-8").split("\0")
    paths = [ROOT / value for value in tracked if value.endswith((".yaml", ".yml"))]
    assert paths, "the retained reviewed-input evidence set must not disappear"
    with (ROOT / "data/manifests/evidence_manifest.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        evidence = {row["evidence_id"]: row for row in csv.DictReader(handle)}

    seen: set[tuple[str, str]] = set()
    raw_hashes: dict[Path, str] = {}
    for path in paths:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict) and isinstance(data.get("records"), list), path
        workflow_id = path.relative_to(REVIEWED_ROOT).parts[0]
        for row in data["records"]:
            if row.get("review_status") != "accepted":
                continue
            assert row["workflow_id"] == workflow_id, path
            identity = (workflow_id, row["input_id"])
            assert identity not in seen, identity
            seen.add(identity)
            assert row.get("reviewer") and row.get("reviewed_at"), identity
            assert row.get("stock_code") and row.get("source_rank") in {"A", "B"}, identity

            evidence_id = row["source_evidence_id"]
            source = evidence[evidence_id]
            assert source["review_status"] == "reviewed", evidence_id
            assert source["raw_file_path"], evidence_id
            raw_path = (ROOT / source["raw_file_path"]).resolve()
            assert raw_path.is_relative_to(ROOT / "data/raw"), evidence_id
            assert raw_path.is_file(), raw_path
            if raw_path not in raw_hashes:
                payload = raw_path.read_bytes()
                digest = hashlib.sha256(payload).hexdigest()
                if digest != source["file_hash"] and raw_path.suffix.lower() in {
                    ".json", ".csv", ".yaml", ".yml", ".txt", ".md"
                }:
                    # Windows checkouts may expand LF without changing the archived evidence.
                    relative = raw_path.relative_to(ROOT).as_posix()
                    archived = subprocess.check_output(
                        ["git", "-C", str(ROOT), "show", f"HEAD:{relative}"],
                    )
                    assert payload.replace(b"\r\n", b"\n") == archived, raw_path
                    digest = hashlib.sha256(archived).hexdigest()
                raw_hashes[raw_path] = digest
            assert raw_hashes[raw_path] == source["file_hash"], evidence_id
            source_identity = f"{evidence_id} {source['raw_file_path']}".lower()
            assert not any(word in source_identity for word in ("fixture", "sample_report", "template"))

    assert seen, "at least one accepted reviewed input must remain covered"
