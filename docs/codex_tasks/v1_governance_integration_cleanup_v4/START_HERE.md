---
schema_version: "1"
task_id: "v1_governance_integration_cleanup_v4"
contract_path: "docs/codex_tasks/v1_governance_integration_cleanup_v4/CONTRACT.md"
contract_sha256: "c806d4811e4f40ffb86154c6144c75173c7d13e1fc193f9add07686495217736"
state: "ready"
execution_branch: "codex/v1-governance-integration-cleanup"
source_baseline: "312adc73821706b0b7ca6aa00e80ee608bd10b32"
last_completed_phase: "P4"
next_phase: "P5"
last_validation: "pass"
updated_at: "2026-07-26T11:27:50+08:00"
---
# Start or resume this stage in a new Codex chat

本任务包是冻结 v3 的 authorized amended v4。它只闭合 v3 post-freeze 审计证明的 8 个必写路径遗漏，并把 active literal、retained capability dependency 与只读历史字面 archive 分为 A.4/A.5/A.6 三类。P1–P4 结论、P1–P5 数量、完成标准、发布模式 A、Night → Bundle11R–17R → old 002837 三个有序手动删除检查点和全部验证强度保持不变。只有 front matter 为 `state: ready`、启动块包含真实 contract hash 且 `--require-ready` 校验通过时才可启动。

最终 ready 后，在专用工作树 `C:\Projects\03_Investment_System_v1_governance_cleanup` 打开一个全新 Codex 聊天，并原样粘贴：

```text
/goal

Use $autonomous-stage-runner in execute mode.

Task package: docs/codex_tasks/v1_governance_integration_cleanup_v4
Frozen contract: docs/codex_tasks/v1_governance_integration_cleanup_v4/CONTRACT.md
Expected contract SHA-256: c806d4811e4f40ffb86154c6144c75173c7d13e1fc193f9add07686495217736
Execution branch: codex/v1-governance-integration-cleanup
Source baseline: 312adc73821706b0b7ca6aa00e80ee608bd10b32
Engineering source candidate: f60f220ae252262a537c612ce193fc779901984b
Dedicated worktree: C:\Projects\03_Investment_System_v1_governance_cleanup

Read the complete applicable AGENTS.md instruction chain, CONTRACT.md, START_HERE.md, and every phase-required skill file before acting. Treat the frozen contract as the complete objective, constraints, authority, and definition of done. Do not rely on any previous chat, memory, project journal, Night queue, or unstated decision.

Validate package integrity and repository preflight, then resume from the earliest phase whose postconditions are not proven. After each phase, run its validators, inspect scope, update START_HERE.md, and create the specified Git checkpoint. Continue through P1-P5 until every completion criterion passes or a contract hard stop occurs.

Never edit the frozen contract, add phases, weaken a criterion, fabricate data or reviewer decisions, touch the user's dirty main worktree, perform recursive/bulk deletion, direct-push main, or publish beyond the authorization envelope. In P5, stop in order at the Night, Bundle, and old-002837 deletion waves with the exact per-file manifest; wait for the user to delete only that wave manually, then verify the complete Git status vector before continuing.
```

## Current checkpoint

- **State:** `ready`
- **Last completed phase:** `P4`
- **Next phase:** `P5`
- **Latest validation:** `pass`
- **Current blocker:** none。v4 已冻结并通过 `--require-ready`；须先创建以 `312adc73821706b0b7ca6aa00e80ee608bd10b32` 为直接父提交且只新增本包两个文件的 setup checkpoint，随后复核 P1–P4 postconditions 并把本文件切换为 P5 running。
- **Prior hard-stop evidence:** v2 `reports/p1_6/r5_v1_governance_cleanup/validation/p5_authority_conflict.yaml` 与 v3 frozen package 保持只读。v3 blocker package checkpoint 为 `312adc73821706b0b7ca6aa00e80ee608bd10b32`；P5 尚未开始，也没有 arm 任何删除波次。
- **User-main protection snapshot:** HEAD `a345fafb522300831ed4206d35fa17f44570cb1f`；用户在获知外部漂移只来自 untracked 状态后明确回复“继续，以新快照为基线”。连续稳定的新完整 `porcelain=v1 -z -uall` 向量为 130 records、9156 bytes、SHA-256 `1b21ac246cb2ad4b055f5a264503fb1fad8fe9edae153e25c9cd6d19d4a719c0`；tracked-only 仍为 20 records、1025 bytes、SHA-256 `3ab441f68037823866029eb2136149a807f6382755966daf96d33a85b965609b`。任务从未触碰该树；不得清理、修复、吸收或提交其中内容。
- **Next safe action:** 显式暂存本包 `CONTRACT.md` 与 `START_HERE.md`，审计 cached diff 后创建 package-only v4 setup checkpoint。

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
