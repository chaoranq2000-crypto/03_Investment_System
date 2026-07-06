# Docs / Skills Workflow 去重重构 Readout

Date: 2026-07-06

## 1. Summary

本次执行 `investment_system_doc_refactor_patch_20260706.zip`，目标是把 workflow facts 收敛到唯一 kernel：

```text
docs/workflows/RESEARCH_WORKFLOW.md = global workflow kernel
.agents/skills/<skill>/SKILL.md = local execution contract
.agents/skills/<skill>/references/ = runtime contract / local profile
```

本次未删除历史 `docs/plans/`、`docs/logs/`、`docs/codex_tasks/`，未修改样例个股报告观点，未新增研究结论或交易建议。

## 2. Files changed

核心 workflow / navigation：

- `README.md`
- `docs/index.md`
- `docs/meta/DOC_OWNERSHIP_MATRIX.md`
- `docs/meta/TOP_LEVEL_DOCS_INDEX.md`
- `docs/playbooks/OPERATING_PLAYBOOK.md`
- `docs/workflows/README.md`
- `docs/workflows/RESEARCH_WORKFLOW.md`
- `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md`
- `docs/workflows/STOCK_REPORT_PRODUCTION_WORKFLOW.md`

Skill contracts and references：

- `.agents/skills/research-orchestrator/SKILL.md`
- `.agents/skills/research-orchestrator/assets/workflow_state_template.yaml`
- `.agents/skills/research-orchestrator/references/skill_routing_matrix.md`
- `.agents/skills/research-orchestrator/references/workflow_state_schema.md`
- `.agents/skills/research-orchestrator/scripts/validate_workflow_state.py`
- `.agents/skills/stock-deep-dive/SKILL.md`
- `.agents/skills/quality-review/SKILL.md`
- `.agents/skills/quality-review/assets/stock_report_acceptance_checklist.yaml`
- `.agents/skills/quality-review/references/stock_report_quality_gates_v2.md`

Code / tests：

- `src/qa/stock_report_quality_review.py`
- `tests/test_data_layer_bridge_draft.py`
- `tests/test_data_layer_readiness_bridge.py`
- `tests/test_r4_publishable_stock_report_gate.py`
- `tests/test_stock_deep_dive_skill_merge.py`

Workflow run metadata only：

- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/artifact_manifest.csv`
- `reports/workflow_runs/wf_20260703_stock_first_002837_invic/workflow_readout.md`

## 3. Files created

- `docs/codex_tasks/TASK_DOCS_WORKFLOW_DEDUP_REFACTOR.md`
- `docs/codex_tasks/TASK_DOC_DRIFT_CHECK_SCRIPT.md`
- `docs/codex_tasks/TASK_DOCS_WORKFLOW_DEDUP_REFACTOR_READOUT.md`
- `.agents/skills/research-orchestrator/references/orchestration_contract.md`
- `.agents/skills/stock-deep-dive/references/report_production_profile.md`
- `scripts/check_doc_drift.py`

## 4. Compatibility pointers left in place

- `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md`
  - 保留旧链接。
  - 不再定义 `workflow_type`、global stage、global gate 或 run status。
  - runtime contract 迁到 `.agents/skills/research-orchestrator/references/orchestration_contract.md`。

- `docs/workflows/STOCK_REPORT_PRODUCTION_WORKFLOW.md`
  - 保留旧链接。
  - `stock_report_production` 降级为 `profile_id`。
  - profile 迁到 `.agents/skills/stock-deep-dive/references/report_production_profile.md`。

## 5. Before / after grep summary

Baseline before patch：

- `workflow_type:` 出现在 `research-orchestrator/SKILL.md`、`workflow_state_schema.md`、`workflow_state_template.yaml`、`WORKFLOW_ORCHESTRATION_SPEC.md`、`STOCK_REPORT_PRODUCTION_WORKFLOW.md` 和 workflow run artifacts。
- `stock_report_production` 被 `validate_workflow_state.py` 当作 valid workflow type，并在 `STOCK_REPORT_PRODUCTION_WORKFLOW.md` 中作为 workflow metadata。
- `G10/G11` 在 `quality-review/SKILL.md`、`stock_report_quality_gates_v2.md`、`stock_report_acceptance_checklist.yaml` 中作为局部门禁编号。
- `WORKFLOW_ORCHESTRATION_SPEC.md` 被 README、docs index、playbook、ownership matrix 等标为活跃编排事实源。

After patch：

```text
git grep -n "workflow_type: stock_report_production" -- . ':!docs/plans' ':!docs/logs'
=> no results
```

```text
git grep -n "G10\|G11" -- docs .agents ':!docs/plans' ':!docs/logs' ':!docs/codex_tasks' ':!docs/references/project_learning'
=> docs/workflows/RESEARCH_WORKFLOW.md: G10 Close Gate only
```

```text
python scripts/check_doc_drift.py
=> errors: 0, warnings: 14
```

Warnings are long-line warnings in pre-existing evidence-ingest fixtures and stock-report sample/source text files.

## 6. Acceptance checklist result

- [x] `RESEARCH_WORKFLOW.md` 明确是唯一 global workflow kernel。
- [x] `workflow_type` enum、global gate table、backflow decision、run status ownership 收敛到 kernel。
- [x] `stock_report_production` 不再作为 persisted `workflow_type`；保留为 `profile_id`。
- [x] `workflow_diagnostic` 降级为 non-run diagnostic mode。
- [x] `WORKFLOW_ORCHESTRATION_SPEC.md` 降级为 compatibility pointer。
- [x] `research-orchestrator/SKILL.md` 改为 thin execution contract。
- [x] `quality-review` 的 data-layer / R4 检查改为 `G7-DL` / `G7-R4` subcheck。
- [x] `docs/workflows/README.md`、`docs/index.md`、`TOP_LEVEL_DOCS_INDEX.md` 导航边界已更新。
- [x] drift 检查脚本已实现。
- [x] 未删除历史 plans/logs/codex_tasks。
- [x] 未新增买入 / 卖出 / 持有建议。

Validation commands：

```text
conda run -p .\.conda\investment-system python scripts/check_doc_drift.py
=> errors: 0, warnings: 14

conda run -p .\.conda\investment-system python .\.agents\skills\research-orchestrator\scripts\validate_workflow_state.py .\reports\workflow_runs\wf_20260703_stock_first_002837_invic\workflow_state.yaml
=> OK

conda run -p .\.conda\investment-system python -m py_compile scripts\check_doc_drift.py src\qa\stock_report_quality_review.py .agents\skills\research-orchestrator\scripts\validate_workflow_state.py
=> pass

conda run -p .\.conda\investment-system python -m pytest -q
=> 109 passed, 2 skipped

git diff --check
=> no whitespace errors; Git reported LF-to-CRLF conversion warnings only
```

## 7. Remaining TODOs

| issue_id | severity | owner | next_action |
|---|---|---|---|
| docs_drift_warn_001 | low | evidence-ingest / docs maintainer | 可选：单独格式化 evidence-ingest fixture 与样例 source text 的超长物理行；本轮不改样例报告观点。 |
| docs_learning_refresh_001 | low | docs maintainer | 可选：另开任务刷新 `docs/references/project_learning/` 中关于旧 workflow docs 的学习讲解；本轮 drift check 已将其视为生成型学习材料而非活跃事实源。 |
