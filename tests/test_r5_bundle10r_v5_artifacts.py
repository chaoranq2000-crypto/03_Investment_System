from pathlib import Path

from src.report.r5_bundle10r_contracts import load_yaml, sha256_file
from src.report.r5_reader_generation import aggregate_artifacts


RUN = Path("reports/workflow_runs/wf_20260703_stock_first_002837_invic")


def test_v4_locked_history_remains_byte_identical():
    assert sha256_file(RUN / "R5_bundle10r_reader_v4.md") == "7c7286fb96f075016bbc8e3721a396392a392e7e7f4599e0dc45a04a225d9762"
    assert sha256_file(RUN / "R5_bundle10r_human_review_handoff.yaml") == "7310a6654821118b939e8dd78a45c89d6d767530d4ff2699441ff312b54359ff"
    assert sha256_file(RUN / "R5_bundle10r_reader_generation_lock.yaml") == "c012881a0c4a8b5c8e1b451e7d01c1ef3ea6d226a757fbb086c3230c02f6389d"
    lock = load_yaml(RUN / "R5_bundle10r_reader_generation_lock.yaml")
    for artifact in lock["artifacts"]:
        assert sha256_file(Path(artifact["path"])) == artifact["sha256"]


def test_v5_candidate_is_hash_bound_and_narrative_gate_clean():
    report = RUN / "R5_bundle10r_reader_v5.md"
    scorecard = load_yaml(RUN / "R5_bundle10r_reader_v5_quality_scorecard.yaml")
    handoff = load_yaml(RUN / "R5_bundle10r_human_review_handoff_v5.yaml")
    lock = load_yaml(RUN / "R5_bundle10r_reader_generation_lock_v5.yaml")

    assert scorecard["decision"] == "candidate_ready_for_human_review"
    assert scorecard["score"] == 100
    assert scorecard["truthfulness_blockers"] == []
    assert scorecard["core_section_blockers"] == []
    assert scorecard["candidate_blockers"] == []
    diagnostics = scorecard["narrative_style_diagnostics"]
    assert diagnostics["decision"] == "pass"
    assert diagnostics["h2_section_count"] == 6
    assert diagnostics["repeated_template_labels"] == []
    assert diagnostics["process_audit_hits"] == {}
    assert diagnostics["similar_paragraph_pairs"] == []
    assert diagnostics["thin_section_count"] == 0

    assert handoff["status"] == "pending"
    assert handoff["report_schema_version"] == "v5"
    assert handoff["input_hashes"]["report_sha256"] == sha256_file(report)
    assert handoff["sample_quality_allowed"] is False

    assert lock["generation_id"] == "reader_gen_r5_bundle10r_v5_574937bd3943edc1"
    assert lock["missing_artifact_count"] == 0
    assert lock["artifact_count"] == 6
    for artifact in lock["artifacts"]:
        assert sha256_file(Path(artifact["path"])) == artifact["sha256"]
    assert aggregate_artifacts(lock["artifacts"]) == lock["aggregate_sha256"]


def test_v5_human_review_pass_closes_current_loop_without_rewriting_failure_history():
    state = load_yaml(RUN / "workflow_state.yaml")
    feedback = load_yaml(RUN / "R5_bundle10r_human_feedback_v4.yaml")
    feedback_v5 = load_yaml(RUN / "R5_bundle10r_human_feedback_v5.yaml")
    submission = load_yaml(RUN / "R5_bundle10r_human_review_submission_v5.yaml")
    assert feedback["decision"] == "revision_required"
    assert feedback["full_review_attested"] is False
    assert feedback_v5["decision"] == "revision_required"
    assert feedback_v5["finding"]["severity"] == "high"
    assert feedback_v5["input_hashes"]["report_sha256"] == sha256_file(RUN / "R5_bundle10r_reader_v5.md")
    assert submission["decision"] == "accepted"
    assert submission["input_hashes"]["report_sha256"] == sha256_file(RUN / "R5_bundle10r_reader_v5.md")
    assert submission["prior_review_round"]["decision"] == "revision_required"
    assert state["status"] in {"accepted_with_todos", "in_progress"}
    assert state["current_stage"] in {"T10_close_readout", "R5_bundle13r_t1_t2_evidence_backflow"}
    if state["current_stage"] == "R5_bundle13r_t1_t2_evidence_backflow":
        assert state["next_stage"] == "R5_bundle13r_t1_t2_evidence_backflow"
        assert state["required_next_skill"] == "evidence-ingest"
        assert state["bundle13r_backflow_execution"]["status"] == "backflow_execution_in_progress"
    else:
        assert state["next_stage"] is None
        assert state["required_next_skill"] is None
    assert state["canonical_reader_status"] == "reader_v5_human_review_passed_with_todos"
    assert state["bundle10r_rebuild"]["human_review_status"] == "pending"
    assert state["bundle10r_v5_revision"]["status"] == "candidate_ready_for_human_review"
    assert state["bundle10r_v5_close"]["human_review_status"] == "pending"
    assert state["bundle10r_v5_human_review"]["decision"] == "accepted"
    assert state["bundle10r_v5_human_review"]["status"] == "passed_external"
    assert state["bundle10r_v5_human_review"]["next_stage"] is None
    assert state["bundle10r_v5_final_close"]["decision"] == "accepted_with_todos"
    assert state["quality_backflow"]["sample_quality_report_allowed"] is False
    assert state["sample_quality_allowed"] is False
    assert state["p2_allowed"] is False
