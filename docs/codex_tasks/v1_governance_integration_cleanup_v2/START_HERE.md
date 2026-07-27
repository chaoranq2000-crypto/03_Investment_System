---
schema_version: "1"
task_id: "v1_governance_integration_cleanup_v2"
contract_path: "docs/codex_tasks/v1_governance_integration_cleanup_v2/CONTRACT.md"
contract_sha256: "c160ea2d676d5ba9a9893070be1a6e4418193cc508db07e71dd48cd0394a642f"
state: "blocked"
execution_branch: "codex/v1-governance-integration-cleanup"
source_baseline: "23fcd3b6b5ce3574661c4cfd306dadd782ad0717"
last_completed_phase: "P4"
next_phase: "P5"
last_validation: "fail"
updated_at: "2026-07-25T16:34:47+08:00"
---
# Start or resume this stage in a new Codex chat

本任务包是旧 v1 冻结包的 authorized amended v2。它只把 V-003 修正为 P1 七项、P2 八项、P3/final 九项的累加验证；发布模式 A、P1–P5、Night → Bundle11R–17R → old 002837 三个有序手动删除检查点和全部完成标准保持不变。只有 front matter 为 `state: ready`、启动块包含真实 contract hash 且 `--require-ready` 校验通过时才可启动。

最终 ready 后，在专用工作树 `C:\Projects\03_Investment_System_v1_governance_cleanup` 打开一个全新 Codex 聊天，并原样粘贴：

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/v1_governance_integration_cleanup_v2
Frozen contract: docs/codex_tasks/v1_governance_integration_cleanup_v2/CONTRACT.md
Expected contract SHA-256: c160ea2d676d5ba9a9893070be1a6e4418193cc508db07e71dd48cd0394a642f
Execution branch: codex/v1-governance-integration-cleanup
Source baseline: 23fcd3b6b5ce3574661c4cfd306dadd782ad0717
Engineering source candidate: f60f220ae252262a537c612ce193fc779901984b
Dedicated worktree: C:\Projects\03_Investment_System_v1_governance_cleanup

Read the complete applicable AGENTS.md instruction chain, CONTRACT.md, START_HERE.md, and every phase-required skill file before acting. Treat the frozen contract as the complete objective, constraints, authority, and definition of done. Do not rely on any previous chat, memory, project journal, Night queue, or unstated decision.

Validate package integrity and repository preflight, then resume from the earliest phase whose postconditions are not proven. After each phase, run its validators, inspect scope, update START_HERE.md, and create the specified Git checkpoint. Continue through P1-P5 until every completion criterion passes or a contract hard stop occurs.

Never edit the frozen contract, add phases, weaken a criterion, fabricate data or reviewer decisions, touch the user's dirty main worktree, perform recursive/bulk deletion, direct-push main, or publish beyond the authorization envelope. In P5, stop in order at the Night, Bundle, and old-002837 deletion waves with the exact per-file manifest; wait for the user to delete only that wave manually, then verify the complete Git status vector before continuing.
```

## Current checkpoint

- **State:** `blocked`
- **Last completed phase:** `P4`
- **Next phase:** `P5`
- **Latest validation:** P4 checkpoint `3741c807ae1d9859e8cb72d5e587a5bb74f2082e` 保持 clean，V-005、V-009 与 task-package integrity 的 P4 evidence 仍有效。P5 的静态引用图和 filtered-tree 诊断证明：若按合同删除 Night 与 old 002837，`tests/conftest.py`、V-003/V-005 点名测试及其他 full-pytest 测试会失败；修复这些路径又超出 P5 exact mutation set。
- **Current blocker:** 冻结合同同时要求：P5 只能修改五个 exact control files、O-005–O-008 新产物、readout/validation 和 `START_HERE.md`（第 180、207、214、301 行）；删除后 active code/tests/CI 对候选树物理读取为 0 且 full pytest 通过（第 299、305–315、331–354 行）。但 `tests/conftest.py` 直接导入待退役 Night03，`tests/test_r5_v1_blocker_root_cause_map.py` 与 `tests/test_r5_v1_active_control_plane.py` 直接读取 Night/Bundle，至少 56 个既有 tests 需要从 old 002837 物理解耦，其中 `tests/test_valuation_input_contract.py` 还会重新创建旧目录。这些既有路径不在 P5 exact mutation set，且不能通过 retain、skip、弱化测试或扩大 allowlist 合法解决。受影响阶段为 P5；受影响标准为 C-008、C-010、V-003、V-005、V-010；stop class 为 conflicting instructions / unverifiable completion criterion。没有 arm 任何删除波次。
- **Hard-stop recording paths:** `reports/p1_6/r5_v1_governance_cleanup/validation/p5_authority_conflict.yaml` 与本 `START_HERE.md`；没有其他 P5 mutation。
- **Recovery note:** filtered-tree 诊断错误继承了共享 Git 元数据，产生 12 个仅本地 fixture commits，并临时写入共享 `.git/config` 的 `core.worktree`/测试身份。执行分支和索引已精确恢复到 P4；三项测试配置已移除。用户主工作树的完整 preflight 向量再次精确匹配 130 行、9156 bytes、SHA-256 `0cc3779c1d4c8f91101526f2952b4b60c1ba1afd3d683c2cefdf127996070cb2`，tracked 向量精确匹配 20 行、1025 bytes、SHA-256 `b2d3c77f464c3c7fd23fdcdfe3f0583ea81c1f8af1f84492e3073ca7aa46ac02`；远端无 execution ref，`main` 未变化。
- **Next safe action:** 保留本 v2 冻结合同和 P4 checkpoint，准备并冻结 amended v3，逐项授权 P5 为满足 D-011/C-008/C-010 所必需修改的既有 tests/scripts/fixtures，并澄清 `test_r5_bundle*.py` 是否属于 Bundle basename allowlist；不得原地修改 v2 合同。精确 unblock 问题：用户是否授权准备上述 amended v3 task package？

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
