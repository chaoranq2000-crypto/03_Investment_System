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


pytestmark = pytest.mark.legacy_compatibility


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
HISTORICAL_REPLAY_BASELINE = "f60f220ae252262a537c612ce193fc779901984b"
HISTORICAL_REPLAY_PREFIX = (
    "reports/workflow_runs/wf_20260723_stock_first_002837_v1_replay"
)
HISTORICAL_REPLAY_BLOBS = {
    "artifact_manifest.csv": (
        "58c93d464f93b365714747cbb564e7b9263553c3",
        4247,
        "bc256a3be21bbe0f9c8623ce7cf9571f59f7e4f414a506ed65481022367f1052",
    ),
    "inputs/claim_snapshot.csv": (
        "94b3d4668256b98039e35d6128aa41fb6bf56a46",
        151,
        "971ee42de92fcd0e68bf9d5232f40792aa327284c369ae6a79d3413fae4a3015",
    ),
    "inputs/input_provenance.csv": (
        "b4a375269d3ac8bbc4bbf75e277b69a69ca0a5de",
        10831,
        "eec9e4ede0483390ccb1419ac4ef9a84c1a772a9cb6edc8ceb3fc30e987757db",
    ),
    "inputs/metric_candidates.csv": (
        "b7db88fc934c13dd4f51ee343ee09275ccdb621f",
        83200,
        "146d32f45474527ad9abd2d3d473ca9e115f000458f1b825a26ccd3928f91cdf",
    ),
    "open_todos.csv": (
        "02af505e25268e22b7bd80aaab7a9ddd06b6c93d",
        1883,
        "a049c1211cfa669f8dd857c2207768e5cda1f3c5ff7b8a5e3dec4ef3b5ac7706",
    ),
    "quality_gate_report.md": (
        "c55f14588c286833af3f8b199fd1498bbb9d2f32",
        2803,
        "287e8018f9ad14331dfdddf68f1c2e5e75472ca57baafa1b9861dc6b23e18b08",
    ),
    "research/backflow_decision.yaml": (
        "9fa2b2fa077eabdfc488bd26ac4f61d0da9a5b59",
        1452,
        "f60e629eef8377c116d470455f378f5d1ab0defd11f263931570ad4ebd9f6da4",
    ),
    "research/segment_exposure.yaml": (
        "aaabe2608df80a997e7478a3af1e9cf427ad1b70",
        837,
        "cf4067f63af8f7ab492f0693bda40b54e476f4515a9023ab45c93c67d89a4831",
    ),
    "research/stock_report_draft.md": (
        "4a6d0500476be50df4034fe9865d021475f384f1",
        1439,
        "019530a51b0f0a03f0f461ff6dabe35a5b17ae41d06f50db1c9757f612d49cf1",
    ),
    "research/stock_research_pack.yaml": (
        "b5c02f452e51f9c7e1a28fa3888e17492b083833",
        4154,
        "0f803e31f2d935d7741da8eb11311a0666684e35b3381cdf60c5f47ac819e562",
    ),
    "run_log.md": (
        "4504e73d641c11b4f66b7ede1be62420e78c086a",
        1287,
        "f31b714c7584493bf8e07f0763c75f0b746eb36195c9b77025444fb26388e770",
    ),
    "validation/artifact_hashes.csv": (
        "d7fdc17dfe25db8735382643bbc553e9041297c6",
        2755,
        "e23f8e66846dcbc9606b1044272860894c912db8a900b8c124cdfaab19fdfef3",
    ),
    "validation/idempotence_report.yaml": (
        "88e2481cbb83fa2b8e34edc8902671f64a5937fe",
        4253,
        "7c906ff170addcc39a0de1d7574f6eb637026469f5ad0f597f6e30d6bfd88271",
    ),
    "validation/replay_receipt.yaml": (
        "be8d84762e1787d180c0d1b3289b4ed6ff6f1f45",
        1391,
        "a395c2e0a9f2c55342221249a47f4ae2291844dfa5cd59a417284ad01d59c925",
    ),
    "workflow_readout.md": (
        "2e26e373ed0091cd366071d2f1522e36022ba961",
        1585,
        "3a1b7d8df42138041a9d36a4972e2f8811c33bcdc4677ae4d43083709297c4d8",
    ),
    "workflow_state.yaml": (
        "18b27d1d27f9f401850b15510954a68c3a1f1323",
        10261,
        "23331ce5c47d3a5185e7a098de9af94a5a49f0e461289a9dcdc686066b1972a6",
    ),
}

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


def historical_replay_blob(relative_path: str) -> bytes:
    expected_oid, expected_bytes, expected_sha256 = HISTORICAL_REPLAY_BLOBS[
        relative_path
    ]
    repository_path = f"{HISTORICAL_REPLAY_PREFIX}/{relative_path}"
    spec = f"{HISTORICAL_REPLAY_BASELINE}:{repository_path}"
    observed_oid = subprocess.check_output(
        ["git", "rev-parse", "--verify", spec],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()
    assert observed_oid == expected_oid
    assert (
        subprocess.check_output(
            ["git", "cat-file", "-t", spec],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
        ).strip()
        == "blob"
    )
    observed_bytes = int(
        subprocess.check_output(
            ["git", "cat-file", "-s", spec],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
        ).strip()
    )
    assert observed_bytes == expected_bytes
    payload = subprocess.check_output(["git", "cat-file", "blob", spec], cwd=ROOT)
    assert len(payload) == expected_bytes
    assert hashlib.sha256(payload).hexdigest() == expected_sha256
    return payload


@pytest.fixture(scope="module")
def built_replay(tmp_path_factory: pytest.TempPathFactory):
    runner = load_runner()
    output = tmp_path_factory.mktemp("r5_v1_replay") / "run"
    fixture_root = tmp_path_factory.mktemp("r5_v1_replay_source")
    result = runner.materialize_replay(
        ROOT,
        SOURCE_RUN,
        output,
        historical_fixture_root=fixture_root,
    )
    return runner, output, result


def test_replay_cli_rejects_repository_historical_output(tmp_path: Path) -> None:
    runner = load_runner()
    old_target = ROOT / runner.TARGET_RUN_REL
    with pytest.raises(
        runner.ReplayContractError,
        match="must not recreate the retired repository path",
    ):
        runner.validate_output_run(ROOT, old_target)
    with pytest.raises(
        runner.ReplayContractError,
        match="repository output must be an explicit child of .codex_tmp",
    ):
        runner.validate_output_run(
            ROOT,
            ROOT / "reports" / "workflow_runs" / "another_historical_replay",
        )
    with pytest.raises(
        runner.ReplayContractError,
        match="repository output must be an explicit child of .codex_tmp",
    ):
        runner.validate_output_run(ROOT, ROOT / ".codex_tmp")
    with pytest.raises(
        runner.ReplayContractError,
        match="must be an explicit child of the system temporary directory",
    ):
        runner.validate_output_run(
            ROOT,
            Path(ROOT.anchor) / "codex_replay_forbidden_output",
        )

    allowed_system_temp = runner.validate_output_run(
        ROOT,
        tmp_path / "explicit_replay_output",
    )
    assert allowed_system_temp == (tmp_path / "explicit_replay_output").resolve()
    allowed_repo_temp = runner.validate_output_run(
        ROOT,
        ROOT / ".codex_tmp" / "explicit_replay_output",
    )
    assert allowed_repo_temp == (
        ROOT / ".codex_tmp" / "explicit_replay_output"
    ).resolve()

    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(SCRIPT),
            "--repo-root",
            str(ROOT),
            "--source-run",
            str(SOURCE_RUN),
            "--output-run",
            str(old_target),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert completed.returncode == 2
    assert "must not recreate the retired repository path" in completed.stderr


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
        assert row["source_hash_scope"] == "file_bytes"
        if runner.is_historical_source_path(row["source_path"]):
            payload = runner.read_git_blob(
                ROOT,
                runner.HISTORICAL_BASELINE,
                row["source_path"],
            )
            observed = hashlib.sha256(payload).hexdigest()
        else:
            source = ROOT / row["source_path"]
            assert source.is_file()
            observed = sha256_for_scope(source, row["source_hash_scope"])
        assert observed == row["expected_sha256"] == row["observed_sha256"]
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


def test_replay_is_byte_idempotent_and_source_isolated(
    built_replay,
    tmp_path: Path,
) -> None:
    runner, output, first_result = built_replay
    source_before = {
        rel: hashlib.sha256(
            runner.read_git_blob(ROOT, runner.HISTORICAL_BASELINE, rel)
        ).hexdigest()
        for rel in runner.EXPECTED_SOURCE_HASHES
        if runner.is_historical_source_path(rel)
    }
    first_tree = tree_hashes(output)
    second_result = runner.materialize_replay(
        ROOT,
        SOURCE_RUN,
        output,
        historical_fixture_root=tmp_path / "historical_source_fixture",
    )
    second_tree = tree_hashes(output)
    source_after = {
        rel: hashlib.sha256(
            runner.read_git_blob(ROOT, runner.HISTORICAL_BASELINE, rel)
        ).hexdigest()
        for rel in source_before
    }
    assert first_tree == second_tree
    assert source_before == source_after
    assert first_result["semantic_content_sha256"] == second_result["semantic_content_sha256"]
    report = yaml.safe_load((output / "validation/idempotence_report.yaml").read_text(encoding="utf-8"))
    assert report["decision"] == "pass"
    assert report["semantic_drift_count"] == 0
    assert report["allowed_normalizations"] == []
    with pytest.raises(runner.ReplayContractError):
        runner.resolve_contract_paths(ROOT, SOURCE_RUN, SOURCE_RUN)


def test_historical_replay_tree_is_git_recoverable(built_replay) -> None:
    runner, output, _ = built_replay
    assert runner.HISTORICAL_BASELINE == HISTORICAL_REPLAY_BASELINE
    generated_hashes = tree_hashes(output)
    expected_hashes = {
        relative_path: receipt[2]
        for relative_path, receipt in HISTORICAL_REPLAY_BLOBS.items()
    }
    assert generated_hashes == expected_hashes
    assert len(HISTORICAL_REPLAY_BLOBS) == 16
    assert sum(row[1] for row in HISTORICAL_REPLAY_BLOBS.values()) == 132529

    payloads = {
        relative_path: historical_replay_blob(relative_path)
        for relative_path in HISTORICAL_REPLAY_BLOBS
    }
    manifest_rows = list(
        csv.DictReader(
            payloads["artifact_manifest.csv"]
            .decode("utf-8-sig")
            .splitlines()
        )
    )
    prefix = HISTORICAL_REPLAY_PREFIX + "/"
    assert {
        row["path"].removeprefix(prefix) for row in manifest_rows
    } == set(HISTORICAL_REPLAY_BLOBS)
    for row in manifest_rows:
        relative_path = row["path"].removeprefix(prefix)
        assert row["path"].startswith(prefix)
        if relative_path == "artifact_manifest.csv":
            assert "recursive self-hash intentionally omitted" in row["notes"]
        else:
            expected_sha256 = HISTORICAL_REPLAY_BLOBS[relative_path][2]
            assert row["notes"].rsplit("sha256=", 1)[-1] == expected_sha256

    hash_rows = list(
        csv.DictReader(
            payloads["validation/artifact_hashes.csv"]
            .decode("utf-8-sig")
            .splitlines()
        )
    )
    for row in hash_rows:
        relative_path = row["path"].removeprefix(prefix)
        assert row["path"].startswith(prefix)
        assert row["sha256"] == HISTORICAL_REPLAY_BLOBS[relative_path][2]
