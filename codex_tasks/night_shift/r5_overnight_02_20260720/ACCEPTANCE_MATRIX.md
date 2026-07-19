# Acceptance Matrix

| Task | Delivery required | Work units | Primary acceptance |
|---|---:|---:|---|
| `ns02_t00_exact_baseline_preflight` | yes | 2 | `python -c "import subprocess; s=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(); assert s == '4340945457d661ed62967e949f862ccf2214aff2', s"` |
| `ns02_t01_night01_completion_audit` | yes | 2 | `python -c "from pathlib import Path; assert Path('reports/p1_6/r5_night_shift/r5_overnight_02_20260720/completion_audit.md').is_file()"` |
| `ns02_t02_windows_path_branch_guard` | yes | 4 | `python -m pytest -q tests/test_r5_night_shift_git_targets.py` |
| `ns02_t03_stale_baseline_detector` | yes | 4 | `python -m pytest -q tests/test_r5_night_shift_publication.py` |
| `ns02_t10_mission_outcome_model` | yes | 4 | `python -m pytest -q tests/test_r5_night_shift_outcome.py` |
| `ns02_t11_no_safe_pilot_not_success` | yes | 4 | `python -m pytest -q tests/test_r5_night_shift_outcome.py tests/test_r5_night_shift_pilot_eligibility.py` |
| `ns02_t12_program_goal_close_policy` | yes | 4 | `python -m pytest -q tests/test_r5_night_shift_goal_policy.py` |
| `ns02_t13_open_mission_resume` | yes | 4 | `python -m pytest -q tests/test_r5_night_shift_resume.py tests/test_r5_night_shift_lock.py` |
| `ns02_t14_two_phase_publication` | yes | 5 | `python -m pytest -q tests/test_r5_night_shift_publication.py tests/test_r5_night_shift_receipts.py` |
| `ns02_t15_digest_integrity` | yes | 3 | `python -m pytest -q tests/test_r5_night_shift_digest.py tests/test_r5_night_shift_receipts.py` |
| `ns02_t20_contract_authority_schema` | yes | 5 | `python -m pytest -q tests/test_r5_night_shift_contract.py tests/test_r5_night_shift_authority.py` |
| `ns02_t21_contract_lint` | yes | 4 | `python -m pytest -q tests/test_r5_night_shift_contract_lint.py` |
| `ns02_t22_acceptance_command_safety` | yes | 4 | `python -m pytest -q tests/test_r5_night_shift_command_safety.py` |
| `ns02_t23_task_diff_scope_guard` | yes | 5 | `python -m pytest -q tests/test_r5_night_shift_scope_guard.py` |
| `ns02_t24_contract_proposal_generator` | yes | 5 | `python -m pytest -q tests/test_r5_night_shift_contract_proposals.py` |
| `ns02_t25_review_packet_hash_lock` | yes | 4 | `python -m pytest -q tests/test_r5_night_shift_review_handoff.py` |
| `ns02_t26_semantic_contract_router` | yes | 5 | `python -m pytest -q tests/test_r5_night_shift_semantic_router.py` |
| `ns02_t30_occurrence_queue_expander` | yes | 5 | `python -m pytest -q tests/test_r5_night_shift_queue_expansion.py tests/test_r5_night_shift_bf2_seed.py` |
| `ns02_t31_dependency_dag` | yes | 4 | `python -m pytest -q tests/test_r5_night_shift_dependency_dag.py` |
| `ns02_t32_evidence_request_packets` | yes | 4 | `python -m pytest -q tests/test_r5_night_shift_backflow_packets.py` |
| `ns02_t33_analysis_workbooks` | yes | 4 | `python -m pytest -q tests/test_r5_night_shift_backflow_packets.py` |
| `ns02_t34_human_gate_handoffs` | yes | 4 | `python -m pytest -q tests/test_r5_night_shift_human_gate.py` |
| `ns02_t35_pointer_contract_proposals` | yes | 6 | `python -m pytest -q tests/test_r5_night_shift_pointer_proposals.py` |
| `ns02_t36_fallback_engineering_backlog` | yes | 5 | `python -m pytest -q tests/test_r5_night_shift_fallback_backlog.py` |
| `ns02_t37_failure_spawn_retry` | yes | 4 | `python -m pytest -q tests/test_r5_night_shift_retry_graph.py` |
| `ns02_t38_queue_metrics_and_capacity` | yes | 4 | `python -m pytest -q tests/test_r5_night_shift_metrics.py` |
| `ns02_t39_pilot_eligibility_gate` | no | 5 | `python -m pytest -q tests/test_r5_night_shift_pilot_eligibility.py` |
| `ns02_t40_adversarial_test_matrix` | yes | 7 | `python -m pytest -q tests/test_r5_night_shift_adversarial.py tests/test_r5_night_shift_git_targets.py tests/test_r5_night_shift_digest.py tests/test_r5_night_shift_semantic_router.py` |
| `ns02_t41_crash_cutoff_resume_tests` | yes | 6 | `python -m pytest -q tests/test_r5_night_shift_crash_recovery.py tests/test_r5_night_shift_resume.py tests/test_r5_night_shift_lock.py` |
| `ns02_t42_ci_integration` | yes | 5 | `python -m pytest -q tests/test_r5_night_shift_ci_contract.py` |
| `ns02_t43_bf2_dry_run_truth_preservation` | yes | 6 | `python -m pytest -q tests/test_r5_night_shift_bf2_dry_run.py tests/test_r5_night_shift_bf2_seed.py` |
| `ns02_t44_determinism_double_run` | yes | 5 | `python -m pytest -q tests/test_r5_night_shift_determinism.py tests/test_r5_night_shift_readout.py` |
| `ns02_t45_full_regression_scope_audit` | yes | 7 | `python -m pytest -q tests/test_r5_night_shift_*.py` |
| `ns02_t46_commit_push_remote_ci` | yes | 5 | `python -c "import subprocess; b=subprocess.check_output(['git','branch','--show-current'], text=True).strip(); assert b == 'codex/r5-night02-contract-recovery', b"` |
| `ns02_t47_morning_readout_next_queue` | yes | 5 | `python -c "from pathlib import Path; assert Path('reports/p1_6/r5_night_shift/r5_overnight_02_20260720/morning_readout.md').is_file()"` |
| `ns02_t50_golden_case_inventory` | no | 5 | `python -m pytest -q tests/test_r5_night_shift_golden_inventory.py` |
| `ns02_t51_semantic_quality_negative_fixtures` | no | 6 | `python -m pytest -q tests/test_r5_night_shift_semantic_fixture_contract.py` |
| `ns02_t52_driver_contract_gap_matrix` | no | 5 | `python -c "from pathlib import Path; assert Path('reports/p1_6/r5_night_shift/r5_overnight_02_20260720/strategic/driver_contract_gap_matrix.yaml').is_file()"` |
| `ns02_t53_bundle18_readiness_precheck` | no | 4 | `python -m pytest -q tests/test_r5_night_shift_bundle18_precheck.py` |
| `ns02_t54_next_mission_seed` | no | 4 | `python -m pytest -q tests/test_r5_night_shift_readout.py tests/test_r5_night_shift_fallback_backlog.py` |
