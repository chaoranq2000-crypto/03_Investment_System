from __future__ import annotations

import csv
import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_r5_v1_replay_002837.py"
VALIDATOR = (
    ROOT
    / ".agents"
    / "skills"
    / "research-orchestrator"
    / "scripts"
    / "validate_workflow_state.py"
)
SOURCE_RUN = (
    ROOT
    / "reports"
    / "workflow_runs"
    / "wf_20260703_stock_first_002837_invic"
)
CANONICAL_REPLAY = (
    ROOT
    / "reports"
    / "workflow_runs"
    / "wf_20260723_stock_first_002837_v1_replay"
)

SIX_PIECES = {
    "workflow_state.yaml",
    "run_log.md",
    "artifact_manifest.csv",
    "open_todos.csv",
    "quality_gate_report.md",
    "workflow_readout.md",
}
SINGLETON_CONTROLS = {
    "workflow_state.yaml",
    "open_todos.csv",
    "quality_gate_report.md",
    "workflow_readout.md",
}


def load_runner():
    spec = importlib.util.spec_from_file_location("run_r5_v1_replay_002837", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_for_scope(path: Path, scope: str) -> str:
    if scope == "file_bytes":
        return sha256_file(path)
    if scope == "canonical_lf_text_bytes":
        payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        return hashlib.sha256(payload).hexdigest()
    raise AssertionError(f"unexpected hash scope: {scope!r}")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture(scope="module")
def built_replay(tmp_path_factory: pytest.TempPathFactory):
    runner = load_runner()
    output = tmp_path_factory.mktemp("r5_v1_replay") / "run"
    result = runner.materialize_replay(ROOT, SOURCE_RUN, output)
    return runner, output, result


def test_replay_has_canonical_six_piece_control_plane(built_replay) -> None:
    runner, output, result = built_replay
    assert SIX_PIECES.issubset({path.name for path in output.iterdir() if path.is_file()})
    state = yaml.safe_load((output / "workflow_state.yaml").read_text(encoding="utf-8"))
    assert state["workflow_id"] == runner.TARGET_WORKFLOW_ID
    assert state["source_workflow_id"] == runner.SOURCE_WORKFLOW_ID
    assert state["state_schema_version"] == "r5_v1"
    assert state["run_mode"] == "normal"
    assert state["workflow_type"] == "stock_first_closed_loop"
    assert state["status"] == "needs_fix"
    assert state["current_stage"] == "T10"
    assert state["next_stage"] == "T1"
    assert state["required_next_skill"] == "evidence-ingest"
    assert state["completed_stages"] == [f"T{index}" for index in range(11)]
    gates = {row["gate_id"]: row["status"] for row in state["quality_gates"]}
    assert set(gates) == {f"G{index}" for index in range(11)}
    assert gates["G3"] == "fail"
    assert gates["G6"] == "fail"
    assert gates["G5"] == "not_applicable"
    assert gates["G9"] == "pass"
    assert gates["G10"] == "pass"
    assert result["semantic_drift_count"] == 0

    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    completed = subprocess.run(
        [sys.executable, "-B", str(VALIDATOR), str(output / "workflow_state.yaml")],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr
    assert "OK" in completed.stdout


def test_replay_uses_real_hash_bound_read_only_sources(built_replay) -> None:
    runner, output, _ = built_replay
    _, rows = read_csv(output / "inputs/input_provenance.csv")
    evidence_rows = [row for row in rows if row["evidence_id"]]
    assert {row["evidence_id"] for row in evidence_rows} == set(runner.SELECTED_EVIDENCE_IDS)
    assert sum(row["source_group"] == "official_disclosure" for row in evidence_rows) == 2
    assert sum(row["source_group"] == "structured_database" for row in evidence_rows) == 2
    for row in rows:
        source_text = f"{row['source_path']}\n{row['processed_path']}".lower()
        assert "fixture" not in source_text
        source = ROOT / row["source_path"]
        assert source.is_file()
        assert row["source_hash_scope"] == "file_bytes"
        assert (
            sha256_for_scope(source, row["source_hash_scope"])
            == row["expected_sha256"]
            == row["observed_sha256"]
        )
        if row["processed_path"]:
            processed = ROOT / row["processed_path"]
            assert processed.is_file()
            assert (
                sha256_for_scope(processed, row["processed_hash_scope"])
                == row["processed_sha256"]
            )
        else:
            assert row["processed_hash_scope"] == ""
            assert row["processed_sha256"] == ""

    processed_by_evidence = {row["evidence_id"]: row for row in evidence_rows}
    annual = processed_by_evidence["ev_annual_report_002837_20260421_2cbfc5"]
    quarterly = processed_by_evidence["ev_quarterly_report_002837_20260421_2f00c7"]
    assert annual["processed_hash_scope"] == "canonical_lf_text_bytes"
    assert annual["processed_sha256"] == (
        "503b62a47363ca5c985a22980e4eb36fe883821db92d1d9febe0fffb74224876"
    )
    assert quarterly["processed_hash_scope"] == "canonical_lf_text_bytes"
    assert quarterly["processed_sha256"] == (
        "884beb31af91df96dddf8383b157dcde95a3b348272d5f8883ed3f14c6a62f53"
    )
    structured_scopes = {
        row["processed_hash_scope"]
        for row in evidence_rows
        if row["source_group"] == "structured_database"
    }
    assert structured_scopes == {"file_bytes"}

    expected_start = {
        "R5_bundle13r_close_readout.md": "b62e64cafcd93bf164c4f4ff76adde1f0d107510a0e39807411d082515f92e5c",
        "R5_bundle13r_verification_summary.yaml": "4cfe4b07c12da3f108f164ca504018a825f33a4331cbbb2ebfa93cb29348b1c0",
        "R5_bundle13r_quality_report.md": "6b3c41dc521c916faf599439e94a261613fc6782b9de69698755a913ca169831",
        "R5_bundle13r_quality_issues.csv": "fa6f98f2a3ecc6363d6a7d7e458cae2892118b5081af8374cdd0174ebe795f57",
    }
    by_name = {Path(row["source_path"]).name: row for row in rows}
    for name, digest in expected_start.items():
        assert by_name[name]["observed_sha256"] == digest

    pack = yaml.safe_load((output / "research/stock_research_pack.yaml").read_text(encoding="utf-8"))
    assert pack["replay_mode"] == {
        "offline": True,
        "live_network_used": False,
        "synthetic_inputs_used": False,
        "historical_writes_allowed": False,
    }
    assert pack["metric_boundary"]["promoted_metric_count"] == 0
    assert pack["metric_boundary"]["review_status"] == "draft"
    assert pack["bundle13r_replay"]["archived_result_match"] is True


def test_processed_text_hash_is_stable_across_line_endings(tmp_path: Path) -> None:
    runner = load_runner()
    lf_path = tmp_path / "lf.txt"
    crlf_path = tmp_path / "crlf.txt"
    lf_path.write_bytes(b"alpha\nbeta\n")
    crlf_path.write_bytes(b"alpha\r\nbeta\r\n")

    lf_hash, lf_scope = runner.processed_input_hash(lf_path)
    crlf_hash, crlf_scope = runner.processed_input_hash(crlf_path)

    assert lf_scope == crlf_scope == "canonical_lf_text_bytes"
    assert lf_hash == crlf_hash == hashlib.sha256(b"alpha\nbeta\n").hexdigest()

    semantic_payload = runner.build_semantic_payload(
        {},
        [
            {
                "source_path": "raw.bin",
                "source_hash_scope": "file_bytes",
                "observed_sha256": "a" * 64,
                "processed_path": "processed.txt",
                "processed_hash_scope": "canonical_lf_text_bytes",
                "processed_sha256": "b" * 64,
            }
        ],
        {},
        {},
        {},
        {},
    )
    assert semantic_payload["source_hashes"] == [
        {
            "path": "raw.bin",
            "source_hash_scope": "file_bytes",
            "sha256": "a" * 64,
            "processed_path": "processed.txt",
            "processed_hash_scope": "canonical_lf_text_bytes",
            "processed_sha256": "b" * 64,
        }
    ]


def test_replay_preserves_honest_research_gaps(built_replay) -> None:
    runner, output, _ = built_replay
    _, todos = read_csv(output / "open_todos.csv")
    state = yaml.safe_load((output / "workflow_state.yaml").read_text(encoding="utf-8"))
    assert tuple(row["issue_id"] for row in todos) == runner.EXPECTED_OPEN_ISSUES
    assert all(row["severity"] == "high" and row["status"] == "open" for row in todos)
    assert {row["gate_id"] for row in todos} == {"G3", "G6"}
    assert all(row["fix_owner_skill"] and "next_step=" in row["notes"] for row in todos)
    state_todos = {
        row["issue_id"]: (
            row["severity"],
            row["gate_id"],
            row["fix_owner_skill"],
            row["status"],
        )
        for row in state["open_todos"]
    }
    csv_todos = {
        row["issue_id"]: (
            row["severity"],
            row["gate_id"],
            row["fix_owner_skill"],
            row["status"],
        )
        for row in todos
    }
    assert state_todos == csv_todos
    for truth in ("sample_quality_ready", "p2_ready", "release_ready"):
        assert state[truth] is False
    assert state["human_review_status"] == "not_triggered_no_new_reader"

    exposure = yaml.safe_load((output / "research/segment_exposure.yaml").read_text(encoding="utf-8"))
    row = exposure["exposures"][0]
    assert row["revenue_pct"] == "MISSING_DISCLOSURE"
    assert row["profit_pct"] == "MISSING_DISCLOSURE"
    assert row["backflow_decision"] == "blocked"
    assert exposure["global_exposure_updated"] is False

    backflow = yaml.safe_load((output / "research/backflow_decision.yaml").read_text(encoding="utf-8"))
    assert backflow["backflow_decision"] == "blocked"
    assert backflow["global_state_updated"] is False
    assert backflow["required_next_skill"] == "evidence-ingest"

    report = (output / "research/stock_report_draft.md").read_text(encoding="utf-8").lower()
    for prohibited in ("buy", "sell", "hold", "买入", "卖出", "持有", "passed_external"):
        assert prohibited not in report
    assert "不构成投资建议" in report


def test_artifact_manifest_is_complete_and_hash_traceable(built_replay) -> None:
    runner, output, _ = built_replay
    fields, rows = read_csv(output / "artifact_manifest.csv")
    assert fields == runner.MANIFEST_FIELDS
    assert len({row["artifact_id"] for row in rows}) == len(rows)
    assert len({row["path"] for row in rows}) == len(rows)
    prefix = runner.TARGET_RUN_REL.as_posix() + "/"
    singleton_counts = {name: 0 for name in SINGLETON_CONTROLS}
    for row in rows:
        assert row["path"].startswith(prefix)
        assert "\\" not in row["path"]
        rel = row["path"][len(prefix) :]
        path = output / rel
        assert row["exists"] == "true"
        assert path.is_file()
        if rel in singleton_counts:
            singleton_counts[rel] += 1
            assert row["status"] == "current"
        if rel == "artifact_manifest.csv":
            assert "recursive self-hash intentionally omitted" in row["notes"]
        else:
            digest = row["notes"].rsplit("sha256=", 1)[-1]
            assert digest == sha256_file(path)
    assert singleton_counts == {name: 1 for name in SINGLETON_CONTROLS}

    _, hash_rows = read_csv(output / "validation/artifact_hashes.csv")
    assert len(hash_rows) == len(runner.HASH_INDEX_PATHS)
    for row in hash_rows:
        rel = row["path"][len(prefix) :]
        assert sha256_file(output / rel) == row["sha256"]


def test_replay_is_byte_idempotent_and_source_isolated(built_replay) -> None:
    runner, output, first_result = built_replay
    source_before = {
        rel: sha256_file(ROOT / rel)
        for rel in runner.EXPECTED_SOURCE_HASHES
        if rel.startswith(runner.SOURCE_RUN_REL.as_posix())
    }
    first_tree = tree_hashes(output)
    second_result = runner.materialize_replay(ROOT, SOURCE_RUN, output)
    second_tree = tree_hashes(output)
    source_after = {rel: sha256_file(ROOT / rel) for rel in source_before}
    assert first_tree == second_tree
    assert source_before == source_after
    assert first_result["semantic_content_sha256"] == second_result["semantic_content_sha256"]
    report = yaml.safe_load((output / "validation/idempotence_report.yaml").read_text(encoding="utf-8"))
    assert report["decision"] == "pass"
    assert report["semantic_drift_count"] == 0
    assert report["allowed_normalizations"] == []
    with pytest.raises(runner.ReplayContractError):
        runner.resolve_contract_paths(ROOT, SOURCE_RUN, SOURCE_RUN)


def test_checked_in_replay_matches_materializer(built_replay) -> None:
    _, output, _ = built_replay
    assert CANONICAL_REPLAY.is_dir()
    assert tree_hashes(CANONICAL_REPLAY) == tree_hashes(output)
