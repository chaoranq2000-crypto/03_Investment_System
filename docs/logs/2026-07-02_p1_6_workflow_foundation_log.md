# 2026-07-02 P1.6 Workflow Foundation Log

## date

2026-07-02

## scope

P1.6 workflow foundation / research workflow orchestration.

## status

PASS

本次将根目录补丁包 `research_workflow_foundation_patch.zip` 中的正式工作流基础设施落地到仓库，用于在进入 P2 前固化“永久工作流事实源”和总编排 skill。当前变更不进入 P2，不生成新的投资结论，不包含买卖建议。

## changed_paths

新增：

- `.agents/skills/research-orchestrator/SKILL.md`
- `.agents/skills/research-orchestrator/references/skill_routing_matrix.md`
- `.agents/skills/research-orchestrator/references/workflow_state_schema.md`
- `.agents/skills/research-orchestrator/assets/workflow_state_template.yaml`
- `.agents/skills/research-orchestrator/assets/handoff_template.md`
- `.agents/skills/research-orchestrator/scripts/validate_workflow_state.py`
- `.codex/config.research_orchestrator.snippet.toml`
- `docs/workflows/README.md`
- `docs/workflows/RESEARCH_WORKFLOW.md`
- `docs/workflows/WORKFLOW_ORCHESTRATION_SPEC.md`
- `docs/plans/P1_6_WORKFLOW_BUILDOUT_PLAN.md`
- `docs/logs/2026-07-02_p1_6_workflow_foundation_log.md`

修改：

- `.codex/config.toml`
- `docs/index.md`

未纳入正式提交：

- `research_workflow_foundation_patch.zip`：补丁包原件，保留在本地根目录，未作为正式仓库产物提交。

## summary

本次新增 `docs/workflows/` 作为永久工作流事实源层，明确 segment-led、stock-led、segment-stock interlock、refresh 和 comparison readiness gate 的边界。

新增 `.agents/skills/research-orchestrator/` 作为总编排 skill。该 skill 负责识别 workflow 类型、维护 workflow state、路由下层 skills、生成 handoff、执行质量门和 close readout；它不替代下层 research skills，也不直接产出未审查的研究结论。

新增 `docs/plans/P1_6_WORKFLOW_BUILDOUT_PLAN.md` 作为后续 P1.6 建设计划，用于指导逐个补强下层 workflow / skills、复跑 segment-led、调试 stock-led 和 interlock，并在最后形成 P2 readiness gate。

## verification

已执行：

```text
conda run -p .\.conda\investment-system python -m py_compile .\.agents\skills\research-orchestrator\scripts\validate_workflow_state.py
```

结果：通过。

已执行：

```text
conda run -p .\.conda\investment-system python .\.agents\skills\research-orchestrator\scripts\validate_workflow_state.py .\.agents\skills\research-orchestrator\assets\workflow_state_template.yaml
```

结果：

```text
OK: .agents\skills\research-orchestrator\assets\workflow_state_template.yaml
```

已执行：

```text
conda run -p .\.conda\investment-system python -m pytest -q
```

结果：

```text
23 passed
```

## quality_notes

- `workflow_state_template.yaml` 原始补丁中 `workflow_type` 为空，无法通过校验器；已将模板默认值修正为合法的 `workflow_diagnostic` 占位样例。
- `py_compile` 产生的 `__pycache__` 已逐个明确路径清理，没有使用递归删除命令。
- `.env.local`、`.conda/`、`.pytest_cache/`、`docs/playbooks/tushare_configuration_guide.pdf` 已确认受 `.gitignore` 保护。

## open_risks

- `research_workflow_foundation_patch.zip` 仍作为本地未跟踪文件保留在根目录；若需要清理，应由用户确认后按单个明确路径删除。
- P1.6 计划仍需后续逐个补强下层 skills，并通过 segment-led、stock-led、interlock 三类调试后，才可执行 P2 readiness gate。
