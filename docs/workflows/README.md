# Workflows — 永久工作流文档入口

`docs/workflows/` 只承载系统级 workflow 事实。

它不承载单个 skill 的完整执行契约，也不维护历史计划、执行日志或样例报告正文。

## Canonical workflow kernel

| 文件 | 定位 | 是否定义 global workflow facts |
|---|---|---:|
| `RESEARCH_WORKFLOW.md` | 唯一全局 workflow kernel；定义 `workflow_type`、全局阶段、全局 `gate_id`、回写决策、P2 前置条件 | 是 |
| `DATA_LAYER_WORKFLOW.md` | 数据层 workflow；定义 source adapter、archive、manifest、candidate、data pack 与 evidence-ingest 的边界 | 只定义 data-layer 事实 |

## Compatibility pointers

以下文件为兼容旧链接或迁移说明，不再定义新的 workflow facts：

| 文件 | 新事实源 |
|---|---|
| `WORKFLOW_ORCHESTRATION_SPEC.md` | `.agents/skills/research-orchestrator/references/orchestration_contract.md` for runtime contract；`RESEARCH_WORKFLOW.md` for global IDs |
| `STOCK_REPORT_PRODUCTION_WORKFLOW.md` | `.agents/skills/stock-deep-dive/references/report_production_profile.md` for stock report production profile；`RESEARCH_WORKFLOW.md` for `stock_first_closed_loop` |

## 与 skills 的关系

```text
docs/workflows/RESEARCH_WORKFLOW.md
    = 系统事实：workflow_type / stage / gate / backflow / P2 readiness

.agents/skills/research-orchestrator/SKILL.md
    = 执行入口：创建 run、更新状态、写 handoff、路由下层 skills、close readout

.agents/skills/<lower-skill>/SKILL.md
    = 下层执行契约：说明本 skill 何时使用、输入、局部步骤、输出、blocked 条件

.agents/skills/<skill>/references/
    = 字段、模板、runtime contract、局部 profile
```

## 不负责

本目录不负责：

```text
项目路线图
P0 / P1 / P1.5 / P2 / P3 阶段计划
单次执行 readout
某个细分或个股的研究报告
日常命令速查
单个 skill 的内部 schema 或模板
```

阶段计划放在 `docs/plans/`；日常提示放在 `docs/playbooks/`；执行日志放在 `docs/logs/`。

## 版本纪律

如果要改全局 ID：

```text
workflow_type
global stage_id
global gate_id
backflow_decision
run status enum
```

只改 `RESEARCH_WORKFLOW.md`，再让其他文件引用。

如果要改单个 skill 的执行细节，改该 skill 的 `SKILL.md` 或 `references/`，不要新增 workflow doc。
