---
schema_version: "1"
task_id: "v1_governance_integration_cleanup_v5"
contract_path: "docs/codex_tasks/v1_governance_integration_cleanup_v5/CONTRACT.md"
contract_sha256: "7a02675ea94dd9ef83f40df42889720998cbea0d8db26992d158bf3c78135ef4"
state: "running"
execution_branch: "codex/v1-governance-integration-cleanup"
source_baseline: "f1dafeb32b08d24a6960f31d4a0f6d8820b95839"
last_completed_phase: "P4"
next_phase: "P5"
last_validation: "pass"
updated_at: "2026-07-26T15:10:00+08:00"
---
# Start or resume this stage in a new Codex chat

本任务包是冻结 v4 的 authorized amended v5。它只新增 A.7 `transition_modify_then_delete_exact` 三路径权限：三个 Night CI tests 可先把旧路由/history-guard 正向要求改为等强退休断言，随后仍必须完整留在 Night actual manifest，由用户在 Night wave 手工删除。A.1–A.6 数量、历史 snapshot `312adc...`、P1–P4 结论、P1–P5 数量、完成标准、发布模式 A、Night → Bundle11R–17R → old 002837 三个有序手动删除检查点和全部验证强度保持不变。只有 front matter 为 `state: ready`、启动块包含真实 contract hash 且 `--require-ready` 校验通过时才可启动。

最终 ready 后，在专用工作树 `C:\Projects\03_Investment_System_v1_governance_cleanup` 打开一个全新 Codex 聊天，并原样粘贴：

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/v1_governance_integration_cleanup_v5
Frozen contract: docs/codex_tasks/v1_governance_integration_cleanup_v5/CONTRACT.md
Expected contract SHA-256: 7a02675ea94dd9ef83f40df42889720998cbea0d8db26992d158bf3c78135ef4
Execution branch: codex/v1-governance-integration-cleanup
Source baseline: f1dafeb32b08d24a6960f31d4a0f6d8820b95839
Historical cleanup snapshot: 312adc73821706b0b7ca6aa00e80ee608bd10b32
Engineering source candidate: f60f220ae252262a537c612ce193fc779901984b
Dedicated worktree: C:\Projects\03_Investment_System_v1_governance_cleanup

Read the complete applicable AGENTS.md instruction chain, CONTRACT.md, START_HERE.md, and every phase-required skill file before acting. Treat the frozen contract as the complete objective, constraints, authority, and definition of done. Do not rely on any previous chat, memory, project journal, Night queue, or unstated decision.

Validate package integrity and repository preflight, then resume from the earliest phase whose postconditions are not proven. After each phase, run its validators, inspect scope, update START_HERE.md, and create the specified Git checkpoint. Continue through P1-P5 until every completion criterion passes or a contract hard stop occurs.

Never edit the frozen contract, add phases, weaken a criterion, fabricate data or reviewer decisions, touch the user's dirty main worktree, perform recursive/bulk deletion, direct-push main, or publish beyond the authorization envelope. In P5, stop in order at the Night, Bundle, and old-002837 deletion waves with the exact per-file manifest; wait for the user to delete only that wave manually, then verify the complete Git status vector before continuing.
```

## Current checkpoint

- **State:** `running`
- **Last completed phase:** `P4`
- **Next phase:** `P5`
- **Latest validation:** `pass`。v5 setup checkpoint `ce4f9554db4fcdfa4699c70516d9a3497c565fc7` 已完成。P5 删除前 V-002/V-003/V-004/V-005/V-006/V-008/V-009/V-010 和 package integrity 全部通过；full pytest 为 `1349 passed, 2 skipped`，两项 skip 与 `f60f220...` 完全相同。独立只读质量审计无阻断。
- **Current blocker:** none。v4 的三测试权限冲突已由 A.7 等强退休断言转换解决；活动物理引用与未知分类均为 0。尚未 arm 或删除任何 wave。
- **Prior hard-stop evidence:** v4 checkpoints `0f58259983d47a34ec04d0ae16b419ea81b913ba` 与 `f1dafeb32b08d24a6960f31d4a0f6d8820b95839` 保留历史冲突证据；v5 已修复该冲突以及 A.2 retained-dependency/unknown-classification 缺陷。当前 manifests 和 restore receipt 是通过验证的 P5 删除前证据，不再是 diagnostic-only。
- **User-main protection snapshot:** HEAD `a345fafb522300831ed4206d35fa17f44570cb1f`；批准的新完整 `porcelain=v1 -z -uall` 向量为 130 records、9156 bytes、SHA-256 `1b21ac246cb2ad4b055f5a264503fb1fad8fe9edae153e25c9cd6d19d4a719c0`，tracked-only 为 20 records、1025 bytes、SHA-256 `3ab441f68037823866029eb2136149a807f6382755966daf96d33a85b965609b`。v5 准备时两份草稿曾误落该树，已按明确单文件逐一撤销，HEAD 与两组向量随后精确恢复；不得再写入、清理、修复、吸收或提交其中内容。
- **Next safe action:** 只 stage 当前 A.1/A.2/A.7 精确授权路径，创建 `refactor(v1): decouple active runtime from legacy history`；确认 checkpoint clean 后，把 680 个 Night exact absolute paths 写入本文件，创建 clean Night arm checkpoint 并停止，等待用户只手工删除该波。

### P5 pre-delete completion evidence

- A.7 exact paths: `tests/test_r5_night_shift_ci_contract.py`, `tests/test_r5_night_shift_night03_ci_contract.py`, `tests/test_r5_night_shift_night04_ci_contract.py`; each now contains equal-strength CI retirement assertions and remains in the Night manifest.
- Historical cleanup inventory: 1,386 files / 9,787,412 content bytes / 121,264 path-vector bytes / SHA-256 `974d45610144d616f69c3c368d9ea1a0a27d66601a24f748aa8148e2ee702f33`.
- Wave aggregates: Night 680 / 4,480,614 / `1ec2f42b84c1078f6b26caa377e9c1fb3efff9221196bc2e02bd819588a59c59`; Bundle 205 / 1,770,109 / `fc8912dfe6d20d92bd8fe907d4400ae90b724826a7c468ba5286232dc3b3363a`; old002837 501 / 3,536,689 / `73d0a405b928fa3fa615d5b0d527f16f7c1182bb16239fb9ef89266d9868862f`.
- Reference graph: `reference_count=0`, `unknown_classification_count=0`, A.7 overlap exact and all Night, retained/protected overlap 0.
- Restore proof: all 1,386 Git blobs recovered byte-for-byte; final root `C:\Users\Q\AppData\Local\Temp\r5_v1_historical_restore_final_a5b1d2db3a3b4eb78631eba15a2ef2a8`; `cat_file_e_verified`, `content_hash_verified`, `full_restore_verified` and `byte_for_byte_match` all true.
- Focused validators: V-003 194 passed; V-004 16 passed with equal digests; V-005 18 passed; V-006 21 passed; A.7 4 passed; source route `decision=pass`, blocking 0.
- Full repository pytest: `1349 passed, 2 skipped in 650.20s`; no failures/errors and no new skip/xfail/mock/collection-ignore.
- Scope: only A.1/A.2/A.7 paths changed; no deletion, untracked path, frozen-contract change, raw-data change or user-main write.

### P5 initial planned mutation paths

本清单只授权初始 decoupling iteration，不以 wildcard 或 family 替代实际路径。其他既有 A.1 文件即使合同允许，也必须先由 reference scan 证明需要修改，并先逐项加入本检查点后才能写入。

新增或继续维护的 A.2 路径：

- `scripts/manage_r5_v1_historical_cleanup.py`
- `reports/p1_6/r5_v1_governance_cleanup/historical_baseline_manifest.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/historical_cleanup_manifest.yaml`
- `tests/test_r5_v1_historical_baseline_manifest.py`
- `tests/test_r5_v1_historical_cleanup_manifest.py`
- `tests/test_r5_v1_active_routing_retirement.py`
- `reports/p1_6/r5_v1_governance_cleanup/validation/historical_decoupling.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/validation/manual_deletion_wave_night.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/validation/manual_deletion_wave_bundle.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/validation/manual_deletion_wave_old002837.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/validation/clean_checkout_smoke.txt`
- `reports/p1_6/r5_v1_governance_cleanup/validation/full_pytest.txt`
- `docs/codex_tasks/v1_governance_integration_cleanup_v5/START_HERE.md`

A.7 `transition_modify_then_delete_exact` 三路径：

- `tests/test_r5_night_shift_ci_contract.py`
- `tests/test_r5_night_shift_night03_ci_contract.py`
- `tests/test_r5_night_shift_night04_ci_contract.py`

三者仅改为等强 CI retirement assertions，仍必须进入 Night actual manifest，并在 Night wave 由用户手工删除。

首轮高置信既有物理解耦路径：

- `.github/workflows/ci.yml`
- `.github/workflows/r5_bundle11r_runtime.yml`
- `.gitattributes`
- `config/r5_readout_canonical_index.yaml`
- `config/a_stock_data_capability_catalog.yaml`
- `config/adapter_contract_registry.yaml`
- `scripts/run_r5_v1_replay_002837.py`
- `tests/conftest.py`
- `tests/test_r5_v1_active_control_plane.py`
- `tests/test_r5_v1_blocker_root_cause_map.py`
- `tests/test_r5_v1_replay_002837.py`
- `tests/test_r5_v1_workflow_state_validator.py`
- `tests/test_valuation_input_contract.py`

P5 readout 与 validator receipt 路径：

- `reports/p1_6/r5_v1_governance_cleanup/governance_cleanup_readout.md`
- `reports/p1_6/r5_v1_governance_cleanup/validation/preflight.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/validation/doc_drift.txt`
- `reports/p1_6/r5_v1_governance_cleanup/validation/governance_targeted.txt`
- `reports/p1_6/r5_v1_governance_cleanup/validation/refresh_002837.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/validation/blocker_root_reconciliation.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/validation/source_route_quality_report.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/validation/scope_audit.yaml`

### P5 reference-scan expanded exact mutation paths

活动根反向扫描已证明 A.1 中全部 46 个保留代码路径都需要 D-017 最小物理解耦：41 个直接包含固定旧 workflow ID；其余 5 个通过 A.4 配置中的 `default_paths` 或 `required_inputs` 间接解析旧目录。`scripts/run_r5_v1_replay_002837.py` 已列于首轮清单；以下是其余逐路径代码 mutation set：

- `scripts/build_evidence_generation_lock.py`
- `scripts/build_r5_analysis_pack_v2.py`
- `scripts/build_r5_bundle10_reader_pack.py`
- `scripts/build_r5_bundle5_benchmark_coverage_precheck.py`
- `scripts/build_r5_bundle5_forecast_valuation_onboarding.py`
- `scripts/build_r5_bundle5_market_peer_onboarding.py`
- `scripts/build_r5_bundle5_official_disclosure_onboarding.py`
- `scripts/build_r5_bundle6_close_readout.py`
- `scripts/build_r5_bundle6_human_review_handoff.py`
- `scripts/build_r5_bundle6_reader_baseline.py`
- `scripts/build_r5_bundle6_research_remediation.py`
- `scripts/build_r5_bundle8_research_depth_plan.py`
- `scripts/build_r5_bundle8r_pilot_artifacts.py`
- `scripts/build_r5_bundle9_forecast.py`
- `scripts/build_r5_bundle9_valuation.py`
- `scripts/build_r5_bundle9r_forecast_valuation.py`
- `scripts/build_r5_evidence_coverage_matrix.py`
- `scripts/build_r5_reader_section_payloads.py`
- `scripts/build_r5_reviewed_input_staging.py`
- `scripts/close_r5_bundle8b.py`
- `scripts/close_r5_bundle9.py`
- `scripts/promote_r5_reviewed_inputs_to_registries.py`
- `scripts/r5_next_pilot_gate.py`
- `scripts/r5_pack_promotion_gate.py`
- `scripts/r5_readiness_gate.py`
- `scripts/r5_reviewed_input_pilot_gate.py`
- `scripts/render_r5_reviewed_input_output.py`
- `scripts/run_r5_bundle10_cross_industry_writer_regression.py`
- `scripts/run_r5_bundle5_real_registry_promotion.py`
- `scripts/run_r5_bundle5_research_draft_quality_gate.py`
- `scripts/run_r5_bundle8_research_depth_gate.py`
- `scripts/run_r5_reader_quality_gate.py`
- `scripts/sync_r5_bundle10_external_review_pending.py`
- `scripts/validate_r5_bundle10_close.py`
- `scripts/validate_r5_bundle10_human_review_submission.py`
- `scripts/validate_r5_bundle8b_close.py`
- `scripts/validate_r5_bundle9_close.py`
- `src/ingest/adapters/adapter_runtime.py`
- `src/ingest/adapters/eastmoney_report_pdf_adapter.py`
- `src/ingest/business_segment_extraction.py`
- `src/ingest/official_financial_reconciliation.py`
- `src/qa/r4_disclosure_backflow_review.py`
- `src/qa/r4_publishable_stock_report_gate.py`
- `src/report/r5_section_payload_builder.py`
- `src/research/r5_bundle13r_evidence_backflow.py`

同一扫描证明 A.1 的 60 个保留测试中有 58 个会物理读取候选目录或依赖旧默认输入；首轮清单已包含其中 6 个。下列其余 52 个测试路径进入 exact mutation set；`tests/test_r5_bundle4_close.py` 与 `tests/test_r5_bundle5_status_baseline.py` 仅检查 A.4 metadata，保持只读：

- `tests/test_build_r5_evidence_plan_from_gaps.py`
- `tests/test_build_r5_evidence_request_queue.py`
- `tests/test_business_segment_extraction.py`
- `tests/test_data_layer_bridge_draft.py`
- `tests/test_liquid_cooling_exposure_evidence_review.py`
- `tests/test_official_reconciliation_review_decision.py`
- `tests/test_r4_artifact_formatting.py`
- `tests/test_r4_publishable_stock_report_gate.py`
- `tests/test_r4_stock_report_v0_2_gate.py`
- `tests/test_r5_002837_reviewed_input_dry_run.py`
- `tests/test_r5_002837_reviewed_input_staging.py`
- `tests/test_r5_after_patch55_close.py`
- `tests/test_r5_bundle10_close.py`
- `tests/test_r5_bundle10_dynamic_writer.py`
- `tests/test_r5_bundle10_human_review_finalize.py`
- `tests/test_r5_bundle10_human_review_handoff.py`
- `tests/test_r5_bundle10_human_review_submission.py`
- `tests/test_r5_bundle10_state_sync.py`
- `tests/test_r5_bundle10r_v5_artifacts.py`
- `tests/test_r5_bundle10r_v5_human_review.py`
- `tests/test_r5_bundle13r_evidence_backflow.py`
- `tests/test_r5_bundle4_post_promotion_dry_run.py`
- `tests/test_r5_bundle4_registry_promotion.py`
- `tests/test_r5_bundle4_reviewed_input_smoke.py`
- `tests/test_r5_bundle5_benchmark_coverage_precheck.py`
- `tests/test_r5_bundle5_close.py`
- `tests/test_r5_bundle5_real_input_inventory.py`
- `tests/test_r5_bundle5_real_pilot_gate.py`
- `tests/test_r5_bundle5_real_registry_promotion.py`
- `tests/test_r5_bundle6_close.py`
- `tests/test_r5_bundle6_human_review_handoff.py`
- `tests/test_r5_bundle6_reader_baseline.py`
- `tests/test_r5_bundle6_research_remediation.py`
- `tests/test_r5_bundle7_close.py`
- `tests/test_r5_bundle8b_local_close.py`
- `tests/test_r5_bundle9_close.py`
- `tests/test_r5_bundle9_forecast.py`
- `tests/test_r5_bundle9_valuation.py`
- `tests/test_r5_composer_research_draft_plus.py`
- `tests/test_r5_forecast_valuation_interlock.py`
- `tests/test_r5_pilot_gate_recheck_and_render.py`
- `tests/test_r5_quality_backflow.py`
- `tests/test_r5_reader_quality_gate.py`
- `tests/test_r5_reader_report_writer.py`
- `tests/test_r5_report_composer_degradation.py`
- `tests/test_r5_reviewed_input_registry_promotion.py`
- `tests/test_r5_source_gapped_002837_pack.py`
- `tests/test_segment_exposure_gate.py`
- `tests/test_segment_stock_backflow_review.py`
- `tests/test_validate_r5_forecast_assumption_registry.py`
- `tests/test_validate_r5_market_peer_input_registry.py`
- `tests/test_validate_r5_market_peer_inputs.py`

### P4 completion scope

- `reports/p1_6/r5_v1_governance_cleanup/root_policy_migration.yaml`
- `schemas/r5_v1_root_policy_migration.schema.json`
- `scripts/validate_r5_v1_root_policy_migration.py`
- `tests/test_r5_v1_root_policy_migration.py`
- `reports/p1_6/r5_v1_governance_cleanup/validation/blocker_root_reconciliation.yaml`
- `config/r5_readout_canonical_index.yaml`
- `reports/p1_6/r5_v1_governance_cleanup/governance_cleanup_readout.md`
- `reports/p1_6/r5_v1_governance_cleanup/validation/scope_audit.yaml`
- `docs/codex_tasks/v1_governance_integration_cleanup_v2/START_HERE.md`

### P4 completion evidence

- Seven-root migration with no occurrence/candidate overlay: `reports/p1_6/r5_v1_governance_cleanup/root_policy_migration.yaml`.
- Strict schema, dynamic validator and adversarial tests: `schemas/r5_v1_root_policy_migration.schema.json`, `scripts/validate_r5_v1_root_policy_migration.py`, `tests/test_r5_v1_root_policy_migration.py`.
- Dynamic 63/20/6/69/43/0, 532-edge, six-duplicate reconciliation and zero active defects: `reports/p1_6/r5_v1_governance_cleanup/validation/blocker_root_reconciliation.yaml`.
- Active pointer: `config/r5_readout_canonical_index.yaml` → `policy_migrations.blocker_root_policy`.
- V-009, unchanged protected root map and user-main vector: `reports/p1_6/r5_v1_governance_cleanup/validation/scope_audit.yaml`.
- Required P5 follow-up: before Night/Bundle deletion, decouple `tests/test_r5_v1_blocker_root_cause_map.py` from physical historical paths while preserving V-005 behavior through durable baseline/blob reads.

### P3 completion scope

- Runner and tests: `scripts/run_r5_v1_policy_refresh_002837.py`, `tests/test_r5_v1_policy_refresh_002837.py`.
- Canonical pointer: `config/r5_readout_canonical_index.yaml`.
- New run control plane: `reports/workflow_runs/wf_20260725_stock_first_002837_v1_policy_refresh/workflow_state.yaml`, `artifact_manifest.csv`, `open_todos.csv`, `quality_gate_report.md`, `run_log.md`, `workflow_readout.md`.
- New run evidence/research: `reports/workflow_runs/wf_20260725_stock_first_002837_v1_policy_refresh/inputs/input_provenance.csv`, `research/disclosed_facts.yaml`, `research/limitations.yaml`, `research/issue_change_log.csv`, `research/stock_research_pack.yaml`, `research/segment_exposure.yaml`, `research/stock_report_draft.md`, `research/backflow_decision.yaml`.
- New run validation: `reports/workflow_runs/wf_20260725_stock_first_002837_v1_policy_refresh/validation/artifact_hashes.csv`, `replay_receipt.yaml`, `idempotence_report.yaml`.
- Phase evidence/checkpoint: `reports/p1_6/r5_v1_governance_cleanup/governance_cleanup_readout.md`, `validation/refresh_002837.yaml`, `validation/governance_targeted.txt`, `validation/source_route_quality_report.yaml`, `validation/scope_audit.yaml`, and this `START_HERE.md`.

### P3 completion evidence

- Canonical state and six-piece control plane: `reports/workflow_runs/wf_20260725_stock_first_002837_v1_policy_refresh/`.
- Fixed official provenance, page locators, facts and visible limitations: new run `inputs/` and `research/` artifacts.
- Two-pass and two-directory replay: new run `validation/` plus `reports/p1_6/r5_v1_governance_cleanup/validation/refresh_002837.yaml`.
- V-003 P3: `reports/p1_6/r5_v1_governance_cleanup/validation/governance_targeted.txt`.
- V-008: `reports/p1_6/r5_v1_governance_cleanup/validation/source_route_quality_report.yaml`.
- V-009 and unchanged protected assets: `reports/p1_6/r5_v1_governance_cleanup/validation/scope_audit.yaml`.

### P2 completion scope

- Permanent workflow/policy/meta docs: `docs/workflows/RESEARCH_WORKFLOW.md`, `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md`, `docs/workflows/R5_SAMPLE_QUALITY_STOCK_REPORT_SPEC.md`, `docs/workflows/R5_REAL_COMPANY_REGRESSION_CONTRACT.md`, `docs/policies/QUALITY_GUARDRAILS.md`, `docs/meta/DOC_OWNERSHIP_MATRIX.md`.
- Active skills/references: `.agents/skills/research-orchestrator/SKILL.md`, `.agents/skills/research-orchestrator/references/workflow_state_schema.md`, `.agents/skills/research-orchestrator/assets/workflow_state_template.yaml`, `.agents/skills/research-orchestrator/scripts/validate_workflow_state.py`, `.agents/skills/quality-review/SKILL.md`, `.agents/skills/quality-review/references/r5_quality_gate.md`, `.agents/skills/stock-deep-dive/SKILL.md`, `.agents/skills/stock-deep-dive/references/r5_stock_research_pack_contract.md`, `.agents/skills/stock-deep-dive/references/report_production_profile.md`.
- New schema and tests: `schemas/r5_final_report_review.schema.json`, `tests/test_r5_v1_active_control_plane.py`, `tests/test_r5_v1_completion_semantics.py`, `tests/test_r5_v1_workflow_state_validator.py`, `tests/test_r5_final_report_review_semantics.py`.
- P2 evidence/checkpoint: `reports/p1_6/r5_v1_governance_cleanup/governance_cleanup_readout.md`, files under `reports/p1_6/r5_v1_governance_cleanup/validation/`, and this `START_HERE.md`.

### P2 completion evidence

- Unique final-report human boundary and current-byte binding: `schemas/r5_final_report_review.schema.json`, workflow-state template/schema/validator, and permanent workflow/policy documents.
- Machine-vs-human truth separation and `changes_requested` routing: active orchestrator, quality-review, and stock-deep-dive skills/references.
- V-002: `reports/p1_6/r5_v1_governance_cleanup/validation/doc_drift.txt`.
- V-003 P2 and compatibility regression: `reports/p1_6/r5_v1_governance_cleanup/validation/governance_targeted.txt`.
- Human-boundary and adversarial audit: `reports/p1_6/r5_v1_governance_cleanup/validation/final_report_review_audit.yaml`.
- V-009 and unchanged user-main vector: `reports/p1_6/r5_v1_governance_cleanup/validation/scope_audit.yaml`.

### P1 completion evidence

- Canonical fields and outcome derivation: `decision_semantics_version: current_goal_v1`, `impact_scope`, `active_disposition`, `affected_capabilities`, `blocks_current_goal`.
- Degradation ladder: direct disclosure → audited aggregate → bounded estimate/scenario → unknown/omit.
- Bundle11R–16R and R5-G1–R5-G11: removed from ordinary routing; retained evaluators require explicit inputs and cannot write canonical state.
- V-002: `reports/p1_6/r5_v1_governance_cleanup/validation/doc_drift.txt`.
- V-003 P1: `reports/p1_6/r5_v1_governance_cleanup/validation/governance_targeted.txt`.
- Active routing: `reports/p1_6/r5_v1_governance_cleanup/validation/active_routing_audit.yaml`.
- V-009: `reports/p1_6/r5_v1_governance_cleanup/validation/scope_audit.yaml`.

The Git commit containing this file is the checkpoint commit. Do not write that commit's own hash into this file.

## Checkpoint history

- 2026-07-25T11:57:27+08:00 — prior package `docs/codex_tasks/v1_governance_integration_cleanup/` 在 P1 前因 V-003 阶段依赖冲突硬停止；其 frozen hash 为 `a681812f9e91993d4a009ebcd972df1b06fc3f808323574387b84afa2ca3353e`，blocker checkpoint 为 `23fcd3b6b5ce3574661c4cfd306dadd782ad0717`。
- 2026-07-25T12:55:36+08:00 — 用户授权 amended v2；新包只拆分 V-003 为 P1 七项、P2 八项、P3/final 九项，并把 package baseline 固定为 amendment 前 checkpoint。旧包、工程目标、P1–P5、完成标准、发布与删除授权保持不变；尚未 finalize。
- 2026-07-25T13:10:43+08:00 — amended v2 已冻结并通过 `--require-ready`；contract SHA-256 为 `c160ea2d676d5ba9a9893070be1a6e4418193cc508db07e71dd48cd0394a642f`，setup checkpoint 为 `f41d99dc3685da6b1317da58b73beb23fc95135c`。V-001、用户主工作树只读快照与 P1 baseline 七项测试（61 passed）通过，开始 P1。
- 2026-07-25T13:25:09+08:00 — P1 scope-aware blocker/outcome、降级阶梯和 explicit capability-evaluator routing 已实现；V-002、V-003 P1（90 passed）、额外兼容测试（63 passed）、V-009 和 task-package integrity 通过，等待指定 P1 checkpoint。
- 2026-07-25T13:31:22+08:00 — P1 指定 checkpoint `0906a5fa8c785da1a74326aa19dbf0abc58ddd2e` 已创建且工作树 clean；完整读取 P2 点名的人审、sample-quality、real-company regression、Reader 与 generation-lock 契约/测试后，按上述精确路径开始 P2。
- 2026-07-25T14:23:39+08:00 — P2 最终报告唯一人审边界、当前字节 hash 失效、truth 分离、`changes_requested` 路由与历史 review 只读兼容已实现；V-002、V-003 P2（178 passed）、兼容回归（75 passed）、对抗复核、V-009 和 task-package integrity 通过，等待指定 P2 checkpoint。
- 2026-07-25T14:33:04+08:00 — P2 指定 checkpoint `aa73859ddf8dbef2ad94b8c72dbf0ffc3931b851` 已创建且工作树 clean；P3 点名的四个 skills 及其适用必读 references、旧 replay 实现/测试和固定官方输入已完整读取，按上述精确路径开始 P3。
- 2026-07-25T15:30:31+08:00 — P3 独立 002837 policy refresh 已生成 17 件 canonical 产物；正式披露 hash/page、四 issue 动态处置、unknown 非数值使用、毛利率与未披露毛利贡献字段语义隔离、双临时目录重放、V-003 P3（194 passed）、V-004（16 passed）、V-008 和 V-009 均通过，等待指定 P3 checkpoint。
- 2026-07-25T15:37:32+08:00 — P3 指定 checkpoint `6c7fc2a35942bb04f5ef0ecfa2c6ccbd10e0a069` 已创建且工作树 clean；原 root map 与 engineering source 的 Git blob 相同（worktree SHA-256 `39aadff44cf51d1ad5607d8ec8481bbab42650723eaf5a981415df0ee3facacf`），7 roots、63 occurrence、20 dependency-blocked、6 parent、69 carry-forward、43 candidate-ready、0 historical resolved 和 532 dependency edges 已完整读取，V-005 既有基线 7 passed，按上述 9 条精确路径开始 P4。
- 2026-07-25T15:55:38+08:00 — P4 七 root 活动处置迁移已实现：1 `policy_retired`、1 `not_required_for_active_v1`、1 `report_limitation`、1 visible unused `unknown`、3 open `historical_backlog`、0 `active_defect`；动态证明 63/20/6/69/43/0、532 edges、6 duplicate references，未复制 occurrence/candidate 决定或声称历史 resolution/system completion。V-005（18 passed）、额外索引兼容回归（27 passed）、对抗复核、V-009 和 task-package integrity 通过，等待指定 P4 checkpoint。
- 2026-07-25T16:34:47+08:00 — P4 指定 checkpoint `3741c807ae1d9859e8cb72d5e587a5bb74f2082e` 已创建且 clean。P5 三种实质不同方法（retain 分类、静态引用图、filtered-tree full-pytest 诊断）均指向同一授权冲突：冻结 exact mutation set 不允许修改删除后必然失败的既有 tests/scripts/fixtures。诊断造成的 12 个本地 fixture commits、索引和共享 Git 配置副作用已完整恢复，专用树 clean，用户主工作树完整状态向量与 preflight 逐字节相同，远端未写入。P5 在任何删除 arm 前硬停止，等待 amended v3。
- 2026-07-25T21:30:00+08:00 — 用户明确授权 amended v3，并补充“允许所有操作”“继续”。专用树仍位于 clean blocker checkpoint `1c4040edced3fa0829fb68f36bc156aeac223870`，远端 refs 未漂移。用户主工作树 HEAD 未变但脏状态由用户外部更新，已连续两次采集新的完整/跟踪 NUL 向量作为只读保护快照。v3 只扩充 Appendix A 的 P5 精确路径权限和 Bundle action/test 命名边界；旧 v1/v2 合同、P1–P4、全部标准、三波人工删除和发布模式 A 不变。package 仍为 draft，等待 finalize。
- 2026-07-26T03:01:18+00:00 — state=blocked; completed=P4; next=P5; validation=fail; Post-freeze audit proved that eight existing P5 readout and validation paths were described in prose but omitted from modify_existing_exact; P5 did not start and no deletion wave was armed; prepare amended v4 without editing frozen v3.
- 2026-07-26T10:42:00+08:00 — v3 frozen package 和 blocker 状态以 package-only checkpoint `312adc73821706b0b7ca6aa00e80ee608bd10b32` 保存；该 commit 仅新增 v3 `CONTRACT.md` 与 `START_HERE.md`。工作树恢复 clean，P5 mutation 和 deletion wave 均未开始。
- 2026-07-26T11:11:15+08:00 — 用户再次回复“批准”。v4 draft 以 `312adc73821706b0b7ca6aa00e80ee608bd10b32` 为 source baseline，补齐 A.1 八个既有 readout/validation 路径，并闭合 A.1=120、A.2=13、A.3=44、A.4=35、A.5=27 与 A.6 source-baseline archive inventory 机制；P1–P4、三波用户手工删除边界与发布模式 A 不变。当时 package 仍为 draft，未冻结。
- 2026-07-26T11:23:54+08:00 — 用户主工作树完整状态向量因仅 untracked 的外部变化由 102 records 漂移到 130 records，tracked-only 和 HEAD 均未变。按合同暂停并报告后，用户明确回复“继续，以新快照为基线”；两次连续采样确认新完整向量为 130 records/9156 bytes/SHA-256 `1b21ac246cb2ad4b055f5a264503fb1fad8fe9edae153e25c9cd6d19d4a719c0`，tracked-only 仍为 20 records/1025 bytes/SHA-256 `3ab441f68037823866029eb2136149a807f6382755966daf96d33a85b965609b`。v4 同时闭合 exact amendment disclosure、A6 与两个 Bundle17R direct-child deletion targets 的保护重叠、唯一 A.1/A.5 交集和 116-path ordinal NUL inventory 指纹。
- 2026-07-26T11:27:50+08:00 — 两项独立只读审计均返回 `SAFE TO FREEZE`，并复现 A.1=120、A.2=13、A.3=44、A.4=35、A.5=27、唯一 A.1∩A.5 两路径、A.6 116 paths/8065 bytes/SHA-256 `6c667b2aa0db007d5e89baf5b7bae837fd62249be3d85613f16aba3d14d32e6a`、active old-ID/Bundle unknown=0、新用户主树状态向量及远端 refs。v4 合同已冻结，canonical SHA-256 为 `c806d4811e4f40ffb86154c6144c75173c7d13e1fc193f9add07686495217736`；`--require-ready` 通过，只产生预期的 last_completed=P4 warning。
- 2026-07-26T11:37:24+08:00 — package-only v4 setup checkpoint `63e542ddc8a7329812e8aac15ead871253b58ca6` 已创建且 clean。P1→P4 checkpoint direct ancestry 与产物逐项通过；当前 doc drift pass，V-003 final 九项 `194 passed`，V-005 `18 passed`，V-004 两次 replay semantic digest `2d8487beb46f10b6df103a9a2808998870a19556ef6879959ed15c6eb90cbcc6`、tree digest `3baefe904ef244d272f9432ea661a3e13f2704003bd8d19590232a4d9f78df5f` 且 `16 passed`，V-008 `decision=pass`/blocking=0；原 root map blob `526d9964a95ddc866fa960a1b9556e720ca80178` 与 f60f220 完全一致。最早未证明阶段为 P5，本文件切换为 running，并记录首轮逐路径 mutation set。
- 2026-07-26T12:00:00+08:00 — P5 Group A/B 的授权内解耦补丁完成首轮只读审查和 75 项针对性测试，但 pre-delete full-pytest 复现 `tests/test_r5_night_shift_ci_contract.py` 为 `1 failed, 1 passed`。该只读删除候选要求 CI 保留 Night glob，而 C-008/V-006 要求 CI physical route=0；三种可能规避分别违反 C-008 或 D-017。两项独立审查与诊断工具确认 frozen v4 无授权内解，状态切换为 blocked；未删除、arm、stage、push、PR 或发布。用户主树完整新快照再次逐字节匹配，合同 hash 不变。
- 2026-07-26T12:18:01+08:00 — blocker 后只读全仓冲突扫描把同类自依赖从 1 项纠正为 3 项：除直接 CI contract 外，Night03/Night04 CI contract 也分别经冻结 builder 要求旧 Night glob/history guards，实测另有 `2 failed`。未发现第四项同类权限/顺序冲突；Night05 `.gitattributes` 检查绑定固定 `a96c...` delivery，不依赖当前内容。最小 v5 unblock 因此改为三个 exact transition-modify-then-delete 路径，不能只授权原一项。另记录两个 A.2 诊断工具缺陷；均不扩大合同权限。
- 2026-07-26T12:47:52+08:00 — 用户精确批准 v5：三个 Night CI tests 进入 A.7 `transition_modify_then_delete_exact`，只改为等强退休断言，随后仍在 Night wave 由用户手工删除；其余 v4 标准和三波边界不变。准备预检确认 dedicated HEAD/source baseline=`f1dafeb32b08d24a6960f31d4a0f6d8820b95839`、remote main/Night05/V1 refs 未漂移、execution ref 不存在、P1–P4 与 v4 checkpoints 全部为祖先。两份机械草稿曾误落用户主树，已按明确单文件逐一撤销并复核 full/tracked NUL 向量精确恢复；v5 当前只在专用工作树新增 `CONTRACT.md` 与 `START_HERE.md` draft，等待独立审计、finalize 和 package-only setup checkpoint。
- 2026-07-26T13:05:30+08:00 — 两项独立只读审计分别返回 `SAFE TO FREEZE` 与 `SAFE TO FINALIZE`，独立复现 A.1=120、A.2=13、A.3=44、A.4=35、A.5=27、A.6 116/8065/`6c667...`、A.7 精确三路径及三项 Night manifest 登记。标准 finalize 完成，v5 contract frozen hash=`7a02675ea94dd9ef83f40df42889720998cbea0d8db26992d158bf3c78135ef4`；`--require-ready` 返回 `ok: true`，仅有继承 P4 的预期 ready warning。等待 package-only setup checkpoint。
- 2026-07-26T13:06:28+08:00 — v5 package-only setup checkpoint `ce4f9554db4fcdfa4699c70516d9a3497c565fc7` 已创建，直接父为 `f1dafeb32b08d24a6960f31d4a0f6d8820b95839`，提交只含 v5 `CONTRACT.md` 与 `START_HERE.md`；随后从最早未证明阶段 P5 恢复。
- 2026-07-26T15:10:00+08:00 — P5 删除前解耦完成：三个 A.7 tests 改为等强退休断言；活动引用/unknown 均为 0；exact manifest 1,386 files，Night/Bundle/old002837=`680/205/501`；全量 Git blob 恢复逐字节通过；V-003/V-004/V-005/V-006/V-008 和 full pytest `1349 passed, 2 skipped` 通过；独立质量审计 PASS。尚未 arm、删除、stage、push、PR 或发布，等待指定 decoupling checkpoint。
