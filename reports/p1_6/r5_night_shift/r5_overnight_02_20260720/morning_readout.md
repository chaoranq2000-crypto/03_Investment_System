# R5 Night Shift Morning Readout — r5_overnight_02_20260720

## 0. Mission outcome 与长期 Goal

- Night02 mission outcome: `delivered`
- Long-term program goal: `open_needs_targeted_backflow`
- Program goal close allowed: `false`
- Research truth: `6 work orders pending; 0/63 blocker occurrences resolved`
- Final publication identity: `publication/remote_delivery_receipt.json`（post-push 事实源）

## 1. Baseline

- Source branch: `codex/r5-night01-autonomous-harness`
- Source SHA: `4340945457d661ed62967e949f862ccf2214aff2`
- Target branch: `codex/r5-night02-contract-recovery`
- Local SHA: `ad9b2c2df7049060e093fa08869266a1fdc74366`
- Remote SHA: `ad9b2c2df7049060e093fa08869266a1fdc74366`
- Local/remote SHA equality: `true`
- Embedded CI status: `success`

## 2. Completed tasks

- Passed: `40` / `40`
- Passed task IDs: `ns02_t00_exact_baseline_preflight, ns02_t01_night01_completion_audit, ns02_t02_windows_path_branch_guard, ns02_t03_stale_baseline_detector, ns02_t10_mission_outcome_model, ns02_t11_no_safe_pilot_not_success, ns02_t12_program_goal_close_policy, ns02_t13_open_mission_resume, ns02_t14_two_phase_publication, ns02_t15_digest_integrity, ns02_t20_contract_authority_schema, ns02_t21_contract_lint, ns02_t22_acceptance_command_safety, ns02_t23_task_diff_scope_guard, ns02_t24_contract_proposal_generator, ns02_t25_review_packet_hash_lock, ns02_t26_semantic_contract_router, ns02_t30_occurrence_queue_expander, ns02_t31_dependency_dag, ns02_t32_evidence_request_packets, ns02_t33_analysis_workbooks, ns02_t34_human_gate_handoffs, ns02_t35_pointer_contract_proposals, ns02_t36_fallback_engineering_backlog, ns02_t37_failure_spawn_retry, ns02_t38_queue_metrics_and_capacity, ns02_t39_pilot_eligibility_gate, ns02_t40_adversarial_test_matrix, ns02_t41_crash_cutoff_resume_tests, ns02_t42_ci_integration, ns02_t43_bf2_dry_run_truth_preservation, ns02_t44_determinism_double_run, ns02_t45_full_regression_scope_audit, ns02_t46_commit_push_remote_ci, ns02_t47_morning_readout_next_queue, ns02_t50_golden_case_inventory, ns02_t51_semantic_quality_negative_fixtures, ns02_t52_driver_contract_gap_matrix, ns02_t53_bundle18_readiness_precheck, ns02_t54_next_mission_seed`

## 3. Commits

- `762884f8cabf9457a139321ffb47a341cdcb40af` — feat(night-shift): harden mission outcome and publication
- `7696df7f16831604092b089fa948794742c94cc6` — feat(night-shift): enforce executable contract authority
- `664f1d31ae644a259d0448c5f563a3e20d2e3eca` — feat(night-shift): expand backflow queue and fallback work
- `d3e1b192a58f6b53ecc4b32a7bf8ee66a3d0c7cf` — test(night-shift): add adversarial recovery coverage
- `2a25550f480e7b0011497b1bc96feb80f20c08c3` — fix(night-shift): make git target validation cross-platform
- `ad9b2c2df7049060e093fa08869266a1fdc74366` — docs(night-shift): publish mission 02 evidence and next queue

## 4. Validation

| Result | Command | Summary |
|---|---|---|
| pass | `python -m pytest -q tests/test_r5_night_shift_*.py` | 99 passed in 3.74s |
| pass | `python scripts/run_source_route_quality_gate.py --import-check --output reports/quality/ci_source_route_quality_report.yaml` | decision=pass capabilities=17 blocking=0 |
| pass | `python -m pytest -q` | 1032 passed, 2 skipped in 49.82s |
| pass | `git diff --check` |  |
| pass | `python -c "import subprocess; files=subprocess.check_output(['git','ls-files'], text=True).splitlines(); bad=[p for p in files if p.startswith('.local/') or p.endswith('.pyc') or '/__pycache__/' in p]; assert not bad, bad"` |  |
| pass | `byte-for-byte determinism comparisons` | comparisons=10 |

## 5. BF2 truth delta

| Metric | Start | End |
|---|---:|---:|
| Work orders pending | 6 | 6 |
| Blocker occurrences resolved | 0 / 63 | 0 / 63 |
| Failed results | 0 | 0 |
| Orphans | 0 | 0 |
| Rejected artifacts | 0 | 0 |

## 6. Scope audit

- Forbidden paths changed: `0`
- `.local/` tracked: `0`
- BF2 run outputs tracked: `0`
- Scope guard: `pass`
- PR created: `false`
- Main merged: `false`

## 7. Current research gate

`needs_targeted_backflow`. Classification did not resolve research blockers; sample quality and P2 remain closed.

## 8. Next-night queue

| Priority | Task | Status | Dependency |
|---:|---|---|---|
| 200 | `ns02_t30_occ_04343acd916afae4` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_07e49c037427403b` | `dependency_blocked` | `ns02_t30_occ_04343acd916afae4, ns02_t30_occ_101f0195f0c5cf37, ns02_t30_occ_1842382e6647f17d, ns02_t30_occ_1977687ea7bce884, ns02_t30_occ_23259d462e4ca0f3, ns02_t30_occ_2c030a28f8631544, ns02_t30_occ_3139481aee5c01e0, ns02_t30_occ_3caf2ad00e1b6285, ns02_t30_occ_3d282b4ad0ca31e2, ns02_t30_occ_6491a19059d9ec6c, ns02_t30_occ_6870f1ec5d1048be, ns02_t30_occ_6b198842cf80755a, ns02_t30_occ_6cd0e0bd57166a21, ns02_t30_occ_6d2b87d81881062e, ns02_t30_occ_6ff83cb834d7176d, ns02_t30_occ_7213df41458cf67d, ns02_t30_occ_76d9fbbac37b50a6, ns02_t30_occ_7745e52b12c07f1c, ns02_t30_occ_7a3640d70206502d, ns02_t30_occ_86fb71b6c845c94f, ns02_t30_occ_97d3e4a3c0388529, ns02_t30_occ_99e77539490b01ad, ns02_t30_occ_9fe0bbfe8ab9bb7d, ns02_t30_occ_a88a58ab2685ee6e, ns02_t30_occ_a9673677adb3ef8a, ns02_t30_occ_ab0f8aac8f21f0db, ns02_t30_occ_ab6b62516df0a0f1, ns02_t30_occ_b52cbf88aff2c105, ns02_t30_occ_be4e0eb69d196ff7, ns02_t30_occ_becffa9c7cb6d886, ns02_t30_occ_c7f5c80f4b2e7a9c, ns02_t30_occ_c8af30bbe2f10e8a, ns02_t30_occ_cdf02c368ebec0a7, ns02_t30_occ_d2ef6aeae1113c9c, ns02_t30_occ_db819651b1640db8, ns02_t30_occ_dc67ef1afb1051ef, ns02_t30_occ_e3fefccd3e77fd5a, ns02_t30_occ_e48b0cd43634c242, ns02_t30_occ_e855cd5fb843f9bf, ns02_t30_occ_e95d9ae85fb2fba0, ns02_t30_occ_eb221be0020f7038, ns02_t30_occ_ee055856e18cd3f4, ns02_t30_occ_f9fff3f413f6c43c` |
| 200 | `ns02_t30_occ_101f0195f0c5cf37` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_10e1e793011ee907` | `dependency_blocked` | `ns02_t30_occ_101f0195f0c5cf37, ns02_t30_occ_3d282b4ad0ca31e2, ns02_t30_occ_6d2b87d81881062e, ns02_t30_occ_76d9fbbac37b50a6, ns02_t30_occ_9fe0bbfe8ab9bb7d, ns02_t30_occ_ab0f8aac8f21f0db, ns02_t30_occ_c8af30bbe2f10e8a, ns02_t30_occ_cdf02c368ebec0a7, ns02_t30_occ_e3fefccd3e77fd5a, ns02_t30_occ_ee055856e18cd3f4` |
| 200 | `ns02_t30_occ_139f375db9714f27` | `dependency_blocked` | `ns02_t30_occ_04343acd916afae4, ns02_t30_occ_1977687ea7bce884, ns02_t30_occ_23259d462e4ca0f3, ns02_t30_occ_2c030a28f8631544, ns02_t30_occ_3caf2ad00e1b6285, ns02_t30_occ_6870f1ec5d1048be, ns02_t30_occ_6cd0e0bd57166a21, ns02_t30_occ_86fb71b6c845c94f, ns02_t30_occ_becffa9c7cb6d886, ns02_t30_occ_d2ef6aeae1113c9c` |
| 200 | `ns02_t30_occ_1842382e6647f17d` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_1977687ea7bce884` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_1a742ef3d6224c6a` | `dependency_blocked` | `ns02_t30_occ_1842382e6647f17d, ns02_t30_occ_6b198842cf80755a, ns02_t30_occ_6ff83cb834d7176d, ns02_t30_occ_7745e52b12c07f1c, ns02_t30_occ_7a3640d70206502d, ns02_t30_occ_a88a58ab2685ee6e, ns02_t30_occ_db819651b1640db8, ns02_t30_occ_e48b0cd43634c242, ns02_t30_occ_e855cd5fb843f9bf, ns02_t30_occ_f9fff3f413f6c43c` |
| 200 | `ns02_t30_occ_23259d462e4ca0f3` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_2a2ab71eced6e937` | `dependency_blocked` | `ns02_t30_occ_1842382e6647f17d, ns02_t30_occ_6b198842cf80755a, ns02_t30_occ_6ff83cb834d7176d, ns02_t30_occ_7745e52b12c07f1c, ns02_t30_occ_7a3640d70206502d, ns02_t30_occ_a88a58ab2685ee6e, ns02_t30_occ_db819651b1640db8, ns02_t30_occ_e48b0cd43634c242, ns02_t30_occ_e855cd5fb843f9bf, ns02_t30_occ_f9fff3f413f6c43c` |
| 200 | `ns02_t30_occ_2b0567ebbd443da5` | `dependency_blocked` | `ns02_t30_occ_3139481aee5c01e0, ns02_t30_occ_6491a19059d9ec6c, ns02_t30_occ_97d3e4a3c0388529, ns02_t30_occ_99e77539490b01ad, ns02_t30_occ_a9673677adb3ef8a, ns02_t30_occ_b52cbf88aff2c105, ns02_t30_occ_c7f5c80f4b2e7a9c, ns02_t30_occ_dc67ef1afb1051ef, ns02_t30_occ_e95d9ae85fb2fba0, ns02_t30_occ_eb221be0020f7038` |
| 200 | `ns02_t30_occ_2c030a28f8631544` | `evidence_required` | `none` |
| 200 | `ns02_t30_occ_3139481aee5c01e0` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_3b0dd1527f9e0144` | `dependency_blocked` | `ns02_t30_occ_04343acd916afae4, ns02_t30_occ_101f0195f0c5cf37, ns02_t30_occ_1842382e6647f17d, ns02_t30_occ_1977687ea7bce884, ns02_t30_occ_23259d462e4ca0f3, ns02_t30_occ_2c030a28f8631544, ns02_t30_occ_3139481aee5c01e0, ns02_t30_occ_3caf2ad00e1b6285, ns02_t30_occ_3d282b4ad0ca31e2, ns02_t30_occ_6491a19059d9ec6c, ns02_t30_occ_6870f1ec5d1048be, ns02_t30_occ_6b198842cf80755a, ns02_t30_occ_6cd0e0bd57166a21, ns02_t30_occ_6d2b87d81881062e, ns02_t30_occ_6ff83cb834d7176d, ns02_t30_occ_7213df41458cf67d, ns02_t30_occ_76d9fbbac37b50a6, ns02_t30_occ_7745e52b12c07f1c, ns02_t30_occ_7a3640d70206502d, ns02_t30_occ_86fb71b6c845c94f, ns02_t30_occ_97d3e4a3c0388529, ns02_t30_occ_99e77539490b01ad, ns02_t30_occ_9fe0bbfe8ab9bb7d, ns02_t30_occ_a88a58ab2685ee6e, ns02_t30_occ_a9673677adb3ef8a, ns02_t30_occ_ab0f8aac8f21f0db, ns02_t30_occ_ab6b62516df0a0f1, ns02_t30_occ_b52cbf88aff2c105, ns02_t30_occ_be4e0eb69d196ff7, ns02_t30_occ_becffa9c7cb6d886, ns02_t30_occ_c7f5c80f4b2e7a9c, ns02_t30_occ_c8af30bbe2f10e8a, ns02_t30_occ_cdf02c368ebec0a7, ns02_t30_occ_d2ef6aeae1113c9c, ns02_t30_occ_db819651b1640db8, ns02_t30_occ_dc67ef1afb1051ef, ns02_t30_occ_e3fefccd3e77fd5a, ns02_t30_occ_e48b0cd43634c242, ns02_t30_occ_e855cd5fb843f9bf, ns02_t30_occ_e95d9ae85fb2fba0, ns02_t30_occ_eb221be0020f7038, ns02_t30_occ_ee055856e18cd3f4, ns02_t30_occ_f9fff3f413f6c43c` |
| 200 | `ns02_t30_occ_3caf2ad00e1b6285` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_3d282b4ad0ca31e2` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_4177e7d48f374473` | `dependency_blocked` | `ns02_t30_occ_3139481aee5c01e0, ns02_t30_occ_6491a19059d9ec6c, ns02_t30_occ_97d3e4a3c0388529, ns02_t30_occ_99e77539490b01ad, ns02_t30_occ_a9673677adb3ef8a, ns02_t30_occ_b52cbf88aff2c105, ns02_t30_occ_c7f5c80f4b2e7a9c, ns02_t30_occ_dc67ef1afb1051ef, ns02_t30_occ_e95d9ae85fb2fba0, ns02_t30_occ_eb221be0020f7038` |
| 200 | `ns02_t30_occ_60f5539e2d72463f` | `dependency_blocked` | `ns02_t30_occ_101f0195f0c5cf37, ns02_t30_occ_3d282b4ad0ca31e2, ns02_t30_occ_6d2b87d81881062e, ns02_t30_occ_76d9fbbac37b50a6, ns02_t30_occ_9fe0bbfe8ab9bb7d, ns02_t30_occ_ab0f8aac8f21f0db, ns02_t30_occ_c8af30bbe2f10e8a, ns02_t30_occ_cdf02c368ebec0a7, ns02_t30_occ_e3fefccd3e77fd5a, ns02_t30_occ_ee055856e18cd3f4` |
| 200 | `ns02_t30_occ_6491a19059d9ec6c` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_6870f1ec5d1048be` | `evidence_required` | `none` |
| 200 | `ns02_t30_occ_6b198842cf80755a` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_6cd0e0bd57166a21` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_6d2b87d81881062e` | `evidence_required` | `none` |
| 200 | `ns02_t30_occ_6e5fb996533eab2b` | `dependency_blocked` | `ns02_t30_occ_101f0195f0c5cf37, ns02_t30_occ_3d282b4ad0ca31e2, ns02_t30_occ_6d2b87d81881062e, ns02_t30_occ_76d9fbbac37b50a6, ns02_t30_occ_9fe0bbfe8ab9bb7d, ns02_t30_occ_ab0f8aac8f21f0db, ns02_t30_occ_c8af30bbe2f10e8a, ns02_t30_occ_cdf02c368ebec0a7, ns02_t30_occ_e3fefccd3e77fd5a, ns02_t30_occ_ee055856e18cd3f4` |
| 200 | `ns02_t30_occ_6ff83cb834d7176d` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_7213df41458cf67d` | `human_gate` | `none` |
| 200 | `ns02_t30_occ_76d9fbbac37b50a6` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_7745e52b12c07f1c` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_7a3640d70206502d` | `evidence_required` | `none` |
| 200 | `ns02_t30_occ_86fb71b6c845c94f` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_8e3768557d6f2dde` | `dependency_blocked` | `ns02_t30_occ_04343acd916afae4, ns02_t30_occ_101f0195f0c5cf37, ns02_t30_occ_1842382e6647f17d, ns02_t30_occ_1977687ea7bce884, ns02_t30_occ_23259d462e4ca0f3, ns02_t30_occ_2c030a28f8631544, ns02_t30_occ_3139481aee5c01e0, ns02_t30_occ_3caf2ad00e1b6285, ns02_t30_occ_3d282b4ad0ca31e2, ns02_t30_occ_6491a19059d9ec6c, ns02_t30_occ_6870f1ec5d1048be, ns02_t30_occ_6b198842cf80755a, ns02_t30_occ_6cd0e0bd57166a21, ns02_t30_occ_6d2b87d81881062e, ns02_t30_occ_6ff83cb834d7176d, ns02_t30_occ_7213df41458cf67d, ns02_t30_occ_76d9fbbac37b50a6, ns02_t30_occ_7745e52b12c07f1c, ns02_t30_occ_7a3640d70206502d, ns02_t30_occ_86fb71b6c845c94f, ns02_t30_occ_97d3e4a3c0388529, ns02_t30_occ_99e77539490b01ad, ns02_t30_occ_9fe0bbfe8ab9bb7d, ns02_t30_occ_a88a58ab2685ee6e, ns02_t30_occ_a9673677adb3ef8a, ns02_t30_occ_ab0f8aac8f21f0db, ns02_t30_occ_ab6b62516df0a0f1, ns02_t30_occ_b52cbf88aff2c105, ns02_t30_occ_be4e0eb69d196ff7, ns02_t30_occ_becffa9c7cb6d886, ns02_t30_occ_c7f5c80f4b2e7a9c, ns02_t30_occ_c8af30bbe2f10e8a, ns02_t30_occ_cdf02c368ebec0a7, ns02_t30_occ_d2ef6aeae1113c9c, ns02_t30_occ_db819651b1640db8, ns02_t30_occ_dc67ef1afb1051ef, ns02_t30_occ_e3fefccd3e77fd5a, ns02_t30_occ_e48b0cd43634c242, ns02_t30_occ_e855cd5fb843f9bf, ns02_t30_occ_e95d9ae85fb2fba0, ns02_t30_occ_eb221be0020f7038, ns02_t30_occ_ee055856e18cd3f4, ns02_t30_occ_f9fff3f413f6c43c` |
| 200 | `ns02_t30_occ_950802f6c70d5036` | `dependency_blocked` | `ns02_t30_occ_04343acd916afae4, ns02_t30_occ_1977687ea7bce884, ns02_t30_occ_23259d462e4ca0f3, ns02_t30_occ_2c030a28f8631544, ns02_t30_occ_3caf2ad00e1b6285, ns02_t30_occ_6870f1ec5d1048be, ns02_t30_occ_6cd0e0bd57166a21, ns02_t30_occ_86fb71b6c845c94f, ns02_t30_occ_becffa9c7cb6d886, ns02_t30_occ_d2ef6aeae1113c9c` |
| 200 | `ns02_t30_occ_97d3e4a3c0388529` | `evidence_required` | `none` |
| 200 | `ns02_t30_occ_99e77539490b01ad` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_9fe0bbfe8ab9bb7d` | `evidence_required` | `none` |
| 200 | `ns02_t30_occ_a88a58ab2685ee6e` | `evidence_required` | `none` |
| 200 | `ns02_t30_occ_a9673677adb3ef8a` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_ab0f8aac8f21f0db` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_ab6b62516df0a0f1` | `human_gate` | `none` |
| 200 | `ns02_t30_occ_ae4ebd1d82c2bd03` | `dependency_blocked` | `ns02_t30_occ_04343acd916afae4, ns02_t30_occ_101f0195f0c5cf37, ns02_t30_occ_1842382e6647f17d, ns02_t30_occ_1977687ea7bce884, ns02_t30_occ_23259d462e4ca0f3, ns02_t30_occ_2c030a28f8631544, ns02_t30_occ_3139481aee5c01e0, ns02_t30_occ_3caf2ad00e1b6285, ns02_t30_occ_3d282b4ad0ca31e2, ns02_t30_occ_6491a19059d9ec6c, ns02_t30_occ_6870f1ec5d1048be, ns02_t30_occ_6b198842cf80755a, ns02_t30_occ_6cd0e0bd57166a21, ns02_t30_occ_6d2b87d81881062e, ns02_t30_occ_6ff83cb834d7176d, ns02_t30_occ_7213df41458cf67d, ns02_t30_occ_76d9fbbac37b50a6, ns02_t30_occ_7745e52b12c07f1c, ns02_t30_occ_7a3640d70206502d, ns02_t30_occ_86fb71b6c845c94f, ns02_t30_occ_97d3e4a3c0388529, ns02_t30_occ_99e77539490b01ad, ns02_t30_occ_9fe0bbfe8ab9bb7d, ns02_t30_occ_a88a58ab2685ee6e, ns02_t30_occ_a9673677adb3ef8a, ns02_t30_occ_ab0f8aac8f21f0db, ns02_t30_occ_ab6b62516df0a0f1, ns02_t30_occ_b52cbf88aff2c105, ns02_t30_occ_be4e0eb69d196ff7, ns02_t30_occ_becffa9c7cb6d886, ns02_t30_occ_c7f5c80f4b2e7a9c, ns02_t30_occ_c8af30bbe2f10e8a, ns02_t30_occ_cdf02c368ebec0a7, ns02_t30_occ_d2ef6aeae1113c9c, ns02_t30_occ_db819651b1640db8, ns02_t30_occ_dc67ef1afb1051ef, ns02_t30_occ_e3fefccd3e77fd5a, ns02_t30_occ_e48b0cd43634c242, ns02_t30_occ_e855cd5fb843f9bf, ns02_t30_occ_e95d9ae85fb2fba0, ns02_t30_occ_eb221be0020f7038, ns02_t30_occ_ee055856e18cd3f4, ns02_t30_occ_f9fff3f413f6c43c` |
| 200 | `ns02_t30_occ_b52cbf88aff2c105` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_b531d3c48931ba58` | `dependency_blocked` | `ns02_t30_occ_1842382e6647f17d, ns02_t30_occ_6b198842cf80755a, ns02_t30_occ_6ff83cb834d7176d, ns02_t30_occ_7745e52b12c07f1c, ns02_t30_occ_7a3640d70206502d, ns02_t30_occ_a88a58ab2685ee6e, ns02_t30_occ_db819651b1640db8, ns02_t30_occ_e48b0cd43634c242, ns02_t30_occ_e855cd5fb843f9bf, ns02_t30_occ_f9fff3f413f6c43c` |
| 200 | `ns02_t30_occ_b7467ff5401814aa` | `dependency_blocked` | `ns02_t30_occ_3139481aee5c01e0, ns02_t30_occ_6491a19059d9ec6c, ns02_t30_occ_97d3e4a3c0388529, ns02_t30_occ_99e77539490b01ad, ns02_t30_occ_a9673677adb3ef8a, ns02_t30_occ_b52cbf88aff2c105, ns02_t30_occ_c7f5c80f4b2e7a9c, ns02_t30_occ_dc67ef1afb1051ef, ns02_t30_occ_e95d9ae85fb2fba0, ns02_t30_occ_eb221be0020f7038` |
| 200 | `ns02_t30_occ_be4e0eb69d196ff7` | `human_gate` | `none` |
| 200 | `ns02_t30_occ_becffa9c7cb6d886` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_c03007a138e83e9b` | `dependency_blocked` | `ns02_t30_occ_04343acd916afae4, ns02_t30_occ_101f0195f0c5cf37, ns02_t30_occ_1842382e6647f17d, ns02_t30_occ_1977687ea7bce884, ns02_t30_occ_23259d462e4ca0f3, ns02_t30_occ_2c030a28f8631544, ns02_t30_occ_3139481aee5c01e0, ns02_t30_occ_3caf2ad00e1b6285, ns02_t30_occ_3d282b4ad0ca31e2, ns02_t30_occ_6491a19059d9ec6c, ns02_t30_occ_6870f1ec5d1048be, ns02_t30_occ_6b198842cf80755a, ns02_t30_occ_6cd0e0bd57166a21, ns02_t30_occ_6d2b87d81881062e, ns02_t30_occ_6ff83cb834d7176d, ns02_t30_occ_7213df41458cf67d, ns02_t30_occ_76d9fbbac37b50a6, ns02_t30_occ_7745e52b12c07f1c, ns02_t30_occ_7a3640d70206502d, ns02_t30_occ_86fb71b6c845c94f, ns02_t30_occ_97d3e4a3c0388529, ns02_t30_occ_99e77539490b01ad, ns02_t30_occ_9fe0bbfe8ab9bb7d, ns02_t30_occ_a88a58ab2685ee6e, ns02_t30_occ_a9673677adb3ef8a, ns02_t30_occ_ab0f8aac8f21f0db, ns02_t30_occ_ab6b62516df0a0f1, ns02_t30_occ_b52cbf88aff2c105, ns02_t30_occ_be4e0eb69d196ff7, ns02_t30_occ_becffa9c7cb6d886, ns02_t30_occ_c7f5c80f4b2e7a9c, ns02_t30_occ_c8af30bbe2f10e8a, ns02_t30_occ_cdf02c368ebec0a7, ns02_t30_occ_d2ef6aeae1113c9c, ns02_t30_occ_db819651b1640db8, ns02_t30_occ_dc67ef1afb1051ef, ns02_t30_occ_e3fefccd3e77fd5a, ns02_t30_occ_e48b0cd43634c242, ns02_t30_occ_e855cd5fb843f9bf, ns02_t30_occ_e95d9ae85fb2fba0, ns02_t30_occ_eb221be0020f7038, ns02_t30_occ_ee055856e18cd3f4, ns02_t30_occ_f9fff3f413f6c43c` |
| 200 | `ns02_t30_occ_c7f5c80f4b2e7a9c` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_c8af30bbe2f10e8a` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_cdf02c368ebec0a7` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_d19d9b744d7aff4a` | `dependency_blocked` | `ns02_t30_occ_04343acd916afae4, ns02_t30_occ_101f0195f0c5cf37, ns02_t30_occ_1842382e6647f17d, ns02_t30_occ_1977687ea7bce884, ns02_t30_occ_23259d462e4ca0f3, ns02_t30_occ_2c030a28f8631544, ns02_t30_occ_3139481aee5c01e0, ns02_t30_occ_3caf2ad00e1b6285, ns02_t30_occ_3d282b4ad0ca31e2, ns02_t30_occ_6491a19059d9ec6c, ns02_t30_occ_6870f1ec5d1048be, ns02_t30_occ_6b198842cf80755a, ns02_t30_occ_6cd0e0bd57166a21, ns02_t30_occ_6d2b87d81881062e, ns02_t30_occ_6ff83cb834d7176d, ns02_t30_occ_7213df41458cf67d, ns02_t30_occ_76d9fbbac37b50a6, ns02_t30_occ_7745e52b12c07f1c, ns02_t30_occ_7a3640d70206502d, ns02_t30_occ_86fb71b6c845c94f, ns02_t30_occ_97d3e4a3c0388529, ns02_t30_occ_99e77539490b01ad, ns02_t30_occ_9fe0bbfe8ab9bb7d, ns02_t30_occ_a88a58ab2685ee6e, ns02_t30_occ_a9673677adb3ef8a, ns02_t30_occ_ab0f8aac8f21f0db, ns02_t30_occ_ab6b62516df0a0f1, ns02_t30_occ_b52cbf88aff2c105, ns02_t30_occ_be4e0eb69d196ff7, ns02_t30_occ_becffa9c7cb6d886, ns02_t30_occ_c7f5c80f4b2e7a9c, ns02_t30_occ_c8af30bbe2f10e8a, ns02_t30_occ_cdf02c368ebec0a7, ns02_t30_occ_d2ef6aeae1113c9c, ns02_t30_occ_db819651b1640db8, ns02_t30_occ_dc67ef1afb1051ef, ns02_t30_occ_e3fefccd3e77fd5a, ns02_t30_occ_e48b0cd43634c242, ns02_t30_occ_e855cd5fb843f9bf, ns02_t30_occ_e95d9ae85fb2fba0, ns02_t30_occ_eb221be0020f7038, ns02_t30_occ_ee055856e18cd3f4, ns02_t30_occ_f9fff3f413f6c43c` |
| 200 | `ns02_t30_occ_d2ef6aeae1113c9c` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_d705e67d4c161924` | `dependency_blocked` | `ns02_t30_occ_04343acd916afae4, ns02_t30_occ_101f0195f0c5cf37, ns02_t30_occ_1842382e6647f17d, ns02_t30_occ_1977687ea7bce884, ns02_t30_occ_23259d462e4ca0f3, ns02_t30_occ_2c030a28f8631544, ns02_t30_occ_3139481aee5c01e0, ns02_t30_occ_3caf2ad00e1b6285, ns02_t30_occ_3d282b4ad0ca31e2, ns02_t30_occ_6491a19059d9ec6c, ns02_t30_occ_6870f1ec5d1048be, ns02_t30_occ_6b198842cf80755a, ns02_t30_occ_6cd0e0bd57166a21, ns02_t30_occ_6d2b87d81881062e, ns02_t30_occ_6ff83cb834d7176d, ns02_t30_occ_7213df41458cf67d, ns02_t30_occ_76d9fbbac37b50a6, ns02_t30_occ_7745e52b12c07f1c, ns02_t30_occ_7a3640d70206502d, ns02_t30_occ_86fb71b6c845c94f, ns02_t30_occ_97d3e4a3c0388529, ns02_t30_occ_99e77539490b01ad, ns02_t30_occ_9fe0bbfe8ab9bb7d, ns02_t30_occ_a88a58ab2685ee6e, ns02_t30_occ_a9673677adb3ef8a, ns02_t30_occ_ab0f8aac8f21f0db, ns02_t30_occ_ab6b62516df0a0f1, ns02_t30_occ_b52cbf88aff2c105, ns02_t30_occ_be4e0eb69d196ff7, ns02_t30_occ_becffa9c7cb6d886, ns02_t30_occ_c7f5c80f4b2e7a9c, ns02_t30_occ_c8af30bbe2f10e8a, ns02_t30_occ_cdf02c368ebec0a7, ns02_t30_occ_d2ef6aeae1113c9c, ns02_t30_occ_db819651b1640db8, ns02_t30_occ_dc67ef1afb1051ef, ns02_t30_occ_e3fefccd3e77fd5a, ns02_t30_occ_e48b0cd43634c242, ns02_t30_occ_e855cd5fb843f9bf, ns02_t30_occ_e95d9ae85fb2fba0, ns02_t30_occ_eb221be0020f7038, ns02_t30_occ_ee055856e18cd3f4, ns02_t30_occ_f9fff3f413f6c43c` |
| 200 | `ns02_t30_occ_db819651b1640db8` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_dc67ef1afb1051ef` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_e3fefccd3e77fd5a` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_e48b0cd43634c242` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_e7027bc57e1dc7a7` | `dependency_blocked` | `ns02_t30_occ_04343acd916afae4, ns02_t30_occ_101f0195f0c5cf37, ns02_t30_occ_1842382e6647f17d, ns02_t30_occ_1977687ea7bce884, ns02_t30_occ_23259d462e4ca0f3, ns02_t30_occ_2c030a28f8631544, ns02_t30_occ_3139481aee5c01e0, ns02_t30_occ_3caf2ad00e1b6285, ns02_t30_occ_3d282b4ad0ca31e2, ns02_t30_occ_6491a19059d9ec6c, ns02_t30_occ_6870f1ec5d1048be, ns02_t30_occ_6b198842cf80755a, ns02_t30_occ_6cd0e0bd57166a21, ns02_t30_occ_6d2b87d81881062e, ns02_t30_occ_6ff83cb834d7176d, ns02_t30_occ_7213df41458cf67d, ns02_t30_occ_76d9fbbac37b50a6, ns02_t30_occ_7745e52b12c07f1c, ns02_t30_occ_7a3640d70206502d, ns02_t30_occ_86fb71b6c845c94f, ns02_t30_occ_97d3e4a3c0388529, ns02_t30_occ_99e77539490b01ad, ns02_t30_occ_9fe0bbfe8ab9bb7d, ns02_t30_occ_a88a58ab2685ee6e, ns02_t30_occ_a9673677adb3ef8a, ns02_t30_occ_ab0f8aac8f21f0db, ns02_t30_occ_ab6b62516df0a0f1, ns02_t30_occ_b52cbf88aff2c105, ns02_t30_occ_be4e0eb69d196ff7, ns02_t30_occ_becffa9c7cb6d886, ns02_t30_occ_c7f5c80f4b2e7a9c, ns02_t30_occ_c8af30bbe2f10e8a, ns02_t30_occ_cdf02c368ebec0a7, ns02_t30_occ_d2ef6aeae1113c9c, ns02_t30_occ_db819651b1640db8, ns02_t30_occ_dc67ef1afb1051ef, ns02_t30_occ_e3fefccd3e77fd5a, ns02_t30_occ_e48b0cd43634c242, ns02_t30_occ_e855cd5fb843f9bf, ns02_t30_occ_e95d9ae85fb2fba0, ns02_t30_occ_eb221be0020f7038, ns02_t30_occ_ee055856e18cd3f4, ns02_t30_occ_f9fff3f413f6c43c` |
| 200 | `ns02_t30_occ_e855cd5fb843f9bf` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_e95d9ae85fb2fba0` | `evidence_required` | `none` |
| 200 | `ns02_t30_occ_eb221be0020f7038` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_ee055856e18cd3f4` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_f9fff3f413f6c43c` | `blocked_external` | `none` |
| 200 | `ns02_t30_occ_fc4fc2c77ab26f2d` | `dependency_blocked` | `ns02_t30_occ_04343acd916afae4, ns02_t30_occ_1977687ea7bce884, ns02_t30_occ_23259d462e4ca0f3, ns02_t30_occ_2c030a28f8631544, ns02_t30_occ_3caf2ad00e1b6285, ns02_t30_occ_6870f1ec5d1048be, ns02_t30_occ_6cd0e0bd57166a21, ns02_t30_occ_86fb71b6c845c94f, ns02_t30_occ_becffa9c7cb6d886, ns02_t30_occ_d2ef6aeae1113c9c` |
| 120 | `ns02_t30_wo_554708d47fac02bc` | `pending` | `ns02_t30_occ_07e49c037427403b, ns02_t30_occ_3b0dd1527f9e0144, ns02_t30_occ_7213df41458cf67d, ns02_t30_occ_8e3768557d6f2dde, ns02_t30_occ_ab6b62516df0a0f1, ns02_t30_occ_ae4ebd1d82c2bd03, ns02_t30_occ_be4e0eb69d196ff7, ns02_t30_occ_c03007a138e83e9b, ns02_t30_occ_d19d9b744d7aff4a, ns02_t30_occ_d705e67d4c161924, ns02_t30_occ_e7027bc57e1dc7a7` |
| 120 | `ns02_t30_wo_bc7d70d0bd2786f8` | `pending` | `ns02_t30_occ_2b0567ebbd443da5, ns02_t30_occ_3139481aee5c01e0, ns02_t30_occ_4177e7d48f374473, ns02_t30_occ_6491a19059d9ec6c, ns02_t30_occ_97d3e4a3c0388529, ns02_t30_occ_99e77539490b01ad, ns02_t30_occ_a9673677adb3ef8a, ns02_t30_occ_b52cbf88aff2c105, ns02_t30_occ_b7467ff5401814aa, ns02_t30_occ_c7f5c80f4b2e7a9c, ns02_t30_occ_dc67ef1afb1051ef, ns02_t30_occ_e95d9ae85fb2fba0, ns02_t30_occ_eb221be0020f7038` |
| 120 | `ns02_t30_wo_db304e8553027647` | `pending` | `ns02_t30_occ_1842382e6647f17d, ns02_t30_occ_1a742ef3d6224c6a, ns02_t30_occ_2a2ab71eced6e937, ns02_t30_occ_6b198842cf80755a, ns02_t30_occ_6ff83cb834d7176d, ns02_t30_occ_7745e52b12c07f1c, ns02_t30_occ_7a3640d70206502d, ns02_t30_occ_a88a58ab2685ee6e, ns02_t30_occ_b531d3c48931ba58, ns02_t30_occ_db819651b1640db8, ns02_t30_occ_e48b0cd43634c242, ns02_t30_occ_e855cd5fb843f9bf, ns02_t30_occ_f9fff3f413f6c43c` |
| 120 | `ns02_t30_wo_e205ce3a49c56b7e` | `pending` | `ns02_t30_occ_04343acd916afae4, ns02_t30_occ_139f375db9714f27, ns02_t30_occ_1977687ea7bce884, ns02_t30_occ_23259d462e4ca0f3, ns02_t30_occ_2c030a28f8631544, ns02_t30_occ_3caf2ad00e1b6285, ns02_t30_occ_6870f1ec5d1048be, ns02_t30_occ_6cd0e0bd57166a21, ns02_t30_occ_86fb71b6c845c94f, ns02_t30_occ_950802f6c70d5036, ns02_t30_occ_becffa9c7cb6d886, ns02_t30_occ_d2ef6aeae1113c9c, ns02_t30_occ_fc4fc2c77ab26f2d` |
| 120 | `ns02_t30_wo_f9d03098e6d0feba` | `pending` | `ns02_t30_occ_101f0195f0c5cf37, ns02_t30_occ_10e1e793011ee907, ns02_t30_occ_3d282b4ad0ca31e2, ns02_t30_occ_60f5539e2d72463f, ns02_t30_occ_6d2b87d81881062e, ns02_t30_occ_6e5fb996533eab2b, ns02_t30_occ_76d9fbbac37b50a6, ns02_t30_occ_9fe0bbfe8ab9bb7d, ns02_t30_occ_ab0f8aac8f21f0db, ns02_t30_occ_c8af30bbe2f10e8a, ns02_t30_occ_cdf02c368ebec0a7, ns02_t30_occ_e3fefccd3e77fd5a, ns02_t30_occ_ee055856e18cd3f4` |
| 100 | `ns02_t30_wo_fba4b40642ae1dd4` | `pending` | `ns02_t30_wo_554708d47fac02bc, ns02_t30_wo_bc7d70d0bd2786f8, ns02_t30_wo_db304e8553027647, ns02_t30_wo_e205ce3a49c56b7e, ns02_t30_wo_f9d03098e6d0feba` |

## 9. Human decisions required

- Review exact allowed_paths and acceptance commands for 8 pointer occurrences.
- Acquire and review evidence for evidence-required occurrences through evidence-ingest.
- Complete analyst and exact-hash human gates without auto-acceptance.
